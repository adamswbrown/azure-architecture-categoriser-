# DESCRIPTION
Use this template ONLY when the user explicitly asks for a user asks about migration readiness of a **specific application with known name**, e.g.
- “Give me a full migration readiness summary for {App Name}.”
- "Is my {App Name} app ready for migration?"
- "Is it ready for migration?" (where the app name has been established in prior conversation)


# RESPONSE TEMPLATE
Give a comprehensive summary of the specified application's migration readiness assessment, covering the application's overview, complexity, risks and blockers, 6R treatments, and resource team requirements for its migration. For each paragraph use `#` header formatting for the section heading. After your response for each section add a `---` section break followed by two blank lines to segment the end of the paragraph. 

Follow this structure:
1. **Gather data** Retrieve data from `application_overview`, `application_cost_comparison`, `server_overview_current`, and `network_application_overview`.
2. **Introduction**: Write 1–2 sentences introducing the migration readiness summary. Clarify that this is planning readiness, not “ready-to-migrate today.”. Do not include an `Introduction` header in your response.
3. **Key Metrics**: Present key metrics using `display_kpi_tiles`:
    - Number of machines
    - Number of environments
    - Migration Wave
    - Number of unique Operating Systems
    - 6R Treatment (`assigned_migration_strategy` in `application_overview`)
    - Current on-prem annual cost (do NOT show decimal places)
    - Future cloud annual cost estimate (do NOT show decimal places)
4. **Application Quick Facts**: Summarize high-level details, including app owner and SME if available. Short bullet section:
    - App owner
    - App SME
    - Business criticality (`pii_data` column in `application_overview`)
    - Data classification (`business_critical` column in `application_overview`)
    - Any notable constraints or cloud blockers (e.g. out of support OS, `CloudVMReadiness`, `CloudReadinessIssues`, `DataCollectionIssues`)
5. **Complexity Analysis**: Write a section that summarizes the application's complexity and migration readiness. Include the following datapoints: 
    - Dependencies (`communicates` in `network_application_overview`)
    - OS versions (`unique_operating_systems` in `application_overview`)
    - Database engines (identify db engines based on data in `detected_app_components` in `application_overview`)
    - Integration count (`integration_count` in `network_application_overview`)
    - HA/DR requirements (`high_availiability` and `disaster_recovery` in `application_overview`)
    - Environment parity (compare the number of servers in each environment and analyse major differences. This could indicate missing environments or a lack of parity between environments. In that case, ask user if they have mapped all servers to the application)
6.  **Risk & Blockers**: Write a short paragraph introducing the `Risk & Blockers` table calling out the importance of mitigating risks/blockers for a successful cloud migration. Present a table using `render_table_to_user` showing the following columns:
    - Risk / Blocker
    - Impact
    - Mitigation
    Examples can include:
    - Unsupported OS or DB versions
    - Unknown integration paths
    - Data discovery coverage (`software_data` and `assessment_data` in `server_overview_current`)
    Use the following SQL syntax to generate the table data:
    - `SELECT '<resource_type_name>' AS "Resource Type", '<text>' AS "Why Required", '<text>' AS "Work Areas" UNION ALL SELECT '<resource_type_name>' AS "Resource Type", '<text>' AS "Why Required", '<text>' AS "Work Areas"`
7. **6R Treatment Summary**: Write a section that summarizes the application's 6R treatment readiness.
    Summarise the following information:
    - Assigned treatments (`assigned_treatment` and `assigned_target` in `server_overview_current`)
    - Why this treatment makes sense
    - Expected changes (e.g., config, DB refactor, dependencies)
8. **Resource Types Required**: Write a section that outlines the resources required to migrate the application. Explain why each resource type is required and how it will be used. Be specific. Determine roles required based on:
     - Treatment type
     - Technologies detected
     - Integration pattern
     - SQL or DB complexity
     - Number of servers/environments
9. **TCO Summary**: Write an introductory 1-2 sentences that summarizes the application's TCO. Lead with `Let’s explore the cost profile for this application.`. Following thatAnalyze and visualize the cost breakdown:
   - Donut chart of current on-prem costs by category (e.g. `Hardware`, `Software`, etc.). To do so, select the data from the previously generated data from `application_cost_comparison` like this:
    - `SELECT \'Hardware\' as label, current_hardware_cost_annual as value FROM <previous_data>\\nUNION ALL SELECT \'Software\', current_software_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Data center\', current_data_center_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Virtualisation\', current_virtualisation_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Networking\', current_networking_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Backup\', current_backup_cost_annual FROM <previous_data>\\nUNION ALL SELECT \'Storage\', current_storage_cost_annual FROM <previous_data>`
   - Bar chart comparing current on-prem and estimated cloud costs. To do so, select the data from the previously generated data from `application_cost_comparison` like this:
    - `SELECT 'Current on-prem cost' as label, current_total_cost_annual as value FROM <previous_data> UNION ALL SELECT 'Estimated cloud cost' as label, cloud_total_cost_annual as value FROM <previous_data>`
10. **Cost Insights**: Write a section that outlines the currently biggest cost components and how that cost can be reduced in the cloud as dotpoints.
11. **Server Inventory Appendix**: Introduce and display a table using `render_table_to_user` with server details:
    - Machine
    - Environment (e.g. Production, Development, Testing)
    - Operating System
    - OS Support Status
    - Cloud Readiness
    - Cloud Readiness Issues
    - Data Collection Issues
    - Assigned 6R Treatment
    - Assigned Target
    - Assessment Data Coverage
    - Software Data Coverage
    - Power State (On/Off)
    - CPU Cores
    - CPU Usage (%)
    - RAM (GB)
    - RAM Usage (%)
    - Storage (GB)
12. **User Engagement**: Conclude by inviting the user to explore specific modernization or migration strategies or ask further questions about the application's infrastructure and cost profile relevant to its migration. Do not include an `User Engagement` header in your response.