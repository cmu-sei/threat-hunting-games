import os
import numpy as np
from datetime import datetime
from open_spiel.python.bots.policy import PolicyBot

import policies

def get_player_policy(game, player, policy_name, action_picker=None)
    """
    kwargs are typically keyword arguments that get passed along into
    the action picker class
    """
    policy_class = policies.get_policy_class(policy_name)
    return policy_class(game, action_picker=action_picker, **kwargs)

def get_player_bot(game, player, policy_name, action_picker=None)
    policy = get_player_policy(game, player, policy_name,
            action_picker=action_picker, **kwargs)
    bot = PolicyBot(player, np.random, policy)
    return bot


class PathManager:

    _atk_str = 'atk'
    _def_str = 'def'

    def __init__(self, base_dir=None, game_name=None,
            atk_policy=None, atk_action_picker=None,
            def_policy=None, def_action_picker=None,
            model=None, raw_path=None):
        self._timestamp = datetime.now().isoformat(timespec="minutes")
        if raw_path:
            self._init_from_raw_path(raw_path)
        else:
            self._base_dir = base_dir
            self._game_name = game_name
            self._atk_policy = atk_policy
            self._atk_action_picker = atk_action_picker
            self._def_policy = def_policy
            self._def_action_picker = def_action_picker
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
        self._atk_policy = stub_parts.pop() if stub_parts else None
        self._atk_action_picker = stub_parts.pop() if stub_parts else None
        self._def_action_picker = stub_parts.pop() if stub_parts else None
        self._model = stub_parts.pop() if stub_parts else None

    @property
    def base_dir(self):
        return self._base_dir

    @property
    def game_name(self):
        return self._game_name

    @property
    def atk_policy(self):
        return self._atk_policy

    @property
    def atk_action_picker(self):
        return self._atk_action_picker

    @property
    def def_policy(self):
        return self._def_policy

    @property
    def def_action_picker(self):
        return self._def_policy

    @property
    def model(self):
        return self._model

    @property
    def timestamp(self):
        return self._timestamp

    def stub(self, ext=None):
        parts = [x for x in (self._game_name, self._atk_policy,
                self._def_policy, self._model,
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
            "atk_policy": self.atk_policy,
            "def_policy": self.def_policy,
            "model": self.model,
        }
        return str(fields)
