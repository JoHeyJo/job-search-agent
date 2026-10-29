> **Canonical reference:** https://docs.exa.ai/reference/search-api-guide-for-coding-agents
>
> If anything below looks outdated or contradicts real API behavior, fetch that URL — it is the source of truth for search types, parameters, and response shape. Report staleness back to the user.

---

# Exa API Setup Guide

## Your Configuration

| Setting | Value |
|---------|-------|
| Coding Tool | Claude |
| Integration | Python |
| Use Case | Web search tool |
| Search Type | Auto - Balanced relevance and speed (default) |
| Content | Highlights |

**Project Description:** Agent to query job listings.

---

## API Key Setup

### Environment Variable

```bash
export EXA_API_KEY="YOUR_API_KEY"
```

### .env File

```env
EXA_API_KEY=YOUR_API_KEY
```

### Usage in Code

```python
import os
from exa_py import Exa

exa = Exa(api_key=os.environ.get("EXA_API_KEY"))
```

---

## Quick Start (Python)

```bash
pip install exa-py==2.14.0
```

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_API_KEY")

results = exa.search(
    "recent product announcements from developer tools companies",
    type="auto",
    num_results=10,
    contents={"highlights": True}
)

for result in results.results:
    print(result.title, result.url)
```

---

## Pick Your Search Pattern

Start with one of these two patterns:

### 1. Raw retrieval for your own agent

Use this when your app should inspect `results` directly, pass `highlights` into your own LLM, or expose Exa as a tool inside an existing agent loop.

```json
{
  "query": "recent product announcements from developer tools companies",
  "type": "auto",
  "numResults": 10,
  "contents": {
    "highlights": true
  }
}
```

### 2. Synthesized search when you want grounded output

Use this when you want Exa to synthesize a grounded answer or structured payload for you. `systemPrompt` sets behavior and source preferences; `outputSchema` sets the shape of `output.content`.

```json
{
  "query": "recent product announcements from developer tools companies",
  "type": "deep",
  "systemPrompt": "Prefer official sources, collapse duplicate reporting, and keep the output grounded.",
  "outputSchema": {
    "type": "object",
    "properties": {
      "summary": {
        "type": "string",
        "description": "A grounded summary of the most important findings"
      }
    },
    "required": [
      "summary"
    ]
  },
  "contents": {
    "highlights": true
  }
}
```

### Deep search notes

- Use `deep` when you need harder comparisons, structured synthesis, or multi-step reasoning across many sources.
- Use `additionalQueries` only on `deep-lite`, `deep`, and `deep-reasoning` when you want to force a few explicit query angles instead of relying entirely on automatic query expansion.
- If you only need raw search results and excerpts, stay on `results` + `highlights` and skip `outputSchema`.

---

## Function Calling / Tool Use

Function calling (also known as tool use) allows your AI agent to dynamically decide when to search the web based on the conversation context. Instead of searching on every request, the LLM intelligently determines when real-time information would improve its response—making your agent more efficient and accurate.

**Why use function calling with Exa?**
- Your agent can ground responses in current, factual information
- Reduces hallucinations by fetching real sources when needed
- Enables multi-step reasoning where the agent searches, analyzes, and responds

📚 **Full documentation**: https://docs.exa.ai/reference/openai-tool-calling

### OpenAI Function Calling

```python
import json
from openai import OpenAI
from exa_py import Exa

openai = OpenAI()
exa = Exa(api_key="YOUR_EXA_API_KEY")

tools = [{
    "type": "function",
    "function": {
        "name": "exa_search",
        "description": "Search the web for current information.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"]
        }
    }
}]

def exa_search(query: str) -> str:
    results = exa.search(query, type="auto", num_results=10, contents={"highlights": True})
    return "\n".join([f"{r.title}: {r.url}" for r in results.results])

messages = [{"role": "user", "content": "What's the latest in AI safety?"}]
response = openai.chat.completions.create(model="gpt-4o", messages=messages, tools=tools)

if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    search_results = exa_search(json.loads(tool_call.function.arguments)["query"])
    messages.append(response.choices[0].message)
    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": search_results})
    final = openai.chat.completions.create(model="gpt-4o", messages=messages)
    print(final.choices[0].message.content)
```

### Anthropic Tool Use

```python
import anthropic
from exa_py import Exa

client = anthropic.Anthropic()
exa = Exa(api_key="YOUR_EXA_API_KEY")

tools = [{
    "name": "exa_search",
    "description": "Search the web for current information.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"]
    }
}]

def exa_search(query: str) -> str:
    results = exa.search(query, type="auto", num_results=10, contents={"highlights": True})
    return "\n".join([f"{r.title}: {r.url}" for r in results.results])

messages = [{"role": "user", "content": "Latest quantum computing developments?"}]
response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096, tools=tools, messages=messages)

if response.stop_reason == "tool_use":
    tool_use = next(b for b in response.content if b.type == "tool_use")
    tool_result = exa_search(tool_use.input["query"])
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": tool_result}]})
    final = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096, tools=tools, messages=messages)
    print(final.content[0].text)
```

---

## Search Type Reference

| Type | Best For | Approx Latency | Depth |
|------|----------|----------------|-------|
| `auto` | Most queries — balanced relevance and speed | ~1 second | Smart | ← your selection
| `fast` | Latency-sensitive queries that still need good relevance | ~450 ms | Basic |
| `instant` | Chat, voice, autocomplete, quick lookups | ~250 ms | Basic |
| `deep-lite` | Cheaper synthesis when full deep search is overkill | 4 seconds | Deep |
| `deep` | Research, enrichment, thorough results | 4-15 seconds | Deep |
| `deep-reasoning` | Complex research, multi-step reasoning, hard synthesis tasks | 12-40 seconds | Deepest |

Latency numbers are ballpark — synthesis (`outputSchema`) and forced livecrawls (`contents.maxAgeHours: 0`) stack on top of the base `type`. See the Latency Characteristics section for details.

**Tip:** `type="auto"` works well for most queries. `outputSchema` works on every search type, so you can request structured, grounded output regardless of which type you pick.

---

## Optional: Structured Outputs (outputSchema)

Raw `results` + `highlights` should still be your default starting point for many agent workflows. Add `outputSchema` only when you want Exa to synthesize grounded JSON or a structured answer for you.

`outputSchema` works on **every** search type. Pass a JSON schema and Exa returns the synthesized answer as structured JSON in `output.content`, with field-level citations in `output.grounding`. Deep variants (`deep-lite`, `deep`, `deep-reasoning`) give higher-quality synthesis for complex queries, but the response shape is the same.

**Use `systemPrompt` and `outputSchema` together:** `systemPrompt` controls source preferences, dedupe behavior, and synthesis rules; `outputSchema` controls the exact shape of `output.content`.

**Schema controls:** `type`, `description`, `required`, `properties`, `items`. Max nesting depth 2, max total properties 10. Do NOT add citation or confidence fields to the schema — `/search` returns grounding data automatically.

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_API_KEY")

results = exa.search(
    "articles about GPUs",
    type="auto",
    system_prompt="Prefer official sources, collapse duplicate reporting, and keep the output grounded.",
    output_schema={
        "type": "object",
        "description": "Companies mentioned in articles",
        "required": ["companies"],
        "properties": {
            "companies": {
                "type": "array",
                "description": "List of companies mentioned",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the company"
                        },
                        "description": {
                            "type": "string",
                            "description": "Short description of what the company does"
                        }
                    }
                }
            }
        }
    },
    contents={"highlights": True}
)

# Access structured output
print(results.output.content)   # {"companies": [{"name": "Nvidia", "description": "..."}]}
print(results.output.grounding) # Field-level citations
```

### Response Shape

Responses with `outputSchema` include:
- `output.content` — structured JSON matching your schema (or a string for `{"type": "text"}` schemas)
- `output.grounding` — array of `{field, citations, confidence}` entries with source URLs

```json
{
  "output": {
    "content": {
      "companies": [
        {"name": "Nvidia", "description": "GPU and AI chip manufacturer"},
        {"name": "AMD", "description": "Semiconductor company producing GPUs and CPUs"}
      ]
    },
    "grounding": [
      {
        "field": "companies[0].name",
        "citations": [{"url": "https://...", "title": "Source"}],
        "confidence": "high"
      }
    ]
  }
}
```

### When to Use Structured Outputs

- ==**Enrichment workflows** — extract specific fields (company info, people data, product details)==
- **Data pipelines** — get structured data directly instead of parsing free text
- **Grounded answers** — prefer `outputSchema` on `/search` for new structured search flows
- Prefer a deep variant (`deep-lite`/`deep`/`deep-reasoning`) when you need multi-step reasoning or synthesis across many sources

---

## Content Configuration

The generated examples request highlights by default:

```json
"contents": {
  "highlights": true
}
```

Highlights return query-relevant excerpts, which are usually the right content mode for LLM workflows because they keep token usage predictable.

Content is controlled via the `contents` object on `/search` (or top-level fields on `/contents`). Pick one of `text`, `highlights`, or `summary` by default. You can combine them, but it is usually an antipattern to do so at the start of a project.

| Mode | Config | Best For |
|------|--------|----------|
| Highlights | `"highlights": true` | Token-efficient excerpts |
| Text | `"text": {"maxCharacters": 20000}` | Full content extraction, RAG |
| Summary | `"summary": {"query": "your question"}` or `"summary": true` | LLM-written summary per result |

### Tuning knobs

- **`highlights`** — pass `true` to return query-relevant highlights for each result.
- **`summary`** — pass `true` for a generic summary, or `{"query": "..."}` to bias the summary toward a specific question. Supports a `schema` field for per-result structured output. Summary has no `verbosity` setting — verbosity lives on `text` (below).
- **`text.verbosity`** — `"compact" | "full"` (default `"compact"`). Compact returns only the main content of the page, excluding navbars, banners, footers etc.
- **`text.includeHtmlTags`** — boolean (default `false`). When `true`, preserves HTML structure (useful for code blocks, tables).
- **`text.maxCharacters`** — hard cap on extracted text length. Always set this to control token cost when requesting text.

**Case conventions:** JavaScript SDK and raw JSON use camelCase (`maxCharacters`). Python SDK uses snake_case (`max_characters`) — this applies inside nested dicts too.

**Token usage:** `text: true` with no cap can blow up context. Prefer `highlights: true` for most agent workflows, and add `text` only when downstream reasoning truly needs broad page context.

---

## Domain Filtering (Optional)

Usually not needed - Exa's neural search finds relevant results without domain restrictions.

**When to use:**
- Targeting specific authoritative sources
- Excluding low-quality domains from results

**Example:**

```json
{
  "includeDomains": ["arxiv.org", "github.com"],
  "excludeDomains": ["pinterest.com"]
}
```

**Note:** `includeDomains` and `excludeDomains` can be used together to include a broad domain while excluding specific subdomains (e.g., `"includeDomains": ["vercel.com"], "excludeDomains": ["community.vercel.com"]`).

---

## Web Search Tool

```json
{
  "query": "recent product announcements from developer tools companies",
  "numResults": 10,
  "contents": {
    "highlights": true
  }
}
```

**Tips:**
- Use `type: "auto"` for most queries
- Great for building search-powered chatbots or agents
- Combine with contents for RAG workflows

---

## Content Freshness (maxAgeHours)

`maxAgeHours` sets the maximum acceptable age (in hours) for cached content. If the cached version is older than this threshold, Exa will livecrawl the page to get fresh content
| Value | Behavior | Best For |
|-------|----------|----------|
| 24 | Use cache if less than 24 hours old, otherwise livecrawl | Daily-fresh content |
| 1 | Use cache if less than 1 hour old, otherwise livecrawl | Near real-time data |
| 0 | Always livecrawl (ignore cache entirely) | Real-time data where cached content is unusable |
| -1 | Never livecrawl (cache only) | Maximum speed, historical/static content |
| *(omit)* | Default behavior (livecrawl as fallback if no cache exists) | **Recommended** — balanced speed and freshness |

**When LiveCrawl Isn't Necessary:**
Cached data is sufficient for many queries, especially for historical topics or educational content. These subjects rarely change, so reliable cached results can provide accurate information quickly.

See [maxAgeHours docs](https://exa.ai/docs/reference/livecrawling-contents#maxAgeHours) for more details.

---

## Other Endpoints

Beyond `/search`, the next two endpoints to know are `/contents` and `/answer`:

| Endpoint | Description | Docs |
|----------|-------------|------|
| `/contents` | Get clean, parsed content for URLs you already have | [Docs](https://exa.ai/docs/reference/get-contents) |
| `/answer` | Get a grounded answer with citations when the UI is question-first | [Docs](https://exa.ai/docs/reference/answer) |

> For new structured search flows, prefer `/search` + `outputSchema` when you want both retrieval control and grounded output. Keep `/answer` for question-first UIs where you do not need to inspect raw search results.

### /contents — Get Contents for Known URLs

Use `/contents` when you already have URLs and need their content. Unlike `/search` (which finds and optionally retrieves content), `/contents` is purely for content extraction from known URLs.

**When to use `/contents` vs `/search`:**
- URLs from another source (database, user input, RSS feeds) → `/contents`
- Need to refresh stale content for URLs you already have → `/contents` with `maxAgeHours`
- Need to find AND get content in one call → `/search` with `contents`

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_API_KEY")

results = exa.get_contents(
    ["https://example.com/article", "https://example.com/blog-post"],
    highlights=True
)

for result in results.results:
    print(result.title, result.url)
    print(result.highlights)
```

**Content retrieval options** (choose one per request):

| Option | Config | Best For |
|--------|--------|----------|
| Highlights | `"highlights": true` | Key excerpts, lower token usage |
| Text | `"text": {"max_characters": 20000}` | Full content extraction, RAG |

**Highlights example:**

```json
{
  "urls": ["https://example.com/article"],
  "highlights": true
}
```

**Freshness control:** Add `maxAgeHours` to ensure content is fresh:
- `24` — livecrawl if cached content is older than 24 hours
- `0` — always livecrawl (ignore cache)
- Omit — use cache when available, livecrawl as fallback

---

## Troubleshooting

**⚠️ COMMON PARAMETER MISTAKES — avoid these:**
- `useAutoprompt` → **deprecated**, remove it entirely
- `includeUrls` / `excludeUrls` → **do not exist**. Use `includeDomains` / `excludeDomains`
- `text`, `summary`, `highlights` at the top level of `/search` → **must be nested** inside `contents` (e.g. `"contents": {"highlights": true}`). On `/contents` they ARE top-level — don't confuse the two.
- `numSentences`, `highlightsPerUrl` → **deprecated** highlights params. Use `highlights: true` instead
- `tokensNum` → **does not exist**. Use `contents.text.maxCharacters` to limit text length
- `livecrawl: "always"` → **deprecated**. Use `contents.maxAgeHours: 0` instead
- `excludeDomains` + `category: "company" | "people"` → **400 error**. Those categories don't support `excludeDomains` or any date filters.

> **`stream: true`** switches `/search` to SSE mode (OpenAI-compatible chat-completion chunks). It's supported — just expect streaming chunks instead of one JSON response.

**Results not relevant?**
1. Try `type: "auto"` - most balanced option
2. Try `type: "deep"` - runs multiple query variations and ranks the combined results
3. Refine query - use singular form, be specific
4. Check category matches your use case

**Need structured data from search?**
1. Pass `outputSchema` on any search type — `auto` works, `deep`/`deep-reasoning` gives higher-quality synthesis
2. Define the fields you need in the schema, then add `systemPrompt` for source preferences and dedupe rules

**Results too slow?**
1. Use `type: "fast"` or `type: "instant"`
2. Reduce `numResults`
3. Skip contents if you only need URLs

**No results?**
1. Remove filters (date, domain restrictions)
2. Simplify query
3. Try `type: "auto"` - has fallback mechanisms

---

## Resources

- Docs: https://exa.ai/docs
- Dashboard: https://dashboard.exa.ai
- API Status: https://status.exa.ai

### Roles for tools
Exa still has a job, just a smaller one: finding which companies use which board when you don't know the slug. One search, then the slug goes in BOARDS permanently.

# Overview
deterministic (plain Python, async)      →  fetch N postings from ATS APIs
per-listing, parallel (cheap model)      →  normalize one posting → JobListing
cached, per-company (cheap model)        →  company blurb
deterministic                            →  rank, dedupe, take top 5

### WorkFlow
Aquire known ATS APIs
## pre-agent work
Fetch jobs from knowns ATS APIs

GET .../jobs (no content) → filter deterministically on title, location.name, first_published
GET .../jobs/{id} for the survivors only, to pull content

## Agent (search job listings)
Normalize content
Weight content against resume
If no known ATS API Exa can search for a known ATS API.
Object will hold whether an API exists, None(does not have API), "na" not available


### Public ATS API
ATSs requiring pagination: SmartRecruiters, Workday
{
  "Greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs",
  "Lever":      "https://api.lever.co/v0/postings/{slug}?mode=json",
  "Ashby":      "https://api.ashbyhq.com/posting-api/job-board/{slug}",
  "Workable":   "https://apply.workable.com/api/v1/widget/accounts/{slug}",
  "Recruitee":  "https://{slug}.recruitee.com/api/offers/",
  "Breezy HR":  "https://{slug}.breezy.hr/json",
  "BambooHR":   "https://{slug}.bamboohr.com/careers/list",
  "Personio":   "https://{slug}.jobs.personio.de/xml"
}

## ATS Notes

| ATS | Method | Format | Auth | Slug Source | Key Quirk |
|---|---|---|---|---|---|
| **Greenhouse** | `GET` | JSON | None | `boards.greenhouse.io/{slug}` | Add `?content=true` for full HTML descriptions in same response |
| **Lever** | `GET` | JSON (bare array, not object) | None | `jobs.lever.co/{slug}` | Timestamps are Unix **milliseconds**, not ISO 8601 |
| **Ashby** | `GET` | JSON | None | `jobs.ashbyhq.com/{slug}` | Descriptions included by default; add `?includeCompensation=true` for salary |
| **Workable** | `GET` | JSON | None | `apply.workable.com/{slug}` | Add `?details=true` for descriptions; location is 3 separate fields (`city`, `state`, `country`) |
| **Recruitee** | `GET` | JSON | None | `{slug}.recruitee.com` | Trailing slash matters (`/api/offers/`); dual location fields (flat + structured array) |
| **Breezy HR** | `GET` | JSON | None | `{slug}.breezy.hr` | Returns `403` (not `404`) for non-existent boards; no descriptions in list response |
| **BambooHR** | `GET` | JSON | None | `{slug}.bamboohr.com` | Returns `302` redirect (not `404`) for non-existent boards; location fields frequently `null` |
| **Personio** | `GET` | **XML** (not JSON) | None | `{slug}.jobs.personio.de` | Returns `307` redirect (not `404`) for non-existent boards |


Greenhouse : boards-api.greenhouse.io/v1/boards/{token}/jobs 
Lever : api.lever.co/v0/postings/{slug}?mode=json
Ashby: api.ashbyhq.com/posting-api/job-board/{name}
SmartRecruiters: api.smartrecruiters.com/v1/companies/{id}/postings
Workday:  {tenant}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

For aggregator breadth beyond a company list, use a licensed API: Adzuna, Jooble, or SerpApi's Google Jobs engine







=== AI Security Research & Red Team Engineer  (6 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8097321?gh_jid=8097321
  [R] GATE 4+ years in offensive security, application security or other relevant field
        ↳ "4+ years in offensive security, application security or other relevant field"
  [R] Deep knowledge of AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts
        ↳ "Deep knowledge:  AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts all for use in the red team but also testing Cloudflare  uses."
  [R] Strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)
        ↳ "A strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)."
  [R] Experience using the MITRE ATT&CK framework to map coverage and identify blind spots in defensive telemetry
        ↳ "Experience using the MITRE ATT&CK framework to map coverage and identify "blind spots" in defensive telemetry."
  [R] Ability to explain complex exploits to non-technical stakeholders while maintaining credibility with engineering teams
        ↳ "The ability to explain a complex "0-day" exploit to a non-technical stakeholder while maintaining the respect of a deep-dive engineering team."
  [R] Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure
        ↳ "Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure."

=== Customer Engineer, Korea  (18 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8140643?gh_jid=8140643
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services,  Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal leveling)."
  [R] Ability to white-board, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four of the listed technical areas (Internet fundamentals, Security, Performance, AI Proficiency, Coding/Scripting, Developer Platform Fluency)
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments; familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement — workshops, code samples, documentation, or developer onboarding — that accelerates customer adoption of complex platforms
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% for customer meetings, conferences, industry events, and in-person team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."

=== Customer Engineer, Turkish Speaking  (19 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8158994?gh_jid=8158994
  [R] Fluency in English and Turkish (written and spoken)
        ↳ "Fluency in English and Turkish (written and spoken)."
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal levelling)."
  [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four technical areas out of the listed domains
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments, including infrastructure-as-code and CI/CD pipelines
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% for customer meetings, conferences, industry events, and in-person team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."

=== Customer Solutions Engineer  (14 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8220770?gh_jid=8220770
  [R] GATE 5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments.
        ↳ "5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments."
  [R] Working knowledge of Cloudflare product foundations: Application Security, CDN, Zero Trust/SASE, and Network Services.
        ↳ "Cloudflare product foundations: working knowledge of Application Security, CDN, Zero Trust/SASE, and Network Services."
  [R] Understanding of networking fundamentals: DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP.
        ↳ "Networking fundamentals: understanding of DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP."
  [R] Familiarity with web security basics: OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles.
        ↳ "Web security basics: familiarity with OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles."
  [R] Hands-on experience with the Cloudflare Dashboard, and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations.
        ↳ "Configuration and integration: hands-on experience with the Cloudflare Dashboard, and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations."
  [R] Ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding.
        ↳ "Observability: ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding."
  [R] Ability to read and debug REST API calls; basic proficiency with Python and Bash.
        ↳ "Scripting and APIs: ability to read and debug REST API calls; basic proficiency with Python and Bash."
  [R] Strong written and verbal communication skills, able to document clearly, summarize concisely, and interact professionally with both technical and non-technical customer contacts.
        ↳ "Strong written and verbal communication skills. Able to document clearly, summarize concisely, and interact professionally with both technical and non-technical customer contacts."
  [R] GATE Fluency in English is required.
        ↳ "Fluency in English is required."
  [P] Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001.
        ↳ "Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001 is a plus."
  [P] Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers).
        ↳ "Cloudflare Certifications: Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers)."
  [P] Direct experience onboarding or administering Cloudflare in a production environment.
        ↳ "Prior Cloudflare Experience: Direct experience onboarding or administering Cloudflare in a production environment."
  [P] Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management.
        ↳ "Automation Mindset: Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management."
  [P] Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation.
        ↳ "AI-Augmented Workflow: Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation."

=== Digital Customer Engineer - Swedish or Russian Speaker  (22 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8232806?gh_jid=8232806
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience
        ↳ "An undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience."
  [R] GATE Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, technical consulting, technical support, or a related field
        ↳ "Up to 1–5 years of professional experience in a customer-facing technical role, such as Sales Engineering, technical consulting, technical support, or a related field."
  [R] Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures
        ↳ "Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures."
  [R] Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes
        ↳ "Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes."
  [R] Understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth
        ↳ "An understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth."
  [R] Strong presentation and stakeholder-management skills, with ability to explain technical concepts to both practitioners and business decision-makers
        ↳ "Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers."
  [R] Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment
        ↳ "Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment."
  [R] Knowledge or experience in at least three of the listed technical breadth areas
        ↳ "Qualified candidates should demonstrate knowledge or experience in at least three of the following areas:"
  [R] Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts
        ↳ "Internet Fundamentals: Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts."
  [R] Familiarity with Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE
        ↳ "Security: Familiarity with areas such as Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE."
  [R] Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols
        ↳ "Performance: Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols."
  [R] Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation."
  [R] Experience with at least one coding/scripting language such as Python, JavaScript, Bash, Lua, or Go
        ↳ "Coding and Scripting: Experience with at least one language such as Python, JavaScript, Bash, Lua, or Go."
  [R] Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability
        ↳ "Developer Platform Fluency: Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability."
  [R] Curiosity, initiative, and a demonstrated ability to learn new technologies quickly
        ↳ "Curiosity, initiative, and a demonstrated ability to learn new technologies quickly."
  [R] GATE Native-like fluency, both written and spoken, in English AND (Swedish OR Russian)
        ↳ "Languages: Native-like fluency, both written & spoken, in English AND (Swedish OR Russian)"
  [P] Experience creating reusable technical assets such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops
        ↳ "Experience creating reusable technical assets, such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops."
  [P] Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud
        ↳ "Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud."
  [P] Exposure to modern application architectures including serverless computing, containers, microservices, and APIs
        ↳ "Exposure to modern application architectures, including serverless computing, containers, microservices, and APIs."
  [P] Knowledge of common application-security risks and mitigation strategies
        ↳ "Knowledge of common application-security risks and mitigation strategies."
  [P] Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls
        ↳ "Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls."
  [P] Experience working with SMB or Digital Native Business customers
        ↳ "Experience working with SMB or Digital Native Business customers."

=== Digital Presales Customer Engineer  (20 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8238758?gh_jid=8238758
  [R] GATE Mandarin is required to deal with customers in the Greater China region
        ↳ "Language: Mandarin is required to deal with customers in the Greater China region"
  [P] Cantonese is a plus
        ↳ "Cantonese is a plus"
  [R] Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services,  Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal leveling)."
  [R] Ability to white-board, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four of the listed technical areas (Internet fundamentals, Security, Performance, AI Proficiency, Coding/Scripting, Developer Platform Fluency)
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments; familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."

=== Forward Deployed Engineer (FDE)  (9 kept, 1 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/7572075?gh_jid=7572075
  [R] GATE 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security
        ↳ "10+ Years of Technical Customer Facing Experience: Proven track record as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security."
  [R] Extensive experience implementing and supporting complex technical solutions using Terraform for infrastructure management
        ↳ "Terraform Proficiency: Extensive experience implementing and supporting complex technical solutions using Terraform for infrastructure management."
  [R] Demonstrated ability to build trust and rapport in challenging environments, remaining flexible and persistent in establishing regular cadences with stakeholders
        ↳ "High-Stakes Relationship Management: Demonstrated ability to build trust and rapport in challenging environments, remaining flexible and persistent in establishing regular cadences with stakeholders."
  [R] Exceptional ability to navigate Slack-first communication cultures, providing clear guidance and managing technical threads under pressure
        ↳ "Advanced Communication: Exceptional ability to navigate "Slack-first" communication cultures, providing clear guidance and managing technical threads under pressure."
  [R] Strong technical understanding of and passion for AI/LLM concepts
        ↳ "AI/LLM Knowledge: A strong technical understanding of and passion for AI/LLM concepts, fitting the culture of a cutting-edge AI-centric organization."
  [R] Strong knowledge of networking protocols, cybersecurity, and industry standards such as Zero Trust/SASE
        ↳ "Technical Background: Strong knowledge of networking protocols, cybersecurity, and industry standards (e.g., Zero Trust/SASE)."
  [P] Experience or strong interest in transitioning application-heavy environments toward comprehensive Network Security and SASE models
        ↳ "Network Security Background: Experience or strong interest in transitioning application-heavy environments toward comprehensive Network Security and SASE models."
  [P] Proficiency in coding languages beyond Terraform to automate tasks at scale and build proof-of-concept setups
        ↳ "Scripting & Automation: Proficiency in coding languages beyond Terraform to automate tasks at scale and build proof-of-concept setups."
  [P] Experience managing or advising on project-based fund pools to maximize the value of a customer's strategic investment
        ↳ "Financial Acumen: Experience managing or advising on project-based fund pools to maximize the value of a customer's strategic investment."
  [DROPPED] Extensive and proven knowledge of Application Security, Workers and Workers AI, cybersecurity, web performance, and cloud infrastructure
        ↳ "Application Security Expertise: Extensive and proven knowledge of development platforms such as Cloudflare's Application Security, Workers and Workers AI, cybersecurity, web performance, and cloud infrastructure."

=== Forward Deployed Engineer, Professional Services  (7 kept, 2 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8043339?gh_jid=8043339
  [R] In-depth experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure
        ↳ "In Depth Experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure."
  [R] Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools
        ↳ "Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools."
  [R] Proven ability to work with Cloudflare products within Enterprise-level accounts
        ↳ "Proven ability to work with Cloudflare products within Enterprise-level accounts."
  [R] Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences
        ↳ "Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences."
  [R] Strong consultative skills with a track record of successfully solving complex technical problems in customer environments
        ↳ "Strong consultative skills with a track record of successfully solving complex technical problems in customer environments."
  [P] Hands-on experience with coding, Cloudflare Workers, and Workers AI
        ↳ "Hands-on experience with coding, Cloudflare Workers, and Workers AI."
  [P] Prior experience in customer onsite placement
        ↳ "Prior experience in customer onsite placement."
  [DROPPED] Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure
        ↳ "Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure."
  [DROPPED] Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack
        ↳ "Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack."

=== Forward Deployed Engineer, Professional Services  (7 kept, 2 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8043287?gh_jid=8043287
  [R] In-depth experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure
        ↳ "In Depth Experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure."
  [R] Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools
        ↳ "Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools."
  [R] Proven ability to work with Cloudflare products within Enterprise-level accounts
        ↳ "Proven ability to work with Cloudflare products within Enterprise-level accounts."
  [R] Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences
        ↳ "Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences."
  [R] Strong consultative skills with a track record of successfully solving complex technical problems in customer environments
        ↳ "Strong consultative skills with a track record of successfully solving complex technical problems in customer environments."
  [P] Hands-on experience with coding, Cloudflare Workers, and Workers AI
        ↳ "Hands-on experience with coding, Cloudflare Workers, and Workers AI."
  [P] Prior experience in customer onsite placement
        ↳ "Prior experience in customer onsite placement."
  [DROPPED] Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure
        ↳ "Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure."
  [DROPPED] Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack
        ↳ "Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack."

=== Forward Deployed Engineer, Professional Services  (7 kept, 2 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8043305?gh_jid=8043305
  [R] In-depth experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure
        ↳ "In Depth Experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure."
  [R] Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools
        ↳ "Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools."
  [R] Proven ability to work with Cloudflare products within Enterprise-level accounts
        ↳ "Proven ability to work with Cloudflare products within Enterprise-level accounts."
  [R] Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences
        ↳ "Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences."
  [R] Strong consultative skills with a track record of successfully solving complex technical problems in customer environments
        ↳ "Strong consultative skills with a track record of successfully solving complex technical problems in customer environments."
  [P] Hands-on experience with coding, Cloudflare Workers, and Workers AI
        ↳ "Hands-on experience with coding, Cloudflare Workers, and Workers AI."
  [P] Prior experience in customer onsite placement
        ↳ "Prior experience in customer onsite placement."
  [DROPPED] Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure
        ↳ "Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure."
  [DROPPED] Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack
        ↳ "Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack."

10 listings · 129 requirements kept · 7 dropped


[R] GATE 4+ years in offensive security, application security or other relevant field
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
[R] GATE 5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, 
[R] GATE Fluency in English is required.
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical 
[R] GATE Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, 
[R] GATE Native-like fluency, both written and spoken, in English AND (Swedish OR Russian)
[R] GATE Mandarin is required to deal with customers in the Greater China region
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
[R] GATE 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level 



=== AI Security Research & Red Team Engineer  (6 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8097321?gh_jid=8097321
  [R] GATE 4+ years in offensive security, application security or other relevant field
        ↳ "Experience: 4+ years in offensive security, application security or other relevant field"
  [R] Deep knowledge of AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts
        ↳ "Deep knowledge:  AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts all for use in the red team but also testing Cloudflare  uses."
  [R] Strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)
        ↳ "Technical Roots: A strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)."
  [R] Experience using the MITRE ATT&CK framework to map coverage and identify blind spots in defensive telemetry
        ↳ "Operational Mindset: Experience using the MITRE ATT&CK framework to map coverage and identify "blind spots" in defensive telemetry."
  [R] Ability to explain complex exploits to non-technical stakeholders while maintaining credibility with engineering teams
        ↳ "Communication Skills: The ability to explain a complex "0-day" exploit to a non-technical stakeholder while maintaining the respect of a deep-dive engineering team."
  [R] Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure
        ↳ "Tooling Familiarity: Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure."

=== Customer Engineer, Korea  (18 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8140643?gh_jid=8140643
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services,  Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal leveling)."
  [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four of the listed technical areas (internet fundamentals, security, performance, AI proficiency, coding/scripting, developer platform fluency)
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments, including infrastructure-as-code and CI/CD pipelines
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% for customer meetings, conferences, industry events, and team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."

=== Customer Engineer, Turkish Speaking  (19 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8158994?gh_jid=8158994
  [R] Fluency in English and Turkish (written and spoken)
        ↳ "Fluency in English and Turkish (written and spoken)."
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal levelling)."
  [R] Ability to white-board, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four of the listed technical areas
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments, with familiarity with infrastructure-as-code, CI/CD pipelines, and observability
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% for customer meetings, conferences, industry events, and in-person team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."

=== Customer Solutions Engineer  (14 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8220770?gh_jid=8220770
  [R] GATE 5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments
        ↳ "5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments."
  [R] Working knowledge of Cloudflare product foundations: Application Security, CDN, Zero Trust/SASE, and Network Services
        ↳ "Cloudflare product foundations: working knowledge of Application Security, CDN, Zero Trust/SASE, and Network Services."
  [R] Understanding of networking fundamentals: DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP
        ↳ "Networking fundamentals: understanding of DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP."
  [R] Familiarity with web security basics: OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles
        ↳ "Web security basics: familiarity with OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles."
  [R] Hands-on experience with the Cloudflare Dashboard and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations
        ↳ "Configuration and integration: hands-on experience with the Cloudflare Dashboard, and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations."
  [R] Ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding
        ↳ "Observability: ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding."
  [R] Ability to read and debug REST API calls; basic proficiency with Python and Bash
        ↳ "Scripting and APIs: ability to read and debug REST API calls; basic proficiency with Python and Bash."
  [R] Strong written and verbal communication skills; able to document clearly, summarize concisely, and interact professionally with both technical and non-technical customer contacts
        ↳ "Strong written and verbal communication skills. Able to document clearly, summarize concisely, and interact professionally with both technical and non-technical customer contacts."
  [R] GATE Fluency in English is required
        ↳ "Fluency in English is required."
  [P] Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001
        ↳ "Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001 is a plus."
  [P] Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers)
        ↳ "Cloudflare Certifications: Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers)."
  [P] Direct experience onboarding or administering Cloudflare in a production environment
        ↳ "Prior Cloudflare Experience: Direct experience onboarding or administering Cloudflare in a production environment."
  [P] Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management
        ↳ "Automation Mindset: Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management."
  [P] Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation
        ↳ "AI-Augmented Workflow: Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation."

=== Digital Customer Engineer - Swedish or Russian Speaker  (22 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8232806?gh_jid=8232806
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience
        ↳ "An undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience."
  [R] GATE Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, technical consulting, technical support, or a related field
        ↳ "Up to 1–5 years of professional experience in a customer-facing technical role, such as Sales Engineering, technical consulting, technical support, or a related field."
  [R] Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures
        ↳ "Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures."
  [R] Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes
        ↳ "Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes."
  [R] Understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth
        ↳ "An understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth."
  [R] Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers
        ↳ "Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers."
  [R] Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment
        ↳ "Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment."
  [R] Knowledge or experience in at least three of the listed technical breadth areas
        ↳ "Qualified candidates should demonstrate knowledge or experience in at least three of the following areas:"
  [R] Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts
        ↳ "Internet Fundamentals: Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts."
  [R] Familiarity with Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE
        ↳ "Security: Familiarity with areas such as Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE."
  [R] Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols
        ↳ "Performance: Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols."
  [R] Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation."
  [R] Experience with at least one coding/scripting language such as Python, JavaScript, Bash, Lua, or Go
        ↳ "Coding and Scripting: Experience with at least one language such as Python, JavaScript, Bash, Lua, or Go."
  [R] Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability
        ↳ "Developer Platform Fluency: Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability."
  [R] Curiosity, initiative, and a demonstrated ability to learn new technologies quickly
        ↳ "Curiosity, initiative, and a demonstrated ability to learn new technologies quickly."
  [R] GATE Native-like fluency, both written and spoken, in English AND (Swedish OR Russian)
        ↳ "Languages: Native-like fluency, both written & spoken, in English AND (Swedish OR Russian)"
  [P] Experience creating reusable technical assets such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops
        ↳ "Experience creating reusable technical assets, such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops."
  [P] Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud
        ↳ "Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud."
  [P] Exposure to modern application architectures, including serverless computing, containers, microservices, and APIs
        ↳ "Exposure to modern application architectures, including serverless computing, containers, microservices, and APIs."
  [P] Knowledge of common application-security risks and mitigation strategies
        ↳ "Knowledge of common application-security risks and mitigation strategies."
  [P] Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls
        ↳ "Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls."
  [P] Experience working with SMB or Digital Native Business customers
        ↳ "Experience working with SMB or Digital Native Business customers."

=== Digital Presales Customer Engineer  (20 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8238758?gh_jid=8238758
  [R] GATE Mandarin is required to deal with customers in the Greater China region
        ↳ "Language: Mandarin is required to deal with customers in the Greater China region"
  [P] Cantonese is a plus
        ↳ "Cantonese is a plus"
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services,  Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal leveling)."
  [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four of the listed technical areas
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments, including infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developer onboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."
/Users/jf/Desktop/portfolio/lumbergh/my_agent/extract.py:88: DeprecationWarning: Agent.structured_output method is deprecated. You should pass in `structured_output_model` directly into the agent invocation. see: https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/
  result = _agent().structured_output(

=== Director, Customer Engineering   (19 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8007189?gh_jid=8007189
  [R] GATE 10+ years of experience in technical go-to-market roles with a demonstrated track record of building and managing high-performing teams in SaaS, cloud, or infrastructure companies
        ↳ "10+ years of experience in technical go-to-market roles with a demonstrated track record of building and managing high-performing teams in SaaS, cloud, or infrastructure companies."
  [R] GATE Prior experience managing managers and owning revenue targets at scale is required
        ↳ "Prior experience managing managers and owning revenue targets at scale is required."
  [R] Proven experience owning and forecasting a large CE or Solutions Engineering revenue number in an enterprise B2B or infrastructure environment
        ↳ "Proven experience owning and forecasting a large CE or Solutions Engineering revenue number in an enterprise B2B or infrastructure environment."
  [R] Deep understanding of ACV, renewal, expansion, consumption, and platform economics
        ↳ "Deep understanding of ACV, renewal, expansion, consumption, and platform economics."
  [R] Exceptional ability to inspire, coach, and develop senior managers and senior individual contributors
        ↳ "Exceptional ability to inspire, coach, and develop senior managers and senior individual contributors."
  [R] Comfortable presenting to and influencing C-level executives inside and outside Cloudflare
        ↳ "Comfortable presenting to and influencing C-level executives inside and outside Cloudflare."
  [R] Ability to synthesize market signals, customer feedback, and business data into a clear operating plan for a multi-team organization
        ↳ "Ability to synthesize market signals, customer feedback, and business data into a clear operating plan for a multi-team organization."
  [R] Outstanding written and verbal communication skills, capable of representing the CE organization in executive reviews, board-level discussions, and large internal forums
        ↳ "Outstanding written and verbal communication skills. Capable of representing the CE organization in executive reviews, board-level discussions, and large internal forums."
  [R] Technical fluency in at least two or three domains: Internet fundamentals (DNS, HTTP(S), TCP/IP, BGP, SSL/TLS, and network architecture)
        ↳ "Internet fundamentals: Strong understanding of DNS, HTTP(S), TCP/IP, BGP, SSL/TLS, and network architecture."
  [R] Technical fluency in security: WAF, Bot Management, Zero Trust, SASE, DDoS mitigation, and modern enterprise security posture
        ↳ "Security: Foundational knowledge of WAF, Bot Management, Zero Trust, SASE, DDoS mitigation, and modern enterprise security posture."
  [R] Technical fluency in performance/networking: caching, latency, content delivery, traffic steering, and global network architecture
        ↳ "Performance / Networking: Foundational knowledge of caching, latency, content delivery, traffic steering, and global network architecture."
  [R] Technical fluency in AI and platform: AI-augmented workflows, LLMs, automation, cloud platforms, edge services, and developer tooling
        ↳ "AI & Platform: Familiarity with AI-augmented workflows, LLMs, automation, cloud platforms, edge services, and developer tooling."
  [P] Direct experience with Cloudflare's product portfolio, including Application Security, CDN, Zero Trust/SASE, Network Services, or AI/Workers platform
        ↳ "Cloudflare Domain Expertise: Direct experience with Cloudflare's product portfolio, including Application Security, CDN, Zero Trust/SASE, Network Services, or AI/Workers platform."
  [P] Experience leading distributed teams across multiple regions and time zones
        ↳ "Global Scale: Experience leading distributed teams across multiple regions and time zones."
  [P] Proven track record of leading through organizational change, role redefinition, and operating model evolution
        ↳ "Transformation Leadership: Proven track record of leading through organizational change, role redefinition, and operating model evolution."
  [P] Experience as an executive sponsor for Fortune 500 or strategic accounts
        ↳ "Executive Customer Engagement: Experience as an executive sponsor for Fortune 500 or strategic accounts."
  [P] Track record of building dashboards, playbooks, and scalable processes for technical field organizations
        ↳ "Operational Rigor: Track record of building dashboards, playbooks, and scalable processes for technical field organizations."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, Business, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, Business, or a related field."
  [R] Role may require travel up to 25–50%
        ↳ "This role may require travel up to 25–50% to attend customer meetings, executive briefings, team offsites, industry events, and in-person collaboration."

=== Engineering Manager, Agentic Internet & Data Insights  (20 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8143649?gh_jid=8143649
  [R] Led and developed high-performing engineering team(s) with demonstrable results in shipping and growing people
        ↳ "You have led and developed high-performing engineering team(s) and can point to what that team shipped and how the people on it grew."
  [R] Technically credible with experienced engineers, able to review designs and understand trade-offs in distributed or data platform systems
        ↳ "You are technically credible with experienced engineers. You can review a design, understand the trade-offs in a distributed system or data platform, and recognize when a technical problem needs deeper investigation."
  [R] Able to manage a team working across several related technical areas and create clarity without requiring every problem to fit neatly into a single box
        ↳ "You are comfortable managing a team working across several related technical areas and can create clarity without requiring every problem to fit neatly into a single box."
  [R] Cares deeply about reliability and quality, particularly when system output is data people use to understand the Internet
        ↳ "You care deeply about reliability and quality, particularly when the output of a system is data that people use to understand the Internet."
  [R] Strong product judgment and enjoys working with Product Management to decide what is worth building
        ↳ "You have strong product judgment and enjoy working with Product Management to decide what is worth building, what needs improvement and what should not be built at all."
  [R] Comfortable with ambiguity and finding structure in areas where the opportunity is clearer than the roadmap
        ↳ "You are comfortable with ambiguity and with finding structure in areas where the opportunity is clearer than the roadmap."
  [R] Communicates clearly, gives direct feedback, and can explain complex technical decisions to both engineers and non-engineers
        ↳ "You communicate clearly, give direct feedback, and can explain complex technical decisions to both engineers and non-engineers."
  [R] Strong technical grounding in distributed systems, search systems, data-intensive systems, Internet infrastructure, or adjacent areas
        ↳ "Strong technical grounding in distributed systems, search systems, data-intensive systems, Internet infrastructure, or adjacent areas."
  [R] Experience building or operating products involving crawling, content ingestion, indexing, retrieval, analytics, or large-scale data processing
        ↳ "Experience building or operating products involving crawling, content ingestion, indexing, retrieval, analytics, or large-scale data processing."
  [R] Experience operating systems where correctness, reliability, and quality matter as much as feature delivery
        ↳ "Experience operating systems where correctness, reliability, and quality matter as much as feature delivery."
  [R] Track record of hiring, developing, and retaining strong engineers
        ↳ "A track record of hiring, developing, and retaining strong engineers."
  [R] Experience partnering closely with Product Management to shape and execute a roadmap
        ↳ "Experience partnering closely with Product Management to shape and execute a roadmap."
  [R] Experience taking products or major capabilities from an ambiguous opportunity to a clear customer outcome
        ↳ "Experience taking products or major capabilities from an ambiguous opportunity to a clear customer outcome."
  [R] Strong written and verbal communication
        ↳ "Strong written and verbal communication."
  [P] Familiarity with Retrieval-Augmented Generation (RAG)
        ↳ "Familiarity with Retrieval-Augmented Generation (RAG), which combines information retrieval with generative AI to produce answers grounded in selected source material."
  [P] Experience building products for AI developers, AI agents, publishers, or content-heavy websites
        ↳ "Experience building products for AI developers, AI agents, publishers, or content-heavy websites."
  [P] Experience working with large
  -scale telemetry or Internet-scale datasets
        ↳ "Experience working with large-scale telemetry or Internet-scale datasets."
  [P] Experience turning complex underlying systems or data into useful products for a broad audience
        ↳ "Experience turning complex underlying systems or data into useful products for a broad audience."
  [P] Familiarity with Cloudflare Radar, Internet measurement research, or the broader ecosystem of tools used to understand Internet performance, availability and security
        ↳ "Familiarity with Cloudflare Radar, Internet measurement research, or the broader ecosystem of tools used to understand Internet performance, availability and security."
  [R] GATE Role is based in Lisbon, Portugal
        ↳ "Available Locations: Lisbon, Portugal"

=== Engineering Manager, Browser Run  (15 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8099000?gh_jid=8099000
  [R] GATE 2+ years managing engineering teams
        ↳ "2+ years managing engineering teams, on top of a solid track record as a hands-on engineer."
  [R] GATE Solid track record as a hands-on engineer
        ↳ "2+ years managing engineering teams, on top of a solid track record as a hands-on engineer."
  [R] Experience owning a production service end to end, including on-call rotation, capacity planning and incident review
        ↳ "Experience owning a production service end to end, including on-call rotation, capacity planning and incident review."
  [R] Demonstrated experience growing engineers — promotions supported, and ideally a team lead or first-line manager developed
        ↳ "Demonstrated experience growing engineers — promotions you supported, and ideally a team lead or first-line manager you developed."
  [R] Hands-on familiarity with browser automation — Chrome DevTools Protocol, Puppeteer or Playwright — or with the browser internals underneath them
        ↳ "Hands-on familiarity with browser automation — Chrome DevTools Protocol, Puppeteer or Playwright — or with the browser internals underneath them."
  [R] Strong technical grounding in distributed systems, web platform fundamentals (HTTP, JavaScript execution models, rendering) or cloud infrastructure
        ↳ "Strong technical grounding in distributed systems, web platform fundamentals (HTTP, JavaScript execution models, rendering) or cloud infrastructure — enough to hold a credible design review."
  [R] Track record of partnering with Product Management to set and defend a roadmap, including saying no
        ↳ "A track record of partnering with Product Management to set and defend a roadmap, including saying no."
  [R] Excellent written communication for internal and public-facing technical content
        ↳ "Excellent written communication for internal and public-facing technical content."
  [R] Experience hiring: writing job descriptions, running interview loops, calibrating a panel and closing candidates
        ↳ "Experience hiring: writing job descriptions, running interview loops, calibrating a panel and closing candidates."
  [P] Experience running headless browser infrastructure at scale — browser fleet management, sandboxing and resource isolation
        ↳ "Experience running headless browser infrastructure at scale — browser fleet management, sandboxing and resource isolation."
  [P] Experience shipping AI or agent-facing platform primitives, such as MCP servers, tool-calling surfaces or agent orchestration
        ↳ "Experience shipping AI or agent-facing platform primitives, such as MCP servers, tool-calling surfaces or agent orchestration."
  [P] Familiarity with the Cloudflare Workers development platform: Workers, Durable Objects, Workflows, R2, D1
        ↳ "Familiarity with the Cloudflare Workers development platform: Workers, Durable Objects, Workflows, R2, D1."
  [P] Experience taking an internal tool to a billed external product, including usage metering and pricing
        ↳ "Experience taking an internal tool to a billed external product, including usage metering and pricing."
  [P] Experience managing a distributed team across time zones
        ↳ "Experience managing a distributed team across time zones."
  [P] Open source maintainership, or a public body of technical writing
        ↳ "Open source maintainership, or a public body of technical writing."

=== Engineering Manager, Cloudflare Network Interconnect  (16 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8083701?gh_jid=8083701
  [R] GATE 3+ years experience as an Engineering Manager for a team of Software and Systems Engineers
        ↳ "3+ years experience as an Engineering Manager for a team of Software and Systems Engineers."
  [R] Track record of managing a team including hiring, onboarding, and professional development
        ↳ "Demonstrate a track record of managing a team including hiring, onboarding, and professional development. You inspire your team to reach higher. You're as good at explaining "why" as you are "how"."
  [R] Ability to plan and oversee execution to meet commitments and deliver with predictability
        ↳ "Excel at planning and overseeing execution to meet commitments and deliver with predictability."
  [R] Technical background in IP networking: BGP, Layer 3 routing, physical and virtual interconnect technologies (cross-connects, VLANs, partner fabric integrations)
        ↳ "Technical background in IP networking: BGP, Layer 3 routing, physical and virtual interconnect technologies (cross-connects, VLANs, partner fabric integrations)."
  [R] Experience building or operating provisioning/automation systems for network infrastructure
        ↳ "Experience building or operating provisioning/automation systems for network infrastructure."
  [R] Experience with monitoring, alerting, and debugging distributed systems
        ↳ "Experience with monitoring, alerting, and debugging distributed systems."
  [R] Experience participating in and/or managing an on-call rotation for production services with direct customer impact
        ↳ "Experience participating in and/or managing an on-call rotation for production services with direct customer impact."
  [R] Willingness to adopt and integrate AI tools and systems into your workflow
        ↳ "Willingness to adopt and integrate AI tools and systems into your workflow."
  [R] Clarity in written and verbal communication
        ↳ "Clarity in written and verbal communication."
  [P] Hands-on experience with BGP configuration, route policy, and peering operations
        ↳ "Hands-on experience with BGP configuration, route policy, and peering operations."
  [P] Familiarity with network inventory and IPAM systems (e.g., NetBox)
        ↳ "Familiarity with network inventory and IPAM systems (e.g., NetBox)."
  [P] Experience with cloud provider networking (AWS Direct Connect, GCP Partner Interconnect, Azure ExpressRoute)
        ↳ "Experience with cloud provider networking (AWS Direct Connect, GCP Partner Interconnect, Azure ExpressRoute)."
  [P] Knowledge of GRE, VXLAN, or other overlay/tunnel technologies
        ↳ "Knowledge of GRE, VXLAN, or other overlay/tunnel technologies."
  [P] Systems-level programming experience in Go, Python, Rust, C, or C++
        ↳ "Systems-level programming experience in Go, Python, Rust, C, or C++."
  [P] Comfort with customer-facing technical communication (escalation handling, partner engagements)
        ↳ "Comfort with customer-facing technical communication (escalation handling, partner engagements)."
  [P] Experience using AI-assisted engineering tools (e.g., code completion, codebase analysis, log/data exploration) in a professional setting
        ↳ "Experience using AI-assisted engineering tools (e.g., code completion, codebase analysis, log/data exploration) in a professional setting."

10 listings · 169 requirements kept · 0 dropped


[R] GATE 4+ years in offensive security, application security or other relevant field
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
[R] GATE 5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, 
[R] GATE Fluency in English is required
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical 
[R] GATE Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, 
[R] GATE Native-like fluency, both written and spoken, in English AND (Swedish OR Russian)
[R] GATE Mandarin is required to deal with customers in the Greater China region
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
[R] GATE 10+ years of experience in technical go-to-market roles with a demonstrated track record of building and 
[R] GATE Prior experience managing managers and owning revenue targets at scale is required
[R] GATE Undergraduate or graduate degree in Computer Science, Engineering, Business, or a related field
[R] GATE Role is based in Lisbon, Portugal
[R] GATE 2+ years managing engineering teams
[R] GATE Solid track record as a hands-on engineer
[R] GATE 3+ years experience as an Engineering Manager for a team of Software and Systems Engineers































=== AI Security Research & Red Team Engineer  (6 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8097321?gh_jid=8097321
  [R] GATE 4+ years in offensive security, application security or other relevant field
        ↳ "Experience: 4+ years in offensive security, application security or other relevant field"
  [R] Deep knowledge of AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts
        ↳ "Deep knowledge:  AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts all for use in the red team but also testing Cloudflare  uses."
  [R] Strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)
        ↳ "Technical Roots: A strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)."
  [R] Experience using the MITRE ATT&CK framework to map coverage and identify blind spots in defensive telemetry
        ↳ "Operational Mindset: Experience using the MITRE ATT&CK framework to map coverage and identify "blind spots" in defensive telemetry."
  [R] Ability to explain complex exploits to non-technical stakeholders while maintaining credibility with engineering teams
        ↳ "Communication Skills: The ability to explain a complex "0-day" exploit to a non-technical stakeholder while maintaining the respect of a deep-dive engineering team."
  [R] Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure
        ↳ "Tooling Familiarity: Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure."

=== Customer Engineering Specialist - Network Services  (21 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/7525971?gh_jid=7525971
  [R] GATE 5+ years in Customer Engineering, Pre-sales, Solutions or Systems Engineering, or Technical Sales
        ↳ "GTM experience: 5+ years in Customer Engineering, Pre-sales, Solutions or Systems Engineering, or Technical Sales. You should have experience guiding customers through discovery, solution design, POC and handover to delivery or support."
  [R] Strong working knowledge of BGP (eBGP, route advertisement and filtering, AS paths, communities, anycast, RPKI and route hygiene), static and dynamic routing, subnetting, route-based policy and split tunnels
        ↳ "BGP and routing: Strong working knowledge of BGP (eBGP, route advertisement and filtering, AS paths, communities, anycast, RPKI and routehygiene). You should also be comfortable with static and dynamic routing, subnetting, route-based policy and split tunnels."
  [R] Deep understanding of the TCP/IP protocol stack and packet-level troubleshooting, including MTU/MSS, tunneling (GRE, IPsec), NAT and asymmetric routing
        ↳ "TCP/IP: Deep understanding of the TCP/IP protocol stack and packet-level troubleshooting (for example with tcpdump and Wireshark). This includes MTU/MSS, tunneling (GRE, IPsec), NAT and asymmetric routing."
  [R] Understanding of L3/L4/L7 DDoS attack types and mitigation approaches, and how on-demand and always-on protection differ
        ↳ "DDoS protection: Understanding of L3/L4/L7 DDoS attack types and mitigation approaches (for example volumetric floods, SYN floods, amplification and reflection attacks). You should also understand how on-demand and always-on protection differ."
  [R] Familiarity with SD-WAN architectures and routing protocols, underlay and overlay design, local internet breakout, branch connectivity, and migration from MPLS or legacy WAN
        ↳ "SD-WAN and WAN architecture: Familiarity with SD-WAN architectures and routing protocols (BGP and OSPF overlays), underlay and overlay design, local internet breakout, branch connectivity, and migration from MPLS or legacy WAN."
  [R] Fluent in English, written and spoken
        ↳ "Fluent in English, written and spoken. Additional languages are a plus."
  [P] Additional languages beyond English are a plus
        ↳ "Additional languages are a plus."
  [R] Ability to manage a project, work to deadlines and prioritize between competing goals
        ↳ "Ability to manage a project, work to deadlines and prioritize between competing goals."
  [R] Curiosity and learning agility to keep up with industry trends and Cloudflare's own products
        ↳ "Curiosity and learning agility. Cloudflare sits at the cutting edge of internet technology, so you are expected to keep up with industry trends as well as our own products."
  [P] Good knowledge of DNS, including authoritative and recursive resolution, DNSSEC, DNS over HTTPS/TLS, DNS-based attacks and DNS filtering
        ↳ "DNS: Good knowledge of DNS, including authoritative and recursive resolution, DNSSEC, DNS over HTTPS/TLS, DNS-based attacks (such as tunneling and cache poisoning) and DNS filtering."
  [P] Detailed understanding of the path from user to application, including hybrid and multi-cloud architectures (Azure, AWS, GCP)
        ↳ "Detailed understanding of the path from user to application, including hybrid and multi-cloud architectures (Azure, AWS, GCP)."
  [P] Knowledge of end-user and application security risks including DDoS, malware, phishing, viruses, ransomware
        ↳ "Knowledge of end-user and application security risks. These include DDoS, malware, phishing, viruses, ransomware."
  [P] Knowledge of VPN and remote access challenges, and moving to Zero Trust access
        ↳ "VPN and remote access challenges, and moving to Zero Trust access."
  [P] Familiarity with SIEM and log analytics platforms, and network telemetry such as NetFlow and sFlow
        ↳ "SIEM and log analytics platforms. You should also be comfortable with network telemetry such as NetFlow and sFlow."
  [P] Experience and knowledge with network and security vendors including Cisco, Juniper, Fortinet, Palo Alto Networks, and Check Point
        ↳ "Experience and knowledge with network and security vendors, including Cisco, Juniper, Fortinet, Palo Alto Networks, and Check Point (covering architecture, capabilities, configuration, and troubleshooting)."
  [P] Understanding of the market for CDN providers, WAF, remote access, next-gen firewalls, CASB, DDoS mitigation, SD-WAN and secure gateway solutions
        ↳ "Understanding of the market for CDN providers, Web Application Firewalls, remote access solutions, next-generation firewalls, CASB, DDoS mitigation, SD-WAN and secure gateway solutions."
  [P] Knowledge of SASE concepts and Zero Trust networking architectures
        ↳ "SASE concepts and Zero Trust networking architectures."
  [P] Knowledge of Cloudflare Zero Trust solutions: Access, Gateway, Browser Isolation, and WARP client deployment
        ↳ "Knowledge of Cloudflare Zero Trust solutions: Access, Gateway, Browser Isolation, and WARP client deployment."
  [P] Knowledge of Secure Web Gateway, CASB and DLP
        ↳ "Secure Web Gateway, CASB and DLP."
  [P] Knowledge of IdP and authentication (SAML, OTP), SaaS application integration and tenant controls
        ↳ "IdP and authentication (SAML, OTP), plus SaaS application integration and tenant controls."
  [P] Client OS fundamentals and software distribution knowledge
        ↳ "Client OS fundamentals and software distribution."

=== Customer Engineer, Korea  (17 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8140643?gh_jid=8140643
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services,  Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal leveling)."
  [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Technical depth in at least four of the listed technical areas (Internet fundamentals, Security, Performance, AI Proficiency, Coding/Scripting, Developer Platform Fluency)
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computingfunctions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments, with familiarity with infrastructure-as-code, CI/CD pipelines, and observability
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks,and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developeronboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."

=== Customer Engineer, Turkish Speaking  (18 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8158994?gh_jid=8158994
  [R] Fluency in English and Turkish (written and spoken)
        ↳ "Fluency in English and Turkish (written and spoken)."
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior,Staff, or Principal levelling)."
  [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four technical areas listed (Internet fundamentals, Security, Performance, AI Proficiency, Coding/Scripting, Developer Platform Fluency)
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computingfunctions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments; familiarity with infrastructure-as-code, CI/CD pipelines, and observability
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks,and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding that accelerates customer adoption
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developeronboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."

=== Customer Solutions Engineer  (14 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8220770?gh_jid=8220770
  [R] GATE 5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments.
        ↳ "5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments."
  [R] Working knowledge of Cloudflare product foundations: Application Security, CDN, Zero Trust/SASE, and Network Services.
        ↳ "Cloudflare product foundations: working knowledge of Application Security, CDN, Zero Trust/SASE, and Network Services."
  [R] Understanding of networking fundamentals: DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP.
        ↳ "Networking fundamentals: understanding of DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP."
  [R] Familiarity with web security basics: OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles.
        ↳ "Web security basics: familiarity with OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles."
  [R] Hands-on experience with the Cloudflare Dashboard, and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations.
        ↳ "Configuration and integration: hands-on experience with the Cloudflare Dashboard, and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations."
  [R] Ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding.
        ↳ "Observability: ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding."
  [R] Ability to read and debug REST API calls; basic proficiency with Python and Bash.
        ↳ "Scripting and APIs: ability to read and debug REST API calls; basic proficiency with Python and Bash."
  [R] Strong written and verbal communication skills, able to document clearly, summarize concisely, and interact professionally with both technicaland non-technical customer contacts.
        ↳ "Strong written and verbal communication skills. Able to document clearly, summarize concisely, and interact professionally with both technical and non-technical customer contacts."
  [P] Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001.
        ↳ "Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001 is a plus."
  [P] Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers).
        ↳ "Cloudflare Certifications: Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers)."
  [P] Direct experience onboarding or administering Cloudflare in a production environment.
        ↳ "Prior Cloudflare Experience: Direct experience onboarding or administering Cloudflare in a production environment."
  [P] Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management.
        ↳ "Automation Mindset: Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management."
  [P] Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation.
        ↳ "AI-Augmented Workflow: Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation."
  [R] GATE Fluency in English is required.
        ↳ "Fluency in English is required."

=== Digital Customer Engineer - Swedish or Russian Speaker  (22 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8232806?gh_jid=8232806
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience
        ↳ "An undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience."
  [R] GATE Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, technical consulting, technicalsupport, or a related field
        ↳ "Up to 1–5 years of professional experience in a customer-facing technical role, such as Sales Engineering, technical consulting, technical support, or a related field."
  [R] Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures
        ↳ "Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures."
  [R] Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes
        ↳ "Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes."
  [R] Understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth
        ↳ "An understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth."
  [R] Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers
        ↳ "Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers."
  [R] Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment
        ↳ "Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment."
  [R] Knowledge or experience in at least three of the listed technical breadth areas
        ↳ "Qualified candidates should demonstrate knowledge or experience in at least three of the following areas:"
  [R] Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts
        ↳ "Internet Fundamentals: Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts."
  [R] Familiarity with Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE
        ↳ "Security: Familiarity with areas such as Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE."
  [R] Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols
        ↳ "Performance: Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols."
  [R] Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation."
  [R] Experience with at least one coding/scripting language such as Python, JavaScript, Bash, Lua, or Go
        ↳ "Coding and Scripting: Experience with at least one language such as Python, JavaScript, Bash, Lua, or Go."
  [R] Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability
        ↳ "Developer Platform Fluency: Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability."
  [R] Curiosity, initiative, and a demonstrated ability to learn new technologies quickly
        ↳ "Curiosity, initiative, and a demonstrated ability to learn new technologies quickly."
  [R] GATE Native-like fluency in English AND either Swedish or Russian (written and spoken)
        ↳ "Languages: Native-like fluency, both written & spoken, in English AND (Swedish OR Russian)"
  [P] Experience creating reusable technical assets such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops
        ↳ "Experience creating reusable technical assets, such as demonstrations, code samples, technical documentation, reference architectures, orcustomer workshops."
  [P] Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud
        ↳ "Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud."
  [P] Exposure to modern application architectures including serverless computing, containers, microservices, and APIs
        ↳ "Exposure to modern application architectures, including serverless computing, containers, microservices, and APIs."
  [P] Knowledge of common application-security risks and mitigation strategies
        ↳ "Knowledge of common application-security risks and mitigation strategies."
  [P] Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls
        ↳ "Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls."
  [P] Experience working with SMB or Digital Native Business customers
        ↳ "Experience working with SMB or Digital Native Business customers."

=== Digital Presales Customer Engineer  (20 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8238758?gh_jid=8238758
  [R] GATE Mandarin is required to deal with customers in the Greater China region
        ↳ "Language: Mandarin is required to deal with customers in the Greater China region"
  [P] Cantonese is a plus
        ↳ "Cantonese is a plus"
  [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
        ↳ "Experience: Experience in a customer-facing technical role, such as Solutions Engineering, Customer Engineering, Professional Services,  Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer (years of experience required will vary based on Associate, Senior, Staff, or Principal leveling)."
  [R] Ability to white-board, design, and articulate complex enterprise network and security architectures clearly
        ↳ "Architectural Mindset: Ability to white-board, design, and articulate complex enterprise network and security architectures clearly."
  [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
        ↳ "Consultative & Advisory Skills: Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives."
  [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
        ↳ "Commercial Mindset: Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles."
  [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
        ↳ "Communication: Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy."
  [R] Depth in at least four of the listed technical areas
        ↳ "Technical Breadth: We do not expect every candidate to be an expert in every domain. Qualified candidates will demonstrate depth in at least four of the technical areas below:"
  [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), andSSL/TLS
        ↳ "Internet fundamentals: Deep understanding of how the Internet works, including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS."
  [R] Expertise in security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
        ↳ "Security: Expertise in the security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts."
  [R] Expertise in performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
        ↳ "Performance: Expertise in the performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3."
  [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
        ↳ "AI Proficiency: Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation to augment everyday CE workflows."
  [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computingfunctions
        ↳ "Coding/Scripting: Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions."
  [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments; familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments
        ↳ "Developer Platform Fluency: Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks,and developer tooling in cloud-native environments. Familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments."
  [P] Track record of creating and delivering technical enablement — workshops, code samples, documentation, or developer onboarding — that accelerates customer adoption of complex platforms
        ↳ "Technical Enablement: Track record of creating and delivering technical enablement - workshops, code samples, documentation, or developeronboarding - that accelerates customer adoption of complex platforms."
  [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
        ↳ "Applied AI Knowledge: Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls."
  [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
        ↳ "Regulatory Knowledge: Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2."
  [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
        ↳ "Hyperscaler / Digital Native Background: Talent coming out of hyperscalers, digital natives, distributed systems environments, or startups is strongly valued for its deeper cloud fluency and advanced architecture depth."
  [R] GATE Undergraduate or graduate degree in Computer Science, Engineering, or a related field
        ↳ "Undergraduate or graduate degree in Computer Science, Engineering, or a related field."
  [R] Willingness to travel up to 20–50% for customer meetings, conferences, industry events, and in-person team collaboration
        ↳ "This role may require travel up to 20–50% to attend customer meetings, conferences, industry events, and in-person team collaboration."

=== Forward Deployed Engineer (FDE)  (10 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/7572075?gh_jid=7572075
  [R] GATE 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security
        ↳ "10+ Years of Technical Customer Facing Experience: Proven track record as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security."
  [R] Extensive and proven knowledge of Application Security, Workers and Workers AI, cybersecurity, web performance, and cloud infrastructure
        ↳ "Application Security Expertise: Extensive and proven knowledge of development platforms such as Cloudflare's Application Security, Workers and Workers AI, cybersecurity, web performance, and cloud infrastructure."
  [R] Extensive experience implementing and supporting complex technical solutions using Terraform for infrastructure management
        ↳ "Terraform Proficiency: Extensive experience implementing and supporting complex technical solutions using Terraform for infrastructure management."
  [R] Demonstrated ability to build trust and rapport in challenging environments, remaining flexible and persistent in establishing regular cadences with stakeholders
        ↳ "High-Stakes Relationship Management: Demonstrated ability to build trust and rapport in challenging environments, remaining flexible and persistent in establishing regular cadences with stakeholders."
  [R] Exceptional ability to navigate Slack-first communication cultures, providing clear guidance and managing technical threads under pressure
        ↳ "Advanced Communication: Exceptional ability to navigate "Slack-first" communication cultures, providing clear guidance and managing technical threads under pressure."
  [R] Strong technical understanding of and passion for AI/LLM concepts
        ↳ "AI/LLM Knowledge: A strong technical understanding of and passion for AI/LLM concepts, fitting the culture of a cutting-edge AI-centric organization."
  [R] Strong knowledge of networking protocols, cybersecurity, and industry standards such as Zero Trust/SASE
        ↳ "Technical Background: Strong knowledge of networking protocols, cybersecurity, and industry standards (e.g., Zero Trust/SASE)."
  [P] Experience or strong interest in transitioning application-heavy environments toward comprehensive Network Security and SASE models
        ↳ "Network Security Background: Experience or strong interest in transitioning application-heavy environments toward comprehensive Network Security and SASE models."
  [P] Proficiency in coding languages beyond Terraform to automate tasks at scale and build proof-of-concept setups
        ↳ "Scripting & Automation: Proficiency in coding languages beyond Terraform to automate tasks at scale and build proof-of-concept setups."
  [P] Experience managing or advising on project-based fund pools to maximize the value of a customer's strategic investment
        ↳ "Financial Acumen: Experience managing or advising on project-based fund pools to maximize the value of a customer's strategic investment."

=== Forward Deployed Engineer, Professional Services  (9 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8043305?gh_jid=8043305
  [R] In-depth experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure
        ↳ "In Depth Experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure."
  [R] Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure
        ↳ "Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure."
  [R] Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools
        ↳ "Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools."
  [R] Proven ability to work with Cloudflare products within Enterprise-level accounts
        ↳ "Proven ability to work with Cloudflare products within Enterprise-level accounts."
  [R] Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences
        ↳ "Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences."
  [R] Strong consultative skills with a track record of successfully solving complex technical problems in customer environments
        ↳ "Strong consultative skills with a track record of successfully solving complex technical problems in customer environments."
  [R] Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack
        ↳ "Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack."
  [P] Hands-on experience with coding, Cloudflare Workers, and Workers AI
        ↳ "Hands-on experience with coding, Cloudflare Workers, and Workers AI."
  [P] Prior experience in customer onsite placement
        ↳ "Prior experience in customer onsite placement."

=== Forward Deployed Engineer, Professional Services  (9 kept, 0 dropped)
    https://boards.greenhouse.io/cloudflare/jobs/8043339?gh_jid=8043339
  [R] In-depth experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure
        ↳ "In Depth Experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure."
  [R] Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure
        ↳ "Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure."
  [R] Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools
        ↳ "Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools."
  [R] Proven ability to work with Cloudflare products within Enterprise-level accounts
        ↳ "Proven ability to work with Cloudflare products within Enterprise-level accounts."
  [R] Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences
        ↳ "Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences."
  [R] Strong consultative skills with a track record of successfully solving complex technical problems in customer environments
        ↳ "Strong consultative skills with a track record of successfully solving complex technical problems in customer environments."
  [R] Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack
        ↳ "Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack."
  [P] Hands-on experience with coding, Cloudflare Workers, and Workers AI
        ↳ "Hands-on experience with coding, Cloudflare Workers, and Workers AI."
  [P] Prior experience in customer onsite placement
        ↳ "Prior experience in customer onsite placement."

10 listings · 146 requirements kept · 0 dropped
















































=== AI Security Research & Red Team Engineer
  unmet   [R GATE] 4+ years in offensive security, application security or other relevant field
  partial [R] Deep knowledge of AI, Coding agents, LLMs, prompt engineering, AI-related attack vectors (e.g., prompt injection, jailbreaking), and Agentic concepts
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  partial [R] Strong background in manual penetration testing, exploit development, or cloud security (AWS/GCP/Bare Metal)
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  unmet   [R] Experience using the MITRE ATT&CK framework to map coverage and identify blind spots in defensive telemetry
  partial [R] Ability to explain complex exploits to non-technical stakeholders while maintaining credibility with engineering teams
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [R] Knowledge of automated breach and attack simulation (BAS) tools, as well as custom-built frameworks for payload delivery and C2 infrastructure

=== Customer Engineering Specialist - Network Services
  unmet   [R GATE] 5+ years in Customer Engineering, Pre-sales, Solutions or Systems Engineering, or Technical Sales
  unmet   [R] Strong working knowledge of BGP (eBGP, route advertisement and filtering, AS paths, communities, anycast, RPKI and route hygiene), static and dynamic routing, subnetting, route-based policy and split tunnels
  unmet   [R] Deep understanding of the TCP/IP protocol stack and packet-level troubleshooting, including MTU/MSS, tunneling (GRE, IPsec), NAT and asymmetric routing
  unmet   [R] Understanding of L3/L4/L7 DDoS attack types and mitigation approaches, and how on-demand and always-on protection differ
  unmet   [R] Familiarity with SD-WAN architectures and routing protocols, underlay and overlay design, local internet breakout, branch connectivity, and migration from MPLS or legacy WAN
  partial [R] Fluent in English, written and spoken
          ↳ "Spoken language: Spanish"
  met     [P] Additional languages beyond English are a plus
          ↳ "Spoken language: Spanish"
  partial [R] Ability to manage a project, work to deadlines and prioritize between competing goals
          ↳ "managed Agile task delegation"
  partial [R] Curiosity and learning agility to keep up with industry trends and Cloudflare's own products
          ↳ "LLMs, AI models, Agile, CI/CD, Cloud Computing"
  unmet   [P] Good knowledge of DNS, including authoritative and recursive resolution, DNSSEC, DNS over HTTPS/TLS, DNS-based attacks and DNS filtering
  partial [P] Detailed understanding of the path from user to application, including hybrid and multi-cloud architectures (Azure, AWS, GCP)
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  unmet   [P] Knowledge of end-user and application security risks including DDoS, malware, phishing, viruses, ransomware
  unmet   [P] Knowledge of VPN and remote access challenges, and moving to Zero Trust access
  unmet   [P] Familiarity with SIEM and log analytics platforms, and network telemetry such as NetFlow and sFlow
  unmet   [P] Experience and knowledge with network and security vendors including Cisco, Juniper, Fortinet, Palo Alto Networks, and Check Point
  unmet   [P] Understanding of the market for CDN providers, WAF, remote access, next-gen firewalls, CASB, DDoS mitigation, SD-WAN and secure gateway solutions
  unmet   [P] Knowledge of SASE concepts and Zero Trust networking architectures
  unmet   [P] Knowledge of Cloudflare Zero Trust solutions: Access, Gateway, Browser Isolation, and WARP client deployment
  unmet   [P] Knowledge of Secure Web Gateway, CASB and DLP
  unmet   [P] Knowledge of IdP and authentication (SAML, OTP), SaaS application integration and tenant controls
  unmet   [P] Client OS fundamentals and software distribution knowledge

=== Customer Engineer, Korea
  unmet   [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
  unmet   [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
  partial [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
          ↳ "coached engineers on debugging, version control, and research methods."
  unmet   [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
  partial [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation"
  partial [R] Technical depth in at least four of the listed technical areas (Internet fundamentals, Security, Performance, AI Proficiency, Coding/Scripting, Developer Platform Fluency)
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  unmet   [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
  unmet   [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
  unmet   [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
  partial [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  met     [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  partial [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments, with familiarity with infrastructure-as-code, CI/CD pipelines, and observability
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  partial [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews"
  unmet   [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
  unmet   [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
  partial [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
          ↳ "Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses; implemented microservice architecture"
  partial [R GATE] Undergraduate or graduate degree in Computer Science, Engineering, or a related field
          ↳ "Full Stack Web Development, Rithm School, Mar 2022–Jun 2022"

=== Customer Engineer, Turkish Speaking
  partial [R] Fluency in English and Turkish (written and spoken)
          ↳ "Spoken language: Spanish"
  unmet   [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
  unmet   [R] Ability to whiteboard, design, and articulate complex enterprise network and security architectures clearly
  partial [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both engineers and C-level executives
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
  unmet   [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
  partial [R] Depth in at least four technical areas listed (Internet fundamentals, Security, Performance, AI Proficiency, Coding/Scripting, Developer Platform Fluency)
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  unmet   [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS, HTTP(S), and SSL/TLS
  unmet   [R] Expertise in security of Internet properties including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
  unmet   [R] Expertise in performance of Internet properties including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
  partial [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  met     [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  partial [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments; familiarity with infrastructure-as-code, CI/CD pipelines, and observability
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  partial [P] Track record of creating and delivering technical enablement such as workshops, code samples, documentation, or developer onboarding that accelerates customer adoption
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
  unmet   [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
  partial [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
          ↳ "Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses; implemented microservice architecture; added real-time WebSocket (Socket.IO) communication; constructed and deployed custom AWS suite for high-availability production."
  partial [R GATE] Undergraduate or graduate degree in Computer Science, Engineering, or a related field
          ↳ "Full Stack Web Development, Rithm School, Mar 2022–Jun 2022"

=== Customer Solutions Engineer
  partial [R GATE] 5-12 years of experience in a customer-facing technical role such as Customer Engineer, Technical Support, Implementation Engineer, Onboarding Engineer, Sales/Systems Engineer, Technical Account Manager, or NOC/SOC analyst or equivalent hands-on technical experience managing customer deployments.
          ↳ "Software Engineer, Freelance, Apr 2024–Present: Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses; implemented microservice architecture; added real-time WebSocket (Socket.IO) communication; constructed and deployed custom AWS suite for high-availability production."
  unmet   [R] Working knowledge of Cloudflare product foundations: Application Security, CDN, Zero Trust/SASE, and Network Services.
  partial [R] Understanding of networking fundamentals: DNS, TLS/SSL, HTTP/HTTPS, CIDR, NAT, and BGP.
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  unmet   [R] Familiarity with web security basics: OWASP, WAF rules, OAuth, SAML, MFA, and Zero Trust principles.
  unmet   [R] Hands-on experience with the Cloudflare Dashboard, and comfort with Terraform, API-based configurations, or identity providers such as Okta, Azure AD, and SAML/OIDC integrations.
  unmet   [R] Ability to read and interpret Security Events, Logs, cURL outputs, and HAR files; awareness of common causes of 5xx/4xx errors post-onboarding.
  partial [R] Ability to read and debug REST API calls; basic proficiency with Python and Bash.
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  partial [R] Strong written and verbal communication skills, able to document clearly, summarize concisely, and interact professionally with both technical and non-technical customer contacts.
          ↳ "upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [P] Familiarity with compliance frameworks such as PCI DSS, HIPAA, SOC 2, or ISO 27001.
  unmet   [P] Existing Cloudflare certifications (e.g., Cloudflare Fundamentals, Cloudflare for Teams, or Cloudflare for Developers).
  unmet   [P] Direct experience onboarding or administering Cloudflare in a production environment.
  partial [P] Familiarity with Infrastructure-as-Code (Terraform, Pulumi) or CI/CD pipelines for configuration management.
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  partial [P] Comfort using AI assistants, LLM-based tools, or scripting to accelerate routine onboarding tasks, log analysis, or documentation.
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  met     [R GATE] Fluency in English is required.
          ↳ "Spoken language: Spanish"

=== Data Center Engineer
  unmet   [R] Experience with Juniper, Cisco and DWDM network equipment
  unmet   [R GATE] Minimum of 4 years experience of Linux systems administration
  partial [R] Experience managing and instructing remote contractors
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery"
  unmet   [R] Familiarity with work required to stand up infrastructure in remote colocation facilities
  partial [R] Experience running and improving operational processes, including automation tooling, in a rapidly changing environment
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  unmet   [R] Familiarity with day-to-day tasks and projects common to Data Center Operations (deployment, migration, decommissioning etc.)
  unmet   [R] Comfortable handling basic program management responsibilities such as JIRA
  unmet   [R] Participate in a shared on-call rotation to maintain 24×7 operational availability of the global network
  partial [P GATE] Bachelor's degree with technical background in engineering, computer science, or MIS
          ↳ "Full Stack Web Development, Rithm School, Mar 2022–Jun 2022"
  unmet   [P] Direct experience executing on complex data center/infrastructure projects
  unmet   [P] Previous experience installing / maintaining data center (and other IT) infrastructure and DCIM tools
  partial [P] Experience running and improving operational processes in a rapidly changing environment
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  partial [P] Strong verbal and written communication skills, problem-solving skills, attention to detail, and interpersonal skills
          ↳ "upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  partial [P GATE] Must be proactive with proven ability to learn fast and execute on multiple tasks simultaneously
          ↳ "Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses"
  unmet   [P] Ability to manage Microsoft Excel and Google Sheets
  unmet   [P] Comfortable handling basic program management responsibilities such as JIRA
  partial [P GATE] Must be a team player
          ↳ "managed Agile task delegation"
  partial [P] Multi-lingual; experience working with infrastructure in multiple countries
          ↳ "Spoken language: Spanish"
  unmet   [P] Comfortable with remote lights-out and out-of-band access to data center resources
  unmet   [P] Linux certifications (RHCSA etc.)
  unmet   [P] Network certifications (CCNA, JNCIA or higher)
  unmet   [P] Experience with configuration management systems such as Saltstack, Chef, Puppet or Ansible
  partial [P] Scripting or software development experience in Bash, Python or Go-lang
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  unmet   [P] Familiarity with load balancing and reverse proxies such as Nginx, Varnish, HAProxy, Apache
  unmet   [P] Experience working within a large scale SaaS vendor

=== Digital Customer Engineer - Swedish or Russian Speaker
  partial [R GATE] Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience
          ↳ "Full Stack Web Development, Rithm School, Mar 2022–Jun 2022"
  partial [R GATE] Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, technical consulting, technical support, or a related field
          ↳ "Practicum Lead / Mentor, Code The Dream, Sep 2023–Present: Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  partial [R] Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  partial [R] Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes
          ↳ "Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses"
  unmet   [R] Understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth
  partial [R] Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  partial [R] Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment
          ↳ "managed Agile task delegation"
  met     [R] Knowledge or experience in at least three of the listed technical breadth areas
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  partial [R] Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts
          ↳ "Converted Node.js services to Flask with RESTful endpoints"
  unmet   [R] Familiarity with Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE
  partial [R] Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  partial [R] Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  met     [R] Experience with at least one coding/scripting language such as Python, JavaScript, Bash, Lua, or Go
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  met     [R] Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  partial [R] Curiosity, initiative, and a demonstrated ability to learn new technologies quickly
          ↳ "Open Source Contributor — Open Disclosure (Ruby, JavaScript, Jekyll): optimized campaign-contribution calculation algorithm; used Slack and code reviews to align on technical strategy."
  partial [R GATE] Native-like fluency in English AND either Swedish or Russian (written and spoken)
          ↳ "Spoken language: Spanish"
  partial [P] Experience creating reusable technical assets such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops
          ↳ "upheld coding standards via code reviews"
  met     [P] Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  met     [P] Exposure to modern application architectures including serverless computing, containers, microservices, and APIs
          ↳ "implemented microservice architecture; added real-time WebSocket (Socket.IO) communication; constructed and deployed custom AWS suite for high-availability production."
  unmet   [P] Knowledge of common application-security risks and mitigation strategies
  unmet   [P] Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls
  partial [P] Experience working with SMB or Digital Native Business customers
          ↳ "Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses"

=== Digital Presales Customer Engineer
  unmet   [R GATE] Mandarin is required to deal with customers in the Greater China region
  unmet   [P] Cantonese is a plus
  unmet   [R] Experience in a customer-facing technical role such as Solutions Engineering, Customer Engineering, Professional Services, Sales Engineering, Technical Account Management, or as a Forward Deployed Engineer
  unmet   [R] Ability to white-board, design, and articulate complex enterprise network and security architectures clearly
  partial [R] Excellent communication skills with the ability to translate deeply technical concepts into business outcomes for both hands-on engineers and C-level executives
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [R] Proven track record of operating in a quota-carrying or revenue-aligned environment, with a strong understanding of SaaS metrics, business value translation, and enterprise sales cycles
  unmet   [R] Exceptional presentation and stakeholder management skills, capable of bridging the gap between deep technical implementation details and high-level C-suite business strategy
  partial [R] Depth in at least four of the listed technical areas
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  unmet   [R] Deep understanding of Internet fundamentals including OSI Model layers 1–7, BGP, GRE, TCP/UDP, DNS (authoritative and recursive), HTTP(S), and SSL/TLS
  unmet   [R] Expertise in security of Internet properties, including WAF, Bot Management, Firewalls, Rate Limiting, (M)TLS, Zero Trust, and SASE concepts
  unmet   [R] Expertise in performance of Internet properties, including speed, latency, caching, video streaming, HTTP/2, and TLS 1.3
  partial [R] Familiarity with prompt engineering, AI-assisted scripting and log analysis, LLM utilization, and workflow automation
          ↳ "Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing"
  partial [R] Proficiency in Python, JavaScript, Bash, Lua, Go, or similar languages to write custom integration scripts, API connectors, and edge computing functions
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  partial [R] Experience designing, building, deploying or scaling applications using RESTful/GraphQL APIs, SDKs, webhooks, and developer tooling in cloud-native environments; familiarity with infrastructure-as-code (Terraform, Pulumi), CI/CD pipelines, and observability for developer-led deployments
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  partial [P] Track record of creating and delivering technical enablement — workshops, code samples, documentation, or developer onboarding — that accelerates customer adoption of complex platforms
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [P] Experience with LLM orchestration, Retrieval-Augmented Generation (RAG) architectures, and model-access controls
  unmet   [P] Understanding of regulatory requirements such as PCI DSS, HIPAA, and SOC 2
  partial [P] Background from hyperscalers, digital natives, distributed systems environments, or startups
          ↳ "Software Engineer, Freelance, Apr 2024–Present: Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses; implemented microservice architecture; added real-time WebSocket (Socket.IO) communication; constructed and deployed custom AWS suite for high-availability production."
  partial [R GATE] Undergraduate or graduate degree in Computer Science, Engineering, or a related field
          ↳ "Full Stack Web Development, Rithm School, Mar 2022–Jun 2022"
  unmet   [R] Willingness to travel up to 20–50% for customer meetings, conferences, industry events, and in-person team collaboration

=== Forward Deployed Engineer (FDE)
  unmet   [R GATE] 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security
  unmet   [R] Extensive and proven knowledge of Application Security, Workers and Workers AI, cybersecurity, web performance, and cloud infrastructure
  unmet   [R] Extensive experience implementing and supporting complex technical solutions using Terraform for infrastructure management
  partial [R] Demonstrated ability to build trust and rapport in challenging environments, remaining flexible and persistent in establishing regular cadences with stakeholders
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  partial [R] Exceptional ability to navigate Slack-first communication cultures, providing clear guidance and managing technical threads under pressure
          ↳ "used Slack and code reviews to align on technical strategy."
  partial [R] Strong technical understanding of and passion for AI/LLM concepts
          ↳ "LLMs, AI models, Agile, CI/CD, Cloud Computing"
  unmet   [R] Strong knowledge of networking protocols, cybersecurity, and industry standards such as Zero Trust/SASE
  unmet   [P] Experience or strong interest in transitioning application-heavy environments toward comprehensive Network Security and SASE models
  partial [P] Proficiency in coding languages beyond Terraform to automate tasks at scale and build proof-of-concept setups
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  unmet   [P] Experience managing or advising on project-based fund pools to maximize the value of a customer's strategic investment

=== Forward Deployed Engineer, Professional Services
  unmet   [R] In-depth experience in a technical customer-facing role such as Solutions Architect or Technical Account Manager, ideally within cloud networking, security, or web infrastructure
  partial [R] Extensive knowledge of Cloudflare's Application and Security portfolio (DNS, WAF, DDoS, Bot Management, CDN) and cloud infrastructure
          ↳ "AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC"
  unmet   [R] Hands-on experience protecting and securing web applications, APIs, and web services using WAF, DDoS, DNS, and Bot Management tools
  unmet   [R] Proven ability to work with Cloudflare products within Enterprise-level accounts
  partial [R] Exceptional written and verbal communication skills, with the ability to present complex topics effectively to both technical and non-technical audiences
          ↳ "Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods."
  unmet   [R] Strong consultative skills with a track record of successfully solving complex technical problems in customer environments
  partial [R] Ability to translate customer requirements into practical, scalable solutions that align with Cloudflare's technology stack
          ↳ "constructed and deployed custom AWS suite for high-availability production."
  partial [P] Hands-on experience with coding, Cloudflare Workers, and Workers AI
          ↳ "Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS"
  unmet   [P] Prior experience in customer onsite placement

10 listings · 0 met→partial downgrades
























RANKED         met/part/unmet
   52.6   5/13/ 4  Digital Customer Engineer - Swedish or Russian Speaker
   30.4   1/ 6/ 7  Customer Solutions Engineer
   30.0   1/ 8/ 8  Customer Engineer, Korea
   28.1   1/ 8/ 9  Customer Engineer, Turkish Speaking
   21.9   0/ 4/ 5  Forward Deployed Engineer, Professional Services

BLOCKED
   25.0   0/ 3/ 3  AI Security Research & Red Team Engineer
         ⛔ 4+ years in offensive security, application security or other relevant field
   20.6   0/ 4/ 6  Forward Deployed Engineer (FDE)
         ⛔ 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security
   20.0   0/ 8/12  Digital Presales Customer Engineer
         ⛔ Mandarin is required to deal with customers in the Greater China region
   16.7   0/ 9/16  Data Center Engineer
         ⛔ Minimum of 4 years experience of Linux systems administration
   15.5   1/ 4/16  Customer Engineering Specialist - Network Services
         ⛔ 5+ years in Customer Engineering, Pre-sales, Solutions or Systems Engineering, or Technical Sales

======================================================================
Digital Customer Engineer - Swedish or Russian Speaker — Cloudflare  [52.6]
https://boards.greenhouse.io/cloudflare/jobs/8232806?gh_jid=8232806

  partial REQ  gate Undergraduate or graduate degree in Computer Science, Engineering, or a related field, or equivalent practical experience
          ↳ Full Stack Web Development, Rithm School, Mar 2022–Jun 2022
  partial REQ  gate Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, technical consulting, technical support, or a related field
          ↳ Practicum Lead / Mentor, Code The Dream, Sep 2023–Present: Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods.
  partial REQ       Ability to understand, whiteboard, and clearly explain network, security, application, or developer-platform architectures
          ↳ constructed and deployed custom AWS suite for high-availability production.
  partial REQ       Ability to understand customer needs, ask effective discovery questions, and translate technical capabilities into relevant customer and business outcomes
          ↳ Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses
  unmet   REQ       Understanding of customer buying decisions, enterprise or technology sales cycles, and how technical value supports adoption, retention, and growth
  partial REQ       Strong presentation and stakeholder-management skills, with the ability to explain technical concepts clearly to both hands-on practitioners and business decision-makers
          ↳ Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods.
  partial REQ       Ability to prioritize work, manage multiple concurrent customer engagements, and collaborate effectively within a pooled team environment
          ↳ managed Agile task delegation
  met     REQ       Knowledge or experience in at least three of the listed technical breadth areas
          ↳ AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC
  partial REQ       Understanding of how the Internet works, including TCP/IP, DNS, HTTP(S), SSL/TLS, APIs, and core networking concepts
          ↳ Converted Node.js services to Flask with RESTful endpoints
  unmet   REQ       Familiarity with Web Application Firewalls, Bot Management, firewalls, rate limiting, Zero Trust, and SASE
  partial REQ       Understanding of website and application performance concepts, including latency, caching, content delivery, and modern web protocols
          ↳ AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC
  partial REQ       Familiarity with prompt engineering, AI-assisted research, scripting or log analysis, LLM usage, and workflow automation
          ↳ Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing
  met     REQ       Experience with at least one coding/scripting language such as Python, JavaScript, Bash, Lua, or Go
          ↳ Languages: TypeScript, JavaScript (ES6), Python, Ruby, SQL, HTML, CSS
  met     REQ       Familiarity with APIs, SDKs, webhooks, cloud-native applications, infrastructure as code, CI/CD, or observability
          ↳ Tools & Strategies: Git, GitHub, Slack, Asana, LLMs, AI models, Agile, CI/CD, Cloud Computing
  partial REQ       Curiosity, initiative, and a demonstrated ability to learn new technologies quickly
          ↳ Open Source Contributor — Open Disclosure (Ruby, JavaScript, Jekyll): optimized campaign-contribution calculation algorithm; used Slack and code reviews to align on technical strategy.
  partial REQ  gate Native-like fluency in English AND either Swedish or Russian (written and spoken)
          ↳ Spoken language: Spanish
  partial pref      Experience creating reusable technical assets such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops
          ↳ upheld coding standards via code reviews
  met     pref      Familiarity with cloud providers such as AWS, Microsoft Azure, or Google Cloud
          ↳ AWS: EC2, S3, CloudFront, CodeBuild, CloudWatch, CloudTrail, Route 53, IAM, Amazon RDS, VPC
  met     pref      Exposure to modern application architectures including serverless computing, containers, microservices, and APIs
          ↳ implemented microservice architecture; added real-time WebSocket (Socket.IO) communication; constructed and deployed custom AWS suite for high-availability production.
  unmet   pref      Knowledge of common application-security risks and mitigation strategies
  unmet   pref      Familiarity with LLM orchestration, Retrieval-Augmented Generation architectures, or model-access controls
  partial pref      Experience working with SMB or Digital Native Business customers
          ↳ Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses
(venv) jf@Joanness-MacBook-Pro lumbergh % 












































1588 fetched · 37 considered · 54 model calls · 41.3s

 1.  78.6  Discord — Software Engineer, Notifications  (5/1/2)
 2.  73.3  Figma — Software Engineer - C++  (6/3/2)
 3.  71.4  Figma — Software Engineer - AI Product (London, United Kingdom)  (4/3/2)
 4.  61.1  Discord — Software Engineer, Consumer Revenue  (2/7/0)
 5.  53.1  Duolingo — Platform Engineer II  (3/4/3)
 6.  52.9  Figma — Forward Deployed Engineer  (1/8/1)
 7.  52.6  Cloudflare — Digital Customer Engineer - Swedish or Russian Speaker  (5/13/4)
 8.  44.4  Databricks — Applied AI Engineer  (1/2/3)
 9.  35.3  Databricks — AI Forward Deployed Engineer - London  (1/4/4)
10.  30.4  Cloudflare — Customer Solutions Engineer  (1/6/7)
11.  30.0  Cloudflare — Customer Engineer, Korea  (1/8/8)
12.  28.1  Cloudflare — Customer Engineer, Turkish Speaking  (1/8/9)
13.  26.8  Databricks — AI Automation Engineer  (2/4/10)
14.  21.9  Cloudflare — Forward Deployed Engineer, Professional Services  (0/4/5)

blocked:
     50.0  Figma — Software Engineer - AI Platforms  ⛔ 3+ years of experience in one or more of: AI, search infrastructure, or developer platforms
     50.0  Databricks — Forward Deployed Engineer  ⛔ Ability and interest to travel up to 50% as needed to client sites
     46.4  Figma — Security Engineer  ⛔ Role must be held in the United States (US hubs or remote)
     43.3  Figma — Software Engineer - Data Infrastructure  ⛔ 5+ years of backend or infrastructure engineering experience, including designing and building distributed data infrastructure at scale
     40.0  Duolingo — AI Research Engineer, New PhD Graduate   ⛔ PhD in computer science or related technical field (or expect to by August 2027); Ability to relocate to Pittsburgh, PA or New York, NY
     36.4  Figma — Data Platform Engineer  ⛔ 5+ years of experience building and operating production data platforms, developer infrastructure, or distributed systems
     33.3  Databricks — Customer Enablement Architect (Capability Engineering & AI Adoption)  ⛔ 5+ years of experience in Customer Enablement, Talent Transformation, Training, Customer Success, Consulting, or managing a book of business
     29.4  Figma — Software Engineer - Application Platform  ⛔ 3+ years building production systems with Ruby; Role can be held from a US hub or remotely in the United States
     29.4  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE)  ⛔ Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
     29.4  Databricks — AI Forward Deployed Engineer - Sweden  ⛔ Extensive years of hands-on industry data science experience, leveraging common machine learning and data science tools (pandas, scikit-learn, PyTorch, etc.); Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
     26.3  Databricks — AI Forward Deployed Engineer - Netherlands  ⛔ Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience; Candidates must be based in the Netherlands region only (no remote working available from any other country)
     25.0  Cloudflare — AI Security Research & Red Team Engineer  ⛔ 4+ years in offensive security, application security or other relevant field
     24.0  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE), U.S. Public Sector (Federal Focus)  ⛔ U.S. citizenship required due to federal contract requirements and client site access obligations; Eligibility for a U.S. government secret clearance required; Position is based in the Washington, D.C., Maryland, or Virginia metropolitan area; Candidates with an active Secret or higher clearance are strongly encouraged to apply
     21.9  Figma — Software Engineer - AI Product  ⛔ 1 or more years of experience developing generative AI products; A relevant advanced degree (Masters or PhD) in Machine Learning, Artificial Intelligence, Statistics, or a related field
     21.1  Databricks — AI Engineer - FDE (Forward Deployed Engineer)  ⛔ 7+ years of experience building GenAI applications, including RAG, multi-agent systems, Text2SQL, fine-tuning, etc., with tools such as HuggingFace, LangChain, and DSPy; Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience; Native-level fluency in Korean and professional working proficiency in English (both written and verbal)















     1588 fetched · 37 considered · 5 model calls · 16.9s

 1.  78.6  Discord — Software Engineer, Notifications  (5/1/2)
 2.  73.3  Figma — Software Engineer - C++  (6/3/2)
 3.  71.4  Figma — Software Engineer - AI Product (London, United Kingdom)  (4/3/2)
 4.  61.1  Discord — Software Engineer, Consumer Revenue  (2/7/0)
 5.  53.1  Duolingo — Platform Engineer II  (3/4/3)
 6.  52.9  Figma — Forward Deployed Engineer  (1/8/1)
 7.  52.6  Cloudflare — Digital Customer Engineer - Swedish or Russian Speaker  (5/13/4)
 8.  44.4  Databricks — Applied AI Engineer  (1/2/3)
 9.  35.3  Databricks — AI Forward Deployed Engineer - London  (1/4/4)
10.  30.8  Databricks — Forward Deployed Engineer  (0/8/5)
11.  30.4  Cloudflare — Customer Solutions Engineer  (1/6/7)
12.  30.0  Cloudflare — Customer Engineer, Korea  (1/8/8)
13.  28.1  Cloudflare — Customer Engineer, Turkish Speaking  (1/8/9)
14.  26.8  Databricks — AI Automation Engineer  (2/4/10)
15.  15.6  Cloudflare — Forward Deployed Engineer, Professional Services  (0/3/6)

blocked:
     50.0  Figma — Software Engineer - AI Platforms  ⛔ 3+ years of experience in one or more of: AI, search infrastructure, or developer platforms
     46.4  Figma — Security Engineer  ⛔ Role must be held in the United States (US hubs or remote)
     40.0  Duolingo — AI Research Engineer, New PhD Graduate   ⛔ PhD in computer science or related technical field (or expect to by August 2027); Ability to relocate to Pittsburgh, PA or New York, NY
     36.4  Figma — Data Platform Engineer  ⛔ 5+ years of experience building and operating production data platforms, developer infrastructure, or distributed systems
     33.3  Databricks — Customer Enablement Architect (Capability Engineering & AI Adoption)  ⛔ 5+ years of experience in Customer Enablement, Talent Transformation, Training, Customer Success, Consulting, or managing a book of business
     29.4  Figma — Compliance Engineer  ⛔ 5+ years of hands-on experience in security compliance, security assurance, IT audit, or compliance engineering
     29.4  Figma — Software Engineer - Application Platform  ⛔ 3+ years building production systems with Ruby; Role can be held from a US hub or remotely in the United States
     29.4  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE)  ⛔ Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
     29.4  Databricks — AI Forward Deployed Engineer - Sweden  ⛔ Extensive years of hands-on industry data science experience, leveraging common machine learning and data science tools (pandas, scikit-learn, PyTorch, etc.); Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
     26.3  Databricks — AI Forward Deployed Engineer - Netherlands  ⛔ Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience; Candidates must be based in the Netherlands region only (no remote working available from any other country)
     25.0  Cloudflare — AI Security Research & Red Team Engineer  ⛔ 4+ years in offensive security, application security or other relevant field
     24.0  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE), U.S. Public Sector (Federal Focus)  ⛔ U.S. citizenship required due to federal contract requirements and client site access obligations; Eligibility for a U.S. government secret clearance required; Position is based in the Washington, D.C., Maryland, or Virginia metropolitan area; Candidates with an active Secret or higher clearance are strongly encouraged to apply
     21.9  Figma — Software Engineer - AI Product  ⛔ 1 or more years of experience developing generative AI products; A relevant advanced degree (Masters or PhD) in Machine Learning, Artificial Intelligence, Statistics, or a related field
     21.1  Databricks — AI Engineer - FDE (Forward Deployed Engineer)  ⛔ 7+ years of experience building GenAI applications, including RAG, multi-agent systems, Text2SQL, fine-tuning, etc., with tools such as HuggingFace, LangChain, and DSPy; Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience; Native-level fluency in Korean and professional working proficiency in English (both written and verbal)
     20.6  Cloudflare — Forward Deployed Engineer (FDE)  ⛔ 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security
     \
    










      blocked
         50.0  Figma — Software Engineer - AI Platforms  ⛔ 3+ years of experience in one or more of: AI, search infrastructure, or developer platforms
     46.4  Figma — Security Engineer  ⛔ Role must be held in the United States (US hubs or remote)
     40.0  Duolingo — AI Research Engineer, New PhD Graduate   ⛔ PhD in computer science or related technical field (or expect to by August 2027); Ability to relocate to Pittsburgh, PA or New York, NY
     36.4  Figma — Data Platform Engineer  ⛔ 5+ years of experience building and operating production data platforms, developer infrastructure, or distributed systems
     33.3  Databricks — Customer Enablement Architect (Capability Engineering & AI Adoption)  ⛔ 5+ years of experience in Customer Enablement, Talent Transformation, Training, Customer Success, Consulting, or managing a book of business
     29.4  Figma — Compliance Engineer  ⛔ 5+ years of hands-on experience in security compliance, security assurance, IT audit, or compliance engineering
     29.4  Figma — Software Engineer - Application Platform  ⛔ 3+ years building production systems with Ruby; Role can be held from a US hub or remotely in the United States
     29.4  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE)  ⛔ Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
     29.4  Databricks — AI Forward Deployed Engineer - Sweden  ⛔ Extensive years of hands-on industry data science experience, leveraging common machine learning and data science tools (pandas, scikit-learn, PyTorch, etc.); Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
     26.3  Databricks — AI Forward Deployed Engineer - Netherlands  ⛔ Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience; Candidates must be based in the Netherlands region only (no remote working available from any other country)
     25.0  Cloudflare — AI Security Research & Red Team Engineer  ⛔ 4+ years in offensive security, application security or other relevant field
     24.0  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE), U.S. Public Sector (Federal Focus)  ⛔ U.S. citizenship required due to federal contract requirements and client site access obligations; Eligibility for a U.S. government secret clearance required; Position is based in the Washington, D.C., Maryland, or Virginia metropolitan area; Candidates with an active Secret or higher clearance are strongly encouraged to apply
     21.9  Figma — Software Engineer - AI Product  ⛔ 1 or more years of experience developing generative AI products; A relevant advanced degree (Masters or PhD) in Machine Learning, Artificial Intelligence, Statistics, or a related field
     21.1  Databricks — AI Engineer - FDE (Forward Deployed Engineer)  ⛔ 7+ years of experience building GenAI applications, including RAG, multi-agent systems, Text2SQL, fine-tuning, etc., with tools such as HuggingFace, LangChain, and DSPy; Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience; Native-level fluency in Korean and professional working proficiency in English (both written and verbal)
     20.6  Cloudflare — Forward Deployed Engineer (FDE)  ⛔ 10+ years of technical customer facing experience as a technical architect or lead on complex, enterprise-level projects within cloud networks, web infrastructure, or security











     > find backend roles, remote, mid-level
  → discover_boards({"role": "backend engineer", "limit": 5})
  ← boards for 'backend engineer': cloudflare, figma, discord, duolingo, databricks  (seed list; live di  (1 lines)
  → rank_jobs({"boards": ["cloudflare", "figma", "discord", "duolingo", "databricks"], "title_any": ["backend", "software", "developer", "engineer"], "title_none": ["senior", "staff", "lead", "manager", "intern", "principal", "director"], "per_board": 10})
  ← 1587 fetched · 37 considered · 0 model calls · 1.3s  (26 lines)
  → filter_results({"location": "remote"})
  ← 1 of 14 after filtering  (2 lines)
  → filter_results({"location": "United States"})
  ← 0 of 14 after filtering  (2 lines)
  → filter_results({})
  ← 0 of 14 after filtering  (2 lines)
  → filter_results({"min_score": 30})
  ← 0 of 14 after filtering  (2 lines)
  → filter_results({})
  ← 0 of 14 after filtering  (2 lines)

The filter state seems stuck — let me note what I can confirm from the full ranked results. Here's the complete picture based on the raw pipeline output, with remote/flexible locations called out:

Top results with remote or flexible locations:

1. Score 78.6 — Discord, Software Engineer Notifications. Location: San Francisco Bay Area (office-based).
2. Score 73.3 — Figma, Software Engineer C++. Location: San Francisco / New York / United States — the "United States" tag suggests remote is an option.
3. Score 71.4 — Figma, Software Engineer AI Product. Location: London, England (not remote).
4. Score 61.1 — Discord, Software Engineer Consumer Revenue. Location: San Francisco Bay Area (office-based).
5. Score 53.1 — Duolingo, Platform Engineer II. Location: New York, NY (office-based).
6. Score 52.9 — Figma, Forward Deployed Engineer. Location: San Francisco / New York / United States — likely remote-eligible in the US.
7. Score 30.8 — Databricks, Forward Deployed Engineer. Location: Remote — India only.

Best bets for remote (US):

The two Figma roles (ranks 2 and 6) both list "United States" as a location option alongside their offices, making them the strongest remote-eligible matches. Figma Software Engineer C++ scores highest at 73.3, followed by Figma Forward Deployed Engineer at 52.9.

Want me to dig into why either of those matched your resume? Just say "explain rank 2" or "explain rank 6" and I'll break it down requirement by requirement.


  [8 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 5} · 23073 tokens]


















Save this transcript; it’s the demo for the README.
  > find backend roles, remote, mid-level
  → discover_boards({"role": "backend engineer", "limit": 5})
  ← boards for 'backend engineer': cloudflare, figma, discord, duolingo, databricks  (seed list; live di  (1 lines)
  → rank_jobs({"boards": ["cloudflare", "figma", "discord", "duolingo", "databricks"], "title_any": ["backend", "software engineer", "developer"]})
  ← 1587 fetched · 33 considered · 34 model calls · 25.1s  (31 lines)
  → filter_results({"location": "United States"})
  ← 3 of 19 after filtering  (4 lines)

Here are your results. Only 3 listings explicitly mention "United States" in the location (meaning remote/US-flexible). Figma dominates this slice.

1. 73.3 — Figma, Software Engineer - C++ — San Francisco / New York / United States
2. 63.9 — Figma, Software Engineer - Full Stack — San Francisco / New York / United States
3. 50.0 — Figma, Software Engineer - Distributed Systems — San Francisco / New York / United States

A few notes:

The full unfiltered list has 19 ranked results, most tied to specific cities (SF Bay Area, Mountain View, Hybrid, etc.). If you're open to hybrid or on-site roles, I can drop the location filter and show all 19.

Also worth calling out from the blocked list: Figma's Software Engineer - Application Platform explicitly says "US hub or remotely in the United States" but got blocked on a Ruby requirement — let me know if that's not a dealbreaker and I can look closer at it.

Want me to explain why any specific listing matched or didn't, or widen the location filter?


  [4 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 1} · 10188 tokens]








This transcript is the README demo. Save it as-is.
  > show all 19
  → filter_results({})
  ← 19 of 19 after filtering  (20 lines)

Here are all 19, ranked by fit:

1. 82.1 — Figma, Software Engineer - Figma Weave — Tel Aviv, Israel
2. 78.6 — Discord, Software Engineer, Notifications — San Francisco Bay Area
3. 73.3 — Figma, Software Engineer - C++ — San Francisco / New York / United States
4. 71.4 — Figma, Software Engineer - AI Product — London, England
5. 71.4 — Databricks, Software Engineer - Backend — Aarhus, Denmark
6. 63.9 — Figma, Software Engineer - Full Stack — San Francisco / New York / United States
7. 61.1 — Discord, Software Engineer, Consumer Revenue — San Francisco Bay Area
8. 59.1 — Databricks, Software Engineer, Web Products — Mountain View, California
9. 59.1 — Databricks, Software Engineer, Web Products — Mountain View, California
10. 57.1 — Cloudflare, Software Engineer, Deploy at Scale — Hybrid
11. 53.6 — Cloudflare, Software Engineer, FL — Hybrid
12. 50.0 — Figma, Software Engineer - Distributed Systems — San Francisco / New York / United States
13. 47.1 — Databricks, Software Engineer, Infrastructure — Bengaluru, India
14. 46.7 — Cloudflare, Software Engineer, CDN Configuration Group — Hybrid
15. 42.3 — Cloudflare, Software Engineer - Egress (Go/Rust) — Hybrid
16. 41.7 — Cloudflare, Software Engineer, Agentic Discovery — In-Office
17. 36.4 — Cloudflare, Software Engineer, AI Agents — In-Office
18. 27.5 — Cloudflare, Software Engineer, Cloudflare Network Interconnect — Hybrid
19. 27.3 — Cloudflare, Software Engineer, AI Agents — In-Office

Quick orientation: ranks 3, 6, and 12 are the US-remote-friendly Figma roles. Ranks 10, 11, 14, 15 are Cloudflare Hybrid (location not specified, likely US). The bottom half of the Cloudflare roles score low, mostly due to mismatches. Roles in Tel Aviv, London, Denmark, and Bengaluru would require relocation.

Want a breakdown on any specific listing, or filter further (e.g. score above a threshold, drop certain locations)?


  [6 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 2} · 18558 tokens]

> explain #1
  → explain_match({"rank": 1})
  ← Software Engineer - Figma Weave (Tel Aviv, Israel)  — Figma  [82.1]  (20 lines)

Here's the breakdown for Figma — Software Engineer, Figma Weave (82.1):
https://boards.greenhouse.io/figma/jobs/6073106004

Requirements (must-haves):

- 5+ years experience — PARTIAL. Your freelance work and shipped app were counted, but the total years are borderline for this threshold.
- Shipping and maintaining complex production systems — MET. Your full-stack app with microservices, WebSockets, and AWS deployment covers this well.
- Full-stack with React/TypeScript — MET. Direct match from your app.
- Back-end technologies (Ruby, Go, Node.js, PostgreSQL) — MET. Your Node-to-Flask conversion, SQLAlchemy, and RESTful work cover this.
- Collaboration and communication — MET. Your mentoring, code reviews, and Agile work are strong evidence here.

Preferences (nice-to-haves):

- Rust, WebAssembly, or graphics rendering — UNMET. Nothing in your résumé touches this.
- Extensibility platforms or open source — PARTIAL. Your Open Disclosure open source contribution helps, but it's not a deep plugin/API platform background.
- Passion for developer/user experience and clean architecture — MET.
- Mentoring and knowledge sharing — MET. Strong evidence across multiple roles.

The main risk is the years-of-experience gate and the Rust/WebAssembly gap. The role is also Tel Aviv-based, so relocation would be required. Want me to dig into another listing?


  [8 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 2, 'explain_match': 1} · 29343 tokens]

> why is #1 above #2?
  → explain_match({"rank": 2})
  ← Software Engineer, Notifications — Discord  [78.6]  (17 lines)

Here's the comparison based purely on what the evidence tables show:

Figma Weave (82.1) has 5 met requirements and 2 met preferences, with 1 partial requirement and 1 partial preference. The unmet preference (Rust/WebAssembly) is just a nice-to-have.

Discord Notifications (78.6) has 5 met requirements too, but has 1 partial requirement (customer-focused/measurable goals — only weak evidence) and 2 unmet preferences, including one fairly specific one: prior notifications or growth team experience. That gap is more pointed than a missing nice-to-have skill.

In short, Figma Weave scores higher because your résumé satisfies more of its preferences, while Discord Notifications has two unmet preferences and a partially met requirement with thin evidence. The gap is small — 3.5 points — and Discord has the advantage of being US-based if remote is a priority for you.


  [10 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 2, 'explain_match': 2} · 42024 tokens]

> drop anything in New York
  → filter_results({"exclude_keywords": ["New York"]})
  ← 16 of 19 after filtering  (17 lines)

Done. 3 listings dropped (the Figma C++, Full Stack, and Distributed Systems roles that listed New York). 16 remain. Anything else you'd like to filter or dig into?


  [12 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 3, 'explain_match': 2} · 56165 tokens]

> explain #1

That's still the same Figma Weave listing — I already pulled its full breakdown. Here's a quick recap:

5 met requirements: production systems, React/TypeScript, back-end tech, collaboration, and shipping track record. The experience gate was partial (years are borderline). One unmet preference (Rust/WebAssembly) and one partial preference (open source/extensibility). Strong on mentoring and architecture preferences.

Full detail is a few messages up. Want me to explain any of the other listings instead?


  [13 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 3, 'explain_match': 2} · 63668 tokens]









blocked:
     52.9  Figma — Forward Deployed Engineer  ⛔ 5+ years shipping production software end-to-end, with meaningful time embedded with customers or partner teams
     52.6  Cloudflare — Digital Customer Engineer - Swedish or Russian Speaker  ⛔ Up to 1–5 years of professional experience in a customer-facing technical role such as Sales Engineering, technical consulting, technical support, or a related field
     50.0  Figma — Software Engineer - AI Platforms  ⛔ 5+ years of Software Engineering experience, especially in backend or infrastructure engineering; 3+ years of experience in one or more of: AI, search infrastructure, or developer platforms
     46.4  Figma — Security Engineer  ⛔ Role must be held in the United States (US hubs or remote)
     44.4  Databricks — Applied AI Engineer  ⛔ 2-8 years of engineering experience in high-velocity, high-growth companies
     40.0  Duolingo — AI Research Engineer, New PhD Graduate   ⛔ PhD in computer science or related technical field (or expect to by August 2027); Ability to relocate to Pittsburgh, PA or New York, NY
     36.4  Figma — Data Platform Engineer  ⛔ 5+ years of experience building and operating production data platforms, developer infrastructure, or distributed systems
     33.3  Databricks — Customer Enablement Architect (Capability Engineering & AI Adoption)  ⛔ 5+ years of experience in Customer Enablement, Talent Transformation, Training, Customer Success, Consulting, or managing a book of business
     30.8  Databricks — Forward Deployed Engineer  ⛔ 6+ years of experience in data engineering, data platforms & analytics, or software engineering
     29.4  Figma — Compliance Engineer  ⛔ 5+ years of hands-on experience in security compliance, security assurance, IT audit, or compliance engineering
     29.4  Figma — Software Engineer - Application Platform  ⛔ 5+ years of professional software engineering experience; 3+ years building production systems with Ruby; Role can be held from a US hub or remotely in the United States
     29.4  Databricks — AI Forward Deployed Engineer - Sweden  ⛔ Extensive years of hands-on industry data science experience, leveraging common machine learning and data science tools (pandas, scikit-learn, PyTorch, etc.)
     26.3  Databricks — AI Forward Deployed Engineer - Netherlands  ⛔ Candidates must be based in the Netherlands region only (no remote working available from any other country)
     25.0  Cloudflare — AI Security Research & Red Team Engineer  ⛔ 4+ years in offensive security, application security or other relevant field
     24.0  Databricks — AI Engineer – Forward Deployed Engineering (AI FDE), U.S. Public Sector (Federal Focus)  ⛔ U.S. citizenship required due to federal contract requirements and client site access obligations; Eligibility for a U.S. government secret clearance required; Position is based in the Washington, D.C., Maryland, or Virginia metropolitan area










     ## software engineer
  beaconsoftware       https://job-boards.greenhouse.io/beaconsoftware/jobs/4974798008
  beaconsoftware       https://job-boards.greenhouse.io/beaconsoftware/jobs/4974799008
  optiverus            https://job-boards.greenhouse.io/optiverus/jobs/8565971002
  spacex               https://boards.greenhouse.io/spacex/jobs/8322723002?gh_jid=8322723002%3Fref%3Demploybl
  mongodb              https://job-boards.greenhouse.io/mongodb/jobs/7993984
  beaconsoftware       https://job-boards.greenhouse.io/beaconsoftware/jobs/4675777008
  optiverus            https://job-boards.greenhouse.io/optiverus/jobs/8561859002
  snyk                 https://job-boards.greenhouse.io/snyk/jobs/7867048002
  cannondesign         https://job-boards.greenhouse.io/cannondesign/jobs/8643124002
  elly                 https://job-boards.greenhouse.io/elly/jobs/4411926009
  amtechsoftware       https://job-boards.greenhouse.io/amtechsoftware/jobs/4339920009
  shiftleft            https://job-boards.greenhouse.io/shiftleft/jobs/7123365002
  avepoint             https://job-boards.greenhouse.io/avepoint/jobs/7738463
  roblox               https://job-boards.greenhouse.io/roblox/jobs/8262223
  roblox               https://job-boards.greenhouse.io/roblox/jobs/8115917
  livecareer           https://boards.greenhouse.io/livecareer/jobs/6863943
  spacex               https://boards.greenhouse.io/spacex/jobs/8398447002?gh_jid=8398447002%3Fref%3Demploybl
  spacex               https://boards.greenhouse.io/spacex/jobs/8398552002?gh_jid=8398552002%3Fref%3Demploybl
  spacex               https://job-boards.greenhouse.io/spacex/jobs/8208238002
  efihr                https://job-boards.greenhouse.io/efihr/jobs/4843600101

## software engineer jobs
  robinhood            http://job-boards.greenhouse.io/robinhood/jobs/7263592?t=gh_src%3D
  fanduel              https://job-boards.greenhouse.io/fanduel/jobs/7981990
  roku                 https://job-boards.greenhouse.io/roku/jobs/7906005
  optiverus            https://job-boards.greenhouse.io/optiverus/jobs/8561859002
  spire                https://job-boards.greenhouse.io/spire/jobs/8203849
  roku                 https://job-boards.greenhouse.io/roku/jobs/7032137
  pinterest            https://job-boards.greenhouse.io/pinterest/jobs/7838591
  thenewyorktimes      http://job-boards.greenhouse.io/thenewyorktimes?departments%5B%5D=4030236005
  spacex               http://job-boards.greenhouse.io/spacex/jobs/8532395002
  roblox               https://job-boards.greenhouse.io/roblox/jobs/8072244
  warp                 http://job-boards.greenhouse.io/warp/jobs/4324888004
  samsara              https://job-boards.greenhouse.io/samsara/jobs/8042387
  roblox               https://job-boards.greenhouse.io/roblox/jobs/7978492
  pinterest            https://job-boards.greenhouse.io/pinterest?error=true
  intrinsicrobotics    https://boards.greenhouse.io/intrinsicrobotics/jobs/5989807004
  neuralink            https://job-boards.greenhouse.io/neuralink/jobs/4723041003
  waymo                https://job-boards.greenhouse.io/waymo?error=true
  cloudflare           https://job-boards.greenhouse.io/cloudflare/jobs/8278702?gh_jid=8278702
  coreweave            https://job-boards.greenhouse.io/coreweave
  figma                https://job-boards.greenhouse.io/figma/jobs/6115082004

## junior software engineer
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/5761145003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/7541127003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/7541127003?utm_data=hiring.lat
  sezzle               https://job-boards.greenhouse.io/sezzle/jobs/6110231003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/7598109003
  sezzle               https://job-boards.greenhouse.io/sezzle/jobs/7598109003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/6110231003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/7598109003?gh_src=844ef6823us
  sezzle               https://job-boards.greenhouse.io/sezzle/jobs/7586431003?gh_src=844ef6823us
  sezzle               https://job-boards.greenhouse.io/sezzle/jobs/6275706003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/6110233003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/6110233003?ref=employbl
  sezzle               https://job-boards.greenhouse.io/sezzle/jobs/6275706003?gh_src=6d383ce23us
  sezzle               https://boards.greenhouse.io/sezzle/jobs/5761145003
  sezzle               https://job-boards.greenhouse.io/sezzle/jobs/6110238003
  sezzle               http://job-boards.greenhouse.io/sezzle/jobs/6110238003
  jumo                 https://job-boards.greenhouse.io/jumo/jobs/7676854?gh_jid=7676854
  verisign             https://job-boards.greenhouse.io/verisign/jobs/7766899003
  elwoodtechnologies   https://job-boards.greenhouse.io/elwoodtechnologies/jobs/6209718004
  helsing              https://job-boards.greenhouse.io/helsing/jobs/4976480101

## software engineer II
  icapitalnetwork      https://job-boards.greenhouse.io/icapitalnetwork/jobs/8607441002
  smartsheet           http://job-boards.greenhouse.io/smartsheet/jobs/8097667
  maymobility          http://job-boards.greenhouse.io/maymobility/jobs/8552080002
  coherehealth         https://job-boards.greenhouse.io/coherehealth/jobs/8038003003
  hyannisportresearch  http://job-boards.greenhouse.io/hyannisportresearch/jobs/6578754003
  samsara              https://job-boards.greenhouse.io/samsara/jobs/8036387
  diligentcorporation  https://job-boards.greenhouse.io/diligentcorporation/jobs/6142432004
  upstart              https://job-boards.greenhouse.io/upstart/jobs/8026826
  idme                 http://job-boards.greenhouse.io/idme/jobs/8011089003
  relativity           https://job-boards.greenhouse.io/relativity/jobs/8834015002
  upstart              https://job-boards.greenhouse.io/upstart/jobs/8159614
  formationbio         https://job-boards.greenhouse.io/formationbio/jobs/8167853
  klaviyo              https://job-boards.greenhouse.io/klaviyo/jobs/7806006003?gh_src=Summit+Partners+job+board
  kargo22              https://job-boards.greenhouse.io/kargo22/jobs/5218131007
  mcmastercarr         http://job-boards.greenhouse.io/mcmastercarr/jobs/4053357009
  freenome             http://job-boards.greenhouse.io/freenome/jobs/8414748002
  affirm               http://job-boards.greenhouse.io/affirm/jobs/8003020003
  pinterest            https://job-boards.greenhouse.io/pinterest/jobs/5459622
  axon                 https://job-boards.greenhouse.io/axon/jobs/7766519003
  affirm               http://job-boards.greenhouse.io/affirm/jobs/8003028003

## new grad software engineer
  scaleai              http://job-boards.greenhouse.io/scaleai/jobs/4730836005
  scaleai              http://job-boards.greenhouse.io/scaleai/jobs/4736426005
  stripe               https://job-boards.greenhouse.io/stripe/jobs/8130930
  freeformfuturecorp   https://job-boards.greenhouse.io/freeformfuturecorp/jobs/7826634003
  trueanomalyinc       https://job-boards.greenhouse.io/trueanomalyinc/jobs/5232802007
  kikoff               http://job-boards.greenhouse.io/kikoff/jobs/4393822009
  perpay               http://job-boards.greenhouse.io/perpay/jobs/4034578007
  generalmatter        http://job-boards.greenhouse.io/generalmatter/jobs/5375987008
  singlestore          https://job-boards.greenhouse.io/singlestore/jobs/8205427
  cssmerge             http://job-boards.greenhouse.io/cssmerge/jobs/8687930002
  idmeuniversityrecruiting https://job-boards.greenhouse.io/idmeuniversityrecruiting/jobs/7980382003
  idme                 http://job-boards.greenhouse.io/idme/jobs/8011089003
  authenticinsurance   http://job-boards.greenhouse.io/authenticinsurance/jobs/4114318009
  pinterest            https://job-boards.greenhouse.io/pinterest/jobs/7838591
  seatgeek             https://job-boards.greenhouse.io/seatgeek/jobs/8227548
  singlestore          https://job-boards.greenhouse.io/singlestore/jobs/8220882
  newsbreak            http://job-boards.greenhouse.io/newsbreak/jobs/4615879006
  deliveroo            https://job-boards.greenhouse.io/deliveroo/jobs/8202627
  wehrtyou             https://job-boards.greenhouse.io/wehrtyou/jobs/8052122
  fanduel              https://job-boards.greenhouse.io/fanduel/jobs/7981990

## early career software engineer
  wonderschool         http://job-boards.greenhouse.io/wonderschool/jobs/6359139003
  roblox               https://job-boards.greenhouse.io/roblox/jobs/8072244
  asm                  https://job-boards.greenhouse.io/asm/jobs/4876722101
  idme                 http://job-boards.greenhouse.io/idme/jobs/8011089003
  sirenopt             https://job-boards.greenhouse.io/sirenopt/jobs/4452002009
  stripe               https://job-boards.greenhouse.io/stripe/jobs/8212508
  stripe               https://job-boards.greenhouse.io/stripe/jobs/8212517
  andurilindustries    http://job-boards.greenhouse.io/andurilindustries/jobs/5162263007
  affirm               http://job-boards.greenhouse.io/affirm/jobs/8010617003
  earlycareerprograms  https://job-boards.greenhouse.io/earlycareerprograms/jobs/7258158






  110 result URLs → 68 distinct slugs

slug                   company                         jobs hits
sezzle                 Sezzle                           231   16
spacex                 SpaceX                          2776    5
roblox                 Roblox                           262    5
pinterest              Pinterest                        156    4
stripe                 Stripe                           731    3
affirm                 Affirm                           219    3
optiverus              Optiver                          167    3
idme                   ID.me                             46    3
samsara                Samsara                          285    2
scaleai                Scale AI                         178    2
upstart                Upstart                           92    2
roku                   Roku                              90    2
fanduel                FanDuel                           81    2
singlestore            SingleStore                       45    2
andurilindustries      Anduril Industries              2530    1
asm                    ASM                              499    1
axon                   Axon                             483    1
cloudflare             Cloudflare                       436    1
mongodb                MongoDB                          394    1
relativity             Relativity Space                 382    1
waymo                  Waymo                            366    1
cssmerge               ATOMS Careers page               333    1
coreweave              CoreWeave                        318    1
avepoint               AvePoint                         296    1
deliveroo              Deliveroo                        226    1
icapitalnetwork        iCapital                         209    1
trueanomalyinc         True Anomaly                     206    1
klaviyo                Klaviyo                          165    1
helsing                Helsing                          157    1
robinhood              Robinhood                        156    1
cannondesign           CannonDesign                     151    1
thenewyorktimes        The New York Times               150    1
figma                  Figma                            143    1
generalmatter          General Matter                   127    1
smartsheet             Smartsheet                        88    1
wehrtyou               Hudson River Trading              87    1
freeformfuturecorp     Freeform                          84    1
neuralink              Neuralink                         79    1
coherehealth           Cohere Health                     76    1
newsbreak              NewsBreak                         66    1
kikoff                 Kikoff                            53    1
maymobility            May Mobility                      41    1
wonderschool           Wonderschool                      39    1
efihr                  OMP Careers                       38    1
spire                  Spire                             38    1
seatgeek               SeatGeek                          38    1
diligentcorporation    Diligent Corporation              34    1
livecareer             BOLD                              30    1
kargo22                Kargo                             30    1
mcmastercarr           McMaster-Carr                     30    1
freenome               Freenome                          30    1
amtechsoftware         Amtech Software                   24    1
intrinsicrobotics      Intrinsic                         24    1
perpay                 Perpay - Career's Page            22    1
formationbio           Formation Bio                     20    1
verisign               Verisign                          16    1
sirenopt               SirenOpt                          14    1
authenticinsurance     Authentic                         12    1
hyannisportresearch    HPR                               11    1
idmeuniversityrecruiting ID.me University Recruiting        7    1
elly                   elly                               6    1
elwoodtechnologies     Elwood Technologies                5    1
warp                   Warp                               4    1

63 verified · 5 failed verification: beaconsoftware, earlycareerprograms, jumo, shiftleft, snyk
watchlist: data/watchlist.csv (63 boards)






{
  "skills": [
    "TypeScript",
    "JavaScript (ES6)",
    "Python",
    "Ruby",
    "SQL",
    "HTML",
    "CSS",
    "React.js",
    "Next.js",
    "Node.js",
    "Express.js",
    "Flask",
    "React Testing Library",
    "Jest",
    "Unittest",
    "Tailwind",
    "MUI",
    "Socket.IO",
    "PostgreSQL",
    "SQLAlchemy",
    "Supabase",
    "AWS EC2",
    "AWS S3",
    "CloudFront",
    "CodeBuild",
    "CloudWatch",
    "CloudTrail",
    "Route 53",
    "IAM",
    "Amazon RDS",
    "VPC",
    "Git",
    "GitHub",
    "Slack",
    "Asana",
    "LLMs",
    "AI models",
    "CI/CD"
  ],
  "experience": [
    "Software Engineer, Freelance (Full-time), Apr 2024–Present: 
    Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses; 
    implemented microservice architecture;
     added real-time WebSocket (Socket.IO) messaging; 
     deployed custom AWS suite for high-availability production.",

    "Practicum Lead / Mentor, Code The Dream, Sep 2023–Present: 
    Led and mentored cohorts through month-long React projects from planning to delivery; upheld coding standards via code reviews; managed Agile task delegation; coached engineers on debugging, version control, and research methods.",

    "Software Engineer, Pantry (Full-time), Aug 2022–Sep 2023:
     Designed responsive UI/UX with React and Tailwind; overhauled JavaScript codebase to TypeScript; architected loosely coupled modular React components; conducted code reviews that reduced bug-related issues by 40%.",
    
    "Software Engineer Intern, Numbers API, May 2022–Jun 2022: 
    Converted Node.js services to Flask with RESTful endpoints and DRY principles; 
    modeled data tables with SQLAlchemy backed by Jest tests; refactored legacy codebase to MVC pattern with comprehensive documentation."
  ],
  "education": [
    "Full Stack Web Development, Rithm School, Mar 2022–Jun 2022"
  ],
  "other": [
    "Spoken languages: English, Spanish",
    "Open Source Contributor — Open Disclosure (Ruby | JavaScript | Jekyll): optimized campaign-contribution calculation algorithm, improving processing efficiency and reducing data footprint."
  ]
}







v) jf@Joanness-MacBook-Pro lumbergh % python3 my_agent/resume.py
{
  "skills": [
    "TypeScript",
    "JavaScript (ES6)",
    "Python",
    "Ruby",
    "SQL",
    "HTML",
    "CSS",
    "React.js",
    "Next.js",
    "Node.js",
    "Express.js",
    "Flask",
    "React Testing Library",
    "Jest",
    "Unittest",
    "Tailwind",
    "MUI",
    "Socket.IO",
    "PostgreSQL",
    "SQLAlchemy",
    "Supabase",
    "EC2",
    "S3",
    "CloudFront",
    "CodeBuild",
    "CloudWatch",
    "CloudTrail",
    "Route 53",
    "IAM",
    "Amazon RDS",
    "VPC",
    "Git",
    "GitHub",
    "Slack",
    "Asana",
    "LLMs",
    "AI models",
    "Agile",
    "CI/CD",
    "Cloud Computing"
  ],
  "experience": [
    "Software Engineer, Freelance (Full-time), Oakland, CA, Apr 2024 – Present: Designed, built, and shipped a full stack application, now live in beta with local businesses, owning every layer from concept to production: a React/TypeScript front end, a Python/PostgreSQL back end.",
    "Software Engineer, Freelance (Full-time), Oakland, CA, Apr 2024 – Present: Implemented microservice architecture to facilitate client requests and database management boosting code maintainability.",
    "Software Engineer, Freelance (Full-time), Oakland, CA, Apr 2024 – Present: Boosted user engagement and productivity with an intuitive and polished UX with custom built, user-facing React features.",
    "Software Engineer, Freelance (Full-time), Oakland, CA, Apr 2024 – Present: Implemented real-time communication features with WebSockets (Socket.IO), enabling live updates and messaging between concurrent logged-in clients.",
    "Software Engineer, Freelance (Full-time), Oakland, CA, Apr 2024 – Present: Constructed and deployed a custom AWS suite to run a high-availability full stack application, improving performance, security, and maintainability.",
    "Practicum Lead / Mentor, Code The Dream, Remote, Sep 2023 – Present: Lead and mentor cohorts of student engineers through month-long React projects, guiding teams from planning through delivery across Git, GitHub, and Slack.",
    "Practicum Lead / Mentor, Code The Dream, Remote, Sep 2023 – Present: Uphold coding standards through comprehensive code reviews while managing Agile task delegation for high-quality, on-time delivery.",
    "Practicum Lead / Mentor, Code The Dream, Remote, Sep 2023 – Present: Coach engineers on core professional skills: debugging, troubleshooting, version control, and effective research methods, accelerating their growth and collaboration.",
    "Software Engineer, Pantry (Full-time), Emeryville, CA, Aug 2022 – Sep 2023: Designed a polished, responsive UI/UX with React and Tailwind, elevating the product's visual quality.",
    "Software Engineer, Pantry (Full-time), Emeryville, CA, Aug 2022 – Sep 2023: Overhauled the JavaScript codebase to TypeScript, improving reliability, maintainability, and developer productivity.",
    "Software Engineer, Pantry (Full-time), Emeryville, CA, Aug 2022 – Sep 2023: Architected React components with a loosely coupled, modular pattern for improved scalability.",
    "Software Engineer, Pantry (Full-time), Emeryville, CA, Aug 2022 – Sep 2023: Conducted thorough code reviews that reduced bug-related issues by 40%, ensuring high-quality production features.",
    "Software Engineer Intern, Numbers API, San Francisco, CA, May 2022 – Jun 2022: Converted Node.js services to Flask, enforcing RESTful endpoints and DRY principles for better maintainability and scalability.",
    "Software Engineer Intern, Numbers API, San Francisco, CA, May 2022 – Jun 2022: Modeled data tables with SQLAlchemy, backed by Jest tests, ensuring reliable functionality.",
    "Software Engineer Intern, Numbers API, San Francisco, CA, May 2022 – Jun 2022: Refactored a legacy codebase to an MVC pattern with comprehensive documentation, streamlining collaborative development."
  ],
  "education": [
    "Full Stack Web Development, Rithm School, San Francisco, CA, Mar 2022 – Jun 2022"
  ],
  "other": [
    "Spoken language: English",
    "Spoken language: Spanish",
    "Candidate location: Oakland, CA",
    "Open Disclosure (Ruby | JavaScript | Jekyll): Optimized a campaign-contribution calculation algorithm, improving processing efficiency and reducing the data footprint.",
    "Open Disclosure (Ruby | JavaScript | Jekyll): Used Slack and code reviews to align on technical strategy, improving communication and remote-work efficacy."
  ]
}






728 fetched · 10 considered · 15 model calls · 14.2s

 1.  80.8  Stripe —     Backend / API Engineer, Radar  (6/2/1)
 2.  80.8  Stripe — Backend / API Engineer, Radar  (6/2/1)
 3.  47.9  Stripe — AI Engineer  (4/4/7)

blocked:
     75.0  Stripe — Backend/API Engineer, Money as a Service (Product)   ⛔ 2-12+ years of industry software engineering experience (excluding internships and co-ops)
     58.3  Stripe — Backend/API Engineer, Money as a Service  ⛔ 2–12+ years of industry software engineering experience (does not include internships or co-ops)
     38.9  Stripe — Backend Engineer, Core Technology  ⛔ 2–12+ years of professional hands-on software development experience
     33.3  Stripe — Android Engineer, Terminal OS Platform  ⛔ 2–6 years of experience in Android development
     25.0  Stripe — Android Engineer, Terminal - CA  ⛔ 2+ years of experience in Android development
     15.6  Stripe — Abuse Research Engineer  ⛔ 5+ years of experience conducting threat intelligence, threat hunting, or technical incident response within cyber security, product abuse, or trust domains.; 5+ years of experience analyzing large, complex datasets using data analytics tools to identify anomalies, map behavioral trends, and solve complex fraud problems.
     13.6  Stripe — Android BSP Engineer  ⛔ 2+ years of software engineering experience in device driver development, embedded systems, or operating systems; 2+ years working with mobile or other connected devices









## Save it next to the v0 trace.
     > find backend roles at mid-size product companies, skip defense and crypto
  → discover_boards({"role": "backend engineer", "limit": 15})
  ← 15 boards for 'backend engineer' (slug — company, open jobs):  (16 lines)
  → rank_jobs({"boards": ["stripe", "cloudflare", "verkada", "doordashusa", "esri", "avepoint", "axon", "generalmatter"], "title_any": ["backend", "software engineer", "developer"]})
  ← 3364 fetched · 76 considered · 49 model calls · 41.1s  (36 lines)
  → filter_results({"exclude_keywords": ["Singapore", "Vietnam", "Romania", "Poland", "London", "United Kingdom"]})
  ← 14 of 24 after filtering  (15 lines)

Boards: stripe, cloudflare, verkada, doordashusa, esri, avepoint, axon, generalmatter — skipped spacex (defense/aerospace), andurilindustries (defense), relativity (aerospace), helsing (defense AI), trueanomalyinc (defense/space), asm (industrial, not product), cssmerge (unclear fit).

Dropped 10 non-US listings: Singapore (AvePoint ×4, Axon ×1), Vietnam (Axon ×3), Romania (Axon ×1), Poland (Verkada ×1), London/UK (Axon ×1). 14 listings remain.

Ranked results:

1. 80.8 (6 met / 2 partial / 1 unmet) — Stripe, Backend / API Engineer, Radar — San Francisco, Seattle, New York
2. 80.8 (6/2/1) — Stripe, Backend / API Engineer, Radar — Toronto (Canadian office, if open to that)
3. 78.6 (5/1/1) — Cloudflare, Software Engineer, Deploy at Scale — Hybrid
4. 78.6 (4/3/0) — DoorDash USA, Software Engineer, Backend (All Teams) — SF / NYC / Sunnyvale / Seattle
5. 65.4 (4/2/3) — Verkada, Software Engineer, Platform Infrastructure — San Mateo, CA
6. 60.7 (2/6/1) — Cloudflare, Software Engineer, FL — Hybrid
7. 60.0 (1/1/1) — Verkada, Software Engineer - Data Platform — San Mateo, CA
8. 53.3 (1/8/1) — Cloudflare, Software Engineer, CDN Configuration Group — Hybrid
9. 47.2 (1/8/3) — Cloudflare, Software Engineer, Agentic Discovery — In-Office
10. 42.3 (2/9/5) — Cloudflare, Software Engineer - Egress (Go/Rust) — Hybrid
11. 33.3 (2/1/5) — DoorDash USA, Software Engineer, Data Platform — SF / Sunnyvale / Seattle / NYC
12. 30.0 (1/6/7) — Cloudflare, Software Engineer, Cloudflare Network Interconnect — Hybrid
13. 21.1 (1/3/6) — DoorDash USA, Software Engineer, Data and AI Platform — SF / Sunnyvale
14. 5.0 (0/1/10) — Cloudflare, Software Engineer, Mobile SDK — Hybrid

Top picks to focus on: #1/#2 (Stripe Radar), #3 (Cloudflare Deploy at Scale), and #4 (DoorDash Backend) are all strong matches near Oakland.

Blocked: 10 listings were blocked. Top three by score:
- 75.0 Stripe, Backend/API Engineer, Money as a Service — blocked by "2–12+ years of industry software engineering experience (excluding internships and co-ops)"
- 72.7 Verkada, Backend Engineer - Connectivity — blocked by "BS or MS degree in Computer Science or similar technical field of study"
- 61.1 Stripe, Backend Engineer, Link — blocked by "2–10+ years of industry software engineering experience (not including internships or co-ops)"

Want me to explain the match details on any specific listing, or filter further (e.g., only hybrid/remote, score above a threshold)?


  [4 cycles · tools {'discover_boards': 1, 'rank_jobs': 1, 'filter_results': 1} · 13944 tokens]