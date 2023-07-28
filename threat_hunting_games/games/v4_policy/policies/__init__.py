from open_spiel.python.policy import UniformRandomPolicy, FirstActionPolicy

from . import arena_zsum_v4 as arena

from .simple_random import SimpleRandomPolicy
from .independent_intervals import IndependentIntervalsPolicy
from .aggregate_history_random import AggregateHistoryPolicy

_policies = {
    # from open_spiel
    "uniform_random": UniformRandomPolicy,
    "first_action": FirstActionPolicy,
    # our policies
    "independent_intervals": IndependentIntervalsPolicy,
    "simple_random": SimpleRandomPolicy,
    "aggregate_history": AggregateHistoryPolicy,
}

def get_policy_class(name):
    if not name:
        return None
    else:
        return _policies[name]

def available_policies():
    return list(_policies.keys())

def policy_classes():
    return dict(_policies)
