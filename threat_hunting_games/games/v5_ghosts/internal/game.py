"""
Model of version 2 of the threat hunt statechain game, sequential,
constant sum. (action cost is the opposing players gain)
"""

# pylint: disable=c-extension-no-member missing-class-docstring missing-function-docstring

import sys

from typing import NamedTuple, Mapping, Any, List
from enum import IntEnum
from dataclasses import dataclass, field
import numpy as np

from threat_hunting_games import gameload
from . import arena_zsum as arena
from . import policies
from .arena_zsum import debug

game_name = "chain_game_v5_lb_seq_zsum"
game_long_name = "Chain game version 5 Sequential Zero Sum LockBit with Policies"
game_max_turns = 30
game_max_turns = 8
game_max_turns = 12
num_players = len(arena.Players)


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
    history: list[ActionState] = field(default_factory=list)
    policy: policies.Policy = None
    policy_args: field(default_factory=list) = None
    policy_stash: list[arena.Actions] = field(default_factory=list)
    available_actions: list[arena.Actions] = field(default_factory=list)
    costs: list[int] = field(default_factory=list)
    rewards: list[int] = field(default_factory=list)
    damages: list[int] = field(default_factory=list)
    utilities: list[int] = field(default_factory=list)
    curr_turn: int = 0
    player_id: int = None
    player: str = None

    @property
    def action_history(self) -> tuple[arena.Actions]:
        return [x.action for x in self.history]

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

    def append_util_histories(self):
        # this has to get called during attack actions for defender
        # since defender gets the cost reward
        self.costs.append(0)
        self.rewards.append(0)
        self.damages.append(0)
        self.utilities.append(0)

    def record_action(self, action: arena.Actions):
        # create action_state, maintain history
        if action in arena.NoOp_Actions:
            # no-op actions are never faulty
            action_state = ActionState(action,
                    self.curr_turn, faulty=False)
        else:
            # but completed actions can be faulty
            action_state = ActionState(action, self.curr_turn)
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

    def select_policy_action(self, game_state):
        assert self.policy, "no policy present"
        action_probs = self.policy.action_probabilities(
                game_state, int(self.player_id))
        print("AP ACTIONS:", self.player_id, action_probs)
        action_list = list(action_probs.keys())
        if not action_list:
            print("no action probabilities returned from policy")
            #return pyspiel.INVALID_ACTION
            return None
        psum = sum(action_probs.values())
        if psum:
            if psum != 1.0:
                print(f"scaling probability sums ({psum})")
                for action in action_probs:
                    action_probs[action] *= 1 / psum
        else:
            print("no probability sum")
            scale = 1 / len(action_list)
            action_probs = { x: scale for x in action_list }
        action = np.random.choice(action_list, p=list(action_probs.values()))
        return action

    def restore_actions_from_policy_stash(self):
        assert self.policy_stash, "no policy stash actions present"
        assert self.available_actions != [arena.Actions.IN_PROGRESS], \
                "attempted action restore while IN_PROGRESS"
        self.available_actions = self.policy_stash
        self.policy_stash = []

    def legal_actions(self):
        raise NotImplementedError()


@dataclass
class AttackerState(BasePlayerState):
    """
    Track all state and history for the attacker. Adds one more field to
    BaseState: state_pos, which tracks the advancement steps/stages of
    an attack sequence.
    """
    available_actions: list[arena.Actions] = field(default_factory=list)
    state_pos: int = 0
    player_id: int = arena.Players.ATTACKER
    player: str = arena.player_to_str(arena.Players.ATTACKER)

    @property
    def got_all_the_marbles(self):
        """
        Final attack stage has been successfully completed.
        """
        return self.state_pos == len(arena.Atk_Actions_By_Pos)

    def increment_pos(self):
        self.state_pos += 1

    def legal_actions(self):
        #return [x for x in arena.Atk_Actions_By_Pos[self.state_pos]
        #        if arena.action_cost(x) <= self.utility]
        return arena.Atk_Actions_By_Pos[self.state_pos]

    def advance(self, action: arena.Actions, game_state):
        """
        Attacker attempts to make their move.
        """

        self.curr_turn = 2 * len(self.history) + 1

        self.record_action(action)

        if self.policy and self.policy_stash:
            # embedded policy works by limiting available actions to
            # this current action, so restore action choices if policy
            # is present
            self.restore_actions_from_policy_stash()
        if not self.available_actions:
            self.available_actions = arena.Atk_Actions_By_Pos[self.state_pos]

        if action != arena.Actions.IN_PROGRESS:
            debug(f"{self.player} (turn {self.curr_turn}): selected {arena.a2s(action)}")

        utils = arena.Utilities[action]

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
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: faulty execution, {self.player} stays at position {self.state_pos}")
            elif self.state.was_delayed:
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: executed, {self.player} advances to position {self.state_pos}")
            if self.policy:
                next_action = self.select_policy_action(game_state)
                if next_action:
                    self.policy_stash = self.available_actions
                    self.available_actions = [next_action]
                else:
                    self.available_actions = []
            else:
                self.available_actions = self.legal_actions()

        if action == arena.Actions.IN_PROGRESS:
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
            turn_cnt = arena.get_timewait(action).rand_turns()
            self.last_asserted_state.set_turns(turn_cnt)
            if self.last_asserted_state.completed:
                # don't currently have any actions besides WAIT that
                # have turn_cnt == 0, but there could be if there are
                # timewaits defined with 0 as max/min.
                _resolve_action()
            else:
                self.available_actions = [arena.Actions.IN_PROGRESS]
                debug(f"{self.player} (turn {self.curr_turn}): will resolve {arena.a2s(action)} in turn {self.curr_turn + 2*turn_cnt} after {turn_cnt} {arena.a2s(arena.Actions.IN_PROGRESS)} actions")


@dataclass
class DefenderState(BasePlayerState):
    """
    Track all state and history for the defender.
    """
    available_actions: list[arena.Actions] = field(default_factory=list)
    player_id: int = arena.Players.DEFENDER
    player: str = arena.player_to_str(arena.Players.DEFENDER)

    def legal_actions(self):
        #return [x for x in arena.Defend_Actions
        #        if arena.action_cost(x) <= self.utility]
        return arena.Defend_Actions

    def detect(self, action: arena.Actions, game_state):

        if self.policy and self.policy_stash:
            # embedded policy works by limiting available actions to
            # this current action, so restore action choices if policy
            # is present
            self.restore_actions_from_policy_stash()
        if not self.available_actions:
            self.available_actions = arena.Defend_Actions

        # +2 because defender always moves second
        self.curr_turn = 2 * len(self.history) + 2

        self.record_action(action)

        if action != arena.Actions.IN_PROGRESS:
            debug(f"{self.player} (turn {self.curr_turn}): selected {arena.a2s(action)}")

        utils = arena.Utilities[action]

        def _resolve_action():
            # the defender action does *not* immediately yield a reward
            # -- that happens only with a successful detect action which
            # is determined later in GameState._apply_action()
            if self.state.faulty:
                if self.state.was_delayed:
                    # action suffered a general failure at outset
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: faulty execution")
            else:
                if self.state.was_delayed:
                    debug(f"\n{self.player} (turn {self.curr_turn}): resolved {arena.a2s(self.state.action)} from turn {self.state.from_turn}: executed")
            # back to all defend actions available
            if self.policy:
                next_action = self.select_policy_action(game_state)
                if next_action:
                    self.policy_stash = self.available_actions
                    self.available_actions = [next_action]
                else:
                    self.available_actions = []
            else:
                self.available_actions = self.legal_actions()

        if action == arena.Actions.IN_PROGRESS:
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
            turn_cnt = arena.get_timewait(action).rand_turns()
            self.last_asserted_state.set_turns(turn_cnt)
            if self.last_asserted_state.completed:
                # don't currently have any actions besides WAIT that
                # have turn_cnt == 0
                _resolve_action()
            else:
                # limit actions to just IN_PROGRESS for turn_cnt turns
                self.available_actions = [arena.Actions.IN_PROGRESS]
                debug(f"{self.player} (turn {self.curr_turn}): will resolve {arena.a2s(action)} in turn {self.curr_turn + 2*turn_cnt} after {turn_cnt} {arena.a2s(arena.Actions.IN_PROGRESS)} actions")


class FakeGame:
    """
    Mock game for passing into policies if required.
    """

    def __init__(self, game_params=None):
        self.game_params = game_params or {}

    def get_parameters(self):
        return dict(self.game_params)

    def num_players(self):
        return len(arena.Players)


class GameState:
    """Game state, and also action resolution for some reason."""

    def __init__(self, game_params=None):
        # we do some trickery here with a fake game in order to be able
        # to pass game into a policy if policies are being used (in
        # non-bot mode)
        game = FakeGame(game_params)
        game_params = game.get_parameters()
        self._num_turns = game_params.get("num_turns", game_max_turns)
        assert not (self._num_turns % 2), \
            "game length must have even number of turns"
        self._turns_exhausted = False
        # if policies are None, actions are random choice out of
        # legal actions
        if game_params.get("defender_policy"):
            policy_name = game_params["defender_policy"]
            policy_class = policies.get_policy_class(policy_name)
            policy_args = policies.get_player_policy_args(
                    arena.Players.DEFENDER, policy_name)
            #print("DEFENDER POLICY CLASS:", policy_class)
            #print("DEFENDER POLICY ARGS:", policy_args)
            self._defender_policy = policy_class(game, *policy_args)
        else:
            self._defender_policy = None
        if game_params.get("attacker_policy"):
            policy_name = game_params["attacker_policy"]
            policy_class = policies.get_policy_class(policy_name)
            policy_args = policies.get_player_policy_args(
                    arena.Players.ATTACKER, policy_name)
            #print("ATTACKER POLICY CLASS:", policy_class)
            #print("ATTACKER POLICY ARGS:", policy_args)
            self._attacker_policy = policy_class(game, *policy_args)
        else:
            self._attacker_policy = None
        self._curr_turn = 0
        # _turns_seen is just for display purposes in _legal_actions()
        self._turns_seen = set()
        # GameState._legal_actions gets called before available actions
        # can be popuated in AttackerState and DefenderState...so
        # initiaize available actions here.
        self._attacker = AttackerState(policy=self._attacker_policy)
        self._defender = DefenderState(policy=self._defender_policy)

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
            return None
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

    def legal_actions(self, player) -> list[arena.Actions]:
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
                actions = self._attacker.available_actions \
                    if self._attacker.available_actions \
                    else arena.Atk_Actions_By_Pos[self._attacker.state_pos]
            case arena.Players.DEFENDER:
                actions = self._defender.available_actions \
                    if self._defender.available_actions \
                    else arena.Defend_Actions
            case _:
                raise ValueError(f"undefined player: {player}")
        if not (actions and actions[0] == arena.Actions.IN_PROGRESS) \
                and self._curr_turn not in self._turns_seen:
            debug(f"\n{arena.player_to_str(self.current_player())} (turn {self._curr_turn+1}): legal actions: {', '.join([arena.a2s(x) for x in actions])}")
            self._turns_seen.add(self._curr_turn)
        return actions

    def apply_actions(self, actions: List[int]):
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

    def apply_action(self, action):
        """
        Apply the actions of a single player in sequential-move
        games. In all stochastic games, _apply_action is called to
        resolve the actions of the chance player. Not used here, but
        shown for reference.
        """

        #if action != arena.Actions.IN_PROGRESS:
        debug(f"{arena.player_to_str(self.current_player())}: apply action {arena.a2s(action)} now in turn {self._curr_turn+1}")
        #debug([len(self.history()), self.history()])

        # Asserted as invariant in sample games:
        # assert self._is_chance and not self._game_over
        assert not self._game_over

        # convert from int to actual Action
        action = arena.Actions(action)

        # _curr_turn is 0-based; this value is for display purposes
        dsp_turn = self._curr_turn + 1

        # some bookeeping to avoid index errors
        self._attacker.append_util_histories()
        self._defender.append_util_histories()

        #debug(self.history_str())
        #debug([self.history()])

        if self._current_player is arena.Players.ATTACKER:
            # Do not terminate game here for completed action sequence,
            # defender still has a chance to detect. Game will not
            # terminate here by reaching self._num_turns either because
            # defender always gets the last action.
            self._attacker.advance(action, self)
            cost = arena.action_cost(action)
            self._attacker.increment_cost(cost)
            self._defender.increment_reward(cost)

            self._attack_vec[self._curr_turn] = action
            #debug(f"ATTACK({self._curr_turn}): {self._attack_vec}")

            self._current_player = arena.Players.DEFENDER
            self._curr_turn += 1

            # attacker turn complete
            return

        assert(self._current_player is arena.Players.DEFENDER)

        # "action" is now defender action

        # register cost of action, add to history, initiate IN_PROGRESS
        # sequences, etc
        self._defender.detect(action, self)

        self._defend_vec[self._curr_turn] = action
        #debug(f"DEFEND({self._curr_turn}): {self._defend_vec}")

        cost = arena.action_cost(action)
        self._defender.increment_cost(cost)
        self._attacker.increment_reward(cost)

        # All completed attack action states -- does not include last
        # state if it is still in progress.
        attack_action_states = list(self._attacker.completed_history)

        detected = False
        atk_action = None
        #if action == arena.Actions.IN_PROGRESS \
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
                if arena.action_succeeds(defend_action, attack_action):
                    # attack action is *actually* detected by the
                    # current defend action; defender gets reward,
                    # attacker takes damage
                    reward = arena.defend_reward(defend_action, attack_action)
                    damage = arena.defend_damage(defend_action, attack_action)
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
            reward = arena.attack_reward(self._attacker.state.action)
            damage = arena.attack_damage(self._attacker.state.action)
            dmg = self._defender.increment_damage(damage)
            self._attacker.increment_reward(dmg)
            if self._attacker.state.action not in arena.NoOp_Actions:
                self._attacker.increment_pos()
            self._attacker.state.expend()

        self._defender.record_utility()
        self._attacker.record_utility()

        self._current_player = arena.Players.ATTACKER

        # self._curr_turn is 0 based
        assert self._curr_turn < self._num_turns

        if detected:
            # we are done if defender detected attack
            debug(f"\nattack action detected, game over after {dsp_turn} turns: {arena.a2s(defend_action)} detected {arena.a2s(atk_action)}\n")
            self._game_over = True
        elif self._attacker.got_all_the_marbles:
            # we are done if attacker completed action escalation sequence
            debug(f"\nattacker is feeling smug, attack sequence complete: game over after {dsp_turn} turns\n")
            self._game_over = True

        self._curr_turn += 1

        # Have we reached max game length? Terminate if so.
        if not self._game_over and self._curr_turn >= self._num_turns:
            debug(f"\nmax game length reached, terminating game after {dsp_turn} turns\n")
            self._turns_exhausted = True
            self._game_over = True


    ### Not sure if these methods are required, but they are
    ### implemented in sample games. We should probably do some
    ### logging/error injection to figure this out.

    def action_to_string(self, player, action):
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

    def turns_played(self):
        """Number of turns played thus far."""
        return self._curr_turn

    def turns_exhausted(self):
        """
        Indicates whether the game maxed out turns rather than either
        player having a conclusive victory. This is not necessarily
        equivalent to max turns having been reached since the final turn
        might have been a success for either player.
        """
        return self._turns_exhausted

    def __str__(self):
        """String for debugging. No particular semantics."""
        return f"Attacker pos at Turn {self._curr_turn+1}: {self._attacker.state_pos}"
