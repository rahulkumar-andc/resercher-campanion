import asyncio
import time
from typing import Callable, List, Dict, Any
from src.core.models import AgentMessage, PipelineContext, PipelineStage


class SupervisorBus:
    """Layer 6 Event Bus & Router that coordinates all agent operations and state transitions."""
    
    def __init__(self):
        self._listeners: List[Callable[[AgentMessage], None]] = []
        self._async_listeners: List[Callable[[AgentMessage], Any]] = []
        self._message_history: List[AgentMessage] = []

    def subscribe(self, callback: Callable[[AgentMessage], None]):
        self._listeners.append(callback)

    def subscribe_async(self, callback: Callable[[AgentMessage], Any]):
        self._async_listeners.append(callback)

    def publish(self, ctx: PipelineContext, agent_name: str, layer: int, content: str, level: str = "INFO", data: Dict[str, Any] = None):
        from src.core.progress import update_progress
        msg = AgentMessage(
            agent_name=agent_name,
            layer=layer,
            content=content,
            level=level,
            data=data or {},
            timestamp=time.time()
        )
        ctx.logs.append(msg)
        self._message_history.append(msg)
        update_progress(ctx, agent_name=agent_name)

        for listener in self._listeners:
            try:
                listener(msg)
            except Exception as e:
                print(f"[EventBus Error] Listener exception: {e}")

        try:
            loop = asyncio.get_running_loop()
            for async_listener in self._async_listeners:
                loop.create_task(async_listener(msg))
        except RuntimeError:
            pass

    def set_stage(self, ctx: PipelineContext, stage: PipelineStage, reason: str = ""):
        from src.core.progress import update_progress
        ctx.stage = stage
        update_progress(ctx, agent_name="SupervisorAgent", stage=stage)
        self.publish(
            ctx,
            agent_name="SupervisorAgent",
            layer=6,
            content=f"Pipeline state transitioned to {stage.value}. {reason}".strip(),
            level="STAGE",
            data={"stage": stage.value}
        )

    def get_history(self) -> List[AgentMessage]:
        return list(self._message_history)
