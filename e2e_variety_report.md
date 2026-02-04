# Azure Architecture Recommender - E2E Variety Test Report

**Generated**: 2026-02-04 13:33:32
**Catalog**: architecture-catalog.json
**Sample Files Tested**: 36

## Summary

- **Successful Tests**: 35/36
- **Failed Tests**: 1/36

## Architecture Variety Analysis

### Top Recommendation Distribution

| Architecture | Count | Percentage |
|-------------|-------|------------|
| Mission-critical AKS Cluster With Private Networking | 8 | 26.7% |
| Highly Available AKS Cluster With Private Networking | 4 | 13.3% |
| Zone-redundant Article Layout With Private Networking | 4 | 13.3% |
| Enterprise-grade AKS Cluster With Private Networking And WAF | 4 | 13.3% |
| Enterprise-grade Vm-based Workload With Caching | 3 | 10.0% |
| Highly Available App Service Web Application | 2 | 6.7% |
| Serverless Application With Private Networking | 1 | 3.3% |
| Production-ready Container Apps Deployment With Private Netw | 1 | 3.3% |
| Baseline Vm-based Workload With Global Load Balancing | 1 | 3.3% |
| Mission-critical Key Design Decisions With Private Networkin | 1 | 3.3% |
| Highly Available Cloud Workload With Private Networking | 1 | 3.3% |

### All Recommendations Distribution (Top 15)

| Architecture | Appearances |
|-------------|-------------|
| Mission-critical AKS Cluster With Private Networking | 19 |
| Enterprise-grade AKS Cluster With Private Networking And WAF | 15 |
| Highly Available App Service Web Application | 14 |
| Mission-critical Serverless Application With Private Network | 11 |
| Highly Available AKS Cluster With Private Networking | 10 |
| Zone-redundant Article Layout With Private Networking | 9 |
| Production-ready Container Apps Deployment With Private Netw | 7 |
| Mission-critical AKS Cluster With Private Networking And Geo | 7 |
| Highly Available AKS Cluster With Gitops | 6 |
| Mission-critical Key Design Decisions With Private Networkin | 6 |
| Mission-critical Article Layout With Private Networking And  | 5 |
| Baseline Vm-based Workload With Global Load Balancing | 4 |
| Enterprise-grade Vm-based Workload With Caching | 4 |
| Highly Available Cloud Workload With Private Networking | 4 |
| Highly Available Architecture Notes With Private Networking | 4 |

### Catalog Quality Distribution

| Quality | Count |
|---------|-------|
| curated | 121 |
| example_only | 27 |
| ai_suggested | 2 |

### Treatment Distribution (from input files)

| Treatment | Count |
|-----------|-------|
| replatform | 13 |
| refactor | 11 |
| rehost | 3 |
| rebuild | 2 |
| retire | 2 |
| replace | 2 |
| tolerate | 1 |
| retain | 1 |

### AKS vs Non-AKS Analysis

- **AKS as Top Recommendation**: 16 (53.3%)
- **Non-AKS Top Recommendations**: 14 (46.7%)

**Non-AKS Top Recommendations**:
- Baseline Vm-based Workload With Global Load Balancing (1)
- Enterprise-grade Vm-based Workload With Caching (3)
- Highly Available App Service Web Application (2)
- Highly Available Cloud Workload With Private Networking (1)
- Mission-critical Key Design Decisions With Private Networking (1)
- Production-ready Container Apps Deployment With Private Networking (1)
- Serverless Application With Private Networking (1)
- Zone-redundant Article Layout With Private Networking (4)

## Detailed Test Results

| # | File | App Name | Treatment | Top Recommendation | Score | Confidence |
|---|------|----------|-----------|-------------------|-------|------------|
| 1 | 01-java-refactor-aks.json | OrderProcessingPlatf | refactor | Highly Available AKS Cluster With Private Net... | 66.9 | Low |
| 2 | 02-dotnet-replatform-apps | FinanceLedger | replatform | Zone-redundant Article Layout With Private Ne... | 50.9 | Low |
| 3 | 03-legacy-tolerate.json | HRArchiveTool | tolerate | - | - | Low |
| 4 | 04-mixed-java-dotnet-part | CustomerPortalSuite | refactor | Highly Available AKS Cluster With Private Net... | 68.3 | Low |
| 5 | 05-java-replatform-partia | InventoryBatchRunner | replatform | Highly Available AKS Cluster With Private Net... | 54.8 | Low |
| 6 | 06-dotnet-conflicting-sig | ClaimsIntake | replatform | Zone-redundant Article Layout With Private Ne... | 41.7 | Low |
| 7 | 07-greenfield-cloud-nativ | RealtimeFraudDetecti | rebuild | Mission-critical AKS Cluster With Private Net... | 63.1 | Low |
| 8 | 08-enterprise-java-aks-cu | PaymentGateway | refactor | Mission-critical AKS Cluster With Private Net... | 63.9 | Low |
| 9 | 09-rehost-vm-lift-shift.j | InventoryTracker | rehost | Enterprise-grade Vm-based Workload With Cachi... | 53.9 | Low |
| 10 | 10-retire-end-of-life.jso | LegacyReportingPorta | retire | - | - | Low |
| 11 | 11-replace-saas-crm.json | CustomerRelationship | replace | - | - | Low |
| 12 | 12-retain-hybrid-on-premi | ManufacturingControl | retain | Enterprise-grade Vm-based Workload With Cachi... | 58.8 | Low |
| 13 | 13-highly-regulated-healt | PatientRecordsSystem | replatform | Enterprise-grade AKS Cluster With Private Net... | 60.9 | Low |
| 14 | 14-multi-region-active-ac | GlobalTradingPlatfor | refactor | Mission-critical AKS Cluster With Private Net... | 63.6 | Low |
| 15 | 15-traditional-it-erp.jso | ERPFinanceModule | replatform | Zone-redundant Article Layout With Private Ne... | 52.1 | Low |
| 16 | 16-sre-mission-critical.j | CoreBankingPlatform | refactor | Mission-critical AKS Cluster With Private Net... | 62.4 | Low |
| 17 | 17-cost-minimized-startup | StartupMVP | replatform | Enterprise-grade AKS Cluster With Private Net... | 58.7 | Low |
| 18 | 18-innovation-first-ai-ml | IntelligentDocumentP | rebuild | Enterprise-grade AKS Cluster With Private Net... | 58.4 | Low |
| 19 | 19-appmod-blockers-mainfr | CoreInsurancePolicy | refactor | Serverless Application With Private Networkin... | 32.4 | Low |
| 20 | 20-eliminate-time-categor | DeprecatedPayrollCal | retire | - | - | Low |
| 21 | 21-low-complexity-3tier-d | DepartmentBudgetTrac | replatform | Mission-critical AKS Cluster With Private Net... | 60.9 | Low |
| 22 | 22-medium-complexity-java | CustomerPortal | replatform | Zone-redundant Article Layout With Private Ne... | 58.8 | Low |
| 23 | 23-high-complexity-dotnet | OrderManagementSyste | replatform | Mission-critical AKS Cluster With Private Net... | 63.5 | Low |
| 24 | 24-very-high-complexity-j | SupplyChainPlatform | refactor | Enterprise-grade AKS Cluster With Private Net... | 62.2 | Low |
| 25 | 25-extra-high-complexity- | GlobalBankingCore | refactor | Production-ready Container Apps Deployment Wi... | 64.2 | Low |
| 26 | 26-Acuvera.json | ERROR | - | Failed to load context file: 1 validatio | - | - |
| 27 | 27-simple-webapp-appservi | EmployeeDirectory | replatform | Mission-critical AKS Cluster With Private Net... | 59.0 | Low |
| 28 | 28-serverless-functions-e | OrderNotificationSer | refactor | Mission-critical AKS Cluster With Private Net... | 66.5 | Low |
| 29 | 29-legacy-vb6-vm-only.jso | LegacyWarehouseSyste | rehost | Enterprise-grade Vm-based Workload With Cachi... | 57.5 | Low |
| 30 | 30-static-webapp-spa.json | MarketingPortal | replatform | Baseline Vm-based Workload With Global Load B... | 50.8 | Low |
| 31 | 31-container-apps-microse | ProductCatalogAPI | refactor | Highly Available App Service Web Application | 62.5 | Low |
| 32 | 32-data-analytics-synapse | SalesDataWarehouse | replatform | Highly Available AKS Cluster With Private Net... | 51.9 | Low |
| 33 | 33-wcf-service-appservice | LegacyPaymentGateway | replatform | Mission-critical Key Design Decisions With Pr... | 51.1 | Low |
| 34 | 34-sharepoint-migration.j | CompanyIntranet | replace | - | - | Low |
| 35 | 35-sap-hana-vm.json | SAPERP | rehost | Highly Available Cloud Workload With Private ... | 57.5 | Low |
| 36 | 36-iot-edge-hybrid.json | FactoryIoTGateway | refactor | Highly Available App Service Web Application | 55.0 | Low |

## Full Recommendation Lists by Sample

### 01-java-refactor-aks.json
**App**: OrderProcessingPlatform | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available AKS Cluster With Private Networking | curated | 66.9 |
| 2 | Mission-critical AKS Cluster With Private Networking | curated | 61.7 |
| 3 | Highly Available App Service Web Application | curated | 58.7 |
| 4 | Highly Available AKS Cluster With Gitops | curated | 56.9 |
| 5 | Production-ready Container Apps Deployment With Private | curated | 56.7 |

### 02-dotnet-replatform-appservice.json
**App**: FinanceLedger | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Zone-redundant Article Layout With Private Networking | curated | 50.9 |
| 2 | Highly Available AKS Cluster With Private Networking | curated | 50.6 |
| 3 | Highly Available AKS Cluster With Gitops | curated | 46.6 |
| 4 | Mission-critical Key Design Decisions With Private Netw | curated | 46.1 |
| 5 | Mission-critical AKS Cluster With Private Networking | curated | 45.5 |

### 03-legacy-tolerate.json
**App**: HRArchiveTool | **Treatment**: tolerate | **Confidence**: Low

*No recommendations generated*

### 04-mixed-java-dotnet-partial-appmod.json
**App**: CustomerPortalSuite | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available AKS Cluster With Private Networking | curated | 68.3 |
| 2 | Highly Available App Service Web Application | curated | 60.2 |
| 3 | Highly Available AKS Cluster With Gitops | curated | 59.8 |
| 4 | Production-ready Container Apps Deployment With Private | curated | 58.1 |
| 5 | Highly Available App Service Web Application | curated | 57.5 |

### 05-java-replatform-partial-appmod-missing-compat.json
**App**: InventoryBatchRunner | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available AKS Cluster With Private Networking | curated | 54.8 |
| 2 | Mission-critical Serverless Application With Private Ne | example_only | 45.7 |
| 3 | Zone-redundant Article Layout With Private Networking | curated | 45.4 |
| 4 | Enterprise-grade AKS Cluster With Private Networking An | curated | 42.3 |
| 5 | Mission-critical AKS Cluster With Private Networking | curated | 41.9 |

### 06-dotnet-conflicting-signals-appmod-overrides.json
**App**: ClaimsIntake | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Zone-redundant Article Layout With Private Networking | curated | 41.7 |
| 2 | Mission-critical Key Design Decisions With Private Netw | curated | 39.6 |
| 3 | Mission-critical Serverless Application With Private Ne | example_only | 37.0 |
| 4 | Baseline Vm-based Workload With Global Load Balancing | curated | 36.9 |
| 5 | Highly Available Vm-based Workload With Private Network | example_only | 36.3 |

### 07-greenfield-cloud-native-perfect.json
**App**: RealtimeFraudDetection | **Treatment**: rebuild | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 63.1 |
| 2 | Enterprise-grade AKS Cluster With Private Networking An | curated | 56.9 |
| 3 | Mission-critical AKS Cluster With Private Networking An | curated | 55.2 |
| 4 | Highly Available AKS Cluster With Zero Trust | curated | 51.5 |
| 5 | Baseline AKS Cluster With Private Networking | curated | 50.2 |

### 08-enterprise-java-aks-curated.json
**App**: PaymentGateway | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 63.9 |
| 2 | Highly Available AKS Cluster With Private Networking | curated | 61.8 |
| 3 | Highly Available App Service Web Application | curated | 59.8 |
| 4 | Production-ready Container Apps Deployment With Private | curated | 59.2 |
| 5 | Enterprise-grade AKS Cluster With Private Networking An | curated | 57.6 |

### 09-rehost-vm-lift-shift.json
**App**: InventoryTracker | **Treatment**: rehost | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade Vm-based Workload With Caching | curated | 53.9 |
| 2 | Highly Available Cloud Workload With Private Networking | curated | 53.1 |
| 3 | Mission-critical Serverless Application With Private Ne | example_only | 47.9 |
| 4 | Enterprise-grade Potential Use Cases | example_only | 44.1 |
| 5 | Mission-critical Serverless Application With Private Ne | example_only | 43.6 |

### 10-retire-end-of-life.json
**App**: LegacyReportingPortal | **Treatment**: retire | **Confidence**: Low

*No recommendations generated*

### 11-replace-saas-crm.json
**App**: CustomerRelationshipManager | **Treatment**: replace | **Confidence**: Low

*No recommendations generated*

### 12-retain-hybrid-on-premises.json
**App**: ManufacturingControlSystem | **Treatment**: retain | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade Vm-based Workload With Caching | curated | 58.8 |
| 2 | Highly Available Cloud Workload With Private Networking | curated | 57.1 |
| 3 | Highly Available Virtual Network Connection Types | curated | 53.8 |
| 4 | Highly Available AKS Cluster | curated | 53.5 |
| 5 | Mission-critical Serverless Application With Private Ne | example_only | 50.4 |

### 13-highly-regulated-healthcare.json
**App**: PatientRecordsSystem | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade AKS Cluster With Private Networking An | curated | 60.9 |
| 2 | Mission-critical Article Layout With Private Networking | curated | 60.8 |
| 3 | Mission-critical AKS Cluster With Private Networking An | curated | 60.5 |
| 4 | Highly Available Architecture Notes With Private Networ | curated | 56.7 |
| 5 | Mission-critical AKS Cluster With Private Networking | curated | 55.1 |

### 14-multi-region-active-active.json
**App**: GlobalTradingPlatform | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 63.6 |
| 2 | Mission-critical AKS Cluster With Private Networking An | curated | 62.8 |
| 3 | Enterprise-grade AKS Cluster With Private Networking An | curated | 62.2 |
| 4 | Mission-critical Article Layout With Private Networking | curated | 59.8 |
| 5 | Highly Available Architecture Notes With Private Networ | curated | 58.0 |

### 15-traditional-it-erp.json
**App**: ERPFinanceModule | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Zone-redundant Article Layout With Private Networking | curated | 52.1 |
| 2 | Mission-critical Key Design Decisions With Private Netw | curated | 45.6 |
| 3 | Mission-critical Serverless Application With Private Ne | example_only | 43.2 |
| 4 | Highly Available App Service Web Application | example_only | 40.5 |
| 5 | Enterprise-grade App Service Web Application With Priva | example_only | 40.2 |

### 16-sre-mission-critical.json
**App**: CoreBankingPlatform | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 62.4 |
| 2 | Mission-critical AKS Cluster With Private Networking An | curated | 61.1 |
| 3 | Production-ready Container Apps Deployment With Private | curated | 61.1 |
| 4 | Enterprise-grade AKS Cluster With Private Networking An | curated | 60.8 |
| 5 | Mission-critical Article Layout With Private Networking | curated | 59.9 |

### 17-cost-minimized-startup.json
**App**: StartupMVP | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade AKS Cluster With Private Networking An | curated | 58.7 |
| 2 | Zone-redundant Article Layout With Private Networking | curated | 58.1 |
| 3 | Highly Available AKS Cluster With Private Networking | curated | 56.7 |
| 4 | Mission-critical AKS Cluster With Private Networking | curated | 56.1 |
| 5 | Highly Available AKS Cluster With Gitops | curated | 51.2 |

### 18-innovation-first-ai-ml.json
**App**: IntelligentDocumentProcessor | **Treatment**: rebuild | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade AKS Cluster With Private Networking An | curated | 58.4 |
| 2 | Mission-critical AKS Cluster With Private Networking | curated | 52.1 |
| 3 | Highly Available AKS Cluster With Zero Trust | curated | 50.0 |
| 4 | Zone-redundant AKS Cluster With Private Networking And  | example_only | 48.3 |
| 5 | Baseline AKS Cluster With Private Networking | curated | 46.2 |

### 19-appmod-blockers-mainframe.json
**App**: CoreInsurancePolicy | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Serverless Application With Private Networking | example_only | 32.4 |
| 2 | Zone-redundant Data Pipeline With Caching And Blue-gree | example_only | 32.0 |
| 3 | Baseline Serverless Application With Private Networking | example_only | 28.8 |
| 4 | Data Pipeline | example_only | 27.8 |
| 5 | Container Apps Deployment | example_only | 27.1 |

### 20-eliminate-time-category.json
**App**: DeprecatedPayrollCalculator | **Treatment**: retire | **Confidence**: Low

*No recommendations generated*

### 21-low-complexity-3tier-dotnet.json
**App**: DepartmentBudgetTracker | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 60.9 |
| 2 | Baseline Vm-based Workload With Global Load Balancing | curated | 56.7 |
| 3 | Highly Available AKS Cluster With Gitops | curated | 56.6 |
| 4 | Enterprise-grade AKS Cluster With Private Networking An | curated | 53.8 |
| 5 | Highly Available App Service Web Application | ai_suggested | 53.8 |

### 22-medium-complexity-java-multi-env.json
**App**: CustomerPortal | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Zone-redundant Article Layout With Private Networking | curated | 58.8 |
| 2 | Highly Available AKS Cluster With Private Networking | curated | 56.7 |
| 3 | Enterprise-grade AKS Cluster With Private Networking An | curated | 55.6 |
| 4 | Mission-critical AKS Cluster With Private Networking | curated | 55.2 |
| 5 | Highly Available Architecture Notes With Private Networ | curated | 52.5 |

### 23-high-complexity-dotnet-ha-dr.json
**App**: OrderManagementSystem | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 63.5 |
| 2 | Mission-critical Key Design Decisions With Private Netw | curated | 58.5 |
| 3 | Enterprise-grade AKS Cluster With Private Networking An | curated | 56.1 |
| 4 | Highly Available Architecture Notes With Private Networ | curated | 53.6 |
| 5 | Zone-redundant Article Layout With Private Networking | curated | 51.9 |

### 24-very-high-complexity-java-enterprise.json
**App**: SupplyChainPlatform | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade AKS Cluster With Private Networking An | curated | 62.2 |
| 2 | Mission-critical AKS Cluster With Private Networking An | curated | 62.1 |
| 3 | Mission-critical AKS Cluster With Private Networking | curated | 62.0 |
| 4 | Mission-critical Article Layout With Private Networking | curated | 59.5 |
| 5 | Baseline AKS Cluster With Private Networking | curated | 57.1 |

### 25-extra-high-complexity-mixed-enterprise.json
**App**: GlobalBankingCore | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Production-ready Container Apps Deployment With Private | curated | 64.2 |
| 2 | Mission-critical AKS Cluster With Private Networking | curated | 62.9 |
| 3 | Enterprise-grade AKS Cluster With Private Networking An | curated | 61.5 |
| 4 | Mission-critical AKS Cluster With Private Networking An | curated | 61.5 |
| 5 | Mission-critical Article Layout With Private Networking | curated | 61.0 |

### 27-simple-webapp-appservice.json
**App**: EmployeeDirectory | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 59.0 |
| 2 | Baseline Vm-based Workload With Global Load Balancing | curated | 56.7 |
| 3 | Highly Available App Service Web Application | ai_suggested | 53.8 |
| 4 | Enterprise-grade AKS Cluster With Private Networking An | curated | 51.9 |
| 5 | Enterprise-grade AKS Cluster With Caching | example_only | 51.7 |

### 28-serverless-functions-eventdriven.json
**App**: OrderNotificationService | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical AKS Cluster With Private Networking | curated | 66.5 |
| 2 | Highly Available App Service Web Application | curated | 56.7 |
| 3 | Enterprise-grade AKS Cluster With Private Networking An | curated | 52.7 |
| 4 | Highly Available App Service Web Application | curated | 52.3 |
| 5 | Mission-critical AKS Cluster With Private Networking An | curated | 51.7 |

### 29-legacy-vb6-vm-only.json
**App**: LegacyWarehouseSystem | **Treatment**: rehost | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Enterprise-grade Vm-based Workload With Caching | curated | 57.5 |
| 2 | Highly Available Cloud Workload With Private Networking | curated | 53.1 |
| 3 | Mission-critical Serverless Application With Private Ne | example_only | 51.0 |
| 4 | Mission-critical Serverless Application With Private Ne | example_only | 46.7 |
| 5 | Highly Available Components | example_only | 45.1 |

### 30-static-webapp-spa.json
**App**: MarketingPortal | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Baseline Vm-based Workload With Global Load Balancing | curated | 50.8 |
| 2 | Highly Available AKS Cluster With Zero Trust | curated | 50.0 |
| 3 | Mission-critical AKS Cluster With Private Networking | curated | 49.9 |
| 4 | Mission-critical AKS Cluster | example_only | 46.3 |
| 5 | Serverless Application | example_only | 44.9 |

### 31-container-apps-microservice.json
**App**: ProductCatalogAPI | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available App Service Web Application | curated | 62.5 |
| 2 | Highly Available AKS Cluster With Private Networking | curated | 60.4 |
| 3 | Production-ready Container Apps Deployment With Private | curated | 60.2 |
| 4 | Highly Available App Service Web Application | curated | 60.0 |
| 5 | Highly Available App Service Web Application | curated | 56.0 |

### 32-data-analytics-synapse.json
**App**: SalesDataWarehouse | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available AKS Cluster With Private Networking | curated | 51.9 |
| 2 | Mission-critical Key Design Decisions With Private Netw | curated | 47.3 |
| 3 | Mission-critical Serverless Application With Private Ne | example_only | 43.2 |
| 4 | Zone-redundant Article Layout With Private Networking | curated | 43.1 |
| 5 | Highly Available AKS Cluster With Gitops | curated | 41.9 |

### 33-wcf-service-appservice.json
**App**: LegacyPaymentGateway | **Treatment**: replatform | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Mission-critical Key Design Decisions With Private Netw | curated | 51.1 |
| 2 | Mission-critical Serverless Application With Private Ne | example_only | 44.8 |
| 3 | Zone-redundant Article Layout With Private Networking | curated | 43.4 |
| 4 | Enterprise-grade App Service Web Application With Priva | example_only | 43.3 |
| 5 | Mission-critical Serverless Application With Private Ne | example_only | 40.5 |

### 34-sharepoint-migration.json
**App**: CompanyIntranet | **Treatment**: replace | **Confidence**: Low

*No recommendations generated*

### 35-sap-hana-vm.json
**App**: SAPERP | **Treatment**: rehost | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available Cloud Workload With Private Networking | curated | 57.5 |
| 2 | Enterprise-grade Vm-based Workload With Caching | curated | 52.5 |
| 3 | Highly Available Vm-based Workload | curated | 47.3 |
| 4 | Highly Available Vm-based Workload With WAF And Geo-red | curated | 47.3 |
| 5 | Highly Available Components | example_only | 40.9 |

### 36-iot-edge-hybrid.json
**App**: FactoryIoTGateway | **Treatment**: refactor | **Confidence**: Low

| Rank | Architecture | Quality | Score |
|------|-------------|---------|-------|
| 1 | Highly Available App Service Web Application | curated | 55.0 |
| 2 | Highly Available AKS Cluster With Private Networking | curated | 50.8 |
| 3 | Production-ready Container Apps Deployment With Private | curated | 50.0 |
| 4 | Highly Available App Service Web Application | curated | 50.0 |
| 5 | Mission-critical AKS Cluster With Private Networking | curated | 48.3 |

## Failed Tests

### 26-Acuvera.json
**Error**: Failed to load context file: 1 validation error for RawContextFile
app_overview
  Field required [type=missing, input_value={'application_overview': ...integration_count': 4}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.12/v/missing

## Conclusion

- **Unique Top Recommendations**: 11
- **Unique Architectures Recommended (all positions)**: 34

✅ **Good variety**: The recommendations show diversity across different architecture patterns.