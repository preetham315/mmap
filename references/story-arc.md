# Story arc — make the questions a narrative

A mind map should read like a **story told through its questions**, not a flat Q&A list.
The **solid spine is a chain of questions** (`question → question`), each building on the last;
**answers hang off each question as dashed, confidence-colored branches**. The renderer enforces
this automatically (solid = an edge into a `question`; dashed+colored = an edge into an answer).

## The cardinal rules

1. **Adaptive opening question.** The root question is a _hook specific to this repo_ — never a
   fixed template. Bad: "What is the best way to represent the architecture?" Good (a payments
   service): "The one thing it can't get wrong is charging an order twice — where does the code make
   its stand?"
2. **Pick a lens, then a protagonist, and never break POV.** Choose the lens that fits the repo
   (below). The protagonist is the thing the story follows (a request, a build, the data, a
   newcomer). Every question asks "what happens to _it_ here", not "what does module X do".
3. **Chain questions, don't hub them.** `q1 → q2 → q3 …`, each question's `parent` is the
   **previous question** — so the solid spine is one continuous thread. Read the questions
   top-to-bottom: they must form one escalating-then-resolving paragraph.
4. **Inherit a noun each beat** so the spine reads as prose: "…walk me through one _build_" →
   "given that _build_, what _threatens_ it?" → "given that _threat_, how is it _gated_?" →
   "given that _gate_, what does it _cost_?".
5. **Each question gets answers as dashed branches:** exactly one `primary:true` lead finding
   (heavier dash) + 0–3 alternatives/rivals/waypoints. Star (`highlight`) the genuinely clever
   ones, sparingly.
6. **Climax = your strongest node.** The beat that pays off the opening tension should be the
   highest-confidence, most evidence-dense, gold-starred node. Don't hand-wave the payoff —
   verify it in code so it can be green.
7. **Let color darken honestly.** Green orientation facts up top; amber/red are _expected_ at the
   cracks. An explicit "I couldn't open this path:line — point me at it" red node is a feature.
8. **Falling action in a collapsed `group`.** Cluster the costs/cracks into a "Considerations"
   group near the end; close on price, risks, and the first file to open at 3am — not a
   triumphant summary.

## Lenses (pick one to fit the repo)

| Lens                 | Use when                                                                                        | The arc                                                                                    |
| -------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **Crux / stakes**    | the code spends visible structure defending one hard guarantee (invariants, gates, consistency) | the stand → happy path → the threat → how it's enforced (climax) → the cost → the 3am file |
| **Artifact journey** | a central artifact flows through the system (a request, a record, a dataset)                    | intent/input → transforms → the guarantees that hold → output → where it can leak          |
| **Onboarding**       | general-purpose app/library with no single crux                                                 | what is this & why → how it's shaped → trace one path → what will bite a newcomer          |

Default heuristic: if there's one guarantee the architecture clearly bends around → **crux**;
else if one artifact obviously flows end-to-end → **artifact**; else → **onboarding**.

## Worked spine (a payments service, crux lens)

q1 "where does it make its stand (charge each order exactly once)?" → q2 "walk one checkout end to
end" → q3 "what threatens it (double-submit, retry, partial failure)?" → q4 "how is it enforced with
no escape hatch?" (climax: the idempotency check + the one-transaction commit — gold-starred, green)
→ q5 "what does that cost; where could it quietly not hold?" → q6 "if it failed in prod tomorrow,
first file to open?". Each beat carries a primary finding + dashed alternatives; the genuinely clever
bits (e.g. idempotency-key dedupe) are starred.
