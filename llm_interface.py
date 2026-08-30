"""
Pluggable LLM interface for LUCID.

This is the ONLY place in the codebase that talks to an LLM. Every other module
calls generate() and doesn't know or care whether it hit Gemini or a stub.
This is what lets the whole pipeline (Detect/Attribute/Fuse/Act logic) be tested
end-to-end for $0, and lets us flip one config flag to use real Gemini calls
only when recording the actual demo.

It also logs telemetry (latency, approx tokens, approx cost) for every call,
satisfying the Round 2 "LLM economics" requirement.
"""

import time
import json
import os
import config


def _approx_tokens(text: str) -> int:
    # Rough heuristic: ~4 chars/token. Good enough for demo telemetry, not billing.
    return max(1, len(text) // 4)


def _log_telemetry(record: dict):
    os.makedirs(os.path.dirname(config.TELEMETRY_LOG_PATH), exist_ok=True)
    with open(config.TELEMETRY_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def _stub_generate(prompt: str, system: str = "", structured: dict = None) -> str:
    """
    Deterministic, template-style stand-in for an LLM call. Used so the pipeline
    is fully testable without hitting a real API.

    IMPORTANT: this does NOT parse the prompt text (that was the old, broken
    approach - it ended up echoing instruction lines meant for a real LLM,
    like "Do NOT assert a single confirmed cause...", as if they were content).
    Instead, callers pass a `structured` dict with the actual facts, and this
    builds a real templated narrative directly from those fields.
    """
    if not structured:
        return (
            "[STUB] No structured data was provided to render a narrative from. "
            "Set LUCID_LLM_MODE=gemini and provide GEMINI_API_KEY for real narration."
        )

    kpi = structured.get("kpi_label", "This KPI")
    region = structured.get("region")
    where = f" in {region}" if region and region != "All" else ""
    pct = structured.get("pct_change_wow")
    direction = "dropped" if (pct is not None and pct < 0) else "increased"
    what = f"{kpi}{where} {direction} {abs(pct):.1f}% vs. the prior period." if pct is not None else f"{kpi}{where} moved outside its normal range."

    driver = structured.get("driver")
    driver_confidence = structured.get("driver_confidence")
    evidence_texts = structured.get("evidence_texts", [])
    is_verified_driver = structured.get("is_verified_driver", False)

    if driver and is_verified_driver:
        why = f"The most likely cause is **{driver}** ({driver_confidence:.0%} relative confidence), based on: " + "; ".join(evidence_texts[:2]) + "."
    elif evidence_texts:
        why = "No single cause was statistically confirmed, but evidence found near this time period may be related: " + "; ".join(evidence_texts[:2]) + "."
    else:
        why = "No supporting evidence was found or provided, so a specific cause cannot be identified from the data alone."

    so_what = structured.get("so_what", "This is a large enough movement to warrant attention before it compounds further.")
    now_what = structured.get("now_what", "Review the evidence above and confirm with the relevant owner before taking action.")

    return (
        f"**What:** {what}\n\n"
        f"**Why:** {why}\n\n"
        f"**So what:** {so_what}\n\n"
        f"**Now what:** {now_what}"
    )


def _gemini_generate(prompt: str, system: str = "") -> str:
    from google import genai
    from google.genai import types

    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "LUCID_LLM_MODE=gemini but GEMINI_API_KEY is not set. "
            "export GEMINI_API_KEY=... first."
        )
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system or None),
    )
    return response.text


def generate(prompt: str, system: str = "", tag: str = "narrate", structured: dict = None) -> dict:
    """
    Returns {"text": ..., "latency_ms": ..., "approx_tokens": ..., "backend": ...}
    and appends a telemetry record. `tag` identifies which pipeline stage called
    this (e.g. "narrate", "attribute_reasoning") for cost breakdowns. `structured`
    is only used by the stub backend (see _stub_generate) - the real Gemini
    backend uses the full prompt text as normal.
    """
    start = time.time()
    if config.LLM_MODE == "gemini":
        text = _gemini_generate(prompt, system)
        backend = config.GEMINI_MODEL
    else:
        text = _stub_generate(prompt, system, structured=structured)
        backend = "stub"
    latency_ms = round((time.time() - start) * 1000, 1)

    approx_tokens_in = _approx_tokens(prompt + system)
    approx_tokens_out = _approx_tokens(text)
    # Illustrative Gemini Flash pricing used only for the demo's cost telemetry.
    # Illustrative gemini-3.6-flash pricing (~$1.50/M input, ~$7.50/M output as of Aug 2026)
    # used only for the demo's cost telemetry - check ai.google.dev for current rates.
    est_cost_usd = round((approx_tokens_in * 0.0000015) + (approx_tokens_out * 0.0000075), 6)

    record = {
        "tag": tag,
        "backend": backend,
        "latency_ms": latency_ms,
        "approx_tokens_in": approx_tokens_in,
        "approx_tokens_out": approx_tokens_out,
        "est_cost_usd": est_cost_usd,
        "timestamp": time.time(),
    }
    _log_telemetry(record)

    return {"text": text, **record}
