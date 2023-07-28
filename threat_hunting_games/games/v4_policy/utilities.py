import random

import arena_zsum_v4 as arena

# for attacker

_atk_action_groups = (
    (arena.Actions.S0_VERIFY_PRIV, arena.Actions.S0_VERIFY_PRIV_CAMO),
    (arena.Actions.S1_WRITE_EXE, arena.Actions.S1_WRITE_EXE_CAMO),
    (arena.Actions.S2_ENCRYPT, arena.Actions.S2_ENCRYPT_CAMO),
)

_def_action_groups = (
    (arena.Actions.PSGREP, arena.Actions.PSGREP_STRONG),
    (arena.Actions.SMB_LOGS, arena.Actions.SMB_LOGS_STRONG),
    (arena.Actions.FF_SEARCH, arena.Actions.FF_SEARCH_STRONG),
)

_atk_flat_defs = {
    "val": 5,
}

def atk_flat_rewards(val=_atk_flat_defs["val"]):
    rewards = {}
    for action_group in _atk_action_groups:
        for action in action_group:
            rewards[action] = val
    return rewards

_atk_front_loaded_defs = {
    "val": 10,
    "factor": 0.5,
}

def atk_front_loaded_rewards(
        val=_atk_fromt_loaded_defs["val"],
        factor=_atk_fromt_loaded_defs["factor"]):
    rewards = {}
    for action_group in _atk_action_groups:
        for action in action_group:
            rewards[action] = val
        val *= factor
    return rewards

_atk_all_or_nothing_defs = {
    "val": 20,
}

def atk_all_or_nothing_rewards(val=_atk_all_or_nothing_defs["val"]):
    rewards = []
    for action_group in _atk_action_groups:
        for action in action_group:
            rewards.append([action, 0])
    for i in range(len(_atk_action_groups[-1])):
        rewards[-i] = val
    return rewards

_atk_key_goals_defs = {
    "r_min": 10,
    "r_max": 30,
}

def atk_key_goals_rewards(
        r_min=_atk_key_goals_defs["r_min"],
        r_max=_atk_key_goals_defs["r_max"]):
    rewards = {}
    for action_group in _atk_action_groups:
        reward = random.randint(0, r_max)
        if reward < r_min
            reward = 0
        for action in action_group:
            rewards[action] = reward
    return rewards

_def_increasing_stealth_defs = {
    "noisy_const": 1,
    "camo_initial": 2,
    "increment": 1,
}

def atk_increasing_stealth_cost(
        noisy_const=_def_increasing_stealth_defs["noisy_const"],
        camo_initial=_def_increasing_stealth_defs["camo_initial"]2,
        increment=_def_increasing_stealth_defs["increment"]1):
    costs = {}
    camo_val = camo_initial
    for action_group in _atk_action_groups:
        for action in action_group:
            if action in arena.Attack_Camo_Actions:
                costs[action] = camo_val
            else:
                costs[action] = noisy_const
        camo_val += increment
    return rewards

_def_decreasing_defs = {
    "max_val": None,
    "decrement": 1,
    "ratio": 2,
}

def def_decreasing_cost(
        max_val=_def_decreasing_defs["max_val"],
        decrement=_def_decreasing_defs["decrement"],,
        ratio=_def_decreasing_defs["ratio"]):
    if not max_val:
        max_val = 2 * len(_def_action_groups)
    costs = {}
    g_val = max_val
    for action_group in reversed(_def_action_groups):
        val = g_val
        for i, action in enumerate(reversed(action_group)):
            rewards[action] = val
            val = int(val/ratio)
        g_val -= decrement
    return costs


_atk_reward_functions = {
    "flat": (atk_flat_rewards, _atk_flat_defs),
    "front_loaded": (atk_front_loaded_rewards, _atk_front_loaded_defs),
    "all_or_nothing": (atk_all_or_nothing_rewards, _atk_all_or_nothing_defs),
    "key_goals": (atk_key_goals_rewards, _atk_key_goals_defs),
}

_atk_cost_functions = {
    "increasing_stealth": (atk_increasing_stealth_cost,
        _atk_increasing_stealth_defs),
}

_def_cost_functions = {
    "decreasing": (def_decreasing_cost, _def_decreasing_defs),
}

def available_attack_reward_functions():
    return tuple(_atk_reward_functions.keys())

def available_attack_cost_functions():
    return tuple(_atk_cost_functions.keys())

def available_defend_cost_functions():
    return tuple(_def_cost_functions.keys())

def get_attack_reward_function(func_name):
    f, defs = _atk_reward_functions[func_name]
    return f, dict(defs)

def get_attack_cost_function(func_name):
    f, defs = _atk_cost_functions[func_name]
    return f, dict(defs)

def get_defend_cost_functions(func_name):
    f, defs = _def_cost_functions[func_name]
    return f, dict(defs)
