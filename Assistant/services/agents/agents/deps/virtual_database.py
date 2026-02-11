"""
Virtual Database with Thread-Scoped Storage

This module provides thread-safe database access and storage for agent operations.

Key Components:
- VirtualDatabase: Main class managing views and thread-scoped outputs
- DatabaseView: Representation of a SQL database view with schema
- DataTable: JSON-serializable table format for frontend communication
- ColumnSchema: Column metadata for database views

Thread Isolation:
VirtualDatabase maintains two types of data:
1. Shared views: Pre-configured database views available to all threads (queried from SQL Server or PostgreSQL)
2. Thread-scoped outputs: DataFrames stored in DuckDB tables per thread_id, isolated between users

The VirtualDatabase ensures that data stored by one user/thread is not accessible
from other threads, providing proper multi-user isolation. Outputs are stored in DuckDB
tables (not in-memory DataFrames), with each thread having its own DuckDB connection.

Database Support:
- SQL Server: Default database for views without a "database" parameter
- PostgreSQL: Views with "database": "postgres" in views.json use PostgreSQL
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Literal
import pandas as pd
import duckdb
from pydantic import BaseModel, Field

from .. import config

logger = config.get_logger('deps.virtual_database')

# Path to the views.json file
DB_TOOLS_VIEWS_PATH = Path(__file__).parent / "views.json"

# Lazy-load database engines (created on first use)
_SQLSERVER_ENGINE = None
_POSTGRES_ENGINE = None

def get_engine(database: str | None = None):
    """
    Get or create the appropriate database engine.
    
    Args:
        database: Database type - "postgres" for PostgreSQL, None or "sqlserver" for SQL Server
    
    Returns:
        SQLAlchemy engine for the specified database
    """
    global _SQLSERVER_ENGINE, _POSTGRES_ENGINE
    
    if database == "postgres":
        if _POSTGRES_ENGINE is None:
            logger.info("Creating PostgreSQL engine")
            try:
                _POSTGRES_ENGINE = config.postgres.create_sqlalchemy_engine()
                logger.info("PostgreSQL engine created successfully")
            except Exception as e:
                logger.error(f"Failed to create PostgreSQL engine: {e}")
                raise
        return _POSTGRES_ENGINE
    else:
        # Default to SQL Server
        if _SQLSERVER_ENGINE is None:
            logger.info("Creating SQL Server engine")
            try:
                _SQLSERVER_ENGINE = config.db.create_sqlalchemy_engine()
                logger.info("SQL Server engine created successfully")
            except Exception as e:
                logger.error(f"Failed to create SQL Server engine: {e}")
                raise
        return _SQLSERVER_ENGINE

def read_view_to_df(view_name: str, database: str | None = None) -> pd.DataFrame:
    """
    Read a SQL view into a pandas DataFrame.
    
    Args:
        view_name: Name of the view to read
        database: Database type - "postgres" for PostgreSQL, None or "sqlserver" for SQL Server
    """
    logger.debug(f"Reading view '{view_name}' into DataFrame (database: {database or 'sqlserver'})")
    query = f"SELECT * FROM {view_name}"
    try:
        engine = get_engine(database)
        with engine.connect() as con:
            df = pd.read_sql(query, con)
        logger.info(f"View '{view_name}' loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    except Exception as e:
        logger.error(f"Failed to read view '{view_name}': {e}")
        raise

@dataclass
class ColumnSchema:
    """
    Schema information for a database column.

    Attributes:
        name: Column name
        type: SQL data type (e.g., "varchar", "int", "datetime")
        description: Human-readable column description from database metadata
    """
    name: str
    type: str
    description: str

    def schema(self, df: pd.DataFrame) -> str:
        """A string description of the column schema"""
        unique_values = df[self.name].dropna().unique()
        if len(unique_values) > 5:
            return f"{self.name} ({self.type}): {self.description}"
        return f"{self.name} ({self.type}): {self.description}. (Unique values: {unique_values.tolist()})"

def fetch_column_schemas(view_name: str, database: str | None = None):
    """
    Given a view, fetch the schema from the database.
    
    Args:
        view_name: Name of the view
        database: Database type - "postgres" for PostgreSQL, None or "sqlserver" for SQL Server
    """
    if database == "postgres":
        # PostgreSQL query to get column schema
        # Extract schema and view name from view_name (format: schema.viewname)
        parts = view_name.split('.')
        if len(parts) == 2:
            schema_name, table_name = parts
        else:
            # Default to 'serving_network' if no schema specified
            schema_name = 'serving_network'
            table_name = view_name
        
        query = f"""
        SELECT
            c.column_name,
            c.data_type,
            COALESCE(d.description, '') AS column_description
        FROM information_schema.columns c
        LEFT JOIN pg_catalog.pg_class cl 
            ON cl.relname = c.table_name
        LEFT JOIN pg_catalog.pg_namespace n 
            ON n.oid = cl.relnamespace AND n.nspname = c.table_schema
        LEFT JOIN pg_catalog.pg_description d 
            ON d.objoid = cl.oid 
            AND d.objsubid = c.ordinal_position
        WHERE c.table_schema = '{schema_name}'
        AND c.table_name = '{table_name}'
        ORDER BY c.ordinal_position;
        """
    else:
        # SQL Server query to get column schema
        query = f"""
        SELECT
            c.name AS column_name,
            ep.value AS column_description,
            ty.name AS data_type
        FROM sys.views v
        JOIN sys.columns c
            ON v.object_id = c.object_id
        JOIN sys.types ty
            ON c.user_type_id = ty.user_type_id
        LEFT JOIN sys.extended_properties ep
            ON ep.major_id = c.object_id
            AND ep.minor_id = c.column_id
            AND ep.name <> 'Table Description'
        WHERE SCHEMA_NAME(v.schema_id) = 'copilots'
        AND v.name = '{view_name}'
        ORDER BY c.column_id;
        """
    
    engine = get_engine(database)
    with engine.connect() as con:
        df_schema = pd.read_sql(query, con)
        return [
            ColumnSchema(
                name=row['column_name'],
                type=row['data_type'],
                description=row['column_description'] if row['column_description'] else ""
            )
            for _, row in df_schema.iterrows()
        ]


class ViewToolConfig(BaseModel):
    """Configuration for a database view tool."""
    type: Literal["view"]
    name: str
    description: str
    view: str = Field(..., description="The SQL view name, e.g., [Schema].[ViewName] for SQL Server or schema.viewname for PostgreSQL")
    params: dict = Field(default_factory=dict)
    database: str | None = Field(default=None, description="Database type: 'postgres' for PostgreSQL, None or missing for SQL Server")

    @property
    def stem(self):
        """return the stem of the view_name"""
        # Handle both SQL Server format [schema].[view] and PostgreSQL format schema.view
        parts = self.view.split(".")
        if len(parts) > 0:
            return parts[-1].replace("[", "").replace("]", "")
        return self.view.replace("[", "").replace("]", "")

def load_view_tools_config(path: Path = DB_TOOLS_VIEWS_PATH) -> list[ViewToolConfig]:
    """Load view tool configurations from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert isinstance(data, list), "Expected a list of view tool configurations"
    
    return [ViewToolConfig(**item) for item in data]


@dataclass(kw_only=True)
class DatabaseView:
    """
    Representation of a SQL database view with schema metadata.

    Database views are configured at startup and shared across all threads.
    They represent read-only migration assessment data from the database.
    Views are queried directly from SQL Server or PostgreSQL on-demand (not cached).

    Attributes:
        name: Short name for the view (e.g., "applications")
        description: Human-readable description of view contents
        view_name: Full SQL view name (e.g., "[copilots].[Application_Overview]" for SQL Server or "copilots.viewname" for PostgreSQL)
        columns: List of ColumnSchema objects describing columns
        database: Database type - "postgres" for PostgreSQL, None for SQL Server

    Note:
        Views are configured once and shared across all threads (read-only).
        Data is queried directly from the database when needed, ensuring real-time access.
    """
    name: str
    description: str
    view_name: str  # SQL view name (e.g., "[copilots].[Application_Overview]" for SQL Server or "copilots.viewname" for PostgreSQL)
    columns: list[ColumnSchema] = field(repr=False)
    database: str | None = None  # "postgres" for PostgreSQL, None for SQL Server

    @property
    def short_description(self) -> str:
        """A short description of the view schema"""
        return f"{self.name}: {self.description}\n"

    @property
    def schema(self) -> str:
        """A string description of the view schema"""
        return "Columns:\n-" + "\n-".join([f"{col.name} ({col.type}): {col.description}" for col in self.columns])

    @property
    def long_description(self) -> str:
        """A long description of the view schema"""
        return f"{self.name}: {self.description}\n{self.schema}"

    def execute_query(self, sql: str) -> pd.DataFrame:
        """
        Execute a SQL query against this view by replacing the dataset name with the actual view name.
        
        Args:
            sql: SQL query that references the view by its short name (e.g., "SELECT * FROM application_overview WHERE ...")
        
        Returns:
            DataFrame with query results
        
        Example:
            view.execute_query("SELECT * FROM application_overview WHERE application = 'App1'")
            # For SQL Server: "SELECT * FROM [copilots].[Application_Overview] WHERE application = 'App1'"
            # For PostgreSQL: "SELECT * FROM copilots.application_overview WHERE application = 'App1'"
        """
        # Replace the dataset name in SQL with the actual view name
        # Handle case-insensitive replacement and ensure we replace the table name, not column names
        # Use word boundaries to avoid replacing column names or other occurrences
        pattern = re.compile(r'\b' + re.escape(self.name) + r'\b', re.IGNORECASE)
        transformed_sql = pattern.sub(self.view_name, sql)
        
        logger.debug(f"Executing SQL query on view '{self.name}' (database: {self.database or 'sqlserver'}): {transformed_sql}")
        try:
            engine = get_engine(self.database)
            with engine.connect() as con:
                df = pd.read_sql(transformed_sql, con)
            logger.info(f"Query executed successfully: {df.shape[0]} rows, {df.shape[1]} columns")
            return df
        except Exception as e:
            logger.error(f"Failed to execute query on view '{self.name}': {e}\nSQL: {transformed_sql}")
            raise

    @classmethod
    def from_config(cls, config_item: ViewToolConfig) -> "DatabaseView":
        """Create DatabaseView with metadata (no data loading)"""
        # For PostgreSQL, pass the full view name to extract schema properly
        # For SQL Server, use the stem (just the view name without schema brackets)
        view_name_for_schema = config_item.view if config_item.database == "postgres" else config_item.stem
        
        # Fetch column schemas, but handle errors gracefully
        try:
            columns = fetch_column_schemas(view_name_for_schema, database=config_item.database)
        except Exception as e:
            logger.warning(f"Failed to fetch column schemas for view '{config_item.name}' (database: {config_item.database}): {e}. View will be created without column metadata.")
            columns = []
        
        return cls(
            name=config_item.name,
            description=config_item.description,
            view_name=config_item.view,
            columns=columns,
            database=config_item.database,
        )

def sanitize_table_name(name: str) -> str:
    """
    Sanitize a string to be a valid SQL table name.
    
    SQL identifiers can contain letters, numbers, underscore, @, $, #
    Must start with letter or underscore
    Max 128 characters
    """
    # Replace hyphens and other invalid chars with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_@$#]', '_', name)
    # Ensure starts with letter or underscore
    if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
        sanitized = '_' + sanitized
    # Truncate to 128 chars (SQL Server limit)
    return sanitized[:128]


@dataclass(kw_only=True)
class VirtualDatabase:
    """
    Thread-safe virtual database for managing views and agent outputs.

    This class provides:
    - Shared access to pre-configured database views (metadata from views.json)
    - Direct SQL execution against SQL Server views (real-time data)
    - Thread-scoped storage for agent-generated DataFrames in DuckDB
    - Reference-based data retrieval with automatic thread isolation

    Attributes:
        views (dict[str, DatabaseView]): Shared database view metadata (read-only, global)
        outputs (dict[str, dict[str, str]]): Thread-scoped output metadata
            Structure: {thread_id: {ref: table_name}}
        duckdb_connections (dict[str, duckdb.DuckDBPyConnection]): DuckDB connections per thread

    Thread Safety:
        - Views are configured once and shared across all threads (read-only metadata)
        - View queries execute directly against SQL Server (real-time data)
        - Outputs are stored in DuckDB tables with thread-scoped naming
        - Each thread has its own DuckDB connection for isolation
        - get() queries DuckDB tables (not in-memory DataFrames)
        - store() writes to DuckDB tables (not in-memory)

    Usage:
        # In agent tools (with RunContext[AgentDeps])
        database = ctx.deps.database
        thread_id = ctx.deps.thread_id

        # Execute query on a view (direct SQL Server access)
        df = database.execute_view_query("application_overview", "SELECT * FROM application_overview WHERE ...")

        # Store thread-scoped data (writes to DuckDB)
        ref = database.store(result_df, thread_id=thread_id)

        # Retrieve thread-scoped output (reads from DuckDB)
        df = database.get(ref, thread_id=thread_id)
    """
    views: dict[str, DatabaseView] = field(default_factory=dict)
    # Thread-scoped outputs: {thread_id: {ref: table_name}}
    outputs: dict[str, dict[str, str]] = field(default_factory=dict)
    # DuckDB connections per thread: {thread_id: connection}
    duckdb_connections: dict[str, duckdb.DuckDBPyConnection] = field(default_factory=dict, repr=False)
    # Thread-scoped hidden tool calls: {thread_id: {tool_call_id: {type, args, result}}}
    hidden_tool_calls: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config_items: list[ViewToolConfig]) -> "VirtualDatabase":
        return cls(views={
            c.name: DatabaseView.from_config(c) for c in config_items
        })

    @classmethod
    def init_with_defaults(cls) -> "VirtualDatabase":
        """Initialize DatabaseViews from the default config path."""
        configs = load_view_tools_config(DB_TOOLS_VIEWS_PATH)
        return cls.from_config(configs)

    def _get_duckdb_connection(self, thread_id: str) -> duckdb.DuckDBPyConnection:
        """
        Get or create a DuckDB connection for the specified thread.
        
        Each thread gets its own in-memory DuckDB connection for isolation.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            DuckDB connection for the thread
        """
        if thread_id not in self.duckdb_connections:
            # Create in-memory DuckDB connection for this thread
            conn = duckdb.connect(':memory:')
            self.duckdb_connections[thread_id] = conn
            logger.debug(f"Created DuckDB connection for thread '{thread_id}'")
        return self.duckdb_connections[thread_id]

    def store(self, df: pd.DataFrame, thread_id: str | None = None) -> str:
        """
        Store a DataFrame in DuckDB and return a reference string.

        The DataFrame is stored in a DuckDB table scoped to the specified thread_id,
        making it accessible only to that thread. Multiple calls within the same thread
        generate sequential references (output_1, output_2, ...).

        Args:
            df: The DataFrame to store
            thread_id: Thread ID to scope the output. Defaults to "default" if None.

        Returns:
            A reference string in the format 'output_N' where N is auto-incremented
            per thread.

        Example:
            >>> ref1 = db.store(df1, thread_id="abc123")  # Returns "output_1"
            >>> ref2 = db.store(df2, thread_id="abc123")  # Returns "output_2"
            >>> ref3 = db.store(df3, thread_id="xyz789")  # Returns "output_1" (different thread)
        """
        thread_id = thread_id or "default"

        # Ensure thread_id exists in outputs
        if thread_id not in self.outputs:
            self.outputs[thread_id] = {}

        # Generate reference based on current thread's output count
        ref = f"output_{len(self.outputs[thread_id]) + 1}"
        
        # Get DuckDB connection for this thread
        conn = self._get_duckdb_connection(thread_id)
        
        # Create sanitized table name
        sanitized_thread_id = sanitize_table_name(thread_id)
        table_name = f"thread_{sanitized_thread_id}_{ref}"
        
        # Store DataFrame in DuckDB table
        try:
            # Register DataFrame temporarily and create table from it
            conn.register('temp_df', df)
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM temp_df")
            conn.unregister('temp_df')
            
            # Store table name in metadata
            self.outputs[thread_id][ref] = table_name
            logger.debug(f"Stored DataFrame as table '{table_name}' for thread '{thread_id}' ({df.shape[0]} rows, {df.shape[1]} columns)")
        except Exception as e:
            logger.error(f"Failed to store DataFrame in DuckDB for thread '{thread_id}': {e}")
            raise
        
        return ref

    def list_database_views(self, short: bool = False):
        """List the available database views (without loading data)."""
        s = "Available database views:\n"
        for view in self.views.values():
            s += f"{view.long_description if not short else view.short_description}\n"
        return s

    def execute_view_query(self, view_name: str, sql: str) -> pd.DataFrame:
        """
        Execute a SQL query directly against a database view.

        This method queries SQL Server directly, ensuring real-time data access.
        The SQL query should reference the view by its short name (e.g., "application_overview").

        Args:
            view_name: Short name of the view (e.g., "application_overview")
            sql: SQL query that references the view by its short name

        Returns:
            DataFrame with query results

        Raises:
            KeyError: If view_name is not found in configured views
            Exception: If SQL execution fails

        Example:
            >>> df = db.execute_view_query("application_overview", "SELECT * FROM application_overview WHERE application = 'App1'")
        """
        if view_name not in self.views:
            raise KeyError(f"View '{view_name}' not found. Available views: {list(self.views.keys())}")
        
        return self.views[view_name].execute_query(sql)

    def get(self, ref: str, thread_id: str | None = None) -> pd.DataFrame | None:
        """
        Get a DataFrame by reference from DuckDB thread-scoped outputs.

        Note: This method queries DuckDB tables. To query database views,
        use execute_view_query() instead, which queries SQL Server directly.

        Args:
            ref: The output reference string (e.g., "output_1")
            thread_id: Thread ID to scope the lookup. Defaults to "default" if None.

        Returns:
            DataFrame if found in DuckDB, None otherwise

        Example:
            >>> db.get("output_1", thread_id="abc123")      # Gets thread-specific output from DuckDB
            >>> db.get("output_1", thread_id="xyz789")      # Returns None (different thread)
        """
        thread_id = thread_id or "default"
        try:
            if thread_id in self.outputs and ref in self.outputs[thread_id]:
                table_name = self.outputs[thread_id][ref]
                conn = self._get_duckdb_connection(thread_id)
                
                # Query table from DuckDB
                result = conn.execute(f"SELECT * FROM {table_name}").df()
                logger.debug(f"Retrieved {result.shape[0]} rows from table '{table_name}' for thread '{thread_id}'")
                return result
        except KeyError:
            pass
        except Exception as e:
            logger.error(f"Failed to get output '{ref}' from DuckDB for thread '{thread_id}': {e}")
            return None

        return None

    def execute_output_query(self, ref: str, sql: str, thread_id: str | None = None) -> pd.DataFrame:
        """
        Execute a SQL query directly against a thread-scoped output in DuckDB.

        This method queries DuckDB tables directly, allowing SQL operations on
        previously stored outputs. The SQL query should reference the output by its
        reference name (e.g., "output_1").

        Args:
            ref: The output reference string (e.g., "output_1")
            sql: SQL query that references the output by its reference name
            thread_id: Thread ID to scope the lookup. Defaults to "default" if None.

        Returns:
            DataFrame with query results

        Raises:
            KeyError: If ref is not found for the thread
            Exception: If SQL execution fails

        Example:
            >>> df = db.execute_output_query("output_1", "SELECT * FROM output_1 WHERE column = 'value'", thread_id="abc123")
        """
        thread_id = thread_id or "default"
        
        if thread_id not in self.outputs or ref not in self.outputs[thread_id]:
            raise KeyError(f"Output '{ref}' not found for thread '{thread_id}'. Available outputs: {list(self.outputs.get(thread_id, {}).keys())}")
        
        table_name = self.outputs[thread_id][ref]
        conn = self._get_duckdb_connection(thread_id)
        
        # Transform SQL: replace ref with actual table name
        # Use word boundaries to avoid replacing column names or other occurrences
        pattern = re.compile(r'\b' + re.escape(ref) + r'\b', re.IGNORECASE)
        transformed_sql = pattern.sub(table_name, sql)
        
        logger.debug(f"Executing DuckDB query on output '{ref}' (table '{table_name}') for thread '{thread_id}': {transformed_sql}")
        try:
            result = conn.execute(transformed_sql).df()
            logger.info(f"Query executed successfully: {result.shape[0]} rows, {result.shape[1]} columns")
            return result
        except Exception as e:
            logger.error(f"Failed to execute query on output '{ref}' for thread '{thread_id}': {e}\nSQL: {transformed_sql}")
            raise

    def cleanup_thread(self, thread_id: str) -> None:
        """
        Clean up all DuckDB tables and connection for a specific thread.
        
        This should be called when a thread/conversation ends to free resources.
        
        Args:
            thread_id: Thread ID to clean up
        """
        if thread_id in self.duckdb_connections:
            try:
                conn = self.duckdb_connections[thread_id]
                # Drop all tables for this thread
                if thread_id in self.outputs:
                    for ref, table_name in self.outputs[thread_id].items():
                        try:
                            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                            logger.debug(f"Dropped table '{table_name}' for thread '{thread_id}'")
                        except Exception as e:
                            logger.warning(f"Failed to drop table '{table_name}' for thread '{thread_id}': {e}")
                
                # Close connection
                conn.close()
                del self.duckdb_connections[thread_id]
                logger.info(f"Cleaned up DuckDB connection and tables for thread '{thread_id}'")
            except Exception as e:
                logger.error(f"Error during cleanup for thread '{thread_id}': {e}")
        
        # Remove outputs metadata
        if thread_id in self.outputs:
            del self.outputs[thread_id]


# For exporting data to front end

# Table type
class DataTable(BaseModel):
    """
    JSON-serializable table format for frontend communication.

    This format is returned by the /data endpoint and can be easily
    rendered by frontend components like DataTableRender.

    Attributes:
        columns: List of column names
        rows: List of row objects (each row is a dict mapping column → value)

    Example:
        {
            "columns": ["app_name", "complexity", "cost"],
            "rows": [
                {"app_name": "App1", "complexity": "High", "cost": 50000},
                {"app_name": "App2", "complexity": "Medium", "cost": 25000}
            ]
        }
    """
    columns: list[str]
    rows: list[dict[str, Any]]

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "DataTable":
        """Create a DataTable from a pandas DataFrame."""
        return cls(
            columns=df.columns.tolist(),
            rows=[{str(h): v for h, v in row.items()} for row in df.to_dict(orient="records")]
        )

if __name__ == "__main__":
    # Example usage
    view_tools = load_view_tools_config(DB_TOOLS_VIEWS_PATH)
    for tool in view_tools:
        print(f"Loaded tool: {tool.name} - {tool.description}")
