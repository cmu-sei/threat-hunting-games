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

"""Python XFP example."""

import sys
from absl import app
from absl import flags

#from open_spiel.python.algorithms import exploitability
#from open_spiel.python.algorithms import fictitious_play
from threat_hunting_games.algorithms import exploitability
from threat_hunting_games.algorithms import fictitious_play
import pyspiel

from threat_hunting_games.games import game_name

FLAGS = flags.FLAGS

flags.DEFINE_integer("iterations", 100, "Number of iterations")
flags.DEFINE_string("game", game_name, "Name of the game")
flags.DEFINE_integer("players", 2, "Number of players")
flags.DEFINE_integer("print_freq", 10, "How often to print the exploitability")


def main(_):
  #game = pyspiel.load_game(FLAGS.game, {"players": FLAGS.players})
  game = pyspiel.load_game(FLAGS.game)
  xfp_solver = fictitious_play.XFPSolver(game)
  for i in range(FLAGS.iterations):
    print("\niter:", i)
    xfp_solver.iteration()
    conv = exploitability.exploitability(game, xfp_solver.average_policy())
    sys.stdout.flush()
    if i % FLAGS.print_freq == 0:
      print("Iteration: {} Conv: {}".format(i, conv))
      sys.stdout.flush()


if __name__ == "__main__":
  app.run(main)
