#!/bin/env python3

"""
Test saved trained models (i.e. checkpoint) against fixed agents (bot
agents) and see what happens.

The `play_episodes()` code is largely lifted from the OpenSpiel
examples/rl_response.py evaluation method against fixed agents.
"""

import os, sys, json
import argparse
import collections
import numpy as np
# I added matplotlib import because without having imported it
# the tensorflow import will segfault
import matplotlib
import tensorflow.compat.v1 as tf
from datetime import datetime
from glob import glob
from dataclasses import dataclass

import pyspiel
from open_spiel.python import rl_environment
from open_spiel.python.bots.policy import PolicyBot
from open_spiel.python.algorithms import dqn
#from policy import PolicyBot

import policies, util, std_args
import arena
from bot_agent import BotAgent
from threat_hunting_games import games

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
    iterations: int = 1000
    # Attacker will always have a two actions (whatever the next action
    # in the chain is plus its CAMO version) plus WAIT...so randomly
    # choose one of the three; uniform random comes stock with OpenSpiel
    advancement_rewards = arena.Default_Advancement_Rewards
    detection_costs = arena.Default_Detection_Costs
    defender_policy: str = def_defender_policy
    defender_action_picker: str|None = def_defender_action_picker
    attacker_policy: str = def_attacker_policy
    attacker_action_picker: str|None = def_attacker_action_picker
    use_waits: bool = arena.USE_WAITS
    use_timewaits: bool = arena.USE_TIMEWAITS
    use_chance_fail: bool = arena.USE_CHANCE_FAIL
    dat_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dat")
    dump_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dump_rl")

DEFAULTS = Defaults()

_expected_dqn_kwargs = set([
    "num_actions",
    "info_state_size",
    "hidden_layers_sizes",
    "replay_buffer_capacity",
    "batch_size",
])


def play_episodes(env, rl_agents, fixed_agents,
        num_episodes=DEFAULTS.iterations, skip_attacker=False):
    num_players = len(arena.Players)
    tallies = []
    for player_pos, p_name in enumerate(["attacker", "defender"]):
        if skip_attacker and p_name == "attacker":
            print("skipping attacker...")
            continue
        sum_rewards = np.zeros(num_players)
        sum_wins = np.zeros(num_players + 1)
        histories = collections.defaultdict(int)
        # We play through once for each player; each time the current
        # player plays with the RL model and the opposing player plays
        # with a fixed policy.
        cur_agents = fixed_agents[:]
        cur_agents[player_pos] = rl_agents[player_pos]
        if player_pos == 0:
            bot_pos = 1
        else:
            bot_pos = 0
        for ep in range(num_episodes):
            if (ep + 1) % 100 == 0:
                print(f"episodes player {arena.p2s(player_pos)}: {ep + 1}/{num_episodes}")
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
            "player": arena.p2s(player_pos),
            "player_pos": player_pos,
            "bot": arena.p2s(bot_pos),
            "bot_pos": bot_pos,
            "bot_policy": cur_agents[bot_pos].name,
            "num_episodes": num_episodes,
            "sum_rewards": list(sum_rewards),
            "sum_wins": list(sum_wins),
            "r_means": [x / num_episodes for x in sum_rewards],
            "histories": histories,
        }
        tallies.append(tally)
    return tallies

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

def load_bot_agents(game,
        attacker_policy=DEFAULTS.attacker_policy,
        attacker_action_picker=DEFAULTS.attacker_action_picker,
        defender_policy=DEFAULTS.defender_policy,
        defender_action_picker=DEFAULTS.defender_action_picker):
    agents = []
    for player_id, (policy_name, action_picker) in enumerate(
            [[attacker_policy, attacker_action_picker],
                [defender_policy, defender_action_picker]]):
        bot = util.get_player_bot(game, player_id,
                policy_name, action_picker=action_picker)
        name = policy_name
        if action_picker:
            name = '-'.join([policy_name, action_picker])
        agent = BotAgent(len(arena.Actions), bot, name=policy_name)
        agents.append(agent)
    return agents

def main(game_name=DEFAULTS.game,
        iterations=DEFAULTS.iterations, checkpoint_dir=None,
        detection_costs=None, advancement_rewards=None,
        defender_policy=None, defender_action_picker=None,
        attacker_policy=None, attacker_action_picker=None,
        use_waits=None, use_timewaits=None, use_chance_fail=None,
        skip_attacker=False,
        dump_dir=None):
    if checkpoint_dir:
        checkpoint_pm = util.PathManager(base_dir=checkpoint_dir)
    else:
        dirs = sorted([x
            for x in glob(f"{DEFAULTS.dat_dir}/{game_name}-dqn-*") \
                if os.path.isdir(x)])
        checkpoint_dir = dirs[-1]
        checkpoint_pm = util.PathManager(base_dir=checkpoint_dir)
    params_file = os.path.join(checkpoint_pm.path(), "params.json")
    assert os.path.exists(params_file), f"params file missing: {params_file}"
    params = json.load(open(params_file))
    param_deltas = {}
    key = "detection_costs"
    if detection_costs is None:
        detection_costs = params[key]
    elif detection_costs != params[key]:
        param_deltas[key] = detection_costs
    key = "advancement_rewards"
    if advancement_rewards is None:
        advancement_rewards = params[key]
    elif advancement_rewards != params[key]:
        param_deltas[key] = advancement_rewards
    key = "defender_policy"
    if defender_policy is None:
        defender_policy = params[key]
    elif defender_policy != params[key]:
        param_deltas[key] = defender_policy
    key = "defender_action_picker"
    if defender_action_picker is None:
        defender_action_picker = params[key]
    elif defender_action_picker != params[key]:
        param_deltas[key] = defender_action_picker
    key = "attacker_policy"
    if attacker_policy is None:
        attacker_policy = params[key]
    elif attacker_policy != params[key]:
        param_deltas[key] = attacker_policy
    if attacker_action_picker is None:
        attacker_action_picker = params[key]
    elif attacker_action_picker != params[key]:
        param_deltas[key] = attacker_action_picker
    key = "use_waits"
    if use_waits is None:
        use_waits = params[key]
    elif use_waits != params[key]:
        param_deltas[key] = use_waits
    key = "use_timewaits"
    if use_timewaits is None:
        use_timewaits = params[key]
    elif use_timewaits != params[key]:
        param_deltas[key] = use_timewaits
    key = "use_chance_fail"
    if use_chance_fail is None:
        use_chance_fail = params[key]
    elif use_chance_fail != params[key]:
        param_deltas[key] = use_chance_fail
    game = pyspiel.load_game(game_name, {
        "advancement_rewards": advancement_rewards,
        "detection_costs": detection_costs,
        "use_waits": use_waits,
        "use_timewaits": use_timewaits,
        "use_chance_fail": use_chance_fail,
    })
    env = rl_environment.Environment(game, include_full_state=True)
    num_actions = env.action_spec()["num_actions"]
    pm = None
    with tf.Session() as sess:
        print(f"Loading RL agents from checkpoint: {checkpoint_pm.path()}")
        rl_agents = load_rl_agents(sess, checkpoint_pm)
        fixed_agents = load_bot_agents(game,
                detection_costs=detection_costs,
                advancement_rewards=advancement_rewards,
                defender_policy=defender_policy,
                defender_action_picker=defender_action_picker,
                attacker_policy=attacker_policy,
                attacker_action_picker=attacker_action_picker)
        tallies = play_episodes(env, rl_agents, fixed_agents,
            num_episodes=iterations, skip_attacker=skip_attacker)
        if dump_dir:
            dump_pm = util.PathManager(base_dir=dump_dir,
                detection_costs=detection_costs,
                defender_policy=defender_policy,
                defender_action_picker=defender_action_picker,
                attacker_policy=attacker_policy,
                attacker_action_picker=attacker_action_picker,
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
                     "agents vs a fixed policy agent. Unless otherwise "
                     "mentiond, default values are loaded from the "
                     "saved parameter file of the trained models. "
                     "Note that changing these parameters will alter "
                     "the nature of the game away from the parameters "
                     "upon which the RL model was trained. Also note "
                     "that policy (and action picker) parameters will "
                     "only be applied to the fixed agents -- the "
                     "trained models will be relying upon their "
                     "training for selecting actions.")
    #parser.add_argument("-g", "--game", default=DEFAULTS.game,
    #        description="Name of game to play"
    parser.add_argument("-i", "--iterations", default=DEFAULTS.iterations,
            type=int,
            help=f"Number of game episodes to play. ({DEFAULTS.iterations})")

    std_args.add_std_args(DEFAULTS, parser)

    parser.add_argument("--skip-attacker-model", "--sam", action="store_true",
            help="Omit testing the attacker's trained model since it's typically just uniform_random currently.")
    parser.add_argument("--checkpoint-dir",
            help=f"Directory from which to find and load RL agent checkpoints and default game parameters. (most recent in {DEFAULTS.dat_dir})")
    parser.add_argument("-d", "--dump-dir",
            default=DEFAULTS.dump_dir,
            help=f"Directory in which to dump game states over iterations of the game. ({DEFAULTS.dump_dir})")
    parser.add_argument("-n", "--no-dump", action="store_true",
            help="Disable logging of game playthroughs.")
    args = parser.parse_args()

    param_values = std_args.handle_std_args(args)

    if args.no_dump:
        args.dump_dir = None

    main(game_name=DEFAULTS.game,
        iterations=args.iterations, checkpoint_dir=args.checkpoint_dir,
        detection_costs=param_values["detection_costs"],
        advancement_rewards=param_values["advancement_rewards"],
        defender_policy=param_values["defender_policy"],
        defender_action_picker=param_values["defender_action_picker"],
        attacker_policy=param_values["attacker_policy"],
        attacker_action_picker=param_values["attacker_action_picker"],
        use_waits=param_values["use_waits"],
        use_timewaits=param_values["use_timewaits"],
        use_chance_fail=param_values["use_chance_fail"],
        skip_attacker=args.skip_attacker_model,
        dump_dir=args.dump_dir)
