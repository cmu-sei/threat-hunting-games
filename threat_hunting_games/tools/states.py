import os, sys, re

import pyspiel
#from open_spiel.python.algorithms.get_all_states import get_all_states
from .threat_hunting_games.algorithms.get_all_states import get_all_states

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
    for state_str, state in get_all_states(game, depth_limit).items():
        if not state.is_terminal():
            continue
        yield state
