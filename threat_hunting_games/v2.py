"""
Model of version 2 of the threat hunt statechain game.
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
#
# Also I ran into difficulties trying to put attack/defend actions in
# their own IntEnums (0, 1, 2 value for each). Pyspiel will blow up if
# the action values are not indeed distinct.

class Actions(IntEnum):
    WAIT = 0
    ADVANCE_NOISY = 1
    ADVANCE_CAMO = 2
    DETECT_WEAK = 3
    DETECT_STRONG = 4

class Utility(NamedTuple):
    cost:    int # utility cost
    reward:  int # action success reward
    penalty: int # action failure penalty

# these action_utils dicts could be strung together in a turn-based
# chain, or put in a dict with turn number as key (for sparse changes)
# in order to have varying utilities as the game progresses
_utils = {
    Actions.WAIT:          Utility(0, 0, 0),
    Actions.ADVANCE_NOISY: Utility(1, 3, 0),
    Actions.ADVANCE_CAMO:  Utility(2, 3, 0),
    Actions.DETECT_WEAK:   Utility(1, 0, 3),
    Actions.DETECT_STRONG: Utility(2, 0, 3),
}

_attack_actions = (
    Actions.WAIT,
    Actions.ADVANCE_NOISY,
    Actions.ADVANCE_CAMO,
)

_defend_actions = (
    Actions.WAIT,
    Actions.DETECT_WEAK,
    Actions.DETECT_STRONG,
)

_max_cost = max(x.cost for x in _utils.values())
_max_penalty = max(x.penalty for x in _utils.values())
_max_reward = max(x.reward for x in _utils.values())

# just an idea rather than all the if/then logic
_detect_table = np.array([
    # if this was a proper game matrix, these would be utility pairs;
    # columns are defend, rows are attack:
    #   -1 = no-op
    #    0 = breached
    #    1 = detect
    [ -1, -1, -1 ],
    [ -1,  1,  1 ],
    [ -1,  0,  1 ],
])

_action_idx = {}
for i, action in enumerate(_attack_actions):
    _action_idx[action] = i
for i, action in enumerate(_defend_actions):
    _action_idx[action] = i

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

game_name = "chain_game_v2"

game_turns = 2

_GAME_TYPE = pyspiel.GameType(
    short_name=game_name,
    long_name="Chain game version 2",
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
    provides_information_state_string=False,
    provides_information_state_tensor=False,
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
        "num_turns": 2,
    }
)


def make_game_info(num_turns):
    # The most expensive strategy is for D to always wait while A
    # always advances. An advance is worth 2 to A and -2 to D, so the
    # minimum utility is for D, and it's -2 * num_turns
    min_utility = -(_max_cost + _max_penalty) * num_turns
    # Max utility is for A to always advance while D defends. A spends
    # 1 to get 2 (or 2 to get 3 for stealth), for a net utility of 1
    # each turn. Hence:
    max_utility = _max_reward * num_turns

    # Arguments to pyspiel.GameInfo:
    # (num_distinct_actions: int,
    #  max_chance_outcomes: int,
    #  num_players: int,
    #  min_utility: float,
    #  max_utility: float,
    #  utility_sum: float = 0,
    #  max_game_length: int)

    return pyspiel.GameInfo(
        num_distinct_actions=5,
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

    def advance(self, action: Actions, detected: bool) -> "AttackerState":

        print("ATTACK old_utility:", self.utility)

        utils = _utils[action]

        new_utility = self.utility - utils.cost
        new_state = self.state_pos

        if action and not detected:
            # If successful, the attacker advances to a new state and
            # gets 2 utility
            new_utility += utils.reward
            # (Assuming an infinite-length, uniform-value state chain,
            # which is silly but simple.)
            new_state += 1

        print("ATTACK new_utility:", new_utility)

        # pylint: disable=no-member
        return self._replace(
            state_pos=new_state,
            utility=new_utility,
        )


class DefenderState(NamedTuple):
    utility: int

    def detect(self, action: Actions, breached: bool) -> "DefenderState":

        print("DEFEND old_utility:", self.utility)

        utils = _utils[action]

        new_utility = self.utility - utils.cost

        if breached:
            new_utility -= utils.penalty

        print("DEFEND new_utility:", new_utility)

        # pylint: disable=no-member
        return self._replace(
            utility=new_utility,
        )


# pylint: disable=too-few-public-methods
class V2GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info):
        super().__init__(game)
        self._num_turns = game_info.max_game_length
        self._curr_turn = 0
        self._attacker = AttackerState(0, 0)
        self._defender = DefenderState(0)

        # Phil was talking about tracking the IV down in the Observer,
        # which is certainly possible...will seek clarification -- some
        # of this will become more clear when we start building
        # harnesses around the game that actually create and use
        # observers
        self._info_vec = np.zeros((self._num_turns,), int)
        self._attack_vec = self._info_vec

        # this wasn't asked for; but we could also track things like
        # detect history, utility history, etc, if any of that might be
        # useful for determining future actions
        self._defend_vec = np.zeros((self._num_turns,), int)

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
                # is detected_vec useful for this?
                #return available_actions(player, self._SOME_STATE)
                return self.legal_attack_actions()
            case Players.DEFENDER:
                # is detected_vec useful for this?
                #return available_actions(player, self._SOME_STATE)
                return self.legal_defend_actions()
            case _:
                raise ValueError(f"undefined player: {player}")

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

        self._attack_vec[self._curr_turn - 1] = attacker_action
        self._defend_vec[self._curr_turn - 1] = defender_action

        def _resolve_with_logic():
            # I can see this getting complicated as the number of
            # available actions grows
            detected = False
            breached = False
            if attacker_action: # not WAIT
                if defender_action: # not WAIT
                    if defender_action is Actions.DETECT_STRONG:
                        detected = True
                    elif attacker_action is Actions.ADVANCE_NOISY:
                        detected = True
                    breached = not detected
                else:
                    breached = True
            return detected, breached

        def _resolve_with_lookup():
            detected = False
            breached = False
            result = _detect_table[
                _action_idx[defender_action],
                _action_idx[attacker_action]]
            if result > 0:
                detected = True
            elif not result:
                breached = False
            return detected, breached

        detected, breached = _resolve_with_lookup()

        # WAIT still needs to be passed in since there might be
        # consequences; these methods are what handle the metting out of
        # utilities
        self._attacker = \
                self.attacker_state.advance(attacker_action, detected)
        self._defender = \
                self.defender_state.detect(defender_action, breached)

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
        player_str = ["Attacker", "Defender"][player]
        action_str = ["WAIT", "ADVANCE_NOISY", "ADVANCE_CAMO",
                      "DEFEND_WEAK", "DEFEND_STRONG"][action]
        return f"{player_str}: {action_str}"

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

    ### some overrides that make playthrough history strings look better

    def history_str(self):
        # in spiel.h this still uses history(), only there for
        # backwards-compatibility reasons, which only returns actions
        return ', '.join(
            f"({x.player}, {x.action})" for x in self.full_history())

    ### The folowing methods are custom and not part of the API

    def legal_attack_actions(self):
        # Things we have to play with here for determining next actions:
        #
        #   - IV (attack_vec)
        #   - current turn (position in the vector)
        #   - we could track utility history also
        # 
        # If we want to make determinations based on future action
        # chains, probabilities, etc, we need to build a wrapper around
        # this game that explores the tree -- we probably need a
        # wrapper anyway.

        return _attack_actions

    def legal_defend_actions(self):
        # Things we have to play with here for determining next action:
        #
        #   - defend_vec (I'm tracking it here, but we don't have to)
        #   - current turn (position in the vector)
        #   - we could track detections (and for strong detect whether
        #     it detected a noisy or camo attack)
        #   - we could track utility history also
        #
        # This logic will probably end up living into a wrapper(s) when
        # probabability distributions, etc, enter the picture.

        return _defend_actions


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
        self, state: V2GameState, player: int
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


class V2Game(pyspiel.Game):
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
        return V2GameState(self, self.game_info)

    def make_py_observer(self, iig_obs_type=None, params=None):
        """
        Create an observer object of type `iig_obs_type`, configured
        using `params`.

        In this simple example, only one type of Observer exists, and
        it isn't configurable, so both input arguments are ignored.
        """
        match iig_obs_type:
            case _:
                return OmniscientObserver(params)


pyspiel.register_game(_GAME_TYPE, V2Game)
