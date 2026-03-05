#!/usr/bin/env python3
"""
Convergence detection for multi-agent debate rounds.
Adapted from Mysti's _assessConvergence() (BrainstormManager.ts:1462-1527)
and _calculateTextSimilarity() (BrainstormManager.ts:1532-1545).

Usage:
    python3 convergence_detector.py /tmp/debate-session/phase3/round-{R}/

Reads all agent-*.md files in the directory. If a previous round exists
(round-{R-1}/), computes position stability. Outputs JSON convergence metrics.
"""

import json
import os
import re
import sys
from pathlib import Path


# Agreement signal patterns (from Mysti BrainstormManager.ts:1462-1527)
AGREE_PATTERNS = [
    re.compile(r'\bagree\b', re.IGNORECASE),
    re.compile(r'\bconcede\b', re.IGNORECASE),
    re.compile(r'\bvalid point\b', re.IGNORECASE),
    re.compile(r'\bcorrect\b', re.IGNORECASE),
    re.compile(r'\baccept\b', re.IGNORECASE),
    re.compile(r'\bwell-taken\b', re.IGNORECASE),
    re.compile(r'\bconvinc(?:ed|ing)\b', re.IGNORECASE),
    re.compile(r'\byou\'re right\b', re.IGNORECASE),
    re.compile(r'\bstrong evidence\b', re.IGNORECASE),
    re.compile(r'\bwell supported\b', re.IGNORECASE),
]

DISAGREE_PATTERNS = [
    re.compile(r'\bdisagree\b', re.IGNORECASE),
    re.compile(r'\bhowever\b', re.IGNORECASE),
    re.compile(r'\bincorrect\b', re.IGNORECASE),
    re.compile(r'\bwrong\b', re.IGNORECASE),
    re.compile(r'\breject\b', re.IGNORECASE),
    re.compile(r'\bmaintain\b', re.IGNORECASE),
    re.compile(r'\bdefend\b', re.IGNORECASE),
    re.compile(r'\boverlooked\b', re.IGNORECASE),
    re.compile(r'\bflawed\b', re.IGNORECASE),
    re.compile(r'\binsufficient\b', re.IGNORECASE),
]


def calculate_text_similarity(text_a: str, text_b: str) -> float:
    """
    Max-normalized word overlap (Jaccard-like).
    From Mysti BrainstormManager.ts:1532-1545.
    Filters words to length > 3 (stop-word removal).
    """
    words_a = set(w for w in text_a.lower().split() if len(w) > 3)
    words_b = set(w for w in text_b.lower().split() if len(w) > 3)

    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0

    intersection = len(words_a & words_b)
    return intersection / max(len(words_a), len(words_b))


def count_signals(text: str, patterns: list[re.Pattern]) -> int:
    """Count total regex matches across all patterns in text."""
    count = 0
    for pattern in patterns:
        count += len(pattern.findall(text))
    return count


def extract_position(text: str) -> str:
    """Extract the product pick from an agent's response.
    Looks for 'My Pick:', 'PICK:', 'recommend', 'champion' patterns.
    Handles markdown bold formatting like **My Pick**: **Product Name**."""
    pick_patterns = [
        re.compile(r'\*{0,2}(?:My Pick|PICK|Winner)\*{0,2}\s*:\s*\*{0,2}(.+?)\*{0,2}\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'\b(?:recommend|champion)\s*:\s*\*{0,2}(.+?)\*{0,2}\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'I (?:still )?(?:support|recommend|pick|choose|advocate)\s+\*{0,2}(.+?)\*{0,2}\s*$', re.IGNORECASE | re.MULTILINE),
    ]
    for pattern in pick_patterns:
        match = pattern.search(text)
        if match:
            result = match.group(1).strip().strip('*').strip()
            return result
    return ""


def extract_facilitator_score(round_dir: str) -> float | None:
    """
    Extract Delphi facilitator convergence score if a facilitator summary exists.
    From Mysti BrainstormManager.ts:735-741.

    Looks for "Convergence Score: N/10" in a facilitator summary file.
    When present, this score overrides the heuristic convergence calculation.
    """
    facilitator_file = Path(round_dir) / "facilitator-summary.md"
    if not facilitator_file.exists():
        return None

    text = facilitator_file.read_text()
    score_match = re.search(r'Convergence Score:\s*(\d+)\s*/\s*10', text, re.IGNORECASE)
    if score_match:
        return int(score_match.group(1)) / 10.0
    return None


FACILITATOR_PROMPT = """You are a Delphi facilitator summarizing the current state of a multi-agent debate.

Review all agents' positions from this round and produce:

## Consensus Points
- **Strong confidence**: [points all agents agree on]
- **Moderate confidence**: [points most agents agree on]
- **Tentative**: [points with slight majority]

## Divergence Points
- **Position A**: [description] — held by [agents]
- **Position B**: [description] — held by [agents]
- **Key tension**: [what drives the disagreement]

## Open Questions
- [evidence gaps or unresolved points]

## Convergence Score: ?/10

(0 = total disagreement, 5 = split positions, 7 = emerging consensus, 10 = full agreement)
"""


def assess_convergence(round_dir: str) -> dict:
    """
    Assess convergence for a debate round.
    Adapted from Mysti _assessConvergence() with product-debate extensions.

    Returns dict with:
        - agreement_count, disagreement_count, agreement_ratio
        - avg_stability (if previous round exists)
        - overall_convergence = (agreement_ratio * 0.6) + (avg_stability * 0.4)
        - facilitator_score (if facilitator summary exists, overrides heuristic)
        - recommendation: 'continue' | 'converged' | 'stalled'
        - per_agent positions and stability scores
    """
    round_path = Path(round_dir)
    agent_files = sorted(round_path.glob('agent-*.md'))

    if not agent_files:
        return {"error": f"No agent files found in {round_dir}"}

    # Read current round responses
    current_responses = {}
    for f in agent_files:
        agent_id = f.stem  # e.g. "agent-1"
        current_responses[agent_id] = f.read_text()

    # Count agreement/disagreement signals across all responses
    total_agree = 0
    total_disagree = 0
    per_agent_signals = {}

    for agent_id, text in current_responses.items():
        agree = count_signals(text, AGREE_PATTERNS)
        disagree = count_signals(text, DISAGREE_PATTERNS)
        total_agree += agree
        total_disagree += disagree
        per_agent_signals[agent_id] = {
            "agreement_signals": agree,
            "disagreement_signals": disagree,
            "position": extract_position(text),
        }

    # Agreement ratio (from Mysti: agreementCount / total, default 0.5)
    total = total_agree + total_disagree
    agreement_ratio = total_agree / total if total > 0 else 0.5

    # Position stability: compare with previous round
    avg_stability = 0.5  # default when no previous round
    per_agent_stability = {}

    # Infer round number from directory name
    round_match = re.search(r'round-(\d+)', round_path.name)
    if round_match:
        round_num = int(round_match.group(1))
        prev_dir = round_path.parent / f"round-{round_num - 1}"
        if prev_dir.exists():
            prev_files = {f.stem: f.read_text() for f in sorted(prev_dir.glob('agent-*.md'))}
            stability_values = []
            for agent_id, current_text in current_responses.items():
                if agent_id in prev_files:
                    sim = calculate_text_similarity(prev_files[agent_id], current_text)
                    per_agent_stability[agent_id] = sim
                    stability_values.append(sim)
            if stability_values:
                avg_stability = sum(stability_values) / len(stability_values)

    # Weighted convergence score (from Mysti)
    overall_convergence = (agreement_ratio * 0.6) + (avg_stability * 0.4)

    # Delphi facilitator score override (from Mysti BrainstormManager.ts:735-741)
    facilitator_score = extract_facilitator_score(round_dir)
    if facilitator_score is not None:
        overall_convergence = facilitator_score

    # Recommendation logic (from Mysti thresholds)
    recommendation = 'continue'
    if facilitator_score is not None and facilitator_score >= 0.7:
        recommendation = 'converged'
    elif agreement_ratio >= 0.7 and avg_stability >= 0.8:
        recommendation = 'converged'
    elif round_match and int(round_match.group(1)) >= 2:
        # Check for stalling: not improving + unstable
        prev_convergence_file = round_path.parent / f"convergence-round-{int(round_match.group(1)) - 1}.json"
        if prev_convergence_file.exists():
            prev_data = json.loads(prev_convergence_file.read_text())
            prev_overall = prev_data.get("overall_convergence", 0)
            if prev_overall >= overall_convergence and avg_stability < 0.3:
                recommendation = 'stalled'

    # Check if agents converged on the same product
    positions = [s["position"] for s in per_agent_signals.values() if s["position"]]
    unique_positions = len(set(p.lower().strip() for p in positions if p))
    position_convergence = 1.0 / unique_positions if unique_positions > 0 else 0.0

    result = {
        "agreement_count": total_agree,
        "disagreement_count": total_disagree,
        "agreement_ratio": round(agreement_ratio, 3),
        "avg_stability": round(avg_stability, 3),
        "overall_convergence": round(overall_convergence, 3),
        "facilitator_score": facilitator_score,
        "position_convergence": round(position_convergence, 3),
        "unique_positions": unique_positions,
        "recommendation": recommendation,
        "per_agent": per_agent_signals,
        "per_agent_stability": per_agent_stability,
    }

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 convergence_detector.py <round_directory>")
        sys.exit(1)

    round_dir = sys.argv[1]
    result = assess_convergence(round_dir)

    # Write JSON output
    output_path = Path(round_dir).parent / f"convergence-{Path(round_dir).name}.json"
    output_path.write_text(json.dumps(result, indent=2))

    # Also print summary
    print(json.dumps(result, indent=2))

    if result.get("recommendation") == "converged":
        print(f"\n>>> CONVERGED (agreement={result['agreement_ratio']}, stability={result['avg_stability']})")
        sys.exit(0)
    elif result.get("recommendation") == "stalled":
        print(f"\n>>> STALLED (agreement={result['agreement_ratio']}, stability={result['avg_stability']})")
        sys.exit(2)
    else:
        print(f"\n>>> CONTINUE (agreement={result['agreement_ratio']}, stability={result['avg_stability']})")
        sys.exit(1)
