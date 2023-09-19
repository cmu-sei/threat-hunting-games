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
import pyspiel  # type: ignore
import numpy as np

from absl import logging
#from absl.logging import debug
# this gets reset somewhere mysterious
#logging.set_verbosity(logging.DEBUG)

from threat_hunting_games import games
from . import arena as arena_mod
from . import policies
from .arena import debug

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

USE_ZSUM = False

game_utility = pyspiel.GameType.Utility.ZERO_SUM if USE_ZSUM \
        else pyspiel.GameType.Utility.CONSTANT_SUM


game_name = "chain_game_v6_seq"
game_long_name = \
        "Chain game version 6 Sequential Simple Base Game with Policies"
game_max_turns = 50
#game_max_turns = 8
#game_max_turns = 12
num_players = len(arena_mod.Players)

_GAME_TYPE = pyspiel.GameType(
    short_name=game_name,
    long_name=game_long_name,
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=game_utility,
    # The other option here is REWARDS, which supports model-based
    # Markov decision processes. (See spiel.h)
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    # Note again: num_players doesn't count Chance
    max_num_players=num_players,
    min_num_players=num_players,
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
        "num_turns": game_max_turns,
        "advancement_rewards": arena_mod.Default_Advancement_Rewards,
        "detection_costs": arena_mod.Default_Detection_Costs,
        "use_waits": int(arena_mod.USE_WAITS),
        "use_timewaits": int(arena_mod.USE_TIMEWAITS),
        "use_chance_fail": int(arena_mod.USE_CHANCE_FAIL),
    }
)

def make_game_info(num_turns: int) -> pyspiel.GameInfo:
    # In this constant sum game, each player starts with 30 utility, so
    # max is 60

    # this uses the Utilities defaults, not ideal since they are
    # determined prior to game load.
    #utilities = arena.Utilities()
    #min_utility = utilities.min_utility() * num_turns
    #max_utility = utilities.max_utility() * num_turns

    # Arguments to pyspiel.GameInfo:
    # (num_distinct_actions: int,
    #  max_chance_outcomes: int,
    #  num_players: int,
    #  min_utility: float,
    #  max_utility: float,
    #  utility_sum: float = 0,
    #  max_game_length: int)

    return pyspiel.GameInfo(
        num_distinct_actions=len(arena_mod.Actions),
        max_chance_outcomes=0,
        num_players=num_players,
        #min_utility=float(min_utility),
        #max_utility=float(max_utility),
        # with our game structure these are hard to compute prior to
        # game load, so these are arbitrary values that are nevertheless
        # bounding (probably)
        min_utility=-100,
        max_utility=100,
        utility_sum=0.0,
        max_game_length=num_turns,
    )


@dataclass
class ActionState:
    """
    Class for storing a particular (non IN_PDROGRESS) action along with
    some meta-information -- used for storing action histories within
    AttackerState and DefenderState.
    """
    arena: arena_mod.Arena
    action: arena_mod.Actions|None = None
    from_turn: int|None = None
    turns_remaining: int = 0
    initial_turns: int = 0
    faulty: bool|None = None
    expended: bool|None = None

    @property
    def in_progress(self) -> bool:
        # even faulty actions have to complete their progress sequence
        return self.turns_remaining > 0

    @property
    def completed(self) -> bool:
        return not self.in_progress

    @property
    def was_delayed(self) -> bool:
        return bool(self.initial_turns)

    @property
    def primed(self) -> bool:
        return not self.in_progress and not self.faulty and not self.expended

    def take_turn(self):
        assert self.in_progress, "no turns to take"
        self.turns_remaining -= 1

    def set_turns(self, turns: int):
        assert turns >= 0, "turn count must be >= 0"
        assert turns <= self.arena.get_timewait(self.action).max, \
                f"turn count for {self.arena.a2s(self.action)} must be <= {self.arena.get_timewait(self.action).max}: {turns}"
        self.initial_turns = turns
        self.turns_remaining = turns

    def expend(self):
        self.expended = True

    def __str__(self):
        return f"[ from turn: {self.from_turn} turns left: {self.turns_remaining} action: {self.arena.a2s(self.action)} ]"


@dataclass
class BasePlayerState:
    """
    Common properties/methods shared between AttackerState and
    DefenderState. Note that "completed" means any action exluding
    IN_PROGRESS and excluding the last action if it is still in
    progress. And "asserted" means the same thing but includes the last
    action even if it is still in progress.
    """
    arena: arena_mod.Arena
    utility: int = 0
    history: list[ActionState] = field(default_factory=list)
    available_actions: list[arena_mod.Actions] = field(default_factory=list)
    costs: list[int] = field(default_factory=list)
    rewards: list[int] = field(default_factory=list)
    damages: list[int] = field(default_factory=list)
    utilities: list[int] = field(default_factory=list)
    curr_turn: int = 0
    player_id: int = None
    player: str = None

    @property
    def action_history(self) -> tuple[arena_mod.Actions]:
        return [x.action for x in self.history]

    @property
    def asserted_history(self) -> tuple[ActionState]:
        # Return all ActionStates excluding IN_PROGRESS actions,
        # including the last state even if it is still in progress.
        history = self.history if self.history else []
        return (x for x in history if x.action != \
                self.arena.actions.IN_PROGRESS)

    @property
    def completed_history(self) -> tuple[ActionState]:
        # Return all ActionStates excluding IN_PROGRESS actions. Also
        # exclude the last non-IN_PROGRESS ActionState if it is still in
        # progress.
        if self.history and \
                self.history[-1].action == self.arena.actions.IN_PROGRESS:
            history = list(self.history)
            while history and \
                    (history[-1].action == self.arena.actions.IN_PROGRESS
                            or history[-1].in_progress):
                history.pop()
        else:
            history = self.history
        return (x for x in history if x.action != \
                self.arena.actions.IN_PROGRESS)

    @property
    def last_state(self) -> ActionState|None:
        # Return last ActionState, even if it is the IN_PROGRESS action.
        return self.history[-1] if self.history else None

    @property
    def last_asserted_state(self) -> ActionState|None:
        # Return the just the last ActionState excluding IN_PROGRESS but
        # including the last ActionState if it is still in progress.
        last = None
        if self.history:
            try:
                idx = -1
                while True:
                    last = self.history[idx]
                    idx -= 1
                    if last.action != self.arena.actions.IN_PROGRESS:
                        break
            except IndexError:
                pass
        return last

    @property
    def last_completed_state(self) -> ActionState|None:
        # Return the just the last ActionState excluding IN_PROGRESS and
        # the last ActionState if it is still in progress.
        last = None
        if self.history:
            try:
                idx = -1
                while True:
                    last = self.history[idx]
                    idx -= 1
                    if last.action != self.arena.actions.IN_PROGRESS \
                            and last.completed:
                        break
            except IndexError:
                pass
        return last

    @property
    def state(self) -> ActionState|None:
        # exclude last state if it is still in progress
        return self.last_completed_state

    @property
    def last_cost(self) -> int|None:
        return self.costs[-1] if self.costs else 0

    @property
    def last_reward(self) -> int|None:
        return self.rewards[-1] if self.rewards else 0

    @property
    def last_damage(self) -> int|None:
        return self.damages[-1] if self.damages else 0

    @property
    def last_result(self) -> int|None:
        if self.utilities:
            return self.last_reward - self.last_cost - self.last_damage
        else:
            return 0

    def append_util_histories(self):
        # this has to get called during attack actions for defender
        # since defender gets the cost reward
        self.costs.append(0)
        self.rewards.append(0)
        self.damages.append(0)
        self.utilities.append(0)

    def record_action(self, action: arena_mod.Actions):
        # create action_state, maintain history
        if action in self.arena.noop_actions:
            # no-op actions are never faulty
            action_state = ActionState(self.arena, action,
                    self.curr_turn, faulty=False)
        else:
            # but completed actions can be faulty
            action_state = ActionState(self.arena, action, self.curr_turn)
        self.history.append(action_state)

    def increment_cost(self, inc):
        inc = abs(inc)
        self.costs[-1] -= inc
        self.utility -= inc

    def increment_reward(self, inc):
        inc = abs(inc)
        self.rewards[-1] += inc
        self.utility += inc

    def increment_damage(self, inc):
        # want to return the actual damage in case the increment
        # exceeds remaining utility
        inc = abs(inc)
        #inc = self.utility if inc > self.utility else inc
        self.damages[-1] -= inc
        self.utility -= inc
        return inc

    def record_utility(self):
        self.utilities[-1] = self.utility

    def legal_actions(self):
        raise NotImplementedError()


@dataclass
class AttackerState(BasePlayerState):
    """
    Track all state and history for the attacker. Adds one more field to
    BaseState: state_pos, which tracks the advancement steps/stages of
    an attack sequence.
    """
    state_pos: int = 0
    player_id: int = arena_mod.Players.ATTACKER
    player: str = arena_mod.player_to_str(arena_mod.Players.ATTACKER)

    @property
    def got_all_the_marbles(self):
        """
        Final attack stage has been successfully completed.
        """
        return self.state_pos == len(self.arena.atk_actions_by_pos)

    def increment_pos(self):
        self.state_pos += 1
        self.available_actions = self.legal_actions()

    def legal_actions(self):
        #return [x for x in arena.Atk_Actions_By_Pos[self.state_pos]
        #        if arena.action_cost(x) <= self.utility]
        if self.got_all_the_marbles:
            actions = ()
        else:
            actions = self.arena.atk_actions_by_pos[self.state_pos]
        return actions

    def advance(self, action: arena_mod.Actions, game_state: pyspiel.State):
        """
        Attacker attempts to make their move.
        """

        self.curr_turn = 2 * len(self.history) + 1

        self.record_action(action)

        if not self.available_actions:
            self.available_actions = \
                    self.arena.atk_actions_by_pos[self.state_pos]

        if action != self.arena.actions.IN_PROGRESS:
            debug(f"{self.player} (turn {self.curr_turn}): selected {self.arena.a2s(action)}")

        def _resolve_action():
            # tally action -- the delayed source action gets its reward;
            # this reward can potentially be lessened or nullified later
            # by defend action damage if this action is detected. If the
            # action was faulty there is no reward or advancement.
            assert self.state, "no current action state in ActionState"
            if self.state.faulty:
                # action suffered a general failure determined at
                # the outset
                if self.state.was_delayed:
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {self.arena.a2s(self.state.action)} from turn {self.state.from_turn}: faulty execution, {self.player} stays at position {self.state_pos}")
            elif self.state.was_delayed:
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {self.arena.a2s(self.state.action)} from turn {self.state.from_turn}: executed, {self.player} advances to position {self.state_pos}")
            # back to all attack actions by pos
            #self.available_actions = self.legal_actions()

        if action == self.arena.actions.IN_PROGRESS:
            # still in the progress sequence of a completed action;
            # possibly conclude that action and reset available actions
            if self.last_asserted_state.in_progress:
                self.last_asserted_state.take_turn()
            else:
                debug(f"{self.player} WHOOPS TAKING TURN!")
            if self.last_asserted_state.completed:
                # time to resolve the action that triggered this
                # IN_PROGRESS sequence
                _resolve_action()
        else:
            # initiate the sequence of IN_PROGRESS actions (turns can
            # be 0 also, it's a no-op and this current action will be
            # resolved in the IN_PROGRESS block above); available
            # actions are limited to just IN_PROGRESS for turn_cnt
            # turns; this initiating action is not detectable by the
            # defender until the progress turns are complete.

            # limit actions to just IN_PROGRESS for turn_cnt turns
            turn_cnt = self.arena.get_timewait(action).rand_turns()
            self.last_asserted_state.set_turns(turn_cnt)
            if self.last_asserted_state.completed:
                # don't currently have any actions besides WAIT that
                # have turn_cnt == 0, but there could be if there are
                # timewaits defined with 0 as max/min.
                _resolve_action()
            else:
                self.available_actions = (self.arena.actions.IN_PROGRESS,)
                debug(f"{self.player} (turn {self.curr_turn}): will resolve {self.arena.a2s(action)} in turn {self.curr_turn + 2*turn_cnt} after {turn_cnt} {self.arena.a2s(self.arena.actions.IN_PROGRESS)} actions")


@dataclass
class DefenderState(BasePlayerState):
    """
    Track all state and history for the defender.
    """
    available_actions: list[arena_mod.Actions] = field(default_factory=list)
    player_id: int = arena_mod.Players.DEFENDER
    player: str = arena_mod.player_to_str(arena_mod.Players.DEFENDER)

    def legal_actions(self):
        actions = self.arena.player_actions[self.player_id]
        return actions

    def detect(self, action: arena_mod.Actions, game_state: pyspiel.State):

        if not self.available_actions:
            self.available_actions = self.arena.defend_actions

        # +2 because defender always moves second
        self.curr_turn = 2 * len(self.history) + 2

        self.record_action(action)

        if action != self.arena.actions.IN_PROGRESS:
            debug(f"{self.player} (turn {self.curr_turn}): selected {self.arena.a2s(action)}")

        def _resolve_action():
            # the defender action does *not* immediately yield a reward
            # -- that happens only with a successful detect action which
            # is determined later in GameState._apply_action()
            if self.state.faulty:
                if self.state.was_delayed:
                    # action suffered a general failure at outset
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {self.arena.a2s(self.state.action)} from turn {self.state.from_turn}: faulty execution")
            else:
                if self.state.was_delayed:
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {self.arena.a2s(self.state.action)} from turn {self.state.from_turn}: executed")
            # back to all defend actions available
            self.available_actions = self.legal_actions()

        if action == self.arena.actions.IN_PROGRESS:
            # still in progress sequence
            #debug("defend progress:", self.progress)
            if self.last_asserted_state.in_progress:
                self.last_asserted_state.take_turn()
            else:
                debug(f"{self.player} WHOOPS TAKING TURN!")
            if self.last_asserted_state.completed:
                _resolve_action()
        else:
            # initiate the sequence of IN_PROGRESS actions (turns can be
            # 0 also, it's a no-op and this current action will be
            # resolved in the IN_PROGRESS block above); available
            # actions are limited to just IN_PROGRESS for turn_cnt
            # turns; this initiating action does not (potentially)
            # detect an attacker action until the progress turns are
            # complete.
            turn_cnt = self.arena.get_timewait(action).rand_turns()
            self.last_asserted_state.set_turns(turn_cnt)
            if self.last_asserted_state.completed:
                # don't currently have any actions besides WAIT that
                # have turn_cnt == 0
                _resolve_action()
            else:
                # limit actions to just IN_PROGRESS for turn_cnt turns
                self.available_actions = (self.arena.actions.IN_PROGRESS,)
                debug(f"{self.player} (turn {self.curr_turn}): will resolve {self.arena.a2s(action)} in turn {self.curr_turn + 2*turn_cnt} after {turn_cnt} {self.arena.a2s(self.arena.actions.IN_PROGRESS)} actions")


# pylint: disable=too-few-public-methods
class GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info, game_arena=None):
        assert not (game_info.max_game_length % 2), \
            "game length must have even number of turns"
        super().__init__(game)
        game_params = game.get_parameters()
        self._num_turns = game_params["num_turns"]
        if not game_arena:
            game_arena = arena_mod.Arena(
                    advancement_rewards=game_params["advancement_rewards"],
                    detection_costs=game_params["detection_costs"],
                    use_waits=bool(game_params["use_waits"]),
                    use_timewaits=bool(game_params["use_timewaits"]),
                    use_chance_fail=bool(game_params["use_chance_fail"]))
        self._arena = game_arena
        self._victor = None
        self._curr_turn = 0
        # _turns_seen is just for display purposes in _legal_actions()
        self._turns_seen = set()
        # GameState._legal_actions gets called before available actions
        # can be popuated in AttackerState and DefenderState...so
        # initiaize available actions here.
        self._attacker = AttackerState(arena=self._arena)
        self._defender = DefenderState(arena=self._arena)

        # attacker always moves first
        self._current_player = self._arena.players.ATTACKER

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
    def arena(self):
        return self._arena

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

    def _legal_actions(self, player) -> list[arena_mod.Actions]:
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
            case self._arena.players.ATTACKER:
                actions = self._attacker.available_actions \
                    if self._attacker.available_actions \
                    else self._arena.atk_actions_by_pos[self._attacker.state_pos]
            case self._arena.players.DEFENDER:
                actions = self._defender.available_actions \
                    if self._defender.available_actions \
                    else self._arena.defend_actions
            case _:
                raise ValueError(f"undefined player: {player}")
        if not (actions and \
                list(actions) == [self._arena.actions.IN_PROGRESS]) \
                    and self._curr_turn not in self._turns_seen:
            debug(f"\n{self.arena.p2s(self.current_player())} (turn {self._curr_turn+1}): legal actions: {', '.join([self.arena.a2s(x) for x in actions])}")
            self._turns_seen.add(self._curr_turn)
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

        #if action != self._arena.actions.IN_PROGRESS:
        debug(f"{self._arena.p2s(self.current_player())}: apply action {self._arena.a2s(action)} now in turn {self._curr_turn+1}")
        debug([len(self.history()), self.history()])

        # Asserted as invariant in sample games:
        # assert self._is_chance and not self._game_over
        assert not self._game_over

        # convert from int to actual Action
        action = self._arena.actions(action)

        # _curr_turn is 0-based; this value is for display purposes
        dsp_turn = self._curr_turn + 1

        # some bookeeping to avoid index errors
        self._attacker.append_util_histories()
        self._defender.append_util_histories()

        #debug(self.history_str())
        #debug([self.history()])

        if self._current_player is self._arena.players.ATTACKER:
            # Do not terminate game here for completed action sequence,
            # defender still has a chance to detect. Game will not
            # terminate here by reaching self._num_turns either because
            # defender always gets the last action.
            self._attacker.advance(action, self)
            cost = self._arena.utilities.action_cost(action)
            self._attacker.increment_cost(cost)
            if USE_ZSUM:
                self._defender.increment_reward(cost)

            self._attack_vec[self._curr_turn] = action
            #debug(f"ATTACK({self._curr_turn}): {self._attack_vec}")

            self._current_player = self._arena.players.DEFENDER
            self._curr_turn += 1

            # attacker turn complete
            return

        assert(self._current_player is self._arena.players.DEFENDER)

        # "action" is now defender action

        # register cost of action, add to history, initiate IN_PROGRESS
        # sequences, etc
        self._defender.detect(action, self)

        self._defend_vec[self._curr_turn] = action
        #debug(f"DEFEND({self._curr_turn}): {self._defend_vec}")

        cost = self._arena.utilities.action_cost(action)
        self._defender.increment_cost(cost)
        if USE_ZSUM:
            self._attacker.increment_reward(cost)

        # All completed attack action states -- does not include last
        # state if it is still in progress.
        attack_action_states = list(self._attacker.completed_history)

        detected = False
        atk_action = None
        #if action == self._arena.actions.IN_PROGRESS \
        #        and self._defender.state.completed \
        #        and attack_action_states:
        if self._defender.state.primed and attack_action_states:
            defend_action = self._defender.state.action
            # perform action sweep of attacker history to see if *any*
            # of the attacker's past actions are detected by this
            # defender action.
            for attack_action_state in attack_action_states:
                if attack_action_state.faulty:
                    # attack action suffered a general failure
                    # (determined at outset); faulty actions are not
                    # detectable currently
                    continue
                # attack action was not faulty and is not still in progress
                attack_action = attack_action_state.action
                if self._arena.action_succeeds(defend_action, attack_action):
                    # attack action is *actually* detected by the
                    # current defend action; defender gets reward,
                    # attacker takes damage
                    if self._arena.use_defender_clawback:
                        # it could be interesting for the defender to
                        # regain all of the damage it took up until the
                        # latest attacker stage -- the way these work at
                        # the moment is to regain the damage from just
                        # the attack action that was detected.
                        reward = \
                            self._arena.utilities.defend_reward(defend_action)
                        damage = \
                            self._arena.utilities.defend_damage(defend_action)
                    else:
                        # no damage is regained by defender, no rewards
                        # are lost by attacker
                        reward = 0
                        damage = 0
                    dmg = self._attacker.increment_damage(damage)
                    self._defender.increment_reward(dmg)
                    detected = True
                    # atk_action is merely used for debug
                    # statements below
                    atk_action = attack_action
                    break
                else:
                    # note that if the detection *could have*
                    # detected the attack action, but failed, we
                    # continue sweeping the attack action history.
                    pass
        # this defend action is spent
        self._defender.state.expend()

        if not detected and self._attacker.state.primed:
            # a viable completed attack action that is undetected
            reward = self._arena.utilities.attack_reward(
                    self._attacker.state.action)
            damage = self._arena.utilities.attack_damage(
                    self._attacker.state.action)
            dmg = self._defender.increment_damage(damage)
            self._attacker.increment_reward(dmg)
            if self._attacker.state.action not in self._arena.noop_actions:
                self._attacker.increment_pos()
            self._attacker.state.expend()

        self._defender.record_utility()
        self._attacker.record_utility()

        self._current_player = self._arena.players.ATTACKER

        # self._curr_turn is 0 based
        assert self._curr_turn < self._num_turns

        if detected:
            # we are done if defender detected attack
            debug(f"\nattack action detected, game over after {dsp_turn} turns: {self._arena.a2s(defend_action)} detected {self._arena.a2s(atk_action)}\n")
            self._victor = int(self._arena.players.DEFENDER)
            self._game_over = True
        elif self._attacker.got_all_the_marbles:
            # we are done if attacker completed action escalation sequence
            debug(f"\nattacker is feeling smug, attack sequence complete: game over after {dsp_turn} turns\n")
            self._victor = int(self._arena.players.ATTACKER)
            self._game_over = True

        self._curr_turn += 1

        # Have we reached max game length? Terminate if so.
        if not self._game_over and self._curr_turn >= self._num_turns:
            debug(f"\nmax game length reached, terminating game after {dsp_turn} turns\n")
            self._victor = None
            self._game_over = True

        if self._game_over:
            debug(f"{self.arena.p2s(self.arena.players.DEFENDER)} util history:", self._defender.utilities)
            debug(f"{self.arena.p2s(self.arena.players.ATTACKER)} util history:", self._attacker.utilities)


    ### Not sure if these methods are required, but they are
    ### implemented in sample games. We should probably do some
    ### logging/error injection to figure this out.

    def _action_to_string(self, player, action):
        """Convert an action to a string representation, presumably
        for logging."""
        player_str = self._arena.player_to_str(player)
        action_str = self._arena.action_to_str(action)
        return f"{player_str}: {action_str}"

    def is_terminal(self):
        """Return True if the game is over."""
        return self._game_over

    def rewards(self):
        """Total reward for each player for current turn"""
        # this does not get called by openspiel...?
        return [self._attacker.last_result, self._defender.last_result]

    def returns(self):
        """Total reward for each player over the course of the game so
        far."""
        return [self._attacker.utility, self._defender.utility]

    def turns_played(self):
        """Number of turns played thus far."""
        return self._curr_turn

    def victor(self):
        """
        Only set to the player that made a detection or completed the
        attack sequence.
        """
        return self._victor

    def __str__(self):
        """String for debugging. No particular semantics."""
        return f"Attacker pos at Turn {self._curr_turn+1}: {self._attacker.state_pos}"


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
        hist_size = game_max_turns
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
        #print("\ngame params:\n", self.get_parameters(), "\n")

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
