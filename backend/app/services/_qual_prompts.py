"""Prompt templates for the L2 qualitative summary layer.

v2.1 (2026-05): trimmed and hardened after v2 regressed on qwen2.5:7b.
v2 was longer than v1 with XML ceremony and a compressed-JSON few-shot;
qwen responded with truncated output, Chinese drift, and stringified-dict
positives. v2.1 removes the ceremony, pretty-prints the few-shot output so
the model can actually parse the example structure, and adds an explicit
"plain strings, not objects" rule for positives/risks.

- PROMPT_VERSION is bumped whenever the system prompt or output schema
  changes in a way that would invalidate cached DocumentSummary rows.
- The number-guard in qualitative.py is a safety net for hallucinated
  numbers; the prompt is the primary defence.
"""

from __future__ import annotations

from backend.app.models.rag import RetrievedChunk


PROMPT_VERSION = "qual-v2.1"


_OUTPUT_SCHEMA = """\
{
  "tone": "positive | neutral | cautious | negative | mixed",
  "thesis": "string, <=600 chars",
  "positives": ["string <=240 chars", "..."],
  "risks": ["string <=240 chars", "..."],
  "guidance_flavor": "raised | reaffirmed | lowered | withdrawn | none_mentioned",
  "evidence_quality": "strong | moderate | thin"
}"""


# Pretty-printed JSON in the example so the model imitates its structure
# correctly. Derived from a real NVDA 10-K run.
_FEW_SHOT_EXAMPLE = """\
EXAMPLE INPUT:
TICKER: NVDA
FILING EXCERPTS:
[1] "Revenue for fiscal year 2026 was $215.9 billion, up 65% from a year ago,
driven by major platform shifts in AI and accelerated computing. Data Center
revenue grew 68%."
[2] "Our business is exposed to macroeconomic factors including tariffs,
inflation, and global supply chain constraints, any of which could impact
operations or margins."

EXAMPLE OUTPUT:
{
  "tone": "positive",
  "thesis": "NVIDIA delivered a step-change year with revenue up 65% to $215.9 billion on the AI and accelerated-computing platform shift, led by a 68% jump in Data Center, while flagging macro and supply-chain pressures as the main offsets.",
  "positives": [
    "Fiscal 2026 revenue reached $215.9 billion, up 65% year over year",
    "Data Center segment grew 68%, the dominant contributor to growth",
    "AI and accelerated-computing platform shift driving demand"
  ],
  "risks": [
    "Tariffs, inflation, and global supply chain constraints could pressure operations",
    "Concentration in AI/accelerated computing leaves results sensitive to platform-shift timing"
  ],
  "guidance_flavor": "none_mentioned",
  "evidence_quality": "moderate"
}"""


SYSTEM_PROMPT = f"""\
You are an investment research assistant. You read filing excerpts and produce
a concise qualitative summary as a single JSON object.

Schema:
{_OUTPUT_SCHEMA}

Rules:
1. Reply with ONLY one flat JSON object. No prose, no markdown fences, no
   wrapper keys. Top-level keys must be exactly: tone, thesis, positives,
   risks, guidance_flavor, evidence_quality.
2. positives and risks are arrays of PLAIN STRINGS (2-5 items each, each
   <=240 chars). Never emit objects, dicts, or key/value pairs inside these
   arrays. Just write the point as a sentence.
3. Stay grounded. Every claim must be supported by text in the FILING
   EXCERPTS. A number (revenue, EPS, growth %, etc.) may appear in your
   output ONLY if it appears verbatim in the excerpts.
4. Do NOT use audit, SOX, or disclosure-controls language as a positive
   (e.g. "internal control was effective", "financial statements fairly
   presented"). Positives are about business performance, segment growth,
   product traction, or strategic execution.
5. tone must match the thesis. If the excerpts describe strong growth use
   "positive"; if material decline use "negative" or "cautious". Reserve
   "neutral" for genuinely flat or balanced situations.
6. guidance_flavor: scan the excerpts for forward-looking language ("we
   expect", "we anticipate", "outlook", "for fiscal YEAR", "reaffirm",
   "raise", "lower", "withdraw"). Use none_mentioned only if no such
   language is present.
7. evidence_quality: strong if 4+ relevant chunks, moderate if 2-3, thin if
   fewer than 2. If thin, set thesis to "Insufficient filings retrieved to
   form a grounded view." and use minimal placeholders.
8. Reply in English regardless of any other language present in the excerpts.

{_FEW_SHOT_EXAMPLE}
"""


def build_user_prompt(
    ticker: str,
    chunks: list[RetrievedChunk],
    facts: dict | None = None,
) -> str:
    """Build the user-turn message for the qualitative summary call."""
    lines: list[str] = [f"TICKER: {ticker}", ""]

    if facts is not None:
        lines.append("FACTS (pre-validated; you may reference these numbers):")
        for key, value in facts.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

    lines.append("FILING EXCERPTS:")
    if chunks:
        for i, chunk in enumerate(chunks, 1):
            header = (
                f"[{i}] chunk_id={chunk.chunk_id} "
                f"filing_type={chunk.filing_type} "
                f"filing_date={chunk.filing_date} "
                f"score={chunk.score:.3f}"
            )
            lines.append(header)
            lines.append(chunk.text)
            lines.append("")
    else:
        lines.append("(no excerpts retrieved)")
        lines.append("")

    return "\n".join(lines)
