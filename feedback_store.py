"""
Persists analyst/leader feedback (accept / reject / correct) on recommendations,
and exposes a weight adjustment that attribute.py's driver scoring can apply on
the NEXT run - making the feedback loop real rather than a claimed feature.

Mechanism (kept simple and legible, appropriate for a prototype):
  - Each "accept" on a driver nudges that driver's future weight up by +0.03.
  - Each "reject" nudges it down by -0.03 (floor 0.0).
  - "correct" logs the analyst's replacement driver and nudges the replacement up,
    the originally-suggested one down.
Weights are persisted to a small JSON file (sqlite would also work; JSON is
sufficient for a prototype and keeps this dependency-free).
"""

import json
import os
import time
import config

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "outputs", "driver_weight_adjustments.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "outputs", "feedback_log.jsonl")


def _load_weights():
    if os.path.exists(WEIGHTS_PATH):
        return json.load(open(WEIGHTS_PATH))
    return {}


def _save_weights(weights):
    os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
    json.dump(weights, open(WEIGHTS_PATH, "w"), indent=2)


def record_feedback(kpi: str, suggested_driver: str, decision: str, corrected_driver: str = None, persona: str = None):
    """decision in {"accept", "reject", "correct"}"""
    weights = _load_weights()

    def bump(driver, delta):
        weights[driver] = round(max(0.0, weights.get(driver, 0.0) + delta), 3)

    if decision == "accept":
        bump(suggested_driver, 0.03)
    elif decision == "reject":
        bump(suggested_driver, -0.03)
    elif decision == "correct" and corrected_driver:
        bump(suggested_driver, -0.03)
        bump(corrected_driver, 0.05)

    _save_weights(weights)

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "kpi": kpi, "persona": persona, "suggested_driver": suggested_driver,
            "decision": decision, "corrected_driver": corrected_driver,
            "timestamp": time.time()
        }) + "\n")

    return weights


def get_weight_adjustment(driver: str) -> float:
    weights = _load_weights()
    return weights.get(driver, 0.0)
