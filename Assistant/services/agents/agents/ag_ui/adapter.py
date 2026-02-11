"""
Custom adapter to emit changes to shared state at the beginning of an agent response

The CustomAGUIAdapter defined here now ensures that the agent state is emitted 
"""
from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent, StateSnapshotEvent
from pydantic_ai.ui.ag_ui import AGUIAdapter, AGUIEventStream

from ..deps import AgentDeps


class CustomAGUIEventStream(AGUIEventStream[AgentDeps, str]):
    """
    Custom event stream to emit state snapshot at the start of agent response
    """

    async def before_stream(self) -> AsyncIterator[BaseEvent]:
        """
        Add a StateSnapshotEvent immediately before the stream starts
        """
        # Yield all events from parent's before_stream
        async for event in super().before_stream():
            yield event
        
        # Then emit the agent state using a StateSnapshotEvent
        yield StateSnapshotEvent(
            snapshot=self.run_input.state
        )


class CustomAGUIAdapter(AGUIAdapter[AgentDeps, str]):
    """
    Custom AG-UI adapter to use the custom event stream
    """
    def build_event_stream(self) -> AGUIEventStream[AgentDeps, str]:
        """
        Build a custom AG-UI event stream transformer which emits state snapshot at start of agent response.
        """
        return CustomAGUIEventStream(self.run_input, accept=self.accept)
