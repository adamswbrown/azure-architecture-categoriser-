"""
Database Tools for Thread-Safe Agent Operations

This module provides database querying and visualization tools for agents,
with full thread-scoped isolation via AgentDeps dependency injection.

Tools:
- view_schema: Get schema information for a database view
- query_dataset: Execute SQL queries on views (direct SQL Server) or previous outputs (DuckDB)
- get_output: Retrieve stored DataFrame by reference
- render_table_to_user: Display data table in UI
- generate_chart: Create charts from stored data
- display_kpi_tiles: Display KPI tiles (with hidden support)

Thread Safety:
All tools use ctx.deps to access:
- ctx.deps.database: VirtualDatabase instance for data access
- ctx.deps.thread_id: Current thread ID for scoped operations

Data stored via query_dataset is automatically scoped to the current thread,
ensuring isolation between concurrent users. Outputs are stored in DuckDB tables,
not in-memory DataFrames.
"""
import csv
import json

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset
from typing import Literal, Optional
from pydantic import BaseModel

from ... import config
from ...deps import AgentDeps
from .charts import SUPPORTED_CHART_TYPES, ChartSpec

logger = config.get_logger('tools.db_tools')

# Init db toolset
db_toolset = FunctionToolset[AgentDeps](sequential=False)


@db_toolset.tool
async def view_schema(ctx: RunContext[AgentDeps], view_name: str) -> str:
    """
    Returns the schema of a view in the database.
    
    Supports both SQL Server and PostgreSQL views. The schema information
    includes column names, data types, and descriptions.
    
    Args:
        view_name: Name of the view to get schema for (e.g., "application_overview", "network_server_overview")
    
    Returns:
        String description of the view schema including all columns
    """
    logger.debug(f"Fetching schema for view: {view_name}")
    view = ctx.deps.database.views.get(view_name)
    if view is None:
        logger.error(f"View '{view_name}' not found. Available views: {list(ctx.deps.database.views.keys())}")
        raise ModelRetry(f"Error: No view found with the name '{view_name}'")
    
    db_type = view.database or "sqlserver"
    logger.debug(f"Schema retrieved for {view_name} ({db_type}): {len(view.columns)} columns")
    return view.schema


@db_toolset.tool(retries=5)
async def query_dataset(ctx: RunContext[AgentDeps], dataset: str, sql: str, description: str) -> str:
    """
    Run SQL query on a View (direct SQL Server/PostgreSQL) or previous output (DuckDB, thread-scoped).

    For database views: Executes SQL directly against SQL Server or PostgreSQL for real-time data access.
    The database type (SQL Server or PostgreSQL) is determined automatically from the view configuration.
    For thread outputs: Queries directly from DuckDB tables (stored in DuckDB, not in-memory).

    Results are automatically stored in DuckDB tables scoped to the current thread,
    making them accessible only to this conversation thread.

    Include a VERY BRIEF description that will be displayed to the user while
    the query executes. It should be no more than 15 words and explain the
    action you are taking in business friendly language.
    (E.g. "Analysing network traffic between VM_001 and VM_002")

    Args:
        dataset: Reference string for view or output (e.g., "application_overview", "output_1")
        sql: SQL query (SQL Server or PostgreSQL syntax for views depending on view config, DuckDB syntax for outputs)
        description: Brief user-facing description of the action

    Returns:
        Confirmation message with reference to stored result and preview

    Thread Isolation:
        - Views: Queried directly from SQL Server or PostgreSQL (real-time data)
        - Thread outputs: Queries thread-specific DuckDB tables (each thread has its own DuckDB connection)
        - Results stored in DuckDB tables scoped to thread (ctx.deps.thread_id)
        - Other threads cannot access this query's results

    Note:
        The dataset must be either a view name or a previous output reference (output_N).
        No joins between datasets are permitted - query one dataset at a time.
    """
    thread_id = ctx.deps.thread_id
    
    # Check if dataset is a view or a thread output
    is_view = dataset in ctx.deps.database.views
    is_output = dataset.startswith("output_")
    
    if is_view:
        # Execute SQL directly against SQL Server or PostgreSQL
        view = ctx.deps.database.views[dataset]
        db_type = view.database or "sqlserver"
        logger.debug(f"Executing {db_type} query on view '{dataset}' in thread '{thread_id}': {sql}")
        try:
            result_df = ctx.deps.database.execute_view_query(dataset, sql)
            logger.info(f"Query executed successfully in thread '{thread_id}': {result_df.shape[0]} rows, {result_df.shape[1]} columns")
        except Exception as e:
            error_msg = (
                f"Error running {db_type} query on view '{dataset}' in thread '{thread_id}': {e}\n"
                f"  SQL: {sql}\n"
                f"  Description: {description}"
            )
            logger.error(error_msg)
            raise ModelRetry(f"Error running SQL: {e}. Please try again with a valid SQL query.")
        
        # Store result in thread-scoped storage
        ref = ctx.deps.database.store(result_df, thread_id=thread_id)
        result_shape = (result_df.shape[0], result_df.shape[1])
        result_for_preview = result_df
        
    elif is_output:
        # Query directly from DuckDB tables (no in-memory DataFrames)
        logger.debug(f"Executing DuckDB SQL on output '{dataset}' in thread '{thread_id}': {sql}")
        try:
            result_df = ctx.deps.database.execute_output_query(dataset, sql, thread_id=thread_id)
            logger.info(f"Query executed successfully in thread '{thread_id}': {result_df.shape[0]} rows, {result_df.shape[1]} columns")
        except KeyError as ke:
            available_outputs = list(ctx.deps.database.outputs.get(thread_id, {}).keys())
            logger.error(f"Output '{dataset}' not found in thread '{thread_id}'. Available outputs: {available_outputs}")
            raise ModelRetry(f"Error: No output found with the name '{dataset}'. Available outputs: {available_outputs}") from ke
        except Exception as e:
            error_msg = (
                f"Error running DuckDB SQL on output '{dataset}' in thread '{thread_id}': {e}\n"
                f"  SQL: {sql}\n"
                f"  Description: {description}"
            )
            logger.error(error_msg)
            raise ModelRetry(f"Error running SQL: {e}. Please try again with a valid SQL query.") from e
        
        # Store result in thread-scoped storage (creates new DuckDB table)
        ref = ctx.deps.database.store(result_df, thread_id=thread_id)
        result_shape = (result_df.shape[0], result_df.shape[1])
        result_for_preview = result_df
    else:
        # Neither a view nor an output
        available_views = list(ctx.deps.database.views.keys())
        available_outputs = list(ctx.deps.database.outputs.get(thread_id, {}).keys())
        logger.error(f"Dataset '{dataset}' not found in thread '{thread_id}'. Available views: {available_views}, outputs: {available_outputs}")
        raise ModelRetry(f"Error: No dataset found with the name '{dataset}'. Available views: {available_views}, outputs: {available_outputs}")

    # Return confirmation with a preview of the result
    confirmation_msg = f'Executed SQL, result is `{ref}` with {result_shape[0]} rows and {result_shape[1]} columns.'

    if result_shape[0] > 5:
        table_string = result_for_preview.head().to_csv(
            sep="\t",             # TSV is safest for free-text cells
            index=False,
            header=True,          # short headers; avoid long prose
            na_rep="_",           # single-char null
            quoting=csv.QUOTE_MINIMAL,  # avoid quotes unless needed
            lineterminator="\n"
        )
        confirmation_msg += f'\nHere are the first 5 rows:\n{table_string}'
    else:
        table_string = result_for_preview.to_csv(
            sep="\t",             # TSV is safest for free-text cells
            index=False,
            header=True,          # short headers; avoid long prose
            na_rep="_",           # single-char null
            quoting=csv.QUOTE_MINIMAL,  # avoid quotes unless needed
            lineterminator="\n"
        )
        confirmation_msg += f'\nHere is the full result:\n{table_string}'

    return confirmation_msg


@db_toolset.tool(retries=5)
async def render_table_to_user(ctx: RunContext[AgentDeps], ref: str, title: str, hidden: bool = True):
    """
    Display the data contained in a table using a reference `ref`
    with a title `title` in the UI.

    Args:
        ref: reference string for the data
        title: title for the table to be shown to the user
        hidden: If True, the table will not render immediately. Use reveal_visualization to show it later.
    Returns:
        str: confirmation message, or dict with hidden flag if hidden=True
    """
    thread_id = ctx.deps.thread_id

    if ref not in ctx.deps.database.outputs.get(thread_id, {}):
        available_outputs = list(ctx.deps.database.outputs.get(thread_id, {}).keys())
        error_msg = (
            f"Error: No output found with the reference '{ref}' in thread '{thread_id}'. "
            f"Available outputs: {available_outputs}. "
            f"Please check the reference and try again."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)
    
    if hidden:
        # Generate tool call ID (same format as frontend expects)
        tool_call_id = f"table_{ref}_{title}".replace(' ', '_').replace('-', '_')
        
        # Store in hidden tool calls
        if thread_id not in ctx.deps.database.hidden_tool_calls:
            ctx.deps.database.hidden_tool_calls[thread_id] = {}
        
        ctx.deps.database.hidden_tool_calls[thread_id][tool_call_id] = {
            'type': 'table',
            'args': {'ref': ref, 'title': title},
            'hidden': True
        }
        
        logger.debug(f"Table '{title}' marked as hidden with ID: {tool_call_id}")
        # Return dict format for frontend to parse
        return {
            'hidden': True,
            'tool_call_id': tool_call_id,
            'message': f"Prepared table '{title}' with data from `{ref}` (hidden). Use reveal_visualization('{tool_call_id}') to display it."
        }
    
    return f"Rendered table '{title}' with data from `{ref}` in UI."


@db_toolset.tool(retries=5)
async def get_output(ctx: RunContext[AgentDeps], ref: str, limit: int, description: str) -> str:
    """
    Get an output DataFrame by reference string.

    Include a VERY BRIEF description that will be displayed to the user.
    It should be no more than 15 words and explain the action you are taking in business friendly language.
    (E.g. "Checking if VM_001 has traffic on port 1234" or "Reading data to find servers with high CPU usage")

    Args:
        ref: reference string to the output DataFrame
        limit: number of rows to return (-1 for all)
        description: briefly describe how this data helps you answer the user's question
    Returns:
        str: string representation of the DataFrame (limited to `limit` rows)
    """
    thread_id = ctx.deps.thread_id
    df = ctx.deps.database.get(ref, thread_id=thread_id)
    if df is None:
        logger.error(f"Output reference '{ref}' not found in thread '{thread_id}'. Available outputs: {list(ctx.deps.database.outputs.get(thread_id, {}).keys())}")
        return f"Error: No output found with the reference '{ref}'"

    if (limit >= 0) and (df.shape[0] > limit):
        n_rows = min(df.shape[0], limit)
        table_string = df.head(limit).to_csv(
            sep="\t",             # TSV is safest for free-text cells
            index=False,
            header=True,          # short headers; avoid long prose
            na_rep="_",           # single-char null
            quoting=csv.QUOTE_MINIMAL,  # avoid quotes unless needed
            lineterminator="\n"
        )
        return f"top {n_rows} rows of {ref}:\n" + table_string
    table_string = df.to_csv(
        sep="\t",             # TSV is safest for free-text cells
        index=False,
        header=True,          # short headers; avoid long prose
        na_rep="_",           # single-char null
        quoting=csv.QUOTE_MINIMAL,  # avoid quotes unless needed
        lineterminator="\n"
    )
    return f"All ({df.shape[0]}) rows of {ref}:\n" + table_string


@db_toolset.tool(retries=5)
async def generate_chart(ctx: RunContext[AgentDeps], chart_type: SUPPORTED_CHART_TYPES, ref: str, title: str, x: str, ys: list[str], hidden: bool = True):
    """
    Generate a chart from the data in a reference.

    For charts:
        - The `x` column values will be the labels for the x-axis
        - Each column specified in `ys` will be displayed as a separate series/dataset for comparison
    
    N.B. For doughnut charts, only one column should be specified in `ys` and the x column should contain the labels.

    Args:
        chart_type: type of chart to generate (e.g. 'bar', 'line', 'doughnut')
        ref: reference string to the output DataFrame
        title: title for the chart
        x: column name for the x-axis or labels
        ys: list of column names for the y-axis or values (for doughnut charts, use exactly one column)
        hidden: If True, the chart will not render immediately. Use reveal_visualization to show it later.
    Returns:
        ChartSpec: specification of the chart to be rendered (or dict with hidden flag if hidden=True)
    """
    thread_id = ctx.deps.thread_id
    df = ctx.deps.database.get(ref, thread_id=thread_id)
    if df is None:
        available_outputs = list(ctx.deps.database.outputs.get(thread_id, {}).keys())
        error_msg = (
            f"Error: No output found with the reference '{ref}' in thread '{thread_id}'. "
            f"Available outputs: {available_outputs}. "
            f"Please check the reference and try again."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)

    logger.debug(f"DataFrame columns: {df.columns.tolist()}")
    logger.debug(f"Label column: {x}")
    logger.debug(f"Value columns: {ys}")

    # Validate that the specified columns exist
    available_columns = df.columns.tolist()
    missing_columns = []
    
    if x not in available_columns:
        missing_columns.append(f"label column '{x}'")
    
    for y_col in ys:
        if y_col not in available_columns:
            missing_columns.append(f"value column '{y_col}'")
    
    if missing_columns:
        error_msg = (
            f"Error: Column(s) not found in data reference '{ref}': {', '.join(missing_columns)}. "
            f"Available columns: {available_columns}. "
            f"Please check the column names and try again."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)

    # Validate data is not empty
    if df.empty:
        error_msg = (
            f"Error: Data reference '{ref}' is empty (no rows). "
            f"Cannot generate a chart from empty data. "
            f"Please ensure the data contains at least one row."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)

    try:
        spec = ChartSpec.from_df(chart_type, df=df, label_col=x, value_cols=ys)
        
        # If hidden, store the chart spec and return a reference
        if hidden:
            thread_id = ctx.deps.thread_id
            # Use ref + title as identifier (agent can use this with reveal_visualization)
            tool_call_id = f"chart_{ref}_{title}".replace(' ', '_').replace('-', '_')
            
            # Store in hidden tool calls
            if thread_id not in ctx.deps.database.hidden_tool_calls:
                ctx.deps.database.hidden_tool_calls[thread_id] = {}
            
            # Convert ChartSpec to dict for storage
            spec_dict = spec.model_dump()
            ctx.deps.database.hidden_tool_calls[thread_id][tool_call_id] = {
                'type': 'chart',
                'args': {'chart_type': chart_type, 'ref': ref, 'title': title, 'x': x, 'ys': ys},
                'result': spec_dict,
                'hidden': True
            }
            
            logger.debug(f"Chart '{title}' marked as hidden with ID: {tool_call_id}")
            # Return a dict that includes the hidden flag and tool_call_id
            return {
                'hidden': True,
                'tool_call_id': tool_call_id,
                'message': f"Prepared {chart_type} chart '{title}' (hidden). Use reveal_visualization('{tool_call_id}') to display it.",
                'chart_spec': spec_dict  # Include spec for frontend when revealed
            }
        
    except KeyError as e:
        error_msg = (
            f"Error: Column not found when generating chart: {e}. "
            f"Available columns: {available_columns}. "
            f"Please verify the column names '{x}' and {ys} exist in the data."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)
    except (ValueError, TypeError) as e:
        error_msg = (
            f"Error: Cannot convert data to numeric values for chart generation: {e}. "
            f"Please ensure the value columns {ys} contain numeric data that can be converted to floats."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)
    except Exception as e:
        error_msg = (
            f"Error generating chart from reference '{ref}': {e}. "
            f"Chart type: {chart_type}, label column: '{x}', value columns: {ys}. "
            f"Please check the data format and try again."
        )
        logger.error(error_msg)
        raise ModelRetry(error_msg)

    return spec


class KpiTile(BaseModel):
    label: str
    value: float | int | str
    valueType: Optional[Literal["currency", "count", "percentage", "string"]] = None
    icon: Optional[Literal["cloud", "server", "database", "heartbeat", "piggy-bank"]] = None
    currencySymbol: Optional[str] = "$"


@db_toolset.tool(retries=5)
async def display_kpi_tiles(ctx: RunContext[AgentDeps], kpis: list[KpiTile], hidden: bool = True) -> dict | str:
    """
    Display a list of KPI tiles.
    
    Use the icon most appropriate to the KPI being displayed. Only return string values if the KPI is non-numeric.
    Use whole currency values for anything over $10 for nicer looking outputs. The cents won't matter for display purposes.

    Args:
        kpis: A list of KpiTile objects to display.
            - label: The label for the KPI.
            - value: The value for the KPI. (number or string)
            - valueType: The type of value (e.g., currency, count, percentage, custom).
            - icon: An optional icon to display with the KPI (e.g., cloud, server, database, heartbeat, piggy-bank).
            - currencySymbol: The currency symbol to use if valueType is currency. Defaults to "$".
        hidden: If True, the KPI tiles will not render immediately. Use reveal_visualization to show them later.
    
    Returns:
        str: Confirmation message, or dict with hidden flag if hidden=True
    """
    thread_id = ctx.deps.thread_id
    
    if hidden:
        # Generate tool call ID (same format as charts/tables)
        # Use a hash of the KPI data to ensure uniqueness, or a counter
        import hashlib
        kpis_str = json.dumps([kpi.model_dump() for kpi in kpis], sort_keys=True)
        kpis_hash = hashlib.md5(kpis_str.encode()).hexdigest()[:8]
        tool_call_id = f"kpi_{kpis_hash}"
        
        # Store in hidden tool calls
        if thread_id not in ctx.deps.database.hidden_tool_calls:
            ctx.deps.database.hidden_tool_calls[thread_id] = {}
        
        # Convert KpiTile objects to dicts for storage
        kpis_dict = [kpi.model_dump() for kpi in kpis]
        ctx.deps.database.hidden_tool_calls[thread_id][tool_call_id] = {
            'type': 'kpi',
            'args': {'kpis': kpis_dict},
            'result': kpis_dict,
            'hidden': True
        }
        
        logger.debug(f"KPI tiles marked as hidden with ID: {tool_call_id}")
        # Return a dict that includes the hidden flag and tool_call_id
        return {
            'hidden': True,
            'tool_call_id': tool_call_id,
            'message': f"Prepared {len(kpis)} KPI tiles (hidden). Use reveal_visualization('{tool_call_id}') to display them.",
            'kpis': kpis_dict  # Include KPIs for frontend when revealed
        }
    
    return "Displaying the KPI tiles defined in args to user"


@db_toolset.tool(retries=5)
async def reveal_visualization(ctx: RunContext[AgentDeps], tool_call_id: str) -> str:
    """
    Reveal a previously hidden visualization (chart, table, or KPI tiles) in the UI.
    
    Use this tool after calling generate_chart, render_table_to_user, or display_kpi_tiles with hidden=True
    to control when the visualization appears in the response.
    
    Args:
        tool_call_id: The identifier of the hidden visualization to reveal.
                     For charts: use the format "chart_{ref}_{title}" (spaces replaced with underscores)
                     For tables: use the tool_call_id returned from render_table_to_user
                     For KPIs: use the tool_call_id returned from display_kpi_tiles
    
    Returns:
        str: Special marker [VISUALIZATION:tool_call_id] that should be included in your text response
    """
    thread_id = ctx.deps.thread_id
    
    # Check if tool call exists in hidden tool calls
    if thread_id not in ctx.deps.database.hidden_tool_calls:
        return "Error: No hidden visualizations found for this thread."
    
    if tool_call_id not in ctx.deps.database.hidden_tool_calls[thread_id]:
        available_ids = list(ctx.deps.database.hidden_tool_calls[thread_id].keys())
        return f"Error: Tool call ID '{tool_call_id}' not found. Available IDs: {available_ids}"
    
    # Mark as revealed (remove hidden flag)
    tool_call_data = ctx.deps.database.hidden_tool_calls[thread_id][tool_call_id]
    tool_call_data['hidden'] = False
    
    tool_type = tool_call_data.get('type', 'unknown')
    logger.info(f"Revealed {tool_type} visualization: {tool_call_id}")
    
    # Return a special marker that will be parsed by the frontend to inject the visualization inline
    # The marker format is: [VISUALIZATION:tool_call_id]
    return f"[VISUALIZATION:{tool_call_id}]"
