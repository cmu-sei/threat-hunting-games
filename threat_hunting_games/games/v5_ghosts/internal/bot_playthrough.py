#!/bin/env python3
#
# This playthrough wrapper uses bots, one for the defender and one for
# the attacker. These bots are responsible for using policies to select
# each player's next action. Since the bots are controlling the policies
# there is no need to pass policies as parameters to the Game
# initialization.

import os, sys, json
import argparse
import collections
import numpy as np
from datetime import datetime

import policies
import arena_zsum as arena
from game import FakeGame, game_max_turns
from pyspiel_policy_bot import PolicyBot


default_game = "chain_game_v5_lb_seq_zsum"
default_iterations = 1

# Need to include loading policy of choice in our parameterization
# efforts.
default_defender_policy = "simple_random"
#default_defender_policy = "independent_intervals"
#default_defender_policy = "aggregate_history"

# Attacker will always have three actions -- whatever the next action in
# the chain is, plus its CAMO version, and plus WAIT...so randomly
# choose one of the three; uniform random comes stock with OpenSpiel
default_attacker_policy = "uniform_random"

def get_player_policy(game, player, policy_name):
    policy_class = policies.get_policy_class(policy_name)
    policy_args = policies.get_player_policy_args(player, policy_name)
    return policy_class(game, *policy_args)

def get_player_bot(game, player, policy_name):
    policy = get_player_policy(game, player, policy_name)
    bot = PolicyBot(player, np.random, policy)
    return bot

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
    return returns, history, state.turns_played(), \
            state.turns_exhausted(), state.winner()

def main(iterations=default_iterations,
        defender_policy=default_defender_policy,
        attacker_policy=default_attacker_policy,
        dump_dir=None):
    if not iterations:
        iterations = default_iterations
    game = FakeGame()
    print("GAME:", game)
    def_bot = get_player_bot(game, arena.Players.DEFENDER, defender_policy)
    atk_bot = get_player_bot(game, arena.Players.ATTACKER, attacker_policy)
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
    if dump_dir:
        dump_dir = os.path.join(dump_dir,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir)
    iter_fmt = len(str(iterations))
    num_games_maxed = 0
    game_num = 0
    try:
        for game_num in range(iterations):
            returns, history, turns_played, turns_exhausted, winner \
                    = play_game(game, bots)
            histories[" ".join(str(int(x)) for x in history)] += 1
            for i, v in enumerate(returns):
                overall_returns[i] += v
                if v > 0:
                    overall_wins[i] += 1
            if dump_dir:
                history_strings = []
                for i, a in enumerate(history):
                    player = arena.p2s(i % 2)
                    action = arena.a2s(a)
                    history_strings.append([player, action])
                history_str = [arena.a2s(x) for x in history]
                dump = {
                    "defender_policy": defender_policy,
                    "attacker_policy": attacker_policy,
                    "returns": returns,
                    "history": history,
                    "history_str": history_strings,
                    "max_turns": game.get_parameters().get(
                        "num_turns", game_max_turns),
                    "turns_played": turns_played,
                    "turns_exhausted": turns_exhausted,
                    "winner": int(winner) if winner else None,
                    "winner_str": arena.p2s(winner) if winner else None,
                }
                df = os.path.join(dump_dir, f"%0{iter_fmt}d.json" % game_num)
                with open(df, 'w') as dfh:
                    json.dump(dump, dfh, indent=2)
    except (KeyboardInterrupt, EOFError):
        game_num -= 1
        print("Game iterations aborted")
    print(f"Defender policy: {defender_policy}")
    print(f"Attacker policy: {attacker_policy}")
    print("Number of games played:", game_num + 1)
    print("Number of distinct games played:", len(histories))
    if dump_dir:
        rp = os.path.relpath(dump_dir,
                os.path.dirname(os.path.abspath(__file__)))
        print(f"Dumped {game_num + 1} game playthroughs into: {rp}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Bot Policy Playthrough",
        description=f"Play through {default_game} using player "
                     "bots with policies"
    )
    parser.add_argument("-i", "--iterations", default=default_iterations,
            type=int,
            help=f"Number of games to play ({default_iterations})")
    parser.add_argument("--defender_policy", "--dp",
            default=default_defender_policy,
            help=f"Defender policy ({default_defender_policy})")
    parser.add_argument("--attacker_policy", "--ap",
            default=default_attacker_policy,
            help=f"Attacker policy ({default_attacker_policy})")
    parser.add_argument("-l", "--list_policies", action="store_true",
            help="List available policies")
    default_dump_dir = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "dump")
    parser.add_argument("-p", "--dump_dir",
            default=default_dump_dir,
            help=f"Directory in which to dump game states over iterations of the game. ({default_dump_dir})")
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
        iterations=args.iterations,
        defender_policy=args.defender_policy,
        attacker_policy=args.attacker_policy,
        dump_dir = args.dump_dir,
    )
