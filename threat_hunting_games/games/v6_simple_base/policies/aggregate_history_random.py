import random
import numpy as np

import pyspiel
from open_spiel.python.policy import Policy

from . import arena
from .util import normalize_action_probs


def uniform_seeds(actions):
    pct = 1 / len(actions)
    probs = {}
    for action in actions:
        probs[action] = pct
    return probs


class ActionPickerIncrement:
    """
    Original description of strategy.

    Keeps track of the running probabilities for available actions. When
    an action is selected, the remaining actions are incremented by the
    pct_per_interval and the selected action is restored to its seed
    probability.
    """

    pct_per_interval = 0.10

    def __init__(self, all_actions, pct_per_interval=None, **kwargs):
        if pct_per_interval is not None:
            # override class default
            self.pct_per_interval = abs(pct_per_interval)
        assert pct_per_interval > 0, "only positive non-zero values"
        assert pct_per_interval <= 1.0, "only values below 1.0"
        all_actions = [int(x) for x in all_actions]
        pct = 1 / len(all_actions)
        self._seed_probs = {}
        for action in all_actions:
            self._seed_probs[action] = pct
        self._running_probs = dict(self._seed_probs)

    def take_action(self, selected_actions=None):
        """
        Select an action and adjust the probabilities for all actions.
        """

        if selected_actions:
            probs = {}
            for action in selected_actions:
                action = int(action)
                probs[action] = self._running_probs[action]
            probs = normalize_action_probs(probs)
        else:
            probs = self._running_probs
        action = np.random.choice(list(probs.keys()), p=list(probs.values()))
        # this increments all other actions, even those not in
        # selected_actions...
        for p_action in self._running_probs:
            self._running_probs[p_action] += self.pct_per_interval
        # reset selected action to seed pct -- which will be scaled
        # accordingly with the accumplated percentages of the
        # other actions
        self._running_probs[action] = self._seed_probs[action]
        self._running_probs = normalize_action_probs(self._running_probs)
        return action

    @classmethod
    def defaults(cls):
        return { "pct_per_interval": cls.pct_per_interval }


class ActionPickerDecrement:
    """
    Example strategy #8 from the writeup.

    Keeps track of the running probabilities for available actions. When
    an action is selected, scale its probability by the pct_per_interval
    and distribute the remaining probability uniformly across the
    remaining actions.
    """

    pct_per_interval = 0.8

    def __init__(self, all_actions, pct_per_interval=None, **kwargs):
        if pct_per_interval is not None:
            # override class default
            self.pct_per_interval = abs(pct_per_interval)
        assert pct_per_interval > 0, "only positive non-zero values"
        assert pct_per_interval <= 1.0, "only values below 1.0"
        all_actions = [int(x) for x in all_actions]
        pct = 1 / len(all_actions)
        self._seed_probs = {}
        for action in all_actions:
            self._seed_probs[action] = pct
        self._running_probs = dict(self._seed_probs)

    def take_action(self, selected_actions=None):
        """
        Selects an action and adjusts the probabilities for all action.
        """

        if selected_actions:
            # if selected actions are a subset of all actions
            selected_actions = [int(x) for x in selected_actions]
            probs = {}
            for action in selected_actions:
                probs[action] = self._running_probs[action]
            probs = normalize_action_probs(probs)
        else:
            probs = self._running_probs
        action = None
        action = np.random.choice(list(probs.keys()), p=list(probs.values()))
        old_prob = probs[action]
        new_prob = old_prob * self.pct_per_interval
        pct_slack = old_prob - new_prob
        # this distributes the slack to all other actions, even those
        # not in selected_actions...
        incr = pct_slack / (len(self._running_probs) - 1)
        for r_action in self._running_probs:
            if r_action == action:
                self._running_probs[r_action] = new_prob
            else:
                self._running_probs[r_action] += incr
        self._running_probs = normalize_action_probs(self._running_probs)
        return action

    @classmethod
    def defaults(cls):
        return { "pct_per_interval": cls.pct_per_interval }


Action_Pickers = {
    "increment": ActionPickerIncrement,
    "decrement": ActionPickerDecrement,
}

Default_Action_Picker = "decrement"

def get_action_picker_class(action_picker_name):
    return Action_Pickers[action_picker_name]

def list_action_pickers():
    return list(Action_Pickers.keys())


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

    def __init__(self, game, action_picker=None):
        if action_picker is None:
            action_picker = Default_Action_Picker
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        if not callable(action_picker):
            action_picker = get_action_picker_class(action_picker)
        self._action_picker_class = action_picker
        self._action_pickers = {}

    @classmethod
    def defaults(cls):
        def_ap_class = get_action_picker_class(Default_Action_Picker)
        return { Default_Action_Picker: dict(def_ap_class.defaults()) }

    @classmethod
    def get_action_picker_class(cls, ap_name):
        return get_action_picker_class(ap_name)

    @classmethod
    def list_action_pickers(cls):
        return list_action_pickers()

    def action_probabilities(self, state, player_id=None):
        """
        This is the primary interface to Policies; return a dict of
        actions and their assosciated probabilities. In this particular
        case this will be a single action with a probability of 1.0.
        """
        if player_id is not None:
            player_id = arena.Players(player_id)
        legal_actions = (
            state.legal_actions() if player_id is None \
                    else state.legal_actions(player_id))
        if not legal_actions:
            return { pyspiel.ILLEGAL_ACTION, 1.0 }
        if len(legal_actions) == 1 \
                and legal_actions[0] == arena.Actions.IN_PROGRESS:
            return { legal_actions[0]: 1.0 }
        if player_id not in self._action_pickers:
            uniform_pct = 1 / len(arena.Player_Actions[player_id])
            #seed_probs = {}
            #for action in arena.Player_Actions[player_id]:
            #        seed_probs[action] = uniform_pct
            self._action_pickers[player_id] = \
                self._action_picker_class(arena.Player_Actions[player_id])
        action = self._action_pickers[player_id].take_action(legal_actions)
        if not action:
            action = arena.Actions.WAIT
        return { int(action): 1.0 }
