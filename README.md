# LUCID — Language-driven Understanding & Causal Insight Discovery

**Accenture Innovation Challenge 2026 — Round 2 - Team Reinventors**  
**Problem Statement:** BusinessIntelligence.ai (PS-3)

LUCID is a working prototype that converts KPI anomalies into **evidence-backed explanations and actionable recommendations**. Instead of stopping at *“revenue is down 8%”*, it determines whether the change is statistically significant, identifies and ranks likely drivers, retrieves supporting evidence, explains the finding for the relevant persona, and recommends a concrete next action.

---

## Prototype Overview

LUCID implements the core mechanism proposed in our Round 2 solution through a five-stage pipeline:

**Fuse → Detect → Attribute → Narrate → Act**

- **Fuse** — Ingests KPI data and supporting evidence from structured and unstructured sources.
- **Detect** — Statistically identifies genuine anomalies and separates them from insufficient-history cases.
- **Attribute** — Ranks likely drivers using deterministic rules, segment decomposition, and retrieved evidence.
- **Narrate** — Converts verified findings into a concise, persona-specific explanation with supporting citations. This is the **only stage that uses an LLM**.
- **Act** — Converts the identified driver into a structured recommendation with an owner, expected impact, confidence, and monitoring plan.

### Design Principle

**The LLM does not determine what is true.** Quantitative values, anomaly detection, classifications, and driver rankings are computed before the LLM is called. The LLM is used only to communicate already-verified findings in a role-appropriate form.

The prototype also demonstrates **feedback-driven driver reweighting, role-based entitlement enforcement, and LLM cost/latency telemetry**.

**Two ways to use it:**
1. **Upload your own data** — real CSV upload, auto-detects KPIs and segments, works on data it has never seen before.
2. **Sample data (full demo)** — a curated dataset that demonstrates the fuller required feature set (persona-specific narratives, ranked driver attribution, security/entitlement scenario, sparse-history handling) which needs a predefined KPI contract to work.

---

## Quick start

```bash
git clone <this-repo-url>
cd lucid_prototype
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python data/generate_data.py      # generates the sample dataset
streamlit run app.py              # launches the UI at http://localhost:8501
```

No API key required — it runs on a free, offline stub LLM backend by default. See [Using real Gemini narration](#using-real-gemini-narration) to enable live calls.

You can also run the full pipeline headlessly (no UI), which prints all 6 built-in demo scenarios:
```bash
python main.py
```

---

## Project structure

```
lucid_prototype/
├── app.py                    # Streamlit UI — upload mode + sample-data mode
├── main.py                   # Headless runner — 6 scenarios end to end
├── config.py                 # LLM mode toggle, thresholds
├── llm_interface.py          # The ONLY file that calls an LLM (stub or Gemini)
├── feedback_store.py         # Persists accept/reject/correct, reweights future runs
├── semantic_contract.json    # KPI definitions, grains, owners, entitlements
├── data/
│   └── generate_data.py      # Synthetic data generator (sample-data mode)
├── pipeline/
│   ├── fuse.py                # Loads sources; parses uploaded CSVs; retrieves evidence
│   ├── detect.py              # Statistical anomaly detection (z-score, no LLM)
│   ├── attribute.py           # Driver ranking / segment decomposition (no LLM)
│   ├── narrate.py             # Persona-specific narrative (the only LLM-calling stage)
│   └── act.py                 # Structured recommendation + entitlement checks
└── outputs/                   # Generated at runtime: telemetry, feedback logs
```

---

## How it works

### The 5 stages

| Stage | What it does | Uses an LLM? |
|---|---|---|
| **Fuse** | Loads KPI data + evidence sources (support tickets, memos), or an uploaded CSV | No |
| **Detect** | Z-score anomaly detection against trailing history; flags insufficient-history KPIs separately | No |
| **Attribute** | Ranks candidate causes by evidence support; computes segment decomposition (e.g. which region drove the change) | No |
| **Narrate** | Turns the already-computed facts into a persona-specific story, with citations. Abstains (skips the LLM call) if confidence is low or evidence is ambiguous | **Yes — only stage that does** |
| **Act** | Builds a structured recommendation (driver → lever → action → impact → owner → confidence → monitoring plan); enforces role-based entitlements | No |

**Core design rule:** the LLM is never the source of quantitative truth. All numbers, classifications, and driver rankings are computed by statistics and rule-based logic before the LLM is ever called — its only job is to phrase already-verified facts, never to decide what's true.

### Upload mode vs. sample-data mode

Upload mode works on any CSV (auto-detects date/KPI/segment columns) but is intentionally honest about its limits: with no predefined domain knowledge, it can flag *that* something moved and cite *nearby* evidence, but can't invent a specific named cause, owner, or business lever it has no basis for.

Sample-data mode uses a maintained `semantic_contract.json` (KPI definitions, owners, access rules) and a curated evidence set, which is what allows the fuller behaviors — ranked driver attribution with confidence scores, specific lever-mapped recommendations, and entitlement enforcement.

### The 6 built-in demo scenarios (sample-data mode, via `python main.py`)

| Scenario | What it proves |
|---|---|
| A — Northeast revenue drop | High-confidence, multi-factor attribution (carrier delay correctly isolated over red herrings) |
| B — Product engagement dip | Genuine ambiguity — two causes score too close to call, system presents both instead of guessing |
| C — New feature adoption | Sparse history (only 3 data points) — system refuses to force a confidence score |
| D — Entitlement check | Product Lead correctly denied access to a Finance-owned KPI |
| E — SMB churn spike | Multi-segment decomposition by customer tier |
| F — Social conversion drop | Multi-segment decomposition by marketing channel, new driver type |

### Feedback loop

Accepting, rejecting, or correcting a recommendation in the UI persists to `outputs/driver_weight_adjustments.json` and measurably changes driver scoring on the next run — this is a real mechanism, not a logged-but-unused event.

### Telemetry

Every LLM call logs backend, latency, approximate token count, and estimated cost to `outputs/telemetry.jsonl`, summarized at the end of every `main.py` run and visible in the app's telemetry panel.

---

## Using real Gemini narration

By default, `LUCID_LLM_MODE=stub` — a free, instant, template-based response used for all development and testing. To use real Gemini calls (recommended only when recording a final demo, to conserve API usage):

```bash
export GEMINI_API_KEY="your-key"        # get one free at aistudio.google.com/apikey
export LUCID_LLM_MODE=gemini
streamlit run app.py
```

---

## Known limitations (stated explicitly, not hidden)

- **Retrieval** is keyword + date-window matching, not embedding-based semantic search. Sufficient to prove the mechanism; a production system would swap this for a vector search, same interface.
- **Upload mode** cannot assign a specific business lever or owner for unknown data — this is a deliberate honesty constraint, not an oversight (see "Upload mode vs. sample-data mode" above).
- **Feedback mechanism** uses simple weight nudges (+/- per accept/reject/correct) rather than a trained model — proves the mechanism at prototype scale; a production version would use a proper ML model over accumulated feedback.
- Evidence sources are limited to two types (structured KPI table + free-text memos/tickets) in the sample data; the schema generalizes to more source types without pipeline changes.

---

## Team / Submission

Built for Accenture Innovation Challenge 2026, Round 2 — BusinessIntelligence.ai (PS-3).
