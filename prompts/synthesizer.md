# Synthesis Prompt Template

Used in Phase 6 — Final Synthesis. Implements:
- **Structured synthesis** adapted from Mysti (BrainstormManager.ts:1376-1452)
- **3-level fallback chain** from Mysti (BrainstormManager.ts:912-988)

---

## Primary Synthesis Prompt

Adapted from Mysti's verbatim synthesis prompt:
```
# Synthesis: Final Team Recommendation
Your job is not merely to merge — it is to produce a recommendation BETTER than
any individual agent's.
```

### Prompt

```
You are synthesizing a multi-agent adversarial product research debate.

Your job is not merely to announce the winner — it is to produce a recommendation
document that is MORE useful than any individual agent's research.

## Original Query
{{QUERY}}

## Debate Results

**Winner**: {{WINNER}} — selected by {{JUDGE_METHOD}} with {{JURY_STATUS}}
**Runner-up**: {{RUNNER_UP}}
**Eliminated products**: {{ELIMINATED_LIST_WITH_ROUND}}

## Evidence Archive
{{ALL_RESEARCH_AND_DEBATE_EVIDENCE}}

## Convergence Status: {{CONVERGENCE_RECOMMENDATION}}
Overall convergence: {{CONVERGENCE_PERCENTAGE}}%
{{IF_STALLED: "The panel could NOT reach consensus. Pay special attention to unresolved disagreements below — they represent genuine tradeoffs."}}
{{IF_CONVERGED: "The panel reached consensus after {{N}} of {{MAX}} rounds. High confidence in this recommendation."}}

## Required Output (ALL sections mandatory)

### Recommendation

**{{WINNER}}** — {{ONE_SENTENCE_VERDICT}}

**Buy here**: [direct product link — must be a working URL to purchase or view the product]

### Comparison Table

| | {{WINNER}} | {{RUNNER_UP}} | {{ELIMINATED_1}} | {{ELIMINATED_2}} | {{ELIMINATED_3}} |
|---|---|---|---|---|---|
| **Price** | | | | | |
| **[Key Spec 1]** | | | | | |
| **[Key Spec 2]** | | | | | |
| **[Key Spec 3]** | | | | | |
| **Best for** | | | | | |
| **Worst for** | | | | | |
| **Verdict** | WINNER | Runner-up | Eliminated | Eliminated | Eliminated |

(Adapt spec rows to the product category. Table MUST include ALL products from Phase 1, not just finalists.)

### Why {{WINNER}} Wins

[2-3 paragraphs explaining the reasoning chain. Reference:
- What evidence was most persuasive across agents
- What tradeoffs were accepted and why
- Specific debate moments where positions shifted
- Why the runner-up fell short on the query's specific requirements]

### The Case for {{RUNNER_UP}} (When It Might Be Better)

**Buy here**: [direct product link — must be a working URL to purchase or view the runner-up]

[1-2 paragraphs on specific scenarios where the runner-up IS the better choice. Different use case, different budget, different priorities. Be specific — "if you prioritize X over Y" not "if your needs differ."]

### What the Debate Missed

[Honest assessment of:
- Evidence gaps (claims no agent could verify)
- Market factors not researched (upcoming models, seasonal pricing)
- Use cases not explored
- Potential biases in the research (e.g., all sources were US-centric)]

### Sources

[Deduplicated list of all URLs cited, organized by product:]

**{{WINNER}}**:
- [url1]
- [url2]

**{{RUNNER_UP}}**:
- [url1]

(Continue for all products)

## Rules
- Comparison table MUST include ALL products from Phase 1, not just finalists
- Every claim MUST come from the debate evidence — no new claims
- Price MUST appear for every product
- Sources MUST be real URLs from agents' research — never fabricate
- **"Buy here" links are MANDATORY** for winner and runner-up — must be direct product pages (manufacturer, Amazon, or major retailer), not search results or category pages
- Be direct: "Buy X" not "X could be a good option"
- If jury challenged the winner, acknowledge the controversy
```

---

## 3-Level Synthesis Fallback (from Mysti BrainstormManager.ts:912-988)

From Mysti's verbatim fallback chain:
```
1. Try synthesis agent
2. Try another session agent
3. Concatenate raw individual analyses with prefix:
   "*Synthesis unavailable — individual analyses below:*"
```

### Level 1 — Primary (above prompt)

Run the full synthesis prompt via Task tool with `model: "opus"`.

### Level 2 — Backup

If primary synthesis agent fails or produces garbage (missing required sections), run a second agent with simplified prompt:

```
Summarize the results of this product research debate.

Winner: {{WINNER}} (${{PRICE}}). Runner-up: {{RUNNER_UP}} (${{PRICE}}).

Create:
1. A comparison table of all products with price, key specs, best/worst for
2. A 2-paragraph recommendation explaining why the winner was chosen
3. A list of all source URLs organized by product

Evidence: {{EVIDENCE_SUMMARY}}
```

### Level 3 — Concatenate Raw

If both fail, present raw findings:

```
*Full synthesis unavailable. Individual agent findings below:*

## Judge's Verdict
{{JUDGE_VERDICT}}

## Agent Research Summaries

### {{PERSONA_1}}'s Pick: {{PRODUCT_1}}
{{FINAL_POSITION_1}}

### {{PERSONA_2}}'s Pick: {{PRODUCT_2}}
{{FINAL_POSITION_2}}

[... all agents ...]
```
