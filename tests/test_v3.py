"""
Test running a trajectory for V1 of the threat hunting game.
"""
# pylint: disable=missing-function-docstring

from logging import debug  # pylint: disable=unused-import
from numpy import random
from typing import NoReturn

import pytest
import pyspiel  # type: ignore
from open_spiel.python.algorithms.get_all_states import get_all_states

from threat_hunting_games.games.v3 import arena_v3 as arena

game_name = "chain_game_v3_bitlock"

@pytest.fixture
def game():
    return pyspiel.load_game(game_name)


def test_game_load(game):
    """A game can be loaded via pyspiel.load_game."""
    assert True


#def test_game_finishes(game):
#    """The game state correctly reflects when the game terminates."""
#    state = game.new_initial_state()
#    # After turn 0
#    assert state.is_terminal() is False
#    play_a_turn(state, random_strategy)
#    # After turn 1
#    assert state.is_terminal() is False
#    play_a_turn(state, random_strategy)
#    # After turn 2 (should be over)
#    assert state.is_terminal() is True

def test_arena_consequence():
    action1 = arena.Actions.S1_WRITE_EXE
    action2 = arena.Actions.SMB_LOGS

    utils1 = arena.Utilities[action1] = arena.Utility(2, 4, arena.ZSUM)
    utils2 = arena.Utilities[action2] = \
            arena.Utility(2, arena.ZSUM, arena.ZSUM)

    assert arena.utils1_reward(utils1, utils2) == utils1.reward
    assert arena.utils2_damage(utils1, utils2) == utils1.reward
    assert arena.utils1_reward(utils2, utils1) == utils1.reward
    assert arena.utils2_damage(utils2, utils1) == utils1.reward

    assert arena.consequence(action1, action2) == utils1.reward
    assert arena.consequence(action2, action1) == -utils1.reward
