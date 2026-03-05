#!/usr/bin/env python3
"""
Vote tallying and elimination logic for adversarial debate.
Adapted from elimination_game's voting.py and elimination.py
(reconstructed from log patterns, analysis.md lines 785-884).

Usage:
    python3 vote_tallier.py /tmp/debate-session/phase4/

Reads vote-agent-*.md files, extracts ELIMINATE targets, tallies votes,
applies 4-step tie-break chain, outputs elimination results.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path


def extract_vote(text: str) -> dict:
    """Extract vote target and reasoning from agent vote file.

    Expected format in vote files:
    **ELIMINATE**: [Product Name]
    **Reasoning**: [text]
    **Confidence**: [LOW/MEDIUM/HIGH]
    """
    result = {"target": None, "reasoning": "", "confidence": "MEDIUM"}

    # Extract target
    target_patterns = [
        re.compile(r'\*?\*?ELIMINATE\*?\*?[:\s]+\*?\*?([^\n*]+)', re.IGNORECASE),
        re.compile(r'(?:vote to eliminate|eliminate|my vote)[:\s]+\*?\*?([^\n*]+)', re.IGNORECASE),
        re.compile(r'(?:weakest|worst)[:\s]+\*?\*?([^\n*]+)', re.IGNORECASE),
    ]
    for pattern in target_patterns:
        match = pattern.search(text)
        if match:
            result["target"] = match.group(1).strip().strip('*').strip()
            break

    # Extract reasoning
    reason_match = re.search(r'\*?\*?Reasoning\*?\*?[:\s]+([^\n]+(?:\n(?!\*\*)[^\n]+)*)', text, re.IGNORECASE)
    if reason_match:
        result["reasoning"] = reason_match.group(1).strip()

    # Extract confidence
    conf_match = re.search(r'\*?\*?Confidence\*?\*?[:\s]+(LOW|MEDIUM|HIGH)', text, re.IGNORECASE)
    if conf_match:
        result["confidence"] = conf_match.group(1).upper()

    return result


def collect_votes(vote_dir: str) -> tuple[dict, dict]:
    """
    Read all vote files and tally votes.
    Adapted from elimination_game voting.py (analysis.md:785-807).

    Returns:
        votes: {target_product: vote_count}
        vote_details: {agent_id: {target, reasoning, confidence}}
    """
    vote_path = Path(vote_dir)
    vote_files = sorted(vote_path.glob('vote-agent-*.md'))

    votes = Counter()
    vote_details = {}

    for f in vote_files:
        agent_id = f.stem  # e.g. "vote-agent-1"
        text = f.read_text()
        vote = extract_vote(text)

        if vote["target"]:
            # Normalize product name for counting
            normalized = vote["target"].lower().strip()
            votes[normalized] += 1
            vote_details[agent_id] = {
                "target": vote["target"],
                "target_normalized": normalized,
                "reasoning": vote["reasoning"],
                "confidence": vote["confidence"],
            }
        else:
            vote_details[agent_id] = {
                "target": None,
                "error": "Could not extract vote target from response",
            }

    return dict(votes), vote_details


def resolve_elimination(
    votes: dict,
    vote_details: dict,
    cumulative_votes: dict | None = None,
) -> dict:
    """
    Resolve elimination with 4-step tie-break chain.
    Adapted from elimination_game elimination.py (analysis.md:811-884).

    Tie-break chain:
        1. Plurality — most votes eliminated
        2. Re-vote (simulated: use confidence weighting as proxy)
        3. Cumulative vote check
        4. Random

    Returns dict with eliminated product and metadata.
    """
    if not votes:
        return {"error": "No valid votes cast", "eliminated": None}

    max_votes = max(votes.values())
    leaders = [product for product, count in votes.items() if count == max_votes]

    # Step 1: Clean elimination (no tie)
    if len(leaders) == 1:
        return {
            "eliminated": leaders[0],
            "vote_count": max_votes,
            "total_votes": sum(votes.values()),
            "tie_break": False,
            "method": "plurality",
            "vote_distribution": votes,
        }

    # Step 2: Tie-break via confidence weighting
    # Agents who voted with HIGH confidence get 1.5 weight,
    # MEDIUM gets 1.0, LOW gets 0.5
    confidence_weights = {"HIGH": 1.5, "MEDIUM": 1.0, "LOW": 0.5}
    weighted_votes = Counter()
    for agent_id, detail in vote_details.items():
        if detail.get("target_normalized") in leaders:
            weight = confidence_weights.get(detail.get("confidence", "MEDIUM"), 1.0)
            weighted_votes[detail["target_normalized"]] += weight

    if weighted_votes:
        max_weighted = max(weighted_votes.values())
        weighted_leaders = [p for p, w in weighted_votes.items() if w == max_weighted]
        if len(weighted_leaders) == 1:
            return {
                "eliminated": weighted_leaders[0],
                "vote_count": max_votes,
                "total_votes": sum(votes.values()),
                "tie_break": True,
                "method": "confidence_weighted",
                "vote_distribution": votes,
                "weighted_scores": dict(weighted_votes),
            }
        leaders = weighted_leaders  # narrow down for next step

    # Step 3: Cumulative vote check
    if cumulative_votes:
        cumu_scores = {p: cumulative_votes.get(p, 0) for p in leaders}
        max_cumu = max(cumu_scores.values())
        cumu_leaders = [p for p, c in cumu_scores.items() if c == max_cumu]
        if len(cumu_leaders) == 1:
            return {
                "eliminated": cumu_leaders[0],
                "vote_count": max_votes,
                "total_votes": sum(votes.values()),
                "tie_break": True,
                "method": "cumulative_votes",
                "vote_distribution": votes,
                "cumulative_scores": cumu_scores,
            }
        leaders = cumu_leaders

    # Step 4: Jury tie-breaker required (no random elimination)
    # Returns unresolved tie — orchestrator must spawn a jury agent
    # to hear both sides and make a reasoned decision
    return {
        "eliminated": None,
        "vote_count": max_votes,
        "total_votes": sum(votes.values()),
        "tie_break": True,
        "method": "jury_tiebreak_required",
        "vote_distribution": votes,
        "tied_products": leaders,
    }


def run_elimination(vote_dir: str, cumulative_votes: dict | None = None) -> dict:
    """Full elimination pipeline: collect votes -> resolve -> output."""
    votes, vote_details = collect_votes(vote_dir)
    result = resolve_elimination(votes, vote_details, cumulative_votes)
    result["vote_details"] = vote_details
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 vote_tallier.py <vote_directory> [--cumulative '{json}' | cumulative_votes.json]")
        sys.exit(1)

    vote_dir = sys.argv[1]
    cumulative = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--cumulative" and i + 1 < len(sys.argv):
            cumulative = json.loads(sys.argv[i + 1])
            break
        elif not arg.startswith("--"):
            cumulative = json.loads(Path(arg).read_text())
            break

    result = run_elimination(vote_dir, cumulative)

    # Write result
    output_path = Path(vote_dir) / "elimination-results.json"
    output_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))

    if result.get("method") == "jury_tiebreak_required":
        tied = ", ".join(result["tied_products"])
        print(f"\n>>> TIE — JURY TIEBREAK REQUIRED between: {tied}")
        print(">>> Orchestrator must spawn a jury agent to decide. See judge.md 'Elimination Tie-Breaker Jury' template.")
        sys.exit(2)
    elif result.get("eliminated"):
        print(f"\n>>> ELIMINATED: {result['eliminated']} "
              f"(method: {result['method']}, votes: {result['vote_count']}/{result['total_votes']})")
    else:
        print("\n>>> ERROR: Could not determine elimination")
        sys.exit(1)
