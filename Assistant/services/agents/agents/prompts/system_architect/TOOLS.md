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

---

## Architecture Recommendation Tool

You have access to `get_architecture_recommendation` which scores an application against the Azure Architecture Catalog (~170 reference architectures) using a multi-dimensional scoring engine.

### When to Use

Use `get_architecture_recommendation` when the user asks about:
- Which Azure architecture pattern fits an application
- Architecture recommendations for migration
- What Azure services or landing zone to target
- Comparing architecture options for an application

Use `list_scorable_applications` if you need to confirm which applications are available for scoring.

### How to Present Results

The tool returns structured text with recommendations and a DuckDB data reference. Use this workflow:

1. **Call** `get_architecture_recommendation(application_name="...", max_recommendations=5)`
2. **Display KPI tiles** with 4 headline metrics from the result:
   - Top match score (percentage, `cloud` icon)
   - Treatment (string, `cloud` icon)
   - Confidence (string, `heartbeat` icon)
   - Eligible architectures count (count, `database` icon)
3. **Write narrative** discussing the top recommendation: why it fits, key considerations, and core Azure services. Include the Microsoft Docs link from the result.
4. **Generate a bar chart** from the stored data reference showing architecture names vs scores
5. **Render a table** from the stored data reference for the full recommendation list
6. Briefly discuss the **runner-up** alternative and when it might be preferred

### Combining with Other Tools

After presenting architecture recommendations, you can enrich the analysis:
- Query `application_cost_comparison` to show current vs cloud cost alongside the recommendation
- Query `server_overview_current` to discuss the server footprint that drives the recommendation
- Query `network_application_overview` to discuss integration complexity
