"""
Test running a trajectory for V0 of the threat hunting game.
"""
# pylint: disable=missing-function-docstring

from logging import debug  # pylint: disable=unused-import
from numpy import random
from typing import NoReturn

import pytest
import pyspiel  # type: ignore

from threat_hunting_games import v0


@pytest.fixture
def game():
    return pyspiel.load_game("chain_game_v0", {"num_turns": 2})


def play_a_turn(state, strategy):
    state.apply_actions(strategy(state))


def wait_strategy(state):
    return [0, v0.Actions.WAIT, v0.Actions.WAIT]


def random_strategy(state):
    return [
        0,
        random.choice(state.legal_actions(v0.Players.ATTACKER)),
        random.choice(state.legal_actions(v0.Players.DEFENDER)),
    ]


def test_game_load(game):
    """A game can be loaded via pyspiel.load_game."""
    assert True


def test_state(game):
    """The  game can return an initial state"""
    state = game.new_initial_state()
    assert str(state) == "Attacker pos at Turn 0: 0"


def test_game_finishes(game):
    """The game state correctly reflects when the game terminates."""
    state = game.new_initial_state()
    # After turn 0
    assert state.is_terminal() is False
    play_a_turn(state, random_strategy)
    # After turn 1
    assert state.is_terminal() is False
    play_a_turn(state, random_strategy)
    # After turn 2 (should be over)
    assert state.is_terminal() is True
