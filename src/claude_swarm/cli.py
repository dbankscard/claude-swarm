#!/usr/bin/env python3
"""CLI interface for Claude Code Agent Swarm."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .swarm import Swarm
from .patterns import fan_out, pipeline, hierarchical, competitive, map_reduce

# Tool profiles for common use cases
TOOL_PROFILES = {
    "all": [
        "Read", "Write", "Edit", "Glob", "Grep",
        "Bash", "WebSearch", "WebFetch", "AskUserQuestion",
        "TodoWrite", "Task", "NotebookEdit",
    ],
    "build": [
        "Read", "Write", "Edit", "Glob", "Grep", "Bash", "AskUserQuestion",
    ],
    "research": [
        "Read", "Glob", "Grep", "WebSearch", "WebFetch",
    ],
    "code": [
        "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    ],
    "readonly": [
        "Read", "Glob", "Grep",
    ],
}


def resolve_tools(args: argparse.Namespace) -> list[str] | None:
    """Resolve --allowed-tools and --profile to a list of tools."""
    tools = []

    # Handle --profile
    profile = getattr(args, 'profile', None)
    if profile:
        if profile not in TOOL_PROFILES:
            print(f"Unknown profile: {profile}. Available: {', '.join(TOOL_PROFILES.keys())}")
            sys.exit(1)
        tools.extend(TOOL_PROFILES[profile])

    # Handle --allowed-tools
    allowed = getattr(args, 'allowed_tools', None)
    if allowed:
        for tool in allowed:
            if tool.lower() == "all":
                tools.extend(TOOL_PROFILES["all"])
            elif tool in TOOL_PROFILES:
                tools.extend(TOOL_PROFILES[tool])
            else:
                tools.append(tool)

    # Deduplicate while preserving order
    if tools:
        seen = set()
        unique = []
        for t in tools:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique

    return None


def add_tool_args(parser: argparse.ArgumentParser) -> None:
    """Add --allowed-tools and --profile arguments to a parser."""
    parser.add_argument(
        "--allowed-tools", nargs="+",
        help="Tools to allow (e.g. WebSearch WebFetch). Use 'all' for all tools.",
    )
    parser.add_argument(
        "--profile", choices=list(TOOL_PROFILES.keys()),
        help="Tool profile: all, build, research, code, readonly",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="claude-swarm",
        description="Orchestrate multiple Claude Code agents",
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Fan-out command
    fanout = subparsers.add_parser("fan-out", help="Run tasks in parallel")
    fanout.add_argument("tasks", nargs="+", help="Tasks to run")
    fanout.add_argument("--cwd", default=".", help="Working directory")
    fanout.add_argument("--max-concurrent", type=int, default=5)
    add_tool_args(fanout)

    # Pipeline command
    pipe = subparsers.add_parser("pipeline", help="Run tasks sequentially")
    pipe.add_argument("stages", nargs="+", help="Pipeline stages")
    pipe.add_argument("--cwd", default=".", help="Working directory")
    add_tool_args(pipe)

    # Hierarchical command
    hier = subparsers.add_parser("hierarchical", help="Plan, execute, synthesize")
    hier.add_argument("goal", help="High-level goal")
    hier.add_argument("--cwd", default=".", help="Working directory")
    hier.add_argument("--max-subtasks", type=int, default=5)
    hier.add_argument("--max-concurrent", type=int, default=5)
    add_tool_args(hier)

    # Competitive command
    comp = subparsers.add_parser("competitive", help="Multiple agents compete")
    comp.add_argument("task", help="Task for agents")
    comp.add_argument("--num-agents", type=int, default=3)
    comp.add_argument("--cwd", default=".", help="Working directory")
    add_tool_args(comp)

    # Map-reduce command
    mr = subparsers.add_parser("map-reduce", help="Map over items, reduce results")
    mr.add_argument("--items", nargs="+", required=True, help="Items to process")
    mr.add_argument("--map-prompt", required=True, help="Map prompt (use {item})")
    mr.add_argument("--reduce-prompt", required=True, help="Reduce prompt")
    mr.add_argument("--cwd", default=".", help="Working directory")
    mr.add_argument("--max-concurrent", type=int, default=5)
    add_tool_args(mr)
    
    # Profiles command
    profiles = subparsers.add_parser("profiles", help="List available tool profiles")

    # Interactive swarm management
    manage = subparsers.add_parser("manage", help="Manage persistent swarm")
    manage_sub = manage.add_subparsers(dest="action", required=True)
    
    # manage add-agent
    add_agent = manage_sub.add_parser("add-agent", help="Add an agent")
    add_agent.add_argument("name", help="Agent name")
    add_agent.add_argument("--role", required=True, help="Agent role")
    add_agent.add_argument("--system-prompt", default="", help="System prompt")
    add_agent.add_argument("--state-file", default=".swarm_state.json")
    
    # manage remove-agent
    rm_agent = manage_sub.add_parser("remove-agent", help="Remove an agent")
    rm_agent.add_argument("name", help="Agent name")
    rm_agent.add_argument("--state-file", default=".swarm_state.json")
    
    # manage list-agents
    list_agents = manage_sub.add_parser("list-agents", help="List agents")
    list_agents.add_argument("--state-file", default=".swarm_state.json")
    
    # manage invoke
    invoke = manage_sub.add_parser("invoke", help="Invoke an agent")
    invoke.add_argument("agent", help="Agent name")
    invoke.add_argument("task", help="Task for agent")
    invoke.add_argument("--cwd", default=".")
    invoke.add_argument("--state-file", default=".swarm_state.json")
    
    # manage dispatch
    dispatch = manage_sub.add_parser("dispatch", help="Dispatch to multiple agents")
    dispatch.add_argument("--assignments", nargs="+", help="agent:task pairs")
    dispatch.add_argument("--cwd", default=".")
    dispatch.add_argument("--state-file", default=".swarm_state.json")
    
    # manage broadcast
    broadcast = manage_sub.add_parser("broadcast", help="Broadcast to all agents")
    broadcast.add_argument("task", help="Task for all agents")
    broadcast.add_argument("--cwd", default=".")
    broadcast.add_argument("--state-file", default=".swarm_state.json")
    
    # manage set-context
    set_ctx = manage_sub.add_parser("set-context", help="Set shared context")
    set_ctx.add_argument("key", help="Context key")
    set_ctx.add_argument("value", help="Context value (JSON)")
    set_ctx.add_argument("--state-file", default=".swarm_state.json")
    
    # manage show-context
    show_ctx = manage_sub.add_parser("show-context", help="Show shared context")
    show_ctx.add_argument("--state-file", default=".swarm_state.json")
    
    return parser.parse_args()


async def run_command(args: argparse.Namespace) -> int:
    result = None
    allowed_tools = resolve_tools(args)

    if args.command == "fan-out":
        result = await fan_out(
            args.tasks,
            cwd=args.cwd,
            max_concurrent=args.max_concurrent,
            allowed_tools=allowed_tools,
        )

    elif args.command == "pipeline":
        result = await pipeline(
            args.stages,
            cwd=args.cwd,
            allowed_tools=allowed_tools,
        )

    elif args.command == "hierarchical":
        result = await hierarchical(
            args.goal,
            cwd=args.cwd,
            max_subtasks=args.max_subtasks,
            max_concurrent=args.max_concurrent,
            allowed_tools=allowed_tools,
        )

    elif args.command == "competitive":
        result = await competitive(
            args.task,
            num_agents=args.num_agents,
            cwd=args.cwd,
            allowed_tools=allowed_tools,
        )

    elif args.command == "map-reduce":
        result = await map_reduce(
            items=args.items,
            map_prompt=args.map_prompt,
            reduce_prompt=args.reduce_prompt,
            cwd=args.cwd,
            max_concurrent=args.max_concurrent,
            allowed_tools=allowed_tools,
        )
    
    elif args.command == "profiles":
        print("Available tool profiles:\n")
        for name, tools in TOOL_PROFILES.items():
            print(f"  {name}:")
            print(f"    {', '.join(tools)}\n")
        return 0

    elif args.command == "manage":
        result = await handle_manage(args)

    if result is not None:
        print(json.dumps(result, indent=2, default=str))
    
    return 0


async def handle_manage(args: argparse.Namespace) -> dict | list | None:
    state_file = args.state_file
    
    if args.action == "add-agent":
        swarm = Swarm.load(state_file) if Path(state_file).exists() else Swarm()
        agent = swarm.add_agent(
            name=args.name,
            role=args.role,
            system_prompt=args.system_prompt,
        )
        swarm.save(state_file)
        return {"added": agent.to_dict()}
    
    elif args.action == "remove-agent":
        swarm = Swarm.load(state_file)
        removed = swarm.remove_agent(args.name)
        swarm.save(state_file)
        return {"removed": args.name, "success": removed}
    
    elif args.action == "list-agents":
        swarm = Swarm.load(state_file)
        return swarm.list_agents()
    
    elif args.action == "invoke":
        swarm = Swarm.load(state_file, cwd=args.cwd)
        result = await swarm.invoke(args.agent, args.task)
        swarm.save(state_file)
        return result
    
    elif args.action == "dispatch":
        swarm = Swarm.load(state_file, cwd=args.cwd)
        # Parse agent:task pairs
        assignments = {}
        for pair in args.assignments:
            agent, task = pair.split(":", 1)
            assignments[agent] = task
        result = await swarm.dispatch(assignments)
        swarm.save(state_file)
        return result
    
    elif args.action == "broadcast":
        swarm = Swarm.load(state_file, cwd=args.cwd)
        result = await swarm.broadcast(args.task)
        swarm.save(state_file)
        return result
    
    elif args.action == "set-context":
        swarm = Swarm.load(state_file) if Path(state_file).exists() else Swarm()
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        swarm.update_context(args.key, value)
        swarm.save(state_file)
        return {"context": swarm.state.shared_context}
    
    elif args.action == "show-context":
        swarm = Swarm.load(state_file)
        return swarm.state.shared_context
    
    return None


def main() -> int:
    args = parse_args()
    return asyncio.run(run_command(args))


if __name__ == "__main__":
    sys.exit(main())
