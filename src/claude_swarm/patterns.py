"""Common orchestration patterns for agent swarms."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .swarm import Swarm


async def fan_out(
    tasks: list[str],
    cwd: str = ".",
    max_concurrent: int = 5,
    allowed_tools: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Run multiple independent tasks in parallel.
    
    Each task gets its own Claude instance. Results are returned
    in the same order as the input tasks.
    
    Example:
        results = await fan_out([
            "Analyze ./src/auth for security issues",
            "Review ./src/api error handling",
            "Check ./src/models for N+1 queries",
        ])
    """
    swarm = Swarm(max_concurrent=max_concurrent, cwd=cwd)

    async def run_task(idx: int, task: str) -> dict:
        result = await swarm.run_prompt(task, allowed_tools=allowed_tools)
        return {"index": idx, "task": task, **result}
    
    results = await asyncio.gather(*[
        run_task(i, task) for i, task in enumerate(tasks)
    ])
    
    return sorted(results, key=lambda x: x["index"])


async def pipeline(
    stages: list[str],
    cwd: str = ".",
    context_key: str = "previous_output",
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run tasks sequentially, passing output from each stage to the next.
    
    Each stage receives the output of the previous stage in its context.
    
    Example:
        result = await pipeline([
            "Draft a Python CLI for file encryption",
            "Add error handling to the code",
            "Add type hints and docstrings",
        ])
    """
    swarm = Swarm(cwd=cwd)
    results = []
    
    for i, stage in enumerate(stages):
        if i > 0 and results:
            prev = results[-1]
            prompt = f"{stage}\n\n## Previous Stage Output\n{json.dumps(prev.get('result', ''), indent=2)}"
        else:
            prompt = stage
        
        result = await swarm.run_prompt(prompt, allowed_tools=allowed_tools)
        results.append({"stage": i, "prompt": stage, **result})
    
    return {
        "stages": results,
        "final": results[-1] if results else None,
    }


async def hierarchical(
    goal: str,
    cwd: str = ".",
    max_subtasks: int = 5,
    max_concurrent: int = 5,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """
    Coordinator plans subtasks, workers execute in parallel, synthesizer combines.
    
    Three-phase execution:
    1. Planner breaks goal into subtasks
    2. Workers execute subtasks in parallel
    3. Synthesizer combines results
    
    Example:
        result = await hierarchical(
            "Refactor this Flask app to use async and add logging",
            cwd="~/projects/flask-api"
        )
    """
    swarm = Swarm(max_concurrent=max_concurrent, cwd=cwd)
    
    # Phase 1: Planning
    plan_prompt = f"""You are a planning coordinator. Break this goal into {max_subtasks} or fewer independent subtasks that can be executed in parallel.

Return ONLY a JSON array of task strings. No explanation, no markdown, just the JSON array.

Goal: {goal}"""
    
    plan_result = await swarm.run_prompt(plan_prompt)
    
    # Parse subtasks
    try:
        raw = plan_result.get("result", {})
        if isinstance(raw, dict):
            raw = raw.get("result", "[]")
        subtasks = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(subtasks, list):
            subtasks = [goal]
    except (json.JSONDecodeError, TypeError):
        subtasks = [goal]
    
    # Phase 2: Parallel execution
    worker_results = await fan_out(subtasks, cwd=cwd, max_concurrent=max_concurrent, allowed_tools=allowed_tools)
    
    # Phase 3: Synthesis
    synth_prompt = f"""You are a synthesis coordinator. Combine these worker results into a cohesive response.

## Original Goal
{goal}

## Subtask Results
{json.dumps(worker_results, indent=2)}

Provide a unified, coherent response that addresses the original goal."""
    
    synthesis = await swarm.run_prompt(synth_prompt)
    
    return {
        "goal": goal,
        "subtasks": subtasks,
        "worker_results": worker_results,
        "synthesis": synthesis,
    }


async def competitive(
    task: str,
    num_agents: int = 3,
    cwd: str = ".",
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """
    Multiple agents solve the same task independently, then a judge picks the best.
    
    Useful for creative tasks or when you want multiple perspectives.
    
    Example:
        result = await competitive(
            "Write a Python function to find the longest palindrome in a string",
            num_agents=3
        )
    """
    swarm = Swarm(max_concurrent=num_agents, cwd=cwd)
    
    # Run same task with different "personas"
    personas = [
        "Focus on code clarity and readability.",
        "Focus on optimal performance and efficiency.",
        "Focus on robustness and edge case handling.",
    ]
    
    tasks = [
        f"{task}\n\nApproach: {personas[i % len(personas)]}"
        for i in range(num_agents)
    ]
    
    solutions = await fan_out(tasks, cwd=cwd, max_concurrent=num_agents, allowed_tools=allowed_tools)
    
    # Judge the solutions
    judge_prompt = f"""You are a judge evaluating {num_agents} solutions to this task:

## Task
{task}

## Solutions
{json.dumps(solutions, indent=2)}

Evaluate each solution and select the best one. Explain your reasoning briefly, then output which solution index (0-{num_agents-1}) is best."""
    
    judgment = await swarm.run_prompt(judge_prompt)
    
    return {
        "task": task,
        "solutions": solutions,
        "judgment": judgment,
    }


async def map_reduce(
    items: list[str],
    map_prompt: str,
    reduce_prompt: str,
    cwd: str = ".",
    max_concurrent: int = 5,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """
    Map a prompt over items in parallel, then reduce the results.
    
    Example:
        result = await map_reduce(
            items=["file1.py", "file2.py", "file3.py"],
            map_prompt="Analyze this file for security issues: {item}",
            reduce_prompt="Summarize all security findings and prioritize by severity",
        )
    """
    # Map phase
    map_tasks = [map_prompt.format(item=item) for item in items]
    map_results = await fan_out(map_tasks, cwd=cwd, max_concurrent=max_concurrent, allowed_tools=allowed_tools)

    # Reduce phase
    swarm = Swarm(cwd=cwd)
    full_reduce = f"""{reduce_prompt}

## Map Results
{json.dumps(map_results, indent=2)}"""

    reduce_result = await swarm.run_prompt(full_reduce, allowed_tools=allowed_tools)
    
    return {
        "items": items,
        "map_results": map_results,
        "reduce_result": reduce_result,
    }
