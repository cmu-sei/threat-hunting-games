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

import policies, util
import arena_zsum_v4 as arena
from threat_hunting_games import games


@dataclass
class Defaults:
    game: str = "chain_game_v4_lb_seq_zsum"
    iterations: int = 1

    # Need to include loading policy of choice in our parameterization
    # efforts.
    defender_policy: str = "simple_random"
    #default_defender_policy = "independent_intervals"
    #default_defender_policy = "aggregate_history"

    # Attacker will always have a two actions (whatever the next action
    # in the chain is plus its CAMO version) plus WAIT...so randomly
    # choose one of the three; uniform random comes stock with OpenSpiel
    attacker_policy: str = "uniform_random"

    dump_dir: str = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "dump")

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
        player_str = arena.player_to_str(player)
        action_str = arena.a2s(action)
        print(f"Player {player_str} sampled action: {action_str}")
        # convert to int; json.dump() can't dump int64
        history.append(int(action))
        state.apply_action(action)
    returns = state.returns()
    print("Returns:", " ".join(map(str, returns)))
    return returns, history, state.turns_played(), state.turns_exhausted()

def main(game_name=DEFAULTS.game,
        iterations=DEFAULTS.iterations,
        defender_policy=DEFAULTS.defender_policy,
        attacker_policy=DEFAULTS.attacker_policy,
        dump_dir=None):
    if not iterations:
        iterations = DEFAULTS.iterations
    game = pyspiel.load_game(game_name)
    def_bot = util.get_player_bot(game, arena.Players.DEFENDER,
            defender_policy)
    atk_bot = util.get_player_bot(game, arena.Players.ATTACKER,
            attacker_policy)
    bots = {
        arena.Players.DEFENDER: def_bot,
        arena.Players.ATTACKER: atk_bot,
    }
    histories = collections.defaultdict(int)
    overall_returns = {
        arena.Players.DEFENDER: 0,
        arena.Players.ATTACKER: 0,
    }
    overall_wins = {
        arena.Players.DEFENDER: 0,
        arena.Players.ATTACKER: 0,
    }
    dump_pm = None
    if dump_dir:
        dump_pm = util.PathManager(base_dir=dump_dir, game_name=game_name,
            attacker_policy=attacker_policy, defender_policy=defender_policy)
        dump_dir = os.path.join(dump_dir, str(datetime.now()))
        if not os.path.exists(dump_pm.path()):
            os.makedirs(dump_pm.path())
    iter_fmt = len(str(iterations))
    num_games_maxed = 0
    game_num = 0
    try:
        for game_num in range(iterations):
            returns, history, turns_played, turns_exhausted \
                    = play_game(game, bots)
            histories[" ".join(str(int(x)) for x in history)] += 1
            for i, v in enumerate(returns):
                overall_returns[i] += v
                if v > 0:
                    overall_wins[i] += 1
            if dump_pm:
                dump = {
                    "defender_policy": defender_policy,
                    "attacker_policy": attacker_policy,
                    "returns": returns,
                    "history": history,
                    "max_turns": game.get_parameters()["num_turns"],
                    "turns_played": turns_played,
                    "turns_exhausted": turns_exhausted,
                }
                df = dump_pm.path(ext="json")
                with open(df, 'w') as dfh:
                    json.dump(dump, dfh, indent=2)
    except (KeyboardInterrupt, EOFError):
        game_num -= 1
        print("Game iterations aborted")
    print(f"Defender policy: {defender_policy}")
    print(f"Attacker policy: {attacker_policy}")
    print("Number of games played:", game_num + 1)
    print("Number of distinct games played:", len(histories))
    if dump_pm:
        print(f"Dumped {game_num + 1} game playthroughs into: {dump_pm.path()}")


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
    parser.add_argument("--defender_policy", "--dp",
            default=DEFAULTS.defender_policy,
            help=f"Defender policy ({DEFAULTS.defender_policy})")
    parser.add_argument("--attacker_policy", "--ap",
            default=DEFAULTS.attacker_policy,
            help=f"Attacker policy ({DEFAULTS.attacker_policy})")
    parser.add_argument("-l", "--list_policies", action="store_true",
            help="List available policies")
    parser.add_argument("-p", "--dump_dir",
            default=DEFAULTS.dump_dir,
            help=f"Directory in which to dump game states over iterations of the game. ({DEFAULTS.dump_dir})")
    parser.add_argument("-n", "--no_dump", action="store_true",
            help="Disable logging of game playthroughs")
    args = parser.parse_args()
    if args.list_policies:
        for policy_name in policies.available_policies():
            print("  ", policy_name)
        sys.exit()
    if args.no_dump:
        args.dump_dir = None
    main(
        game_name=DEFAULTS.game,
        iterations=args.iterations,
        defender_policy=args.defender_policy,
        attacker_policy=args.attacker_policy,
        dump_dir = args.dump_dir,
    )
