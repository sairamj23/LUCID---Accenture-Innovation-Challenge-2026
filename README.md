# LUCID — Language-driven Understanding & Causal Insight Discovery

**Team Reinventors** · Accenture Innovation Challenge '26 · PS-3, BusinessIntelligence.ai

A single-file, zero-dependency prototype that turns a raw KPI dataset into cited,
confidence-scored, plain-English explanations — automatically.

**Live logic:** load any dataset → LUCID detects the KPI(s), the time axis, and the
categorical dimensions on its own → scans every KPI for statistically real deviations →
attributes each one to the segment most responsible → writes a grounded
**What / Why / So What / Now What** story → routes it for a human accept / reject / correct
decision that recalibrates the next scan.

---

## Why this shape

The problem statement's own diagnosis is that BI tools show correlation, not causation, and
that turning an anomaly into an explanation is a manual, days-long process. A prototype that
only worked on the one illustrative example ("revenue dropped 8% in a region") would just be
restating the pitch. This build is deliberately **dataset-agnostic**: point it at *any* table
with a time/period column, some numeric metrics, and a few categorical dimensions, and it
runs the same five-stage pipeline end to end.

## Solution architecture

```
FUSE          →   DETECT              →   ATTRIBUTE            →   NARRATE              →   ACT
CSV parsed,       Per-KPI time series,     Segment decomposition     Templated LLM-style       Routed to owner,
schema auto-          period-over-period       across every              narrative, every           accept/reject/
detected             % change, adaptive        categorical                clause grounded in         correct feeds
(time col,           z-score gate               dimension, ranked          a computed, cited          back into
KPIs, dims)          separates signal            by explanatory              number — never a          per-dimension
                     from normal noise            share                        free-floating claim       confidence weights
```

**1. FUSE — schema inference.** The CSV is parsed and every column is scored: date-format
match rate, numeric rate, cardinality. From that, LUCID picks the time column (strict date
patterns, or a name-hinted ordinal like "Week 12"), the KPI candidates (numeric, non-ID,
varying), and the dimension candidates (bounded-cardinality categoricals) — no schema is
hard-coded.

**2. DETECT — signal vs. noise.** For each KPI, LUCID builds the period-over-period series,
computes the mean and standard deviation of historical % changes, and flags a period only when
its z-score clears an adjustable threshold (Loose / Standard / Strict). This is the "separate a
meaningful shift from ordinary noise" requirement — a fixed % threshold would flag any volatile
metric constantly; an adaptive, distribution-aware gate does not.

**3. ATTRIBUTE — correlation → cause, honestly.** For a flagged anomaly, LUCID decomposes the
total change across every categorical dimension, computing each segment's share of the delta.
If one segment explains the majority of the swing, it's named as the driver. **If no segment
clears a concentration threshold, LUCID does not force an answer** — it surfaces the top
competing candidates side by side and says so. That's the "stay honest when evidence is
ambiguous" requirement, implemented rather than asserted.

**4. NARRATE — grounded story generation.** Every clause in the What/Why/So-What/Now-What
narrative is filled from the actual computed numbers (previous vs. current totals, z-score,
segment contribution %) and each is tagged with an inline evidence citation you can expand —
nothing is invented. The confidence badge on each card is a blend of statistical significance
(z-score magnitude) and attribution concentration, so a leader can tell at a glance whether to
trust the story or dig further.

**5. ACT — feedback loop.** Confirm / Reject / Correct on any insight is logged to the Evidence
Log and adjusts that dimension's weight for future scans — a lightweight, in-session stand-in
for the "leader feedback recalibrates the model" mechanism in the full proposal.

## What's simulated vs. real in this prototype

- **Real:** CSV parsing, schema inference, statistical anomaly detection, segment
  decomposition/attribution, confidence scoring, narrative templating, the feedback →
  reweighting loop. All of this runs live, in the browser, on whatever data you load.
- **Simulated for the demo:** the "FUSE" stage in the full LUCID vision also ingests
  unstructured sources (support tickets, news, call transcripts) via retrieval. This prototype
  fuses structured tabular data only; the pipeline ribbon and architecture are built so an
  unstructured-retrieval stage slots into ATTRIBUTE without changing anything downstream.
- The NARRATE step here is a grounded template engine, not a live LLM call — every number it
  cites is real, but the prose isn't model-generated. Swapping in an actual LLM call (e.g. the
  Claude API) to turn the same structured evidence bundle into prose is the natural next
  increment, and the evidence bundle is already shaped for that hand-off.

## Dependencies

**None.** No build step, no npm install, no API keys, no external CDN calls — it's a single
HTML file with inline CSS and vanilla JavaScript (CSV parser included). This was a deliberate
choice for a judged demo: it has to run instantly, offline, on any machine.

## Execution instructions

1. Download `index.html` from this repo.
2. Open it in any modern browser (Chrome, Edge, Firefox, Safari).
3. Click **"Use sample dataset"** for an instant demo (a synthetic 16-week, multi-region,
   multi-product dataset with two injected anomalies), or drag your own CSV onto the drop zone.
4. Adjust sensitivity if needed, click **Run scan**, and expand any detected issue to see the
   full narrative, evidence, attribution chart, and feedback controls.
5. Switch to the **Evidence Log** tab to see the feedback/recalibration history.

No server, no installation, no configuration required.

## Team

- Sibani S — Biological Engineering, IIT Madras (2027)
- Sairam J — Biological Sciences, IIT Madras (2027)
- Sadhana R — Biological Engineering, IIT Madras (2028)
