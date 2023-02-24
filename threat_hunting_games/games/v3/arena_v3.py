# These are game elements shared across the various V2 game versions, in
# particular the actions and their assosciated calculation of
# utilities. There is also a function for converting this information
# into matrix form.

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum, auto
import random

class Players(IntEnum):
    # the values of these Player enums are used as 0-based indices later
    # -- also hence IntEnum
    ATTACKER = 0
    DEFENDER = 1

class Actions(IntEnum):
    WAIT = auto()
    IN_PROGRESS = auto()
    S0_VERIFY_PRIV = auto()
    S0_VERIFY_PRIV_CAMO = auto()
    S1_WRITE_EXE = auto()
    S1_WRITE_EXE_CAMO = auto()
    S2_ENCRYPT = auto()
    S2_ENCRYPT_CAMO = auto()
    PSGREP = auto()
    PSGREP_STRONG = auto()
    SMB_LOGS = auto()
    SMB_LOGS_STRONG = auto()
    FF_SEARCH = auto()
    FF_SEARCH_STRONG = auto()

Attack_Actions = tuple(sorted([
    # do not include IN_PROGRESS
    Actions.WAIT,
    Actions.S0_VERIFY_PRIV,
    Actions.S0_VERIFY_PRIV_CAMO,
    Actions.S1_WRITE_EXE,
    Actions.S1_WRITE_EXE_CAMO,
    Actions.S2_ENCRYPT,
    Actions.S2_ENCRYPT_CAMO,
]))

Defend_Actions = tuple(sorted([
    # do not include IN_PROGRESS
    Actions.WAIT,
    Actions.PSGREP,
    Actions.PSGREP_STRONG,
    Actions.SMB_LOGS,
    Actions.SMB_LOGS_STRONG,
    Actions.FF_SEARCH,
    Actions.FF_SEARCH_STRONG,
]))

NoOp_Actions = tuple(sorted([
    Actions.WAIT,
    Actions.IN_PROGRESS
]))

def player_to_string(player: Actions) -> str:
    return Players(int(player)).name.title()

def action_to_string(action: Actions) -> str:
    return Actions(int(action)).name.title()

class Utility(NamedTuple):
    cost:    int # utility cost
    reward:  int # action success reward (only attacker for now)
    damage:  int # cost to opposition if successful action

# ZSUM:
#
#   derived value of reward/damage (note that explicit integers can
#   always be used instead of ZSUM)
#
#   example:
#
#   defender action:     SMB_LOGS Utility(2, ZSUM, ZSUM)
#   attacker action: S1_WRITE_EXE Utility(2,    4, ZSUM)
#
#   defender damage (SMB_LOGS) =
#     SMB_LOGS.damage = ZSUM =
#       SMB_LOGS.reward = ZSUM =
#         S1_WRITE_EXE.damage = ZSUM =
#           S1_WRITE_EXE.reward (4)
#              ... if S1_WRITE_EXE.reward is ZSUM, that's a loop exception
#
# See the winner/loser maps below for which actions are effective
# against other actions. See the attack_reward(),
# attack_damage(), defend_reward(), and defend_damage() functions below
# to see the logic implemented -- and consequence() that uses those to
# tally utility for any particular action vs action.

ZSUM = None

# the following values for utilities can potentially be overridden for
# parameter exploration; results depending on these utilities are
# expressed as functions, so overriding the values of this map will
# still work.
Utilities = {
    Actions.WAIT:                Utility(0, 0, 0),
    Actions.IN_PROGRESS:         Utility(1, 0, 0),
    Actions.S0_VERIFY_PRIV:      Utility(1, 3, ZSUM),
    Actions.S0_VERIFY_PRIV_CAMO: Utility(2, 3, ZSUM),
    Actions.S1_WRITE_EXE:        Utility(2, 4, ZSUM),
    Actions.S1_WRITE_EXE_CAMO:   Utility(3, 4, ZSUM),
    Actions.S2_ENCRYPT:          Utility(3, 5, ZSUM),
    Actions.S2_ENCRYPT_CAMO:     Utility(4, 5, ZSUM),
    # defense takes away attacker reward and gains back damage
    Actions.PSGREP:              Utility(1, ZSUM, ZSUM),
    Actions.PSGREP_STRONG:       Utility(2, ZSUM, ZSUM),
    Actions.SMB_LOGS:            Utility(2, ZSUM, ZSUM),
    Actions.SMB_LOGS_STRONG:     Utility(2, ZSUM, ZSUM),
    Actions.FF_SEARCH:           Utility(2, ZSUM, ZSUM),
    Actions.FF_SEARCH_STRONG:    Utility(2, ZSUM, ZSUM),
}

for action in Actions:
    utils = Utilities[action]
    if utils.cost is None:
        raise ValueError(
        f"action cost must have int value")
for action in Attack_Actions:
    utils = Utilities[action]
    if utils.reward is ZSUM:
        raise ValueError(
        f"attack action reward must have int value: {utils.reward}")


class TimeWait(NamedTuple):
    min: int
    max: int

    def turns(self) -> int:
        return random.randint(self.min, self.max)

# min/max wait actions preceeding the given action
TimeWaits = {
    Actions.WAIT:                TimeWait(0, 0),
    Actions.IN_PROGRESS:         TimeWait(0, 0),
    Actions.S0_VERIFY_PRIV:      TimeWait(1, 4),
    Actions.S0_VERIFY_PRIV_CAMO: TimeWait(2, 5),
    Actions.S1_WRITE_EXE:        TimeWait(1, 4),
    Actions.S1_WRITE_EXE_CAMO:   TimeWait(2, 5),
    Actions.S2_ENCRYPT:          TimeWait(1, 4),
    Actions.S2_ENCRYPT_CAMO:     TimeWait(2, 5),
    Actions.PSGREP:              TimeWait(1, 4),
    Actions.PSGREP_STRONG:       TimeWait(2, 5),
    Actions.SMB_LOGS:            TimeWait(1, 4),
    Actions.SMB_LOGS_STRONG:     TimeWait(2, 5),
    Actions.FF_SEARCH:           TimeWait(1, 4),
    Actions.FF_SEARCH_STRONG:    TimeWait(2, 5),
}

def get_timewait(action):
    return TimeWaits.get(action, TimeWait(0, 0))

ChanceFail = {
    Actions.S0_VERIFY_PRIV:      0.15,
    Actions.S0_VERIFY_PRIV_CAMO: 0.15,
    Actions.S1_WRITE_EXE:        0.15,
    Actions.S1_WRITE_EXE_CAMO:   0.15,
    Actions.S2_ENCRYPT:          0.15,
    Actions.S2_ENCRYPT_CAMO:     0.15,
    Actions.PSGREP:              0.15,
    Actions.PSGREP_STRONG:       0.15,
    Actions.SMB_LOGS:            0.15,
    Actions.SMB_LOGS_STRONG:     0.15,
    Actions.FF_SEARCH:           0.15,
    Actions.FF_SEARCH_STRONG:    0.15,
}

def get_chance_fail(action):
    return ChanceFail.get(action, 0.0)

def action_succeeded(action):
    pct = get_chance_fail(action)
    if pct:
        result = random.random() > pct
        if not result:
            print("ACTION FAIL!", action)
        return result
    else:
        return True

# Winner/Loser action maps. This first one is Winner action as key; note
# that WAIT and IN_PROGRESS are essentially no-ops in terms of win/lose
# due to the asynchronous nature of when advance/detect actions square
# off; if this were a simultaneous game then the passive actions WAIT
# and IN_PROGRESS could be included with empty set (they win aganst no
# actions), but that isn't necessary here. For the active action keys
# below, the actions that are commented out are the actions that the
# given action will lose to.
Win = {
    #Actions.WAIT: set(),
    #Actions.IN_PROGRESS: set(),
    Actions.S0_VERIFY_PRIV: set([
        Actions.WAIT,
        Actions.IN_PROGRESS,
        # Actions.PSGREP,
        # Actions.PSGREP_STRONG,
        Actions.SMB_LOGS,
        Actions.SMB_LOGS_STRONG,
        Actions.FF_SEARCH,
        Actions.FF_SEARCH_STRONG,
    ]),
    Actions.S0_VERIFY_PRIV_CAMO: set([
        Actions.WAIT,
        Actions.IN_PROGRESS,
        Actions.PSGREP,
        # Actions.PSGREP_STRONG,
        Actions.SMB_LOGS,
        Actions.SMB_LOGS_STRONG,
        Actions.FF_SEARCH,
        Actions.FF_SEARCH_STRONG,
    ]),
    Actions.S1_WRITE_EXE: set([
        Actions.WAIT,
        Actions.IN_PROGRESS,
        Actions.PSGREP,
        Actions.PSGREP_STRONG,
        # Actions.SMB_LOGS,
        # Actions.SMB_LOGS_STRONG,
        Actions.FF_SEARCH,
        Actions.FF_SEARCH_STRONG,
    ]),
    Actions.S1_WRITE_EXE_CAMO: set([
        Actions.WAIT,
        Actions.IN_PROGRESS,
        Actions.PSGREP,
        Actions.PSGREP_STRONG,
        Actions.SMB_LOGS,
        # Actions.SMB_LOGS_STRONG,
        Actions.FF_SEARCH,
        Actions.FF_SEARCH_STRONG,
    ]),
    Actions.S2_ENCRYPT: set([
        Actions.WAIT,
        Actions.IN_PROGRESS,
        Actions.PSGREP,
        Actions.PSGREP_STRONG,
        Actions.SMB_LOGS,
        Actions.SMB_LOGS_STRONG,
        #Actions.FF_SEARCH,
        #Actions.FF_SEARCH_STRONG,
    ]),
    Actions.S2_ENCRYPT_CAMO: set([
        Actions.WAIT,
        Actions.IN_PROGRESS,
        Actions.PSGREP,
        Actions.PSGREP_STRONG,
        Actions.SMB_LOGS,
        Actions.SMB_LOGS_STRONG,
        Actions.FF_SEARCH,
        #Actions.FF_SEARCH_STRONG,
    ]),
    Actions.PSGREP: set([
        Actions.S0_VERIFY_PRIV,
        #Actions.S0_VERIFY_PRIV_CAMO,
        #Actions.S1_WRITE_EXE,
        #Actions.S1_WRITE_EXE_CAMO,
        #Actions.S2_ENCRYPT,
        #Actions.S2_ENCRYPT_CAMO,
    ]),
    Actions.PSGREP_STRONG: set([
        Actions.S0_VERIFY_PRIV,
        Actions.S0_VERIFY_PRIV_CAMO,
        #Actions.S1_WRITE_EXE,
        #Actions.S1_WRITE_EXE_CAMO,
        #Actions.S2_ENCRYPT,
        #Actions.S2_ENCRYPT_CAMO,
    ]),
    Actions.SMB_LOGS: set([
        #Actions.S0_VERIFY_PRIV,
        #Actions.S0_VERIFY_PRIV_CAMO,
        Actions.S1_WRITE_EXE,
        #Actions.S1_WRITE_EXE_CAMO,
        #Actions.S2_ENCRYPT,
        #Actions.S2_ENCRYPT_CAMO,
    ]),
    Actions.SMB_LOGS_STRONG: set([
        #Actions.S0_VERIFY_PRIV,
        #Actions.S0_VERIFY_PRIV_CAMO,
        Actions.S1_WRITE_EXE,
        Actions.S1_WRITE_EXE_CAMO,
        #Actions.S2_ENCRYPT,
        #Actions.S2_ENCRYPT_CAMO,
    ]),
    Actions.FF_SEARCH: set([
        #Actions.S0_VERIFY_PRIV,
        #Actions.S0_VERIFY_PRIV_CAMO,
        #Actions.S1_WRITE_EXE,
        #Actions.S1_WRITE_EXE_CAMO,
        Actions.S2_ENCRYPT,
        #Actions.S2_ENCRYPT_CAMO,
    ]),
    Actions.FF_SEARCH_STRONG: set([
        #Actions.S0_VERIFY_PRIV,
        #Actions.S0_VERIFY_PRIV_CAMO,
        #Actions.S1_WRITE_EXE,
        #Actions.S1_WRITE_EXE_CAMO,
        Actions.S2_ENCRYPT,
        Actions.S2_ENCRYPT_CAMO,
    ]),
}

# loser action as key
Lose = {}
for win_action in Win:
    if win_action not in Lose:
        Lose[win_action] = set()
    for lose_action in Win[win_action]:
        if lose_action not in Lose:
            Lose[lose_action] = set()
        Lose[lose_action].add(win_action)

active_actions = set(Actions).difference([Actions.WAIT, Actions.IN_PROGRESS])
missing = active_actions - set(Win)
if missing:
    raise ValueError(f"Missing win actions: {missing}")
missing = active_actions - set(Lose)
if missing:
    raise ValueError(f"Missing lose actions: {missing}")

def action_cmp(action1: Actions, action2: Actions) -> bool:
    result = None
    if action2 in Win[action1]:
        # action1 wins
        result = True
    elif action2 in Lose[action1]:
        # action2 wins
        result = False
    else:
        # no-op (doesn't happen without WAIT and IN_PROGRESS in
        # Win/Lose)
        pass
    return result

def attack_reward(action: Actions):
    utils = Utilities[action]
    return utils.reward

def attack_damage(action: Actions) -> int:
    utils = Utilities[action]
    damage = utils.damage
    if damage is ZSUM:
        damage = attack_reward(action)
    if damage is ZSUM:
        raise ValueError(
            f"attack damage {action} {utils} ZSUM loop")
    return damage

def defend_reward(action: Actions, attack_action: Actions) -> int:
    # reward received for action1
    utils = Utilities[action]
    attack_utils = Utilities[attack_action]
    reward = utils.reward
    if reward is ZSUM:
        reward = attack_damage(attack_action)
    if reward is ZSUM:
        raise ValueError(
            f"defend reward {action} {utils} {attack_action} {attack_utils}  ZSUM loop")
    return reward

def defend_damage(action: Actions, attack_action: Actions) -> int:
    # damage dealt by actionn1
    utils = Utilities[action]
    attack_utils = Utilities[attack_action]
    damage = utils.damage
    if damage is ZSUM:
        damage = utils.reward
        if damage is ZSUM:
            damage = attack_damage(attack_action)
    if damage is ZSUM:
        raise ValueError(
            f"defend damage {action} {utils} {attack_action} {attack_utils} ZSUM loop")
    return damage

def consequence(action1: Actions, action2: Actions) -> int:
    # resulting utility (not including action costs) for action1 when it
    # squares off with action2

    if not set([action1, action2]).difference(Attack_Actions) \
            or not set([action1, action2]).difference(Defend_Actions):
        raise ValueError(f"must provide one attack, one defend action: [{action1}, {action2}]")

    if action1 in Attack_Actions:
        print("\n consq attack reward")
        reward = attack_reward(action1)
        print("\n consq defend damage")
        damage = defend_damage(action2, action1)
        print("\n")
    else:
        print("\n consq defend reward")
        reward = defend_reward(action1, action2)
        print("\n consq attack damage")
        damage = attack_damage(action2)
        print("\n")

    util = 0
    match action_cmp(action1, action2):
        # don't include costs here because of asynchronus
        # resolution in v3
        case True:
            #util = utils1.reward - utils1.cost
            util = reward
        case False:
            #util = -utils2.damage - utils1.cost
            util = -damage
        case None:
            #util = -utils.cost
            util = 0
    return util

class MinMaxUtil(NamedTuple):
    min: int | None
    max: int | None

_min_max_util = MinMaxUtil(None, None)

def max_utility() -> int:
    # per turn
    if _min_max_util.max is not None:
        return _min_max_util.max
    max_util = 0
    for action in Actions:
        if action not in Win:
            continue
        win_cost = Utilities[action].cost
        max_win = 0
        for lose_action in Win.get(action, []):
            if lose_action in Defend_Actions:
                win_reward = attack_reward(action)
            else:
                win_reward = defend_reward(action, lose_action)
            win_util = win_cost + win_reward
            if win_util > max_win:
                max_win = win_util
        if Utilities[Actions.IN_PROGRESS].cost:
            # subtract costs of maximum possible IN_PROGRESS actions
            if TimeWaits.get(action):
                max_win -= TimeWaits[action].max \
                        * Utilities[Actions.IN_PROGRESS].cost
        if max_win > max_util:
            max_util = max_win
    _min_max_util._replace(max=max_util)
    return max_util

def min_utility() -> int:
    # per turn
    if _min_max_util.min is not None:
        return _min_max_util.min
    min_util = 0
    for action in Actions:
        if action not in Lose:
            continue
        lose_cost = Utilities[action].cost
        min_lose = 0
        for win_action in Lose.get(action, []):
            if win_action in Attack_Actions:
                win_damage = attack_damage(win_action)
            else:
                win_damage = defend_damage(win_action, action)
            lose_util = lose_cost + win_damage
            if lose_util > min_lose:
                min_lose = lose_util
        if Utilities[Actions.IN_PROGRESS].cost:
            # add costs of maximum possible IN_PROGRESS actions
            if TimeWaits.get(action):
                min_lose += TimeWaits[action].max \
                        * Utilities[Actions.IN_PROGRESS].cost
        if min_lose > min_util:
            min_util = min_lose
    min_util *= -1
    _min_max_util._replace(min=min_util)
    return min_util

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
    for row_adv_action in Attack_Actions:
        for col_def_action in Defend_Actions:
            _row_adv_utils.append(
                consequence(row_adv_action, col_def_action))
    # col/defend POV
    _col_def_utils = []
    for col_def_action in Defend_Actions:
        for row_adv_action in Attack_Actions:
            _col_def_utils.append(
                consequence(col_def_action, row_adv_action))
    return [
        [x.name for x in Attack_Actions],
        [x.name for x in Defend_Actions],
        _row_adv_utils,
        _col_def_utils,
    ]
