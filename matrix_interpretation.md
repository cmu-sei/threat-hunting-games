Summary of my Understanding of Chris's Matrix Game Example
==========================================================

| Cost       |       -10 |           | 
| Def loss   |       -10 |           | 
| Att gain   |       -10 |           | 
| Att fast   |       -10 |           | 
| Att slow   |        -5 |           | 
|            |           |           |
| Defender   | Fast      | Slow      |
|          1 |       -50 |       -50 |
|          2 |       -50 |       -40 |
|          3 |       -50 |       -40 |
|          4 |       -40 |       -30 |
|          5 |       -40 |       -30 |
|            |           |           |
| Attacker   | Fast      | Slow      |
|          1 |       -10 |        -5 |
|          2 |         0 |        -5 |
|          3 |        10 |         5 |
|          4 |        10 |         5 |
|          5 |        20 |        15 |

Guide
-----

These notes have been reconstructed from more raw (and likely
incomplete) notes from the meeting on 09/14/2023. Items with uncertain
explanations will be noted. Items that have not been noted as uncertain
might still be completely wrong assumptions.

* The transcribed matrices above represent an individual tab/sheet in
  the overall spreadsheet document -- each tab has different
  cost/reward structures (i.e. a different game with different rules)

* The matrix represents many iterations (or episodes) of a
  particular game with specific parameters. (as opposed to a single
  run of the game)

* For our game, the matrix is broken out with two sets of parameters.
  The cost and reward structures are separate from the policies (or
  strategies).
  - The cost/reward structures essentially define a new game.
  - Within that game, different policies are simulated (for both the
    attacker and the defender).

* In the above matrix representation:
  - Then there are two matrices, one for the defender and one for
    the attacker.
  - The values above the two matrices represent the cost/reward
    structures.
    - `Cost` and `Def loss` are used in various formulations to populate
      the Defender matrix. Are these formulations arbitrary? (see the
      formulas in the actual spreadsheet)
      - In this matrix, there are no rewards for the defender.
    - `Att gain`, `Att fast`, and `Att slow` are used in the
      formulations to populate the Attacker matrix. The latter two are
      costs, the first one is the reward. Again, are the formulas
      arbitrary or carefully selected?
    - However, in the matrices we generate, these values above the
      matrices are indeterminant, particularly for the defender,
      depending on how many turns each game takes and whether or not
      WAIT, IN_PROGRESS, and USE_CHANCE_FAIL are enabled. Therefore the
      values within each matrix are purely empirical results gathered
      from the simulations.
  - The columns in each matrix represent the attacker policies -- in
    this case, `fast` and `slow`. There can be more columns if there are
    more attacker policies.
    - In the above example, `Fast` and `Slow` are tags for entire
      policies, not individual action types; actions can be a grab bag
      within each policy depending on how it is defined. More attacker
      policies mean more columns.
  - The rows in each matrix represent the varying policies
    of the defender. More defender policies mean more rows.
  - The values in the matrices are the returns (payouts) for each
    player, respectively.
  - The values represent the results from (possibly) many iterations
    of the game.
    - Are they raw totals or averaged? Does it matter?

* *(unclear)* In the spreadsheet, the matrix values are calculated with
  formulas that use the cost/reward values at the top of the
  spreadsheet. How exactly would we represent our v6 game in this
  format? How do per-action costs/rewards get represented in those
  values at the top? In the v6 game, the total returns (losses) for the
  defender can be highly variable. So...this is the question -- how do
  we generate these matrices using our current game?
