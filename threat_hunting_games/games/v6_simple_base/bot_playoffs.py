#!/bin/env python3

import os, sys, json, csv
import argparse
import collections
import openpyxl
import numpy as np
from datetime import datetime
from dataclasses import dataclass

import pyspiel
from open_spiel.python.bots.policy import PolicyBot

import arena, policies, util
from threat_hunting_games import games
from arena import debug
from sheets import Sheet


@dataclass
class Defaults:
    game: str = "chain_game_v6_seq"
    iterations: int = 1000

    use_waits: bool = arena.USE_WAITS
    use_timewaits: bool = arena.USE_TIMEWAITS
    use_chance_fail: bool = arena.USE_CHANCE_FAIL

    attacker_policies: tuple = (
        "first_action",
        "uniform_random",
        "last_action",
    )

    dump_dir: str = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "dump_playoffs")

DEFAULTS = Defaults()


def _relpath(path):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.relpath(path, base_dir)

def play_game(game, bots):
    # play one game
    state = game.new_initial_state()
    history = []
    sc = 0
    while not state.is_terminal():
        sc += 1
        player = state.current_player()
        bot = bots[player]
        action = bot.step(state)
        debug("BOT ACTION:", action)
        player_str = arena.player_to_str(player)
        action_str = arena.a2s(action)
        debug(f"Player {player_str} sampled action: {action_str}")
        # convert to int; json.dump() can't dump int64
        history.append(int(action))
        state.apply_action(action)
    returns = state.returns()
    debug("Returns:", " ".join(map(str, returns)))
    return state.turns_played(), returns, state.victor(), history

def permutations(attacker_policies=None, attacker_all=False):
    """
    It's important to interate over advancement rewards and detection
    costs first since these are the keys for a matrix (i.e. a csv file
    or a sheet in excel.
    """
    if not attacker_all and not attacker_policies:
        attacker_policies = DEFAULTS.attacker_policies
    for advancement_rewards in arena.list_advancement_utilities():
        for detection_costs in arena.list_detection_utilities():
            for def_policy, def_ap in policies.list_policies_with_pickers():
                for atk_policy, atk_ap \
                        in policies.list_policies_with_pickers():
                    if not attacker_all and \
                            atk_policy not in attacker_policies:
                        continue
                    yield (advancement_rewards, detection_costs,
                            def_policy, def_ap, atk_policy, atk_ap)

def main(game_name=DEFAULTS.game,
        iterations=DEFAULTS.iterations,
        attacker_policies=None,
        attacker_all=False,
        use_waits=DEFAULTS.use_waits,
        use_timewaits=DEFAULTS.use_timewaits,
        use_chance_fail=DEFAULTS.use_chance_fail,
        dump_dir=None, dump_games=None):
    if not iterations:
        iterations = DEFAULTS.iterations
    if not attacker_all and not attacker_policies:
        attacker_policies = DEFAULTS.attacker_policies
    perms_seen = set()
    perm_total = 0
    perm_total = len(list(permutations(
        attacker_policies=attacker_policies, attacker_all=attacker_all)))
    perm_fmt = f"permutation.%0{len(str(perm_total))}d"
    timestamp = None
    dump_pm = json_dump_dir = csv_dump_dir = None
    xls_file = xls_workbook = None
    sheet_key = row_key = col_key = None
    csv_file = None
    sheet = None
    xls_sheet = None
    if dump_dir:
        dump_pm = util.PathManager(base_dir=dump_dir,
                game_name=game_name)
        timestamp = dump_pm.timestamp
        if not os.path.exists(dump_pm.path()):
            os.makedirs(dump_pm.path())
        json_dump_dir = dump_pm.path(suffix="json")
        if not os.path.exists(json_dump_dir):
            os.makedirs(json_dump_dir)
        csv_dump_dir = dump_pm.path(suffix="csv")
        if not os.path.exists(csv_dump_dir):
            os.makedirs(csv_dump_dir)
        xls_file = f"{game_name}-{timestamp}.xlsx"
        xls_file = os.path.join(dump_pm.path(), xls_file)
        xls_workbook = openpyxl.Workbook()
        del xls_workbook["Sheet"]
    perm_cnt = sheet_cnt = 0
    for adv_rewards, det_costs, def_policy, def_ap, atk_policy, atk_ap  \
            in permutations(attacker_policies=attacker_policies,
                    attacker_all=attacker_all):
        def _preamble():
            rows = []
            a_policy = '-'.join([atk_policy, atk_ap])
            d_policy = '-'.join([def_policy, def_ap])
            rows.append(["Episodes:", iterations])
            rows.append(["Use Waits:", "yes" if use_waits else "no"])
            rows.append(["Use Timewaits:", "yes" if use_timewaits else "no"])
            rows.append(["Use Chance Fail:",
                "yes" if use_chance_fail else "no"])
            rows.append([])
            rows.append(["Advancement Rewards:", adv_rewards,
                "Detection Costs:", det_costs])
            rows.append(["attacker policy:", a_policy,
                "defender policy:", d_policy])
            rows.append([])
            rows.append(["attacker", "defender"])
            utilities = arena.Utilities(advancement_rewards=adv_rewards,
                    detection_costs=det_costs)
            max_util_len = max([len(utilities.attacker_utilities),
                len(utilities.defender_utilities)])
            util_rows = []
            for i in range(max_util_len):
                util_rows.append([])
            for i, action in enumerate(sorted(utilities.attacker_utilities)):
                utils = utilities.attacker_utilities[action]
                utils = ','.join(str(x) for x in utils)
                util_rows[i].extend([arena.a2s(action), utils])
            for i, action in enumerate(sorted(utilities.defender_utilities)):
                utils = utilities.defender_utilities[action]
                utils = ','.join(str(x) for x in utils)
                util_rows[i].extend([arena.a2s(action), utils])
            rows.extend(util_rows)
            return rows
        key = (adv_rewards, det_costs, def_policy,
                def_ap, atk_policy, atk_ap,)
        if xls_file and not sheet_key:
            # first iteration, initialize
            sheet_key = (adv_rewards, det_costs)
            sheet = Sheet(sheet_key, preamble=_preamble())
        if xls_file and sheet_key != (adv_rewards, det_costs):
            # when sheet_key expires, dump csv, create new xls_sheet
            sheet_cnt += 1

            csv_file = f"{csv_dump_dir}/{'-'.join(sheet_key)}.csv"
            print(f"\nDumped {sheet_key} CSV to:", _relpath(csv_file))
            with open(csv_file, 'w', newline='') as fh:
                writer = csv.writer(fh)
                sheet.dump_csv(writer)

            xls_sheet = xls_workbook.create_sheet(sheet.name)
            sheet.dump_xlsx(xls_sheet)
            xls_workbook.save(xls_file)
            print(f"Saved excel sheet {sheet_key} in:",
                    _relpath(xls_file), "\n")

            sheet_key = (adv_rewards, det_costs)
            sheet = Sheet(sheet_key, preamble=_preamble())
        if sheet:
            row_key = def_policy
            row_key = (def_policy, def_ap)
            col_key = (atk_policy, atk_ap)
        perm_cnt += 1
        dd_pm = json_perm_dir = games_dir = None
        if dump_dir:
            if not dd_pm:
                json_dump_pm = util.PathManager(
                    base_dir=json_dump_dir,
                    detection_costs=f"det_costs_{det_costs}",
                    advancement_rewards=f"adv_rewards_{adv_rewards}",
                    timestamp=timestamp)
            if dump_games:
                json_perm_dir = os.path.join(json_dump_pm.path(),
                        perm_fmt % perm_cnt)
                games_dir = os.path.join(json_perm_dir, "games")
                if not os.path.exists(games_dir):
                    os.makedirs(games_dir)
            else:
                json_perm_dir = json_dump_pm.path()
            if not os.path.exists(json_perm_dir):
                os.makedirs(json_perm_dir)

        # load_game does not accept bools
        game = pyspiel.load_game(game_name, {
            "advancement_rewards": adv_rewards,
            "detection_costs": det_costs,
            "use_waits": int(use_waits),
            "use_timewaits": int(use_timewaits),
            "use_chance_fail": int(use_chance_fail),
        })
        utilities = arena.Utilities(
                advancement_rewards=adv_rewards,
                detection_costs=det_costs)
        def_bot = util.get_player_bot(game,
                arena.Players.DEFENDER,
                def_policy, action_picker=def_ap)
        atk_bot = util.get_player_bot(game,
                arena.Players.ATTACKER,
                atk_policy, action_picker=atk_ap)
        bots = {
            arena.Players.DEFENDER: def_bot,
            arena.Players.ATTACKER: atk_bot,
        }
        histories = collections.defaultdict(int)
        sum_returns = [0, 0]
        sum_normalized_returns = [0, 0]
        sum_victories = [0, 0]
        sum_inconclusive = 0
        iter_fmt = f"%0{len(str(iterations))}d.json"
        game_num = 0
        for _ in range(iterations):
            game_num += 1
            turns_played, returns, victor, history \
                    = play_game(game, bots)
            histories[" ".join(str(int(x))
                for x in history)] += 1
            for i, v in enumerate(returns):
                sum_returns[i] += v
            victor = int(victor) if victor is not None \
                    else victor
            if victor == int(arena.Players.ATTACKER):
                sum_victories[0] += 1
            elif victor == int(arena.Players.DEFENDER):
                sum_victories[1] += 1
            else:
                sum_inconclusive += 1
            if dump_games and games_dir:
                dump = {
                    "returns": returns,
                    "victor": victor,
                    "max_turns": game.get_parameters()["num_turns"],
                    "turns_played": turns_played,
                    "history": history,
                }
                df = os.path.join(games_dir, iter_fmt % game_num)
                with open(df, 'w') as dfh:
                    json.dump(dump, dfh, indent=2)
        if sheet:
            # make sure row/col exist
            sheet.atk_matrix.row(row_key)
            sheet.atk_matrix.col(col_key)
            sheet.def_matrix.row(row_key)
            sheet.def_matrix.col(col_key)
            # accumulate returns
            sheet.atk_matrix[row_key][col_key] += sum_returns[0]/iterations
            sheet.def_matrix[row_key][col_key] += sum_returns[1]/iterations
        def_policy_str = def_policy
        if not def_ap:
            cls = policies.get_policy_class(def_policy)
            if hasattr(cls, "default_action_picker"):
                def_ap = cls.default_action_picker()
        if def_ap:
            def_policy_str += f"/{def_ap}"
        atk_policy_str = atk_policy
        if not atk_ap:
            cls = policies.get_policy_class(atk_policy)
            if hasattr(cls, "default_action_picker"):
                atk_ap = cls.default_action_picker()
        if atk_ap:
            atk_policy_str += f"/{atk_ap}"
        print(f"\nPermutation {perm_cnt}/{perm_total}:")
        print(f"Advancement rewards: {adv_rewards}")
        print(f"Detection costs: {det_costs}")
        print(f"Defender policy: {def_policy_str}")
        print(f"Attacker policy: {atk_policy_str}")
        print("Number of games played:", game_num)
        print("Number of distinct games played:", len(histories))
        if json_perm_dir:
            r_means = [x / game_num for x in sum_returns]
            max_atk_util = utilities.max_atk_utility()
            scale_factor = 100 / max_atk_util
            sum_normalized_returns = [x * scale_factor for x in sum_returns]
            r_means_normalized = \
                    [x / game_num for x in sum_normalized_returns]
            dump = {
                "episodes": game_num,
                "sum_returns": sum_returns,
                "sum_victories": sum_victories,
                "sum_inconclusive": sum_inconclusive,
                "r_means": r_means,
                "max_atk_util": max_atk_util,
                "sum_normalized_returns": sum_normalized_returns,
                "r_means_normalized": r_means_normalized,
                "max_turns": game.get_parameters()["num_turns"],
                "defender_policy": def_policy,
                "defender_action_picker": def_ap or "n/a",
                "attacker_policy": atk_policy,
                "attacker_action_picker": atk_ap or "n/a",
                "advancement_rewards": adv_rewards,
                "detection_costs": det_costs,
                "use_waits": use_waits,
                "use_timewaits": use_timewaits,
                "use_chance_fail": use_chance_fail,
                "player_map": arena.player_map(),
                "action_map": arena.action_map(),
                "utilities": utilities.tupleize(),
            }
            histories = list(reversed(sorted((y, x)
                for x, y in histories.items())))
            dump["history_tallies"] = histories
            if dump_games:
                summary_file = os.path.join(json_perm_dir, "summary.json")
            else:
                summary_file = f"{perm_fmt % perm_cnt}.json"
                summary_file = os.path.join(json_dump_pm.path(), summary_file)
            with open(summary_file, 'w') as dfh:
                json.dump(dump, dfh, indent=2)
            if dump_games:
                print(f"Dumped {game_num} game playthroughs into: {_relpath(json_perm_dir)}")
            else:
                print(f"Dumped summary of {game_num} game playthroughs into: {_relpath(summary_file)}")
    if dump_dir:
        print()
        print(f"\nSaved {sheet_cnt} CSV matrices in {_relpath(csv_dump_dir)}")
        print(f"Saved {sheet_cnt} excel matrices in {_relpath(xls_file)}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Bot Policy Playthrough",
        description=f"Play through {DEFAULTS.iterations} of game "
                      "{DEFAULTS.game} using player bots for each permutation "
                      "of possible policies and cost/reward structures "
                      "and save the resulting statisistics.")
    #parser.add_argument("-g", "--game", default=DEFAULTS.game,
    #        description="Name of game to play"
    parser.add_argument("-i", "--iterations", default=DEFAULTS.iterations,
            type=int,
            help=f"Number of games per policy permutation to play. ({DEFAULTS.iterations})")
    parser.add_argument("--attacker-all-policies", "--aap", action="store_true",
            help="Permute using all available policies (and action pickers) for attacker rather than just uniform_random.")
    help_str = "WAIT as a possible action for both players."
    if DEFAULTS.use_waits:
        parser.add_argument("--no-waits", action="store_true",
                help=f"Exclude {help_str}")
    else:
        parser.add_argument("--use-waits", action="store_true",
            help=f"Include {help_str}")
    help_str = "IN_PROGRESS actions (random within a range hard   coded in arena.py per action) prior to finalizing an action."
    if DEFAULTS.use_timewaits:
        parser.add_argument("--no-timewaits", action="store_true",
                help=f"Exclude {help_str}")
    else:
        parser.add_argument("--use-timewaits", action="store_true",
                help=f"Include {help_str}")
    help_str = "general percent failure for actions as well as a p  ercent failure for actions applied to their corresponding action of the other   player (percentages hard coded in arena.py)."
    if DEFAULTS.use_chance_fail:
        parser.add_argument("--no-chance-fail", action="store_true",
                help=f"Disable using a {help_str}")
    else:
        parser.add_argument("--use-chance-fail", action="store_true",
                help=f"Use a {help_str}")
    parser.add_argument("-d", "--dump-dir", default=DEFAULTS.dump_dir,
            help=f"Directory in which to dump game states over iterations of the game. ({DEFAULTS.dump_dir})")
    parser.add_argument("-g", "--dump-games", action="store_true",
            help="If dumping, also dump individual game runs along with the summaries for each perumutation of cost/reward models and policy variations.")
    parser.add_argument("-n", "--no-dump", action="store_true",
            help="Disable logging of game playthroughs. (primarily for debugging)")
    args = parser.parse_args()
    if args.no_dump:
        args.dump_dir = None
        args.dump_games = None
    try:
        use_waits = args.use_waits
    except AttributeError:
        use_waits = not args.no_waits
    try:
        use_timewaits = args.use_timewaits
    except AttributeError:
        use_timewaits = not args.no_timewaits
    try:
        use_chance_fail = args.use_chance_fail
    except AttributeError:
        use_chance_fail = not args.no_chance_fail
    main(
        game_name=DEFAULTS.game,
        iterations=args.iterations,
        attacker_all=args.attacker_all_policies,
        use_waits=use_waits,
        use_timewaits=use_timewaits,
        use_chance_fail=use_chance_fail,
        dump_dir = args.dump_dir,
        dump_games = args.dump_games,
    )
