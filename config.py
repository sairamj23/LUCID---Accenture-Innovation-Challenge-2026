"""
LUCID prototype configuration.

LLM_MODE controls which backend narrate.py / attribute.py's retrieval-reasoning use:
  "stub"   -> free, deterministic, template-based text. Use for all dev/testing.
  "gemini" -> real call to Google Gemini API. Only flip this for the final demo
              recording, so you don't burn API quota/tokens while iterating.

To use gemini mode, set an env var: export GEMINI_API_KEY="your-key"
"""

import os

LLM_MODE = os.environ.get("LUCID_LLM_MODE", "stub")  # "stub" or "gemini"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Materiality thresholds (Detect stage)
Z_SCORE_CRITICAL = 2.5
Z_SCORE_WATCH = 1.5

# Confidence below which LUCID abstains / presents competing explanations
ABSTENTION_CONFIDENCE_THRESHOLD = 0.55

# Feedback store
FEEDBACK_DB_PATH = os.path.join(os.path.dirname(__file__), "outputs", "feedback.db")

# Telemetry log
TELEMETRY_LOG_PATH = os.path.join(os.path.dirname(__file__), "outputs", "telemetry.jsonl")
