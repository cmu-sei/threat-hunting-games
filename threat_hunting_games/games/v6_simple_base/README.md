A Brief Guide to the Scripts and Modules
========================================

There are two main themes with these scripts. One is the focus on
*policies*, which are used by *bots*. The other is centered around
training reinforcement learning models -- these in turn can be used
as policies.

An example of a bot that uses a policy is:

    open_spiel.python.bots.policy.PolicyBot

Also see in this directory:

    ./policy_bot.py

An example of a bot being used as an *agent* (which drive RL models) is:

    ./bot_agent.py

This was derived from a game example in OpenSpiel (see the comments in
the script). Using this allows fixed-policy bots to square off against
RL trained agents.

Game Parameters
---------------

During runtime when OpenSpiel loads a particular game, our games have five parameters:

  1. advancement_rewards
  2. detection_costs
  3. use_waits
  4. use_timewaits
  5. use_chance_fail

These have to be declared at runtime because of the way the individual
modules are loaded by `pyspiel`. Advancement rewards are the varying
utility structures for the attacker. Detection costs are the varying
utility structures for the defender. `use_waits` determines whether or
not the `WAIT` action is present for both players. act`use_timewaits`
controls whether or not there are a varying number of `IN_PROGRESS` (a
type of `WAIT` action) actions that need to happen before the actual
action is completed. `use_chance_fail` determines whether or not any
particular action has a general chance of failure as well as a chance
of failure for a detection action vs the attacker action it is designed
to detect.

Policies
--------

Policy modules can be found in the following directory:

    ./policies

The base module, `__init__.py`, loads each policy module and provides
some symbollic string labels for specifying which policy is of
interest -- these strings are also used with command line parameters
in the scripts.

Within each policy module there are several *action pickers* which
represent variations on the overall policy as described in the writeup
available in the _Kill-chain Games_ document on Overleaf. Within each
policy module are symbolic string indicies for each action picker --
these also end up getting used in command line parameters.

All scripts have a `--help` parameter that list more detailed
information about each one.

A note on cost/reward utilities: the way they are currently structured,
each action has three fields: `cost`, `reward`, and `damage`. Damage is
the utility loss of the opposing player and is currently the same value
as the reward for that action.

The utilities can be adjusted with command line parameters -- there is
`advancement-rewards` and `detection-costs` that can be varied according
to the same Overleaf document mentioned above.

The Scripts
-----------

### bot_playthrough.py

This script pits two bots against one another -- the attacker and
defender -- and each bot uses a policy and action-picker. Multipe
iterations (or episodes) can be specified and summary of the iterations
are stored in an output directory (by default `./dump`). There are sums
of returns, victories, inconclusive matches, p_means (averages), as well
as some meta-information about the structure of the game itself. The
returns are the overall utilities for each player. Victories represent
the number of time the attacker completed the kill-chain or the defender
made a successful detection (currently the game ends with *any*
detection of *any* attacker action). The utilities summations are
divided by the number of episodes to produce p_means. `History tallies`
are essentially a histogram of gagmeplay moves -- a `history` is a
sequence of actions alternating between each player beginning with the
attacker. If two separate episodes unfold in the exact some way, their
count is incremented in the tally map. The symbolic names of actions are
detailedc in the `action map`. The structure of the cost/reward
utilities is detailed in the `utilities` field -- these are controlled
by the `advancement-rewards` and `detection-costs` parameters. These too
have symbolic string representations that are used on the command line.

### bot_playoffs.py

This script is basically running the equivalent of `bot_playthrough.py`
for every permutation of policy, action picker, advancement reward
utility structure, and detection cost utility structure. For each
permutation, multiple games/episodes are played (by default 1000) and a
summary file is generated for that particular permutation. Optionally a
record of each individule episode can also be stored.

This also uses the `./dump` directory but can be specified elsewhere.

The summary files are similar to the `bot_playthrough.py` output. Each
summary file has a listing of the game settings (policies and action
pickers for each player, advancement rewards, detection costs, use
waits, use timewaits, use chance fail).

This may or may not be useful, but the maximum attack rewards is
calculated and this is used to scale the sums of returns and the p_means
as though the maximum rewards is 100. (`sum_normalized_returns`,
`p_means_normalized`).

As with `bot_playthrough.py`, each permutation summary has action and
player maps to their symbolic names as well as a history tally histogram
detailing how often identical gameplays occurred.

### rl_train.py

This script trains a DQN model with reinforcement learning. It is mostly
based on the OpenSpiel example `python/examples/rl_response.py` script.
The resulting model can be loaded and used as either an agent (the RL
way of doing things) or a policy (using a wrapper around the agent) and
tested against fixed policies which can be selected via command line
parameters. The training itself happens using a fixed policy for the
attacker as well as the defender, so in all likelyhood will be most
effective against those fixed policies upon which it was trained. The
models are saved in the `dat` directory by default, rather than the
`dump` directory..

### rl_playthrough.py

This is the script that deploys an RL model against the fixed policies.
It too is based on part of the `python/examples/rl_response.py` script.
It uses the `bot_agent.py` to wrap the RL model. Currently the RL agents
are not integrated with `bot_playthrough.py` or `bot_playoffs.py` which
are described above.
