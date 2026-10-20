"""The agent layer. Four tools over the Phase 7 pipeline; a REPL so follow-ups share context.

    python agent.py resume.pdf
    python agent.py resume.pdf --trace     # OpenTelemetry spans to the console

The agent's job is to turn a messy ask into parameters, read a summary back, and explain. It never
sees raw listings, never scores, never re-runs the pipeline to answer a question it already has
the data for.
"""

import asyncio
import json
import sys
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

from config import settings
from models import ResumeProfile
from pipeline import Filters, RankedResult, Summary, rank_listings
from resume import load_profile
from score import explain

SYSTEM_PROMPT = """You help a software engineer find job listings that fit their résumé.

You have four tools. Python does all fetching, matching, and scoring; you choose parameters and
explain results.

- discover_boards: find company job boards for a role. Call this first unless the user named companies.
- rank_jobs: run the full pipeline on a set of boards with title/location filters. Returns a ranked
  summary. This is the expensive call — run it once per distinct search, not per question.
- explain_match: Reproduce each requirement with its status and the evidence line exactly as the table shows it. 
  One sentence of summary at the end is fine; do not add reasons, qualifiers, or judgments the table doesn't contain.
- filter_results: narrow the current results without re-running anything. Use it for "drop X",
  "only remote", "score above N".

Rules:
- Never state or estimate a score yourself. Scores come only from rank_jobs.
- Do not pass location to rank_jobs unless the user insists. Location strings are
     inconsistent; rank everything, then narrow with filter_results so nothing is lost.
-  If fewer than 5 ranked results, widen once on your own (drop location, add
     title terms like "software" "developer" "backend"), then present what you have
     and say what you changed. Do not ask permission to widen.
- Present results as a short ranked list: score, company, title, and the blocked reason if any.
- Entry/mid-level is the default. Keep the default title_none exclusions unless the user asks.
- Run rank_jobs at most twice per user request: once as asked, once widened if thin.
  After that, present what you have and say what's missing.
- "Remote" in the location field is rare even for remote-eligible roles. Do not treat
  "few remote results" as thin; present the full ranked list and point out which
  locations mention "United States" or "Remote".
- Plain text. No markdown tables, headers, or emoji. Keep it short.
"""

# Shared state across tool calls in one session. A single-user REPL; nothing fancier needed.
_profile: ResumeProfile | None = None
_last: RankedResult | None = None
_view: list[
    Summary
] = []  # current (possibly filtered) ranked list; ranks refer to this

# Phase 9 replaces this with Tavily discovery. Until then, a seed list.
SEED_BOARDS = {
    "default": ["cloudflare", "figma", "discord", "duolingo", "databricks"],
}


@tool
def discover_boards(role: str, limit: int = 5) -> str:
    """Find Greenhouse board slugs for companies hiring for a role.

    Args:
        role: the kind of role, e.g. "backend engineer", "frontend", "software engineer".
        limit: maximum number of boards to return.
    """
    slugs = SEED_BOARDS["default"][:limit]
    return f"boards for '{role}': {', '.join(slugs)}  (seed list; live discovery not yet enabled)"


@tool
async def rank_jobs(
    boards: list[str],
    title_any: list[str] | None = None,
    title_none: list[str] | None = None,
    location: str | None = None,
    per_board: int = 10,
) -> str:
    """Fetch listings from the given boards, match each against the résumé, and return a ranked summary.

    Args:
        boards: Greenhouse board slugs, from discover_boards or named by the user.
        title_any: keep listings whose title contains any of these (default: ["engineer"]).
        title_none: drop listings whose title contains any of these (default: senior/staff/lead/manager/intern).
        location: keep only listings whose location contains this text, e.g. "remote", "austin".
        per_board: max listings to evaluate per board (cost control).
    """
    global _last, _view
    kw = {"per_board": per_board, "location": location}
    if title_any:
        kw["title_any"] = title_any
    if title_none:
        kw["title_none"] = title_none
    _last = await rank_listings(_profile, boards, Filters(**kw))
    _view = list(_last.ranked)
    return _render(_view, _last)


@tool
def explain_match(rank: int) -> str:
    """Show the requirement → status → evidence table for one listing in the current ranked list.

    Args:
        rank: 1-based position in the most recent ranked list shown.
    """
    if not _view:
        return "No results yet. Run rank_jobs first."
    if not 1 <= rank <= len(_view):
        return f"rank must be between 1 and {len(_view)}."
    s = _view[rank - 1]
    return explain(_last.results[s.listing_id], _last.listings[s.listing_id])


@tool
def filter_results(
    exclude_keywords: list[str] | None = None,
    location: str | None = None,
    min_score: float | None = None,
) -> str:
    """Narrow the ranked list without re-running the pipeline. Each call filters the FULL ranked
    list, so pass every criterion you want together; calling with no arguments resets to the full list.

    Args:
        exclude_keywords: drop listings whose title, company, or location contains any of these.
        location: keep only listings whose location contains this text.
        min_score: keep only listings scoring at or above this.
    """
    global _view
    if not _last:
        return "No results yet. Run rank_jobs first."
    out = []
    for s in _last.ranked:
        loc = (_last.listings[s.listing_id].location or "").lower()
        hay = f"{s.title} {s.company} {loc}".lower()
        if exclude_keywords and any(k.lower() in hay for k in exclude_keywords):
            continue
        if location and location.lower() not in loc:
            continue
        if min_score is not None and s.score < min_score:
            continue
        out.append(s)
    _view = out
    return _render(
        _view, _last, header=f"{len(out)} of {len(_last.ranked)} after filtering"
    )


def _render(view: list[Summary], res: RankedResult, header: str | None = None) -> str:
    lines = [
        header
        or f"{res.fetched} fetched · {res.considered} considered · {res.model_calls} model calls · {res.seconds}s"
    ]
    for i, s in enumerate(view, 1):
        loc = res.listings[s.listing_id].location or "—"
        lines.append(
            f"{i:2}. {s.score:5.1f}  {s.company} — {s.title}  [{loc}]  ({s.met}/{s.partial}/{s.unmet})"
        )
    if not view:
        lines.append("(nothing ranked)")
    if res.blocked and header is None:
        lines.append("blocked:")
        for s in res.blocked[:10]:
            lines.append(
                f"    {s.score:5.1f}  {s.company} — {s.title}  ⛔ {'; '.join(s.blocked_by)}"
            )
    return "\n".join(lines)


def _show_tools(**kw):
    msg = kw.get("message")
    if not msg:
        return
    for block in msg.get("content", []):
        if "toolUse" in block:
            t = block["toolUse"]
            print(f"  → {t['name']}({json.dumps(t['input'])})", file=sys.stderr)
        elif "toolResult" in block:
            text = " ".join(
                c.get("text", "") for c in block["toolResult"].get("content", [])
            )
            first = text.splitlines()[0] if text else ""
            print(
                f"  ← {first[:100]}  ({len(text.splitlines())} lines)", file=sys.stderr
            )


def make_agent() -> Agent:
    return Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[discover_boards, rank_jobs, explain_match, filter_results],
        callback_handler=_show_tools,
    )


def main() -> None:
    global _profile
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--trace" in sys.argv:
        from strands.telemetry import StrandsTelemetry

        StrandsTelemetry().setup_console_exporter()

    _profile = load_profile(Path(args[0]) if args else Path("resume.pdf"))
    agent = make_agent()
    print("ready. e.g. 'find backend roles, remote, mid-level'   (ctrl-d to quit)\n")

    while True:
        try:
            ask = input("> ").strip()
        except EOFError:
            break
        if not ask:
            continue
        result = agent(ask)
        print(f"\n{result}\n")
        m = result.metrics.get_summary()
        tools = {
            k: v["execution_stats"]["call_count"]
            for k, v in m.get("tool_usage", {}).items()
        }
        usage = m.get("accumulated_usage", {})
        print(
            f"  [{m.get('total_cycles')} cycles · tools {tools} · {usage.get('totalTokens')} tokens]\n"
        )


if __name__ == "__main__":
    main()