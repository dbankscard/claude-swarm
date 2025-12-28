# Claude Swarm

Orchestrate multiple Claude Code agents from your terminal or within Claude Code sessions.

## Requirements

- **Python** >= 3.10
- **[Claude Code](https://claude.ai/code)** - Must be installed and available in your PATH

## Installation

```bash
pip install -e .
```

The `claude-swarm` command will be installed to your Python bin directory. If it's not in your PATH, add it:

```bash
# Add Python user bin to PATH (macOS/Linux)
echo 'export PATH="$PATH:$(python3 -m site --user-base)/bin"' >> ~/.zshrc
source ~/.zshrc
```

## Quick Start

### CLI Usage

```bash
# Fan-out: Run tasks in parallel
claude-swarm fan-out \
  "Review ./src/auth for security issues" \
  "Check ./src/api error handling" \
  "Analyze ./src/models for performance"

# Pipeline: Sequential refinement
claude-swarm pipeline \
  "Draft a Python CLI for file encryption" \
  "Add error handling and validation" \
  "Add docstrings and type hints"

# Hierarchical: Let Claude plan the work
claude-swarm hierarchical "Refactor this codebase to use async handlers"

# Competitive: Multiple solutions, pick the best
claude-swarm competitive "Write a function to find the longest palindrome"

# Enable web search for research tasks
claude-swarm hierarchical "Research best practices for API rate limiting" \
  --allowed-tools WebSearch WebFetch
```

### Managed Swarm with Persistent Agents

```bash
# Create specialized agents
claude-swarm manage add-agent architect --role "software architect" \
  --system-prompt "Focus on design patterns and system structure"

claude-swarm manage add-agent security --role "security analyst" \
  --system-prompt "Focus on vulnerabilities and data protection"

claude-swarm manage add-agent perf --role "performance engineer" \
  --system-prompt "Focus on bottlenecks and optimization"

# Set shared context
claude-swarm manage set-context project '"My E-commerce Platform"'
claude-swarm manage set-context stack '["Python", "Flask", "AWS", "PostgreSQL"]'

# Invoke individual agents
claude-swarm manage invoke architect "Review the authentication flow"

# Dispatch different tasks to different agents
claude-swarm manage dispatch \
  --assignments "architect:Review system design" \
                "security:Audit auth module" \
                "perf:Profile database queries"

# Broadcast same task to all agents
claude-swarm manage broadcast "What improvements would you suggest for ./src?"
```

### Python API

```python
import asyncio
from claude_swarm import Swarm, fan_out, hierarchical

# Quick parallel execution
async def analyze_codebase():
    results = await fan_out([
        "Review ./src/auth",
        "Review ./src/api",
        "Review ./src/models",
    ], cwd="~/projects/myapp", allowed_tools=["WebSearch"])
    return results

# Managed swarm with state
async def run_team():
    swarm = Swarm(cwd="~/projects/myapp")
    
    swarm.add_agent("architect", "software architect", 
                    "Focus on clean architecture and SOLID principles")
    swarm.add_agent("reviewer", "code reviewer",
                    "Focus on code quality and best practices")
    
    swarm.update_context("project", "E-commerce API")
    
    results = await swarm.dispatch({
        "architect": "Propose a new module structure",
        "reviewer": "Review the current error handling",
    })
    
    swarm.save()  # Persist state for next session
    return results

asyncio.run(run_team())
```

## Patterns

| Pattern | Use Case |
|---------|----------|
| `fan_out` | Parallel independent tasks |
| `pipeline` | Sequential processing with context |
| `hierarchical` | Auto-planning with worker execution |
| `competitive` | Multiple solutions, judge picks best |
| `map_reduce` | Process items in parallel, combine results |

## Using Within Claude Code

You can invoke the swarm directly during a Claude Code session:

```bash
# In your Claude Code conversation
claude-swarm fan-out "task1" "task2" "task3"
```

Or use the Python API in scripts Claude creates for you.

## State Persistence

The managed swarm saves state to `.swarm_state.json` by default. This includes:
- Agent definitions and roles
- Shared context
- Recent interaction history
- Agent memory (last 5 interactions per agent)

## Tool Profiles

Control what tools agents can use with `--profile` or `--allowed-tools`:

```bash
# Use a predefined profile
claude-swarm pipeline "build feature" "add tests" --profile build

# Or allow all tools
claude-swarm hierarchical "create an app" --allowed-tools all

# List available profiles
claude-swarm profiles
```

| Profile | Tools | Use Case |
|---------|-------|----------|
| `all` | Everything | Full autonomy |
| `build` | Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion | Building/coding |
| `research` | Read, Glob, Grep, WebSearch, WebFetch | Research tasks |
| `code` | Read, Write, Edit, Glob, Grep, Bash | Code changes only |
| `readonly` | Read, Glob, Grep | Safe exploration |

## Tips

1. **Rate Limits**: Default max concurrent is 5 agents
2. **Working Directory**: Use `--cwd` to set where agents operate
3. **Agent Memory**: Agents remember their last 5 interactions
4. **Shared Context**: Use `set-context` for project-wide info all agents see
5. **Tool Access**: Use `--profile build` or `--allowed-tools all` for full functionality
