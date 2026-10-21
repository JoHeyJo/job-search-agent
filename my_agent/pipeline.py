"""The whole harvest → extract → match → score run as one bounded, deterministic function.

    rank_listings(profile, boards, filters) -> RankedResult

This is what the agent will call in Phase 8. It takes parameters, fans out with a fixed
concurrency cap, and returns a summary. No model decides anything in here.
"""

import asyncio
import time
from dataclasses import dataclass, field

from pydantic import BaseModel

from config import settings
from greenhouse import fetch_board
from match import match_listing
from models import Listing, MatchResult, ResumeProfile, Status
from score import rank, score

SENIOR = ("senior", "staff", "principal", "lead", "manager", "director", "intern")
NOT_SWE = (
    "solutions",
    "solution",
    "sales",
    "customer",
    "support",
    "field",
    "channel",
    "capacity",
    "detection",
    "werkstudent",
    "recruit",
)


class Filters(BaseModel):
    """Cheap Python-side filters applied before any model call. This is the cost control."""

    title_any: list[str] = ["engineer"]  # keep if any of these appear in the title
    title_none: list[str] = list(SENIOR + NOT_SWE)  # drop if any of these appear in the title
    location: str | None = None  # substring match on location, if set
    per_board: int = 10  # max listings per board after filtering


class Summary(BaseModel):
    listing_id: str
    title: str
    company: str
    url: str
    score: float
    met: int
    partial: int
    unmet: int
    blocked_by: list[str] = []


@dataclass
class RankedResult:
    ranked: list[Summary]
    blocked: list[Summary]
    fetched: int
    considered: int
    model_calls: int
    seconds: float
    # Full data kept for follow-ups (explain_match, filter_results). Not for the model to read whole.
    results: dict[str, MatchResult] = field(default_factory=dict)
    listings: dict[str, Listing] = field(default_factory=dict)


def _keep(l: Listing, f: Filters) -> bool:
    t = l.title.lower()
    if f.title_any and not any(k in t for k in f.title_any):
        return False
    if any(k in t for k in f.title_none):
        return False
    if f.location and f.location.lower() not in (l.location or "").lower():
        return False
    return True


def _summarize(r: MatchResult, l: Listing) -> Summary:
    counts = {s: sum(m.status == s for m in r.matches) for s in Status}
    return Summary(
        listing_id=l.id,
        title=l.title,
        company=l.company,
        url=l.url,
        score=r.score,
        met=counts[Status.met],
        partial=counts[Status.partial],
        unmet=counts[Status.unmet],
        blocked_by=r.blocked_by,
    )


def _cache_count() -> int:
    n = 0
    for sub in ("requirements", "matches"):
        d = settings.data_dir / sub
        n += sum(1 for _ in d.glob("*.json")) if d.exists() else 0
    return n


async def rank_listings(
    profile: ResumeProfile, boards: list[str], filters: Filters | None = None
) -> RankedResult:
    f = filters or Filters()
    t0 = time.monotonic()
    cache_before = _cache_count()

    # 1. Harvest: all boards concurrently. fetch_board is sync + cached, so run it in threads.
    board_lists = await asyncio.gather(
        *(asyncio.to_thread(fetch_board, b) for b in boards)
    )
    fetched = sum(len(bl) for bl in board_lists)

    # 2. Filter in Python, drop duplicate postings, cap per board. Only these cost model calls.
    seen: set[tuple[str, str, str]] = set()
    listings: list[Listing] = []
    for bl in board_lists:
        kept = 0
        for l in bl:
            if not _keep(l, f):
                continue
            key = (l.company.lower(), l.title.lower(), (l.location or "").lower())
            if key in seen:
                continue
            seen.add(key)
            listings.append(l)
            kept += 1
            if kept >= f.per_board:
                break

    # 3. Extract + match, bounded. match_listing calls extract_requirements internally; both cached.
    sem = asyncio.Semaphore(settings.concurrency)

    async def one(l: Listing) -> MatchResult:
        async with sem:
            matches = await asyncio.to_thread(match_listing, profile, l)
        return score(l.id, matches)

    results = await asyncio.gather(*(one(l) for l in listings))

    # 4. Rank. Pure Python.
    by_id = {l.id: l for l in listings}
    ranked, blocked, _ = rank(list(results))

    return RankedResult(
        ranked=[_summarize(r, by_id[r.listing_id]) for r in ranked],
        blocked=[_summarize(r, by_id[r.listing_id]) for r in blocked],
        fetched=fetched,
        considered=len(listings),
        model_calls=_cache_count() - cache_before,
        seconds=round(time.monotonic() - t0, 1),
        results={r.listing_id: r for r in results},
        listings=by_id,
    )


def format_summary(res: RankedResult, top: int = 15) -> str:
    """Compact text the agent (and you) can read. The model never sees raw rows."""
    lines = [
        f"{res.fetched} fetched · {res.considered} considered · {res.model_calls} model calls · {res.seconds}s",
        "",
    ]
    for i, s in enumerate(res.ranked[:top], 1):
        lines.append(
            f"{i:2}. {s.score:5.1f}  {s.company} — {s.title}  ({s.met}/{s.partial}/{s.unmet})"
        )
    if res.blocked:
        lines.append("\nblocked:")
        for s in res.blocked[:top]:
            lines.append(
                f"    {s.score:5.1f}  {s.company} — {s.title}  ⛔ {'; '.join(s.blocked_by)}"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from resume import load_profile

    ap = argparse.ArgumentParser()
    ap.add_argument("resume", type=Path)
    ap.add_argument("boards", nargs="+", help="greenhouse board slugs")
    ap.add_argument(
        "--title",
        nargs="*",
        default=["engineer"],
        help="keep titles containing any of these",
    )
    ap.add_argument("--location", default=None)
    ap.add_argument("--per-board", type=int, default=10)
    a = ap.parse_args()

    profile = load_profile(a.resume)
    filters = Filters(title_any=a.title, location=a.location, per_board=a.per_board)
    res = asyncio.run(rank_listings(profile, a.boards, filters))
    print(format_summary(res))
