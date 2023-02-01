# These are game elements shared across the various V2 game versions, in
# particular the actions and their assosciated calculation of
# utilities. There is also a method for converting this information
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

_attack_actions = (
    Actions.WAIT,
    Actions.ADVANCE_NOISY,
    Actions.ADVANCE_CAMO,
)

_defend_actions = (
    Actions.WAIT,
    Actions.DETECT_WEAK,
    Actions.DETECT_STRONG,
)

def attack_actions():
    return _attack_actions

def defend_actions():
    return _defend_actions

class Utility(NamedTuple):
    cost:    int # utility cost
    reward:  int # action success reward
    penalty: int # action failure penalty

_default_utils = {
    Actions.WAIT:          Utility(0, 0, 3),
    Actions.ADVANCE_NOISY: Utility(1, 3, 0),
    Actions.ADVANCE_CAMO:  Utility(2, 3, 0),
    Actions.DETECT_WEAK:   Utility(1, 0, 3),
    Actions.DETECT_STRONG: Utility(2, 0, 3),
}

def default_utilities():
    return _default_utils

# winner action as key
_win = {
    Actions.WAIT: set(),
    Actions.ADVANCE_NOISY: set([Actions.WAIT]),
    Actions.ADVANCE_CAMO: set([Actions.WAIT, Actions.DETECT_WEAK]),
    Actions.DETECT_WEAK: set([Actions.ADVANCE_NOISY]),
    Actions.DETECT_STRONG: set([Actions.ADVANCE_NOISY, Actions.ADVANCE_CAMO]),
}

# loser action as key
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


class ThunderDome():
    """
    The utilities (Utility enums) are wrapped in this class so
    that they can be (potentially) varied dynamically for
    exploratory purposes.
    """

    def __init__(self, utilities=None):
        if utilities is None:
            utilities = default_utilities()
        self._utils = {}
        for action, util in utilities.items():
            if isinstance(util, EnumMeta):
                util = Utility(*util)
            self._utils[action] = util

    @property
    def utilities(self):
        return self._utils

    def consequence(self, action1, action2):
        utils = self._utils[action1]
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

    def action_cmp(self, action1, action2):
        return action_cmp(action1, action2)

    @property
    def actions(self):
        return Actions

    @property
    def attack_actions(self):
        return attack_actions()

    @property
    def defend_actions(self):
        return defend_actions()

    @property
    def players(self):
        return Players

    @property
    def max_cost(self):
        return max(x.cost for x in self.utilities.values())

    @property
    def max_penalty(self):
        return max(x.penalty for x in self.utilities.values())

    @property
    def max_reward(self):
        return max(x.reward for x in self.utilities.values())

    def matrix_args(self):
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
        for row_adv_action in self.attack_actions:
            for col_def_action in self.defend_actions:
                _row_adv_utils.append(
                    self.consequence(row_adv_action, col_def_action))
        # col/defend POV
        _col_def_utils = []
        for col_def_action in self.defend_actions:
            for row_adv_action in self.attack_actions:
                _col_def_utils.append(
                    self.consequence(col_def_action, row_adv_action))
        return [
            [x.name for x in _attack_actions],
            [x.name for x in _defend_actions],
            _row_adv_utils,
            _col_def_utils,
        ]
