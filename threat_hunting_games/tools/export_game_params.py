import os, sys, re, json
from enum import IntEnum
from dataclasses import dataclass, make_dataclass

import pyspiel

from threat_hunting_games import gameload
import import_game_params

VERSION = import_game_params.VERSION

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

def actions_to_json(action_enum=None):
    if not action_enum:
        action_enum = arena.Actions
    actions = int_enum_to_json(action_enum)
    return actions

def attack_actions_to_json(actions=None):
    if not actions:
        actions = arena.Attack_Actions
    return [x.name for x in actions]

def defend_actions_to_json(actions=None):
    if not actions:
        actions = arena.Defend_Actions
    return [x.name for x in actions]

def noop_actions_to_json(actions=None):
    if not actions:
        actions = arena.NoOp_Actions
    return [x.name for x in actions]

def utilities_to_json(utilities=None):
    if not utilities:
        utilities = arena.Utilities
    utils = {}
    for action, util in utilities.items():
        action = action.name
        values = [x if x != arena.ZSUM else "ZSUM" for x in util]
        utils[action] = values
    return utils

def timewaits_to_json(timewaits=None):
    if not timewaits:
        timewaits = arena.TimeWaits
    twaits = {}
    twaits = dict((k.name, list(v)) for k, v in timewaits.items())
    return twaits

def general_fails_to_json(general_fails=None):
    if not general_fails:
        general_fails = arena.GeneralFails
    gfails = dict((k.name, v) for k, v in general_fails.items())
    return gfails

def skirmish_fails_to_json(skirmish_fails=None):
    if not skirmish_fails:
        skirmish_fails = arena.SkirmishFails
    skirmfails = {}
    for action, action_map in skirmish_fails.items():
        action = action.name
        oppose_actions = dict((k.name, v) for k, v in action_map.items())
        skirmfails[action] = oppose_actions
    return skirmfails

def win_actions_to_json(winmap=None):
    if not winmap:
        winmap = arena.Win
    wins = {}
    for action, action_map in winmap.items():
        action = action.name
        lose_actions = [x.name for x in sorted(action_map)]
        wins[action] = lose_actions
    return wins

def atk_actions_by_pos_to_json(atk_actions_by_pos=None):
    if not atk_actions_by_pos:
        atk_actions_by_pos = current_game.Atk_Actions_By_Pos
    atk_by_pos = []
    for actions in atk_actions_by_pos:
        atk_by_pos.append([x.name for x in actions])
    return atk_by_pos

def game_parameters_to_json():
    game = {
        "version": VERSION,
        "name": current_game.game_name,
        "long_name": current_game.game_long_name,
        "max_turns": current_game.game_max_turns,
        "actions": actions_to_json(),
        "attack_actions": attack_actions_to_json(),
        "defend_actions": defend_actions_to_json(),
        "noop_actions": noop_actions_to_json(),
        "utilities": utilities_to_json(),
        "timewaits": timewaits_to_json(),
        "general_fails": general_fails_to_json(),
        "skirmish_fails": skirmish_fails_to_json(),
        "win_actions": win_actions_to_json(),
        "atk_actions_by_pos": atk_actions_by_pos_to_json(),
    }
    return game

def dump_game_parameters(fh=None, params=None, indent=2):
    if not fh:
        fh = sys.stdout
    elif not hasattr(fh, "close"):
        fh = open(fh, "w")
    if not params:
        params = game_parameters_to_json()
    json.dump(params, fh, indent=indent)
