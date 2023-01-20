import os, sys, re

import pyspiel
from open_spiel.python.algorithms.get_all_states import get_all_states

def get_leaf_states(game, depth_limit=None):
    """
    Parse the output of all possible states but only keep the leaf
    (terminal) nodes.
    """
    if isinstance(game, str):
        game = pyspiel.load_game(game)
    if depth_limit is None:
        depth_limit = -1
    tgt_node_cnt = game.max_game_length()
    for state in get_all_states(game, depth_limit):
        state = tuple((int(x), int(y)) for x, y \
                in re.findall(r"(\d+),\s+(\d+)", state))
        if len(state) == tgt_node_cnt:
            yield state
