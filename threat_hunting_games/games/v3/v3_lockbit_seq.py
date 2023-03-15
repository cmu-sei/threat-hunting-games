"""
Model of version 2 of the threat hunt statechain game.
"""

# pylint: disable=c-extension-no-member missing-class-docstring missing-function-docstring

import sys

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum
from dataclasses import dataclass
import pyspiel  # type: ignore
import numpy as np

from absl import logging
from absl.logging import debug
#logging.set_verbosity(logging.DEBUG)

from . import arena_v3 as arena

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
game_long_name = "Chain game version 3 Sequential LockBit"
game_max_turns = 30
num_players = len(arena.Players)

_GAME_TYPE = pyspiel.GameType(
    short_name=game_name,
    long_name=game_long_name,
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
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
        num_players=num_players,
        min_utility=float(min_utility),
        max_utility=float(max_utility),
        utility_sum=0.0,
        max_game_length=game_max_turns,
    )


@dataclass
class ActionState:
    """
    Class for storing a particular (non IN_PDROGRESS) action along with
    some meta-information -- used for storing action histories within
    AttackerState and DefenderState.
    """
    action: arena.Actions|None = None
    from_turn: int|None = None
    turns_remaining: int = 0
    initial_turns: int = 0
    faulty: bool|None = None
    expended: bool|None = None

    @property
    def in_progress(self):
        # even faulty actions have to complete their progress sequence
        return self.turns_remaining > 0

    @property
    def completed(self) -> bool:
        return not self.in_progress

    @property
    def was_delayed(self):
        return bool(self.initial_turns)

    @property
    def active(self):
        return not self.in_progress and not self.faulty and not self.expended

    def take_turn(self):
        assert self.in_progress, "no turns to take"
        self.turns_remaining -= 1

    def set_turns(self, turns: int):
        assert turns >= 0, "turn count must be >= 0"
        assert turns <= arena.get_timewait(self.action).max, \
                f"turn count for {arena.a2s(self.action)} must be <= {arena.get_timewait(self.action).max}: {turns}"
        self.initial_turns = turns
        self.turns_remaining = turns

    def expend(self):
        self.expended = True

    def __str__(self):
        return f"[ from turn: {self.from_turn} turns left: {self.turns_remaining} action: {arena.a2s(self.action)} ]"


@dataclass
class BasePlayerState:
    """
    Common properties/methods shared between AttackerState and
    DefenderState. Note that "completed" means any action exluding
    IN_PROGRESS and excluding the last action if it is still in
    progress. And "asserted" means the same thing but includes the last
    action even if it is still in progress.
    """
    utility: int = 0
    history: tuple[ActionState] = ()
    available_actions: tuple[arena.Actions] = ()
    costs: tuple[int] = ()
    rewards: tuple[int] = ()
    damages: tuple[int] = ()
    curr_turn: int = 0
    player: str = None

    @property
    def asserted_history(self) -> tuple[ActionState]:
        # Return all ActionStates excluding IN_PROGRESS actions,
        # including the last state even if it is still in progress.
        history = self.history if self.history else []
        return (x for x in history if x.action != arena.Actions.IN_PROGRESS)

    @property
    def completed_history(self) -> tuple[ActionState]:
        # Return all ActionStates excluding IN_PROGRESS actions. Also
        # exclude the last non-IN_PROGRESS ActionState if it is still in
        # progress.
        if self.history and \
                self.history[-1].action == arena.Actions.IN_PROGRESS:
            history = list(self.history)
            while history and \
                    (history[-1].action == arena.Actions.IN_PROGRESS
                            or history[-1].in_progress):
                history.pop()
        else:
            history = self.history
        return (x for x in history if x.action != arena.Actions.IN_PROGRESS)

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
                    if last.action != arena.Actions.IN_PROGRESS:
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
                    if last.action != arena.Actions.IN_PROGRESS \
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
    def last_reward(self) -> int|None:
        return self.rewards[-1] if self.rewards else 0

    @property
    def last_damage(self) -> int|None:
        return self.damages[-1] if self.damages else 0

    def record_action(self, action: arena.Actions):
        # create action_state, maintain history
        if action in arena.NoOp_Actions:
            # no-op actions are never faulty
            action_state = ActionState(action,
                    self.curr_turn, faulty=False)
        else:
            # but completed actions can be faulty
            action_state = ActionState(action, self.curr_turn)
        self.history += (action_state,)
        self.costs += (0,)
        self.rewards += (0,)
        self.damages += (0,)

    def _increment_tuple(self, t, inc):
        # dataclass doesn't allow mutable (list) fields (even though you
        # can assign entirely new values to fields)
        return t[:-1] + (t[-1] + inc,)

    def increment_cost(self, inc):
        inc = abs(inc)
        self.costs = self._increment_tuple(self.costs, inc)
        self.utility -= inc

    def increment_reward(self, inc):
        inc = abs(inc)
        self.rewards = self._increment_tuple(self.rewards, inc)
        self.utility += inc

    def increment_damage(self, inc):
        inc = abs(inc)
        self.damages = self._increment_tuple(self.damages, inc)
        self.utility -= inc


@dataclass
class AttackerState(BasePlayerState):
    """
    Track all state and history for the attacker. Adds one more field to
    BaseState: state_pos, which tracks the advancement steps/stages of
    an attack sequence.
    """
    available_actions: tuple[arena.Actions] = arena.Atk_Actions_By_Pos[0]
    state_pos: int = 0
    player: str = arena.player_to_str(arena.Players.ATTACKER)

    @property
    def got_all_the_marbles(self):
        """
        Final attack stage has been successfully completed.
        """
        return self.state_pos == len(arena.Atk_Actions_By_Pos)

    def advance(self, action: arena.Actions):
        """
        Attacker attempts to make their move.
        """

        self.curr_turn = 2 * len(self.history) + 1

        self.record_action(action)

        if not self.available_actions:
            self.available_actions = arena.Atk_Actions_By_Pos[self.state_pos]

        if action != arena.Actions.IN_PROGRESS:
            print(f"{self.player} (turn {self.curr_turn}): selected {arena.a2s(action)}")

        utils = arena.Utilities[action]

        # pay the cost immediately no matter which action this is
        self.utility -= utils.cost

        self.costs += (-utils.cost,)
        self.rewards += (0,)
        self.damages += (0,)

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
                    print(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: faulty execution, {self.player} stays at position {self.state_pos}")
            else:
                if self.state.was_delayed:
                    self.state_pos += 1
                    print(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: executed, {self.player} advance to position {self.state_pos}")
            if self.state_pos >= len(arena.Atk_Actions_By_Pos):
                self.available_actions = ()
            else:
                self.available_actions = \
                        arena.Atk_Actions_By_Pos[self.state_pos]

        if action == arena.Actions.IN_PROGRESS:
            # still in the progress sequence of a completed action;
            # possibly conclude that action and reset available actions
            self.last_asserted_state.take_turn()
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
            turn_cnt = arena.get_timewait(action).rand_turns()
            self.last_asserted_state.set_turns(turn_cnt)
            if self.last_asserted_state.completed:
                # don't currently have any actions besides WAIT that
                # have turn_cnt == 0, but there could be if there are
                # timewaits defined with 0 as max/min.
                _resolve_action()
            else:
                self.available_actions = (arena.Actions.IN_PROGRESS,)
                print(f"{self.player} (turn {self.curr_turn}): will resolve {arena.a2s(action)} in turn {self.curr_turn + 2*turn_cnt} after {turn_cnt} {arena.a2s(arena.Actions.IN_PROGRESS)} actions")


@dataclass
class DefenderState(BasePlayerState):
    """
    Track all state and history for the defender.
    """
    available_actions: tuple[arena.Actions] = arena.Defend_Actions
    player: str = arena.player_to_str(arena.Players.DEFENDER)

    def detect(self, action: arena.Actions):

        if not self.available_actions:
            self.available_actions = arena.Defend_Actions

        # +2 because defender always moves second
        self.curr_turn = 2 * len(self.history) + 2

        self.record_action(action)

        if action != arena.Actions.IN_PROGRESS:
            print(f"{self.player} (turn {self.curr_turn}): selected {arena.a2s(action)}")

        utils = arena.Utilities[action]

        # pay the cost immediately no matter which action this is
        self.utility -= utils.cost

        self.costs += (-utils.cost,)
        self.rewards += (0,)
        self.damages += (0,)

        def _resolve_action():
            # the defender action does *not* immediately yield a reward
            # -- that happens only with a successful detect action which
            # is determined later in GameState._apply_action()
            if self.state.faulty:
                if self.state.was_delayed:
                    # action suffered a general failure at outset
                    print(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: faulty execution")
            else:
                if self.state.was_delayed:
                    print(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: executed")
            # back to all defend actions available
            self.available_actions = arena.Defend_Actions

        if action == arena.Actions.IN_PROGRESS:
            # still in progress sequence
            #print("defend progress:", self.progress)
            self.last_asserted_state.take_turn()
            if self.last_asserted_state.completed:
                _resolve_action()
                self.available_actions = arena.Defend_Actions
        else:
            # initiate the sequence of IN_PROGRESS actions (turns can be
            # 0 also, it's a no-op and this current action will be
            # resolved in the IN_PROGRESS block above); available
            # actions are limited to just IN_PROGRESS for turn_cnt
            # turns; this initiating action does not (potentially)
            # detect an attacker action until the progress turns are
            # complete.
            turn_cnt = arena.get_timewait(action).rand_turns()
            self.last_asserted_state.set_turns(turn_cnt)
            if self.last_asserted_state.completed:
                # don't currently have any actions besides WAIT that
                # have turn_cnt == 0
                _resolve_action()
            else:
                # limit actions to just IN_PROGRESS for turn_cnt turns
                self.available_actions = (arena.Actions.IN_PROGRESS,)
                print(f"{self.player} (turn {self.curr_turn}): will resolve {arena.a2s(action)} in turn {self.curr_turn + 2*turn_cnt} after {turn_cnt} {arena.a2s(arena.Actions.IN_PROGRESS)} actions")


# pylint: disable=too-few-public-methods
class GameState(pyspiel.State):
    """Game state, and also action resolution for some reason."""

    def __init__(self, game, game_info):
        super().__init__(game)
        assert not (game_info.max_game_length % 2), \
            "game length must have even number of turns"
        self._num_turns = game_info.max_game_length
        self._curr_turn = 0
        # _turns_seen is just for display purposes in _legal_actions()
        self._turns_seen = set()
        # GameState._legal_actions gets called before available actions
        # can be popuated in AttackerState and DefenderState...so
        # initiaize available actions here.
        self._attacker = AttackerState()
        self._defender = DefenderState()
        #self._attacker = \
        #        AttackerState(available_actions=arena.Atk_Actions_By_Pos[0])
        #self._defender = \
        #        DefenderState(available_actions=arena.Defend_Actions)
        #self._turns_seen = set()

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
        if not (actions and actions[0] == arena.Actions.IN_PROGRESS) \
                and self._curr_turn not in self._turns_seen:
            print(f"\n{arena.player_to_str(self.current_player())} (turn {self._curr_turn+1}): legal actions: {', '.join([arena.a2s(x) for x in actions])}")
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

        #if action != arena.Actions.IN_PROGRESS:
        #    print(f"{arena.player_to_str(self.current_player())}: apply action {arena.a2s(action)} now in turn {self._curr_turn+1}")

        # Asserted as invariant in sample games:
        # assert self._is_chance and not self._game_over
        assert not self._game_over

        # convert from int to actual Action
        action = arena.Actions(action)

        # _curr_turn is 0-based; this value is for display purposes
        dsp_turn = self._curr_turn + 1

        if self._current_player is arena.Players.ATTACKER:
            # Do not terminate game here for completed action sequence,
            # defender still has a chance to detect. Game will not
            # terminate here by reaching self._num_turns either because
            # defender always gets the last action.
            self._attacker.advance(action)
            cost = arena.action_cost(action)
            self._attacker.increment_cost(cost)

            self._attack_vec[self._curr_turn] = action

            self._current_player = arena.Players.DEFENDER
            self._curr_turn += 1

            # attacker turn complete
            return

        assert(self._current_player is arena.Players.DEFENDER)

        # "action" is now defender action

        # register cost of action, add to history, initiate IN_PROGRESS
        # sequences, etc
        self._defender.detect(action)
        self._defend_vec[self._curr_turn] = action

        self._defender.increment_cost(action)

        if self._attacker.state.active:
            reward = arena.attack_reward(self._attacker.state.action)
            damage = arena.attack_damage(self._attacker.state.action)
            self._attacker.increment_reward(reward)
            self._defender.increment_damage(damage)
            self._attacker.state.expend()

        # All completed attack action states -- does not include last
        # state if it is still in progress.
        attack_action_states = \
                list(self.attacker_state.completed_history)

        detected = False
        atk_action = None
        #if action == arena.Actions.IN_PROGRESS \
        #        and self.defender_state.state.completed \
        #        and attack_action_states:
        if self._defender.state.active and attack_action_states:
            defend_action = self.defender_state.state.action
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
                if arena.action_succeeds(defend_action, attack_action):
                    # attack action is *actually* detected by the
                    # current defend action; defender gets reward,
                    # attacker takes damage
                    reward = arena.defend_reward(defend_action, attack_action)
                    damage = arena.defend_damage(defend_action, attack_action)
                    self._defender.increment_reward(reward)
                    self._attacker.increment_damage(damage)
                    detected = True
                    atk_action = attack_action
                    break
                else:
                    # note that if the detection *could have*
                    # detected the attack action, but failed, we
                    # continue sweeping the attack action history.
                    pass
        self.defender_state.state.expend()

        self._current_player = arena.Players.ATTACKER

        # self._curr_turn is 0 based
        assert self._curr_turn < self._num_turns

        if detected:
            # we are done if defender detected attack
            print(f"\nattack action detected, game over after {dsp_turn} turns: {arena.a2s(action)} detected {arena.a2s(atk_action)}\n")
            self._game_over = True
        elif self.attacker_state.got_all_the_marbles:
            # we are done if attacker completed action escalation sequence
            print(f"\nattacker is feeling smug, attack sequence complete: game over after {dsp_turn} turns\n")
            self._game_over = True

        self._curr_turn += 1

        # Have we reached max game length? Terminate if so.
        if not self._game_over and self._curr_turn >= self._num_turns:
            print(f"\nmax game length reached, terminating game after {dsp_turn} turns\n")
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
        # this does not get called by openspiel...?
        return [self._attacker.last_reward, self._defender.last_reward]

    def returns(self):
        """Total reward for each player over the course of the game so
        far."""
        return [self._attacker.utility, self._defender.utility]

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

        #print("OBS PARAMS:", params)
        #num_turns = params["num_turns"]

        # include turn 0
        num_turns = game_max_turns + 1

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

    def set_from(self, state: GameState, player: int):  # pylint: disable=unused-argument
        """
        Update the observer state to reflect `state` from the POV
        of `player`.

        This is an omniscient observation, so the info will be the same
        for all players.
        """
        #print("set_from() here, turn/player:", state._curr_turn+1, player)
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
        turn = state._curr_turn - 1 # this gets invoked after turn increment
        utility = self.dict["utility"]
        return (
            #f"Attacker position: {self.tensor[0]} | "
            #f"Attacker Utility: {self.tensor[1]} | "
            #f"Defender Utility: {self.tensor[2]}"
            f"Attacker position: {state.attacker_state.state_pos} | "
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
