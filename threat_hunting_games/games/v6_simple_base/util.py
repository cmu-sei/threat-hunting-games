import os
import numpy as np
from datetime import datetime
from open_spiel.python.bots.policy import PolicyBot
#from policy_bot import PolicyBot
import policies
from arena import debug

def get_player_policy(game, player, policy_name, action_picker=None):
    """
    kwargs are typically keyword arguments that get passed along into
    the action picker class
    """
    policy_class = policies.get_policy_class(policy_name)
    if policy_class in (policies.UniformRandomPolicy,
            policies.FirstActionPolicy):
        return policy_class(game)
    else:
        return policy_class(game, action_picker=action_picker)

def get_player_bot(game, player, policy_name, action_picker=None):
    debug(f"Bot selecting {player} policy: {policy_name}")
    policy = get_player_policy(game, player, policy_name,
            action_picker=action_picker)
    bot = PolicyBot(player, np.random, policy)
    return bot


class PathManager:

    _atk_str = 'atk'
    _def_str = 'def'

    def __init__(self, base_dir=None, game_name=None,
            detection_costs=None, advancement_rewards=None,
            defender_policy=None, defender_action_picker=None,
            attacker_policy=None, attacker_action_picker=None,
            model=None, timestamp=None, no_timestamp=False):
            #model=None, raw_path=None):
        self._timestamp = None
        if not no_timestamp:
            if timestamp:
                self._timestamp = timestamp
            else:
                self._timestamp = datetime.now().isoformat(timespec="minutes")
        #if raw_path:
        #    self._init_from_raw_path(raw_path)
        #else:
        self._base_dir = base_dir
        self._game_name = game_name
        self._detection_costs = detection_costs
        self._advancement_rewards = advancement_rewards
        self._def_policy = defender_policy
        self._def_action_picker = defender_action_picker
        self._atk_policy = attacker_policy
        self._atk_action_picker = attacker_action_picker
        self._model = model

    #def _init_from_raw_path(self, rp):
    #    parts = list(os.path.split(rp))
    #    if parts[-1] in [self._atk_str, self._def_str]:
    #        parts.pop()
    #    stub = parts.pop()
    #    self._base_dir = os.path.join(*parts) if parts else None
    #    # get rid of extension if present
    #    stub = stub.rsplit('.', 1)[0]
    #    stub_parts = stub.split('-')
    #    self._timestamp = '-'.join(stub_parts[-3:])
    #    stub_parts = list(reversed(stub_parts[:-3]))
    #    self._game_name = stub_parts.pop() if stub_parts else None
    #    self._atk_policy = stub_parts.pop() if stub_parts else None
    #    self._atk_action_picker = stub_parts.pop() if stub_parts else None
    #    self._def_action_picker = stub_parts.pop() if stub_parts else None
    #    self._model = stub_parts.pop() if stub_parts else None

    @property
    def base_dir(self):
        return self._base_dir

    @property
    def game_name(self):
        return self._game_name

    @property
    def detection_costs(self):
        return self._detection_costs

    @property
    def advancement_rewards(self):
        return self._advancement_rewards

    @property
    def def_policy(self):
        return self._def_policy

    @property
    def def_action_picker(self):
        return self._def_policy

    @property
    def atk_policy(self):
        return self._atk_policy

    @property
    def atk_action_picker(self):
        return self._atk_action_picker

    @property
    def model(self):
        return self._model

    @property
    def timestamp(self):
        return self._timestamp

    def stub(self):
        parts = []
        game_dir = []
        if self._game_name:
            game_dir.append(self._game_name)
        if self._model:
            game_dir.append(self._model)
        if self._timestamp:
            game_dir.append(self._timestamp)
        game_dir = '-'.join(game_dir)
        utility_dir = []
        if self._detection_costs:
            utility_dir.append(self._detection_costs)
        if self._advancement_rewards:
            utility_dir.append(self._advancement_rewards)
        utility_dir = '-'.join(utility_dir)
        def_dir = []
        if self._def_policy:
            def_dir.append(self._def_policy)
        if self._def_action_picker:
            def_dir.append(self._def_action_picker)
        def_dir = '-'.join(def_dir)
        atk_dir = []
        if self._atk_policy:
            atk_dir.append(self._atk_policy)
        if self._atk_action_picker:
            atk_dir.append(self._atk_action_picker)
        parts = [x for x in (game_dir, utility_dir, def_dir, atk_dir) if x]
        stub = os.path.join(*parts)
        return stub

    def path(self, suffix=None, prefix=None):
        parts = []
        if self._base_dir:
            parts.append(self._base_dir)
        if prefix:
            parts.append(prefix)
        parts.append(self.stub())
        if suffix:
            parts.append(suffix)
        return os.path.join(*parts)

    @property
    def atk_dir(self):
        return self.path(suffix=self._atk_str)

    @property
    def def_dir(self):
        return self.path(suffix=self._def_str)

    @property
    def checkpoint_dirs(self):
        return [self.atk_dir, self.def_dir]

    @property
    def atk_str(self):
        return self._atk_str

    @property
    def def_str(self):
        return self._def_str

    def __str__(self):
        fields = {
            "base_dir": self.base_dir,
            "game_name": self.game_name,
            "detection_costs": self.detection_costs,
            "advancement_rewards": self.advancement_rewards,
            "def_policy": self.def_policy,
            "def_action_picker": self.def_action_picker,
            "atk_policy": self.atk_policy,
            "atk_action_picker": self.atk_action_picker,
            "model": self.model,
        }
        return str(fields)
