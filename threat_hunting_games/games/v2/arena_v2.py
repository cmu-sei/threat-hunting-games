# These are game elements shared across the various V2 game versions, in
# particular the actions and their assosciated calculation of
# utilities. There is also a function for converting this information
# into matrix form.

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum, EnumMeta

class Players(IntEnum):
    # the values of these Player enums are used as 0-based indices later
    # -- also hence IntEnum
    ATTACKER = 0
    DEFENDER = 1

class Actions(IntEnum):
    WAIT = 0
    ADVANCE_NOISY = 1
    ADVANCE_CAMO = 2
    DETECT_WEAK = 3
    DETECT_STRONG = 4

Attack_Actions = frozenset((
    Actions.WAIT,
    Actions.ADVANCE_NOISY,
    Actions.ADVANCE_CAMO,
))
Legal_Attack_Actions = tuple(sorted(Attack_Actions))

Defend_Actions = frozenset((
    Actions.WAIT,
    Actions.DETECT_WEAK,
    Actions.DETECT_STRONG,
))
Legal_Defend_Actions = tuple(sorted(Defend_Actions))

def player_to_string(player):
    return Players(int(player)).name.title()

def action_to_string(action):
    return Actions(int(action)).name.title()

class Utility(NamedTuple):
    cost:    int # utility cost
    reward:  int # action success reward
    penalty: int # action failure penalty

# the following values for utilities can potentially be overridden for
# parameter exploration; results depending on these utilities are
# expressed as functions
Utilities = {
    Actions.WAIT:          Utility(0, 0, 3),
    Actions.ADVANCE_NOISY: Utility(1, 3, 0),
    Actions.ADVANCE_CAMO:  Utility(2, 3, 0),
    Actions.DETECT_WEAK:   Utility(1, 0, 3),
    Actions.DETECT_STRONG: Utility(2, 0, 3),
}

def max_cost():
    return max(x.cost for x in Utilities.values())

def max_penalty():
    return max(x.penalty for x in Utilities.values())

def max_reward():
   return max(x.reward for x in Utilities.values())

def max_utility():
    return max((x.reward - x.cost) for x in Utilities.values())

def min_utility():
    return min((-x.cost - x.penalty) for x in Utilities.values())

# winner action as key, including no-ops (empty set)
_win = {
    Actions.WAIT: set(),
    Actions.ADVANCE_NOISY: set([Actions.WAIT]),
    Actions.ADVANCE_CAMO: set([Actions.WAIT, Actions.DETECT_WEAK]),
    Actions.DETECT_WEAK: set([Actions.ADVANCE_NOISY]),
    Actions.DETECT_STRONG: set([Actions.ADVANCE_NOISY, Actions.ADVANCE_CAMO]),
}

# loser action as key, including no-ops (empty set)
_lose = {}
for win_action in Actions:
    if win_action not in _lose:
        _lose[win_action] = set()
    for lose_action in _win[win_action]:
        if lose_action not in _lose:
            _lose[lose_action] = set()
        _lose[lose_action].add(win_action)

def action_cmp(action1, action2):
    if action2 in _win[action1]:
        return True
    elif action2 in _lose[action1]:
        return False
    else:
        return None # no-op

def consequence(action1, action2):
    utils = Utilities[action1]
    match action_cmp(action1, action2):
        case True:
            util = utils.reward - utils.cost
        case False:
            util = -utils.penalty - utils.cost
        case None:
            util = -utils.cost
        case _:
            raise ValueError(f"bad val")
    return util

def matrix_args():
    """
    Return the last four arguments required by MatrixGame():

      pyspiel.MatrixGame(
          game_type,
          params,
          row_action_names,
          col_action_names,
          row_utilities,
          col_utilities
      )

    """

    # row/attack POV
    _row_adv_utils = []
    for row_adv_action in Legal_Attack_Actions:
        for col_def_action in Legal_Defend_Actions:
            _row_adv_utils.append(
                consequence(row_adv_action, col_def_action))
    # col/defend POV
    _col_def_utils = []
    for col_def_action in Legal_Defend_Actions:
        for row_adv_action in Legal_Attack_Actions:
            _col_def_utils.append(
                consequence(col_def_action, row_adv_action))
    return [
        [x.name for x in Legal_Attack_Actions],
        [x.name for x in Legal_Defend_Actions],
        _row_adv_utils,
        _col_def_utils,
    ]
