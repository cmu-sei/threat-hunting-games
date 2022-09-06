"""
Test running a trajectory for V0 of the threat hunting game.
"""
# pylint: disable=missing-function-docstring

from threat_hunting_games import v0


def test_game_and_state():
    info = v0.make_game_info(3)
    game = v0.V0Game(info)
    #    state = game.new_initial_state()
    assert False
    # assert str(state) == "FASLE"
