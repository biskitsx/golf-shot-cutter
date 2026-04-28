from typing import Protocol

from golf_domain.events import DomainEvent


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
