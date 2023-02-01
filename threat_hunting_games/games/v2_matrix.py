"""
Model of version 0 of the threat hunt statechain game.
"""

# pylint: disable=c-extension-no-member missing-class-docstring missing-function-docstring

import sys

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum
from logging import debug  # pylint: disable=unused-import
import pyspiel  # type: ignore
import numpy as np

from .arena_v2 import ThunderDome

arena = ThunderDome()

#_MATRIX = (
#    # ( Attacker, Defender )
#    #      Wait        Detect_Weak     Detect_Strong
#    ( (  0+0,  0-0 ), (  0+0, -1-0 ), (  0+0, -2-0 ) ), # Wait
#    ( ( -1+3,  0-3 ), ( -1+0, -1-0 ), ( -1+0, -2-0 ) ), # Advance_Noisy
#    ( ( -2+3,  0-3 ), ( -2+3, -1-3 ), ( -2+0, -2-0 ) ), # Advance_Camo
#)

# matrix_game_example.py turns this into:
#
# Utility matrix:
# 0,0   0,-1  0,-2
# 2,-3 -1,-1 -1,-1
# 1,-3  1,-4 -2,-2
#
# ...which is *almost* right except for AN/DS. should be:
#
# 0,0   0,-1  0,-2
# 2,-3 -1,-1 -1,-2 <--- there
# 1,-3  1,-4 -2,-2

# Arguments to pyspiel.GameType:
#
# (short_name: str,
#  long_name: str,
#  dynamics: open_spiel::GameType::Dynamics,
#  chance_mode: open_spiel::GameType::ChanceMode,
#  information: open_spiel::GameType::Information,
#  utility: open_spiel::GameType::Utility,
#  reward_model: open_spiel::GameType::RewardModel,
#  max_num_players: int,
#  min_num_players: int,
#  provides_information_state_string: bool,
#  provides_information_state_tensor: bool,
#  provides_observation_string: bool,
#  provides_observation_tensor: bool,
#  parameter_specification: Dict[str,
#                                GameParameter] = {},
#  default_loadable: bool = True,
#  provides_factored_observation_string: bool = False)

game_name = "chain_game_matrix_v2"
game_turns = 2

_GAME_TYPE = pyspiel.GameType(
    # see examples/matrix_game_example.py
    short_name=game_name,
    long_name="Chain game matrix version 2",
    dynamics=pyspiel.GameType.Dynamics.SIMULTANEOUS,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    # The other option here is REWARDS, which supports model-based
    # Markov decision processes. (See spiel.h)
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    # Note again: num_players doesn't count Chance
    max_num_players=len(arena.players),
    min_num_players=len(arena.players),
    provides_information_state_string=True,
    provides_information_state_tensor=True,
    # except observations are False in the example? Breaks here if so.
    provides_observation_string=True,
    provides_observation_tensor=True,
    default_loadable=True,
    provides_factored_observation_string=False,
    parameter_specification={
        "num_turns": 2,
    }
)

class V2MatrixGame(pyspiel.MatrixGame):
    """Game"""

    def __init__(self, params: Mapping[str, Any]):
        self.game_type = _GAME_TYPE
        self.arena = arena
        super().__init__(self.game_type, params, *self.arena.matrix_args())

    def new_initial_state(self, *args, **kwargs):
        return V2MatrixGameState(*args, **kwargs)


class V2MatrixGameState(pyspiel.State):

    def __init__(self, game_type, params, **kwargs):
        super().__init__(game_type, params, **kwargs)


pyspiel.register_game(_GAME_TYPE, V2MatrixGame)
