# DESCRIPTION
Use this template ONLY when the user explicitly asks for a summary or overview of a **specific application with known name**, e.g.
- "Give me a summary of {App Name}"
- "Tell me about the {App Name} application"
- "Could you tell me more about that app?" (where the app name has been established in prior conversation)

# RESPONSE TEMPLATE
Give a comprehensive summary of the specified application, covering its overview, cost profile, server inventory, and modernization opportunities. For each paragraph use `#` header formatting for the section heading. After your response for each section add a `---` section break followed by two blank lines to segment the end of the paragraph. 

Follow this structure:
1. **Gather data**: Retrieve necessary data from `application_overview`, `application_cost_comparison`, and `server_overview_current` for the specified application.
2. **Introduction**: Briefly introduce the application and its significance. Do not include an `Introduction` header in your response.
3. **Key Metrics**: Present key metrics using `display_kpi_tiles`:
   - Number of machines
   - Number of environments
   - Migration Wave
   - Number of unique Operating Systems
   - Current on-prem annual cost
   - Future cloud annual cost estimate
4. **Application Quick Facts**: Summarize high-level details, including app owner and SME if available.
5. **Server Inventory**: Introduce and display a table using `render_table_to_user` with server details:
   - Machine
   - Environment
   - Operating System
   - OS Support Status
   - Power State
   - CPU Cores
   - CPU Usage (%)
   - RAM (GB)
   - RAM Usage (%)
   - Storage (GB)
6. **Modernization Advisor**: Identify components suitable for modernization and suggest strategies aligned with the {{MIGRATION_TARGET}} cloud provider.
7. **Cost Profile**: Analyze and visualize the cost breakdown:
   - Donut chart of current on-prem costs by category (e.g. `Hardware`, `Software`, etc.). To do so, select the data from the previously generated data from `application_cost_comparison` like this:
    - `SELECT \'Hardware\' as label, current_hardware_cost_annual as value FROM <previous_data>\\nUNION ALL SELECT \'Software\', current_software_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Data center\', current_data_center_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Virtualisation\', current_virtualisation_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Networking\', current_networking_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Backup\', current_backup_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Storage\', current_storage_cost_annual FROM <previous_data>`
   - Bar chart comparing current on-prem and estimated cloud costs. To do so, select the data from the previously generated data from `application_cost_comparison` like this:
    - `SELECT 'Current on-prem cost' as label, current_total_cost_annual as value FROM <previous_data> UNION ALL SELECT 'Estimated cloud cost' as label, cloud_total_cost_annual as value FROM <previous_data>`
8. **Cost Insights**: Provide insights on major cost components and potential savings in the cloud.
9. **User Engagement**: Conclude by inviting the user to explore specific modernization or migration strategies or ask further questions about the application's infrastructure and cost profile. Do not include an `User Engagement` header in your response.
