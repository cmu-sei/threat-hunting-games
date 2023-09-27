"""
Modified from the LastAction class in open_spiel/python/policy.py
"""

from open_spiel.python.policy import Policy

class LastActionPolicy(Policy):
  """A policy that always takes the lowest-numbered legal action."""

  def __init__(self, game):
    all_players = list(range(game.num_players()))
    super().__init__(game, all_players)

  def action_probabilities(self, state, player_id=None):
    legal_actions = (
        state.legal_actions()
        if player_id is None else state.legal_actions(player_id))
    if not legal_actions:
      return {0: 1.0}
    max_action = max(legal_actions)
    return {
        action: 1.0 if action == max_action else 0.0 for action in legal_actions
    }
