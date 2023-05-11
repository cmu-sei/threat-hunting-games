
import itertools
from typing import Iterable
from copy import deepcopy

from open_spiel.python.policy import Policy


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

    def __init__(self, game, player_action_probs=None):
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        if player_action_probs:
            assert not \
                set(player_action_probs.keys()).difference(all_players), \
                    "unkown player_ids in action probabilities"
            self._player_action_probs = paprobs = {}
            for player, probs in player_action_probs.items():
                probs = dict(probs)
                psum = sum(probs.values) or (len(probs) / 100)
                for action in probs:
                    probs[action] *= (1 / psum)
                paprobs[player] = probs
        else:
            self._player_action_probs = {}
            for player_id in all_players:
                self._player_action_probs[player_id] = {}

    def action_probabilities(self, state, player_id=None):
        legal_actions = (
            state.legal_actions()
            if player_id is None else state.legal_actions(player_id))
        if not legal_actions:
            return { 0: 1.0 }
        if len(legal_actions) == 1:
            return { legal_actions[0]: 1.0 }
        all_probs = self._player_action_probs.get(player_id)
        if len(all_probs) != len(legal_actions):
            probs = {}
            for action in legal_actions:
                probs[action] = all_probs.get(action, 0)
            # if legal_actions are a subset of all actions, scale
            # probabilities sum to 1.0 accordingly
            psum = sum(probs.values()) or (len(probs) / 100)
            for action in probs:
                probs[action] *= (1 / psum)
        else:
            probs = all_probs
        if not probs:
            # uniform distribution if not otherwise specified
            prob = 1 / len(legal_actions)
            probs = { action: prob for action in legal_actions }
        return probs
