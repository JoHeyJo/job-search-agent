# Golden-set labeling rules

How the labels in this folder were made. Applied identically to every file; when a new case forced a
decision, the rule was written here and earlier files were re-checked against it.

## What counts as a requirement

1. Only items from qualification sections ("Minimum qualifications", "You might be a good fit if",
   "Strong candidates will have", "Preferred qualifications", "Bonus if"). Responsibilities, company
   blurbs, and benefits are not requirements.
2. Working-style and personality items are excluded: communication, collaboration, curiosity,
   ownership, "comfortable with ambiguity", "high bar", "scrappy", "team of one", "prototype
   quickly", "interest in working as a generalist", "minimal oversight". They cannot be verified
   against a résumé and every candidate partially has them.
3. Logistics boilerplate is excluded (hybrid-office policy, visa sponsorship, "years correlate with
   level", "Required field of study"). Exception: the "Minimum education" line is kept, because a
   degree is a real gate.
4. `preferred` is true only for items under a Preferred / Nice to have / Bonus heading or phrased
   "is a plus".
5. Spans must not overlap. A bullet containing two distinct asks is split into two non-overlapping
   spans.

## How status is judged

6. From the résumé text only. Knowing you can do something that the résumé doesn't say is a résumé
   edit, not a `met`.
7. Alternatives ("X, Y, or Z"; "such as"; "e.g."; "etc.") are met if any one alternative is met.
   The named items are examples of a category.
8. Conjunctions ("A, B, and C") are met only if every part is shown; some parts shown → partial.
9. Years: fewer than asked → partial, regardless of the size of the gap. Full-time freelance work
   does not count as "industry experience" when a posting uses that phrase; it does count as
   professional software engineering experience otherwise.
10. Degree required "or equivalent experience/training", no degree on the résumé → partial.
    Degree required with no alternative → unmet.
11. A skill that is only in the skills list, with no role bullet showing it in use, supports at
    most partial.
12. A requirement is partial only with a nameable gap on something partly demonstrated. If the only
    link between evidence and requirement is a shared word, it is unmet.
13. Precedents: shipping production code / production web properties → met (freelance app in
    production, Pantry). MUI counts as a design system. CSS "complex layouts and animations" →
    partial (responsive Tailwind UI shown; animations not). Personal projects do not satisfy
    "in a professional setting" or "shipped production" → partial.

## Mechanics

- `"labeled": true` or the file is ignored. `"status": ""` skips that requirement for the matching
  metric but keeps it for extraction.
- Spans are matched by normalized containment, so copying a slightly longer or shorter span than the
  model's is fine.