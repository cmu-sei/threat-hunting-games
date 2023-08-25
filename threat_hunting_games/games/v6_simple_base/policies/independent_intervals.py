import random

import pyspiel
from open_spiel.python.policy import Policy

from . import arena as arena_mod

Default_Action_Intervals = {}
for i, action in enumerate(arena_mod.Defend_Actions):
    if action == arena_mod.Actions.WAIT:
        continue
    else:
        Default_Action_Intervals[action] = i
Default_Interval_Clock_Seed = 0


class ActionPickerIntervals:
    """
    From original description of independent intervals.
    """

    def __init__(self, all_actions, action_intervals=Default_Action_Intervals,
            clock_seed=Default_Interval_Clock_Seed, **kwargs):
        self._beats = {}
        for action, interval in action_intervals.items():
            if not interval:
                continue
            self._beats[int(action)] = interval
        self._clock = clock_seed if clock_seed else 0
        self._action_queue = []

    @classmethod
    def defaults(cls):
        defs = {
            "action_intervals": dict(Default_Action_Intervals),
            "clock_seed": Default_Interval_Clock_Seed,
        }
        return defs

    def take_action(self, selected_actions=None):
        if not selected_actions:
            selected_actions = self._beats.keys()
        selected_actions = [int(x) for x in selected_actions]
        action = None
        for action in selected_actions:
            if action not in self._beats:
                continue
            if not self._clock % self._beats[action]:
                # should we put multiple actions of the same type in
                # primed actions?
                if action not in self._action_queue:
                    self._action_queue.append(action)
        if self._action_queue:
            # could do random.choice(primed_actions)...but we do
            # FIFO for now
            #
            # also, from the writeup:
            #
            #   Useful constraints will be ensuring all detection types
            #   can trigger without always being over-ridden by a
            #   detection of higher priority, since such cases
            #   degenerate into assignment of zero period (never check)
            #   for the lower-priority detections.
            #
            #   Alternatively, a tiebreaker could be decided based on a
            #   memory as described in aggregate history randomized,
            #   where the decision among multiple actions that are
            #   scheduled to co-occur is made based on which of the
            #   targeted detection actions has been taken least
            #   recently.
            action, self._action_queue[:] = \
                    self._action_queue[0], self._action_queue[1:]
        self._clock += 1
        return action

    def action_intervals(self):
        return dict(self._beats)

    def __str__(self):
        return f"clock: {self._clock} beats: {self._beats}"


class ActionPickerLeastExpensive:
    """
    Example strategy 1: Spam only the cheapest (or earliest in the kill
    chain) detection action at every available time unit.
    """

    def __init__(self, all_actions, arena=None, **kwargs):
        self._arena = arena if arena else arena_mod.Arena()
        self._all_actions = tuple(all_actions)

    @classmethod
    def defaults(cls):
        return {}

    def take_action(self, selected_actions=None):
        if not selected_actions:
            selected_actions = self._all_actions
        action = None
        action = self._arena.utilities.least_expensive_action(selected_actions)
        return action


class ActionPickerLeastRecentLeastExpensive:
    """
    Example strategy 2: Spam every detection action at each time unit.
    Since we restrict to only detect action per time unit, first
    tiebreaker goes to least-recently-executed action. Ties will often
    remain, so second tiebreaker goes to the detect action associated
    with the earliest attacker action. Third tiebreaker goes to less
    expensive detect
    """

    def __init__(self, all_actions, arena=None, **kwargs):
        self._arena = arena if arena else arena_mod.Arena()
        self._all_actions = tuple(all_actions)
        self._beats = {}
        for action in self._all_actions:
            action = self._arena.actions(action)
            self._beats[action] = 0

    @classmethod
    def defaults(cls):
        return {}

    def take_action(self, selected_actions=None):
        if not selected_actions:
            selected_actions = self._beats.keys()
        selected_actions = [int(x) for x in selected_actions]
        by_beats = {}
        for action in selected_actions:
            beat = self._beats[action]
            if beat not in by_beats:
                by_beats[beat] = []
            by_beats[beat].append(action)
        least_recent_actions = by_beats[max(by_beats)]
        action = None
        if len(least_recent_actions) == 1:
            # least recent
            action = least_recent_actions[0]
        if not action:
            # second tie breaker earliest attack chain correlated
            # hmm
            pass
        if not action:
            action = \
                self._arena.utilities.least_expensive_action(
                        least_recent_actions)
        for b_action in self._beats:
            if b_action == action:
                self._beats[b_action] = 0
            else:
                self._beats[b_action] += 1
        return action


class ActionPickerLeastRecentMostExpensive:
    """
    Example strategy 3: Spam every detection action at each time unit.
    Since we restrict to only detect action per time unit, first
    tiebreaker goes to least-recently-executed action. Ties will often
    remain, so second tiebreaker goes to the detect action associated
    with the earliest attacker action. Third tiebreaker goes to more
    expensive detect.
    """

    def __init__(self, all_actions, arena=None, **kwargs):
        self._arena = arena if arena else arena_mod.Arena()
        self._all_actions = tuple(int(x) for x in all_actions)
        self._beats = {}
        for action in self._all_actions:
            self._beats[action] = 0

    @classmethod
    def defaults(cls):
        return {}

    def take_action(self, selected_actions=None):
        if not selected_actions:
            selected_actions = self._beats.keys()
        selected_actions = [int(x) for x in selected_actions]
        by_beats = {}
        for action in selected_actions:
            beat = self._beats[action]
            if beat not in by_beats:
                by_beats[beat] = []
            by_beats[beat].append(action)
        least_recent_actions = by_beats[max(by_beats)]
        action = None
        if len(least_recent_actions) == 1:
            # least recent
            action = least_recent_actions[0]
        if not action:
            # second tie breaker earliest attack chain correlated
            # hmm
            pass
        if not action:
            action = self._arena.utilities.most_expensive_action(
                    least_recent_actions)
        for b_action in self._beats:
            if action == b_action:
                self._beats[b_action] = 0
            else:
                self._beats[b_action] += 1
        return action


class ActionPickerRankedIntervals:
    """
    Example strategy 4: Order detection actions first by steps in the
    kill chain, then by cost of detection, producing an absolute
    ordering. Set the interval for each action equal to its position in
    the order. Break ties by selecting the action of latest position in
    the order.
    """

    def __init__(self, all_actions, action_chain=None, arena=None,
            clock_seed=Default_Interval_Clock_Seed, **kwargs):
        self._arena = arena if arena else arena_mod.Arena()
        self._ordered_actions = []
        for stage_actions in action_chain:
                for action in [x[1] \
                    for x in (sorted((self._arena.utilities.utilities[y].cost, y)) \
                        for y in stage_actions)]:
                            self._ordered_actions.append(action)
        self._beats = {}
        for i, action in enumerate(self._ordered_actions):
            self._beats[action] = i
        self._clock = clock_seed if clock_seed else 1
        self._action_queue = []

    @classmethod
    def defaults(cls):
        defs = {
            "clock_seed": Default_Interval_Clock_Seed,
        }
        return defs

    def take_action(self, selected_actions=None):
        if not selected_actions:
            selected_actions = self._beats.keys()
        selected_actions = [int(x) for x in selected_actions]
        action_queue = self._action_queue
        self._action_queue = []
        for action in action_queue:
            if action in selected_actions:
                self._action_queue.append(action)
        new_actions = []
        for action in selected_actions:
            if not self._beats[action] % self._clock:
                new_actions.append(action)
        # break tie by picking farthest in chain, hence reversing
        for action in reversed(new_actions):
            if action not in self._action_queue:
                self._action_queue.append(action)
        self._clock += 1
        action = None
        if self._action_queue:
            action = self._action_queue.pop(0)
        return action


Action_Pickers = {
    "intervals": ActionPickerIntervals,
    "cheapest": ActionPickerLeastExpensive,
    "least_recent_cheapest": ActionPickerLeastRecentLeastExpensive,
    "least_recent_most_expensive": ActionPickerLeastRecentMostExpensive,
    "ranked_intervals": ActionPickerRankedIntervals,
}

Default_Action_Picker = "intervals"

def get_action_picker_class(action_name):
    return Action_Pickers[action_name]

def list_action_pickers():
    return list(Action_Pickers.keys())


class IndependentIntervalsPolicy(Policy):
    """
    `Independent Intervals` strategies for the defender are policies
    that set a deterministic interval for the number of time steps
    between queries for a specific bit (e.g., bit 5 will be queried
    every 10 time steps). The intervals are independent because they are
    determined separately for each bit. This type of policy can be
    represented by a vector of integers of length ∥Ω∥, where each
    values is between 0 and t^max. Such policies are cyclic and repeat
    after a fixed number of time steps. (Note: there is also an issue
    with defining how to start the policy; one way is to randomly select
    the starting point).

    `player_intervals` should be a dict with players as keys and a pair
    of defined action intervals (a dict of actions to intervals) and
    (can be None) initial values for the action timers (beats).

    ...

    For simulating in the game testing platform, we will want to encode
    a strategy in this type by imposing an order on all the detection
    actions available to the defender, then assigning to each detection
    action a period. At each time interval, execute the highest-priority
    detection action with a period that divides the time index.

    Useful constraints will be ensuring all detection types can trigger
    without always being over-ridden by a detection of higher priority,
    since such cases degenerate into assignment of zero period (never
    check) for the lower-priority detections.

    Alternatively, a tiebreaker could be decided based on a memory as
    described in aggregate history randomized, where the decision
    among multiple actions that are scheduled to co-occur is made
    based on which of the targeted detection actions has been taken
    least recently.

    sisk note: currently not triggering based on div of time exactly --
    this was under the assumption that WAIT would also be in legal
    actions... currently just picking "most stale" first where the
    countdown resets to the seed interval after the action is selected.
    Note that negative counts can possibly accumulate but those values
    still indicate the magnitude of staleness for that action.
    """

    def __init__(self, game, action_picker=None):
        if action_picker is None:
            action_picker = Default_Action_Picker
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        if not callable(action_picker):
            self._action_picker_name = action_picker
            action_picker = get_action_picker_class(action_picker)
        else:
            self._action_picker_name = action_picker.__name__
        self._action_picker_class = action_picker
        self._action_pickers = {}

    @classmethod
    def default_action_picker(cls):
        return Default_Action_Picker

    @classmethod
    def defaults(cls):
        defs = {}
        for ap in list_action_pickers():
            apc = get_action_picker_class(ap)
            defs[ap] = apc.defaults()
        return defs

    @classmethod
    def get_action_picker_class(cls, ap_name):
        return get_action_picker_class(ap_name)

    @classmethod
    def list_action_pickers(cls):
        return list_action_pickers()

    def action_probabilities(self, state, player_id=None):
        """
        Primary interface to a Policy. Returns a dict of actions with
        their associated probabilities. In this particular case this
        will be a single action with probability of 1.0.
        """
        if player_id:
            player_id = int(player_id)
        legal_actions = state.legal_actions() if player_id is None \
                else state.legal_actions(player_id)
        if not legal_actions:
            return { pyspiel.ILLEGAL_ACTION: 1.0 }
        if len(legal_actions) == 1 \
                and legal_actions[0] == state.arena.actions.IN_PROGRESS:
            return { legal_actions[0]: 1.0 }
        if player_id not in self._action_pickers:
            kwargs = {}
            kwargs["arena"] = state.arena
            kwargs["action_chain"] = \
                    state.arena.player_actions_by_pos[player_id]
            all_actions = state.arena.player_actions[player_id]
            self._action_pickers[player_id] = \
                self._action_picker_class(all_actions, **kwargs)
        action = self._action_pickers[player_id].take_action(legal_actions)
        if action is None:
            action = random.choice(legal_actions)
            print("No action picked, random choice:", state.arena.a2s(action),
                    self._action_picker_name)
        return { int(action): 1.0 }
