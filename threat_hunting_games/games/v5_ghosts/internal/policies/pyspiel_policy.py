# Copyright 2019 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as python3
"""Representation of a policy for a game.

This is a standard representation for passing policies into algorithms,
with currently the following implementations:

  TabularPolicy - an explicit policy per state, stored in an array
    of shape `(num_states, num_actions)`, convenient for tabular policy
    solution methods.
  UniformRandomPolicy - a uniform distribution over all legal actions for
    the specified player. This is computed as needed, so can be used for
    games where a tabular policy would be unfeasibly large.

The main way of using a policy is to call `action_probabilities(state,
player_id`), to obtain a dict of {action: probability}. `TabularPolicy`
objects expose a lower-level interface, which may be more efficient for
some use cases.
"""

import itertools
from typing import Iterable

import numpy as np

class Policy:
  """Base class for policies.

  A policy is something that returns a distribution over possible actions
  given a state of the world.

  Attributes:
    game: the game for which this policy applies
    player_ids: list of player ids for which this policy applies; each in the
      interval [0..game.num_players()-1].
  """

  def __init__(self, game, player_ids):
    """Initializes a policy.

    Args:
      game: the game for which this policy applies
      player_ids: list of player ids for which this policy applies; each should
        be in the range 0..game.num_players()-1.
    """
    self.game = game
    self.player_ids = player_ids

  def action_probabilities(self, state, player_id=None):
    """Returns a dictionary {action: prob} for all legal actions.

    IMPORTANT: We assume the following properties hold:
    - All probabilities are >=0 and sum to 1
    - TLDR: Policy implementations should list the (action, prob) for all legal
      actions, but algorithms should not rely on this (yet).
      Details: Before May 2020, only legal actions were present in the mapping,
      but it did not have to be exhaustive: missing actions were considered to
      be associated to a zero probability.
      For example, a deterministic state-poliy was previously {action: 1.0}.
      Given this change of convention is new and hard to enforce, algorithms
      should not rely on the fact that all legal actions should be present.

    Args:
      state: A `pyspiel.State` object.
      player_id: Optional, the player id for whom we want an action. Optional
        unless this is a simultaneous state at which multiple players can act.

    Returns:
      A `dict` of `{action: probability}` for the specified player in the
      supplied state.
    """
    raise NotImplementedError()

  def __call__(self, state, player_id=None):
    """Turns the policy into a callable.

    Args:
      state: The current state of the game.
      player_id: Optional, the player id for whom we want an action. Optional
        unless this is a simultaneous state at which multiple players can act.

    Returns:
      Dictionary of action: probability.
    """
    return self.action_probabilities(state, player_id)


class UniformRandomPolicy(Policy):
  """Policy where the action distribution is uniform over all legal actions.

  This is computed as needed, so can be used for games where a tabular policy
  would be unfeasibly large, but incurs a legal action computation every time.
  """

  def __init__(self, game):
    """Initializes a uniform random policy for all players in the game."""
    all_players = list(range(game.num_players()))
    super().__init__(game, all_players)

  def action_probabilities(self, state, player_id=None):
    """Returns a uniform random policy for a player in a state.

    Args:
      state: A `pyspiel.State` object.
      player_id: Optional, the player id for which we want an action. Optional
        unless this is a simultaneous state at which multiple players can act.

    Returns:
      A `dict` of `{action: probability}` for the specified player in the
      supplied state. This will contain all legal actions, each with the same
      probability, equal to 1 / num_legal_actions.
    """
    legal_actions = (
        state.legal_actions()
        if player_id is None else state.legal_actions(player_id))
    if not legal_actions:
      return {0: 1.0}
    probability = 1 / len(legal_actions)
    return {action: probability for action in legal_actions}


class FirstActionPolicy(Policy):
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
    min_action = min(legal_actions)
    return {
        action: 1.0 if action == min_action else 0.0 for action in legal_actions
    }
