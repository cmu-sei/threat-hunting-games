"""
Model of version 0 of the threat hunt statechain game.
"""

# pylint: disable=c-extension-no-member missing-class-docstring missing-function-docstring

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


class Actions(IntEnum):
    WAIT = 0
    ADVANCE = 1
    DETECT = 2


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
    short_name="chain_game_v0",
    long_name="Chain game version 0",
    dynamics=pyspiel.GameType.Dynamics.SIMULTANEOUS,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    # The other option here is REWARDS, which supports model-based
    # Markov decision processes. (See spiel.h)
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    # Note again: num_players doesn't count Chance
    max_num_players=2,
    min_num_players=2,
    provides_information_state_string=True,
    provides_information_state_tensor=True,
    provides_observation_string=True,
    provides_observation_tensor=True,
    default_loadable=True,
    provides_factored_observation_string=False,
    parameter_specification={"num_turns": 2},
)


def make_game_info(num_turns):
    # The most expensive strategy is for D to always wait while A
    # always advances. An advance is worth 2 to A and -2 to D, so the
    # minimum utility is for D, and it's -2 * num_turns
    min_utility = -2 * num_turns
    # Max utility is for A to always advance while D defends. A spends
    # 1 to get 2, for a net utility of 1 each turn. Hence:
    max_utility = num_turns

    # Arguments to pyspiel.GameInfo:
    # (num_distinct_actions: int,
    #  max_chance_outcomes: int,
    #  num_players: int,
    #  min_utility: float,
    #  max_utility: float,
    #  utility_sum: float = 0,
    #  max_game_length: int)

    return pyspiel.GameInfo(
        num_distinct_actions=3,
        max_chance_outcomes=0,
        num_players=2,
        min_utility=float(min_utility),
        max_utility=float(max_utility),
        utility_sum=0.0,
        max_game_length=num_turns,
    )


class AttackerState(NamedTuple):
    """foo"""

    state_pos: int
    utility: int

    def advance(self, detected: bool) -> "AttackerState":
        # This can be done more concisely, but to make the logic clear:

        # Advancing costs 1, whether it succeeds or not
        new_utility = self.utility - 1

        new_state = self.state_pos

        if not detected:
            # If successful, the attacker advances to a new state and
            # gets 2 utility
            new_utility = self.utility + 2
            # (Assuming an infinite-length, uniform-value state chain,
            # which is silly but simple.)
            new_state = self.state_pos + 1

        # pylint: disable=no-member
        return self._replace(state_pos=new_state, utility=new_utility)


class DefenderState(NamedTuple):
    utility: int

    def detect(self) -> "DefenderState":
        # Detecting costs 1
        new_utility = self.utility - 1

        # Note: A detect action may stop an advance action, but that
        # doesn't change any Defender state.

        # pylint: disable=no-member
        return self._replace(utility=new_utility)


# pylint: disable=too-few-public-methods
class V0GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info):
        super().__init__(game)
        self._num_turns = game_info.max_game_length
        self._curr_turn = 0
        self._attacker = AttackerState(0, 0)
        self._defender = DefenderState(0)

        # A few variables are used in the sample games both to
        # control game state and in assertions to document
        # invariants. Their names are conventional, not encoded into
        # the API, but we re-use them here to establish continuity
        # with the examples.

        # Used by convention in the sample games to indicate that the
        # game should terminate.
        self._game_over = False

        # If this were a stochastic game, _is_chance would used in
        # _apply_action (maybe elsewhere?) by convention, to determine
        # whether the chance player is expected to act. AIUI, all
        # player actions in sequential-move games, including chance,
        # are resolved in _apply_action. In simultaneous-move games,
        # the "regular" players' actions are resolved simultaneously
        # (natch) in _apply_actions, but _apply_action is still called
        # to resolve the actions of the chance player (and perhaps
        # some otherinfrastructure players to be named later).
        #
        # self._is_chance = False

    @property
    def attacker_state(self):
        return self._attacker

    @property
    def defender_state(self):
        return self._defender

    def current_player(self):
        """
        Returns id of the next player to move. TERMINAL indicates
        the game is over, and SIMULTANEOUS indicates that a
        simultaneous turn should take place.

        Additional possibilities in other kinds of games include
        CHANCE (in stochastic games when the chance player should act)
        and a valid player ID (in games with sequential turns).
        """
        if self._game_over:
            return pyspiel.PlayerId.TERMINAL
        return pyspiel.PlayerId.SIMULTANEOUS

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

    def _legal_actions(self, player):
        """
        Returns a list of legal actions, sorted in \"ascending\"
        order. (The underlying structure in the c++ is
        std::vector<Action>, where Action is defined in spiel_utils.h
        as an int64, so your actions are comparable integers, not
        categories.)
        """
        # Asserted as invariant in sample games:
        if self._game_over:
            return []

        assert player >= 0
        debug(f"legal actions for player {player}")
        match player:
            case Players.ATTACKER:
                return [Actions.WAIT, Actions.ADVANCE]
            case Players.DEFENDER:
                return [Actions.WAIT, Actions.DETECT]
            case _:
                # TODO: Maybe raise error here?
                return []

    def _apply_action(self, action):
        """
        Apply the actions of a single player in sequential-move
        games. In all stochastic games, _apply_action is called to
        resolve the actions of the chance player. Not used here, but
        shown for reference.
        """
        # Asserted as invariant in sample games:
        # assert self._is_chance and not self._game_over

        # We're a simultaneous-move game, so this should never be
        # called.
        raise NotImplementedError()

    def _apply_actions(self, actions: List[int]):
        """
        Apply actions of all players in simultaneous-move games.

        Actions is a list of action IDs. I have not verified this in
        the code, but the index of the list item appears to correspond
        to the ID of the player taking the action.
        """
        # Asserted as invariant in sample games:
        # assert not self._is_chance and not self._game_over

        # If this were a stochastic game, we'd want to set
        # self._is_chance here because the next step in the game
        # processing is to call _apply_action for the chance player.
        # (Not sure why it's handled that way.)
        # self._is_chance = True

        attacker_action = actions[Players.ATTACKER]
        defender_action = actions[Players.DEFENDER]

        if defender_action == Actions.DETECT:
            self._defender = self._defender.detect()
        if attacker_action == Actions.ADVANCE:
            self._attacker = self._attacker.advance(defender_action == Actions.DETECT)

        # Note: Actions.WAIT is a no-op

        # Are we done?
        self._curr_turn += 1
        assert self._curr_turn <= self._num_turns
        if self._curr_turn == self._num_turns:
            self._game_over = True

    ### Not sure if these methods are required, but they are
    ### implemented in sample games. We should probably do some
    ### logging/error injection to figure this out.

    def _action_to_string(self, player, action):
        """Convert an action to a string representation, presumably
        for logging."""
        # need clarification on this None player
        #player = [None, "Attacker", "Defender"][player]
        #action = [None, "WAIT", "ADVANCE", "DEFEND"][action]
        player = ["Attacker", "Defender"][player]
        action = ["WAIT", "ADVANCE", "DEFEND"][action]
        return f"{player}: {action}"

    def is_terminal(self):
        """Return True if the game is over."""
        return self._game_over

    def returns(self):
        """Total reward for each player over the course of the game so
        far."""
        return [self._attacker.utility, self._defender.utility]

    def __str__(self):
        """String for debugging. No particular semantics."""
        return f"Attacker pos at Turn {self._curr_turn}: {self._attacker.state_pos}"


class OmniscientObserver:
    """
    Observer, conforming to the PyObserver interface (see
    open_spiel/python/observation.py).
    """

    def __init__(self, params):  # pylint: disable=unused-argument
        self.tensor = np.zeros((3,), int)

    def set_from(
        self, state: V0GameState, player: int
    ):  # pylint: disable=unused-argument
        """
        Update the observer state to reflect `state` from the POV
        of `player`.

        This is an omniscient observation, so the info will be the same for all players.
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


class V0Game(pyspiel.Game):
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

    def new_initial_state(self):
        """Return a new GameState object"""
        return V0GameState(self, self.game_info)

    def make_py_observer(self, iig_obs_type=None, params=None):
        """
        Create an observer object of type `iig_obs_type`, configured using `params`.

        In this simple example, only one type of Observer exists, and
        it isn't configurable, so both input arguments are ignored.
        """
        match iig_obs_type:
            case _:
                return OmniscientObserver(params)


pyspiel.register_game(_GAME_TYPE, V0Game)
