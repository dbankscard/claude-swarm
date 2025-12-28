#!/usr/bin/env python3
"""
Example: Multi-agent code review.

Each agent reviews from their specialty, then results are synthesized.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_swarm import Swarm


async def code_review(target_path: str, state_file: str = ".review_swarm.json"):
    """Run a multi-perspective code review."""
    
    # Create or load swarm
    if Path(state_file).exists():
        swarm = Swarm.load(state_file)
    else:
        swarm = Swarm(max_concurrent=4)
        
        swarm.add_agent(
            "architecture",
            "software architect",
            "Review for design patterns, SOLID principles, modularity, and maintainability.",
        )
        swarm.add_agent(
            "security",
            "security engineer", 
            "Review for vulnerabilities, injection risks, auth issues, and data exposure.",
        )
        swarm.add_agent(
            "performance",
            "performance engineer",
            "Review for bottlenecks, N+1 queries, memory leaks, and scalability issues.",
        )
        swarm.add_agent(
            "quality",
            "code quality specialist",
            "Review for readability, testing, error handling, and documentation.",
        )
    
    swarm.update_context("review_target", target_path)
    
    # Each agent reviews from their perspective
    task = f"Review the code in {target_path}. Provide specific findings with file paths and line numbers where applicable."
    
    print(f"Starting code review of {target_path}...")
    print("Dispatching to agents:", [a["name"] for a in swarm.list_agents()])
    
    results = await swarm.broadcast(task)
    
    # Synthesize findings
    synthesis_prompt = f"""You are a lead engineer synthesizing code review feedback.

## Target
{target_path}

## Agent Reviews
{json.dumps(results, indent=2)}

Create a prioritized summary:
1. Critical issues (must fix)
2. Important improvements (should fix)
3. Minor suggestions (nice to have)

For each item, note which agent(s) identified it."""

    synthesis = await swarm.run_prompt(synthesis_prompt)
    
    swarm.save(state_file)
    
    return {
        "target": target_path,
        "agent_reviews": results,
        "synthesis": synthesis,
    }


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-agent code review")
    parser.add_argument("path", help="Path to review (file or directory)")
    parser.add_argument("--state-file", default=".review_swarm.json")
    args = parser.parse_args()
    
    result = await code_review(args.path, args.state_file)
    
    print("\n" + "=" * 60)
    print("SYNTHESIS")
    print("=" * 60)
    print(json.dumps(result["synthesis"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
