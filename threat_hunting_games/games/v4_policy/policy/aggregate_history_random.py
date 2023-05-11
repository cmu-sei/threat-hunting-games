from open_spiel.python.policy import Policy

from .simple_random import SimpleRandomPolicy
from .independent_intervals import IndependentIntervalsPolicy

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
    """

    def __init__(self, game, player_action_probs=None, player_intervals=None):
        all_players = list(range(game.num_players()))
        super().__init__(game, all_players)
        self._simple_random = \
                SimpleRandomPolicy(game,
                        player_action_probs=player_action_probs)
        self._independent_intervals = \
                IndependentIntervalsPolicy(game,
                        player_intervals=player_intervals)

    def action_probabilities(self, state, player_id=None):
        legal_actions = (
            state.legal_actions()
            if player_id is None else state.legal_actions(player_id))
        if not legal_actions:
            return { 0: 1.0 }
        if len(legal_actions) == 1:
            return { legal_actions[0]: 1.0 }
        simp_rand_probs = self._simple_random.action_probabilities(
                state, player_id=player_id)
        ind_int_probs = self._independent_intervals.action_probabilities(
                state, player_id=player_id)
        probs = {}
        psum = 0
        for action in legal_actions:
            probs[action] = (1 + simp_rand_probs.get(action, 0)) \
                    * (1 + ind_int_probs.get(action, 0))
            psum += probs[action]
        for action in probs:
            probs[action] *= (1 / psum)
        return probs
