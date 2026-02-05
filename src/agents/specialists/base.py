"""
Base agent class for all specialists.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..types import AgentRole, Task, Message
from ..config import AgentConfig, get_config


@dataclass
class AgentResponse:
    """Response from an agent."""
    success: bool
    message: str
    data: Dict[str, Any] | None = None
    requires_escalation: bool = False
    escalation_reason: str | None = None
    next_agent: AgentRole | None = None


class BaseAgent(ABC):
    """Base class for all specialist agents."""

    def __init__(self, role: AgentRole):
        self.role = role
        self.config = get_config()
        self.agent_config = self.config.agents[role]
        self._prompt_template: str | None = None

    @property
    def can_write_code(self) -> bool:
        return self.agent_config.can_write_code

    @property
    def can_veto(self) -> bool:
        return self.agent_config.can_veto

    @property
    def tools(self) -> list[str]:
        return self.agent_config.tools

    def load_prompt_template(self) -> str:
        """Load the prompt template for this agent."""
        if self._prompt_template is None:
            prompt_file = self.config.prompts_dir / self.agent_config.prompt_file
            if prompt_file.exists():
                self._prompt_template = prompt_file.read_text()
            else:
                self._prompt_template = f"No prompt file found for {self.role.value}"
        return self._prompt_template

    def build_prompt(self, context: Dict[str, str]) -> str:
        """Build the full prompt with injected context."""
        template = self.load_prompt_template()

        # Replace context placeholders
        for key, value in context.items():
            placeholder = "{" + key.upper() + "}"
            template = template.replace(placeholder, value)

        return template

    @abstractmethod
    async def process_task(self, task: Task) -> AgentResponse:
        """Process an assigned task."""
        pass

    @abstractmethod
    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle a message from another agent."""
        pass

    def log(self, message: str):
        """Log a message from this agent."""
        print(f"[{self.role.value}] {message}")


class ReviewerAgent(BaseAgent):
    """Base class for agents that review but don't implement."""

    @property
    def can_write_code(self) -> bool:
        return False

    async def process_task(self, task: Task) -> AgentResponse:
        """Reviewers don't implement tasks, they review them."""
        return AgentResponse(
            success=False,
            message=f"{self.role.value} is a reviewer, not an implementer",
        )


class ImplementerAgent(BaseAgent):
    """Base class for agents that implement code."""

    @property
    def can_write_code(self) -> bool:
        return True

    @abstractmethod
    async def implement(self, task: Task) -> AgentResponse:
        """Implement the assigned task."""
        pass

    async def process_task(self, task: Task) -> AgentResponse:
        """Process task by implementing it."""
        return await self.implement(task)
