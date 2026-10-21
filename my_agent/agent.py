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
from discover import discover

SYSTEM_PROMPT = """You help a software engineer find job listings that fit their résumé.

You have four tools. Python does all fetching, matching, and scoring; you choose parameters and
explain results.

- discover_boards: find company job boards for a role. Call this first unless the user named
  companies. Returns up to 15 boards.
- rank_jobs: run the full pipeline on a set of boards with title filters. Returns a ranked
  summary. This is the expensive call — run it once per distinct search, not per question.
- explain_match: the requirement-by-requirement evidence table for one listing. Use it for any
  "why" question; pass blocked=true for a listing in the blocked list. Reproduce each requirement
  with its status and evidence line exactly as the table shows it. One sentence of summary at the
  end is fine; do not add reasons, qualifiers, or judgments the table doesn't contain.
- filter_results: narrow the current results without re-running anything. Each call filters the
  full ranked list. Use it for "drop X", "only remote", "score above N".

Choosing boards:
- Choose at most 8 of the boards discover_boards returns, favoring companies that fit what the
  user said about industry, size, or location.
- After a search, your reply MUST begin with one line of the form:
  "Boards: <chosen slugs> — skipped <slug> (<reason>), <slug> (<reason>)."
  Then the ranked list, then blocked listings, then notes.

Running searches:
- Entry/mid-level is the default. Keep the default title_none exclusions unless the user asks.
- title_any terms must name a software role: "software engineer", "backend", "developer",
  "platform engineer". Never pass "engineer" or "software" alone; they match sales, support,
  and solutions roles and crowd out real matches.
- Do not pass location to rank_jobs unless the user insists. Location strings are inconsistent;
  rank everything, then narrow with filter_results so nothing is lost.
- The user is based in Oakland, CA. Unless they say otherwise, after rank_jobs use
  filter_results(exclude_keywords=[...]) to drop listings located outside the US, naming the
  countries/cities you excluded, and report how many were dropped.
- "Remote" in the location field is rare even for remote-eligible roles. Do not treat few remote
  results as thin; point out which locations mention "United States" or "Remote".
- If fewer than 5 ranked results, widen once on your own (add title terms like "software",
  "developer", "backend"), then present what you have and say what you changed. Do not ask
  permission to widen. Run rank_jobs at most twice per user request.

Presenting results:
- Never state or estimate a score yourself. Scores come only from rank_jobs.
- Show each listing as: score (met/partial/unmet) — company, title, location.
- Always report the blocked count with its score and the two or three highest-scoring blocked listings, quoting
  the requirement that blocked them in the posting's own words, so the user can decide whether
  to apply anyway.
- Never explain why a company has no results; report the count and stop.
- Notes: at most three lines. Each must point at something visible in the tool output
  (a location, a count, a blocked reason). No characterizations of the list as a whole.
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
def discover_boards(role: str, limit: int = 15) -> str:
    """Search for Greenhouse job boards of companies hiring for a role. Slow (30–90s); call once per role.

    Args:
        role: the kind of role, e.g. "backend engineer", "software engineer".
        limit: maximum number of boards to return, best first.
    """
    boards = discover(role, limit)
    if not boards:
        return f"no boards found for '{role}'; fall back to the seed list: {', '.join(SEED_BOARDS['default'])}"
    lines = [f"{len(boards)} boards for '{role}' (slug — company, open jobs):"]
    lines += [
        f"  {b.slug} — {b.company}, {b.matching} open matching roles ({b.jobs} total)"
        for b in boards
    ]
    return "\n".join(lines)


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
def explain_match(rank: int, blocked: bool = False) -> str:
    """Show the requirement → status → evidence table for one listing.

    Args:
        rank: 1-based position in the most recent ranked list shown.
        blocked: if true, rank refers to the blocked list instead of the ranked list.
    """
    source = _last.blocked if blocked else _view
    if not source:
        return "No results yet. Run rank_jobs first."
    if not 1 <= rank <= len(source):
        return f"rank must be between 1 and {len(source)}."
    s = source[rank - 1]
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