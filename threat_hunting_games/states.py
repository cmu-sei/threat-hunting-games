import os, sys, re

import pyspiel
from open_spiel.python.algorithms.get_all_states import get_all_states

def get_leaf_states(game, depth_limit=None):
    if isinstance(game, str):
        game = pyspiel.load_game(game)
    if depth_limit is not None:
        tgt_node_cnt = game.num_players() * depth_limit
    else:
        depth_limit = -1
        tgt_node_cnt = game.num_players() * game.max_game_length()
    for state in get_all_states(game, depth_limit):
        state = tuple((int(x), int(y)) for x, y \
                in re.findall(r"(\d+),\s+(\d+)", state))
        if len(state) == tgt_node_cnt:
            yield state

def get_leaf_actions(game, depth_limit=None):
    for state in get_leaf_states(game, depth_limit):
        yield tuple(x[-1] for x in state)

def get_leaf_actions_strings(game, depth_limit=None):
    for actions in get_leaf_actions(game, depth_limit):
        yield ','.join(str(x) for x in actions)
