"""Golden-set eval: how well do extraction and matching agree with hand labels?

    python eval.py init stripe affirm --per-board 3     # write label templates for listings to data/golden/
    python eval.py run resume.pdf                        # score the model against every labeled file

Labeling workflow, per file in data/golden/:
  1. Read "description" (the posting) and fix "requirements" so it is what YOU would extract:
     delete anything that isn't really a requirement, add anything the model missed (copy the span
     from the description), correct "preferred" / "gate" if wrong.
  2. For each requirement set "status" to met / partial / unmet, judging from the résumé only.
     Leave it "" to skip that one for the matching metric.
  3. Set "labeled": true. Unlabeled files are ignored by `run`.

Metrics:
  extraction precision = model requirements that match a labeled one / model requirements
  extraction recall    = labeled requirements matched by a model one / labeled requirements
  match agreement      = matched pairs where model status == your status / pairs you labeled
  plus a breakdown of disagreements: "generous" (model higher than you) vs "strict" (lower).
"""

import json
import re
import sys
from pathlib import Path

from config import settings
from extract import extract_requirements
from greenhouse import fetch_board
from match import match_listing
from models import Listing, Status
from pipeline import Filters, _keep
from resume import load_profile

GOLDEN = settings.data_dir / "golden"
ORDER = {Status.unmet: 0, Status.partial: 1, Status.met: 2}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip(" .;:,")


def _same(a: str, b: str) -> bool:
    """Two spans refer to the same requirement if one contains the other after normalizing."""
    a, b = _norm(a), _norm(b)
    return bool(a) and bool(b) and (a in b or b in a)


# --- init --------------------------------------------------------------------------------------


def init(
    boards: list[str],
    per_board: int,
    title_any: list[str] | None = None,
    match: list[str] | None = None,
) -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    f = Filters(per_board=per_board, **({"title_any": title_any} if title_any else {}))
    written = 0
    for slug in boards:
        listings = [l for l in fetch_board(slug) if _keep(l, f)]
        if match:  # pick by title substring, ignore the per-board cap
            listings = [
                l for l in listings if any(m.lower() in l.title.lower() for m in match)
            ]
        else:
            listings = listings[:per_board]
        for l in listings:
            path = GOLDEN / (l.id.replace(":", "_") + ".json")
            if path.exists():
                continue
            model_reqs, _ = extract_requirements(l)
            template = {
                "listing_id": l.id,
                "title": l.title,
                "company": l.company,
                "url": l.url,
                "labeled": False,
                "requirements": [
                    {
                        "span": r.source_span,
                        "preferred": r.preferred,
                        "gate": r.gate,
                        "status": "",
                    }
                    for r in model_reqs
                ],
                "description": l.description,
            }
            path.write_text(json.dumps(template, indent=2, ensure_ascii=False))
            written += 1
            print(
                f"wrote {path.name}  {l.title}  ({len(model_reqs)} requirements prefilled)"
            )
    print(
        f"\n{written} templates. Prefilled from the model's extraction — delete what's wrong, ADD what it missed."
    )


# --- run ---------------------------------------------------------------------------------------


def run(resume_path: Path) -> None:
    profile = load_profile(resume_path)
    files = sorted(GOLDEN.glob("*.json")) if GOLDEN.exists() else []
    golden = [json.loads(p.read_text()) for p in files]
    golden = [g for g in golden if g.get("labeled")]
    if not golden:
        print('no labeled files in data/golden/ (set "labeled": true)')
        return

    tot = {
        "model_reqs": 0,
        "model_hit": 0,
        "gold_reqs": 0,
        "gold_hit": 0,
        "pairs": 0,
        "agree": 0,
        "generous": 0,
        "strict": 0,
    }
    disagreements: list[str] = []
    fabricated: list[str] = []
    missed: list[str] = []

    for g in golden:
        slug = g["listing_id"].split(":")[1]
        listing = next(l for l in fetch_board(slug) if l.id == g["listing_id"])
        model_reqs, _ = extract_requirements(listing)
        matches = {
            m.requirement.source_span: m for m in match_listing(profile, listing)
        }
        gold_reqs = g["requirements"]

        # extraction
        tot["model_reqs"] += len(model_reqs)
        tot["gold_reqs"] += len(gold_reqs)
        for r in model_reqs:
            if any(_same(r.source_span, q["span"]) for q in gold_reqs):
                tot["model_hit"] += 1
            else:
                fabricated.append(f'{g["company"]} — {g["title"]}: "{r.source_span}"')
        for q in gold_reqs:
            if any(_same(r.source_span, q["span"]) for r in model_reqs):
                tot["gold_hit"] += 1
            else:
                missed.append(f'{g["company"]} — {g["title"]}: "{q["span"]}"')

        # matching
        for q in gold_reqs:
            if q.get("status") not in ("met", "partial", "unmet"):
                continue
            pair = next(
                (m for span, m in matches.items() if _same(span, q["span"])), None
            )
            if pair is None:
                continue
            tot["pairs"] += 1
            want, got = Status(q["status"]), pair.status
            if want == got:
                tot["agree"] += 1
                continue
            kind = "generous" if ORDER[got] > ORDER[want] else "strict"
            tot[kind] += 1
            ev = f"  ↳ {' | '.join(pair.evidence)}" if pair.evidence else ""
            disagreements.append(
                f'[{kind:8}] you={want.value:7} model={got.value:7} {g["company"]}: "{q["span"]}"{ev}'
            )

    def pct(a, b):
        return f"{100 * a / b:5.1f}%" if b else "   n/a"

    print(f"{len(golden)} labeled listings\n")
    print(
        f"extraction precision  {pct(tot['model_hit'], tot['model_reqs'])}  ({tot['model_hit']}/{tot['model_reqs']} model requirements are real)"
    )
    print(
        f"extraction recall     {pct(tot['gold_hit'], tot['gold_reqs'])}  ({tot['gold_hit']}/{tot['gold_reqs']} real requirements were found)"
    )
    print(
        f"match agreement       {pct(tot['agree'], tot['pairs'])}  ({tot['agree']}/{tot['pairs']} labeled; {tot['generous']} generous, {tot['strict']} strict)"
    )

    for title, items in (
        ("FABRICATED / NOT A REQUIREMENT", fabricated),
        ("MISSED", missed),
        ("DISAGREEMENTS", disagreements),
    ):
        if items:
            print(f"\n{title} ({len(items)})")
            for it in items:
                print(f"  {it}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "init":
        import argparse

        ap = argparse.ArgumentParser(prog="eval.py init")
        ap.add_argument("boards", nargs="+")
        ap.add_argument("--per-board", type=int, default=3)
        ap.add_argument(
            "--title", nargs="*", help="title terms, same as rank_jobs title_any"
        )
        ap.add_argument(
            "--match", nargs="*", help="only listings whose title contains one of these"
        )
        a = ap.parse_args(args[1:])
        init(a.boards, a.per_board, a.title, a.match)
    elif args and args[0] == "run":
        run(Path(args[1]) if len(args) > 1 else Path("resume.pdf"))
    else:
        print(__doc__)
