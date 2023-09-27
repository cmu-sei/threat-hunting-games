from open_spiel.python.policy import UniformRandomPolicy, FirstActionPolicy

from . import arena

from .simple_random import SimpleRandomPolicy
from .independent_intervals import IndependentIntervalsPolicy
from .aggregate_history_random import AggregateHistoryPolicy
from .last_action import LastActionPolicy

_policies = {
    # from open_spiel
    "uniform_random": UniformRandomPolicy,
    "first_action": FirstActionPolicy,
    "last_action": LastActionPolicy,
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

def list_policies():
    return list(_policies.keys())

def policy_classes():
    return dict(_policies)

def list_policies_with_pickers():
    names = []
    for policy, cls in _policies.items():
        if hasattr(cls, "list_action_pickers"):
            for action_picker in cls.list_action_pickers():
                names.append((policy, action_picker))
        else:
            names.append((policy, ""))
    return names

def list_policies_with_pickers_strs():
    names = []
    for policy, ap in list_policies_with_pickers():
        if ap:
            names.append("-".join([policy, ap]))
        else:
            names.append(policy)
    return names
