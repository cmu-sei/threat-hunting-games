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

# compare with open_spiel/python/examples/cfr_example.py

"""Example use of the CFR algorithm on Kuhn Poker."""

from absl import app
from absl import flags

from open_spiel.python.algorithms import cfr
from open_spiel.python.algorithms import exploitability
import pyspiel

from threat_hunting_games.games import game_name

FLAGS = flags.FLAGS

flags.DEFINE_integer("iterations", 100, "Number of iterations")
flags.DEFINE_string("game", game_name, "Name of the game")
# pyspiel.load_game does not accept parameter "players"
#flags.DEFINE_integer("players", 2, "Number of players")
flags.DEFINE_integer("print_freq", 10, "How often to print the exploitability")


def main(_):
  #game = pyspiel.load_game(FLAGS.game, {"players": FLAGS.players})
  game = pyspiel.load_game(FLAGS.game)
  game_name = game.get_type().short_name
  game_type = game.get_type()

  # this conversion is not in the original example
  if game_type.dynamics == pyspiel.GameType.Dynamics.SIMULTANEOUS:
      game = pyspiel.load_game_as_turn_based(game_name)
      game_type = game.get_type()

  cfr_solver = cfr.CFRSolver(game)

  for i in range(FLAGS.iterations):
    cfr_solver.evaluate_and_update_policy()
    if i % FLAGS.print_freq == 0:
      conv = exploitability.exploitability(game, cfr_solver.average_policy())
      print("Iteration {} exploitability {}".format(i, conv))


if __name__ == "__main__":
  app.run(main)
