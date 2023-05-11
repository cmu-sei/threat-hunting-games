import random

from open_spiel.python.policy import Policy

class IntervalActions:

    def __init__(self, action_intervals, beat_seeds=None):
        if not beat_seeds:
            # init timers to max interval per action (lowest intervals
            # go first)
            beat_seeds = {}
        self._action_intervals = dict(action_intervals)
        self._beats = []
        for action, interval in self._action_intervals.items():
            self._beats.append([beat_seeds.get(action, interval), action])
        self._beats.sort()

    def take_action(self, selected_actions=None):
        # select the most stale action -- if more than one action has
        # been languishing for the same amount of time, pick a random
        # one of them
        if selected_actions:
            beats = []
            for beat in self._beats:
                if beat[1] in selected_actions:
                    beats.append(beat)
        else:
            beats = self._beats
        for beat in beats:
            beat[0] -= 1
        action = None
        lowest_count = beats[0][0]
        if lowest_count <= 0:
            beat_choices = []
            for beat in beats:
                if beat[0] == lowest_count:
                    beat_choices.append(beat)
                else:
                    break
            assert beat_choices, "no actions"
            beat = random.choice(beat_choices)
            # reset the interval timer for this action
            action = beat[1]
            beat[0] = self._action_intervals[action]
            self._beats.sort()
        return action

    def action_intervals(self):
        return self._action_intervals

    def action_beats(self):
        return self._beats


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
    """

    def __init__(self, game, player_intervals=None):
        """Initializes a uniform random policy for all players in the game."""
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        # dict of Action -> defined interval per player
        self._intervals = {}
        if player_intervals:
            for player, (intervals, beat_seeds) in player_intervals.items():
                self._intervals[player] = \
                        IntervalActions(intervals, beat_seeds=beat_seeds)

    def action_probabilities(self, state, player_id=None):
        legal_actions = (
            state.legal_actions()
            if player_id is None else state.legal_actions(player_id))
        if not legal_actions:
            return { 0: 1.0 }
        if len(legal_actions) == 1:
            return { legal_actions[0]: 1.0 }
        intervals = self._intervals.get(player_id)
        if intervals:
            action = intervals.take_action(legal_actions)
        else:
            action = random.choice(legal_actions)
        if not action:
            return { 0: 1.0 }
        else:
            return { action: 1.0 }
