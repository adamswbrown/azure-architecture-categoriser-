# TOOLS

## Default Behavior

**Always use `hidden=True` (default)**.

Visualizations render immediately when tools complete. This is the standard behavior for most use cases.

## Deferred Rendering (Template-Only)

Some templates (e.g., `application_summary`) use deferred rendering to interleave text with visualizations:

1. Call tools with `hidden=True`
2. Write explanatory text
3. Call `reveal_visualization(tool_call_id)` - returns `[VISUALIZATION:tool_call_id]`
4. Include the marker in your text where the visualization should appear

**Example:**
```
generate_chart(..., hidden=True) → tool_call_id: chart_output_1_Cost_Analysis
[Write text]: "Here's the breakdown:"
reveal_visualization('chart_output_1_Cost_Analysis') → "[VISUALIZATION:chart_output_1_Cost_Analysis]"
[Include in text]: "Here's the breakdown: [VISUALIZATION:chart_output_1_Cost_Analysis]"
```

## Tool Call ID Format

- Charts: `chart_{ref}_{title}`
- Tables: `table_{ref}_{title}`
- KPIs: `kpi_{hash}`
