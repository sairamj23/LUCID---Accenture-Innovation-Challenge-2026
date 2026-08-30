"""
LUCID Streamlit app — simplified UI layer.

Same two modes and same underlying pipeline calls as before. What changed is
presentation only: raw tables, z-scores, and LLM telemetry are now tucked
into a collapsed "Technical details" section instead of always being on
screen, and the main flow reads in plain language first.

No pipeline logic lives in this file - it only calls fuse/detect/attribute/
narrate/act, same as main.py does headlessly.

Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import json
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import fuse, detect, attribute, narrate, act
import feedback_store
import config

st.set_page_config(page_title="LUCID - KPI Intelligence Engine", layout="wide")


def plain_summary(d: dict) -> str:
    """Turns a detection dict into one plain-English sentence."""
    label = d["kpi"].replace("_", " ").title()
    region = d["region"]
    where = f" ({region})" if region != "All" else ""
    if d["classification"] == "insufficient_history":
        return f"{label}{where} is too new to analyze yet — only {d['n_observations']} data points so far."
    pct = d.get("pct_change_wow")
    if pct is None:
        return f"{label}{where} moved outside its normal range."
    direction = "dropped" if pct < 0 else "rose"
    severity = "sharply" if d["classification"] == "critical" else "somewhat"
    return f"{label}{where} {direction} {severity} — {abs(pct):.1f}% vs. last period, well outside its usual range."


st.title("LUCID")
st.caption("Upload KPI data → LUCID finds what went wrong and what to do about it.")

mode = st.radio("Data source", ["Upload your own data", "Sample data (full demo)"], horizontal=True)

long_df, evidence_source, contract, sources = None, None, None, None
kpi_meta_lookup = {}

# ---------------------------------------------------------------------------
# MODE 1: Upload your own data
# ---------------------------------------------------------------------------
if mode == "Upload your own data":
    c1, c2 = st.columns(2)
    with c1:
        kpi_file = st.file_uploader("Your KPI data (CSV)", type="csv")
    with c2:
        evidence_file = st.file_uploader(
            "Optional: supporting notes (CSV)", type="csv",
            help="Needs a date column and a text column. If your notes contain commas, "
                 "wrap them in quotes in the CSV so columns don't shift.",
        )

    if not kpi_file:
        st.info("Upload a CSV to begin — needs a date column and at least one numeric column, e.g. `date, region, revenue`.")
        st.stop()

    try:
        raw = pd.read_csv(kpi_file)
        long_df, meta = fuse.parse_uploaded_kpi_csv(raw)
    except Exception as e:
        st.error(f"Couldn't read this file: {e}")
        st.stop()

    for k in meta["numeric_cols"]:
        kpi_meta_lookup[k] = k.replace("_", " ").title()

    if evidence_file:
        try:
            ev_raw = pd.read_csv(evidence_file)
            evidence_source = fuse.parse_uploaded_evidence_csv(ev_raw)
        except Exception as e:
            st.warning(f"Couldn't read the notes file ({e}) — continuing without it.")

    with st.expander("Technical details: what LUCID detected in your file"):
        st.write(f"Date column: `{meta['date_col']}` · KPI columns: {', '.join(meta['numeric_cols'])}" +
                 (f" · Segment column: `{meta['segment_col']}`" if meta['segment_col'] else " · No segment column found."))
        st.dataframe(long_df.tail(10), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# MODE 2: Sample data
# ---------------------------------------------------------------------------
else:
    @st.cache_data
    def get_sources():
        return fuse.load_sources()

    @st.cache_data
    def get_contract():
        return fuse.load_contract()

    sources = get_sources()
    contract = get_contract()
    long_df = sources["revenue"]
    for k in [x for x in contract if not x.startswith("_")]:
        kpi_meta_lookup[k] = contract[k]["definition"]

    with st.expander("Technical details: source data"):
        f1, f2, f3 = st.columns(3)
        with f1:
            st.caption(f"revenue.csv — {len(sources['revenue']):,} rows")
            st.dataframe(sources["revenue"].tail(5), use_container_width=True, hide_index=True, height=140)
        with f2:
            st.caption(f"tickets.csv — {len(sources['tickets']):,} rows")
            st.dataframe(sources["tickets"].tail(5), use_container_width=True, hide_index=True, height=140)
        with f3:
            st.caption(f"memos.csv — {len(sources['memos']):,} rows")
            st.dataframe(sources["memos"][["date", "source", "region"]].tail(5), use_container_width=True, hide_index=True, height=140)

# ---------------------------------------------------------------------------
# Scan everything, show only what's actually wrong, in plain language
# ---------------------------------------------------------------------------
st.header("What went wrong")

all_detections = []
for (kpi, region), grp in long_df.groupby(["kpi", "region"]):
    all_detections.append(detect.detect_movement(grp, kpi, region))

scan_df = pd.DataFrame(all_detections)
severity_order = {"critical": 0, "watch": 1, "insufficient_history": 2, "normal": 3}
scan_df["_sort"] = scan_df["classification"].map(severity_order)
scan_df = scan_df.sort_values(["_sort", "confidence"], ascending=[True, False]).drop(columns="_sort")

flagged = scan_df[scan_df["classification"].isin(["critical", "watch", "insufficient_history"])]
icon = {"critical": "🔴", "watch": "🟡", "insufficient_history": "⚪"}

if flagged.empty:
    st.success("Everything looks normal — no issues found.")
    st.stop()

for row in flagged.itertuples():
    st.markdown(f"{icon[row.classification]}&nbsp;&nbsp;{plain_summary(row._asdict())}")

with st.expander(f"Technical details: full scan ({len(scan_df)} KPI/segment combinations checked)"):
    disp = scan_df.copy()
    disp["classification"] = disp["classification"].apply(lambda c: c.replace("_", " ").title())
    disp["confidence"] = (disp["confidence"] * 100).round(0).astype(int).astype(str) + "%"
    disp = disp[["kpi", "region", "classification", "pct_change_wow", "confidence", "n_observations"]]
    disp.columns = ["KPI", "Segment", "Status", "Change %", "Confidence", "Data points"]
    st.dataframe(disp, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Pick one issue to dig into
# ---------------------------------------------------------------------------
st.header("Look into an issue")

options = [f"{row.kpi.replace('_',' ').title()} — {row.region}" for row in flagged.itertuples()]
choice = st.selectbox("Which one?", options)
sel_row = flagged.iloc[options.index(choice)]
kpi, region = sel_row["kpi"], sel_row["region"]
detection = sel_row.to_dict()

persona_options = ["Analyst", "Ops Lead", "Finance Lead", "Product Lead"] if mode == "Upload your own data" \
    else list(contract["_entitlements"].keys())
persona = st.selectbox("Show this to", persona_options)

series = long_df[(long_df["kpi"] == kpi) & (long_df["region"] == region)].sort_values("week")
all_weeks = sorted(series["week"].unique())
window = all_weeks[-2:] if len(all_weeks) >= 2 else all_weeks
window_start, window_end = (pd.Timestamp(window[0]), pd.Timestamp(window[-1])) if window else (None, None)

st.subheader(plain_summary(detection))
st.line_chart(series.set_index("week")["value"])

with st.expander("Technical details: how this was measured"):
    st.write(detection["rationale"])
    st.write(f"Classification: **{detection['classification']}** · Confidence: **{detection['confidence']:.0%}**")

# --- entitlement check (sample mode only) ---
if mode == "Sample data (full demo)":
    access_check = act.build_recommendation(detection, {"ranked_drivers": [{"driver": "n/a"}]}, persona)
    if access_check.get("access_denied"):
        st.error(f"🔒 {persona} doesn't have access to this KPI. ({access_check['reason']})")
        st.stop()

if mode == "Upload your own data":
    evidence = fuse.retrieve_evidence_generic(evidence_source, region, window_start, window_end) if evidence_source is not None else []
    attribution = attribute.rank_drivers_generic(evidence)
    story = narrate.narrate_generic(detection, evidence, persona, kpi_meta_lookup.get(kpi, kpi))
    rec_result = act.build_recommendation_generic(detection, evidence)
    seg, ranked = None, []
else:
    evidence = fuse.retrieve_evidence(sources, region, window_start, window_end)
    attribution = attribute.rank_drivers(evidence, kpi=kpi)
    seg = attribute.segment_decomposition(long_df, kpi, all_weeks[-2:]) if region != "All" else None
    ranked = attribution["ranked_drivers"]
    story = narrate.narrate(detection, attribution, evidence, persona, kpi_meta_lookup.get(kpi, kpi))
    rec_result = act.build_recommendation(detection, attribution, persona)

st.markdown("#### What's likely going on")
if story["abstained"]:
    st.warning(story["narrative"])
else:
    st.info(story["narrative"])

with st.expander("Technical details: evidence & driver scoring"):
    if evidence:
        st.write("Evidence found near this movement:")
        for e in evidence:
            st.markdown(f"- *{e['citation']}*" + (f' — "{e.get("text","")[:150]}"' if e.get("text") else ""))
    else:
        st.caption("No supporting evidence found or provided.")
    if seg:
        st.write("Which segment drove the change:")
        st.bar_chart(pd.DataFrame(list(seg.items()), columns=["Segment", "% of movement"]).set_index("Segment"))
    if ranked:
        ddf = pd.DataFrame(ranked)[["driver", "relative_confidence", "supporting_evidence"]]
        ddf["relative_confidence"] = (ddf["relative_confidence"] * 100).round(0).astype(int).astype(str) + "%"
        ddf["supporting_evidence"] = ddf["supporting_evidence"].apply(lambda ev: "; ".join(ev) if ev else "—")
        ddf.columns = ["Candidate cause", "Confidence", "Supporting evidence"]
        st.dataframe(ddf, use_container_width=True, hide_index=True)
    if story.get("llm_call"):
        lc = story["llm_call"]
        st.caption(f"LLM: `{lc['backend']}` · {lc['latency_ms']}ms · ${lc['est_cost_usd']:.6f}")

st.markdown("#### What to do")
rec = rec_result.get("recommendation")
if rec is None:
    st.caption(rec_result.get("reason", "No action needed."))
else:
    st.markdown(f"**{rec['action']}**")
    st.caption(f"Owner: {rec['owner']}  ·  Confidence: {rec['confidence']:.0%}")
    with st.expander("Technical details: full recommendation"):
        st.write(f"Driver: {rec['driver']}")
        st.write(f"Lever: {rec['controllable_lever']}")
        st.write(f"Expected impact: {rec['expected_impact']}")
        st.write(f"Monitoring plan: {rec['monitoring_plan']}")

    fb1, fb2 = st.columns(2)
    driver_key = rec["driver"] if mode == "Sample data (full demo)" else f"generic::{kpi}"
    if fb1.button("✅ This is right", use_container_width=True):
        feedback_store.record_feedback(kpi, driver_key, "accept", persona=persona)
        st.success("Thanks — recorded.")
    if fb2.button("❌ This is wrong", use_container_width=True):
        feedback_store.record_feedback(kpi, driver_key, "reject", persona=persona)
        st.warning("Recorded — LUCID will weigh this differently next time.")
