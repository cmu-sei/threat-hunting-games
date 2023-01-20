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


class Players(IntEnum):
    # the values of these Player enums are used as 0-based indices later
    # -- also hence IntEnum
    ATTACKER = 0
    DEFENDER = 1

# note: I tried representing the IV as an integer and playing around
# with various values for the action types (splitting out
# attacker/defender actions into their own IntEnums) in such a way as to
# facilitate a truth table for detect/no_detect/don't_care but there was
# no consistent way to do it with a single logical operation (or, !xor,
# etc). Figuring out the bit math as number of actions grows doesn't
# seem scalable. Plus an integer IV limits the number of turns in a game
# if you want perfect recall in the IV

class Actions(IntEnum):
    WAIT = 0
    ADVANCE_NOISY = 1
    ADVANCE_CAMO = 2
    DETECT_WEAK = 3
    DETECT_STRONG = 4

_MATRIX_ROWS = [
    [ "Wait", "Detect_Weak",   "Detect_Strong" ],
    [ "Wait", "Advance_Noisy",  "Advance_Camo" ],
    #          AW              AN              AC
    [ [  0-0, 0+0 ], [  0-3, -1+3 ], [  0-3, -2+3 ], # DW
      [ -1-0, 0+0 ], [ -1-0, -1+0 ], [ -1-3, -2+3 ], # DW
      [ -2-0, 0+0 ], [ -2-0, -1+0 ], [ -2-0, -2+0 ], # DS
    ],
    #          DW              DW              DS
    [ [  0+0, 0-0 ], [  0+0, -1-0 ], [  0+0, -2-0 ], # AW
      [ -1+3, 0-3 ], [ -1+0, -1-0 ], [  1+0, -2-0 ], # AN
      [ -2+3, 0-3 ], [ -2+3, -1-3 ], [ -2+0, -2-0 ], # AC
    ],
]

_MATRIX = {
    "row_actions": _MATRIX_ROWS[0],
    "col_actions": _MATRIX_ROWS[1],
    "row_player_utilities": _MATRIX_ROWS[2],
    "col_player_utilities": _MATRIX_ROWS[3],
 }

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
    max_num_players=len(Players),
    min_num_players=len(Players),
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
        super().__init__(self.game_type, params,
                _MATRIX["row_actions"],
                _MATRIX["col_actions"],
                _MATRIX["row_player_utilities"],
                _MATRIX["col_player_utilities"])

    def new_initial_state(self, *args, **kwargs):
        return V2MatrixGameState(*args, **kwargs)

#    def make_py_observer(self, iig_obs_type=None, params=None):
#        """
#        Create an observer object of type `iig_obs_type`, configured
#        using `params`.
#
#        In this simple example, only one type of Observer exists, and
#        it isn't configurable, so both input arguments are ignored.
#        """
#        match iig_obs_type:
#            case _:
#                return OmniscientObserver(params)


class V2MatrixGameState(pyspiel.State):

    def __init__(self, game_type, params, **kwargs):
        super().__init__(game_type, params, **kwargs)

    ### Not sure if these methods are required, but they are
    ### implemented in sample games. We should probably do some
    ### logging/error injection to figure this out.

    def _action_to_string(self, player, action):
        """Convert an action to a string representation, presumably
        for logging."""
        player_str = ["Attacker", "Defender"][player]
        action_str = ["WAIT", "ADVANCE_NOISY", "ADVANCE_CAMO",
                      "DEFEND_WEAK", "DEFEND_STRONG"][action]
        return f"{player_str}: {action_str}"

    ### some overrides that make playthrough history strings look better

    def history_str(self):
        # in spiel.h this still uses history(), only there for
        # backwards-compatibility reasons, which only returns actions
        return ', '.join(
            f"({x.player}, {x.action})" for x in self.full_history())

#
class OmniscientObserver:
    """
    Observer, conforming to the PyObserver interface (see
    open_spiel/python/observation.py).

    Observers are created and used via pyspiel.observation which is
    used in a harness around games. The primary interface for observers
    is algorithms.generate_playthrough. See examples/playthrough.py.
    """

    def __init__(self, params):  # pylint: disable=unused-argument
        # note: params is invariant, it can't be used to pass things
        # back and forth between states and observer
        self.tensor = np.zeros((3,), int)
        # algorithms.generate_playthrough, at least, expects this to
        # be here:
        self.dict = {}

    def set_from(
        self, state: V2MatrixGameState, player: int
    ):  # pylint: disable=unused-argument
        """
        Update the observer state to reflect `state` from the POV
        of `player`.

        This is an omniscient observation, so the info will be the same
        for all players.
        """
        # Tensor values: attacker position, attacker utility, defender utility
        self.tensor[0] = state.attacker_state.state_pos
        self.tensor[1] = state.attacker_state.utility
        self.tensor[2] = state.defender_state.utility

    def string_from(self, state, player):  # pylint: disable=unused-argument
        """
        Return a string representation of the state updated in
        `state_from`.
        """
        # These are concatenated into a single string. The f prefix is
        # unnecessary for all but the first, but it makes the syntax
        # highlighting work better in Emacs. :)
        return (
            f"Attacker position: {self.tensor[0]} | "
            f"Attacker Utility: {self.tensor[1]} | "
            f"Defender Utility: {self.tensor[2]}"
        )


pyspiel.register_game(_GAME_TYPE, V2MatrixGame)
