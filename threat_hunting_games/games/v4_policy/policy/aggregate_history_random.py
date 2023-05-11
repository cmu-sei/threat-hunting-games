import random

from open_spiel.python.policy import Policy


class ActionPicker:

    pct_per_interval = 0.10

    def __init__(self, action_seed_probs, pct_per_interval=None):
        if pct_per_interval is not None:
            # override class default
            self.pct_per_interval = pct_per_interval
        if not isinstance(action_seed_probs, dict):
            # if just a list of actions, uniform initial distribution
            probs = {}
            pct = 1 / len(action_seed_probs)
            for action in action_seed_probs:
                probs[action] = pct
            action_seed_probs = probs
        self._seed_probs = dict(action_seed_probs)
        self._running_probs = dict(self._seed_probs)

    def take_action(self, selected_actions=None):
        # select an action and increment the percentages of the rest of
        # the actions
        if selected_actions:
            probs = {}
            for action in selected_actions:
                probs[action] = self._running_probs[action]
        else:
            probs = self._running_probs
        psum = sum(probs.values) or (len(probs) / 100)
        for action in probs:
            probs[action] *= (1 / psum)
        selected_action = \
                random.choice(list(probs.keys()), p=list(probs.values()))
        # this increments all actions, even those not in
        # selected_actions...
        for action in self._running_probs:
            self._running_probs[action] += self.pct_per_interval
        # reset selected action to seed pct -- which will be scaled
        # accordingly with the accumplated percentages of the
        # other actions
        self._running_probs[selected_action] = \
                self._seed_probs[selected_action]
        psum = sum(self._running_probs.values())
        for action in self._running_probs::
            self._running_probs *= (1 / psum)
        return action


class AggregateHistoryPolicy(Policy):
    """
    `Aggregate History Randomized` strategies use a simplified
    representation of the query history to allow for more complex
    randomized policies. For each query variable the policy maintains a
    set of history variables, and the probability of performing a query
    in each time step is conditional on this limited set of variables.
    This generalizes the simple randomized policy above to allow for
    richer (but still realistic) strategies such as doing a query with
    higher probability when it has been longer since a particular
    variable has been queried. The complexity of the policy is bounded
    by the number of history variables tracked, rather than the full
    history. A natural version of this strategy essentially combines the
    interval and randomized strategies by tracking the number of turns
    since each query has been executed, and specifying the probability
    of doing a query based on this interval. Again, the simple form of
    these strategies treats each query independently, though more
    complex strategies could generalize this to allow for history
    variables that depend on larger subsets of the queries.

    ...

    For simulating in the game testing platform, we will want to start
    with a tracker of how many time units have elapsed since each detect
    action was taken. We will need a seed list of probabilities for each
    detection and a function that updates the probability of taking an
    action each time unit. An 5 initial strategy is to reset an action
    to its seed probability after a turn in which that action is taken,
    and to increase its probability by ten percent after a turn in which
    it is not taken. (A multiplicative function is preferable here, to
    easily ensure no probability creeps toward 1 too quickly).

    Seed probabilities and values for the update function will likely
    be informed by experimental outcomes with strategies of the other
    two types.
    """

    def __init__(self, game, player_seed_probs):
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        self._action_pickers = {}
        for player in player_seed_probs:
            self._action_pickers[player] = \
                    ActionPicker(player_seed_probs[player])

    def action_probabilities(self, state, player_id=None):
        legal_actions = (
            state.legal_actions()
            if player_id is None else state.legal_actions(player_id))
        if not legal_actions:
            return { 0: 1.0 }
        if len(legal_actions) == 1:
            return { legal_actions[0]: 1.0 }
        if player_id not in self._action_pickers:
            action = random.choice(legal_actions)
        else:
            action = self._action_pickers[player_id].take_action(legal_actions)
        return { action: 1.0 }
