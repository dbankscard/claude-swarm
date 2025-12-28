"""Core swarm classes for agent orchestration."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Agent:
    """Individual agent with role, system prompt, and memory."""
    
    name: str
    role: str
    system_prompt: str = ""
    memory: list[dict] = field(default_factory=list)
    allowed_tools: list[str] | None = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "system_prompt": self.system_prompt,
            "memory": self.memory,
            "allowed_tools": self.allowed_tools,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Agent:
        return cls(**data)


@dataclass
class SwarmState:
    """Persistent state for the swarm."""
    
    agents: dict[str, Agent] = field(default_factory=dict)
    shared_context: dict[str, Any] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    
    def save(self, path: str | Path = ".swarm_state.json") -> None:
        """Save swarm state to disk."""
        Path(path).write_text(json.dumps({
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "shared_context": self.shared_context,
            "history": self.history[-100:],  # Keep last 100 entries
        }, indent=2, default=str))
    
    @classmethod
    def load(cls, path: str | Path = ".swarm_state.json") -> SwarmState:
        """Load swarm state from disk."""
        path = Path(path)
        if not path.exists():
            return cls()
        
        data = json.loads(path.read_text())
        return cls(
            agents={k: Agent.from_dict(v) for k, v in data.get("agents", {}).items()},
            shared_context=data.get("shared_context", {}),
            history=data.get("history", []),
        )


class Swarm:
    """Orchestrate multiple Claude Code agents."""
    
    def __init__(
        self,
        state: SwarmState | None = None,
        max_concurrent: int = 5,
        cwd: str | Path = ".",
        output_format: str = "json",
    ):
        self.state = state or SwarmState()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.cwd = Path(cwd).resolve()
        self.output_format = output_format
    
    def add_agent(
        self,
        name: str,
        role: str,
        system_prompt: str = "",
        allowed_tools: list[str] | None = None,
    ) -> Agent:
        """Add an agent to the swarm."""
        agent = Agent(
            name=name,
            role=role,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
        )
        self.state.agents[name] = agent
        return agent
    
    def remove_agent(self, name: str) -> bool:
        """Remove an agent from the swarm."""
        if name in self.state.agents:
            del self.state.agents[name]
            return True
        return False
    
    def update_context(self, key: str, value: Any) -> None:
        """Update shared context available to all agents."""
        self.state.shared_context[key] = value
    
    def clear_context(self) -> None:
        """Clear all shared context."""
        self.state.shared_context.clear()
    
    async def _invoke_claude(
        self,
        prompt: str,
        allowed_tools: list[str] | None = None,
        cwd: Path | None = None,
    ) -> dict[str, Any]:
        """Run a single Claude Code instance."""
        async with self.semaphore:
            cmd = ["claude", "-p", prompt, "--output-format", self.output_format]
            
            if allowed_tools:
                cmd.extend(["--allowedTools", ",".join(allowed_tools)])
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd or self.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode().strip(),
                    "returncode": proc.returncode,
                }
            
            try:
                result = json.loads(stdout.decode())
                return {"success": True, "result": result}
            except json.JSONDecodeError:
                return {"success": True, "result": stdout.decode().strip()}
    
    def _build_prompt(self, agent: Agent, task: str) -> str:
        """Build the full prompt for an agent including context and memory."""
        parts = []
        
        # Agent identity
        if agent.role:
            parts.append(f"You are {agent.name}, a {agent.role}.")
        if agent.system_prompt:
            parts.append(agent.system_prompt)
        
        # Shared context
        if self.state.shared_context:
            parts.append(f"\n## Shared Context\n{json.dumps(self.state.shared_context, indent=2)}")
        
        # Agent memory (last 5 interactions)
        if agent.memory:
            recent = agent.memory[-5:]
            parts.append(f"\n## Your Recent Memory\n{json.dumps(recent, indent=2)}")
        
        # The task
        parts.append(f"\n## Task\n{task}")
        
        return "\n\n".join(parts)
    
    async def invoke(self, agent_name: str, task: str) -> dict[str, Any]:
        """Invoke a specific agent with a task."""
        if agent_name not in self.state.agents:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        agent = self.state.agents[agent_name]
        prompt = self._build_prompt(agent, task)
        result = await self._invoke_claude(prompt, agent.allowed_tools)
        
        # Update agent memory
        agent.memory.append({
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "result": result.get("result") if result["success"] else result.get("error"),
            "success": result["success"],
        })
        
        # Log to history
        self.state.history.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "task": task,
            "result": result,
        })
        
        return {"agent": agent_name, **result}
    
    async def dispatch(self, assignments: dict[str, str]) -> list[dict[str, Any]]:
        """Dispatch tasks to multiple agents in parallel."""
        tasks = [self.invoke(name, task) for name, task in assignments.items()]
        return await asyncio.gather(*tasks)
    
    async def broadcast(self, task: str) -> list[dict[str, Any]]:
        """Send the same task to all agents."""
        return await self.dispatch({name: task for name in self.state.agents})
    
    async def run_prompt(
        self,
        prompt: str,
        allowed_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a raw prompt without an agent context."""
        result = await self._invoke_claude(prompt, allowed_tools=allowed_tools)
        
        self.state.history.append({
            "timestamp": datetime.now().isoformat(),
            "agent": None,
            "task": prompt,
            "result": result,
        })
        
        return result
    
    def save(self, path: str | Path = ".swarm_state.json") -> None:
        """Save swarm state."""
        self.state.save(path)
    
    @classmethod
    def load(
        cls,
        path: str | Path = ".swarm_state.json",
        **kwargs,
    ) -> Swarm:
        """Load swarm from saved state."""
        state = SwarmState.load(path)
        return cls(state=state, **kwargs)
    
    def list_agents(self) -> list[dict]:
        """List all agents and their roles."""
        return [
            {"name": a.name, "role": a.role, "memory_size": len(a.memory)}
            for a in self.state.agents.values()
        ]
