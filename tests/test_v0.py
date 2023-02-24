"""
Test running a trajectory for V0 of the threat hunting game.
"""
# pylint: disable=missing-function-docstring

from logging import debug  # pylint: disable=unused-import
from numpy import random
from typing import NoReturn

import pytest
import pyspiel  # type: ignore
from open_spiel.python.algorithms.get_all_states import get_all_states

from threat_hunting_games.games.v0 import v0

game_name = "chain_game_v0"
turns = 2

@pytest.fixture
def game():
    return pyspiel.load_game(game_name, {"num_turns": turns})


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

def all_nodes(game):
    depth_limit = turns
    include_terminals = True
    include_chance_states = False
    return get_all_states(game, depth_limit,
            include_terminals, include_chance_states)

def test_allstate():
    game = pyspiel.load_game(game_name, {"num_turns": turns})
    initial_state = game.new_initial_state()
    attack_actions = initial_state.legal_actions(v0.Players.ATTACKER)
    defend_actions = initial_state.legal_actions(v0.Players.DEFENDER)
    branches_per_node = len(attack_actions) * len(defend_actions)
    expected_nodes = (branches_per_node**(turns+1)-1)/(branches_per_node - 1)

    depth_limit = turns
    include_terminals = True
    include_chance_states = False
    sim_nodes = get_all_states(game, depth_limit,
            include_terminals, include_chance_states)
    assert len(sim_nodes) == expected_nodes
