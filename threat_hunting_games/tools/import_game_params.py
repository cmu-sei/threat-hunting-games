import os, sys, re, json
from enum import IntEnum
from dataclasses import dataclass, make_dataclass

import pyspiel

from threat_hunting_games import gameload

VERSION = "v3.1"

def assert_version(ver):
    assert ver == VERSION, \
        f"Parameter exporter version mismatch: expected {VERSION}, got {ver}"

current_game = gameload.v3_lockbit_seq
arena = current_game.arena

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

def int_mem_to_json(member):
    return [member.name, member.value]

def int_enum_to_json(enum):
    return [(k, v.value) for k, v in enum.__members__.items()]

def json_to_int_enum(cls, members):
    if isinstance(members, dict):
        members = members.items()
    mbrs = [(k, v) for v, k in sorted((v, k) for k, v in members)]
    return IntEnum(cls, [(k, int(v)) for k, v in mbrs])

def json_to_dataclass(cls, fields, namespace=None):
    return make_dataclass(cls, list(fields), namespace=namespace) 

###

Action_Map = {}

def actions_from_json(actions):
    # This needs to be called before any of the other import functions
    # that deal with actions.
    action_enum = json_to_int_enum("Actions", actions)
    action_map = {}
    for action in action_enum.__members__:
        action_map[action.name] = action
    return action_enum, action_map

def _n2a(action_name):
    return arena.Actions.__members__[action_name]

def action_tuple_from_json(actions):
    # good for Attack_Actions, Defend_Actions, NoOp_Actions
    return tuple(sorted(_n2a(x) for x in actions))

def utilities_from_json(utilities):
    utils = {}
    for k, values in utilities:
        vals = []
        for v in values:
            if v == "ZSUM":
                v = arena.ZSUM
            else:
                v = int(v)
            vals.append(v)
        vals = arena.Utility(*vals)
        utils[k] = vals
    return utils

def timewaits_from_json(timewaits):
    twaits = dict((_n2a(k), arena.TimeWait(*v)) for k, v in timewaits)
    return twaits

def general_fails_from_json(general_fails):
    gfails = dict((_n2a(k), float(v)) for k, v in general_fails)
    return gfails

def skirmish_fails_from_json(skirmish_fails):
    skirmfails = {}
    for action, action_map in skirmish_fails.items():
        amap = {}
        for opp_action, chance in action_map.items():
            amap[_n2a(opp_action)] = float(chance)
        skirmfails[_n2a(action)] = amap
    return skirmfails

def win_actions_from_json(win_map):
    wins = {}
    for action, lose_actions in win_map.items():
        wins[_n2a(action)] = set(_n2a(x) for x in lose_actions)
    return wins

def atk_actions_by_pos_from_json(atk_actions_by_pos):
    atk_by_pos = []
    for actions in atk_actions_by_pos:
        atk_by_pos.append([_n2a(x) for x in actions])
    return atk_by_pos

def game_parameters_from_json(data):
    assert_version(data["version"])

    arena.game_name = data["name"]
    arena.game_long_name = data["long_name"]
    arena.game_max_turns = data["max_turns"]

    arena.Actions = actions_from_json(data["actions"])

    arena.Attack_Actions = action_tuple_from_json(data["attack_actions"])
    arena.Defend_Actions = action_tuple_from_json(data["defend_actions"])
    arena.NoOp_Actions = action_tuple_from_json(data["noop_actions"])
    arena.Utilities = utilities_from_json(data["utilities"])
    arena.TimeWaits = timewaits_from_json(data["timewaits"])
    arena.General_Fails = general_fails_from_json(data["general_fails"])
    arena.Skirmish_Fails = skirmish_fails_from_json(data["skirmish_fails"])
    arena.Win = win_actions_from_json(data["win_actions"])
    arena.infer_lose()

    arena.assert_arena_parameters()

def dump_game_parameters(fh=None, params=None, indent=2):
    if not fh:
        fh = sys.stdout
    elif not hasattr(fh, "close"):
        fh = open(fh, "w")
    if not params:
        params = game_parameters_to_json()
    json.dump(params, fh, indent=indent)
