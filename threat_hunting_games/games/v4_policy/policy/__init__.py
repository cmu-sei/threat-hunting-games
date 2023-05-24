from open_spiel.python.policy import UniformRandomPolicy, FirstActionPolicy

from . import arena_v4 as arena

from .simple_random import SimpleRandomPolicy
from .independent_intervals import IndependentIntervalsPolicy
from .aggregate_history_random import AggregateHistoryPolicy

_policies = {
    # from open_spiel
    "uniform random": UniformRandomPolicy,
    "first action": FirstActionPolicy,
    # our policies
    "independent intervals": IndependentIntervalsPolicy,
    "simple random": SimpleRandomPolicy,
    "aggregate history": AggregateHistoryPolicy,
}

def get_policy_class(name):
    if not name:
        return None
    else:
        return _policies[name]

def available_policy_classes():
    return list(_policies.keys())

def policy_classes():
    return dict(_policies)

# for use by the independent intervals policy, if used. For parameter
# sweeps can modify this directly or later on load these values from a
# config file
Defend_Action_Intervals = {}
Defend_Interval_Clock_Seed = 0
for i, action in enumerate(arena.Defend_Actions):
    if action == arena.Actions.WAIT:
        continue
    else:
        Defend_Action_Intervals[action] = i

def load_defender_independent_intervals_args():
    # could load from json here
    # need player_id as key for first argument since policy can accept
    # values for multiple players
    return ({arena.Players.DEFENDER: dict(Defend_Action_Intervals)},
            Defend_Interval_Clock_Seed)

Defend_Aggregate_Probs = {}
_pct = .10
for action in reversed(arena.Defend_Actions):
    Defend_Aggregate_Probs[action] = _pct
    _pct += .10
_psum = sum(Defend_Aggregate_Probs.values())
Defend_Aggregate_Probs[arena.Actions.WAIT] = \
        _psum / len(Defend_Aggregate_Probs)
_psum = sum(Defend_Aggregate_Probs.values())
for action in Defend_Aggregate_Probs:
    Defend_Aggregate_Probs[action] *= (1 / _psum)

def load_defender_aggregate_history_args():
    # could load from json here
    # need player_id as key for first argument since policy can accept
    # values for multiple players
    return [{arena.Players.DEFENDER: dict(Defend_Aggregate_Probs)}]

_arg_loaders = {
    arena.Players.DEFENDER: {
        "independent intervals": load_defender_independent_intervals_args,
        "aggregate history": load_defender_aggregate_history_args
    },
}
for player, loaders in _arg_loaders.items():
    assert player in arena.Players, f"{player} not in arena.Players"
    for policy_name in loaders:
        assert policy_name in _policies, f"'{policy_name}' not in _policies"

def get_player_policy_args(player, policy_name):
    assert int(player) in [int(x) for x in arena.Players], \
            f"{player} not in arena.Players"
    assert policy_name in _policies, f"'{policy_name}' not in _policies"
    args = ()
    policy_arg_loaders = _arg_loaders.get(player, {})
    policy_arg_loader = policy_arg_loaders.get(policy_name)
    if policy_arg_loader:
        args = policy_arg_loader()
    return args
