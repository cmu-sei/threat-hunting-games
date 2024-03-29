#!/bin/env python3

import os, sys, json
import argparse
import collections
import numpy as np
from datetime import datetime
from dataclasses import dataclass

import pyspiel
from open_spiel.python.bots.policy import PolicyBot

import arena, policies, util, std_args
from threat_hunting_games import games
from arena import debug

def_defender_policy = "simple_random"
def_dp_class = policies.get_policy_class(def_defender_policy)
if hasattr(def_dp_class, "default_action_picker"):
    def_defender_action_picker = def_dp_class.default_action_picker()
else:
    def_defender_action_picker = None
def_attacker_policy = "uniform_random"
def_ap_class = policies.get_policy_class(def_attacker_policy)
if hasattr(def_ap_class, "default_action_picker"):
    def_attacker_action_picker = def_ap_class.default_action_picker()
else:
    def_attacker_action_picker = None

@dataclass
class Defaults:
    game: str = "chain_game_v6_seq"
    iterations: int = 1

    detection_costs: str = arena.Default_Detection_Costs
    advancement_rewards: str = arena.Default_Advancement_Rewards

    # Need to include loading policy of choice in our parameterization
    # efforts.
    defender_policy: str = def_defender_policy
    defender_action_picker: str|None = def_defender_action_picker

    # Attacker will always have a two actions (whatever the next action
    # in the chain is plus its CAMO version) plus WAIT...so randomly
    # choose one of the three; uniform random comes stock with OpenSpiel
    attacker_policy: str = def_attacker_policy
    attacker_action_picker: str|None = def_attacker_action_picker

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
    #print("Returns:", " ".join(map(str, returns)))
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
    defender_policy_str = defender_policy
    if not defender_action_picker:
        cls = policies.get_policy_class(defender_policy)
        if hasattr(cls, "default_action_picker"):
            defender_action_picker = cls.default_action_picker()
    if defender_action_picker:
        defender_policy_str += f"/{defender_action_picker}"
    attacker_policy_str = attacker_policy
    if not attacker_action_picker:
        cls = policies.get_policy_class(attacker_policy)
        if hasattr(cls, "default_action_picker"):
            attacker_action_picker = cls.default_action_picker()
    if attacker_action_picker:
        attacker_policy_str += f"/{attacker_action_picker}"
    print(f"Defender policy and costs: {defender_policy_str}, {detection_costs}")
    print(f"Attacker policy and rewards: {attacker_policy_str}, {advancement_rewards}")
    print("Number of games played:", game_num)
    print("Number of distinct games played:", len(histories))
    print(f"Total returns: {sum_returns}")
    print(f"r_means: [{sum_returns[0] / game_num}, {sum_returns[1] / game_num}]")
    if dump_pm:
        dump = {
            "sum_returns": returns,
            "sum_victories": sum_victories,
            "sum_inconclusive": sum_inconclusive,
            "r_means": [
                sum_returns[0] / game_num,
                sum_returns[1] / game_num,
            ],
            "max_turns": game.get_parameters()["num_turns"],
            "episodes": turns_played,
            "advancement_rewards": advancement_rewards,
            "detection_costs": detection_costs,
            "use_waits": use_waits,
            "use_timewaits": use_timewaits,
            "use_chance_fail": use_chance_fail,
            "action_map": arena.action_map(),
            "utilities": utilities.tupleize(),
            "history_tallies": histories,
        }
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

    std_args.add_std_args(DEFAULTS, parser)

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

    param_values = std_args.handle_std_args(args)

    main(
        game_name=DEFAULTS.game,
        iterations=args.iterations,
        detection_costs=param_values["detection_costs"],
        advancement_rewards=param_values["advancement_rewards"],
        defender_policy=param_values["defender_policy"],
        defender_action_picker=param_values["defender_action_picker"],
        attacker_policy=param_values["attacker_policy"],
        attacker_action_picker=param_values["attacker_action_picker"],
        use_waits=param_values["use_waits"],
        use_timewaits=param_values["use_timewaits"],
        use_chance_fail=param_values["use_chance_fail"],
        dump_dir = args.dump_dir,
    )
