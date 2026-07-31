from abc import ABC, abstractmethod
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext


class BaseAgent(ABC):
    def __init__(self, name: str, layer: int, bus: SupervisorBus):
        self.name = name
        self.layer = layer
        self.bus = bus

    def log(self, ctx: PipelineContext, message: str, level: str = "INFO", data: dict = None):
        self.bus.publish(ctx, agent_name=self.name, layer=self.layer, content=message, level=level, data=data)

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None:
        """Executes the agent logic modifying context in place."""
        pass
