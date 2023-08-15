#!/bin/env python3

import os, sys, json
import argparse
import collections
import numpy as np
import tensorflow.compat.v1 as tf
from datetime import datetime
from glob import glob
from dataclasses import dataclass

import pyspiel
from open_spiel.python import rl_environment
from open_spiel.python.bots.policy import PolicyBot
from open_spiel.python.algorithms import dqn
#from policy import PolicyBot

import policies, util
import arena_zsum_v4 as arena
from bot_agent import BotAgent
from threat_hunting_games import games

@dataclass
class Defaults:
    game: str = "chain_game_v4_lb_seq_zsum"
    iterations: int = 1000
    # Attacker will always have a two actions (whatever the next action
    # in the chain is plus its CAMO version) plus WAIT...so randomly
    # choose one of the three; uniform random comes stock with OpenSpiel
    defender_policy: str = "simple_random"
    attacker_policy: str = "uniform_random"

    dat_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dat")
    dump_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dump/rl")

DEFAULTS = Defaults()

_expected_dqn_kwargs = set([
    "num_actions",
    "info_state_size",
    "hidden_layers_sizes",
    "replay_buffer_capacity",
    "batch_size",
])


def play_episodes(env, rl_agents, fixed_agents,
        num_episodes=DEFAULTS.iterations):
    num_players = len(arena.Players)
    tallies = []
    for player_pos, p_name in enumerate(["attacker", "defender"]):
        sum_rewards = np.zeros(num_players)
        sum_wins = np.zeros(num_players + 1)
        histories = collections.defaultdict(int)
        # We play through once for each player; each time the current
        # player plays with the RL model and the opposing player plays
        # with a fixed policy.
        cur_agents = fixed_agents[:]
        cur_agents[player_pos] = rl_agents[player_pos]
        for _ in range(num_episodes):
            time_step = env.reset()
            episode_rewards = 0
            turn_num = 0
            history = ()
            while not time_step.last():
                turn_num += 1
                player_id = time_step.observations["current_player"]
                if env.is_turn_based:
                    agent_output = cur_agents[player_id].step(
                        time_step, is_evaluation=True)
                    action_list = (agent_output.action,)
                    history += action_list
                else:
                    agents_output = [
                        agent.step(time_step, is_evaluation=True) \
                                for agent in cur_agents]
                    action_list = tuple([agent_output.action
                        for agent_output in agents_output])
                    history += action_list
                    history.extend(action_list)
                time_step = env.step(action_list)
                episode_rewards += time_step.rewards[player_pos]
            sum_rewards[player_pos] += episode_rewards
            if env.get_state.victor() is None:
                sum_wins[2] += 1
            elif env.get_state.attacker_state.got_all_the_marbles:
                # attacker won (kill chain complete)
                sum_wins[0] += 1
            else:
                # defender won (successful detection)
                sum_wins[1] += 1
            histories[', '.join(str(x) for x in history)] += 1
        tally = {
            "num_episodes": num_episodes,
            "sum_rewards": list(sum_rewards),
            "sum_wins": list(sum_wins),
            "p_means": sum_episode_rewards / num_episodes,
            "histories": histories,
        }
        tallies.append(tally)
    return tallies

_expected_dqn_kwargs = set([
    "num_actions",
    "state_representation_size",
    "hidden_layers_sizes",
    "replay_buffer_capacity",
    "batch_size",
])

def load_rl_agents(sess, pm):
    agents = []
    assert os.path.exists(pm.attacker_dir), \
            f"attacker checkpoint dir missing: {pm.attacker_dir}"
    assert os.path.exists(pm.defender_dir), \
            f"defender checkpoint dir missing: {pm.defender_dir}"
    kwargs_file = pm.path(ext="json")
    assert os.path.exists(kwargs_file), f"kwargs file missing: {kwargs_file}"
    kwargs = json.load(open(kwargs_file))
    kwargs_diff = _expected_dqn_kwargs.difference(kwargs)
    assert not kwargs_diff, f"missing kwargs: {', '.join(kwargs_diff)}"
    for player_id, cp_dir in enumerate([
            pm.attacker_dir, pm.defender_dir]):
        # the parameters that are commented out are expected to be
        # defined in the kwargs file
        agents.append(dqn.DQN(
            session=sess,
            player_id=player_id,
            #state_representation_size=info_state_size,
            #num_actions=num_actions,
            discount_factor=0.99,
            epsilon_start=0.5,
            epsilon_end=0.1,
            #hidden_layers_sizes=hidden_layers_sizes,
            #replay_buffer_capacity=replay_buffer_capacity,
            #batch_size=batch_size
            **kwargs,
        ))
        agents[-1].restore(cp_dir)
    return agents

def load_bot_agents(game, attacker_policy=DEFAULTS.attacker_policy,
        defender_policy=DEFAULTS.defender_policy):
    agents = []
    for player_id, policy_name in enumerate(
            [attacker_policy, defender_policy]):
        bot = util.get_player_bot(game, player_id, policy_name)
        agent = BotAgent(len(arena.Actions), bot, name=policy_name)
        agents.append(agent)
    return agents

def main(game_name=DEFAULTS.game,
        iterations=DEFAULTS.iterations, checkpoint_dir=None,
        defender_policy=DEFAULTS.defender_policy,
        attacker_policy=DEFAULTS.attacker_policy,
        dump_dir=None):
    game = pyspiel.load_game(game_name)
    env = rl_environment.Environment(game, include_full_state=True)
    num_actions = env.action_spec()["num_actions"]
    pm = None
    if checkpoint_dir:
        checkpoint_pm = util.PathManager(raw_path=checkpoint_dir)
    else:
        dirs = sorted([x for x in glob(f"{DEFAULTS.dat_dir}/*-dqn-*") \
                if os.path.isdir(x)])
        checkpoint_dir = dirs[-1]
        checkpoint_pm = util.PathManager(raw_path=checkpoint_dir)
    with tf.Session() as sess:
        print(f"Loading RL agents from checkpoint: {checkpoint_pm.path()}")
        rl_agents = load_rl_agents(sess, checkpoint_pm)
        fixed_agents = load_bot_agents(game,
                attacker_policy=attacker_policy,
                defender_policy=defender_policy)
        tallies = play_episodes(env, rl_agents, fixed_agents,
            num_episodes=iterations)
        if dump_dir:
            dump_pm = util.PathManager(base_dir=dump_dir,
                attacker_policy=attacker_policy,
                defender_policy=defender_policy,
                model="dqn")
            df = dump_pm.path(ext="json")
            if not os.path.exists(os.path.dirname(df)):
                os.makedirs(os.path.dirname(df))
            json.dump(tallies, open(df, 'w'), indent=2)
            print(f"Dumped game playthrough tallies into: {df}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Trained RL Agent Playthrough",
        description=f"Play through {DEFAULTS.game} using trained RL "
                     "agents vs a fixed policy agent."
    )
    #parser.add_argument("-g", "--game", default=DEFAULTS.game,
    #        description="Name of game to play"
    parser.add_argument("-i", "--iterations", default=DEFAULTS.iterations,
            type=int,
            help=f"Number of game episodes to play ({DEFAULTS.iterations})")
    parser.add_argument("--defender_policy", "--dp",
            default=DEFAULTS.defender_policy,
            help=f"Defender policy ({DEFAULTS.defender_policy})")
    parser.add_argument("--attacker_policy", "--ap",
            default=DEFAULTS.attacker_policy,
            help=f"Attacker policy (only one currently: {DEFAULTS.attacker_policy})")
    parser.add_argument("-l", "--list_policies", action="store_true",
            help="List available policies")
    parser.add_argument("--checkpoint_dir",
            help=f"Directory from which to find and load RL agent checkpoints. (most recent in {DEFAULTS.dat_dir})")
    parser.add_argument("-d", "--dump_dir",
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
    main(game_name=DEFAULTS.game,
        iterations=args.iterations, checkpoint_dir=args.checkpoint_dir,
        attacker_policy=args.attacker_policy,
        defender_policy=args.defender_policy,
        dump_dir=args.dump_dir)
