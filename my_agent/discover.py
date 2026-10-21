"""Role → Greenhouse board slugs, via Tavily. One public function: discover(role, limit) -> list[Board].

Mode B discovery: search the Greenhouse hostnames for the role, pull the board slug out of every
result URL, then verify each slug by actually fetching the board. "Verified" means the board API
answered with a company name and at least one live job — not just HTTP 200, since an empty board
also returns 200. Verified boards are appended to data/watchlist.csv so later runs can skip search.

    python discover.py "software engineer"            # discover, verify, print, write watchlist
    python discover.py "software engineer" --raw      # just print Tavily URLs, to eyeball quality
"""

import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date

import httpx
from tavily import TavilyClient

from config import settings
from greenhouse import fetch_board
from pipeline import Filters, _keep

GREENHOUSE_HOSTS = ["boards.greenhouse.io", "job-boards.greenhouse.io"]

# Greenhouse job URLs look like:
#   https://boards.greenhouse.io/{slug}/jobs/123        https://job-boards.greenhouse.io/{slug}/jobs/123
#   https://boards.greenhouse.io/embed/job_app?for={slug}&token=123
_SLUG_PATH = re.compile(r"greenhouse\.io/(?!embed)([a-z0-9_-]+)", re.I)
_SLUG_FOR = re.compile(r"[?&]for=([a-z0-9_-]+)", re.I)

# A few query shapes per role. Tavily returns ≤20 per query, so variety is how recall goes up.
QUERY_SHAPES = [
    "{role}",
    "{role} jobs",
    "junior {role}",
    "{role} II",
    "new grad {role}",
    "early career {role}",
]


@dataclass
class Board:
    slug: str
    company: str
    jobs: int
    matching: int
    hits: int  # how many search results pointed at this slug — a weak relevance signal


def slug_from_url(url: str) -> str | None:
    m = _SLUG_FOR.search(url) or _SLUG_PATH.search(url)
    return m.group(1).lower() if m else None


def _search(query: str) -> list[dict]:
    """Tavily results for one query, cached per day so re-runs don't spend credits."""
    cache_dir = settings.data_dir / "tavily"
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    path = cache_dir / f"{safe}-{date.today().isoformat()}.json"
    if path.exists():
        return json.loads(path.read_text())

    client = TavilyClient(api_key=settings.tavily_api_key)
    resp = client.search(
        query, include_domains=GREENHOUSE_HOSTS, max_results=20, search_depth="basic"
    )
    results = resp.get("results", [])
    path.write_text(json.dumps(results))
    return results


def harvest(role: str) -> Counter:
    """Run every query shape for the role; return slug -> number of query shapes that surfaced it."""
    hits: Counter = Counter()
    for shape in QUERY_SHAPES:
        slugs = {
            slug_from_url(r.get("url", "")) for r in _search(shape.format(role=role))
        }
        for slug in slugs - {None}:
            hits[slug] += 1
    return hits


def verify(slug: str) -> Board | None:
    """A slug is real if the board fetches and has at least one job. fetch_board caches, so this also
    warms the cache for rank_jobs."""
    try:
        listings = fetch_board(slug)
    except httpx.HTTPStatusError:
        return None
    if not listings:
        return None
    f = Filters()
    matching = sum(_keep(l, f) for l in listings)
    return Board(
        slug=slug,
        company=listings[0].company,
        jobs=len(listings),
        matching=matching,
        hits=0,
    )


def _watchlist_path():
    return settings.data_dir / "watchlist.csv"


def load_watchlist() -> dict[str, dict]:
    path = _watchlist_path()
    if not path.exists():
        return {}
    with path.open() as f:
        return {row["slug"]: row for row in csv.DictReader(f)}


def save_watchlist(rows: dict[str, dict]) -> None:
    path = _watchlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["slug", "company", "jobs", "roles", "first_seen"]
        )
        w.writeheader()
        for slug in sorted(rows):
            w.writerow(rows[slug])

def discover(role: str, limit: int = 10) -> list[Board]:
    hits = harvest(role)
    for slug in load_watchlist():
        hits.setdefault(
            slug, 0
        )  # known boards are candidates even if today's search missed them
    boards: list[Board] = []
    for slug, n in hits.most_common():
        b = verify(slug)
        if b:
            b.hits = n
            boards.append(b)

    # Merge into the watchlist. Existing rows (including hand-added ones) are kept.
    wl = load_watchlist()
    for b in boards:
        row = wl.get(
            b.slug,
            {"slug": b.slug, "first_seen": date.today().isoformat(), "roles": ""},
        )
        row["company"] = b.company
        row["jobs"] = str(b.jobs)
        roles = set(filter(None, row["roles"].split("|"))) | {role}
        row["roles"] = "|".join(sorted(roles))
        wl[b.slug] = row
    save_watchlist(wl)

    boards.sort(key=lambda b: (-b.matching, -b.hits))
    return boards[:limit]


if __name__ == "__main__":
    role = (
        sys.argv[1]
        if len(sys.argv) > 1 and not sys.argv[1].startswith("--")
        else "software engineer"
    )

    if "--raw" in sys.argv:
        for shape in QUERY_SHAPES:
            q = shape.format(role=role)
            print(f"\n## {q}")
            for r in _search(q):
                print(f"  {slug_from_url(r['url']) or '?':20} {r['url']}")
        sys.exit()

    hits = harvest(role)
    print(f"{sum(hits.values())} result URLs → {len(hits)} distinct slugs\n")

    boards = discover(role, limit=1000)
    bad = set(hits) - {b.slug for b in boards}
    print(f"{'slug':22} {'company':30} {'jobs':>5} {'hits':>4}")
    for b in boards:
        print(f"{b.slug:22} {b.company[:30]:30} {b.jobs:5} {b.hits:4} {b.matching}")
    print(
        f"\n{len(boards)} verified · {len(bad)} failed verification: {', '.join(sorted(bad)) or '—'}"
    )
    print(f"watchlist: {_watchlist_path()} ({len(load_watchlist())} boards)")
