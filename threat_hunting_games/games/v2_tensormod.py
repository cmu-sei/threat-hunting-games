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

from . import arena_v2 as arena

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

game_name = "chain_game_tensormod_v2"
game_turns = 2

_GAME_TYPE = pyspiel.GameType(
    short_name=game_name,
    long_name="Chain game tensormod version 2",
    dynamics=pyspiel.GameType.Dynamics.SIMULTANEOUS,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    # The other option here is REWARDS, which supports model-based
    # Markov decision processes. (See spiel.h)
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    # Note again: num_players doesn't count Chance
    max_num_players=len(arena.Players),
    min_num_players=len(arena.Players),
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
        "num_turns": game_turns,
    }
)


def make_game_info(num_turns):
    # The most expensive strategy is for D to always wait while A
    # always advances. An advance is worth 2 to A and -2 to D, so the
    # minimum utility is for D, and it's -2 * num_turns
    min_utility = -(arena.max_cost() + arena.max_penalty()) * num_turns
    # Max utility is for A to always advance while D defends. A spends
    # 1 to get 2 (or 2 to get 3 for stealth), for a net utility of 1
    # each turn. Hence:
    max_utility = arena.max_reward() * num_turns

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
        num_players=len(arena.Players),
        min_utility=float(min_utility),
        max_utility=float(max_utility),
        utility_sum=0.0,
        max_game_length=num_turns,
    )


class AttackerState(NamedTuple):
    """foo"""

    pos: int
    utility: int
    last_reward: int

    def advance(self, action: arena.Actions, detected: bool) -> "AttackerState":

        #print("ATTACK old_utility:", self.utility)

        utils = arena.utilities[action]

        new_utility = self.utility - utils.cost
        new_state = self.pos

        if action and not detected:
            # If successful, the attacker advances to a new state and
            # gets 2 utility
            new_utility += utils.reward
            # (Assuming an infinite-length, uniform-value state chain,
            # which is silly but simple.)
            new_state += 1

        reward = new_utility - self.utility

        #print("ATTACK new_utility:", new_utility)

        # pylint: disable=no-member
        return self._replace(
            pos=new_state,
            utility=new_utility,
            last_reward=reward,
        )


class DefenderState(NamedTuple):
    utility: int
    last_reward: int

    def detect(self, action: arena.Actions, breached: bool) -> "DefenderState":

        #print("DEFEND old_utility:", self.utility)

        utils = arena.utilities[action]

        new_utility = self.utility - utils.cost

        if breached:
            new_utility -= utils.penalty

        reward = new_utility - self.utility

        #print("DEFEND new_utility:", new_utility)

        # pylint: disable=no-member
        return self._replace(
            utility=new_utility,
            last_reward=reward
        )


# pylint: disable=too-few-public-methods
class V2GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info):
        super().__init__(game)
        self._num_turns = game_info.max_game_length
        self._curr_turn = 0
        self._attacker = AttackerState(0, 0, 0)
        self._defender = DefenderState(0, 0)

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
            case arena.Players.ATTACKER:
                return arena.Attack_Actions
            case arena.Players.DEFENDER:
                return arena.Defend_Actions
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

        #print("apply_actions, curr turn:", self._curr_turn)

        attacker_action = actions[arena.Players.ATTACKER]
        defender_action = actions[arena.Players.DEFENDER]

        self._attack_vec[self._curr_turn] = attacker_action
        self._defend_vec[self._curr_turn] = defender_action
        #print(f"attack_vec({self._curr_turn}):", self._attack_vec)
        #print(f"defend_vec:({self._curr_turn})", self._defend_vec)

        def _resolve_with_logic():
            # I can see this getting complicated as the number of
            # available actions grows
            detected = False
            breached = False
            if attacker_action: # not WAIT
                if defender_action: # not WAIT
                    if defender_action is arena.Actions.DETECT_STRONG:
                        detected = True
                    elif attacker_action is arena.Actions.ADVANCE_NOISY:
                        detected = True
                    breached = not detected
                else:
                    breached = True
            return detected, breached

        def _resolve_with_lookup():
            detected = False
            breached = False
            if arena.action_cmp(attacker_action, defender_action) is False:
                detected = True
            if arena.action_cmp(defender_action, attacker_action) is False:
                breached = True
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
        player_str = arena.player_to_string(player)
        action_str = arena.action_to_string(action)
        return f"{player_str}: {action_str}"

    def is_terminal(self):
        """Return True if the game is over."""
        return self._game_over

    def rewards(self):
        """Total reward for each player over the course of the game so
        far."""
        return [self._attacker.last_reward, self._defender.last_reward]

    def returns(self):
        return [self._attacker.utility, self._defender.utility]

    def __str__(self):
        """String for debugging. No particular semantics."""
        return f"Attacker pos at Turn {self._curr_turn}: {self._attacker.pos}"

    ### The folowing methods are custom and not part of the API

    def legal_Attack_Actions(self):
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

        return arena.Attack_Actions

    def legal_Defend_Actions(self):
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

        return arena.Defend_Actions


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

        #print("OBS PARAMS:", params)
        #num_turns = params["num_turns"]

        # include turn 0
        num_turns = game_turns + 1

        turn_map_size = num_turns * len(arena.Actions)
        util_size = num_turns
        player_size = turn_map_size + util_size
        # include attacker_pos
        attacker_pos_size = num_turns
        total_size = (2 * player_size) + attacker_pos_size
        self.tensor = np.zeros(total_size, int)

        self.dict = {}
        idx = 0
        action_size = len(arena.Players) * num_turns * len(arena.Actions)
        action_shape = (len(arena.Players), num_turns, len(arena.Actions))
        self.dict["action"] = \
            self.tensor[idx:idx+action_size].reshape(action_shape)
        idx += action_size
        utility_size = len(arena.Players) * num_turns
        utility_shape = (len(arena.Players), num_turns)
        self.dict["utility"] = \
            self.tensor[idx:idx+utility_size].reshape(utility_shape)
        idx += utility_size
        self.dict["pos"] = self.tensor[idx:]

        #print("NEW TENSOR")
        #self.tensor = np.zeros((3,), int)

        ### find out what player gets passed into set_from (it's 1/0)

        # algorithms.generate_playthrough, at least, expects
        # be here (can be empty...this is based on BoardObserver in
        # games/tic_tac_toe.py):
        #self.dict = {"observation": self.tensor}

    def set_from(
        self, state: V2GameState, player: int
    ):  # pylint: disable=unused-argument
        """
        Update the observer state to reflect `state` from the POV
        of `player`.

        This is an omniscient observation, so the info will be the same
        for all players.
        """
        print("set_from() here, turn/player:", state._curr_turn, player)
        # Tensor values: attacker position, attacker utility, defender utility
        #self.tensor[0] = state.attacker_state.pos
        #self.tensor[1] = state.attacker_state.utility
        #self.tensor[2] = state.defender_state.utility

        if player == arena.Players.ATTACKER:
            inner_state = state.attacker_state
            action = state._attack_vec[-1]
            print("attack action:", action)
        elif player == arena.Players.DEFENDER:
            inner_state = state.defender_state
            action = state._defend_vec[-1]
            print("defend action:", action)
        self.dict["action"][player, state._curr_turn, action] = action
        self.dict["utility"][player, state._curr_turn] = inner_state.utility
        self.dict["pos"][state._curr_turn] = state.attacker_state.pos
        print(f"SET ACTION ({player}):", self.dict["action"][player])
        print(f"SET UTILITY ({player}):", self.dict["utility"][player])

    def string_from(self, state, player):  # pylint: disable=unused-argument
        """
        Return a string representation of the state updated in
        `state_from`.
        """
        # These are concatenated into a single string. The f prefix is
        # unnecessary for all but the first, but it makes the syntax
        # highlighting work better in Emacs. :)
        turn = state._curr_turn
        utility = self.dict["utility"]
        pos = self.dict["pos"]

        return (
            #f"Attacker position: {self.tensor[0]} | "
            #f"Attacker Utility: {self.tensor[1]} | "
            #f"Defender Utility: {self.tensor[2]}"
            f"Attacker position: {pos[turn]} | "
            f"Attacker Utility: {utility[arena.Players.ATTACKER][turn]} | "
            f"Defender Utility: {utility[arena.Players.DEFENDER][turn]}"
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
        #print("MAKE OBS:", params)
        match iig_obs_type:
            case _:
                return OmniscientObserver(params)


pyspiel.register_game(_GAME_TYPE, V2Game)
