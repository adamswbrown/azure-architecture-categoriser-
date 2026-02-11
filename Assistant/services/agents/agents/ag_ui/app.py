"""
AG-UI Integration Layer

This module provides the DrMChatApp Starlette application for AG-UI integration
with thread-aware state management and multi-persona support.

Key Components:
- DrMChatApp: Main Starlette application class with AG-UI endpoints
- DelegationRouter: Thread-scoped persona state management
- ThreadState: Per-thread state container (persona, delegation flags)

DrMChatApp Features
- Parallel pre-processing of
    - Template selection via template agent
    - Persona delegation via delegator agent
- Template agent integration for structured response formatting
- Template injection into agent prompts via AgentDeps
- Thread-scoped Database access

Endpoints:
- POST /api: Main AG-UI endpoint for streaming agent responses
- GET /data: Retrieve stored data by reference (thread-scoped)

Thread Isolation:
All state (persona, data) is isolated per thread_id from CopilotKit,
ensuring proper multi-user and multi-tab support.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from http import HTTPStatus
import time
from typing import Any, Callable, Optional, Mapping, Self, Sequence

from pydantic import ValidationError
# AG-UI imports
from ag_ui.core import RunAgentInput, StateSnapshotEvent
from pydantic_ai import AgentRunResult
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.ui.ag_ui import AGUIAdapter
from pydantic_ai.usage import RunUsage
# Starlette App imports
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute
from starlette.types import ExceptionHandler, Lifespan

from .. import config
from ..auxiliary import delegator_agent, template_agent, suggestions_agent
from ..deps import AgentDeps, AgentState
from ..deps.virtual_database import DataTable, VirtualDatabase
from ..telemetry import (
    set_usage_metadata, 
    get_usage_writer, 
    UsageRecord,
    get_quota_tracker,
)
from ..telemetry.usage import UsageAggregator, UsageItem, UsageMetadata
from ..personas import Persona
from ..prompts import Templates, Template

from .adapter import CustomAGUIAdapter

logger = config.get_logger("ag_ui")


@dataclass
class RuntimeMetrics:
    """
    Runtime performance metrics for AG-UI request processing.

    Tracks timing for various stages of request handling including
    preprocessing, delegation, template selection, and broadcasting.
    """
    request_start: float = field(default_factory=time.perf_counter)

    # Request parsing metrics
    request_parse_duration: Optional[float] = None

    # Pre-processing metrics
    preprocess_start: Optional[float] = None
    preprocess_setup_duration: Optional[float] = None
    preprocess_get_thread_state_duration: Optional[float] = None

    # Task durations (template, delegation, etc.)
    task_durations: dict[str, float] = field(default_factory=dict)

    # Pre-processing gather metrics
    preprocess_gather_duration: Optional[float] = None
    preprocess_total_duration: Optional[float] = None

    # Adapter and dependencies metrics
    adapter_init_duration: Optional[float] = None
    deps_build_duration: Optional[float] = None

    def _build_summary(self, thread_id: str) -> list[str]:
        """Build summary lines for all collected metrics."""
        total_time = time.perf_counter() - self.request_start
        prefix = f"[metrics][thread={thread_id}]"
        lines: list[str] = []

        lines.append(f"{prefix} Runtime metrics summary")
        lines.append(f"{prefix} Total request time: {total_time*1000:.2f}ms")

        if self.request_parse_duration is not None:
            lines.append(f"{prefix} Request parsing: {self.request_parse_duration*1000:.2f}ms")

        if self.preprocess_total_duration is not None:
            lines.append(f"{prefix} Pre-processing total: {self.preprocess_total_duration*1000:.2f}ms")
            if self.preprocess_setup_duration is not None:
                lines.append(f"{prefix} Pre-processing setup: {self.preprocess_setup_duration*1000:.2f}ms")
            if self.preprocess_get_thread_state_duration is not None:
                lines.append(
                    f"{prefix} Pre-processing get thread state: "
                    f"{self.preprocess_get_thread_state_duration*1000:.2f}ms"
                )
            if self.preprocess_gather_duration is not None:
                lines.append(f"{prefix} Pre-processing gather: {self.preprocess_gather_duration*1000:.2f}ms")

        # Task durations
        if self.task_durations:
            for task_name, duration in self.task_durations.items():
                lines.append(f"{prefix} Task {task_name}: {duration*1000:.2f}ms")

        if self.adapter_init_duration is not None:
            lines.append(f"{prefix} Adapter initialization: {self.adapter_init_duration*1000:.2f}ms")

        if self.deps_build_duration is not None:
            lines.append(f"{prefix} Dependencies build: {self.deps_build_duration*1000:.2f}ms")

        return lines

    def log_summary(self, thread_id: str):
        """Log a summary of all collected metrics to both logger and logfire."""
        for line in self._build_summary(thread_id):
            logger.debug(line)
    
    @classmethod
    def time_task(cls, task_name: str):
        """A decorator to wrap a task function and record its execution time."""
        def wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
            async def timed_func(self_: "DrMChatApp", *args: Any, **kwargs: Any) -> Any:
                start_time = time.perf_counter()
                result = await func(self_, *args, **kwargs)
                end_time = time.perf_counter()
                self_.metrics.task_durations[task_name] = end_time - start_time
                return result
            return timed_func
        return wrapper
        


class DrMChatApp(Starlette):
    """
    Starlette application that serves AG-UI with multi-persona support.

    This class encapsulates all AG-UI endpoints and manages thread-scoped state
    for persona selection, data storage, and SSE connections.

    Attributes:
        database (VirtualDatabase): Shared VirtualDatabase instance for all threads
        _delegation_router (DelegationRouter): Manages per-thread persona state
        forced_persona (Optional[Persona]): If set, bypasses auto-delegation
        apply_templates (bool): If True, enables template agent for response formatting
        metrics (RuntimeMetrics): Runtime performance metrics for the current request

    Thread Safety:
        - Each thread (identified by CopilotKit's thread_id) has isolated state
        - Persona selection is per-thread
        - Data storage is thread-scoped via VirtualDatabase
        - SSE connections are grouped by thread_id
    """

    def __init__(
        self,
        force_persona: Optional[Persona] = None,  # If set, forces a specific persona for all requests
        apply_templates: bool = True,  # If True, enables template agent for response formatting
        turbo: bool = False,
        # Starlette init params
        debug: bool = False,
        routes: Sequence[BaseRoute] | None = None,
        middleware: Sequence[Middleware] | None = None,
        exception_handlers: Mapping[Any, ExceptionHandler] | None = None,
        on_startup: Sequence[Callable[[], Any]] | None = None,
        on_shutdown: Sequence[Callable[[], Any]] | None = None,
        lifespan: Lifespan[Self] | None = None,
    ) -> None:
        # Init app state (before super() so we can use self in lifespan)
        self.database = VirtualDatabase.init_with_defaults()

        # Preprocessing settings
        self.forced_persona = force_persona
        self.apply_templates = apply_templates

        # Models
        if turbo:
            config.agents.TURBO = True
        # Main model for persona agents
        self.model = config.agents.create_model()
        self.model_settings = config.agents.build_model_settings()
        logger.info(f"Persona agents initialized with {config.agents.DEFAULT_TIER} tier model (model_settings={self.model_settings})")
        # Pre-processing model for delegation and template selection
        pre_processing_tier = "nano" if config.agents.LLM_PROVIDER == "openai" else "light"
        self.pre_processing_model = config.agents.create_model(tier=pre_processing_tier)
        self.pre_processing_model_settings = config.agents.build_model_settings(tier=pre_processing_tier)
        logger.info(f"Pre-processing agents initialized with {pre_processing_tier} tier model (model_settings={self.pre_processing_model_settings})")

        # thread-scoped state
        self._thread_states: dict[str, AgentDeps] = {}

        # Usage tracking per user (keyed by user_id)
        # Includes TTL cleanup to prevent memory leaks in long-running servers
        self._usage_aggregators: dict[str, UsageAggregator] = {}
        self._usage_aggregator_timestamps: dict[str, float] = {}  # user_id -> last_access_time
        self._usage_aggregator_ttl: float = 24 * 60 * 60  # 24 hours in seconds
        self._last_aggregator_cleanup: float = 0.0

        # Runtime metrics (will be reset per request)
        self.metrics: RuntimeMetrics = RuntimeMetrics()

        # Create lifespan handler for cleanup if not provided
        if lifespan is None:
            lifespan = self._create_lifespan_handler()

        # Initialize Starlette app
        super().__init__(
            debug=debug,
            routes=routes,
            middleware=middleware,
            exception_handlers=exception_handlers,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=lifespan,
        )

        # Add AG-UI routes
        ## Main endpoint for streaming agent responses
        self.add_route("/api", self.handle_request, methods=["POST"])
        # Data endpoint for retrieving data by reference
        self.add_route("/data", self.data, methods=["GET"])
    
    def get_deps(self, thread_id: str) -> AgentDeps:
        """
        Get AgentDeps with thread-scoped state for a given thread_id.

        Args:
            thread_id: Unique identifier for the conversation thread
        Returns:
            AgentDeps with thread-scoped state
        """
        # Init if thread is new
        if thread_id not in self._thread_states:
            self._thread_states[thread_id] = AgentDeps(
                state=AgentState(persona=Persona.CORE.value, auto_specialist=True),
                thread_id=thread_id,
                database=self.database,
                migration_target=config.agents.MIGRATION_TARGET,
                llm_provider=config.agents.LLM_PROVIDER,
            )
        return self._thread_states[thread_id]

    def get_usage_aggregator(self, user_id: Optional[str], thread_id: str) -> UsageAggregator:
        """
        Get or create a UsageAggregator for a user.

        Includes TTL-based cleanup to prevent memory leaks - aggregators unused
        for 24 hours are automatically removed.
        
        If user_id is None, uses thread_id as the dictionary key (but stores None in metadata).

        Args:
            user_id: Unique identifier for the user (None for anonymous)
            thread_id: Unique identifier for the conversation thread

        Returns:
            UsageAggregator instance for the user
        """
        now = time.perf_counter()
        
        # Use thread_id as key if user_id is None (for dictionary storage only)
        storage_key = user_id if user_id is not None else f"anonymous:{thread_id}"
        
        # Periodic cleanup: run at most once per hour
        if now - self._last_aggregator_cleanup > 3600:
            self._cleanup_stale_aggregators()
            self._last_aggregator_cleanup = now
        
        # Update access timestamp
        self._usage_aggregator_timestamps[storage_key] = now
        
        if storage_key not in self._usage_aggregators:
            metadata = UsageMetadata(
                user_id=user_id,
                thread_id=thread_id
            )
            self._usage_aggregators[storage_key] = UsageAggregator(metadata=metadata)
        return self._usage_aggregators[storage_key]

    def _cleanup_stale_aggregators(self) -> int:
        """
        Remove usage aggregators that haven't been accessed within the TTL.
        
        Returns:
            Number of aggregators removed
        """
        now = time.perf_counter()
        stale_users = [
            user_id for user_id, last_access in self._usage_aggregator_timestamps.items()
            if now - last_access > self._usage_aggregator_ttl
        ]
        
        for user_id in stale_users:
            del self._usage_aggregators[user_id]
            del self._usage_aggregator_timestamps[user_id]
        
        if stale_users:
            logger.debug(f"Cleaned up {len(stale_users)} stale usage aggregators")
        
        return len(stale_users)


    def _create_lifespan_handler(self) -> Lifespan[Self]:
        """
        Create a lifespan handler that cleans up all DuckDB threads on shutdown.
        
        Returns:
            Lifespan context manager for Starlette
        """
        # Capture self in closure for use in lifespan handler
        app_instance = self
        
        @asynccontextmanager
        async def lifespan(app: Self):
            """
            Lifespan context manager for application startup and shutdown.
            
            On startup: Logs startup message
            On shutdown: Cleans up all DuckDB connections and tables for all threads
            """
            # Startup
            logger.info("DrMChatApp starting up...")
            try:
                yield
            finally:
                # Shutdown - clean up all threads
                # Use finally to ensure cleanup runs even if cancelled
                logger.info("DrMChatApp shutting down, cleaning up DuckDB threads...")
                try:
                    # Run cleanup synchronously (cleanup_thread is not async)
                    # This will run even if the lifespan context is cancelled
                    thread_ids = list(app_instance.database.outputs.keys())
                    if thread_ids:
                        logger.debug(f"Cleaning up {len(thread_ids)} thread(s) with DuckDB data")
                        for thread_id in thread_ids:
                            try:
                                app_instance.database.cleanup_thread(thread_id)
                                logger.debug(f"Cleaned up thread '{thread_id}'")
                            except Exception as e:
                                logger.error(f"Error cleaning up thread '{thread_id}': {e}", exc_info=True)
                        logger.debug("DuckDB cleanup completed")
                    else:
                        logger.debug("No threads to clean up")
                except Exception as e:
                    logger.error(f"Error during DuckDB cleanup: {e}", exc_info=True)
        
        return lifespan

    async def data(self, request: Request) -> JSONResponse:
        """
        Retrieve stored data by reference with thread-scoped isolation.

        Query Parameters:
            ref (required): Reference string (view name or output reference)
            thread_id (optional): Thread ID for scoped lookup (default: "default")
            limit (optional): Max rows to return (default: -1 for all)

        Returns:
            JSONResponse with DataTable (columns + rows) or error

        Status Codes:
            200: Data found and returned
            400: Missing/invalid parameters
            404: Reference not found in thread
            500: Internal server error
        """
        try:
            # Get ref from query parameters
            ref = request.query_params.get("ref")
            if not ref:
                return JSONResponse(
                    content={"detail": "Missing required parameter: ref"},
                    status_code=HTTPStatus.BAD_REQUEST,
                )

            # Get optional thread_id parameter
            thread_id = request.query_params.get("thread_id")

            # Get optional limit parameter
            try:
                limit = int(request.query_params.get("limit", -1))
            except ValueError:
                return JSONResponse(
                    content={"detail": "Parameter 'limit' must be an integer"},
                    status_code=HTTPStatus.BAD_REQUEST,
                )

            logger.debug(
                f"Data request: ref={ref}, thread_id={thread_id}, limit={limit}"
            )
            df = self.database.get(ref, thread_id=thread_id)

            if df is not None:
                if limit > 0:
                    df = df.head(limit)
                table = DataTable.from_dataframe(df)
                return JSONResponse(content=table.model_dump(mode="json"))
            else:
                return JSONResponse(
                    content={
                        "detail": f"Reference '{ref}' not found in thread '{thread_id or 'default'}'."
                    },
                    status_code=HTTPStatus.NOT_FOUND,
                )
        except Exception as e:
            logger.error(f"Error in /data endpoint: {e}", exc_info=True)
            return JSONResponse(
                content={"detail": f"Internal server error: {str(e)}"},
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    async def handle_request(self, request: Request):
        """
        Handle incoming AG-UI requests with persona selection and streaming.

        This method:
        1. Parses the RunAgentInput from request body
        2. Determines appropriate persona (via delegation or forced)
        3. Builds AgentDeps with thread_id and database access
        4. Streams agent response via AGUIAdapter

        Args:
            request: Starlette Request object with AG-UI payload

        Returns:
            StreamingResponse with agent output
        """
        # Initialize runtime metrics for this request
        self.metrics = RuntimeMetrics()

        # Parse run_input for thread_id
        parse_start = time.perf_counter()
        try:
            run_input = AGUIAdapter.build_run_input(await request.body())
        except ValidationError as e:
            return Response(
                content=json.dumps(e.json()),
                media_type="application/json",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        self.metrics.request_parse_duration = time.perf_counter() - parse_start

        thread_id = run_input.thread_id
        logger.debug(f"Handling AG-UI request for thread: {thread_id}")

        # Parse agent state from run_input
        state = AgentState.model_validate(run_input.state)

        # Extract user_id from state (passed from frontend)
        user_id = state.user_id

        # Check quota BEFORE processing (if enforcement is enabled)
        if config.quota.ENFORCE_QUOTA and user_id is not None:
            quota_tracker = get_quota_tracker()
            is_within_quota, quota_error = quota_tracker.check_quota(user_id)
            if not is_within_quota and quota_error is not None:
                logger.warning(
                    f"Quota exceeded for user {user_id}: tokens "
                    f"({quota_error.current_usage}/{quota_error.limit})"
                )
                return JSONResponse(
                    content=quota_error.to_response_dict(),
                    status_code=HTTPStatus.TOO_MANY_REQUESTS,
                )

        # Set usage metadata context for OTEL span attribution
        usage_metadata = UsageMetadata(
            user_id=user_id,
            thread_id=thread_id
        )
        set_usage_metadata(usage_metadata)

        # Pre-process request to determine template and persona
        template, persona = await self._pre_process_request(run_input, thread_id)
        state.persona = persona.value  # Update state with selected persona

        logger.debug(f"Using persona: {persona.value} for thread: {thread_id}")

        # Initialize AG-UI adapter
        adapter_start = time.perf_counter()
        run_input.state = state.model_dump()
        adapter = CustomAGUIAdapter(
            persona.agent,
            run_input=run_input,
            accept=request.headers.get("accept")
        )
        self.metrics.adapter_init_duration = time.perf_counter() - adapter_start

        # Build deps for thread
        deps_start = time.perf_counter()
        deps = self.get_deps(thread_id)
        deps.state = state
        if template:
            logger.info(f"Inserting template '{template.name}' as system message for thread: {thread_id}")
            run_input.messages.append(template.to_system_message(deps))
        self.metrics.deps_build_duration = time.perf_counter() - deps_start

        # Log metrics summary before returning
        self.metrics.log_summary(thread_id)

        # Extract the last user query from messages for usage logging
        last_user_query = ""
        if run_input.messages:
            for msg in reversed(run_input.messages):
                if hasattr(msg, 'role') and msg.role == 'user':
                    content = msg.content if hasattr(msg, 'content') else str(msg)
                    # Handle content that might be a list (multi-part messages)
                    if isinstance(content, list):
                        last_user_query = " ".join(str(part) for part in content)
                    else:
                        last_user_query = str(content)
                    break

        async def on_complete_with_cleanup(run_result: AgentRunResult):
            """
            Handle post-run cleanup and processing.

            This async generator runs all post-processing tasks in parallel:
            - Usage metrics recording
            - Suggestions generation (updates deps.state.suggestions)
            - (Future tasks)

            After post-processing, yields a StateSnapshotEvent to sync
            the updated state (including suggestions) to the frontend.
            """
            from ..telemetry.otel import clear_usage_metadata
            try:
                await self._post_process_request(
                    run_result=run_result,
                    deps=deps,
                    user_id=user_id,
                    query=last_user_query,
                    persona=persona.value,
                )
                # Yield state snapshot with updated suggestions
                yield StateSnapshotEvent(snapshot=deps.state.model_dump())
            finally:
                # Use clear_usage_metadata() instead of reset_usage_metadata(token)
                # because this callback runs in a different async context than
                # where the token was created, which would raise ValueError
                clear_usage_metadata()

        return adapter.streaming_response(
            adapter.run_stream(
                deps=deps,
                model=self.model,
                model_settings=self.model_settings,
                on_complete=on_complete_with_cleanup
            )
        )
    
    def _increment_usage(
        self,
        thread_id: str,
        user_id: Optional[str] = None,
        query: str = "",
        persona: str = "",
        parent_operation: Optional[str] = None,
        enforce_quota: bool = False
    ):
        """
        Create a callback to increment usage metrics for the given thread and run result.

        Args:
            thread_id: Unique identifier for the conversation thread
            user_id: User identifier for quota tracking (None for anonymous)
            query: The user's query/prompt text for usage logging
            persona: The persona that provided the response
            parent_operation: Optional parent operation name for tracking hierarchical usage
            enforce_quota: If True, raises QuotaExceededError when user exceeds quota

        Returns:
            Async callback function to be called when the agent run completes
        """
        # Don't fall back to thread_id - allow None for anonymous users
        effective_user_id = user_id

        # Get provider_id and model_ref from config
        provider_id = config.agents.LLM_PROVIDER
        # Get model reference from the LLM integration
        integration = config.agents._get_llm_integration()
        tier = config.agents.DEFAULT_TIER
        if tier in integration._routers:
            router = integration._routers[tier]
            model_ref = (
                router.endpoint_config.endpoint.get('model') or
                router.endpoint_config.endpoint.get('model_id') or
                router.endpoint_config.endpoint.get('deployment') or
                f"{provider_id}-{tier}"
            )
        else:
            model_ref = f"{provider_id}-{tier}"

        async def on_complete_func(run_result: AgentRunResult):
            """Callback executed when the agent run completes."""
            run_usage: RunUsage = run_result.usage()

            # Create usage item
            usage_item = UsageItem(
                usage=run_usage,
                provider_id=provider_id,
                model_ref=model_ref,
                parent=parent_operation
            )

            # Get or create usage aggregator for this user
            aggregator = self.get_usage_aggregator(
                user_id=effective_user_id,
                thread_id=thread_id
            )

            # Add usage to aggregator (handles quota tracking)
            try:
                aggregator.add_usage_item(usage_item, enforce_quota=enforce_quota)
                logger.debug(
                    f"Usage recorded for thread {thread_id}: "
                    f"input={run_usage.input_tokens}, output={run_usage.output_tokens}, "
                    f"total_session={aggregator.total_tokens}, remaining={aggregator.remaining_tokens}"
                )
            except Exception as e:
                logger.error(f"Failed to record usage for thread {thread_id}: {e}")
                raise

            # Write to usage.jsonl file
            try:
                usage_writer = get_usage_writer()
                if usage_writer is not None:
                    # Extract response text from run_result
                    # AgentRunResult has .output property for the final output
                    response_text = str(run_result.output) if run_result.output else ""

                    usage_record = UsageRecord(
                        user_id=effective_user_id,
                        thread_id=thread_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        query=query,
                        response=response_text,
                        input_tokens=run_usage.input_tokens or 0,
                        output_tokens=run_usage.output_tokens or 0,
                        usage=run_usage,
                        provider=provider_id,
                        model=model_ref,
                        persona=persona
                    )
                    usage_writer.write(usage_record)
                    logger.debug(f"Usage record written for thread {thread_id}")
            except Exception as e:
                # Don't fail the request if usage logging fails
                logger.warning(f"Failed to write usage record for thread {thread_id}: {e}")

        return on_complete_func


    async def _pre_process_request(self, run_input: RunAgentInput, thread_id: str) -> tuple[Optional[Template], Persona]:
        """
        Pre-process the AG-UI request to determine template and persona.

        This method handles the complete agent selection logic:
        1. Determines if persona delegation is needed based on forced_persona and thread state
        2. Concurrently executes template agent (if enabled) and delegator agent (if needed)

        Args:
            run_input: AG-UI input with message history
            thread_id: Current thread ID

        Returns:
            Tuple of (Optional[AbstractTemplate], Persona)
        """
        self.metrics.preprocess_start = (t0 := time.perf_counter())

        # Get messages
        messages = AGUIAdapter.load_messages(run_input.messages)
        short_messages = self._short_message_context(messages)
        
        # Get state
        state = AgentState.model_validate(run_input.state)

        # Build tasks list
        tasks = [
            self._determine_template(short_messages, thread_id),
            self._determine_persona(messages, state, thread_id)
        ]

        self.metrics.preprocess_setup_duration = (tp := time.perf_counter()) - t0

        # Execute all tasks concurrently if any exist
        task_results = await asyncio.gather(*tasks)
        self.metrics.preprocess_gather_duration = time.perf_counter() - tp

        # Unpack results and store metrics
        template, persona = task_results

        # persona must be set by this point (either forced, from thread_state, or from delegation)
        assert isinstance(persona, Persona), "persona is not of type Persona"
        assert (template is None) or isinstance(template, Template), "template is not of type AbstractTemplate"

        self.metrics.preprocess_total_duration = time.perf_counter() - t0

        return template, persona

    @RuntimeMetrics.time_task("template")
    async def _determine_template(self, messages: list[ModelMessage], thread_id: str) -> Optional[Template]:
        """
        Use template agent to select appropriate template for the request.

        Converts the last message from run_input to pydantic-ai format and
        runs the template agent to choose the best template.

        Args:
            run_input: AG-UI input with message history
            thread_id: Current thread ID

        Returns:
            AbstractTemplate or None
        """
        # Run template agent
        response = await template_agent.run(
            message_history=messages,
            model=self.pre_processing_model,
            model_settings=self.pre_processing_model_settings
        )

        selection = response.output

        # Lookup template
        template = Templates.get_template(selection.value)

        if template:
            logger.debug(
                f"Template agent selected template for thread {thread_id}: {selection.name}"
            )
        return template

    @RuntimeMetrics.time_task("persona")
    async def _determine_persona(self, messages: list[ModelMessage], state: AgentState, thread_id: str) -> Persona:
        """
        Use delegator agent to select appropriate persona for the request.

        Converts the last message from run_input to pydantic-ai format and
        runs the delegator agent to choose the best persona.

        Args:
            run_input: AG-UI input with message history
            thread_id: Current thread ID

        Returns:
            Persona
        """
        if self.forced_persona:
            persona = self.forced_persona
        elif state.auto_specialist:
            # Run delegator agent
            delegation = await delegator_agent.run(
                message_history=[messages[-1]],
                model=self.pre_processing_model,
                model_settings=self.pre_processing_model_settings
            )

            logger.debug(
                f"Delegator selected persona for thread {thread_id}: {delegation.output.value}"
            )
            if delegation.output == Persona.CORE:
                # If CORE selected, then stay with current active persona
                persona = Persona(state.persona)
            else:
                persona = delegation.output
        else:
            persona = Persona(state.persona)
        
        return persona

    @RuntimeMetrics.time_task("suggestions")
    async def _run_suggestions(
        self,
        messages: list[ModelMessage],
        deps: AgentDeps,
    ) -> list:
        """
        Run the suggestions agent to generate follow-up suggestions.

        Updates deps.state.suggestions with the generated suggestions.

        Args:
            messages: Message history for context
            deps: Agent dependencies with thread context

        Returns:
            List of SuggestionItems
        """
        try:
            response = await suggestions_agent.run(
                message_history=messages,
                deps=deps,
                model=self.pre_processing_model,
                model_settings=self.pre_processing_model_settings
            )
            suggestions = response.output
            logger.debug(
                f"Suggestions agent generated {len(suggestions)} suggestions for thread {deps.thread_id}"
            )
            # Update state with suggestions
            deps.state.suggestions = suggestions
            return suggestions
        except Exception as e:
            logger.warning(f"Suggestions agent failed for thread {deps.thread_id}: {e}")
            return []

    async def _post_process_request(
        self,
        run_result: AgentRunResult,
        deps: AgentDeps,
        user_id: Optional[str],
        query: str,
        persona: str,
    ) -> dict[str, Any]:
        """
        Post-process the completed agent run with parallelized tasks.

        This method runs after the main agent completes and handles:
        - Recording usage metrics
        - Generating follow-up suggestions via suggestions agent
        - (Future: additional post-processing tasks can be added here)

        All tasks run in parallel using asyncio.gather for optimal performance.

        Args:
            run_result: The completed agent run result
            deps: Agent dependencies with thread context
            user_id: User identifier for usage tracking
            query: The user's query text for usage logging
            persona: The persona that handled the request

        Returns:
            Dictionary containing results from all post-processing tasks:
            - 'usage': None (usage tracking has no return value)
            - 'suggestions': List of suggested follow-up queries
        """
        thread_id = deps.thread_id

        # Create usage tracking callback and invoke it
        usage_on_complete = self._increment_usage(
            thread_id=thread_id,
            user_id=user_id,
            query=query,
            persona=persona,
        )

        messages = run_result.all_messages()

        # Build list of post-processing tasks to run in parallel
        tasks = {
            "usage": usage_on_complete(run_result),
            "suggestions": self._run_suggestions(messages, deps),
            # Future tasks can be added here, e.g.:
            # "analytics": self._run_analytics(run_result, deps),
        }

        # Run all tasks concurrently
        task_names = list(tasks.keys())
        task_coroutines = list(tasks.values())

        results = await asyncio.gather(*task_coroutines, return_exceptions=True)

        # Process results and log any exceptions
        output: dict[str, Any] = {}
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Post-processing task '{name}' failed for thread {thread_id}: {result}")
                output[name] = None
            else:
                output[name] = result

        logger.debug(f"Post-processing completed for thread {thread_id}: {list(output.keys())}")
        return output

    @staticmethod
    def _short_message_context(messages: list[ModelMessage], n: int = 5):
        """Returns the last n user/assistant messages for helper agents that only require a short context."""
        filtered: list[ModelMessage] = []
        ctr = 0

        for msg in reversed(messages):
            match msg:
                case ModelRequest():
                    parts = [part for part in msg.parts if isinstance(part, (TextPart, UserPromptPart)) and part.content]
                    if parts:
                        filtered.append(ModelRequest(parts=[part for part in msg.parts if isinstance(part, UserPromptPart)]))
                        ctr += 1
                case ModelResponse():
                    parts = [part for part in msg.parts if isinstance(part, TextPart) and part.content]
                    if parts:
                        filtered.append(ModelResponse(parts=parts))
                        ctr += 1
                case _:
                    continue
            if ctr >= n:
                break
        
        return list(reversed(filtered))
