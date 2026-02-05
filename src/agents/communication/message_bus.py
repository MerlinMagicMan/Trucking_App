"""
Message bus for inter-agent communication.
"""

from typing import Dict, List, Callable, Optional, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import uuid

from ..types import AgentRole, Message


MessageHandler = Callable[[Message], Awaitable[None]]


@dataclass
class Subscription:
    """A subscription to messages."""
    subscriber: AgentRole
    handler: MessageHandler
    filter_subject: Optional[str] = None


class MessageBus:
    """
    Message bus for agent communication.

    Supports:
    - Direct messages (agent to agent)
    - Broadcast messages (to all agents)
    - Topic-based subscriptions
    - Message history
    """

    def __init__(self):
        self._subscriptions: Dict[AgentRole, List[Subscription]] = defaultdict(list)
        self._history: List[Message] = []
        self._undelivered: List[Message] = []

    def subscribe(
        self,
        agent: AgentRole,
        handler: MessageHandler,
        filter_subject: Optional[str] = None,
    ) -> str:
        """
        Subscribe an agent to receive messages.

        Returns subscription ID.
        """
        sub = Subscription(
            subscriber=agent,
            handler=handler,
            filter_subject=filter_subject,
        )
        self._subscriptions[agent].append(sub)
        return f"{agent.value}:{len(self._subscriptions[agent])}"

    def unsubscribe(self, agent: AgentRole, subscription_id: str) -> bool:
        """Unsubscribe from messages."""
        # Simplified - would need proper tracking in production
        if agent in self._subscriptions:
            self._subscriptions[agent] = []
            return True
        return False

    async def send(self, message: Message) -> bool:
        """
        Send a message to a specific agent.

        Returns True if delivered.
        """
        self._history.append(message)

        target = message.to_agent
        if target in self._subscriptions:
            for sub in self._subscriptions[target]:
                # Check subject filter
                if sub.filter_subject and sub.filter_subject.lower() not in message.subject.lower():
                    continue

                try:
                    await sub.handler(message)
                    return True
                except Exception as e:
                    print(f"Message delivery failed: {e}")
                    self._undelivered.append(message)
                    return False

        # No subscribers - queue for later
        self._undelivered.append(message)
        return False

    async def broadcast(self, message: Message, exclude: List[AgentRole] | None = None) -> int:
        """
        Broadcast a message to all agents.

        Returns count of successful deliveries.
        """
        exclude = exclude or []
        delivered = 0

        for agent, subs in self._subscriptions.items():
            if agent in exclude:
                continue

            # Create a copy for each recipient
            agent_message = Message(
                id=str(uuid.uuid4()),
                from_agent=message.from_agent,
                to_agent=agent,
                subject=message.subject,
                content=message.content,
                priority=message.priority,
                requires_response=message.requires_response,
            )

            for sub in subs:
                if sub.filter_subject and sub.filter_subject.lower() not in message.subject.lower():
                    continue

                try:
                    await sub.handler(agent_message)
                    delivered += 1
                    self._history.append(agent_message)
                except Exception:
                    pass

        return delivered

    async def request_response(
        self,
        message: Message,
        timeout_seconds: float = 30.0,
    ) -> Optional[Message]:
        """
        Send a message and wait for response.

        Returns response message or None if timeout.
        """
        message.requires_response = True
        await self.send(message)

        # In a real implementation, this would use asyncio events/futures
        # For now, just return None (response handled via callbacks)
        return None

    def create_message(
        self,
        from_agent: AgentRole,
        to_agent: AgentRole,
        subject: str,
        content: str,
        priority: str = "normal",
        in_reply_to: Optional[str] = None,
    ) -> Message:
        """Helper to create a message."""
        return Message(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            subject=subject,
            content=content,
            priority=priority,
            in_reply_to=in_reply_to,
        )

    def get_history(
        self,
        agent: Optional[AgentRole] = None,
        limit: int = 100,
    ) -> List[Message]:
        """Get message history, optionally filtered by agent."""
        messages = self._history

        if agent:
            messages = [
                m for m in messages
                if m.from_agent == agent or m.to_agent == agent
            ]

        return messages[-limit:]

    def get_undelivered(self) -> List[Message]:
        """Get undelivered messages."""
        return list(self._undelivered)

    def clear_undelivered(self) -> int:
        """Clear undelivered messages, returns count cleared."""
        count = len(self._undelivered)
        self._undelivered.clear()
        return count

    def get_stats(self) -> Dict:
        """Get message bus statistics."""
        return {
            "total_messages": len(self._history),
            "undelivered": len(self._undelivered),
            "subscribers": sum(len(subs) for subs in self._subscriptions.values()),
            "agents_subscribed": len(self._subscriptions),
        }
