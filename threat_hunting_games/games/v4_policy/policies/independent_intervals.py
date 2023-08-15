import random

import pyspiel
from open_spiel.python.policy import Policy

#import arena_zsum_v4 as arena
from . import arena_zsum_v4 as arena

Default_Action_Intervals = {}
for i, action in enumerate(arena.Defend_Actions):
    if action == arena.Actions.WAIT:
        continue
    else:
        Default_Action_Intervals[action] = i
Default_Interval_Clock_Seed = 0

class IntervalActions:

    def __init__(self, action_intervals=Default_Action_Intervals,
            clock_seed=Default_Interval_Clock_Seed):
        self._beats = {}
        for action, interval in dict(action_intervals).items():
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

    def __init__(self, game, player_intervals, clock_seed=None):
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        self._intervals = {}
        for player, intervals in player_intervals.items():
            self._intervals[int(player)] = \
                IntervalActions(intervals, clock_seed=clock_seed)
        assert not set(self._intervals).difference(all_players), \
                "unknown players in intervals"

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
        intervals = self._intervals.get(player_id)
        if intervals:
            action = intervals.take_action(legal_actions)
        else:
            print("intervals using random choice legal actions")
            action = random.choice(legal_actions)
        if not action:
            return { pyspiel.ILLEGAL_ACTION: 1.0 }
        else:
            return { action: 1.0 }
