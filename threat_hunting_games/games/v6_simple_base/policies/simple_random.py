import math, random
import numpy as np
from dataclasses import dataclass

import pyspiel
from open_spiel.python.policy import Policy

from . import arena as arena_mod
from .util import normalize_action_probs


def uniform_probs(actions):
    psum = len(arena.Defend_Actions)
    probs = {}
    for action in actions:
            probs[action] = 1 / psum
    return probs

def random_probs(actions):
    mid = int(100 / len(actions))
    probs = {}
    for action in actions:
        probs[action] = random.randint(1, (mid + int(mid / 3))) / 100
    probs = normalize_action_probs(probs)
    return probs


class ActionPickerSequentialThenCost:
    """
    Example strategy 5: Order detection actions first by steps in the
    kill chain, then by cost of detection, producing an absolute
    ordering. Assign probability .5 to each detection action, then
    iterate through the actions following the assigned order, sampling
    with probability .5 until an action is picked or the list is
    exhausted.
    """

    _pct = 0.5

    def __init__(self, all_actions, action_chain=None,
            arena=None, pct=None, **kwargs):
        assert action_chain, "Parameter 'action_chain' should be arena.Def_Actions_By_Pos or arena.Atk_Actions_By_Pos"
        if pct is not None:
            # override class default
            self._pct = pct
        assert self._pct > 0, "pct must be gt 0"
        assert self._pct <= 1.0, "pct must be lte 1.0"
        if arena is None:
            arena = arena_mod.Arena()
        self._arena = arena
        self._ordered_actions = []
        for stage_actions in action_chain:
            for action in [x[1] \
                    for x in (sorted((self._arena.utilities.utilities[y].cost, y)) \
                        for y in stage_actions)]:
                self._ordered_actions.append(action)
        self._idx = 0

    def take_action(self, selected_actions = None):
        if not selected_actions:
            selected_actions = self._ordered_actions
        selected_actions = set(selected_actions)
        selected_action = None
        while True:
            if self._ordered_actions[self._idx] not in selected_actions:
                continue
            try:
                if random.random() >= self._pct:
                    selected_action = self._ordered_actions[self._idx]
                    break
            finally:
                self._idx = (self._idx + 1) % len(self._ordered_actions)
        print("RETURNING ACTION:", selected_action)
        return selected_action


class ActionPickerFixedProb:
    """
    Original proposed strategy of having fixed percentages of
    probability for each legal action.

    Note: Example Strategy 6 (uniform random) is a policy provided by
    OpenSpiel already. In this one, if the probabilities are not
    provided, random-ish probabilities are assigned to each action.
    """

    def __init__(self, action_probs, **kwargs):
        if not isinstance(action_probs, dict):
            # just a list of actions, set to uniform random
            probs = random_probs(action_probs)
        else:
            probs = normalize_action_probs(probs)
        self._probs = probs

    def take_action(self, selected_actions=None):
        if selected_actions \
                and set(self._probs).difference(selected_actions):
            probs = {}
            for action in selected_actions:
                probs[action] = self._probs[action]
            probs = normalize_action_probs(probs)
        else:
            probs = self._probs
        action = np.random.choice(list(probs.keys()), p=list(probs.values()))
        return action


class ActionPickerCostScale:
    """
    Example strategy 7: Assign a probability distribution to the set of
    actions that is defined by scaling the costs to a probability
    distribution.

    Note: this doesn't specify whether it should be an inverse scaling
    """

    def __init__(self, all_actions, arena=None, **kwargs):
        self._arena = arena if arena else arena_mod.Arena()
        self._all_actions = tuple(all_actions)
        self._probs = {}
        for action in self._all_actions:
            self._probs[action] = self._arena.utilities.utilities[action].cost / 100
        self._probs = normalize_action_probs(self._probs)

    def take_action(self, selected_actions=None):
        if selected_actions \
                and set(self._probs).difference(selected_actions):
            probs = {}
            for action in selected_actions:
                probs[action] = self._probs[action]
            probs = normalize_action_probs(probs)
        else:
            probs = self._probs
        action = np.random.choice(list(probs.keys()), p=list(probs.values()))
        return action


class ActionPickerCostScaleInverse(ActionPickerCostScale):
    """
    Inverse scaling from example strategy 7 above.
    """

    def __init__(self, all_actions, arena=None, **kwargs):
        self._arena = arena if arena else arena_mod.Arena()
        self._all_actions = tuple(all_actions)
        self._probs = {}
        for action in self._all_actions:
            self._probs[action] = (1 / (2 * self._arena.utilities.utilities[action].cost))
        self._probs = normalize_action_probs(self._probs)


Action_Pickers = {
    "sequential_pct": ActionPickerSequentialThenCost,
    "fixed_prob": ActionPickerFixedProb,
    "cost_scale": ActionPickerCostScale,
    "inverse_cost_scale": ActionPickerCostScaleInverse,
}

Default_Action_Picker = "sequential_pct"

def get_action_picker_class(name):
    return Action_Pickers[name]

def list_action_pickers():
    return list(Action_Pickers.keys())



class SimpleRandomPolicy(Policy):
    """
    `Simple Randomized` are policies that set a probability for
    performing each query in a particular turn, independent of the
    history. This type of policy can be represented by a vector of
    probabilities of length ∥Ω∥. (Note that this could be extended
    to subsets of variables if needed). In the simple form of this type
    of strategy the queries for each bit are also independent.

    ...
    
    For simulating in the game testing platform, we will want to encode
    a strategy in this type by assigning a probability to each detect
    action. Since we will sample from all actions, this need not be a
    probability distribution, but we will want to have as part of the
    strategy either an ordering on the detect actions to iterate through
    until one is chosen for detection or the list is consumed, or choose
    to sample randomly without replacement.

    Useful constraints will be identifying a threshold probability for
    the likelihood any detect action is chosen, and if we order the
    detect actions, some probability threshold for the least likely
    action to be chosen.

    sisk note: we are not sampling without replacement as of yet
    """

    def __init__(self, game, action_picker=None):
        if action_picker is None:
            action_picker = Default_Action_Picker
        self._action_picker_name = action_picker
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        if not callable(action_picker):
            action_picker = get_action_picker_class(action_picker)
        self._action_picker_class = action_picker
        self._action_pickers = {}

    @classmethod
    def get_action_picker_class(cls, ap_name):
        return get_action_picker_class(ap_name)

    @classmethod
    def list_action_pickers(cls):
        return list_action_pickers()

    def action_probabilities(self, state, player_id=None):
        """
        Primary interface to a Policy. Returns a dict of actions with
        their assosciated probabilities.
        """
        legal_actions = state.legal_actions() if player_id is None \
                else state.legal_actions(player_id)
        if player_id:
            player_id = state.arena.players(player_id)
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
            print(f"player {player_id} action picker: {self._action_picker_name}")
            self._action_pickers[player_id] = \
                self._action_picker_class(all_actions, **kwargs)
        action = self._action_pickers[player_id].take_action(legal_actions)
        print("PICKER:", action)
        if action:
            return { int(action): 1.0 }
        else:
            return None
