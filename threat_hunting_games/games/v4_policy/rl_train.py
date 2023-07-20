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

### The core components of this modified script are copied from
### open_spiel/python/rl_response.py

"""RL agents trained against fixed policy/bot as approximate responses.

This can be used to try to find exploits in policies or bots, as described in
Timbers et al. '20 (https://arxiv.org/abs/2004.09677), but only using RL
directly rather than RL+Search.
"""

import os, sys, json
import argparse
import numpy as np
import tensorflow.compat.v1 as tf
import pyspiel

from datetime import datetime
from dataclasses import dataclass

from open_spiel.python import rl_agent
from open_spiel.python import rl_environment
from open_spiel.python import rl_tools
from open_spiel.python.algorithms import dqn
from open_spiel.python.bots.policy import PolicyBot

from threat_hunting_games.games import game_name
import arena_zsum_v4 as arena
import policies 
from bot_agent import BotAgent
from pathmanager import PathManager


@dataclass
class Defaults:

    game: str ="chain_game_v4_lb_seq_zsum"
    dat_dir: str = \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "dat")

    # Player policies
    defender_policy: str = "uniform_random"
    attacker_policy: str = "simple_random"

    # Training parameters
    save_every: int = int(1e4)
    num_train_episodes: int = int(1e6)
    eval_every: int = 1000
    eval_episodes: int = 1000

    # DQN model hyper-parameters
    hidden_layers_sizes: str = "64,64,64"
    replay_buffer_capacity: int = int(1e5)
    batch_size: int = 32

    # Main algorithm parameters
    seed: int = 0
    window_size: int = 30

DEFAULTS = Defaults()

def get_player_policy(game, player, policy_name):
    policy_class = policies.get_policy_class(policy_name)
    policy_args = policies.get_player_policy_args(player, policy_name)
    return policy_class(game, *policy_args)

def get_player_bot(game, player, policy_name):
    policy = get_player_policy(game, player, policy_name)
    bot = PolicyBot(player, np.random, policy)
    return bot

def eval_against_fixed_bots(env, trained_agents, fixed_agents, num_episodes):
  """Evaluates `trained_agents` against `random_agents` for `num_episodes`."""
  num_players = len(fixed_agents)
  sum_episode_rewards = np.zeros(num_players)
  for player_pos in range(num_players):
    cur_agents = fixed_agents[:]
    cur_agents[player_pos] = trained_agents[player_pos]
    for _ in range(num_episodes):
      time_step = env.reset()
      episode_rewards = 0
      turn_num = 0
      while not time_step.last():
        turn_num += 1
        player_id = time_step.observations["current_player"]
        if env.is_turn_based:
          agent_output = cur_agents[player_id].step(
              time_step, is_evaluation=True)
          action_list = [agent_output.action]
        else:
          agents_output = [
              agent.step(time_step, is_evaluation=True) for agent in cur_agents
          ]
          action_list = [agent_output.action for agent_output in agents_output]
        time_step = env.step(action_list)
        episode_rewards += time_step.rewards[player_pos]
      sum_episode_rewards[player_pos] += episode_rewards
  return sum_episode_rewards / num_episodes

def create_training_agents(num_players, sess, num_actions,
        info_state_size, hidden_layers_sizes,
        replay_buffer_capacity=DEFAULTS.replay_buffer_capacity,
        batch_size=DEFAULTS.batch_size):
  """Create the agents we want to use for learning."""
  return [
      dqn.DQN(
          session=sess,
          player_id=idx,
          state_representation_size=info_state_size,
          num_actions=num_actions,
          discount_factor=0.99,
          epsilon_start=0.5,
          epsilon_end=0.1,
          hidden_layers_sizes=hidden_layers_sizes,
          replay_buffer_capacity=replay_buffer_capacity,
          batch_size=batch_size) for idx in range(num_players)
  ]

class RollingAverage(object):
  """Class to store a rolling average."""

  def __init__(self, size=100):
    self._size = size
    self._values = np.array([0] * self._size, dtype=np.float64)
    self._index = 0
    self._total_additions = 0

  def add(self, value):
    self._values[self._index] = value
    self._total_additions += 1
    self._index = (self._index + 1) % self._size

  def mean(self):
    n = min(self._size, self._total_additions)
    if n == 0:
      return 0
    return self._values.sum() / n

# 2 space indent retained for comparison with
# open_spiel/python/rl_response.py
def train(
        game_name=DEFAULTS.game,
        defender_policy=DEFAULTS.defender_policy,
        attacker_policy=DEFAULTS.attacker_policy,
        checkpoint_base_dir=None,
        no_checkpoint_dir=False,
        save_every=DEFAULTS.save_every,
        num_train_episodes=DEFAULTS.num_train_episodes,
        eval_every=DEFAULTS.eval_every,
        eval_episodes=DEFAULTS.eval_episodes,
        hidden_layers_sizes=DEFAULTS.hidden_layers_sizes,
        replay_buffer_capacity=DEFAULTS.replay_buffer_capacity,
        batch_size=DEFAULTS.batch_size,
        seed=DEFAULTS.seed,
        window_size=DEFAULTS.window_size
        ):
  if not checkpoint_base_dir and not no_checkpoint_dir:
      checkpoint_base_dir = DEFAULTS.dat_dir
  cp_pm = None
  if not no_checkpoint_dir:
      cp_pm = PathManager(base_dir=checkpoint_base_dir,
              game_name=game_name,
              attacker_policy=attacker_policy,
              defender_policy=defender_policy,
              model="dqn")
  kwargs_file = None
  if cp_pm:
    for d in cp_pm.checkpoint_dirs:
      if not os.path.exists(d):
        os.makedirs(d)
    kwargs_file = f"{cp_pm.path(ext='.json')}"
  if os.path.exists(kwargs_file):
      os.remove(kwargs_file)
  if isinstance(hidden_layers_sizes, str):
      hidden_layers_sizes = [int(x) for x in hidden_layers_sizes.split(',')]
  assert len(hidden_layers_sizes) == 3
  game = pyspiel.load_game(game_name)
  def_bot = get_player_bot(game, arena.Players.DEFENDER, defender_policy)
  atk_bot = get_player_bot(game, arena.Players.ATTACKER, attacker_policy)
  #def_agent = BotAgent(len(arena.Defend_Actions), def_bot,
  def_agent = BotAgent(len(arena.Actions), def_bot,
          name=defender_policy)
  #atk_agent = BotAgent(len(arena.Attack_Actions), atk_bot,
  atk_agent = BotAgent(len(arena.Actions), atk_bot,
          name=attacker_policy)

  np.random.seed(seed)
  tf.random.set_random_seed(seed)

  num_players = len(arena.Players)

  env = rl_environment.Environment(game, include_full_state=True)
  info_state_size = env.observation_spec()["info_state"][0]
  num_actions = env.action_spec()["num_actions"]

  # Exploitee agents
  exploitee_agents = [atk_agent, def_agent]

  rolling_averager = RollingAverage(window_size)
  rolling_averager_p0 = RollingAverage(window_size)
  rolling_averager_p1 = RollingAverage(window_size)
  rolling_value = 0
  total_value = 0
  total_value_n = 0

  with tf.Session() as sess:
    hidden_layers_sizes = [int(l) for l in hidden_layers_sizes]
    # pylint: disable=g-complex-comprehension
    learning_agents = create_training_agents(num_players, sess, num_actions,
            info_state_size, hidden_layers_sizes,
            replay_buffer_capacity=replay_buffer_capacity,
            batch_size=batch_size)
    sess.run(tf.global_variables_initializer())

    print("Starting...")

    for ep in range(num_train_episodes):
      if (ep + 1) % eval_every == 0:
        r_mean = eval_against_fixed_bots(env, learning_agents,
                exploitee_agents, eval_episodes)
        value = r_mean[0] + r_mean[1]
        rolling_averager.add(value)
        rolling_averager_p0.add(r_mean[0])
        rolling_averager_p1.add(r_mean[1])
        rolling_value = rolling_averager.mean()
        rolling_value_p0 = rolling_averager_p0.mean()
        rolling_value_p1 = rolling_averager_p1.mean()
        total_value += value
        total_value_n += 1
        avg_value = total_value / total_value_n
        print(("[{}] Mean episode rewards {}, value: {}, " +
               "rval: {} (p0/p1: {} / {}), aval: {}").format(
                   ep + 1, r_mean, value, rolling_value, rolling_value_p0,
                   rolling_value_p1, avg_value))

      agents_round1 = [learning_agents[0], exploitee_agents[1]]
      agents_round2 = [exploitee_agents[0], learning_agents[1]]

      if cp_pm and (ep + 1) % save_every == 0:
        print("Saving checkpoints...")
        for i, agent in enumerate(learning_agents):
            agent.save(cp_pm.checkpoint_dirs[i])
        if not os.path.exists(kwargs_file):
          json.dump({
              "num_actions": num_actions,
              "info_state_size": info_state_size,
              "hidden_layers_sizes": hidden_layers_sizes,
              "replay_buffer_capacity": replay_buffer_capacity,
              "batch_size": batch_size,
              }, open(kwargs_file, 'w'), indent=2)

      for agents in [agents_round1, agents_round2]:
        time_step = env.reset()
        while not time_step.last():
          player_id = time_step.observations["current_player"]
          if env.is_turn_based:
            agent_output = agents[player_id].step(time_step)
            action_list = [agent_output.action]
          else:
            agents_output = [agent.step(time_step) for agent in agents]
            action_list = [
                agent_output.action for agent_output in agents_output
            ]
          time_step = env.step(action_list)

        # Episode is over, step all agents with final info state.
        for agent in agents:
          agent.step(time_step)

    if cp_pm:
      print(f"Checkpoints saved  into: {cp_pm.path}")


def main():
    parser = argparse.ArgumentParser(
        prog="RL Training Using Policies",
        description=f"Train DQN models against fixed policies")
    #parser.add_argument("-g", "--game", default=default_game,
    #        description="Name of game to play"
    parser.add_argument("--defender_policy", "--dp",
            default=DEFAULTS.defender_policy,
            help=f"Defender policy ({DEFAULTS.defender_policy})")
    parser.add_argument("--attacker_policy", "--ap",
            default=DEFAULTS.attacker_policy,
            help=f"Attacker policy ({DEFAULTS.attacker_policy})")
    parser.add_argument("-l", "--list_policies", action="store_true",
            help="List available policies")

    # Training parameters
    parser.add_argument("--checkpoint_base_dir",
            help=f"Base directory in which save/load the agent models ({DEFAULTS.dat_dir})")
    parser.add_argument("--save_every", default=DEFAULTS.save_every, type=int,
            help=f"Episode frequency at which the DQN agent models are saved. ({DEFAULTS.save_every})")
    parser.add_argument("--no-checkpoint-dir", action="store_true",
            help=f"Do not use the default checkpoint dir or any other.")
    parser.add_argument("--num_train_episodes",
            default=DEFAULTS.num_train_episodes, type=int,
            help=f"Numnber of training episodes. ({DEFAULTS.num_train_episodes})")
    parser.add_argument("--eval_every",
            default=DEFAULTS.eval_every, type=int,
            help=f"Episode frequency at which the DQN agents are evaluated. ({DEFAULTS.eval_every})")
    parser.add_argument("--eval_episodes",
            default=DEFAULTS.eval_episodes, type=int,
            help=f"How many episodes to run per eval. ({DEFAULTS.eval_episodes})")

    # DQN
    parser.add_argument("--hidden_layers_sizes",
            default=DEFAULTS.hidden_layers_sizes,
            help=f"Number of hidden units in the Q-Network MLP. ({DEFAULTS.hidden_layers_sizes})")
    parser.add_argument("--replay_buffer_capacity",
            default=DEFAULTS.replay_buffer_capacity, type=int,
            help=f"Size of the replay buffer. ({DEFAULTS.replay_buffer_capacity})")
    parser.add_argument("--batch_size", default=DEFAULTS.batch_size, type=int,
            help=f"Number of transitions to sample at each learning step. ({DEFAULTS.batch_size})")

    # Main algorithm
    parser.add_argument("--seed", default=DEFAULTS.seed, type=int,
            help=f"Seed used for everything. ({DEFAULTS.seed})")
    parser.add_argument("--window_size", default=DEFAULTS.window_size, type=int,
            help=f"Size of window for rolling average. ({DEFAULTS.window_size})")
    args = parser.parse_args()
    if args.list_policies:
        for policy_name in policies.available_policies():
            print("  ", policy_name)
        sys.exit()

    hidden_layers_sizes = \
            [int(x) for x in args.hidden_layers_sizes.split(',')]
    assert len(hidden_layers_sizes) == 3

    train(
        game_name=DEFAULTS.game,
        defender_policy=args.defender_policy,
        attacker_policy=args.attacker_policy,
        checkpoint_base_dir=args.checkpoint_base_dir,
        no_checkpoint_dir=args.no_checkpoint_dir,
        save_every=args.save_every,
        num_train_episodes=args.num_train_episodes,
        eval_every=args.eval_every,
        eval_episodes=args.eval_episodes,
        hidden_layers_sizes=hidden_layers_sizes,
        replay_buffer_capacity=args.replay_buffer_capacity,
        batch_size=args.batch_size,
        seed=args.seed,
        window_size=args.window_size
    )


if __name__ == "__main__":
    main()
