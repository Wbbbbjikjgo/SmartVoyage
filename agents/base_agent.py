"""Base agent class and A2A protocol definitions."""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Represents an agent skill/capability."""
    name: str
    description: str
    tags: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCard:
    """Agent Card for A2A protocol - describes agent identity and capabilities."""
    name: str
    description: str
    version: str
    url: str
    skills: List[Skill] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "tags": s.tags,
                }
                for s in self.skills
            ],
            "capabilities": self.capabilities,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class BaseAgent(ABC):
    """
    Base class for all A2A agents.

    Subclasses must implement:
    - get_agent_card(): Returns the agent's card
    - handle_task(): Handles incoming task requests
    """

    def __init__(self, name: str, description: str, version: str = "1.0.0"):
        """
        Initialize base agent.

        Args:
            name: Agent name
            description: Agent description
            version: Agent version
        """
        self.name = name
        self.description = description
        self.version = version
        self.skills: List[Skill] = []
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    def get_agent_card(self, base_url: str) -> AgentCard:
        """
        Get agent card for A2A protocol.

        Args:
            base_url: Base URL where the agent is hosted

        Returns:
            AgentCard instance
        """
        pass

    @abstractmethod
    async def handle_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming task request.

        Args:
            task: Task request dictionary containing:
                - skill: Name of the skill to invoke
                - parameters: Parameters for the skill

        Returns:
            Task result dictionary
        """
        pass

    def register_skill(self, skill: Skill):
        """
        Register a skill with the agent.

        Args:
            skill: Skill to register
        """
        self.skills.append(skill)
        self.logger.info(f"Registered skill: {skill.name}")

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """
        Get a skill by name.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill instance or None
        """
        for skill in self.skills:
            if skill.name == skill_name:
                return skill
        return None

    async def execute_skill(
        self,
        skill_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a skill with given parameters.

        Args:
            skill_name: Name of the skill to execute
            parameters: Parameters for the skill

        Returns:
            Execution result
        """
        skill = self.get_skill(skill_name)
        if not skill:
            return {
                "error": True,
                "message": f"Skill not found: {skill_name}",
            }

        try:
            # Get the skill handler method
            handler = getattr(self, f"skill_{skill_name}", None)
            if not handler:
                return {
                    "error": True,
                    "message": f"Skill handler not found: {skill_name}",
                }

            # Execute the handler
            result = await handler(**parameters)
            return {"success": True, "data": result}

        except Exception as e:
            self.logger.exception(f"Error executing skill {skill_name}: {e}")
            return {
                "error": True,
                "message": str(e),
            }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', version='{self.version}')>"
