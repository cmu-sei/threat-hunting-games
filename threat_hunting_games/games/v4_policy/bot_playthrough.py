#!/bin/env python3

import os, sys
import collections
import numpy as np

import pyspiel
from open_spiel.python.bots.policy import PolicyBot

import policy
import arena_zsum_v4 as arena

game_name = "chain_game_v4_lb_seq_zsum"

number_of_games = 1

player_policy_names = {
    arena.Players.DEFENDER: "aggregate history",
    arena.Players.ATTACKER: "first action",
}

def get_player_policy(game, player):
    policy_name = player_policy_names[player]
    policy_class = policy.get_policy_class(policy_name)
    policy_args = policy.get_player_policy_args(player, policy_name)
    return policy_class(game, *policy_args)

def get_player_bot(game, player):
    policy = get_player_policy(game, player)
    bot = PolicyBot(player, np.random, policy)
    return bot

def play_game(game, bots):
    # play one game
    state = game.new_initial_state()
    history = []
    while not state.is_terminal():
        player = state.current_player()
        bot = bots[player]
        action = bot.step(state)
        player_str = arena.player_to_str(player)
        action_str = arena.action_to_str(action)
        print(f"Player {player_str} sampled action: {action_str}")
        history.append(action)
        state.apply_action(action)

def main():
    game = pyspiel.load_game(game_name)
    def_bot = get_player_bot(game, arena.Players.DEFENDER)
    atk_bot = get_player_bot(game, arena.Players.ATTACKER)
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
    num_games_max_turns_reached = 0
    game_num = 0
    try :
        for game_num in range(number_of_games):
            returns, history = play_game(game, bots)
            histories[" ".join(history)] += 1
            for i, v in enumerate(returns):
                overall_returns[i] += v
                if v > 0:
                    overall_wins[i] += 1
    except (KeyboardInterrupt, EOFError):
        game_num -= 1
        print("Game iterations aborted")
    print("Number of games played:", game_num + 1)
    print("Number of distinct games played:", len(histories))

if __name__ == "__main__":
    main()
