# Lumbergh — résumé-matched job search agent

An AI agent that takes a plain-English request ("backend roles at mid-size product companies, skip
defense"), finds companies hiring for it, reads their live postings, and ranks them against your
résumé — with every rank traceable to specific requirement/evidence pairs. Ask it why #2 beat #4
and it answers from the evidence, without re-running the search.

Strands Agents SDK · AWS Bedrock (Claude) · Tavily · Python 3.11

> Built with Claude as a pair programmer. I set the direction, made the architecture and policy
> decisions, ran and debugged each stage, and labeled the evaluation set.

## Why it looks the way it does

The first version pointed an agent at Indeed. It got blocked, fell back to search-result snippets,
and confidently produced "requirements" and "qualifications" that were never in any posting.
Sixteen tool calls, fluent output, fabricated content. Everything in the current design is a
response to that:

- **Source full postings, not snippets.** Greenhouse publishes a keyless public API that returns
  every posting's complete text. No scraping, no guessing.
- **The model only asserts what it can quote.** Every extracted requirement must carry a verbatim
  span from the posting; every "met" judgment must cite a verbatim line from the résumé. Python
  string-checks both. Anything that doesn't verify is dropped or downgraded.
- **Python computes the score.** The model emits met / partial / unmet per requirement; weights,
  gates, and ranking are Python constants that can be re-tuned on cached results without a single
  model call.
- **Coarse tools.** The agent has four: `discover_boards`, `rank_jobs`, `explain_match`,
  `filter_results`. One search is 3–4 tool calls. Follow-ups touch only cached data.

## Who does what

| The model | Python |
|---|---|
| Turn the request into search terms and title filters | Fetch, normalize, cache every posting |
| Choose which companies fit the user's preferences | Verify every quoted span by string match |
| Extract requirements from a posting (with source spans) | Score, apply gates, rank, deduplicate |
| Judge each requirement against the résumé (with evidence) | Bound concurrency, count model calls |
| Explain results and answer follow-ups | Hold state so follow-ups need no re-run |

## Demo

```
> find backend roles at mid-size product companies, skip defense and crypto
  → discover_boards({"role": "backend engineer", "limit": 15})
  → rank_jobs({"boards": ["stripe", "cloudflare", "axon", "doordashusa", "affirm", ...],
               "title_any": ["backend engineer", "backend developer", "software engineer", "platform engineer"]})
  ← 3262 fetched · 73 considered · 7 model calls · 10.9s
  → filter_results({"exclude_keywords": ["Poland", "Spain", "Canada", "Vietnam", ...]})
  ← 19 of 33 after filtering

Boards: stripe, cloudflare, axon, doordashusa, affirm, avepoint, esri, generalmatter — skipped
spacex (aerospace/defense), andurilindustries (defense), helsing (defense AI), optiverus (trading) ...

1. 77.8 (5 met / 2 partial / 0 unmet) — Affirm, Software Engineer II, Backend — Remote US
2. 75.0 (4/2/0) — Affirm, Software Engineer I, Fullstack — Remote US
3. 72.2 (5/1/1) — Cloudflare, Software Engineer, Deploy at Scale — Hybrid
...
Blocked (10): 71.4 Affirm, Software Engineer I — "Must reside in Alberta, British Columbia, ..."

  [4 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 1} · 15355 tokens]

> why is #1 above #3?
  → explain_match({"rank": 3})
  [... requirement-by-requirement evidence table, no re-run ...]
```

v0 on the same kind of request: 16 tool calls, 2 blocked extractions, fabricated requirements.

## Evaluation

A hand-labeled golden set of 14 postings (`data/golden/`, labeling rules in `data/golden/RULES.md`),
scored by `eval.py` against the current résumé. Labels were made from the résumé text only.

| run | set | extraction P / R | match agreement | generous / strict | what changed |
|---|---|---|---|---|---|
| 1 | 10 listings | 85.2 / 100* | 69.7% | 9 / 14 | baseline; single-line evidence |
| 2 | 10 | 97.4 / 97.4 | 70.3% | 10 / 12 | soft-skill negatives in extraction prompt; evidence may cite up to 3 lines |
| 3 | 15 (new set) | 97.6 / 96.1 | 71.5% | 12 / 23 | same prompts, larger set; plateau confirmed |
| 4 | 15 | 97.3 / 100 | 80.6% | 15 / 6 | `reason` field emitted before `status`; rules reordered with explicit priority; tie-breaks removed |
| 5 | 14 | 97.3 / 100 | 85.2% | 8 / 8 | tie-break rules restored; label consistency pass |

\* run-1 recall is an artifact: templates were prefilled from the model's extraction and no missed
requirements were added. Later runs include a read-through of each posting.

What moved the number and what didn't:
- Changing how evidence is *cited* (run 2) improved the citations and changed almost no verdicts.
- Making the model write its reasoning *before* its verdict (run 4) was worth nine points.
- Tie-break wording controls which way the residual errors fall (run 4 → 5). That matters more than
  the point total: a generous error puts a listing you don't qualify for at the top; a strict one
  hides a listing in the blocked bucket, which is still visible.

Residual disagreements (16/108) are mostly one pattern: when the only evidence is a skills-list
entry, the model holds to "listed skill → at most partial" even where the requirement's own wording
("such as", "e.g.", "or equivalent") would make it met. Verdicts are also not perfectly stable: an
identical years requirement on three Stripe postings was judged partial, partial, and met against
the same résumé; per-listing context shifts borderline calls. Roughly a third of the remainder are
items two careful readers would split on. No fabricated requirements in any run.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install strands-agents tavily-python pydantic pydantic-settings httpx
cp .env.example .env     # AWS_REGION, BEDROCK_MODEL_ID, TAVILY_API_KEY
python agent.py resume.pdf
```

Each stage also runs on its own, which is how it was built and how it's debugged:

```bash
python greenhouse.py                 # fetch five boards, print a sample posting
python resume.py resume.pdf          # résumé → profile (cached on PDF hash)
python extract.py                    # requirements for 10 listings, with dropped spans
python match.py resume.pdf           # met/partial/unmet with evidence
python score.py resume.pdf           # ranked + blocked, no model calls
python pipeline.py resume.pdf stripe affirm
python discover.py "backend engineer" --raw
python eval.py init stripe affirm --per-board 3 && python eval.py run resume.pdf
```

## Layout

```
config.py     settings from .env
models.py     Listing, Requirement, ResumeProfile, RequirementMatch, MatchResult
greenhouse.py fetch_board(slug) -> list[Listing]           cached per board per day
resume.py     load_profile(pdf) -> ResumeProfile           cached on PDF hash
extract.py    extract_requirements(listing)                 span-verified, cached per listing
match.py      match_listing(profile, listing)              evidence-verified, cached per (profile, listing)
score.py      score / rank / explain                        pure Python; all policy constants live here
pipeline.py   rank_listings(profile, boards, filters)      bounded async fan-out
discover.py   discover(role) -> boards                      Tavily + name read-back verification
agent.py      the four tools, system prompt, REPL
eval.py       golden-set metrics
data/         caches, watchlist.csv, golden/               gitignored
```

## Policy knobs (`score.py`)

| constant | meaning |
|---|---|
| `WEIGHT_REQUIRED` / `WEIGHT_PREFERRED` | 2 / 1 |
| `CREDIT` | met 1.0, partial 0.5, unmet 0 |
| `MAX_YEARS` | a stated minimum above this blocks unless fully met (default 4) |
| `SOFT_GATE` | "or equivalent", "encouraged", "preferred" → never blocks |
| `PRIOR_WEIGHT` | pulls thin postings toward 50 so three easy requirements don't beat twelve |

Change any of them and re-run: no model calls, instant re-rank.

## Known limits

- **Verification catches fabrication, not irrelevance.** A quote that exists in the résumé but
  doesn't support the claim passes the string check. Relevance is a model judgment; the golden set
  is how it's measured.
- **Greenhouse only.** Lever, Ashby and SmartRecruiters have similar public APIs; one role query
  already yields 60+ verified Greenhouse boards, so they weren't needed for this scope.
- **Location strings are messy.** "Remote" is rare even for remote-eligible roles. The agent ranks
  everything and narrows afterward rather than filtering up front.
- **Tavily recall depends on query shape.** Six shapes per role; discovered boards accumulate in
  `data/watchlist.csv` so good companies aren't lost between runs.
- **The model's world knowledge is used in exactly two places** (choosing companies by industry,
  recognizing non-US cities) and kept out of everything that touches a score.

## Decisions I'd defend

No scraping of Indeed/LinkedIn. One coarse tool runs the whole pipeline rather than exposing
`fetch_one` / `match_one` and rebuilding the v0 thrash on better data. The model never emits a
number. Evidence is verbatim or it doesn't count. Discovery verifies by reading the company name
back, not by HTTP 200 (an empty board also returns 200). Tools that hold state are idempotent — the
first `filter_results` stacked on its own output and locked the agent into an empty view.