---
allowed-tools:
  - Task
  - WebSearch
  - WebFetch
  - Read
  - Write
  - Grep
  - Glob
  - Bash
  - AskUserQuestion
  - Edit
  - Skill
  - mcp__scrapling-fetch__s_fetch_page
  - mcp__scrapling-fetch__s_fetch_pattern
  - mcp__perplexity-mcp__perplexity_search_web
---

# /debate — Multi-Agent Adversarial Product Research

Run a 6-phase adversarial debate with 5 specialized research agents to find the best product recommendation.

**Query**: $ARGUMENTS

## Execution

Use the Skill tool to invoke the `debate` skill with args `$ARGUMENTS`. This loads the full 6-phase pipeline.

```
Skill(skill: "debate", args: "$ARGUMENTS")
```

Follow the loaded skill instructions exactly — it contains:
- Python scripts for session management, convergence detection, and vote tallying
- Prompt templates for researchers, debaters, judges, and synthesizers
- Concrete Task tool invocation patterns for spawning opus-powered agents
- User checkpoints after Phase 1 (research scope) and Phase 4 (finalists)
