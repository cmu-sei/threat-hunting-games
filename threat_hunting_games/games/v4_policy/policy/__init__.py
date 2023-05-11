from open_spiel.python.policy import UniformRandomPolicy

from .independent_intervals import IndependentIntervalsPolicy
from .simple_random import SimpleRandomPolicy

_policies = {
    "uniform_random": UniformRandomPolicy,
    "independent intervals": IndependentIntervalsPolicy,
    "simple random": SimpleRandomPolicy,
    "aggregate history": AggregateHistoryPolicy,
}

def get_policy(name):
    if not name:
        return None
    else:
        return _policies[name]

def available_policies():
    return list(_policies.keys())

def policies():
    return dict(_policies)
