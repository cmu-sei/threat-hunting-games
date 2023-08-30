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
    iterations: int = 1

    detection_costs: str = arena.Default_Detection_Costs
    advancement_rewards: str = arena.Default_Advancement_Rewards

    # Need to include loading policy of choice in our parameterization
    # efforts.
    defender_policy: str = "simple_random"
    #default_defender_policy = "independent_intervals"
    #default_defender_policy = "aggregate_history"

    # Attacker will always have a two actions (whatever the next action
    # in the chain is plus its CAMO version) plus WAIT...so randomly
    # choose one of the three; uniform random comes stock with OpenSpiel
    attacker_policy: str = "uniform_random"

    use_waits: bool = arena.USE_WAITS
    use_timewaits: bool = arena.USE_TIMEWAITS
    use_chance_fail: bool = arena.USE_CHANCE_FAIL

    dump_dir: str = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "dump_playthroughs")

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
    print("Returns:", " ".join(map(str, returns)))
    return state.turns_played(), returns, state.victor(), history

def main(game_name=DEFAULTS.game,
        iterations=DEFAULTS.iterations,
        detection_costs=DEFAULTS.detection_costs,
        defender_policy=DEFAULTS.defender_policy,
        defender_action_picker=None,
        advancement_rewards=DEFAULTS.advancement_rewards,
        attacker_policy=DEFAULTS.attacker_policy,
        attacker_action_picker=None,
        use_waits=DEFAULTS.use_waits,
        use_timewaits=DEFAULTS.use_timewaits,
        use_chance_fail=DEFAULTS.use_chance_fail,
        dump_dir=None):
    if not iterations:
        iterations = DEFAULTS.iterations
    if detection_costs:
        assert detection_costs in arena.Detection_Costs, \
                f"unknown detection_cost: {detection_costs}"
    if advancement_rewards:
        assert advancement_rewards in arena.Advancement_Rewards, \
                f"unknown advancement_rewards: {advancement_rewards}"
    if defender_policy:
        assert defender_policy in policies.list_policies(), \
                f"unknown defender_policy: {defender_policy}"
    if defender_action_picker:
        policy = defender_policy or DEFAULTS.defender_policy
        policy = policies.get_policy_class(policy)
        assert defender_action_picker in policy.list_action_pickers(), \
                f"unknown defender_action_picker: {defender_action_picker}"
    if attacker_policy:
        assert attacker_policy in policies.list_policies(), \
                f"unknkown attacker_policy: {attacker_policy}"
    if attacker_action_picker:
        policy = attacker_policy or DEFAULTS.attacker_policy
        policy = policies.get_policy_class(policy)
        assert attacker_action_picker in policy.list_action_pickers(), \
                f"unknown attacker_action_picker: {attacker_action_picker}"
    kwargs = {
        "advancement_rewards": advancement_rewards,
        "detection_costs": detection_costs,
        "use_waits": use_waits,
        "use_timewaits": use_timewaits,
        "use_chance_fail": use_chance_fail,
    }
    # load_game does not accept bools
    game = pyspiel.load_game(game_name, {
        "advancement_rewards": advancement_rewards,
        "detection_costs": detection_costs,
        "use_waits": int(use_waits),
        "use_timewaits": int(use_timewaits),
        "use_chance_fail": int(use_chance_fail),
    })
    #        "advancement_rewards": advancement_rewards,
    #        "detection_costs": detection_costs,
    #        "use_waits": int(bool(use_waits)),
    #        "use_timewaits": int(bool(use_timewaits)),
    #        "use_chance_fail": int(bool(use_chance_fail)),
    #    })
    utilities = arena.Utilities(
            advancement_rewards=advancement_rewards,
            detection_costs=detection_costs)
    def_bot = util.get_player_bot(game, arena.Players.DEFENDER,
            defender_policy, action_picker=defender_action_picker)
    atk_bot = util.get_player_bot(game, arena.Players.ATTACKER,
            attacker_policy, action_picker=attacker_action_picker)
    bots = {
        arena.Players.DEFENDER: def_bot,
        arena.Players.ATTACKER: atk_bot,
    }
    histories = collections.defaultdict(int)
    sum_returns = [0, 0]
    sum_victories = [0, 0]
    sum_inconclusive = 0
    dump_pm = None
    if dump_dir:
        dump_pm = util.PathManager(base_dir=dump_dir, game_name=game_name)
        dump_dir = os.path.join(dump_dir, str(datetime.now()))
        games_path = os.path.join(dump_pm.path(), "games")
        if not os.path.exists(games_path):
            os.makedirs(games_path)
    game_num = 0
    try:
        iter_fmt = f"%0{len(str(iterations))}d.json"
        for _ in range(iterations):
            game_num += 1
            turns_played, returns, victor, history \
                    = play_game(game, bots)
            histories[" ".join(str(int(x)) for x in history)] += 1
            for i, v in enumerate(returns):
                sum_returns[i] += v
            victor = int(victor) if victor is not None else victor
            if victor == int(arena.Players.ATTACKER):
                sum_victories[0] += 1
            elif victor == int(arena.Players.DEFENDER):
                sum_victories[1] += 1
            else:
                sum_inconclusive += 1
            if dump_pm:
                dump = {
                    "returns": returns,
                    "victor": victor,
                    "max_turns": game.get_parameters()["num_turns"],
                    "turns_played": turns_played,
                    "history": history,
                }
                df = os.path.join(dump_pm.path(), "games",
                        iter_fmt % game_num)
                with open(df, 'w') as dfh:
                    json.dump(dump, dfh, indent=2)
    except (KeyboardInterrupt, EOFError):
        game_num -= 1
        print("Game iterations aborted")
    if not defender_action_picker:
        cls = policies.get_policy_class(defender_policy)
        defender_action_picker = cls.default_action_picker()
    if not attacker_action_picker:
        cls = policies.get_policy_class(attacker_policy)
        attacker_action_picker = cls.default_action_picker()
    print(f"Defender policy: {defender_policy}/{defender_action_picker}")
    print(f"Attacker policy: {attacker_policy}/{attacker_action_picker}")
    print("Number of games played:", game_num)
    print("Number of distinct games played:", len(histories))
    if dump_pm:
        dump = {
            "sum_returns": returns,
            "sum_victories": sum_victories,
            "sum_inconclusive": sum_inconclusive,
            "p_means": [
                sum_returns[0] / game_num,
                sum_returns[1] / game_num,
            ],
            "max_turns": game.get_parameters()["num_turns"],
            "turns_played": turns_played,
        }
        dump.update(kwargs)
        dump["action_map"] = arena.action_map()
        dump["utilities"] = utilities.tupleize()
        dump["history_tallies"] = histories
        df = os.path.join(dump_pm.path(), "summary.json")
        json.dump(dump, open(df, 'w'), indent=2)
        print(f"Dumped {game_num} game playthroughs into: {dump_pm.path()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Bot Policy Playthrough",
        description=f"Play through {DEFAULTS.game} using player "
                     "bots with policies"
    )
    #parser.add_argument("-g", "--game", default=DEFAULTS.game,
    #        description="Name of game to play"
    parser.add_argument("-i", "--iterations", default=DEFAULTS.iterations,
            type=int,
            help=f"Number of games to play ({DEFAULTS.iterations})")
    parser.add_argument("--detection-costs", "--dc",
            default=DEFAULTS.detection_costs,
            help=f"Defender detect action cost structure ({DEFAULTS.detection_costs})")
    parser.add_argument("--advancement-rewards", "--ar",
            default=DEFAULTS.advancement_rewards,
            help=f"Attacker advance action rewards structure ({DEFAULTS.advancement_rewards})")
    parser.add_argument("--defender-policy", "--dp",
            default=DEFAULTS.defender_policy,
            help=f"Defender policy ({DEFAULTS.defender_policy})")
    parser.add_argument("--attacker-policy", "--ap",
            default=DEFAULTS.attacker_policy,
            help=f"Attacker policy ({DEFAULTS.attacker_policy})")
    parser.add_argument("-l", "--list-policies", action="store_true",
            help="List available policies")
    parser.add_argument("--list-advancement-rewards", "-lar",
            action="store_true", help="List attacker rewards choices")
    parser.add_argument("--list-detection-costs", action="store_true",
            help="List defender costs choices")
    parser.add_argument("-d", "--dump-dir",
            default=DEFAULTS.dump_dir,
            help=f"Directory in which to dump game states over iterations of the game. ({DEFAULTS.dump_dir})")
    parser.add_argument("-n", "--no-dump", action="store_true",
            help="Disable dumping of game playthroughs")
    args = parser.parse_args()
    if args.list_policies:
        for policy_name in policies.list_policies_with_pickers_strs():
            print("  ", policy_name)
        sys.exit()
    if args.list_detection_costs:
        for dc in arena.list_detection_utilities():
            print("  ", dc)
        sys.exit()
    if args.list_advancement_rewards:
        for au in arena.list_advancement_utilities():
            print("  ", au)
        sys.exit()
    if args.no_dump:
        args.dump_dir = None
    def_policy = def_action_picker = None
    def_pol_parts = args.defender_policy.split('-')
    if len(def_pol_parts) > 1:
        def_policy, def_action_picker = def_pol_parts
    else:
        def_policy = def_pol_parts[0]
    atk_policy = atk_action_picker = None
    atk_pol_parts = args.attacker_policy.split('-')
    if len(atk_pol_parts) > 1:
        atk_policy, atk_action_picker = atk_pol_parts
    else:
        atk_policy = atk_pol_parts[0]
    main(
        game_name=DEFAULTS.game,
        iterations=args.iterations,
        detection_costs=args.detection_costs,
        advancement_rewards=args.advancement_rewards,
        defender_policy=def_policy,
        defender_action_picker=def_action_picker,
        attacker_policy=atk_policy,
        attacker_action_picker=atk_action_picker,
        dump_dir = args.dump_dir,
    )
