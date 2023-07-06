from open_spiel.python.policy import Policy

import internal
from internal.policies import get_policy_class
from internal.policies import available_policies
from internal.policies import policy_classes
from internal.policies import load_defender_independent_intervals_args
from internal.policies import load_defender_aggregate_history_args
from internal.policies import get_player_policy_args


class SimpleRandomPolicy(Policy):

    def __init__(self, game, player_action_probs=None):
        all_players = list(range(game.num_players))
        super().__init__(game, all_players)
        self.internal = internal.policies.SimpleRandomPolicy(
                game, player_action_probs)

    def action_probabilities(self, state, player_id=None):
        return self.internal.action_probabilities(state, player_id=player_id)


class IndependentIntervalsPolicy(Policy):

    def __init__(self, game, player_intervals, clock_seed=None):
        all_players = list(range(game.num_players))
        super().__init__(game, all_players)
        self.internal = internal.policies.IndependentIntervalsPolicy(
                game, player_intervals, clock_seed=clock_seed)

    def action_probabilities(self, state, player_id=None):
        return self.internal.action_probabilities(state, player_id=player_id)


class AggregateHistoryPolicy(Policy):

    def __init__(self, game, player_seed_probs):
        all_players = list(range(game.num_players))
        super().__init__(game, all_players)
        self.internal = internal.policies.AggregateHistoryPolicy(
                game, player_seed_probs)

    def action_probabilities(self, state, player_id=None):
        return self.internal.action_probabilities(state, player_id=player_id)
