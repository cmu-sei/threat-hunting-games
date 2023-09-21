#!/bin/env python3

import os, sys, json, glob, argparse
from datetime import datetime

import games

game_mod = games.current_game
game_stub = os.path.dirname(game_mod.__file__)

bin_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.abspath(os.path.join(bin_dir, ".."))
default_tmp_dir = os.path.join(base_dir, "tmp")
dat_dir = os.path.join(base_dir, "games", game_stub, "dump_playoffs")
if not os.path.isdir(dat_dir):
    print("whoops, game dir not found:", dat_dir)
    sys.exit()

dat_dirs = sorted(x for x in glob.glob(f"{dat_dir}/*") if os.path.isdir(x))
if dat_dirs:
    latest_dump = dat_dirs[-1]
else:
    latest_dump = "no playoff directories currently present"

parser = argparse.ArgumentParser(prog="Bot Playoff Selection Filter")
parser.add_argument("--playoff-dir", "--pd", default=latest_dump,
        help=f"Playoff output directory from which to filter. ({latest_dump})")
parser.add_argument("--list-playoffs", "--lp", action="store_true",
        help="List available playoff output choices from which to choose.")
parser.add_argument("--output-dir", "--od", default=default_tmp_dir,
        help=f"Directory in which to store filtered results. ({default_tmp_dir})")
args = parser.parse_args()
dat_dir = args.playoff_dir
if dat_dir:
    summaries = glob.glob(f"{dat_dir}/*/*.json")
else:
    summaries = []
print(f"\ndat dir: {dat_dir}")
print(f"{len(summaries)} summaries found\n")
if not summaries:
    sys.exit()

# collect all values for interesting fields
params = {
    "defender_policy": set(),
    "attacker_policy": set(),
    "advancement_rewards": set(),
    "detection_costs": set(),
}

for summary in summaries:
    with open(summary, "r") as f:
        j = json.load(f)
        def_policy = (j["defender_policy"],)
        def_policy = (j["defender_policy"], j.get("defender_action_picker"))
        params["defender_policy"].add(def_policy)
        atk_policy = (j["attacker_policy"], j.get("attacker_action_picker"))
        params["attacker_policy"].add(atk_policy)
        params["advancement_rewards"].add(j["advancement_rewards"])
        params["detection_costs"].add(j["detection_costs"])
for param, vals in params.items():
    params[param] = sorted(vals)

advancement_rewards = sorted(params["advancement_rewards"])
print("\nSelect advancement rewards: single reward, comma-separated list,\nor hit return for all:\n")
choices = set(x+1 for x in range(len(params["advancement_rewards"])))
for i, val in enumerate(advancement_rewards):
    print(f"{i+1}: {val}")
selected = None
while not selected:
    selected = input("\nAdvancement rewards: ")
    if not selected:
        selected = choices
    else:
        selected = [int(x) for x in selected.split(",")]
        diff = set(selected).difference(choices)
        if diff:
            print("invalid choices:", ','.join(sorted(diff)))
            continue
    advancement_rewards = set(advancement_rewards[x-1] for x in selected)

detection_costs = sorted(params["detection_costs"])
print("\nSelect detection costs: single cost, comma-separated list,\nor hit return for all:\n")
choices = set(x+1 for x in range(len(params["detection_costs"])))
for i, val in enumerate(params["detection_costs"]):
    print(f"{i+1}: {val}")
selected = None
while not selected:
    selected = input("\nDetection costs: ")
    if not selected:
        selected = choices
    else:
        selected = [int(x) for x in selected.split(",")]
        diff = set(selected).difference(choices)
        if diff:
            print("invalid choices:", ','.join(sorted(diff)))
            continue
    detection_costs = set(detection_costs[x-1] for x in selected)

atk_compound_policies = set()
for compound_policy, ap in sorted(params["attacker_policy"]):
    if ap == "n/a":
        ap = None
    if ap:
        compound_policy = "-".join([compound_policy, ap])
    atk_compound_policies.add(compound_policy)
atk_compound_policies = sorted(atk_compound_policies)
print("\nSelect attacker policy: single policy, comma-separated list,\nor hit return for all:\n")
choices = set(x+1 for x in range(len(atk_compound_policies)))
for i, val in enumerate(sorted(atk_compound_policies)):
    print(f"{i+1}: {val}")
selected = None
while not selected:
    selected = input("\nAttacker policies: ")
    if not selected:
        selected = list(choices)
    else:
        selected = [int(x) for x in selected.split(",")]
        diff = set(selected).difference(choices)
        if diff:
            print("invalid choices:", ','.join(sorted(diff)))
            continue
    atk_compound_policies = set(atk_compound_policies[x-1] for x in selected)

def_compound_policies = set()
for compound_policy, ap in sorted(params["defender_policy"]):
    if ap == "n/a":
        ap = None
    if ap:
        compound_policy = "-".join([compound_policy, ap])
    def_compound_policies.add(compound_policy)
def_compound_policies = sorted(def_compound_policies)
print("\nSelect defender policy: single policy, comma-separated list,\nor hit return for all:\n")
choices = set(x+1 for x in range(len(def_compound_policies)))
for i, val in enumerate(sorted(def_compound_policies)):
    print(f"{i+1}: {val}")
selected = None
while not selected:
    selected = input("\nDefender policies: ")
    if not selected:
        selected = list(choices)
    else:
        selected = [int(x) for x in selected.split(",")]
        diff = set(selected).difference(choices)
        if diff:
            print("invalid choices:", ','.join(sorted(diff)))
            continue
    def_compound_policies = set(def_compound_policies[x-1] for x in selected)

now = datetime.now().isoformat(timespec="seconds")
tmp_dir = os.path.join(args.output_dir, now)
if not os.path.exists(tmp_dir):
    os.makedirs(tmp_dir)

for summary in summaries:
    with open(summary, "r") as f:
        j = json.load(f)
        json_keys = j.keys()
        if j["advancement_rewards"] not in advancement_rewards:
            continue
        if j["detection_costs"] not in detection_costs:
            continue
        atk_policy = j["attacker_policy"]
        if j["attacker_action_picker"] \
                and j["attacker_action_picker"] != "n/a":
            atk_policy = '-'.join([atk_policy, j["attacker_action_picker"]])
        if atk_policy not in atk_compound_policies:
            continue
        def_policy = j["defender_policy"]
        if j["defender_action_picker"] \
                and j["defender_action_picker"] != "n/a":
            def_policy = '-'.join([def_policy, j["defender_action_picker"]])
        if def_policy not in def_compound_policies:
            continue
        summary_stub = os.path.basename(summary)
        os.link(summary, os.path.join(tmp_dir, summary_stub))

print(f"Done! JSON summary files with the parameters selected are in {tmp_dir}")
