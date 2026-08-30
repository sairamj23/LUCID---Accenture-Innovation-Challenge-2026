"""
LUCID prototype - end-to-end demo runner.

Runs the full FUSE -> DETECT -> ATTRIBUTE -> NARRATE -> ACT pipeline across
three deliberately engineered scenarios, satisfying the Round 2 minimum
prototype checklist:

  Scenario A: Multi-factor movement, high confidence
              (Northeast weekly_regional_revenue drop -> carrier delay)
  Scenario B: Genuinely ambiguous / low-confidence movement
              (product_engagement_score dip -> no dominant driver -> abstains)
  Scenario C: Sparse-history KPI
              (new_feature_adoption_rate, only 3 weeks -> abstains)

Each scenario is run for 2 personas (Ops Manager / Finance Lead for A,
Product Lead for B and C, per entitlements) to demonstrate persona-specific
narratives and the security/entitlement check in Act.

One simulated feedback event (accept) is recorded at the end of Scenario A
to demonstrate the feedback loop actually changing stored weights.

Run:  python main.py
Toggle real Gemini calls:  export LUCID_LLM_MODE=gemini && export GEMINI_API_KEY=...
"""

import json
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import fuse, detect, attribute, narrate, act
import feedback_store
import config

OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT_DIR, exist_ok=True)


def run_scenario(label, sources, contract, kpi, region, personas):
    print(f"\n{'='*80}\nSCENARIO: {label}  (kpi={kpi}, region={region})\n{'='*80}")

    revenue = sources["revenue"]
    series = revenue[(revenue["kpi"] == kpi) & (revenue["region"] == region)]
    detection = detect.detect_movement(series, kpi, region)
    print(f"\n[DETECT] {json.dumps(detection, indent=2, default=str)}")

    all_weeks = sorted(series["week"].unique())
    window = all_weeks[-2:] if len(all_weeks) >= 2 else all_weeks
    window_start, window_end = (pd.Timestamp(window[0]), pd.Timestamp(window[-1])) if window else (None, None)

    evidence = []
    attribution = {"ranked_drivers": [{"driver": "n/a", "score": 0, "relative_confidence": 0, "supporting_evidence": []}], "is_ambiguous": True}
    if detection["classification"] not in ("normal", "insufficient_history"):
        evidence = fuse.retrieve_evidence(sources, region, window_start, window_end)
        attribution = attribute.rank_drivers(evidence, kpi=kpi)
        seg = attribute.segment_decomposition(revenue, kpi, all_weeks[-2:]) if region != "All" else None
        print(f"\n[ATTRIBUTE] segment_contribution={seg}")
        print(f"[ATTRIBUTE] ranked_drivers={json.dumps(attribution['ranked_drivers'], indent=2)}")
        print(f"[ATTRIBUTE] is_ambiguous={attribution['is_ambiguous']}")
    elif detection["classification"] == "insufficient_history":
        print("\n[ATTRIBUTE] skipped - insufficient history, handled directly by Narrate's abstention path.")
    else:
        print("\n[ATTRIBUTE] skipped - movement classified 'normal', no material change to attribute.")

    kpi_def = contract[kpi]["definition"]
    results = {"scenario": label, "detection": detection, "personas": []}

    for persona in personas:
        story = narrate.narrate(detection, attribution, evidence, persona, kpi_def)
        print(f"\n[NARRATE - {persona}] abstained={story['abstained']} confidence={story['confidence']}")
        print(f"  {story['narrative']}")

        recommendation = act.build_recommendation(detection, attribution, persona)
        print(f"\n[ACT - {persona}] {json.dumps(recommendation, indent=2, default=str)}")

        results["personas"].append({"persona": persona, "narrative": story, "action": recommendation})

    return results


def main():
    sources = fuse.load_sources()
    contract = fuse.load_contract()

    all_results = []

    all_results.append(run_scenario(
        "A - Multi-factor movement (Northeast revenue drop)",
        sources, contract, "weekly_regional_revenue", "Northeast",
        personas=["Ops Manager", "Finance Lead"],
    ))

    all_results.append(run_scenario(
        "B - Ambiguous movement (product engagement dip)",
        sources, contract, "product_engagement_score", "All",
        personas=["Product Lead"],
    ))

    all_results.append(run_scenario(
        "C - Sparse-history KPI (new feature adoption)",
        sources, contract, "new_feature_adoption_rate", "All",
        personas=["Product Lead"],
    ))

    all_results.append(run_scenario(
        "E - Multi-segment movement (SMB churn spike, tier decomposition)",
        sources, contract, "customer_churn_rate", "SMB",
        personas=["Customer Success Lead", "Finance Lead"],
    ))

    all_results.append(run_scenario(
        "F - Multi-segment movement (Social conversion drop, channel decomposition)",
        sources, contract, "marketing_conversion_rate", "Social",
        personas=["Marketing Lead"],
    ))

    # Entitlement/security scenario: Product Lead should be denied on the
    # finance-owned KPI even though the KPI is materially anomalous.
    print(f"\n{'='*80}\nSCENARIO: D - Entitlement check (Product Lead requests a Finance-owned KPI)\n{'='*80}")
    revenue = sources["revenue"]
    series = revenue[(revenue["kpi"] == "weekly_regional_revenue") & (revenue["region"] == "Northeast")]
    detection = detect.detect_movement(series, "weekly_regional_revenue", "Northeast")
    denied = act.build_recommendation(detection, {"ranked_drivers": [{"driver": "carrier_delay_fulfillment"}]}, "Product Lead")
    print(json.dumps(denied, indent=2))

    # Feedback loop demo: leader accepts the Scenario A top driver for Northeast.
    print(f"\n{'='*80}\nFEEDBACK LOOP: Ops Manager accepts 'carrier_delay_fulfillment' for Scenario A\n{'='*80}")
    weights_before = feedback_store._load_weights()
    feedback_store.record_feedback("weekly_regional_revenue", "carrier_delay_fulfillment", "accept", persona="Ops Manager")
    weights_after = feedback_store._load_weights()
    print(f"Weights before: {weights_before}\nWeights after:  {weights_after}")
    print("-> Next Attribute run for this driver will score slightly higher (see attribute.py's feedback_adjustment).")

    with open(os.path.join(OUT_DIR, "run_results.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Telemetry summary
    print(f"\n{'='*80}\nTELEMETRY SUMMARY (LLM economics)\n{'='*80}")
    if os.path.exists(config.TELEMETRY_LOG_PATH):
        records = [json.loads(l) for l in open(config.TELEMETRY_LOG_PATH)]
        total_cost = sum(r["est_cost_usd"] for r in records)
        total_latency = sum(r["latency_ms"] for r in records)
        print(f"LLM calls made: {len(records)}")
        print(f"Backend(s) used: {set(r['backend'] for r in records)}")
        print(f"Total est. cost: ${total_cost:.6f}")
        print(f"Total latency: {total_latency:.1f} ms  (avg {total_latency/max(1,len(records)):.1f} ms/call)")
    else:
        print("No LLM calls logged.")

    print(f"\nFull results written to {os.path.join(OUT_DIR, 'run_results.json')}")


if __name__ == "__main__":
    main()
