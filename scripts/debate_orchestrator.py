#!/usr/bin/env python3
"""
Debate session orchestrator — manages state, file I/O, and phase transitions.

This is the backbone script that the SKILL.md orchestrator calls between phases.
Each session gets a timestamped directory under /tmp/debate-sessions/ (e.g.
/tmp/debate-sessions/debate-20260304-143022/). A symlink at /tmp/debate-session
always points to the latest session. Previous sessions are preserved.

Provides utilities for the prompt-relay architecture (from Mysti: no direct
agent-to-agent communication).

Usage:
    python3 debate_orchestrator.py init <query>
    python3 debate_orchestrator.py detect-domain <query>
    python3 debate_orchestrator.py select-personas <domain>
    python3 debate_orchestrator.py summarize-research
    python3 debate_orchestrator.py check-duplicates
    python3 debate_orchestrator.py format-debate-context <round> <agent_id>
    python3 debate_orchestrator.py assess-convergence <round>
    python3 debate_orchestrator.py format-private-pairs <round>
    python3 debate_orchestrator.py format-judge-input
    python3 debate_orchestrator.py compile-synthesis
    python3 debate_orchestrator.py update-state '{"key": "value"}'
    python3 debate_orchestrator.py status
"""

import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

DEBATE_BASE = Path("/tmp/debate-sessions")
SYMLINK_PATH = Path("/tmp/debate-session")  # always points to latest session


def _resolve_session_dir() -> Path:
    """Resolve current session directory from symlink or create base."""
    if SYMLINK_PATH.is_symlink():
        return SYMLINK_PATH.resolve()
    if SYMLINK_PATH.is_dir():
        return SYMLINK_PATH
    return DEBATE_BASE / "no-session"


SESSION_DIR = _resolve_session_dir()
STATE_FILE = SESSION_DIR / "state.json"

MAX_CONTEXT_CHARS = 12000
MAX_PER_AGENT_CHARS = 2000
MIN_PER_AGENT_CHARS = 500

# Agreement intensity suffixes (from DebateLLM google_ma_debate.yaml, L534-583)
# Level 0-10 scale; level 9 is empirically optimal (90% deference)
AGREEMENT_INTENSITY = {
    0: "These are the opinions of other agents. You completely disagree with all of them.",
    1: "These are the opinions of other agents. You hardly consider these opinions.",
    2: "These are the opinions of other agents. You barely consider these opinions, with very strong reservations.",
    3: "These are the opinions of other agents. You are skeptical of these opinions, with very strong reservations.",
    4: "These are the opinions of other agents. You consider these opinions with strong reservations.",
    5: "These are the opinions of other agents. You consider these opinions with some reservations.",
    6: "You incorporate other agents' evidence 60% of the time and have reservations. Using their positions as additional perspective, provide your updated position.",
    7: "You incorporate other agents' evidence 70% of the time and have some reservations. Using their positions as additional perspective, provide your updated position.",
    8: "You incorporate other agents' evidence 80% of the time and have few reservations. Using their positions as additional perspective, provide your updated position.",
    9: "You incorporate other agents' evidence 90% of the time and have almost no reservations. Using their positions as additional perspective, provide your updated position.",
    10: "You fully incorporate other agents' evidence. Using their positions, provide your updated position.",
}
DEFAULT_AGREEMENT_INTENSITY = 9


# Domain detection keywords
DOMAIN_KEYWORDS = {
    "health": ["pain", "ergonomic", "posture", "health", "medical", "therapy",
               "back", "joint", "sleep", "lumbar", "support", "orthopedic",
               "spine", "comfort", "relief", "wellness", "muscle"],
    "technology": ["computer", "phone", "keyboard", "monitor", "laptop", "gaming",
                   "processor", "wireless", "bluetooth", "usb", "mechanical",
                   "programming", "coding", "developer", "screen", "display",
                   "headphone", "speaker", "audio", "microphone", "camera"],
    "home": ["sofa", "chair", "desk", "mattress", "furniture", "room", "home",
             "kitchen", "bed", "couch", "table", "shelf", "storage", "office",
             "standing desk", "recliner", "sectional", "loveseat"],
    "consumer": ["buy", "best", "review", "product", "brand", "quality",
                 "price", "compare", "recommendation", "top", "rated",
                 "worth", "value", "alternative", "vs"],
}

# Persona sets per domain (from personas.md)
PERSONA_SETS = {
    "health": [
        ("Medical Professional", "You are a medical professional with clinical experience. You evaluate health products and claims based on peer-reviewed research, clinical trials, and evidence-based medicine. You cite PubMed studies and medical guidelines."),
        ("Ergonomics Specialist", "You are an ergonomics specialist who evaluates products for their impact on physical health, posture, and long-term musculoskeletal wellbeing. You reference biomechanical studies and occupational health standards."),
        ("Patient Advocate", "You are a patient advocate who has reviewed thousands of patient experiences with health-related products. You understand real-world usage patterns, compliance challenges, and accessibility needs."),
        ("Budget Strategist", "You are a financial analyst specializing in consumer purchases. You evaluate total cost of ownership, price-to-value ratios, warranty terms, resale value, and hidden costs. You reference price history data and market trends."),
        ("Contrarian Reviewer", "You are a critical reviewer who stress-tests popular recommendations. You actively look for overlooked flaws, astroturfed reviews, survivorship bias in testimonials, and marketing claims that don't hold up to scrutiny."),
    ],
    "technology": [
        ("Hardware Engineer", "You are a hardware engineer who evaluates electronic products based on component quality, thermal design, power efficiency, and manufacturing standards. You reference spec sheets, benchmark data, and teardown analyses."),
        ("Software/UX Analyst", "You are a software and user experience analyst. You evaluate technology products based on software quality, ecosystem integration, update history, and day-to-day usability. You reference long-term reviews and software changelogs."),
        ("Power User", "You are a power user and enthusiast who has extensively tested products in the category. You know the edge cases, the hidden settings, the community mods, and the real-world performance that differs from marketing claims."),
        ("Budget Strategist", "You are a financial analyst specializing in consumer purchases. You evaluate total cost of ownership, price-to-value ratios, warranty terms, resale value, and hidden costs. You reference price history data and market trends."),
        ("Contrarian Reviewer", "You are a critical reviewer who stress-tests popular recommendations. You actively look for overlooked flaws, astroturfed reviews, survivorship bias in testimonials, and marketing claims that don't hold up to scrutiny."),
    ],
    "home": [
        ("Materials Scientist", "You are a materials scientist who evaluates products based on material composition, durability testing, chemical safety, and manufacturing quality. You reference ASTM standards, BIFMA certifications, and material data sheets."),
        ("Interior Design Professional", "You are an interior designer with experience selecting furniture and home products for diverse clients. You evaluate aesthetics, space efficiency, style versatility, and how products integrate into real living spaces."),
        ("Comfort Specialist", "You are a comfort and ergonomics specialist for home furnishings. You evaluate support, firmness, material breathability, and long-term comfort based on body mechanics and material science."),
        ("Budget Strategist", "You are a financial analyst specializing in consumer purchases. You evaluate total cost of ownership, price-to-value ratios, warranty terms, resale value, and hidden costs. You reference price history data and market trends."),
        ("Contrarian Reviewer", "You are a critical reviewer who stress-tests popular recommendations. You actively look for overlooked flaws, astroturfed reviews, survivorship bias in testimonials, and marketing claims that don't hold up to scrutiny."),
    ],
    "consumer": [
        ("Product Analyst", "You are a product analyst specializing in consumer goods. You evaluate products based on build quality, materials, durability, and value for money. You reference teardown analyses, lab testing data, and manufacturer specs."),
        ("Domain Expert", "You are a domain expert for the product category in question. You have deep knowledge of the technical specifications, industry standards, and performance benchmarks that matter most. You cite specific measurements and test results."),
        ("User Experience Researcher", "You are a UX researcher who synthesizes real user feedback at scale. You analyze review patterns across platforms (Amazon, Reddit, specialized forums), identify common complaints and praise points, and weight feedback by reviewer credibility."),
        ("Budget Strategist", "You are a financial analyst specializing in consumer purchases. You evaluate total cost of ownership, price-to-value ratios, warranty terms, resale value, and hidden costs. You reference price history data and market trends."),
        ("Contrarian Reviewer", "You are a critical reviewer who stress-tests popular recommendations. You actively look for overlooked flaws, astroturfed reviews, survivorship bias in testimonials, and marketing claims that don't hold up to scrutiny."),
    ],
    "general": [
        ("Generalist Researcher", "You are a thorough generalist researcher. You approach topics with intellectual curiosity and methodical rigor, cross-referencing multiple authoritative sources."),
        ("Domain Expert", "You are a domain expert for the product category in question. Adapt your expertise to the specific domain of the query."),
        ("User Experience Researcher", "You are a UX researcher who synthesizes real user feedback at scale. You analyze review patterns across platforms (Amazon, Reddit, specialized forums), identify common complaints and praise points, and weight feedback by reviewer credibility."),
        ("Budget Strategist", "You are a financial analyst specializing in consumer purchases. You evaluate total cost of ownership, price-to-value ratios, warranty terms, resale value, and hidden costs. You reference price history data and market trends."),
        ("Contrarian Reviewer", "You are a critical reviewer who stress-tests popular recommendations. You actively look for overlooked flaws, astroturfed reviews, survivorship bias in testimonials, and marketing claims that don't hold up to scrutiny."),
    ],
}


def init_session(query: str) -> dict:
    """Initialize a new debate session with timestamped directory."""
    global SESSION_DIR, STATE_FILE

    # Create timestamped session directory (preserves previous sessions)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    SESSION_DIR = DEBATE_BASE / f"debate-{timestamp}"
    STATE_FILE = SESSION_DIR / "state.json"

    DEBATE_BASE.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    for subdir in ["phase1", "phase2", "phase3", "phase4", "phase5", "phase6"]:
        (SESSION_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # Update symlink to point to latest session
    if SYMLINK_PATH.is_symlink():
        SYMLINK_PATH.unlink()
    elif SYMLINK_PATH.exists():
        import shutil
        shutil.rmtree(SYMLINK_PATH)
    SYMLINK_PATH.symlink_to(SESSION_DIR)

    state = {
        "query": query,
        "domain": detect_domain(query),
        "session_dir": str(SESSION_DIR),
        "created_at": datetime.now().isoformat(),
        "phase": "initialized",
        "agents": [],
        "products": {},
        "eliminated": [],
        "finalists": [],
        "winner": None,
        "runner_up": None,
        "cumulative_votes": {},
        "convergence_history": [],
        "agreement_intensity": DEFAULT_AGREEMENT_INTENSITY,
    }

    STATE_FILE.write_text(json.dumps(state, indent=2))
    return state


def detect_domain(query: str) -> str:
    """Detect query domain from keywords."""
    query_lower = query.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in query_lower)

    if not any(scores.values()):
        return "general"

    return max(scores, key=scores.get)


def select_personas(domain: str) -> list[dict]:
    """Select 5 personas for the detected domain."""
    persona_set = PERSONA_SETS.get(domain, PERSONA_SETS["general"])
    return [{"name": name, "description": desc, "agent_id": i + 1}
            for i, (name, desc) in enumerate(persona_set)]


def get_state() -> dict:
    """Load current session state."""
    if not STATE_FILE.exists():
        return {"error": "No active session. Run 'init' first."}
    return json.loads(STATE_FILE.read_text())


def update_state(updates: dict) -> dict:
    """Update session state."""
    state = get_state()
    state.update(updates)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    return state


def summarize_research() -> dict:
    """Summarize Phase 1 research results — extract all product picks."""
    phase1_dir = SESSION_DIR / "phase1"
    agent_files = sorted(phase1_dir.glob("agent-*.md"))

    all_products = {}
    per_agent = {}

    for f in agent_files:
        text = f.read_text()
        agent_id = f.stem

        # Extract product names from headers like "### 1. Product Name" or "**Name**: Product"
        picks = []
        name_patterns = [
            re.compile(r'###\s*\d+\.\s*(.+)', re.MULTILINE),
            re.compile(r'\*?\*?Name\*?\*?[:\s]+(.+)', re.MULTILINE),
            re.compile(r'##\s*(?:Top Pick|Pick)\s*\d*[:\s]*(.+)', re.MULTILINE),
        ]
        for pattern in name_patterns:
            matches = pattern.findall(text)
            picks.extend([m.strip().strip('*') for m in matches])

        per_agent[agent_id] = picks
        for p in picks:
            normalized = p.lower().strip()
            if normalized not in all_products:
                all_products[normalized] = {"name": p, "mentioned_by": []}
            all_products[normalized]["mentioned_by"].append(agent_id)

    return {
        "total_unique_products": len(all_products),
        "products": all_products,
        "per_agent": per_agent,
    }


def _normalize_product(name: str) -> str:
    """Normalize a product name for comparison.
    Strips markdown, extra whitespace, and common suffixes."""
    name = re.sub(r'\*+', '', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    for suffix in [' mattress', ' sofa', ' chair', ' bed', ' headphones']:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    return name


def _is_fuzzy_match(a: str, b: str) -> bool:
    """Check if two product names are likely the same product.
    Uses containment check and word overlap threshold."""
    na, nb = _normalize_product(a), _normalize_product(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    words_a = set(na.split())
    words_b = set(nb.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap >= 0.7


def check_duplicates() -> dict:
    """Check Phase 2 opening statements for duplicate product picks.
    Uses fuzzy matching to catch near-duplicates like
    'Sony WH-1000XM5' vs 'Sony WH-1000XM5 Headphones'."""
    phase2_dir = SESSION_DIR / "phase2"
    files = sorted(phase2_dir.glob("agent-*-opening.md"))

    sys.path.insert(0, str(Path(__file__).parent))
    from convergence_detector import extract_position

    picks = {}
    for f in files:
        text = f.read_text()
        agent_id = f.stem
        position = extract_position(text)
        picks[agent_id] = position

    seen = {}
    duplicates = []
    for agent_id, pick in picks.items():
        matched = False
        for seen_pick, seen_agent in seen.items():
            if _is_fuzzy_match(pick, seen_pick):
                duplicates.append({
                    "agent": agent_id,
                    "pick": pick,
                    "conflicts_with": seen_agent,
                    "matched_pick": seen_pick,
                })
                matched = True
                break
        if not matched:
            seen[pick] = agent_id

    return {
        "picks": picks,
        "duplicates": duplicates,
        "has_duplicates": len(duplicates) > 0,
    }


def truncate_to_budget(text: str, max_chars: int) -> str:
    """
    Truncate text to budget, preserving structure.
    Inspired by debatellm's concept of context overflow management, but uses a
    different technique: proactive paragraph-level truncation (keep first + last,
    trim middle) vs debatellm's reactive pop-on-error retry loop.
    """
    if len(text) <= max_chars:
        return text

    paragraphs = text.split("\n\n")
    if len(paragraphs) <= 2:
        return text[:max_chars] + "\n[... truncated for context budget ...]"

    first = paragraphs[0]
    last = paragraphs[-1]
    middle = paragraphs[1:-1]

    result = first + "\n\n"
    remaining = max_chars - len(first) - len(last) - 60

    for para in middle:
        if remaining <= 0:
            result += "[... middle sections trimmed for context budget ...]\n\n"
            break
        if len(para) <= remaining:
            result += para + "\n\n"
            remaining -= len(para) + 2
        else:
            result += para[:remaining] + "...\n\n"
            remaining = 0

    result += last
    return result


def format_debate_context(round_num: int, agent_id: int) -> str:
    """
    Format the full context an agent sees for a debate round.
    Dense topology: all agents see all other agents' responses.
    Adapted from debate-or-vote get_new_message() (analysis.md:322-383).

    Context overflow management (from debatellm Innovation 5):
    Progressive truncation — preserve system prompt, trim oldest content first.
    Total context budget: MAX_CONTEXT_CHARS. Per-agent budget computed dynamically.
    """
    state = get_state()

    if round_num == 1:
        source_dir = SESSION_DIR / "phase2"
        pattern = "agent-*-opening.md"
    else:
        source_dir = SESSION_DIR / "phase3" / f"round-{round_num - 1}"
        pattern = "agent-*.md"

    responses = {}
    for f in sorted(source_dir.glob(pattern)):
        responses[f.stem] = f.read_text()

    own_key = f"agent-{agent_id}" if round_num > 1 else f"agent-{agent_id}-opening"

    other_items = [(k, v) for k, v in responses.items()
                   if k != own_key and str(agent_id) not in k]
    random.shuffle(other_items)

    own_response = responses.get(own_key, "")

    num_others = len(other_items)
    suffix_budget = 300
    own_budget = min(MAX_PER_AGENT_CHARS, MAX_CONTEXT_CHARS // 4)
    remaining_budget = MAX_CONTEXT_CHARS - suffix_budget - own_budget
    per_agent_budget = max(
        MIN_PER_AGENT_CHARS,
        remaining_budget // max(num_others, 1),
    )

    context_parts = [
        "These are the recent positions from other agents:\n",
    ]

    for key, response in other_items:
        truncated = truncate_to_budget(response, per_agent_budget)
        context_parts.append(f"One agent's position:\n```\n{truncated}\n```\n")

    if own_response:
        own_truncated = truncate_to_budget(own_response, own_budget)
        context_parts.append(
            f"This was your most recent position:\n```\n{own_truncated}\n```\n"
        )

    # Include private channel notes if they exist
    private_dir = SESSION_DIR / "phase3" / f"round-{round_num}" / "private"
    if private_dir.exists():
        private_files = sorted(private_dir.glob(f"*-to-agent-{agent_id}.md")) + \
                        sorted(private_dir.glob(f"agent-{agent_id}-to-*.md"))
        if private_files:
            context_parts.append("\n## Private Deliberation Notes (only you see these):\n")
            for pf in private_files:
                note = truncate_to_budget(pf.read_text(), MIN_PER_AGENT_CHARS)
                context_parts.append(f"```\n{note}\n```\n")

    intensity = state.get("agreement_intensity", DEFAULT_AGREEMENT_INTENSITY)
    suffix = AGREEMENT_INTENSITY.get(intensity, AGREEMENT_INTENSITY[DEFAULT_AGREEMENT_INTENSITY])
    context_parts.append(
        f"\n{suffix}\n"
        f"Provide your updated position on the query:\n{state['query']}"
    )

    return "\n".join(context_parts)


def format_judge_input() -> dict:
    """
    Format input for the 2-step judge.
    Step 1 uses opening statement evidence (first-round, from MAD memory_lst[2]).
    Step 2 uses both opening and final round evidence.
    """
    state = get_state()

    # Get opening statements (first-round evidence, before groupthink)
    opening_dir = SESSION_DIR / "phase2"
    openings = {}
    for f in sorted(opening_dir.glob("agent-*-opening.md")):
        openings[f.stem] = f.read_text()

    # Get finalist products from state
    finalists = state.get("finalists", [])

    # Get final debate round
    phase5_dir = SESSION_DIR / "phase5"
    finals = {}
    for f in sorted(phase5_dir.glob("finals-agent-*.md")):
        finals[f.stem] = f.read_text()

    return {
        "query": state["query"],
        "finalists": finalists,
        "opening_evidence": openings,
        "final_evidence": finals,
    }


def compile_synthesis() -> dict:
    """Gather all evidence needed for Phase 6 synthesis."""
    state = get_state()

    # Collect from all phases
    evidence = {
        "query": state["query"],
        "winner": state.get("winner"),
        "runner_up": state.get("runner_up"),
        "eliminated": state.get("eliminated", []),
        "convergence_history": state.get("convergence_history", []),
    }

    # Phase 1 research summaries (truncated)
    phase1_dir = SESSION_DIR / "phase1"
    evidence["research"] = {}
    for f in sorted(phase1_dir.glob("agent-*.md")):
        evidence["research"][f.stem] = f.read_text()[:3000]

    # Phase 4 elimination rationale (check all rounds)
    evidence["elimination_details"] = []
    for elim_file in sorted((SESSION_DIR / "phase4").rglob("elimination-results.json")):
        evidence["elimination_details"].append(json.loads(elim_file.read_text()))

    # Phase 5 judge verdict
    verdict_file = SESSION_DIR / "phase5" / "final-verdict.md"
    if verdict_file.exists():
        evidence["judge_verdict"] = verdict_file.read_text()

    # Jury validation
    jury_files = sorted((SESSION_DIR / "phase5").glob("jury-*.md"))
    evidence["jury_validations"] = [f.read_text() for f in jury_files]

    return evidence


def assess_convergence_wrapper(round_num: int) -> dict:
    """
    Wrapper that calls convergence_detector and saves results to state.
    Delegates to convergence_detector.py for the actual analysis.
    """
    round_dir = SESSION_DIR / "phase3" / f"round-{round_num}"
    if not round_dir.exists():
        return {"error": f"Round directory not found: {round_dir}"}

    sys.path.insert(0, str(Path(__file__).parent))
    from convergence_detector import assess_convergence

    result = assess_convergence(str(round_dir))

    output_path = SESSION_DIR / "phase3" / f"convergence-round-{round_num}.json"
    output_path.write_text(json.dumps(result, indent=2))

    state = get_state()
    history = state.get("convergence_history", [])
    history.append({
        "round": round_num,
        "recommendation": result.get("recommendation", "unknown"),
        "overall_convergence": result.get("overall_convergence", 0),
        "agreement_ratio": result.get("agreement_ratio", 0),
        "avg_stability": result.get("avg_stability", 0),
    })
    update_state({"convergence_history": history, "phase": f"phase3-round-{round_num}"})

    return result


def format_private_pairs(round_num: int) -> list[dict]:
    """
    Generate agent pairings for private deliberation channel.
    From elimination_game's dual channel (analysis.md:914-949).

    Each agent is paired with 1-2 others for private critique exchange.
    Uses round-robin pairing to ensure all agents interact privately.
    """
    state = get_state()
    agents = state.get("agents", [])
    num_agents = len(agents) if agents else 5

    pairs = []
    for i in range(1, num_agents + 1):
        partner = ((i - 1 + round_num) % num_agents) + 1
        if partner != i:
            pair = tuple(sorted([i, partner]))
            if pair not in [(p["agent_a"], p["agent_b"]) for p in pairs]:
                pairs.append({"agent_a": pair[0], "agent_b": pair[1]})

    private_dir = SESSION_DIR / "phase3" / f"round-{round_num}" / "private"
    private_dir.mkdir(parents=True, exist_ok=True)

    return pairs


def print_status():
    """Print current session status."""
    state = get_state()
    if "error" in state:
        print(state["error"])
        return

    print(f"Query: {state['query']}")
    print(f"Domain: {state['domain']}")
    print(f"Phase: {state['phase']}")
    print(f"Created: {state['created_at']}")
    if state.get('agents'):
        print(f"Agents: {len(state['agents'])}")
    if state.get('products'):
        print(f"Products tracked: {len(state['products'])}")
    if state.get('eliminated'):
        print(f"Eliminated: {state['eliminated']}")
    if state.get('finalists'):
        print(f"Finalists: {state['finalists']}")
    if state.get('winner'):
        print(f"Winner: {state['winner']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        query = " ".join(sys.argv[2:])
        result = init_session(query)
        print(json.dumps(result, indent=2))

    elif command == "detect-domain":
        query = " ".join(sys.argv[2:])
        domain = detect_domain(query)
        print(json.dumps({"query": query, "domain": domain}))

    elif command == "select-personas":
        domain = sys.argv[2] if len(sys.argv) > 2 else "general"
        personas = select_personas(domain)
        print(json.dumps(personas, indent=2))

    elif command == "summarize-research":
        result = summarize_research()
        print(json.dumps(result, indent=2))

    elif command == "check-duplicates":
        result = check_duplicates()
        print(json.dumps(result, indent=2))

    elif command == "format-debate-context":
        round_num = int(sys.argv[2])
        agent_id = int(sys.argv[3])
        context = format_debate_context(round_num, agent_id)
        print(context)

    elif command == "assess-convergence":
        round_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        result = assess_convergence_wrapper(round_num)
        print(json.dumps(result, indent=2))
        rec = result.get("recommendation", "continue")
        if rec == "converged":
            sys.exit(0)
        elif rec == "stalled":
            sys.exit(2)
        else:
            sys.exit(1)

    elif command == "format-private-pairs":
        round_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        pairs = format_private_pairs(round_num)
        print(json.dumps(pairs, indent=2))

    elif command == "format-judge-input":
        result = format_judge_input()
        print(json.dumps(result, indent=2))

    elif command == "compile-synthesis":
        result = compile_synthesis()
        (SESSION_DIR / "phase6" / "evidence.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({"status": "compiled", "keys": list(result.keys())}))

    elif command == "update-state":
        if len(sys.argv) < 3:
            print("Usage: update-state '{\"key\": \"value\"}'")
            sys.exit(1)
        updates = json.loads(sys.argv[2])
        result = update_state(updates)
        print(json.dumps({"status": "updated", "phase": result.get("phase", "unknown")}))

    elif command == "status":
        print_status()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
