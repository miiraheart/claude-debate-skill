# Claude Code Adversarial Debate Skill

A multi-agent adversarial debate system for product research, built as a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill. Five specialized agents research independently, debate with elimination rounds, and produce structured recommendations with verified sources.

## How It Works

Six-phase pipeline orchestrated by Claude Code's Task tool:

1. **Research Sprint** — 5 agents research independently in parallel (Opus-powered)
2. **Opening Statements** — Each agent declares a unique pick (forced disagreement from [MAD](https://arxiv.org/abs/2305.19118))
3. **Debate Rounds** — Dense-topology debate with convergence detection (from [Mysti](https://github.com/mysticetus-inc/brainstorm))
4. **Elimination** — Vote-on-weakest with 4-step tie-break chain (from [elimination_game](https://arxiv.org/abs/2401.01452))
5. **Finals** — 2-step judge evaluation + forced revision + jury validation
6. **Synthesis** — Structured recommendation with comparison table, buy links, and sources

Each agent runs as a **separate LLM instance** with its own persona. No single LLM roleplays multiple agents.

## Research Foundations

Built on techniques from five multi-agent debate papers:

| Technique | Source |
|-----------|--------|
| Forced disagreement, 2-step judge, first-round evidence | [MAD](https://arxiv.org/abs/2305.19118) (Multi-Agent Debate) |
| Convergence detection, Delphi facilitator, 3-level synthesis | [Mysti](https://github.com/mysticetus-inc/brainstorm) BrainstormManager |
| Dense topology, agreement intensity (level 9 optimal) | [DebateLLM](https://arxiv.org/abs/2311.09763) |
| Vote-on-weakest elimination, jury mechanism, private channels | [Elimination Game](https://arxiv.org/abs/2401.01452) |
| Forced revision ("at least 1 revision"), position-aware prompts | [Agent-for-Debate](https://github.com/AIGeniusInstitute/agent-for-debate) |

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed
- Python 3.10+
- Claude Code tools: `Task`, `WebSearch`, `WebFetch`, `AskUserQuestion`

### Recommended MCP Servers

These are **optional** — the skill falls back to `WebSearch`/`WebFetch` without them — but they significantly improve research quality:

**[scrapling-fetch-mcp](https://github.com/cyberchitta/scrapling-fetch-mcp)** — bypasses bot detection on product pages that block standard fetching:

```bash
uv tool install scrapling-fetch-mcp
uvx --from scrapling-fetch-mcp scrapling install
```

Then add to your Claude Code config (`~/.claude.json` or Claude Desktop config):

```json
{
  "mcpServers": {
    "scrapling-fetch": {
      "command": "uvx",
      "args": ["scrapling-fetch-mcp"]
    }
  }
}
```

**[perplexity-mcp](https://github.com/jsonallen/perplexity-mcp)** — web-grounded search with citations, useful for price verification and fact-checking:

```bash
# Via Smithery (recommended)
npx -y @smithery/cli install perplexity-mcp --client claude

# Or manually add to your Claude config:
```

```json
{
  "mcpServers": {
    "perplexity-mcp": {
      "command": "uvx",
      "args": ["perplexity-mcp"],
      "env": {
        "PERPLEXITY_API_KEY": "your-key-here",
        "PERPLEXITY_MODEL": "sonar"
      }
    }
  }
}
```

> Get a Perplexity API key at [perplexity.ai](https://www.perplexity.ai/)

Without these servers, agents still research via built-in `WebSearch` and `WebFetch` tools — they just can't bypass bot-protected pages or use Perplexity's grounded search.

## Quick Install

One command to clone, install the skill + command, and set the env var:

```bash
git clone https://github.com/miiraheart/claude-debate-skill.git ~/.claude/skills/debate && \
cp ~/.claude/skills/debate/commands/debate.md ~/.claude/commands/debate.md && \
echo 'export DEBATE_SKILL_DIR="$HOME/.claude/skills/debate"' >> ~/.zshrc && \
source ~/.zshrc
```

Then open Claude Code and run:

```
/debate best ergonomic keyboard under $200 for programming
```

That's it. The skill, command, and scripts are all in place.

## Manual Installation

If you prefer more control:

### 1. Clone the repo

```bash
git clone https://github.com/miiraheart/claude-debate-skill.git
```

### 2. Install as a Claude Code skill

Symlink or copy into your Claude Code skills directory:

```bash
# Option A: Symlink (recommended — stays in sync with repo)
ln -s "$(pwd)/claude-debate-skill" ~/.claude/skills/debate

# Option B: Copy
cp -r claude-debate-skill ~/.claude/skills/debate
```

### 3. Install the command (optional)

To use `/debate` as a slash command in Claude Code:

```bash
cp claude-debate-skill/commands/debate.md ~/.claude/commands/debate.md
```

### 4. Set the environment variable

The skill references scripts via `$DEBATE_SKILL_DIR`. Add to your shell profile:

```bash
# zsh
echo 'export DEBATE_SKILL_DIR="$HOME/.claude/skills/debate"' >> ~/.zshrc

# bash
echo 'export DEBATE_SKILL_DIR="$HOME/.claude/skills/debate"' >> ~/.bashrc
```

Or if you installed elsewhere, point to your installation path.

## Usage

### Via slash command

```
/debate best ergonomic keyboard under $200 for programming
```

### Via skill invocation

```
Skill(skill: "debate", args: "best noise-cancelling headphones for commuting under $350")
```

### What happens

1. You'll see 5 agents spawn and research independently
2. After research, you'll be asked to approve the product list before debate begins
3. Agents debate, get eliminated, finalists face off
4. After finals, you'll be asked to approve finalists before synthesis
5. Final output: structured recommendation with comparison table, buy links, and sources

## File Structure

```
claude-debate-skill/
├── SKILL.md                          # Main skill — 6-phase orchestration
├── commands/
│   └── debate.md                     # /debate slash command
├── prompts/
│   ├── researcher.md                 # Phase 1 research agent template
│   ├── debater.md                    # Phase 2-4 debate/vote templates
│   ├── judge.md                      # Phase 5 judge + jury templates
│   ├── synthesizer.md                # Phase 6 synthesis template
│   └── personas.md                   # Domain-specific persona definitions
└── scripts/
    ├── debate_orchestrator.py        # Session state, domain detection, context formatting
    ├── convergence_detector.py       # Convergence assessment (keyword + Jaccard + Delphi)
    └── vote_tallier.py               # Vote collection + 4-step tie-break elimination
```

## Scripts

All scripts are standalone Python 3 with no external dependencies.

### debate_orchestrator.py

Session state management and phase transitions.

```bash
python3 scripts/debate_orchestrator.py init "best standing desk under $500"
python3 scripts/debate_orchestrator.py detect-domain "best standing desk"
python3 scripts/debate_orchestrator.py select-personas home
python3 scripts/debate_orchestrator.py assess-convergence 1
python3 scripts/debate_orchestrator.py status
```

### convergence_detector.py

Measures debate convergence using agreement/disagreement keyword patterns and cross-round text similarity.

```bash
python3 scripts/convergence_detector.py /tmp/debate-session/phase3/round-1/
# Exit codes: 0=CONVERGED, 1=CONTINUE, 2=STALLED
```

### vote_tallier.py

Collects votes and resolves eliminations with a 4-step tie-break chain: plurality, confidence-weighted, cumulative, jury tiebreak.

```bash
python3 scripts/vote_tallier.py /tmp/debate-session/phase4/
# Exit code 2 = jury tiebreak required (unresolved tie)
```

## Session Data

Each debate creates a timestamped directory under `/tmp/debate-sessions/` with a symlink at `/tmp/debate-session` pointing to the latest. Previous sessions are preserved.

## Customization

### Agreement intensity

Default is level 9 (90% deference — empirically optimal). Adjust via:

```bash
python3 scripts/debate_orchestrator.py update-state '{"agreement_intensity": 7}'
```

Scale: 0 (total disagreement) to 10 (full incorporation).

### Domain personas

Edit `prompts/personas.md` to add or modify domain-specific expert personas. Budget Strategist and Contrarian Reviewer are always included regardless of domain.

## License

MIT
