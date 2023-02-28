"""
Model of version 2 of the threat hunt statechain game.
"""

# pylint: disable=c-extension-no-member missing-class-docstring missing-function-docstring

import sys

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum
import pyspiel  # type: ignore
import numpy as np

from absl import logging
from absl.logging import debug
#logging.set_verbosity(logging.DEBUG)

from . import arena_v3 as arena

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

game_name = "chain_game_v2_seq_lockbit"
game_turns = 30

_GAME_TYPE = pyspiel.GameType(
    short_name=game_name,
    long_name="Chain game version 3 Sequential LockBit",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
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


def make_game_info(num_turns: int) -> pyspiel.GameInfo:
    # The most expensive strategy is for D to always wait while A
    # always advances. An advance is worth 2 to A and -2 to D, so the
    # minimum utility is for D, and it's -2 * num_turns
    min_utility = arena.min_utility() * num_turns
    # Max utility is for A to always advance while D defends. A spends
    # 1 to get 2 (or 2 to get 3 for stealth), for a net utility of 1
    # each turn. Hence:
    max_utility = arena.max_utility() * num_turns

    # Arguments to pyspiel.GameInfo:
    # (num_distinct_actions: int,
    #  max_chance_outcomes: int,
    #  num_players: int,
    #  min_utility: float,
    #  max_utility: float,
    #  utility_sum: float = 0,
    #  max_game_length: int)

    return pyspiel.GameInfo(
        num_distinct_actions=len(arena.Actions),
        max_chance_outcomes=0,
        num_players=2,
        min_utility=float(min_utility),
        max_utility=float(max_utility),
        utility_sum=0.0,
        max_game_length=num_turns,
    )


class InProgress():
    """
    For the given action indicate the remaining number of IN_PROGRESS
    actions to take before finalizing the effect of the given action.
    """

    # these get replaced by instance vars in set()
    _action = None
    _turns = 0
    _succeeded = None

    def __init__(self, action=None, turns=0, succeeded=None):
        self.set(action, turns, succeeded)

    @property
    def action(self):
        return self._action

    @property
    def turns(self):
        return self._turns

    @property
    def succeeded(self):
        return self._succeeded

    def take_turn(self):
        self._turns -= 1

    def set(self, action, turn_cnt, succeeded=None):
        self._action = action
        self._turns = turn_cnt
        if action:
            if succeeded is None:
                self._succeeded = arena.action_succeeded(action)
            else:
                self._succeeded = succeeded
        else:
            self._succeeded = None

    def reset(self):
        self.set(None, 0)

    def copy(self):
        return InProgress(self.action, self.turns, self.succeeded)

    def __str__(self):
        return f"[ turn: {self.turns} action: {self.action} ]"


class AttackerState(NamedTuple):
    """foo"""
    state_pos: int
    utility: int
    full_history: list[tuple[arena.Actions, InProgress]]
    available_actions: list[arena.Actions]
    progress: InProgress
    costs: list[int]
    rewards: list[int]
    damages: list[int]

    _avail_actions_by_pos = tuple([
        [
          # pos 0
          arena.Actions.WAIT,
          arena.Actions.S0_VERIFY_PRIV,
          arena.Actions.S0_VERIFY_PRIV_CAMO,
        ],
        [
          # pos 1
          arena.Actions.WAIT,
          arena.Actions.S1_WRITE_EXE,
          arena.Actions.S1_WRITE_EXE_CAMO,
        ],
        [
          # pos 2
          arena.Actions.WAIT,
          arena.Actions.S2_ENCRYPT,
          arena.Actions.S2_ENCRYPT_CAMO,
        ],
    ])

    @property
    def history(self) -> arena.Actions|None:
        if self.full_history:
            return (x[0] for x in self.full_history)
        else:
            return []

    @property
    def asserted_history(self) -> tuple[arena.Actions]:
        return (x[0] for x in self.history if x[0] not in arena.NoOp_Actions)

    @property
    def full_asserted_history(self) -> tuple[arena.Actions]:
        return (x for x in self.full_history
                if x[0] not in arena.NoOp_Actions)

    @property
    def last_action(self) -> arena.Actions|None:
        last = None
        if self.full_history:
            *_, last = self.history
        return last

    @property
    def last_full_action(self) -> arena.Actions|None:
        return self.full_history[-1] if self.full_history else None

    @property
    def last_asserted_action(self) -> arena.Actions|None:
        last = None
        if self.full_history:
            *_, last = self.asserted_history
        return last

    @property
    def last_full_asserted_action(self) -> arena.Actions|None:
        last = None
        if self.full_history:
            *_, last = self.full_asserted_history
        return last

    @property
    def last_reward(self) -> int|None:
        return self.rewards[-1] if self.rewards else 0

    @property
    def got_all_the_marbles(self):
        return self.state_pos == len(self._avail_actions_by_pos)

    def advance(self, action: arena.Actions) -> "AttackerState":

        if not self.available_actions:
            self.available_actions[:] = \
                    self._avail_actions_by_pos[self.state_pos]

        utils = arena.Utilities[action]
        new_pos = self.state_pos
        new_utility = self.utility

        # pay the cost immediately no matter which action this is
        new_utility -= utils.cost

        self.costs.append(-utils.cost)
        self.rewards.append(0)
        self.damages.append(0)

        if action == arena.Actions.IN_PROGRESS:
            # still in progress sequence
            #print(f"attack progress: {self.progress}")
            self.progress.take_turn()
            if self.progress.turns <= 0:
                # tally action -- the delayed source action gets its
                # reward; this reward can potentially be lessened or
                # nullified later by defend action damage if this action
                # is detected. If the action failed there is no reward
                # or advancement.
                if self.progress.succeeded:
                    reward = arena.attack_reward(self.progress.action)
                    new_utility += reward
                    self.rewards[-1] += reward
                    new_pos += 1
                self.progress.reset()
                self.available_actions[:] = arena.Attack_Actions
        else:
            # initiate the sequence of IN_PROGRESS actions (turns can
            # be 0 also, it's a no-op and this current action will be
            # resolved in the IN_PROGRESS block above); available
            # actions are limited to just IN_PROGRESS for turn_cnt
            # turns; this initiating action is not detectable by the
            # defender until the progress turns are complete.
            if self.progress.action:
                raise ValueError(f"stale attacker action: {self.progress}")
            turn_cnt = arena.get_timewait(action).turns()
            self.progress.set(action, turn_cnt)
            self.available_actions[:] = [arena.Actions.IN_PROGRESS]

        self.full_history.append((action, self.progress.copy()))
        return self._replace(state_pos=new_pos, utility=new_utility)

    def tally(self, action: arena.Actions,
            defend_action: arena.Actions) -> "AttackerState":
        # no general failure of last attack action; note that the
        # only conditions where this gets called is down below in
        # GameState._apply_action() is for a non NoOP_Actions and a
        # successful detection of this action but only if this action
        # did not suffer a general failure
        if self.last_action is None:
            raise ValueError("no prior action")
        if self.progress.succeeded:
            # reward has already been tallied when progress/action
            # concluded
            damage = arena.defend_damage(defend_action, action)
            self.damages[-1] -= damage
            return self._replace(utility=(self.utility - damage))
        else:
            return self
        

class DefenderState(NamedTuple):
    utility: int
    full_history: list[arena.Actions]
    available_actions: list[arena.Actions]
    progress: InProgress
    costs: list[int]
    rewards: list[int]
    damages: list[int]

    @property
    def history(self) -> arena.Actions|None:
        return (x[0] for x in self.full_history)

    @property
    def asserted_history(self) -> tuple[arena.Actions]:
        return (x for x in self.history if x not in arena.NoOp_Actions)

    @property
    def full_asserted_history(self) -> tuple[arena.Actions]:
        return (t for t in self.full_history
            if t[0] not in arena.NoOp_Actions)

    @property
    def last_action(self) -> arena.Actions|None:
        last = None
        if self.full_history:
            *_, last = self.history
        return last

    @property
    def last_full_action(self) -> arena.Actions|None:
        return self.full_history[-1] if self.full_history else None

    @property
    def last_asserted_action(self) -> arena.Actions|None:
        last = None
        if self.full_history:
            *_, last = self.asserted_history
        return last

    @property
    def last_full_asserted_action(self) -> arena.Actions|None:
        last = None
        if self.full_history:
            *_, last = self.full_asserted_history
        return last

    @property
    def last_reward(self) -> int|None:
        return self.rewards[-1] if self.rewards else 0

    def detect(self, action: arena.Actions) -> "DefenderState":

        #print("DEFEND old_utility:", self.utility)

        utils = arena.Utilities[action]
        new_utility = self.utility

        # pay the cost immediately no matter which action this is
        new_utility -= utils.cost

        self.costs.append(-utils.cost)
        self.rewards.append(0)
        self.damages.append(0)

        if action == arena.Actions.IN_PROGRESS:
            # still in progress sequence
            #print("defend progress:", self.progress)
            self.progress.take_turn()
            if self.progress.turns <= 0:
                # the delayed defender action does *not* immediately
                # yield a reward -- that happens only with a successful
                # detect action which is determined later in
                # GameState._apply_action()
                self.progress.reset()
                self.available_actions[:] = arena.Defend_Actions
        else:
            # initiate the sequence of IN_PROGRESS actions (turns can
            # be 0 also, it's a no-op and this current action will be
            # resolved in the IN_PROGRESS block above); available
            # actions are limited to just IN_PROGRESS for turn_cnt
            # turns; this initiating action does not (potentially)
            # detect an attacker action until the progress turns are
            # complete.
            if self.progress.action:
                raise ValueError(f"stale defender action: {self.progress}")
            turn_cnt = arena.get_timewait(action).turns()
            self.progress.set(action, turn_cnt)
            self.available_actions[:] = [arena.Actions.IN_PROGRESS]

        self.full_history.append((action, self.progress.copy()))
        return self._replace(utility=new_utility)

    def tally(self, action: arena.Actions,
            attack_action: arena.Actions) -> "DefenderState":
        if self.last_action is None:
            raise ValueError("no prior action")
        if self.progress.succeeded:
            # no general failure of last defend action; the
            # only conditions where this gets called is down below in
            # GameState._apply_action() for this to be a non
            # NoOP_Actions and a successful detection or a confirmed
            # failed detection
            reward = arena.defend_reward(action, attack_action)
            damage = arena.attack_damage(attack_action)
            self.rewards[-1] += reward
            self.damages[-1] -= damage
            return self._replace(utility=(self.utility + reward - damage))
        else:
            return self


# pylint: disable=too-few-public-methods
class GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info):
        super().__init__(game)
        self._num_turns = game_info.max_game_length
        self._curr_turn = 0
        self._attacker = AttackerState(
            state_pos=0, utility=0, full_history=[],
            available_actions=list(arena.Attack_Actions),
            progress=InProgress(), costs=[], rewards=[], damages=[])
        self._defender = DefenderState(
            utility=0, full_history=[],
            available_actions=list(arena.Defend_Actions),
            progress=InProgress(), costs=[], rewards=[], damages=[])

        # attacker always moves first
        self._current_player = arena.Players.ATTACKER

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
        else:
            return self._current_player

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

    def _legal_actions(self, player) -> list[arena.Actions]:
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
        match player:
            case arena.Players.ATTACKER:
                actions = self.attacker_state.available_actions
            case arena.Players.DEFENDER:
                actions = self.defender_state.available_actions
            case _:
                raise ValueError(f"undefined player: {player}")
        #print(f"legal actions for player {player}: {actions}")
        return actions

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

        raise NotImplementedError()

    def _apply_action(self, action):
        """
        Apply the actions of a single player in sequential-move
        games. In all stochastic games, _apply_action is called to
        resolve the actions of the chance player. Not used here, but
        shown for reference.
        """

        #print(f"apply_action, {self.current_player()} turn: {self._curr_turn}")

        # Asserted as invariant in sample games:
        # assert self._is_chance and not self._game_over
        assert not self._game_over

        # Are we done after this turn? We set this here because attacker
        # immediately returns when finished
        self._curr_turn += 1
        if self._curr_turn == self._num_turns:
            print(f"max game length reached, terminating after this turn: {self._curr_turn}")
            self._game_over = True

        if self._current_player is arena.Players.ATTACKER:
            # we *could* deal out damage to the defender here (which
            # would be regained on a successful detect) but it seems
            # more "real" to do that down below when the attack action
            # goes undetected
            self._attacker = self._attacker.advance(action)
            self._attack_vec[self._curr_turn-1] = action
            self._current_player = arena.Players.DEFENDER
            return

        assert(self._current_player is arena.Players.DEFENDER)

        # "action" is now defender action

        # register cost of action, history, initiate IN_PROGRESS
        # sequences, etc
        self._defender = self._defender.detect(action)
        self._defend_vec[self._curr_turn-1] = action

        detected = breached = False
        atk_action = None
        if action not in arena.NoOp_Actions:
            # perform action sweep of attacker history to see if *any*
            # of the attacker's past actions are detected by this
            # defender action
            for (attack_action, result) \
                    in self.attacker_state.full_asserted_history:
                if result.succeeded:
                    # attack action did not suffer a general failure;
                    # now see if it gets detected by this defend action
                    if arena.action_cmp(action, attack_action) is True:
                        # attack action can possibly be detected by the
                        # current defend action
                        if arena.action_succeeded(action, attack_action):
                            # attack action is *actually* detected by
                            # the current defend action; defender gets
                            # reward, attacker takes damage
                            self.defender_state.tally(action, attack_action)
                            self.attacker_state.tally(attack_action, action)
                            detected = True
                            atk_action = attack_action
                        break
        if not detected:
            # if the *last* attack action (only the last, otherwise
            # attacks would potentially yield damage multiple times) was
            # an asserted action (not IN_PROGRESS or WAIT) and goes
            # undetected, met out damage to defender
            attack_action, result = self.attacker_state.last_full_action
            if attack_action not in arena.NoOp_Actions and result.succeeded:
                # attack action did not suffer a general failure;
                # now see if it definitely succeeds against this
                # particular detect action
                if arena.action_succeeded(attack_action, action):
                    # attack action *actually* succeeded against the
                    # current defend action; defender takes damage
                    # (attacker reward has already been tallied)
                    self.defender_state.tally(action, attack_action)
                    breached = True

        self._current_player = arena.Players.ATTACKER

        assert self._curr_turn <= self._num_turns

        # we are done if defender detected attack
        if detected:
            print(f"attack action detected, game over after {self._curr_turn} turns: {arena.action_to_str(action)} detected {arena.action_to_str(atk_action)}")
            self._game_over = True

        # we are done if attacker completed action escalation sequence
        if self.attacker_state.got_all_the_marbles:
            print(f"attack sequence complete, attacker is feeling smug: game over after {self._curr_turn} turns")
            self._game_over = True


    ### Not sure if these methods are required, but they are
    ### implemented in sample games. We should probably do some
    ### logging/error injection to figure this out.

    def _action_to_string(self, player, action):
        """Convert an action to a string representation, presumably
        for logging."""
        player_str = arena.player_to_str(player)
        action_str = arena.action_to_str(action)
        return f"{player_str}: {action_str}"

    def is_terminal(self):
        """Return True if the game is over."""
        return self._game_over

    def rewards(self):
        """Total reward for each player for current turn"""
        return [self._attacker.last_reward, self._defender.last_reward]

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

        #turn_map_size = num_turns * len(arena.Actions)
        turn_map_size = num_turns
        util_size = num_turns
        player_size = turn_map_size + util_size
        total_size = 2 * player_size
        self.tensor = np.zeros(total_size, int)

        self.dict = {}
        idx = 0
        #action_size = len(arena.Players) * num_turns * len(arena.Actions)
        #action_shape = (len(arena.Players), num_turns, len(arena.Actions))
        action_size = len(arena.Players) * num_turns
        action_shape = (len(arena.Players), num_turns)
        self.dict["action"] = \
            self.tensor[idx:idx+action_size].reshape(action_shape)
        idx += action_size
        utility_size = len(arena.Players) * num_turns
        utility_shape = (len(arena.Players), num_turns)
        self.dict["utility"] = \
            self.tensor[idx:idx+utility_size].reshape(utility_shape)

        #print("NEW TENSOR")
        #self.tensor = np.zeros((3,), int)

        ### find out what player gets passed into set_from (it's 1/0)

        # algorithms.generate_playthrough, at least, expects
        # be here (can be empty...this is based on BoardObserver in
        # games/tic_tac_toe.py):
        #self.dict = {"observation": self.tensor}

    def set_from(
        self, state: GameState, player: int
    ):  # pylint: disable=unused-argument
        """
        Update the observer state to reflect `state` from the POV
        of `player`.

        This is an omniscient observation, so the info will be the same
        for all players.
        """
        #print("set_from() here, turn/player:", state._curr_turn, player)
        # Tensor values: attacker position, attacker utility, defender utility
        #self.tensor[0] = state.attacker_state.state_pos
        #self.tensor[1] = state.attacker_state.utility
        #self.tensor[2] = state.defender_state.utility

        if player == arena.Players.ATTACKER:
            inner_state = state.attacker_state
            action = state._attack_vec[-1]
            #print("attack action:", action)
        elif player == arena.Players.DEFENDER:
            inner_state = state.defender_state
            action = state._defend_vec[-1]
            #print("defend action:", action)
        #self.dict["action"][player, state._curr_turn, action] = action
        self.dict["action"][player, state._curr_turn] = action
        self.dict["utility"][player, state._curr_turn] = inner_state.utility
        #print("ACTION:", self.dict["action"])
        #print("UTILITY:", self.dict["action"])
        #print(f"SET ACTION ({player}):", self.dict["action"][player])
        #print(f"SET UTILITY ({player}):", self.dict["utility"][player])

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
        return (
            #f"Attacker position: {self.tensor[0]} | "
            #f"Attacker Utility: {self.tensor[1]} | "
            #f"Defender Utility: {self.tensor[2]}"
            f"Attacker position: {turn} | "
            f"Attacker Utility: {utility[arena.Players.ATTACKER][turn]} | "
            f"Defender Utility: {utility[arena.Players.DEFENDER][turn]}"
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

    def new_initial_state(self):
        """Return a new GameState object"""
        return GameState(self, self.game_info)

    def make_py_observer(self, iig_obs_type=None, params=None):
        return OmniscientObserver(params)

    def _make_py_observer(self, iig_obs_type=None, params=None):
        """
        Create an observer object of type `iig_obs_type`, configured
        using `params`.
        """
        if ((iig_obs_type is None) or
                (iig_obs_type.public_info and not iig_obs_type.perfect_recall)):
            return OmniscientObserver(params)
        else:
            return IIGObserverForPublicInfoGame(iig_obs_type, params)


pyspiel.register_game(_GAME_TYPE, Game)
