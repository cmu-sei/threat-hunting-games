#!/bin/env python3

import os, sys, json
import argparse
import collections
import numpy as np
from datetime import datetime
from dataclasses import dataclass

import pyspiel
from open_spiel.python.bots.policy import PolicyBot
#from policy import PolicyBot

import arena, policies, util
from threat_hunting_games import games
from arena import debug


@dataclass
class Defaults:
    game: str = "chain_game_v6_seq"
    iterations: int = 1000

    use_waits: bool = arena.USE_WAITS
    use_timewaits: bool = arena.USE_TIMEWAITS
    use_chance_fail: bool = arena.USE_CHANCE_FAIL

    dump_dir: str = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "dump_playoffs")

DEFAULTS = Defaults()


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

def permutations(attacker_all=False):
    for def_policy, def_ap in policies.list_policies_with_pickers():
        for atk_policy, atk_ap in policies.list_policies_with_pickers():
            if not attacker_all and atk_policy != "uniform_random":
                continue
            for detection_costs in arena.list_detection_utilities():
                for advancement_rewards in arena.list_advancement_utilities():
                    yield (def_policy, def_ap, atk_policy, atk_ap,
                            detection_costs, advancement_rewards)

def main(game_name=DEFAULTS.game,
        iterations=DEFAULTS.iterations,
        attacker_all=False,
        use_waits=DEFAULTS.use_waits,
        use_timewaits=DEFAULTS.use_timewaits,
        use_chance_fail=DEFAULTS.use_chance_fail,
        dump_dir=None, dump_games=None):
    if not iterations:
        iterations = DEFAULTS.iterations
    perms_seen = set()
    perm_total = 0
    perm_total = len(list(permutations()))
    perm_fmt = f"permutation.%0{len(str(perm_total))}d"
    dump_pm = timestamp = None
    if dump_dir:
        dump_pm = util.PathManager(base_dir=dump_dir,
                game_name=game_name)
        if not os.path.exists(dump_pm.path()):
            os.makedirs(dump_pm.path())
        timestamp = dump_pm.timestamp
    perm_cnt = 0
    for def_policy, def_ap, atk_policy, atk_ap, det_costs, adv_rewards \
            in permutations(attacker_all=attacker_all):
        key = (def_policy, def_ap, atk_policy, atk_ap, det_costs, adv_rewards)
        if key in perms_seen:
            continue
        perms_seen.add(key)
        perm_cnt += 1
        perm_dir = games_dir = dd = None
        if dump_dir:
            dd = util.PathManager(base_dir=dump_dir,
                    game_name=game_name,
                    detection_costs=f"det_costs_{det_costs}",
                    advancement_rewards=f"adv_rewards_{adv_rewards}",
                    timestamp=timestamp)
            if dump_games:
                perm_dir = os.path.join(dd.path(), perm_fmt % perm_cnt)
                games_dir = os.path.join(perm_dir, "games")
                if not os.path.exists(games_dir):
                    os.makedirs(games_dir)
            else:
                perm_dir = dd.path()
            if not os.path.exists(perm_dir):
                os.makedirs(perm_dir)
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
        max_atk_util = utilities.max_atk_utility()
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
            if dd and dump_games:
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
        print(f"\nPermutation {perm_cnt}/{iterations}:")
        print(f"Defender policy: {def_policy_str}, {det_costs}")
        print(f"Attacker policy: {atk_policy_str}, {adv_rewards}")
        print("Number of games played:", game_num)
        print("Number of distinct games played:", len(histories))
        if perm_dir:
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
            }
            dump["defender policy"] = def_policy,
            dump["defender action picker"] = def_ap or "n/a"
            dump["attacker policy"] = atk_policy,
            dump["attacker action picker"] = atk_ap or "n/a"
            dump["advancement_rewards"] = adv_rewards
            dump["detection_costs"] = det_costs
            dump["use_waits"] = use_waits
            dump["use_timewaits"] = use_timewaits
            dump["use_chance_fail"] = use_chance_fail
            dump["player_map"] = arena.player_map()
            dump["action_map"] = arena.action_map()
            dump["utilities"] = utilities.tupleize()
            histories = list(reversed(sorted((y, x)
                for x, y in histories.items())))
            dump["history_tallies"] = histories
            if dump_games:
                summary_file = os.path.join(perm_dir, "summary.json")
            else:
                summary_file = f"{perm_fmt % perm_cnt}.json"
                summary_file = os.path.join(dd.path(), summary_file)
            with open(summary_file, 'w') as dfh:
                json.dump(dump, dfh, indent=2)
            if dump_games:
                print(f"Dumped {game_num} game playthroughs into: {perm_dir}")
            else:
                print(f"Dumped summary of {game_num} game playthroughs into: {summary_file}")


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
