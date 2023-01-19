#!/bin/env python3

import os, sys, json

import pyspiel

from parsers import parse_playthrough
from states import get_leaf_states

from algorithms import generate_playthrough
from gameload import game_name

def playthroughs(game):
    for state_actions, text in playthroughs_text(game):
        yield state_actions, parse_playthrough(text)

def playthroughs_text(game):
    if isinstance(game, str):
        game_name = game
    else:
        game_type = game.get_type()
        game_name = game_type.short_name
    for state_actions in get_leaf_states(game):
        playthrough_text = generate_playthrough.playthrough(
                game_name, state_actions)
        yield state_actions, playthrough_text

def playthroughs_json(game, indent=None):
    for state_actions, playthrough in playthroughs(game):
        yield state_actions, json.dumps(playthrough, indent=indent)

def _action_groups_to_str(action_groups):
    action_str = (f"{x},{y}" for x, y in action_groups)
    action_str = '_'.join(action_str)
    return action_str

def gen_playthrough_text_files(game, tgt_dir):
    if not os.path.isdir(tgt_dir):
        raise ValueError(f"not a dir: {tgt_dir}")
    if isinstance(game, str):
        game = pyspiel.load_game(game)
    game_type = game.get_type()
    for action_groups, playthrough_text in playthroughs_text(game):
        action_str = _action_groups_to_str(action_groups)
        fname = f"{game_type.short_name}.{action_str}.txt"
        f = os.path.join(tgt_dir, fname)
        with open(f, 'w') as fh:
            print(playthrough_text, file=fh)

def gen_playthrough_json_files(game, tgt_dir, indent=None):
    if not os.path.isdir(tgt_dir):
        raise ValueError(f"not a dir: {tgt_dir}")
    if isinstance(game, str):
        game = pyspiel.load_game(game)
    game_type = game.get_type()
    cnt = 0
    for action_groups, playthrough in playthroughs(game):
        action_str = _action_groups_to_str(action_groups)
        fname = f"{game_type.short_name}.{action_str}.json"
        f = os.path.join(tgt_dir, fname)
        with open(f, 'w') as fh:
            json.dump(playthrough, fh, indent=indent)
        cnt += 1
    return cnt

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("output dir required")
        sys.exit(1)
    cnt = gen_playthrough_json_files(game_name, sys.argv[1], indent=2)
    print(f"{cnt} files generated in {sys.argv[1]}")
