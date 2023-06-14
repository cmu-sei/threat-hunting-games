import math

def normalize_action_probs(probs):
    if probs:
        psum = sum(probs.values())
        if not psum:
            new_probs = {}
            for action in probs:
                new_probs[action] = 1 / len(probs)
            probs = new_probs
        elif not math.isclose(psum, 1.0):
            new_probs = {}
            for action in probs:
                new_probs[action] = probs[action] * (1 / psum)
            probs = new_probs
        else:
            probs = dict(probs)
    return probs
