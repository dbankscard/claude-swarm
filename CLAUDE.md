# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Swarm orchestrates multiple Claude Code agents from the terminal or within Claude Code sessions. It provides both a CLI and Python API for running agents in various patterns (parallel, sequential, hierarchical, competitive).

## Development Commands

```bash
# Install in development mode
pip install -e .

# Run the CLI
claude-swarm <command>
```

## Architecture

### Core Components

- **`src/claude_swarm/swarm.py`**: Core orchestration classes
  - `Agent`: Individual agent with role, system prompt, and memory (last 5 interactions)
  - `SwarmState`: Persistent state (agents, shared context, history) saved to `.swarm_state.json`
  - `Swarm`: Main orchestrator that manages agents, invokes Claude via subprocess, and handles concurrency

- **`src/claude_swarm/patterns.py`**: Orchestration patterns (all async)
  - `fan_out`: Parallel independent tasks
  - `pipeline`: Sequential with context passing between stages
  - `hierarchical`: Three-phase (plan → parallel execute → synthesize)
  - `competitive`: Multiple solutions judged for best result
  - `map_reduce`: Map prompt over items, then reduce

- **`src/claude_swarm/cli.py`**: CLI entry point with subcommands for patterns and swarm management

### How It Works

The `Swarm` class invokes Claude Code via `asyncio.create_subprocess_exec` with the `claude -p <prompt> --output-format json` command. Concurrency is controlled via `asyncio.Semaphore` (default max 5 concurrent agents).

Agent prompts are built by combining: agent identity → system prompt → shared context → agent memory → task.

### Enabling Tools for Agents

By default, spawned agents run with limited permissions. Use `--profile` or `--allowed-tools` to grant access:

```bash
# Use a predefined profile
claude-swarm pipeline "build feature" "add tests" --profile build
claude-swarm hierarchical "research topic" --profile research

# Allow all tools
claude-swarm hierarchical "create an app" --allowed-tools all

# Or specific tools
claude-swarm fan-out "task1" "task2" --allowed-tools WebSearch Write Bash

# List available profiles
claude-swarm profiles
```

**Profiles defined in `cli.py`:**
- `all`: Full tool access (Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, AskUserQuestion, TodoWrite, Task, NotebookEdit)
- `build`: For building/coding (Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion)
- `research`: For research (Read, Glob, Grep, WebSearch, WebFetch)
- `code`: Code changes only (Read, Write, Edit, Glob, Grep, Bash)
- `readonly`: Safe exploration (Read, Glob, Grep)

In Python API, pass `allowed_tools` parameter:
```python
results = await fan_out(tasks, allowed_tools=["WebSearch", "WebFetch"])
```

### State Persistence

State is saved to `.swarm_state.json` and includes:
- Agent definitions (name, role, system_prompt, memory)
- Shared context (key-value pairs accessible to all agents)
- History (last 100 interactions)
