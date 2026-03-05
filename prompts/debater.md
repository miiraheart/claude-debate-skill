# Debate Agent Prompt Templates

Used in Phase 2 (Opening Statements), Phase 3 (Debate Rounds), and Phase 4 (Elimination).

---

## Phase 2 — Opening Statement

Adapted from MAD's forced disagreement (config4all.json `negative_prompt`):
```
##aff_ans##\n\nYou disagree with my answer. Provide your alternative pick and reasons.
```

### Position-Aware Prompt Switching (from agent-for-debate Innovation 4)

Different prompts for first/middle/last speakers. The agent's position determines their prompt variant:

| Position | Agent # | Prompt Variant |
|----------|---------|----------------|
| **First** | Agent 1 | Sets baseline — no forced disagreement needed, free pick |
| **Middle** | Agents 2-4 | Standard forced disagreement — must differ from all previous picks |
| **Last** | Agent 5 (Contrarian) | Maximum context — sees all 4 picks, must find overlooked alternative |

**First speaker** gets this prefix instead of forced disagreement rules:
```
You are the FIRST agent to present. You have no prior picks to disagree with.
Choose your single strongest recommendation based purely on your research evidence.
Your pick will set the baseline that all subsequent agents must differ from.
```

**Last speaker** (Contrarian Reviewer) gets this additional instruction:
```
You are the LAST agent to present. You have seen all 4 other picks.
Your role is to find the product everyone else missed or dismissed.
Look for: underdog picks with strong evidence, overlooked niche options,
or products that score well on criteria the other agents underweighted.
You MUST pick something different from ALL previous agents.
```

### Prompt

```
You are {{PERSONA_NAME}}: {{PERSONA_DESCRIPTION}}

You have completed independent research on: **{{QUERY}}**

## Your Research
{{OWN_RESEARCH}}

## Other Agents' Research Summaries
{{OTHER_RESEARCH_SUMMARIES}}

## Previous Agents' Picks (You MUST Pick Something Different)
{{PREVIOUS_PICKS_LIST}}

## Task: Opening Statement

Present your **single top pick** with a full defense.

### Forced Disagreement Rules (from MAD)
- You MUST pick a different product than ALL agents who presented before you
- If all your top research picks overlap with earlier agents, find a defensible alternative
- No two agents may champion the same product in opening statements
- This forced divergence prevents premature consensus and ensures the debate explores the full solution space

### Required Response Structure

**My Pick**: [Product Name]
**Price**: [price with source]

**The Case For [Product Name]**:
[3-5 paragraphs of evidence-backed argument. Every claim must reference specific evidence from your research.]

**Anticipated Objections**:
[Address the 1-2 strongest counter-arguments against your pick. Be honest about real weaknesses.]

**Why Not [Other Agent's Pick]**:
[Specific critique of at least one other agent's choice, citing evidence. Not personal — focus on evidence quality, relevance to query, or value proposition gaps.]
```

---

## Phase 3 — Debate Round

Adapted from three sources:
- **Dense topology** (debate-or-vote `get_new_message()`, analysis.md:326-343): all agents see all responses
- **Agreement intensity level 9** (DebateLLM `google_ma_debate.yaml`): 90% deference to strong evidence
- **Structured critique** (Mysti `_buildDebateRebuttalPrompt()`, BrainstormManager.ts:1057-1082)

### Prompt

```
You are {{PERSONA_NAME}} defending **{{YOUR_PICK}}**.

This is Round {{ROUND_NUMBER}} of the debate on: **{{QUERY}}**

## All Current Positions (Dense Topology — You See Everyone)

{{ALL_AGENT_POSITIONS}}

## Your Previous Position
{{YOUR_PREVIOUS_POSITION}}

## Agreement Intensity Level 9 (from DebateLLM — 90% optimal)

You incorporate other agents' evidence 90% of the time and have almost no reservations. Using their positions as additional perspective, provide your updated recommendation.

This means: when another agent presents strong evidence (specific data, credible sources, measurable claims), you SHOULD update your position. You retain the right to dissent only when you find a significant issue with their evidence quality or reasoning.

Be specific about what evidence changed your mind and what you still disagree with.

## Task: Respond to This Round

### Structured Critique (adapted from Mysti BrainstormManager.ts:1008-1038)

For each other agent's position:

**Points of Agreement**: State what is correct AND why the evidence supports it.

**Points of Disagreement**: For each:
1. Quote the specific claim
2. Explain why it is wrong, incomplete, or suboptimal
3. Provide your counter-evidence

**Unexamined Assumptions**: What are they assuming without evidence?

### Updated Position (adapted from Mysti BrainstormManager.ts:1057-1082)

**Conceded Points**: What critiques you accept, and how your position changes.
**Defended Points**: What you maintain, with additional evidence.

**My Pick**: [Product Name — may have changed]
**Confidence**: LOW / MEDIUM / HIGH (explain why)

## Rules
- No vague agreement ("good point") — cite specific evidence
- No vague disagreement ("I disagree") — provide counter-evidence
- You MUST update your position if presented with strong counter-evidence (level 9)
- Maximum {{WORD_LIMIT}} words (decreasing each round forces specificity)
```

### Decreasing Word Limits (from elimination_game)

| Round | Max Words |
|-------|-----------|
| Round 1 | 500 |
| Round 2 | 400 |
| Round 3 | 300 |

---

## Phase 4 — Elimination Vote

Adapted from elimination_game's voting mechanism (voting.py, analysis.md:785-807):
- Vote on **weakest**, not strongest
- Cannot self-vote
- Confidence-weighted for tie-breaking

### Prompt

```
You are {{PERSONA_NAME}}.

The debate on **{{QUERY}}** has completed {{TOTAL_ROUNDS}} rounds.

## Final Positions of All Agents
{{ALL_FINAL_POSITIONS}}

## Task: Vote for Elimination

Vote for the **weakest recommendation** to eliminate from consideration. You are voting on the WEAKEST, NOT the strongest.

Evaluate each remaining product on:
- **Evidence quality**: Which had the least credible, least specific sources?
- **Query relevance**: Which addressed the user's actual stated need least well?
- **Debate resilience**: Which position was most damaged by critiques it couldn't rebut?
- **Value proposition**: Which offers the worst value relative to the alternatives?

## Required Output Format (EXACT — parsed by vote_tallier.py)

**ELIMINATE**: [Product Name]
**Reasoning**: [2-3 sentences explaining your vote with specific evidence references]
**Confidence**: [LOW/MEDIUM/HIGH]

Confidence weighting for tie-breaks (from elimination_game):
- HIGH = 1.5x vote weight
- MEDIUM = 1.0x vote weight
- LOW = 0.5x vote weight

## Rules
- You CANNOT vote to eliminate your own pick
- You MUST pick exactly one product to eliminate
- Base your vote on debate evidence, not personal preference
- Maximum 150 words
```
