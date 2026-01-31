# ADR-0004: Azure Service Whitelist

**Status:** Accepted
**Date:** January 2025

## Context

Azure has hundreds of services. The Architecture Center documents mention many of them, but not all are relevant for architecture matching. We needed to decide which services to recognize.

## Decision

We maintain a curated whitelist of ~150 Azure services, organized by category:

| Category | Example Services | Count |
|----------|------------------|-------|
| Compute | Virtual Machines, App Service, Functions | 15 |
| Containers | AKS, Container Apps, Container Instances | 3 |
| Databases | SQL Database, Cosmos DB, PostgreSQL | 11 |
| Storage | Blob Storage, Files, Data Lake | 10 |
| Networking | Virtual Network, Load Balancer, Front Door | 21 |
| Integration | Service Bus, Event Grid, Logic Apps | 8 |
| Identity | Entra ID, Key Vault | 6 |
| Security | Defender, Sentinel, Firewall | 9 |
| Management | Monitor, Automation, Policy | 15 |
| Analytics | Synapse, Data Factory, Databricks | 15+ |

## Rationale

### Why a Whitelist?

1. **Noise reduction** - Many service mentions are incidental, not architectural
2. **Canonical names** - "Azure SQL" vs "SQL Database" vs "Azure SQL Database"
3. **Relevance** - Preview services and niche offerings aren't helpful for matching

### What's Excluded?

- Preview/beta services
- Deprecated services
- Services with no architectural significance (e.g., Azure Portal)
- Region-specific variants

### Service Role Classification

We further classify services by their architectural role:

- **core_compute**: Primary compute platform (VMs, AKS, App Service)
- **core_data**: Primary data store (SQL, Cosmos DB)
- **supporting**: Infrastructure services (VNet, Key Vault)
- **optional**: Enhancement services (CDN, API Management)

## Consequences

1. **Some valid services may not match** - If it's not in the whitelist, it's ignored
2. **Whitelist needs maintenance** - New GA services should be added
3. **Custom catalogs can extend** - Add services via config

## Configuration

The whitelist is defined in `src/catalog_builder/parser.py`:

```python
CANONICAL_AZURE_SERVICES = {
    # Compute
    "Azure Virtual Machines",
    "Azure App Service",
    "Azure Functions",
    # ...
}
```

## Adding Services

To add a new service:
1. Add to `CANONICAL_AZURE_SERVICES` in parser.py
2. Optionally classify its role in `SERVICE_ROLES`
3. Regenerate the catalog

## Related

- Code: `src/catalog_builder/parser.py:14-170`
- Config: `catalog-config.yaml` → `services.additional`
