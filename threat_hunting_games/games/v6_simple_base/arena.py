# These are game elements shared across the various V2 game versions, in
# particular the actions and their assosciated calculation of
# utilities. There is also a function for converting this information
# into matrix form.

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum, auto
import random

import pyspiel

DEBUG = True

USE_WAITS = False
USE_TIMEWAITS = False
USE_CHANCE_FAIL = False

def debug(*args, **kwargs):
    '''
    Logging module tends to obliterate log levels when set at the outset
    of module load, so, we roll our own. Strings passed to this will be
    already interpolated, so keep that in mind if the {interpolation} is
    calling methods/functions.
    '''
    DEBUG and print(*args, **kwargs)

# I ran into difficulties trying to put attack/defend actions in their
# own IntEnums (0, 1, 2 value for each). Pyspiel will blow up if the
# action values are not indeed distinct.

class Players(IntEnum):
    # the values of these Player enums are used as 0-based indices later
    # in GameState._assert_action(s) -- also hence IntEnum
    ATTACKER = 0
    DEFENDER = 1

ZERO_BASED_ACTIONS = True

def _action_idx(val):
    # note: cant use auto()-1 because auto() returns an enum.auto which
    # cannot interact with ints or be converted to one. <shrug>
    assert val > 0
    return val-1 if ZERO_BASED_ACTIONS else val

class Actions(IntEnum):
    '''
    Both players; auto() starts at 1; some OpenSpiel
    examples/algorithms test truthiness on action policies, so don't
    start action counts at 0

    On the other hand, algorithms/random_agent.py assigns even
    distributions using numpy array slices, which fail unless the
    indices of actions start with 0.

    Hence the ZERO_BASED_ACTIONS flag for picking which you need.
    '''
    WAIT             = _action_idx(1)
    IN_PROGRESS      = _action_idx(2)
    # attacker
    S0_ADVANCE       = _action_idx(3)
    S0_ADVANCE_CAMO  = _action_idx(4)
    S1_ADVANCE       = _action_idx(5)
    S1_ADVANCE_CAMO  = _action_idx(6)
    S2_ADVANCE       = _action_idx(7)
    S2_ADVANCE_CAMO  = _action_idx(8)
    S3_ADVANCE       = _action_idx(7)
    S3_ADVANCE_CAMO  = _action_idx(8)
    S4_ADVANCE       = _action_idx(7)
    S4_ADVANCE_CAMO  = _action_idx(8)
    # defender
    S0_DETECT        = _action_idx(9)
    S0_DETECT_STRONG = _action_idx(10)
    S1_DETECT        = _action_idx(11)
    S1_DETECT_STRONG = _action_idx(12)
    S2_DETECT        = _action_idx(13)
    S2_DETECT_STRONG = _action_idx(14)
    S3_DETECT        = _action_idx(13)
    S3_DETECT_STRONG = _action_idx(14)
    S4_DETECT        = _action_idx(13)
    S4_DETECT_STRONG = _action_idx(14)

Attack_Actions = tuple(sorted([
    # do not include IN_PROGRESS
    Actions.WAIT,
    Actions.S0_ADVANCE_CAMO,
    Actions.S1_ADVANCE,
    Actions.S1_ADVANCE_CAMO,
    Actions.S2_ADVANCE,
    Actions.S2_ADVANCE_CAMO,
    Actions.S3_ADVANCE,
    Actions.S3_ADVANCE_CAMO,
    Actions.S4_ADVANCE,
    Actions.S4_ADVANCE_CAMO,
]))

Defend_Actions = tuple(sorted([
    # Do not include IN_PROGRESS
    Actions.WAIT,
    Actions.S0_DETECT,
    Actions.S0_DETECT_STRONG,
    Actions.S1_DETECT,
    Actions.S1_DETECT_STRONG,
    Actions.S2_DETECT,
    Actions.S2_DETECT_STRONG,
    Actions.S3_DETECT,
    Actions.S3_DETECT_STRONG,
    Actions.S4_DETECT,
    Actions.S4_DETECT_STRONG,
]))

NoOp_Actions = tuple(sorted([
    Actions.WAIT,
    Actions.IN_PROGRESS,
]))

Player_Actions = {
    Players.ATTACKER: Attack_Actions,
    Players.DEFENDER: Defend_Actions,
}


def player_to_str(player: Players) -> str:
    '''
    Call the enum in case given player is an int
    '''
    if player is not None:
        return Players(player).name.title()
    else:
        return "None"

# shorthand option
p2s = player_to_str

def action_to_str(action: Actions) -> str:
    '''
    Call the enum in case given action is an int
    '''
    if action is not None:
        if action == pyspiel.INVALID_ACTION:
            return "Invalid_Action"
        else:
            return Actions(action).name.title()
    else:
        return "None"

# shorthand option
a2s = action_to_str

Attack_Noisy_Actions = tuple(sorted(
    x for x in Attack_Actions if a2s(x).upper().endswith("ADVANCE")))

Attack_Camo_Actions = tuple(sorted(
    x for x in Attack_Actions if a2s(x).upper().endswith("CAMO")))

Defend_Weak_Actions = tuple(sorted(
    x for x in Defend_Actions if a2s(x).upper().endswith("DETECT")))

Defend_Strong_Actions = tuple(sorted(
    x for x in Attack_Actions if a2s(x).upper().endswith("STRONG")))

# Attacker is operating off of a kill chain -- at any given point in the
# chain, the attacker will have three options: next action, next action
# (camo), and WAIT. IN_PROGRESS actions are injected and handled by
# GameState.
#
# This should be turned into a class that can make more complicated
# decisions such as in an attack graph.
Atk_Actions_By_Pos = (
    (
      # pos 0
      Actions.WAIT,
      Actions.S0_ADVANCE,
      Actions.S0_ADVANCE_CAMO,
    ),
    (
      # pos 1
      Actions.WAIT,
      Actions.S1_ADVANCE,
      Actions.S1_ADVANCE_CAMO,
    ),
    (
      # pos 2
      Actions.WAIT,
      Actions.S2_ADVANCE,
      Actions.S2_ADVANCE_CAMO,
    ),
    (
      # pos 3
      Actions.WAIT,
      Actions.S3_ADVANCE,
      Actions.S3_ADVANCE_CAMO,
    ),
    (
      # pos 4
      Actions.WAIT,
      Actions.S4_ADVANCE,
      Actions.S4_ADVANCE_CAMO,
    ),
)


# Corresponding defend actions
Def_Actions_By_Pos = (
    (
      # pos 0
      Actions.WAIT,
      Actions.S0_DETECT,
      Actions.S0_DETECT_STRONG,
    ),
    (
      # pos 1
      Actions.WAIT,
      Actions.S1_DETECT,
      Actions.S1_DETECT_STRONG,
    ),
    (
      # pos 2
      Actions.WAIT,
      Actions.S2_DETECT,
      Actions.S2_DETECT_STRONG,
    ),
    (
      # pos 3
      Actions.WAIT,
      Actions.S3_DETECT,
      Actions.S3_DETECT_STRONG,
    ),
    (
      # pos 4
      Actions.WAIT,
      Actions.S4_DETECT,
      Actions.S4_DETECT_STRONG,
    ),
)

Player_Actions_By_Pos = {
    Players.ATTACKER: Atk_Actions_By_Pos,
    Players.DEFENDER: Def_Actions_By_Pos,
}


class Utility(NamedTuple):
    '''
    This is one way to look at utilities; right now there is typically
    equivalence between reward/damage.
    '''
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
# See the fail/win maps below for which actions are effective
# against other actions. See the attack_reward(),
# attack_damage(), defend_reward(), and defend_damage() functions below
# to see the logic implemented .

class ZSUM():
    pass

Advancement_Flat_Rewards = {
    Actions.S0_ADVANCE:       Utility(1, 2, ZSUM),
    Actions.S0_ADVANCE_CAMO:  Utility(2, 2, ZSUM),
    Actions.S1_ADVANCE:       Utility(1, 2, ZSUM),
    Actions.S1_ADVANCE_CAMO:  Utility(2, 2, ZSUM),
    Actions.S2_ADVANCE:       Utility(1, 2, ZSUM),
    Actions.S2_ADVANCE_CAMO:  Utility(2, 2, ZSUM),
    Actions.S3_ADVANCE:       Utility(1, 2, ZSUM),
    Actions.S3_ADVANCE_CAMO:  Utility(2, 2, ZSUM),
    Actions.S4_ADVANCE:       Utility(1, 2, ZSUM),
    Actions.S4_ADVANCE_CAMO:  Utility(2, 2, ZSUM),
}

Advancement_Escalating_Rewards = {
    Actions.S0_ADVANCE:       Utility(1, 1,  ZSUM),
    Actions.S0_ADVANCE_CAMO:  Utility(2, 1,  ZSUM),
    Actions.S1_ADVANCE:       Utility(1, 2,  ZSUM),
    Actions.S1_ADVANCE_CAMO:  Utility(2, 2,  ZSUM),
    Actions.S2_ADVANCE:       Utility(1, 4,  ZSUM),
    Actions.S2_ADVANCE_CAMO:  Utility(2, 4,  ZSUM),
    Actions.S3_ADVANCE:       Utility(1, 8,  ZSUM),
    Actions.S3_ADVANCE_CAMO:  Utility(2, 8,  ZSUM),
    Actions.S4_ADVANCE:       Utility(1, 16, ZSUM),
    Actions.S4_ADVANCE_CAMO:  Utility(2, 16, ZSUM),
}

Advancement_All_Or_Nothing_Rewards = {
    Actions.S0_ADVANCE:       Utility(1, 0,  ZSUM),
    Actions.S0_ADVANCE_CAMO:  Utility(2, 0,  ZSUM),
    Actions.S1_ADVANCE:       Utility(2, 0,  ZSUM),
    Actions.S1_ADVANCE_CAMO:  Utility(3, 0,  ZSUM),
    Actions.S2_ADVANCE:       Utility(3, 0,  ZSUM),
    Actions.S2_ADVANCE_CAMO:  Utility(4, 0,  ZSUM),
    Actions.S3_ADVANCE:       Utility(4, 0,  ZSUM),
    Actions.S3_ADVANCE_CAMO:  Utility(5, 0,  ZSUM),
    Actions.S4_ADVANCE:       Utility(5, 40, ZSUM),
    Actions.S4_ADVANCE_CAMO:  Utility(6, 40, ZSUM),
}

Advancement_Key_Goals_Rewards = {
    Actions.S0_ADVANCE:       Utility(1, 0,  ZSUM),
    Actions.S0_ADVANCE_CAMO:  Utility(2, 0,  ZSUM),
    Actions.S1_ADVANCE:       Utility(2, 8,  ZSUM),
    Actions.S1_ADVANCE_CAMO:  Utility(3, 8,  ZSUM),
    Actions.S2_ADVANCE:       Utility(3, 0,  ZSUM),
    Actions.S2_ADVANCE_CAMO:  Utility(4, 0,  ZSUM),
    Actions.S3_ADVANCE:       Utility(4, 0,  ZSUM),
    Actions.S3_ADVANCE_CAMO:  Utility(5, 0,  ZSUM),
    Actions.S4_ADVANCE:       Utility(5, 30, ZSUM),
    Actions.S4_ADVANCE_CAMO:  Utility(6, 30, ZSUM),
}

Advancement_Front_Loaded_Rewards = {
    Actions.S0_ADVANCE:       Utility(1, 4,  ZSUM),
    Actions.S0_ADVANCE_CAMO:  Utility(2, 4,  ZSUM),
    Actions.S1_ADVANCE:       Utility(2, 20, ZSUM),
    Actions.S1_ADVANCE_CAMO:  Utility(3, 20, ZSUM),
    Actions.S2_ADVANCE:       Utility(3, 0,  ZSUM),
    Actions.S2_ADVANCE_CAMO:  Utility(4, 0,  ZSUM),
    Actions.S3_ADVANCE:       Utility(4, 4,  ZSUM),
    Actions.S3_ADVANCE_CAMO:  Utility(5, 4,  ZSUM),
    Actions.S4_ADVANCE:       Utility(5, 10, ZSUM),
    Actions.S4_ADVANCE_CAMO:  Utility(6, 10, ZSUM),
}

Advancement_Rewards = {
    "flat": Advancement_Flat_Rewards,
    "escalating": Advancement_Escalating_Rewards,
    "all_or_nothing": Advancement_All_Or_Nothing_Rewards,
    "key_goals": Advancement_Key_Goals_Rewards,
    "front_loaded": Advancement_Front_Loaded_Rewards,
}

def get_advancement_utilities(name):
    return Advancement_Rewards[name]

def list_advancement_utilities():
    return list(Advancement_Rewards.keys())

Detection_Flat_Costs = {
    Actions.S0_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S0_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
    Actions.S1_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S1_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
    Actions.S2_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S2_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
    Actions.S3_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S3_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
    Actions.S4_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S4_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
}

Detection_Increasing_Costs = {
    Actions.S0_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S0_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
    Actions.S1_DETECT:        Utility(2, ZSUM, ZSUM),
    Actions.S1_DETECT_STRONG: Utility(3, ZSUM, ZSUM),
    Actions.S2_DETECT:        Utility(3, ZSUM, ZSUM),
    Actions.S2_DETECT_STRONG: Utility(4, ZSUM, ZSUM),
    Actions.S3_DETECT:        Utility(4, ZSUM, ZSUM),
    Actions.S3_DETECT_STRONG: Utility(5, ZSUM, ZSUM),
    Actions.S4_DETECT:        Utility(5, ZSUM, ZSUM),
    Actions.S4_DETECT_STRONG: Utility(6, ZSUM, ZSUM),
}

Detection_Decreasing_Costs = {
    Actions.S0_DETECT:        Utility(5, ZSUM, ZSUM),
    Actions.S0_DETECT_STRONG: Utility(6, ZSUM, ZSUM),
    Actions.S1_DETECT:        Utility(4, ZSUM, ZSUM),
    Actions.S1_DETECT_STRONG: Utility(5, ZSUM, ZSUM),
    Actions.S2_DETECT:        Utility(3, ZSUM, ZSUM),
    Actions.S2_DETECT_STRONG: Utility(4, ZSUM, ZSUM),
    Actions.S3_DETECT:        Utility(2, ZSUM, ZSUM),
    Actions.S3_DETECT_STRONG: Utility(3, ZSUM, ZSUM),
    Actions.S4_DETECT:        Utility(1, ZSUM, ZSUM),
    Actions.S4_DETECT_STRONG: Utility(2, ZSUM, ZSUM),
}

Detection_Costs = {
    "flat": Detection_Flat_Costs,
    "increasing": Detection_Increasing_Costs,
    "decreasing": Detection_Decreasing_Costs,
}

def get_detection_utilities(name):
    return Detection_Costs[name]

def list_detection_utilities():
    return list(Detection_Costs.keys())

Default_Advancement_Rewards = "flat"
Default_Detection_Costs = "flat"


class MinMaxUtil(NamedTuple):
    min: int | None
    max: int | None


class Utilities:
    """
    Mix and match attacker/defender utility structures and provide
    reward/damage calculation methods.
    """

    def __init__(self, advancement_rewards=Default_Advancement_Rewards,
        detection_costs=Default_Detection_Costs):
        # mix and match attacker/defender utilities
        self._utilities = {
            Actions.WAIT:        Utility(0, 0,    0),
            Actions.IN_PROGRESS: Utility(0, 0,    0),
        }
        self._utilities.update(get_advancement_utilities(advancement_rewards))
        self._utilities.update(get_detection_utilities(detection_costs))
        self._min_max_util = MinMaxUtil(None, None)

    @property
    def utilities(self):
        return dict(self._utilities)

    def action_cost(self, action: Actions):
        action = Actions(action)
        assert action in Actions
        return self._utilities[action].cost
    
    def attack_reward(self, action: Actions):
        # reward received for attack action
        action = Actions(action)
        assert action in Actions
        assert action in Attack_Actions
        utils = self._utilities[action]
        return utils.reward + self.action_cost(action)
    
    def attack_damage(self, action: Actions) -> int:
        # damage dealt by attack action
        action = Actions(action)
        assert action in Actions
        assert action in Attack_Actions
        utils = self._utilities[action]
        damage = utils.damage
        if damage is ZSUM:
            damage = self.attack_reward(action)
        if damage is ZSUM:
            raise ValueError(
                f"attack damage {action} {utils} ZSUM loop")
        return damage
    
    def defend_reward(self, action: Actions, attack_action: Actions) -> int:
        # reward received for defend action depending on attack_action
        action = Actions(action)
        assert action in Defend_Actions
        assert attack_action in Attack_Actions
        utils = self._utilities[action]
        attack_utils = self._utilities[attack_action]
        reward = utils.reward
        if reward is ZSUM:
            reward = self.attack_damage(attack_action)
        if reward is ZSUM:
            raise ValueError(
                f"defend reward {action} {utils} {attack_action} {attack_utils}  ZSUM loop")
        return reward + self.action_cost(action)
    
    def defend_damage(self, action: Actions, attack_action: Actions) -> int:
        # damage (typically taking back an attack reward) dealt by defend
        # action depending on attack_action
        action = Actions(action)
        assert action in Defend_Actions
        assert attack_action in Attack_Actions
        utils = self._utilities[action]
        attack_utils = self._utilities[attack_action]
        damage = utils.damage
        if damage is ZSUM:
            damage = utils.reward
            if damage is ZSUM:
                damage = self.attack_damage(attack_action)
        if damage is ZSUM:
            raise ValueError(
                f"defend damage {action} {utils} {attack_action} {attack_utils} ZSUM loop")
        return damage

    def cheapest_action(self, actions):
        min_cost = None
        selected_action = None
        for action in actions:
            action = Actions(action)
            util = self.utilities[action]
            if min_cost is None or util.cost < min_cost:
                # if it's a tie, the first one with that cost is
                # selected
                min_cost = util.cost
                selected_action = action
        return selected_action

    def most_expensive_action(self, actions):
        max_cost = None
        selected_action = None
        for action in actions:
            action = Actions(action)
            util = self.utilities[action]
            if max_cost is None or util.cost > max_cost:
                # if it's a tie, the first one with that cost is
                # selected
                max_cost = util.cost
                selected_action = action
        return selected_action

    def resolve_zsums(self):
        """
        This is just for recording the utilites in the meta-info for
        game runs.
        """
        utilities = {}
        for i, atk_actions in enumerate(Atk_Actions_By_Pos):
            for j, atk_action in enumerate(atk_actions):
                atk_util = self._utilities[atk_action]
                atk_res = [atk_util.cost, atk_util.reward, atk_util.damage]
                if atk_res[-1] == ZSUM:
                    atk_res[-1] = atk_util.reward
                def_action = Def_Actions_By_Pos[i][j]
                def_util = self._utilities[def_action]
                def_res = [def_util.cost, def_util.reward, def_util.damage]
                if def_res[1] == ZSUM:
                    def_res[1] = atk_res[-1]
                if def_res[2] == ZSUM:
                    def_res[2] = def_res[1]
                utilities[atk_action] = tuple(atk_res)
                utilities[def_action] = tuple(def_res)
        return tuple(sorted((x, utilities[x]) for x in utilities))

    def max_utility(self) -> int:
        '''
        Max utility per turn...maybe. Without knowing the total number of
        IN_PROGRESS actions it's not really possible to nail this down
        precisely. But it gets used in the game info/game definition for
        OpenSpiel.
    
        Takes a Utilities instance as an argument.
        '''
        if self._min_max_util.max is not None:
            return self._min_max_util.max
        max_util = 0
        for action in Actions:
            win_cost = self._utilities[action].cost
            max_win = 0
            for skirmish_map in (SkirmishFails, SkirmishWins):
                for lose_action in skirmish_map.get(action, []):
                    if lose_action in Defend_Actions:
                        win_reward = self.attack_reward(action)
                    else:
                        win_reward = self.defend_reward(action, lose_action)
                    win_util = win_cost + win_reward
                    if win_util > max_win:
                        max_win = win_util
                if self._utilities[Actions.IN_PROGRESS].cost:
                    # subtract costs of maximum possible IN_PROGRESS actions
                    if Time_Waits.get(action):
                        max_win -= Time_Waits[action].max \
                            * self._utilities[Actions.IN_PROGRESS].cost
            if max_win > max_util:
                max_util = max_win
        self._min_max_util._replace(max=max_util)
        return max_util
    
    def min_utility(self) -> int:
        '''
        Per turn -- see description for max_utility()
        '''
        if self._min_max_util.min is not None:
            return self._min_max_util.min
        min_util = 0
        for action in Actions:
            fail_cost = -self._utilities[action].cost
            min_fail = 0
            for skirmish_map in (SkirmishFails, SkirmishWins):
                for win_action in skirmish_map.get(action, []):
                    if win_action in Attack_Actions:
                        fail_damage = self.attack_damage(win_action)
                    else:
                        fail_damage = self.defend_damage(win_action, action)
                    fail_util = fail_cost - fail_damage
                    if fail_util < min_fail:
                        min_fail = fail_util
                if self._utilities[Actions.IN_PROGRESS].cost:
                    # subtract costs of maximum possible IN_PROGRESS actions
                    if Time_Waits.get(action):
                        min_fail -= Time_Waits[action].max \
                                * self._utilities[Actions.IN_PROGRESS].cost
            if min_fail < min_util:
                min_util = min_fail
        self._min_max_util._replace(min=min_util)
        return min_util

    def __getitem__(self, x):
        return self._utilities[x]


class TimeWait(NamedTuple):
    '''
    Min/Max, inclusive.
    '''
    min: int
    max: int

    def rand_turns(self) -> int:
        return random.randint(self.min, self.max)

# min/max wait actions preceeding the given action
Time_Waits = {
        Actions.WAIT:             TimeWait(0, 0),
        Actions.IN_PROGRESS:      TimeWait(0, 0),
        Actions.S0_ADVANCE:       TimeWait(1, 4),
        Actions.S0_ADVANCE_CAMO:  TimeWait(2, 5),
        Actions.S1_ADVANCE:       TimeWait(1, 4),
        Actions.S1_ADVANCE_CAMO:  TimeWait(2, 5),
        Actions.S2_ADVANCE:       TimeWait(1, 4),
        Actions.S2_ADVANCE_CAMO:  TimeWait(2, 5),
        Actions.S3_ADVANCE:       TimeWait(1, 4),
        Actions.S3_ADVANCE_CAMO:  TimeWait(2, 5),
        Actions.S4_ADVANCE:       TimeWait(1, 4),
        Actions.S4_ADVANCE_CAMO:  TimeWait(2, 5),
        Actions.S0_DETECT:        TimeWait(1, 4),
        Actions.S0_DETECT_STRONG: TimeWait(2, 5),
        Actions.S1_DETECT:        TimeWait(1, 4),
        Actions.S1_DETECT_STRONG: TimeWait(2, 5),
        Actions.S2_DETECT:        TimeWait(1, 4),
        Actions.S2_DETECT_STRONG: TimeWait(2, 5),
        Actions.S3_DETECT:        TimeWait(1, 4),
        Actions.S3_DETECT_STRONG: TimeWait(2, 5),
        Actions.S4_DETECT:        TimeWait(1, 4),
        Actions.S4_DETECT_STRONG: TimeWait(2, 5),
}

def get_timewait(action):
    return Time_Waits.get(action, TimeWait(0, 0))

# The GeneralFails values are the percentage of failure for an
# unspecified failure -- the operation fails no matter which opposing
# action it might be compared against. If the action is not in the
# GeneralFails map, then DEFAULT_FAIL is used.
#
# Specific failure rates of action vs action are in the SkirmishFails
# map farther below...note that if a particular action has a general
# failure rate (G) as well as a failure rate (V) agains a particular
# action then the probability of G or V failing (but not both) will be:
#
#     P(G^V) = P(G) + P(V) - 2P(P(G) * P(V))

DEFAULT_FAIL = 0

# Chance of an unspecified failure.
GeneralFails = {
    Actions.S0_ADVANCE:       0.15,
    Actions.S0_ADVANCE_CAMO:  0.15,
    Actions.S1_ADVANCE:       0.15,
    Actions.S1_ADVANCE_CAMO:  0.15,
    Actions.S2_ADVANCE:       0.15,
    Actions.S2_ADVANCE_CAMO:  0.15,
    Actions.S3_ADVANCE:       0.15,
    Actions.S3_ADVANCE_CAMO:  0.15,
    Actions.S4_ADVANCE:       0.15,
    Actions.S4_ADVANCE_CAMO:  0.15,
    Actions.S0_DETECT:        0.15,
    Actions.S0_DETECT_STRONG: 0.15,
    Actions.S1_DETECT:        0.15,
    Actions.S1_DETECT_STRONG: 0.15,
    Actions.S2_DETECT:        0.15,
    Actions.S2_DETECT_STRONG: 0.15,
    Actions.S3_DETECT:        0.15,
    Actions.S3_DETECT_STRONG: 0.15,
    Actions.S4_DETECT:        0.15,
    Actions.S4_DETECT_STRONG: 0.15,
}

# Chance of the given action failing while encountering another specific
# action. If an action is not a primary key or secondary key in this map
# then by default it will 100% "fail" against other actions (WAIT,
# IN_PROGRESS). If an action appears as a secondary key, it's failure
# rate will be, by definition, the remaining percentage vs the primary
# key action. These skirmishes are currently only calculated from the
# point of view of the primary keys, i.e. defend actions.
SkirmishFails = {
    Actions.S0_DETECT: {
        Actions.S0_ADVANCE:      0.10,
        Actions.S0_ADVANCE_CAMO: 0.90,
    },
    Actions.S0_DETECT_STRONG: {
        Actions.S0_ADVANCE:      0.10,
        Actions.S0_ADVANCE_CAMO: 0.10,
    },
    Actions.S1_DETECT: {
        Actions.S1_ADVANCE:      0.10,
        Actions.S1_ADVANCE_CAMO: 0.90,
    },
    Actions.S1_DETECT_STRONG: {
        Actions.S1_ADVANCE:      0.10,
        Actions.S1_ADVANCE_CAMO: 0.10,
    },
    Actions.S2_DETECT: {
        Actions.S2_ADVANCE:      0.10,
        Actions.S2_ADVANCE_CAMO: 0.90,
    },
    Actions.S2_DETECT_STRONG: {
        Actions.S2_ADVANCE:      0.10,
        Actions.S2_ADVANCE_CAMO: 0.10,
    },
    Actions.S3_DETECT: {
        Actions.S3_ADVANCE:      0.10,
        Actions.S3_ADVANCE_CAMO: 0.90,
    },
    Actions.S3_DETECT_STRONG: {
        Actions.S3_ADVANCE:      0.10,
        Actions.S3_ADVANCE_CAMO: 0.10,
    },
    Actions.S4_DETECT: {
        Actions.S4_ADVANCE:      0.10,
        Actions.S4_ADVANCE_CAMO: 0.90,
    },
    Actions.S4_DETECT_STRONG: {
        Actions.S4_ADVANCE:      0.10,
        Actions.S4_ADVANCE_CAMO: 0.10,
    },
}

SkirmishWins = {}

def infer_wins():
    # invert SkirmishFails
    SkirmishWins.clear()
    for fail_action in SkirmishFails:
        for win_action, pct_skirm_fail in SkirmishFails[fail_action].items():
            if win_action not in SkirmishWins:
                SkirmishWins[win_action] = {}
            pct_skirm_win = 1.0 - pct_skirm_fail
            SkirmishWins[win_action][fail_action] = pct_skirm_win

infer_wins()

def get_general_pct_fail(action):
    #print(f"GENERAL pct_fail: {GeneralFails.get(action, DEFAULT_FAIL)} {action_to_str(action)}")
    if USE_CHANCE_FAIL:
        return GeneralFails.get(action, DEFAULT_FAIL)
    else:
        return 0

# There is probably a way to use skirmish failure rates to model the
# confidence scores we've been discussing that get returned by
# the oracle in GHOSTS land.

def get_skirmish_pct_fail(action1, action2):
    pct_fail = 1.0
    if action1 in SkirmishFails:
        # note: don't use DEFAULT_FAIL as a fallback here
        pct_fail = SkirmishFails[action1].get(action2, 1.0)
        #pct_fail = SkirmishFails[action1].get(action2, 0.9)
        #print("SKIRMISH in level 1 SkirmishFails")
        #if pct_fail != DEFAULT_FAIL:
        #    print("SKIRMISH in level 2 SkirmishFails")
    #print(f"SKIRMISH pct_fail: {pct_fail} {action_to_str(action1)} {action_to_str(action2)}")
    if USE_CHANCE_FAIL:
        return pct_fail
    else:
        return 1.0 if pct_fail >= 0.5 else 0

def get_skirmish_pct_win(action1, action2):
    pct_win = 0.0
    if action1 in SkirmishWins:
        # note: don't use DEFAULT_FAIL as a fallback here
        pct_win = SkirmishWins[action1].get(action2, 0.0)
    if USE_CHANCE_FAIL:
        return pct_win
    else:
        return 1 if pct_win >= 0.5 else 0

def action_faulty(action):
    # I suspect that using chance nodes in open_spiel might be a viable
    # way for dealing with an action failing to execute...

    if action in NoOp_Actions:
        # don't want to advance on a no-op action
        return None
    completed = True
    pct_fail = get_general_pct_fail(action)
    if pct_fail:
        chance = random.random()
        completed = chance > pct_fail
        if not completed:
            action = action_to_str(action)
            DEBUG and print(f"action GENERAL fail! {action}: {chance:.2f} > {pct_fail:.2f} : {completed}")
    #print("action_completed() end\n")
    return not completed

def action_succeeds(action1, action2):
    # should only be called if the action was not faulty (see above)
    if action1 in NoOp_Actions or action2 in NoOp_Actions:
        # don't want to advance on a no-op action
        return None
    # skirmish fail chance
    successful = True
    if action1 in SkirmishFails:
        pct_fail = get_skirmish_pct_fail(action1, action2)
    else:
        pct_fail = 1 - get_skirmish_pct_win(action1, action2)
    if pct_fail:
        chance = random.random()
        successful = chance > pct_fail
        if not successful and pct_fail < 1:
            # don't report skirmishes that are 100% doomed
            DEBUG and print(f"action SKIRMISH fail! {action_to_str(action1)} vs {action_to_str(action2)}: {chance:.2f} > {pct_fail:.2f} : {successful}")
    return successful

def assert_arena_parameters():
    # Assert the various arena parameters in order to check for data
    # integrity while importing their values from JSON.

    def assert_attack_actions():
        for action in Attack_Actions:
            assert action in Actions, f"not an Action: {action}"

    def assert_defend_actions():
        for action in Defend_Actions:
            assert action in Actions, f"not an Action: {action}"
    
    def assert_noop_actions():
        for action in NoOp_Actions:
            assert action in Actions, f"not an Action: {action}"
    
    def assert_utilities():
        util_structs = list(Advancement_Rewards.values())
        util_structs.extend(list(Detection_Costs.values()))
        for util_struct in Advancement_Rewards.values():
            for action in Actions:
                utils = util_struct[action]
                assert isinstance(utils.cost, int), \
                    f"action {action.name} cost must have explicit int value, not {utils.cost}"
        for util_struct in Detection_Costs.values():
            for action in Actions:
                utils = util_struct[action]
                assert isinstance(utils.cost, int), \
                    f"action {action.name} cost must have explicit int value, not {utils.cost}"
        for util_struct in Advancement_Rewards.values():
            for action in util_struct:
                utils = util_struct[action]
                assert isinstance(utils.reward, int), \
                    f"attack action {action.name} reward must have explicit int value, not {utils.reward}"
                assert isinstance(utils.damage, int) or utils.damage == ZSUM, \
                    f"attack action {action.name} damage must be int or ZSUM, not {utils.reward}"
        for util_struct in Detection_Costs.values():
            for action in util_struct:
                utils = util_struct[action]
                assert isinstance(utils.reward, int) or utils.reward == ZSUM, \
                    f"defend action {action.name} reward must be int or ZSUM, not {utils.reward}"
                assert isinstance(utils.damage, int) or utils.damage == ZSUM, \
                    f"defend action {action.name} damage must be int or ZSUM, not {utils.reward}"
    
    def assert_timewaits():
        for action, tw in Time_Waits.items():
            assert action in Actions, f"not an Action: {action}"
            assert isinstance(tw, TimeWait)
    
    def assert_general_fails():
        for action, chance in GeneralFails.items():
            assert action in Actions, f"not an Action: {action}"
            assert (chance >= 0 and chance <= 1)
    
    def assert_skirmish_fails():
        fail_pairs = set()
        reverse_pairs = set()
        for action, oppose_actions in SkirmishFails.items():
            assert action in Actions, f"not an Action: {action}"
            for act in oppose_actions:
                assert act in Actions, f"not an Action: {action}"
                fail_pair = (action, act)
                assert fail_pair not in fail_pairs, f"multiple instances defined for SkirmishFail action pair: {fail_pair}"
                fail_pairs.add(fail_pair)
                reverse_pairs.add(tuple(reversed(fail_pair)))
        # make sure there are no bidirectional fail pairings
        bidirects = fail_pairs.intersection(reverse_pairs)
        assert not bidirects, f"{len(bidirects)} bidirectional SkirmishFail action pairs detected: {list(sorted(bidirects))}"
    
    # assert values in this order
    assert_attack_actions()
    assert_defend_actions()
    assert_noop_actions()
    assert_utilities()
    assert_timewaits()
    assert_general_fails()
    assert_skirmish_fails()
