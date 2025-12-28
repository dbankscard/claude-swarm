"""Claude Code Agent Swarm - Orchestrate multiple Claude instances."""

from .swarm import Swarm, Agent, SwarmState
from .patterns import fan_out, pipeline, hierarchical, competitive
from .cli import main

__version__ = "0.1.0"
__all__ = ["Swarm", "Agent", "SwarmState", "fan_out", "pipeline", "hierarchical", "competitive", "main"]
