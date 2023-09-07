import json
import glob
from os import mkdir, link
from datetime import datetime
from sys import exit

summaries = glob.glob("./*/*.json")

# collect all values for interesting fields
params = {
    "defender policy": set(),
    "defender action picker": set(),
    "attacker policy": set(),
    "attacker action picker": set(),
    "advancement_rewards": set(),
    "detection_costs": set(),
}

for summary in summaries:
    with open(summary, "r") as f:
        j = json.load(f)
        json_keys = j.keys()
        for key in params:
            params[key].add(j[key])

print(params.keys())

tmpdir = (
    str(datetime.now().year)
    + str(datetime.now().month)
    + str(datetime.now().day)
    + str(datetime.now().microsecond)
)
mkdir(tmpdir)


permutes = []
print("Select advancement rewards: single reward, comma-separated list, or 0 for all")
reward_params = []
for i, val in enumerate(params["advancement_rewards"]):
    reward_params.append(val)
    print(f"{i+1}: {val}")
rewards = input("Advancement rewards: ")
if "0" in rewards:
    if len(rewards) > 1:
        print("Cannot select 0 with other parameters. Terminating...")
        exit()
    rewards = params["advancement_rewards"]
    print(reward_params)
else:
    try:
        rewards = [reward_params[i - 1] for i in map(int, rewards.split(","))]
        print(rewards)
    except:
        print("Invalid advancement rewards selected. Terminating...")
        exit()


detect_params = []
for i, val in enumerate(params["detection_costs"]):
    detect_params.append(val)
    print(f"{i+1}: {val}")
detects = input("Detection costs:")
if "0" in detects:
    if len(detects) > 1:
        print("Cannot select 0 with other parameters")
        exit()
    detects = params["detection_costs"]
    print(detects)
else:
    try:
        detects = [detect_params[i - 1] for i in map(int, detects.split(","))]
        print(detects)
    except:
        print("Invalid detection costs selected. Terminating...")
        exit()

for summary in summaries:
    with open(summary, "r") as f:
        j = json.load(f)
        json_keys = j.keys()
        if j["advancement_rewards"] in rewards and j["detection_costs"] in detects:
            permutes.append(summary)
            link(summary, tmpdir + "/" + "".join(summary.split("/")[-2:]))

print(f"Done! JSON summary files with the parameters selected are in {tmpdir}")
