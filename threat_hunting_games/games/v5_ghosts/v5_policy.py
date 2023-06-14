"""
Model of version 2 of the threat hunt statechain game, sequential,
constant sum. (action cost is the opposing players gain)
"""

# pylint: disable=c-extension-no-member missing-class-docstring missing-function-docstring

import sys

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum
from dataclasses import dataclass, field
from open_spiel.python.observation import IIGObserverForPublicInfoGame
from open_spiel.python.policy import Policy
import pyspiel  # type: ignore
import numpy as np

from absl import logging
#from absl.logging import debug
# this gets reset somewhere mysterious
#logging.set_verbosity(logging.DEBUG)

from . import internal
from .internal.game import game_name

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

_GAME_TYPE = pyspiel.GameType(
    short_name=internal.game.game_name,
    long_name=internal.game.game_long_name,
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    #utility=pyspiel.GameType.Utility.CONSTANT_SUM,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    # The other option here is REWARDS, which supports model-based
    # Markov decision processes. (See spiel.h)
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    # Note again: num_players doesn't count Chance
    max_num_players=internal.game.num_players,
    min_num_players=internal.game.num_players,
    provides_information_state_string=True,
    provides_information_state_tensor=True,
    provides_observation_string=True,
    provides_observation_tensor=True,
    default_loadable=True,
    provides_factored_observation_string=False,
    # parameter_specification valid value types (see game_parameters.h)
    #
    #  int, float, str, bytes, dict (can embed other dicts)
    #
    # tuples, lists, and others don't work
    parameter_specification={
        "num_turns": internal.game.game_max_turns,
        # if playing using bots, policies must be None
        "attacker_policy": None,
        #"defender_policy": "uniform_random",
        #"defender_policy": "simple_random",
        #"defender_policy": "independent_intervals",
        #"defender_policy": "aggregate_history",
        "defender_policy": None,
    }
)

def make_game_info(num_turns: int) -> pyspiel.GameInfo:
    # In this constant sum game, each player starts with 30 utility, so
    # max is 60
    min_utility = internal.arena.min_utility() * num_turns
    max_utility = internal.arena.max_utility() * num_turns

    # Arguments to pyspiel.GameInfo:
    # (num_distinct_actions: int,
    #  max_chance_outcomes: int,
    #  num_players: int,
    #  min_utility: float,
    #  max_utility: float,
    #  utility_sum: float = 0,
    #  max_game_length: int)

    return pyspiel.GameInfo(
        num_distinct_actions=len(internal.arena.Actions),
        max_chance_outcomes=0,
        num_players=internal.game.num_players,
        min_utility=float(min_utility),
        max_utility=float(max_utility),
        utility_sum=0.0,
        max_game_length=num_turns,
    )


# pylint: disable=too-few-public-methods
class GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info):
        super().__init__(game)
        game_params = game.get_parameters()
        print("PARAMS:", game_params)
        self.internal = internal.game.GameState(game_params=game_params)

    def current_player(self):
        """
        Returns id of the next player to move. TERMINAL indicates
        the game is over, and SIMULTANEOUS indicates that a
        simultaneous turn should take place.

        Additional possibilities in other kinds of games include
        CHANCE (in stochastic games when the chance player should act)
        and a valid player ID (in games with sequential turns).
        """
        player = self.internal.current_player()
        if player is None:
            return pyspiel.PlayerId.TERMINAL
        else:
            return player

    # Despite the leading underscore, these methods are part of the
    # public API. See the definition of PyState in
    # python_games.cc. They correspond to the similarly-named
    # camelCase methods for open_spiel::State in spiel.h.
    #
    # In case you're wondering (I obviously did), the methods with
    # underscores are pure virtual methods in the C++ that require
    # "trampoline" methods in the binding code to work. This isn't a
    # requirement of pybind11 or the core open_spiel API, afaict. The
    # binding developers seem to have chosen to do this. So blame the
    # folks who developed the open_spiel bindings when you're
    # twitching over redefining Python methods with leading
    # underscores.

    def _legal_actions(self, player) -> list[internal.arena.Actions]:
        """
        Returns a list of legal actions, sorted in \"ascending\"
        order. (The underlying structure in the c++ is
        std::vector<Action>, where Action is defined in spiel_utils.h
        as an int64, so your actions are comparable integers, not
        categories.)
        """
        return self.internal.legal_actions(player)

    def _apply_actions(self, actions: List[int]):
        """
        Apply actions of all players in simultaneous-move games.

        Actions is a list of action IDs. I have not verified this in
        the code, but the index of the list item appears to correspond
        to the ID of the player taking the action.
        """
        # Asserted as invariant in sample games:
        # assert not self._is_chance and not self._game_over

        # We're a sequential-move game, so this should never be
        # called.

        # If this were a stochastic game, we'd want to set
        # self._is_chance here because the next step in the game
        # processing is to call _apply_action for the chance player.
        # (Not sure why it's handled that way.)
        # self._is_chance = True
        return self.internal.apply_actions(actions)

    def _apply_action(self, action):
        """
        Apply the actions of a single player in sequential-move
        games. In all stochastic games, _apply_action is called to
        resolve the actions of the chance player. Not used here, but
        shown for reference.
        """
        return self.internal.apply_action(action)

    ### Not sure if these methods are required, but they are
    ### implemented in sample games. We should probably do some
    ### logging/error injection to figure this out.

    def _action_to_string(self, player, action):
        """Convert an action to a string representation, presumably
        for logging."""
        return self.internal.action_to_string(player, action)

    def is_terminal(self):
        """Return True if the game is over."""
        return self.internal.is_terminal()

    def rewards(self):
        """Total reward for each player for current turn"""
        # this does not get called by openspiel...?
        return self.internal.rewards()

    def returns(self):
        """Total reward for each player over the course of the game so
        far."""
        return self.internal.returns()

    def turns_played(self):
        """Number of turns played thus far."""
        return self.internal.turns_played()

    def turns_exhausted(self):
          """
          Indicates whether the game maxed out turns rather than either
          player having a conclusive victory. This is not necessarily
          equivalent to max turns having been reached since the final turn
          might have been a success for either player.
          """
          return self.internal.turns_exhausted()

    def __str__(self):
        """String for debugging. No particular semantics."""
        return self.internal.__str__()


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

        #debug("OBS PARAMS:", params)
        #num_turns = params["num_turns"]

        board_size = 3 # atk_pos, atk_util, def_util
        hist_size = internal.game_max_turns
        tensor_size = board_size + hist_size
        self.tensor = np.zeros(tensor_size, int)
        self.dict = {}
        idx = 0
        self.dict["board"] = \
                self.tensor[idx:idx+board_size].reshape(board_size,)
        idx += board_size
        self.dict["history"] = \
                self.tensor[idx:idx+hist_size].reshape(hist_size,)

        # algorithms.generate_playthrough, at least, expects
        # be here (can be empty...this is based on BoardObserver in
        # games/tic_tac_toe.py):
        #self.dict["observation"] = self.tensor

    def set_from(self, state: GameState, player: int):  # pylint: disable=unused-argument
        """
        Update the observer state to reflect `state` from the POV
        of `player`.

        This is an omniscient observation, so the info will be the same
        for all players.
        """
        #debug("set_from() here, turn/player:", state._curr_turn+1, player)
        # Tensor values: attacker position, attacker utility, defender utility
        #self.tensor[0] = state._attacker.state_pos
        #self.tensor[1] = state._attacker.utility
        #self.tensor[2] = state._defender.utility

        self.dict["board"][:] = [state._attacker.state_pos,
                state._attacker.utility,state._defender.utility]
        hist = state.history()
        self.dict["history"][:len(hist)] = hist

    def string_from(self, state, player):  # pylint: disable=unused-argument
        """
        Return a string representation of the state updated in
        `state_from`.
        """
        return state.history_str()
        # These are concatenated into a single string. The f prefix is
        # unnecessary for all but the first, but it makes the syntax
        # highlighting work better in Emacs. :)
        turn = round(state._curr_turn/2) - 1 # this gets invoked after turn increment
        board = self.dict["board"]
        hist = self.dict["history"]
        return (
            #f"Attacker position: {self.tensor[0]} | "
            #f"Attacker Utility: {self.tensor[1]} | "
            #f"Defender Utility: {self.tensor[2]}"
            f"Attacker Position: {board[0]} | "
            f"Attacker Utility: {board[1]} | "
            f"Defender Utility: {board[2]} | "
            f"History: {hist}"
        )


class Game(pyspiel.Game):
    """Game"""

    def __init__(self, params: Mapping[str, Any]):
        """
        Constructor.

        Minimum requirement for the constructor is that it can be
        called with a single argument of the parameters for this game
        instance.
        """
        self.game_type = _GAME_TYPE
        self.game_info = make_game_info(params["num_turns"])
        super().__init__(self.game_type, self.game_info, params)
        print("\ngame params:\n", self.get_parameters(), "\n")

    def new_initial_state(self):
        """Return a new GameState object"""
        return GameState(self, self.game_info)

    #def make_py_observer(self, iig_obs_type=None, params=None):
    #    return OmniscientObserver(params)

    def make_py_observer(self, iig_obs_type=None, params=None):
        """
        Create an observer object of type `iig_obs_type`, configured
        using `params`.
        """
        #if iig_obs_type:
        #    debug("make_py_observer:", iig_obs_type, params)
        #    debug(dir(iig_obs_type))
        #    debug(iig_obs_type.private_info)
        #    debug(dir(iig_obs_type.private_info))
        return OmniscientObserver(params)


pyspiel.register_game(_GAME_TYPE, Game)
