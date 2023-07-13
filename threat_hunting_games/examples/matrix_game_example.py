#!/bin/env python3
#
# Copyright 2019 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# compare with: open_spiel/python/examples/matrix_game_example.py

"""Python spiel example."""

import random

from absl import app
import numpy as np

import pyspiel
from open_spiel.python.utils import file_utils

from threat_hunting_games.games import current_game

def _manually_create_game():
  """Creates the game manually from the spiel building blocks."""
  game_type = pyspiel.GameType(
      short_name=current_game.game_name,
      long_name="Chain game version 2 matrix example",
      dynamics=pyspiel.GameType.Dynamics.SIMULTANEOUS,
      chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
      #information=pyspiel.GameType.Information.ONE_SHOT,
      information=pyspiel.GameType.Information.PERFECT_INFORMATION,
      #utility=pyspiel.GameType.Utility.ZERO_SUM,
      utility=pyspiel.GameType.Utility.GENERAL_SUM,
      reward_model=pyspiel.GameType.RewardModel.TERMINAL,
      max_num_players=len(current_game.Players),
      min_num_players=len(current_game.Players),
      #provides_information_state_string=True,
      #provides_information_state_tensor=True,
      #provides_observation_string=False,
      #provides_observation_tensor=False,
      provides_information_state_string=False,
      provides_information_state_tensor=False,
      provides_observation_string=True,
      provides_observation_tensor=True,
      #parameter_specification=dict(),
      parameter_specification={"num_turns": 2}
  )
  matrix = [
      ["Wait",           "Advance_Noisy",    "Advance_Camo"],
      ["Wait",           "Detect_Weak",      "Detect_Strong"],
        # Attacker
        # W vs...           AN vs...            AC vs...
        # W     DW   DS      W     DW    DS      W     DW,   DS 
      [ [ 0+0,  0+0, 0+0], [-1+3, -1+0, -1+0], [-2+3, -2+3, -2+0] ],
        # Defender (still row major order, i.e. attacker's POV)
        # W vs...           AN vs...            AC vs...
        # W    DW   DS      W     DW    DS      W     DW    DS 
      [ [ 0-0, 0-1, 0-2], [ 0-3, -1-0, -1-0], [ 0-3, -1-3, -2-0] ],
  ]
  game = pyspiel.MatrixGame(
      game_type,
      #{},  # game_parameters
      {"num_turns": 2},  # game_parameters

      #["Heads", "Tails"],  # row_action_names
      #["Heads", "Tails"],  # col_action_names
      #[[-1, 1], [1, -1]],  # row player utilities
      #[[1, -1], [-1, 1]]  # col player utilities

      #["Heads", "Tails", "Bozo"],  # row_action_names
      #["Heads", "Tails", "Bozo"],  # col_action_names
      #[[-1, 1, 0], [1, -1, 0], [0,0,0]],  # row player utilities
      #[[1, -1, 0], [-1, 1, 0], [0,0,0]]  # col player utilities

      *matrix

  )
  return game


def _easy_create_game():
  """Uses the helper function to create the same game as above."""
  return pyspiel.create_matrix_game("matching_pennies", "Matching Pennies",
                                    ["Heads", "Tails"], ["Heads", "Tails"],
                                    [[-1, 1], [1, -1]], [[1, -1], [-1, 1]])


def _even_easier_create_game():
  """Leave out the names too, if you prefer."""
  return pyspiel.create_matrix_game([[-1, 1], [1, -1]], [[1, -1], [-1, 1]])


def _import_data_create_game():
  """Creates a game via imported payoff data."""
  payoff_file = file_utils.find_file(
      "open_spiel/data/paper_data/response_graph_ucb/soccer.txt", 2)
  payoffs = np.loadtxt(payoff_file)*2-1
  return pyspiel.create_matrix_game(payoffs, payoffs.T)


def main(_):

  # Load a two-player normal-form game as a two-player matrix game.
  #blotto_matrix_game = pyspiel.load_matrix_game("blotto")
  #print("Number of rows in 2-player Blotto with default settings is {}".format(
  #    blotto_matrix_game.num_rows()))

  # Several ways to load/create the same game of matching pennies.
  print("Creating matrix game...")
  #game = pyspiel.load_matrix_game("matrix_mp")
  game = _manually_create_game()
  #game = _import_data_create_game()
  #game = _easy_create_game()
  #game = _even_easier_create_game()

  # Quick test: inspect top-left utility values:
  print("Values for joint action ({},{}) is {},{}".format(
      game.row_action_name(current_game.Actions.WAIT),
      game.col_action_name(current_game.Actions.WAIT),
      game.player_utility(current_game.Players.ATTACKER, 0, 0),
      game.player_utility(current_game.Players.DEFENDER, 0, 0)))

  state = game.new_initial_state()

  # Print the initial state
  print("State:")
  print(str(state))

  assert state.is_simultaneous_node()

  # Simultaneous node: sample actions for all players.
  chosen_actions = [
      random.choice(state.legal_actions(pid))
      for pid in range(game.num_players())
  ]
  print("Chosen actions: ", [
      state.action_to_string(pid, action)
      for pid, action in enumerate(chosen_actions)
  ])
  state.apply_actions(chosen_actions)

  assert state.is_terminal()

  # Game is now done. Print utilities for each player
  returns = state.returns()
  for pid in range(game.num_players()):
    print("Utility for player {} is {}".format(pid, returns[pid]))


if __name__ == "__main__":
  app.run(main)
