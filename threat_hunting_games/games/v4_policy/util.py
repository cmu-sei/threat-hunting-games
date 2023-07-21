import os
import numpy as np
from datetime import datetime
from open_spiel.python.bots.policy import PolicyBot

import policies

def get_player_policy(game, player, policy_name):
    policy_class = policies.get_policy_class(policy_name)
    policy_args = policies.get_player_policy_args(player, policy_name)
    return policy_class(game, *policy_args)

def get_player_bot(game, player, policy_name):
    policy = get_player_policy(game, player, policy_name)
    bot = PolicyBot(player, np.random, policy)
    return bot


class PathManager:

    _atk_str = 'atk'
    _def_str = 'def'

    def __init__(self, base_dir=None, game_name=None,
            attacker_policy=None, defender_policy=None,
            model=None, raw_path=None):
        self._timestamp = datetime.now().isoformat(timespec="minutes")
        if raw_path:
            self._init_from_raw_path(raw_path)
        else:
            self._base_dir = base_dir
            self._game_name = game_name
            self._attacker_policy = attacker_policy
            self._defender_policy = defender_policy
            self._model = model

    def _init_from_raw_path(self, rp):
        parts = list(os.path.split(rp))
        if parts[-1] in [self._atk_str, self._def_str]:
            parts.pop()
        stub = parts.pop()
        self._base_dir = os.path.join(*parts) if parts else None
        # get rid of extension if present
        stub = stub.rsplit('.', 1)[0]
        stub_parts = stub.split('-')
        self._timestamp = '-'.join(stub_parts[-3:])
        stub_parts = list(reversed(stub_parts[:-3]))
        self._game_name = stub_parts.pop() if stub_parts else None
        self._attacker_policy = stub_parts.pop() if stub_parts else None
        self._defender_policy = stub_parts.pop() if stub_parts else None
        self._model = stub_parts.pop() if stub_parts else None

    @property
    def base_dir(self):
        return self._base_dir

    @property
    def game_name(self):
        return self._game_name

    @property
    def attacker_policy(self):
        return self._attacker_policy

    @property
    def defender_policy(self):
        return self._defender_policy

    @property
    def model(self):
        return self._model

    @property
    def timestamp(self):
        return self._timestamp

    def stub(self, ext=None):
        parts = [x for x in (self._game_name, self._attacker_policy,
                self._defender_policy, self._model,
                self._timestamp) if x]
        if not parts:
            return None
        stub = '-'.join(parts)
        if ext:
            stub = f"{stub}.{ext}"
        return stub

    def path(self, suffix=None, prefix=None, ext=None):
        stub = self.stub(ext=ext)
        parts = []
        if self._base_dir:
            parts.append(self._base_dir)
        if prefix:
            parts.append(prefix)
        parts.append(self.stub(ext=ext))
        if suffix:
            parts.append(suffix)
        return os.path.join(*parts)

    @property
    def attacker_dir(self):
        return self.path(suffix=self._atk_str)

    @property
    def defender_dir(self):
        return self.path(suffix=self._def_str)

    @property
    def checkpoint_dirs(self):
        return [self.attacker_dir, self.defender_dir]

    @property
    def attacker_str(self):
        return self._atk_str

    @property
    def defender_str(self):
        return self._def_str

    def __str__(self):
        fields = {
            "base_dir": self.base_dir,
            "game_name": self.game_name,
            "attacker_policy": self.attacker_policy,
            "defender_policy": self.defender_policy,
            "model": self.model,
        }
        return str(fields)
