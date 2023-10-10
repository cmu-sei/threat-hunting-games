import sys
import itertools
import pyspiel
import numpy as np
import nashpy
from open_spiel.python.algorithms import lp_solver
from open_spiel.python.algorithms import matrix_nash

# Much of this code was derived from OpenSpiel's matrix_nash_example.py

import arena

class Solver:


    solvers = (
        "pure",
        "linear",
        "lrsnash",
        "nashpy_vertex_enumeration",
        "nashpy_lemkey_howson",
    )

    def __init__(self, sheet, tol=1e-7, lrsnash_max_denom=1000,
            lrsnash_path=None):
        """
        tol: olerance for determining dominance.

        lrsnash_path: Full path to lrsnash solver (searches PATH
        by default).

        lrsnash_max_denom: Maximum denominator to use when converting
        payoffs to rationals for lrsnash solver.
        """
        self._sheet = sheet
        self._tol = tol
        self._lrsnash_max_denom = lrsnash_max_denom
        self._lrsnash_path = lrsnash_path
        self._row_payoffs, self._col_payoffs = sheet.as_tensor()
        self._num_rows = sheet.num_rows
        self._num_cols = sheet.num_cols
        self._row_labels = tuple(sheet.def_policies)
        self._col_labels = tuple(sheet.atk_policies)

    def solve(self, nashpy_lemkey_howson=True, pure=False,
            linear=False, lrsnash=False, nashpy_vertex_enumeration=False):
        solutions = {}
        if pure:
            print("\nSolving for pure equilbria...")
            solutions["pure"] = self.solve_pure()
            print("pure", type(solutions["pure"]))
        if linear:
            print("\nSolving for linear equilbria...")
            solutions["linear"] = self.solve_linear()
            print("pure", type(solutions["linear"]))
        if lrsnash:
            print("\nSolving for lrsnash equilbria...")
            solutions["lrsnash"] = self.solve_lrsnash()
            print("lrsnash", type(solutions["lrsnash"]))
        if nashpy_vertex_enumeration:
            print("\nSolving for nashpy_vertex_enumeration equilbria...")
            solutions["nashpy_vertex_enumeration"] = \
                    self.solve_nashpy_vertex_enumeration()
            print("nashpy_vertex_enumeration", type(solutions["nashpy_vertex_enumeration"]))
        if nashpy_lemkey_howson:
            print("\nSolving for nashpy_lemkey_howson...")
            try:
                solutions["nashpy_lemkey_howson"] = \
                        self.solve_nashpy_lemkey_howson()
                print("nashpy_lemkey_howson", type(solutions["nashpy_lemkey_howson"]))
            except ValueError as e:
                print(e)
            if "nashpy_lemkey_howson" not in solutions:
                print("\nnashpy_lemkey_hoson had some problems, running the entire script again will probably work\n")
                sys.exit(1)
        labels = {
            "rows": self._row_labels,
            "cols": self._col_labels,
        }
        return solutions, labels

    def solve_pure(self):
        pure_nash = list(
            zip(*(
                (self._row_payoffs >= \
                        self._row_payoffs.max(0, keepdims=True) - self._tol)
                 & (self._col_payoffs >= self._col_payoffs.max(1,
                     keepdims=True) - self._tol)).nonzero()))
        if not pure_nash:
            print("No pure equilibria found")
            return None
        payoffs = []
        for row, col in pure_nash:
            payoffs.append((self._row_payoffs[row, col],
                self._col_payoffs[row, col]))
        return tuple(payoffs)

    def solve_linear(self):
        if (self._row_payoffs + self._col_payoffs).max() > \
                (self._row_payoffs + self._col_payoffs).min() + self._tol:
            print("Can't use linear solver for non-constant-sum game or "
                       "for finding all optima with lenear solver")
            return None

        def gen():
            p0_sol, p1_sol, _, _ = lp_solver.solve_zero_sum_matrix_game(
                pyspiel.create_matrix_game(
                    self._row_payoffs - self._col_payoffs,
                    self._col_payoffs - self._row_payoffs))
            yield (np.squeeze(p0_sol, 1), np.squeeze(p1_sol, 1))

        equilibria = gen()
        return self._equilibria_to_payoffs(equilibria)

    def solve_lrsnash(self):
        equilibria = matrix_nash.lrs_solve(
                self._row_payoffs, self._col_payoffs,
                self._lrsnash_max_denom, self._lrsnash_path)
        payoffs = self._equilibria_to_payoffs(equilibria)
        if not payoffs:
            print("No equilibria found using lrsnash")
        return payoffs

    def solve_nashpy_vertex_enumeration(self):
        equilibria = nashpy.Game(self._row_payoffs,
                         self._col_payoffs).vertex_enumeration()
        payoffs = self._equilibria_to_payoffs(equilibria)
        if not payoffs:
            print("No equilibria found using nashpy vertex enumeration")
        return payoffs

    def solve_nashpy_lemkey_howson(self):
        equilibria = matrix_nash.lemke_howson_solve(
                        self._row_payoffs, self._col_payoffs)
        payoffs = self._equilibria_to_payoffs(equilibria)
        if not payoffs:
            print("No equilibria found using nashpy lemkey howson")
        return payoffs

    def _equilibria_to_payoffs(self, equilibria):
        equilibria = iter(equilibria)
        payoffs = []
        try:
            equilibria = itertools.chain([next(equilibria)], equilibria)
        except StopIteration:
            return None
        for row_mixture, col_mixture in equilibria:
            payoffs.append(
                (row_mixture.dot(self._row_payoffs.dot(col_mixture)),
                    row_mixture.dot(self._col_payoffs.dot(col_mixture)),
                    row_mixture, col_mixture))
        return payoffs
