# Judge Prompt Templates

Used in Phase 5 — Finals. Implements three techniques:
- **2-step judge** from MAD (interactive.py:199-221, "ultimate deadly technique")
- **Forced revision** from agent-for-debate (reviewer prompts, "至少要让他们修改1次")
- **Jury validation** from elimination_game (finals mechanism, analysis.md:604-675)

---

## Step 1 — Strip to Bare Candidates

Adapted verbatim from MAD's `judge_prompt_last1` (config4all.json):
```
Affirmative side arguing: ##aff_ans##
Negative side arguing: ##neg_ans##
Now, what answer candidates do we have? Present them without reasons.
```

The key insight from MAD: `##aff_ans##` and `##neg_ans##` use `memory_lst[2]` — the **first-round response**, not the latest. This avoids recency bias from tit-for-tat entrenchment.

### Prompt

```
You are an impartial product research judge evaluating finalists for:

**Query**: {{QUERY}}

## Finalist Products (Facts Only — Stripped of All Persuasion)

{{FOR_EACH_FINALIST}}
### {{PRODUCT_NAME}}
- **Price**: {{PRICE}}
- **Key Specs**: {{SPECS_ONLY_NO_OPINIONS}}
{{END_FOR_EACH}}

## Task: Present the Bare Candidates

List each finalist with ONLY:
- Product name and current price
- 3 factual spec bullet points (no adjectives, no opinions, no "best" or "worst")
- The single most important measurable difference vs each other finalist

Do NOT declare a winner. Do NOT evaluate. Just present bare facts.
Strip all persuasive language. If two products are comparable on a spec, say "comparable" and move on.
```

---

## Step 2 — Fresh Evaluation with Evidence

Adapted from MAD's `judge_prompt_last2` (config4all.json):
```
Therefore, ##debate_topic##
Please summarize your reasons and give the final answer that you think is correct.
Now please output your answer in json format: {"Reason": "", "debate_answer": ""}
```

Key design: Step 1 strips context, Step 2 reintroduces evidence. By separating candidate extraction from selection, the judge makes a clean choice without being anchored to either debater's framing.

### Prompt

```
You are an impartial product research judge.

**Query**: {{QUERY}}

## Candidates (Stripped to Facts — from Step 1)
{{STEP_1_OUTPUT}}

## Evidence from Opening Statements (FIRST ROUND — Before Groupthink)

From MAD's memory_lst[2] technique: these are the original positions before
tit-for-tat entrenchment set in. Weight these equally with final-round evidence.

{{OPENING_STATEMENTS_EVIDENCE}}

## Evidence from Final Debate Round
{{FINAL_ROUND_EVIDENCE}}

## Task: Make Your Decision

For each finalist, score on these dimensions:

1. **Query fit (1-10)**: How precisely does this address what was asked?
2. **Evidence strength (1-10)**: How well-supported by credible, specific sources?
3. **Value score (1-10)**: Price-to-quality ratio for the stated needs
4. **Risk score (1-10)**: How likely is the user to be satisfied? (10 = very safe, 1 = risky)

Then declare:

**WINNER**: [Product Name]
**RUNNER-UP**: [Product Name]

**Reasoning**: [3-5 sentences referencing specific evidence from both opening and final rounds]

**Dissent note**: [The strongest argument against your winner — be honest about the tradeoff]

## Rules
- Weight opening-statement evidence equally with final-round evidence
- If scores within 1 point across all dimensions, explain the tiebreaker explicitly
- The query's specific constraints (budget, use case, conditions) override general quality
- You MUST pick a winner — no "it depends"
- Output must be parseable: WINNER and RUNNER-UP on their own lines
```

---

## Forced Revision (from agent-for-debate)

From the reviewer prompt (agent-for-debate, prompt/argument/reviewer_zh.txt):
```
至少要让他们修改1次
```
(Translation: "Must make them revise at least once")

From the English rebuttal reviewer:
```
To ensure your students' success, maintain high standards and guide them towards
crafting impeccable rebuttals. Encourage at least *one* round of revisions.
```

The revision cycle pattern:
```
Judge → initial verdict → Devil's advocate concerns → Judge → revised verdict
```

### Prompt

```
You previously judged this debate and selected **{{WINNER}}** as the winner over **{{RUNNER_UP}}**.

A review panel has flagged these concerns about your judgment:

{{CONCERNS}}

(The orchestrator generates 2-3 devil's-advocate concerns targeting:
- Budget constraint adherence
- Evidence that contradicts the winner
- Scoring inconsistencies
- Whether the runner-up addresses the query's core need better)

## Task: Revised Judgment

Address each concern specifically with evidence. Then either:

1. **MAINTAIN**: Your verdict stands. Provide additional justification that directly addresses every concern.
2. **REVISE**: Change your verdict. Explain what specific evidence changed your mind.

You MUST substantively engage with every concern. Dismissing without evidence is not acceptable.

**FINAL WINNER**: [Product Name]
**FINAL RUNNER-UP**: [Product Name]
**Verdict changed**: YES/NO
**Reasoning**: [Updated reasoning addressing all concerns]
```

---

## Jury Validation (from elimination_game)

From elimination_game's finals mechanism (analysis.md:604-675):
- 2 finalists give statements, all eliminated players form jury
- Jury votes to **eliminate** one finalist — survivor wins
- Jury sees all public history + own private histories

Adapted: **eliminated agents** serve as jurors with their accumulated debate history and private notes.

### Prompt

```
You are {{PERSONA_NAME}}: {{PERSONA_DESCRIPTION}}

You participated in the debate but were eliminated in Phase 4. You now serve as a juror to validate the final verdict.

**Query**: {{QUERY}}

## Your Debate History
{{AGENT_OPENING_STATEMENT}}
{{AGENT_DEBATE_ROUNDS}}
{{AGENT_PRIVATE_NOTES}}

## Finals Result
After elimination voting, a 2-step judge evaluation, and forced revision:

- **Winner**: {{WINNER}} ({{WINNER_PRICE}})
- **Runner-up**: {{RUNNER_UP}} ({{RUNNER_UP_PRICE}})

## Key Evidence Summary
{{EVIDENCE_SUMMARY}}

## Judge's Reasoning
{{JUDGE_REASONING}}

## Task: Validate or Challenge

Using your debate experience and the evidence you gathered, does the winner selection hold up?

1. Does the winner actually address the query's specific requirements better than the runner-up?
2. Is the supporting evidence credible and sufficient?
3. Were arguments you raised during the debate adequately addressed?
4. Would a reasonable person with this information make the same choice?

**Verdict**: VALIDATED / CHALLENGED
**Reasoning**: [2-3 sentences with specific evidence references from your debate experience]
**If CHALLENGED**: What should the winner be instead, and why?
```

### Jury Decision Rule
- If majority of jurors VALIDATE: winner confirmed
- If majority of jurors CHALLENGE: runner-up becomes winner (or jurors' pick if they agree on an alternative)
- If evenly split: winner confirmed but dissent noted in final synthesis

---

## Elimination Tie-Breaker Jury

Used in Phase 4 when `vote_tallier.py` returns `method: "jury_tiebreak_required"` (exit code 2).
Instead of random elimination, the tied products' champions each present a 150-word defense
to an impartial jury agent who evaluates and decides which product to eliminate.

### Step 1: Champions present their case (parallel)

For each tied product, spawn the champion agent:

```
Task(
  subagent_type: "general-purpose",
  model: "opus",
  prompt: "You are {{PERSONA_NAME}} championing **{{TIED_PRODUCT}}**.

  The elimination vote resulted in a tie. You must now defend your product
  against elimination in a tie-breaker round.

  **Query**: {{QUERY}}

  **Products tied for elimination**: {{TIED_PRODUCTS_LIST}}

  **Your product's evidence from the debate**:
  {{CHAMPION_OPENING_STATEMENT}}
  {{CHAMPION_LATEST_POSITION}}

  **Task**: In exactly 150 words, make the strongest possible case for why
  your product should NOT be eliminated. Focus on:
  1. The single strongest piece of evidence supporting your product
  2. The specific weakness of the other tied product(s) that makes them worse
  3. How your product better serves the original query

  Write to /tmp/debate-session/phase4/tiebreak-defense-{{PRODUCT_SLUG}}.md"
)
```

### Step 2: Jury agent decides

A fresh, impartial jury agent reads all defenses and makes the elimination decision:

```
Task(
  subagent_type: "general-purpose",
  model: "opus",
  prompt: "You are an impartial elimination jury for a product research debate.

  **Query**: {{QUERY}}

  The regular elimination vote resulted in a tie between these products:
  {{TIED_PRODUCTS_LIST}}

  Each champion has presented a 150-word defense:

  {{FOR_EACH_TIED_PRODUCT}}
  ### Defense of {{PRODUCT_NAME}}
  {{DEFENSE_CONTENT}}
  {{END_FOR_EACH}}

  **Your task**: Decide which product to ELIMINATE (the weakest).

  Evaluate each defense on:
  1. **Evidence quality (1-10)**: Are claims specific, sourced, and verifiable?
  2. **Query relevance (1-10)**: Does the product actually address what was asked?
  3. **Persuasiveness (1-10)**: Did the champion make a compelling case?

  Score each product, then eliminate the one with the lowest total score.
  If scores are still tied, eliminate the product with the weaker evidence quality
  (evidence > relevance > persuasiveness in priority).

  **Required output format** (parsed by orchestrator):

  ## Scores
  | Product | Evidence | Relevance | Persuasiveness | Total |
  |---------|----------|-----------|----------------|-------|
  | [name]  | [1-10]   | [1-10]    | [1-10]         | [sum] |

  **ELIMINATE**: [Product Name]
  **Reasoning**: [2-3 sentences explaining the decision with specific references to the defenses]
  **Method**: jury_tiebreak

  Write to /tmp/debate-session/phase4/tiebreak-verdict.md"
)
```

### Step 3: Parse result

Read `/tmp/debate-session/phase4/tiebreak-verdict.md`, extract the **ELIMINATE** target,
and continue the elimination flow as if the vote had resolved cleanly.
