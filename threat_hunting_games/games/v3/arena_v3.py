# These are game elements shared across the various V2 game versions, in
# particular the actions and their assosciated calculation of
# utilities. There is also a function for converting this information
# into matrix form.

from typing import NamedTuple, Mapping, Any, List
from dataclasses import dataclass
from enum import IntEnum, auto
import random

# I ran into difficulties trying to put attack/defend actions in their
# own IntEnums (0, 1, 2 value for each). Pyspiel will blow up if the
# action values are not indeed distinct.

class Players(IntEnum):
    # the values of these Player enums are used as 0-based indices later
    # in GameState._assert_action(s) -- also hence IntEnum
    ATTACKER = 0
    DEFENDER = 1

class Actions(IntEnum):
    # both players; auto() starts at 1
    WAIT                = auto()
    IN_PROGRESS         = auto()
    # attacker
    S0_VERIFY_PRIV      = auto()
    S0_VERIFY_PRIV_CAMO = auto()
    S1_WRITE_EXE        = auto()
    S1_WRITE_EXE_CAMO   = auto()
    S2_ENCRYPT          = auto()
    S2_ENCRYPT_CAMO     = auto()
    # defender
    PSGREP              = auto()
    PSGREP_STRONG       = auto()
    SMB_LOGS            = auto()
    SMB_LOGS_STRONG     = auto()
    FF_SEARCH           = auto()
    FF_SEARCH_STRONG    = auto()

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
    Actions.IN_PROGRESS,
]))

Atk_Actions_By_Pos = (
    (
      # pos 0
      Actions.WAIT,
      Actions.S0_VERIFY_PRIV,
      Actions.S0_VERIFY_PRIV_CAMO,
    ),
    (
      # pos 1
      Actions.WAIT,
      Actions.S1_WRITE_EXE,
      Actions.S1_WRITE_EXE_CAMO,
    ),
    (
      # pos 2
      Actions.WAIT,
      Actions.S2_ENCRYPT,
      Actions.S2_ENCRYPT_CAMO,
    ),
)

def player_to_str(player: Actions) -> str:
    # call the enum in case player is an int
    if player is not None:
        return Players(player).name.title()
    else:
        return "None"

def action_to_str(action: Actions) -> str:
    # call the enum in case action is an int
    if action is not None:
        return Actions(action).name.title()
    else:
        return "None"


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
# See the fail/win maps below for which actions are effective
# against other actions. See the attack_reward(),
# attack_damage(), defend_reward(), and defend_damage() functions below
# to see the logic implemented .

class ZSUM():
    pass

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
    Actions.SMB_LOGS_STRONG:     Utility(3, ZSUM, ZSUM),
    Actions.FF_SEARCH:           Utility(3, ZSUM, ZSUM),
    Actions.FF_SEARCH_STRONG:    Utility(4, ZSUM, ZSUM),
}


class TimeWait(NamedTuple):
    min: int
    max: int

    def rand_turns(self) -> int:
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

# Chance of the given action failing while encountering another specific
# action. If an action is not a primary key or secondary key in this map
# then by default it will 100% "fail" against other actions (WAIT,
# IN_PROGRESS). If an action appears as a secondary key, it's failure
# rate will be, by definition, the remaining percentage vs the primary
# key action. These skirmishes are currently only calculated from the
# point of view of the primary keys, i.e. defend actions.
SkirmishFails = {
    Actions.PSGREP: {
        Actions.S0_VERIFY_PRIV: 0.10,
        Actions.S0_VERIFY_PRIV_CAMO: 0.90,
    },
    Actions.PSGREP_STRONG: {
        Actions.S0_VERIFY_PRIV: 0.05,
        Actions.S0_VERIFY_PRIV_CAMO: 0.10,
    },
    Actions.SMB_LOGS: {
        Actions.S1_WRITE_EXE: 0.10,
        Actions.S1_WRITE_EXE_CAMO: 0.90,
    },
    Actions.SMB_LOGS_STRONG: {
        Actions.S1_WRITE_EXE: 0.05,
        Actions.S1_WRITE_EXE_CAMO: 0.10,
    },
    Actions.FF_SEARCH: {
        Actions.S2_ENCRYPT: 0.10,
        Actions.S2_ENCRYPT_CAMO: 0.90,
    },
    Actions.FF_SEARCH_STRONG: {
        Actions.S2_ENCRYPT: 0.05,
        Actions.S2_ENCRYPT_CAMO: 0.10,
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
    return GeneralFails.get(action, DEFAULT_FAIL)

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
    return pct_fail

def get_skirmish_pct_win(action1, action2):
    pct_win = 0.0
    if action1 in SkirmishWins:
        # note: don't use DEFAULT_FAIL as a fallback here
        pct_win = SkirmishWins[action1].get(action2, 0.0)
    return pct_win

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
            print(f"action GENERAL fail! {action}: {chance:.2f} > {pct_fail:.2f} : {completed}")
    #print("action_completed() end\n")
    return not completed

def action_defeated(action1, action2):

    if action1 in NoOp_Actions:
        # don't want to advance on a no-op action
        return None
    # skirmish fail chance
    if action1 in SkirmishFails:
        pct_fail = get_skirmish_pct_fail(action1, action2)
    else:
        pct_fail = 1 - get_skirmish_pct_win(action1, action2)
    successful = True
    if pct_fail:
        chance = random.random()
        successful = chance > pct_fail
        if not successful:
            print(f"action SKIRMISH fail! {action_to_str(action1)} vs {action_to_str(action2)}: {chance:.2f} > {pct_fail:.2f} : {successful}")
    return not successful

def attack_reward(action: Actions):
    # reward received for attack action
    assert action in Attack_Actions
    utils = Utilities[action]
    return utils.reward

def attack_damage(action: Actions) -> int:
    # damage dealt by attack action
    assert action in Attack_Actions
    utils = Utilities[action]
    damage = utils.damage
    if damage is ZSUM:
        damage = attack_reward(action)
    if damage is ZSUM:
        raise ValueError(
            f"attack damage {action} {utils} ZSUM loop")
    return damage

def defend_reward(action: Actions, attack_action: Actions) -> int:
    # reward received for defend action depending on attack_action
    assert action in Defend_Actions
    assert attack_action in Attack_Actions
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
    # damage (typically taking back an attack reward) dealt by defend
    # action depending on attack_action
    assert action in Defend_Actions
    assert attack_action in Attack_Actions
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
        win_cost = Utilities[action].cost
        max_win = 0
        for skirmish_map in (SkirmishFails, SkirmishWins):
            for lose_action in skirmish_map.get(action, []):
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
        fail_cost = -Utilities[action].cost
        min_fail = 0
        for skirmish_map in (SkirmishFails, SkirmishWins):
            for win_action in skirmish_map.get(action, []):
                if win_action in Attack_Actions:
                    fail_damage = attack_damage(win_action)
                else:
                    fail_damage = defend_damage(win_action, action)
                fail_util = fail_cost - fail_damage
                if fail_util < min_fail:
                    min_fail = fail_util
            if Utilities[Actions.IN_PROGRESS].cost:
                # subtract costs of maximum possible IN_PROGRESS actions
                if TimeWaits.get(action):
                    min_fail -= TimeWaits[action].max \
                            * Utilities[Actions.IN_PROGRESS].cost
        if min_fail < min_util:
            min_util = min_fail
    _min_max_util._replace(min=min_util)
    return min_util

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
        for action in Actions:
            utils = Utilities[action]
            assert isinstance(utils.cost, int), \
                f"action {action.name} cost must have explicit int value, not {utils.cost}"
        for action in Attack_Actions:
            utils = Utilities[action]
            assert isinstance(utils.reward, int), \
                f"attack action {action.name} reward must have explicit int value, not {utils.reward}"
            assert isinstance(utils.damage, int) or utils.damage == ZSUM, \
                f"attack action {action.name} damage must be int or ZSUM, not {utils.reward}"
        for action in Defend_Actions:
            utils = Utilities[action]
            assert isinstance(utils.reward, int) or utils.reward == ZSUM, \
                f"defend action {action.name} reward must be int or ZSUM, not {utils.reward}"
            assert isinstance(utils.damage, int) or utils.damage == ZSUM, \
                f"defend action {action.name} damage must be int or ZSUM, not {utils.reward}"
    
    def assert_timewaits():
        for action, tw in TimeWaits.items():
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
