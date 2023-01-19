import os, sys, re, json

import pyspiel

import gameload

cc2snake_re = re.compile(r"(?<!^)(?=[A-Z])")
def _cc2snake(item: str):
    return cc2snake_re.sub('_', item).lower()

def _deserialize(item):
    if m := re.search(r'^"(.*)"$', item):
        item = m.group(1)
    try:
        value = json.loads("[%s]" % item)
        if value:
            value = value[0]
        else:
            value = None
    except json.decoder.JSONDecodeError:
        value = item
    return value

def parse_playthrough(text):
    bout = {}
    cur_state = cur_actions = cur_actions_str = None
    for line in (x.strip() for x in text.split("\n")):
        if not line:
            continue
        if m := re.search(r"game:\s+(.*)", line):
            bout["name"] = m.group(1)
            game = pyspiel.load_game(bout["name"])
            for attr in [
                    'num_distinct_actions',
                    'policy_tensor_shape',
                    'max_chance_outcomes',
                    'get_parameters',
                    'num_players',
                    'min_utility',
                    'max_utility',
                    'utility_sum',
                    'information_state_tensor_shape',
                    'information_state_tensor_layout',
                    'information_state_tensor_size',
                    'observation_tensor_shape',
                    'observation_tensor_layout',
                    'observation_tensor_size',
                    'max_game_length',
                    ]:
                value = getattr(game, attr)()
                try:
                    json.dumps(value)
                except TypeError:
                    value = str(value)
                bout[attr] = value
            bout["to_string"] = str(game)
            game_type = game.get_type()
            gt = bout["GameType"] = {}
            for attr in [
                    "parameter_specification",
                    "provides_information_state_string",
                    "provides_information_state_tensor",
                    "provides_observation_string",
                    "provides_observation_tensor",
                    "provides_factored_observation_string",
                    "reward_model",
                    "short_name",
                    "utility",
                    ]:
                value = getattr(game_type, attr)
                if callable(value):
                    value = value()
                try:
                    json.dumps(value)
                except TypeError:
                    value = str(value)
                gt[attr] = value
        if not bout["name"]:
            continue
        if m := re.search(r"Apply\s+joint\s+action\s+(.*)", line):
            cur_actions_str = _deserialize(m.group(1))
            next
        if m:= re.search(r"actions:\s+(.*)", line):
            cur_actions = _deserialize(m.group(1))
            next
        if "states" not in bout:
            bout["states"] = []
        if m := re.search(r"State\s+(\d+)", line):
            bout["states"].append([cur_actions, cur_actions_str, {}])
            cur_state = bout["states"][-1][-1]
            continue
        if cur_state is None:
            continue
        if m := re.search(r"^(\w+)\((\d+)?\)\s+=\s+(.*)", line):
            attr = _cc2snake(m.group(1))
            player = int(m.group(2)) if m.group(2) else None
            value = _deserialize(m.group(3))
            if player is not None:
                if attr not in cur_state:
                    cur_state[attr] = []
                cur_state[attr].append(value)
            else:
                cur_state[attr] = value
            continue
    return bout

def parse_playthrough_file(fh):
    if not hasattr(fh, "fileno"):
        fh = open(fh)
    return parse_playthrough(fh.read())
