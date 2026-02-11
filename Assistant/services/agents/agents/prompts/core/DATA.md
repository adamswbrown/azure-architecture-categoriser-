# DATA
Below is a schema of the database views you can query. Use these views to inform your responses.
{{DATA_SCHEMA}}

# QUERYING DATA
Use the `query_dataset` tool to run SQL queries against the database views. Note:
- You can only query one dataset (view or previous output) at a time; no joins between datasets are allowed.
- The dataset name must be the same name used in the table referenced within the sql query (e.g., "SELECT * FROM application_overview WHERE ...").
- For database views: Queries execute directly against SQL Server or PostgreSQL for real-time data access. Use the appropriate SQL syntax based on the view's database type (SQL Server syntax for SQL Server views, PostgreSQL syntax for PostgreSQL views).
- For previous outputs (output_N): Uses DuckDB syntax to query stored DataFrames.
