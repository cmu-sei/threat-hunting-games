import math, random

import pyspiel
from open_spiel.python.policy import Policy

from . import arena_zsum_v4 as arena
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

Default_Player_Action_Probs = {
    arena.Players.ATTACKER: \
            uniform_probs(arena.Player_Actions[arena.Players.ATTACKER]),
    arena.Players.DEFENDER: \
            random_probs(arena.Player_Actions[arena.Players.DEFENDER]),
}


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
        if not player_action_probs:
            player_action_probs = Default_Player_Action_Probs
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        if player_action_probs:
            assert not \
                set(player_action_probs.keys()).difference(all_players), \
                    "unkown player_ids in action probabilities"
        else:
            self._player_action_probs = {}
        for player_id in self._player_action_probs:
            psum = sum(self._player_action_probs[player_id].values())
            if not math.isclose(psum, 1.0):
                #print("scaling probs")
                self._player_action_probs[player_id] = \
                    normalize_action_probs(
                            self._player_action_probs[player_id])

    @classmethod
    def defaults(cls):
        pap_probs = {}
        for player, probs in Default_Player_Action_Probs.items():
            pap_probs[player] = dict(probs)
        return pap_probs

    def action_probabilities(self, state, player_id=None):
        """
        Primary interface to a Policy. Returns a dict of actions with
        their assosciated probabilities.
        """
        legal_actions = set(state.legal_actions() if player_id is None \
                else state.legal_actions(player_id))
        if not legal_actions:
            return { pyspiel.ILLEGAL_ACTION: 1.0 }
        probs = dict(self._player_action_probs.get(player_id, {}))
        if not probs:
            probs = uniform_probs(legal_actions)
        if set(probs.keys()).difference(legal_actions):
            #print("calculating subset of action probs for", player_id)
            new_probs = {}
            for action in legal_actions:
                new_probs[action] = probs[action]
            probs = normalize_action_probs(probs)
        return probs
