# ADR-0005: Eligibility Filter Rules

**Status:** Accepted
**Date:** January 2025

## Context

Before scoring architectures, we need to exclude ones that are definitively unsuitable. This is different from scoring—eligibility is binary (yes/no), not ranked.

## Decision

We apply six eligibility rules in order. Failure on any rule excludes the architecture:

| Rule | Description | Example |
|------|-------------|---------|
| 1. Catalog Quality | Discard candidates are excluded | - |
| 2. Treatment | Must support the declared treatment | Refactor app → no Rehost-only arch |
| 3. TIME Category | Must support the TIME category | Invest app → no Tolerate-only arch |
| 4. Security Level | Must meet minimum security requirements | Regulated app → no Basic-only arch |
| 5. Operating Model | Must be achievable by the team | SRE arch → Traditional IT team excluded |
| 6. Platform Compatibility | App Mod blockers are respected | "AKS: NotSupported" → no AKS arch |

## Rationale

### Why Filter Before Scoring?

1. **Performance** - Don't waste cycles scoring impossible matches
2. **Clarity** - Users see "excluded because X" instead of just a low score
3. **Correctness** - Some mismatches can't be overcome by other factors

### Rule Details

#### Treatment Compatibility

If the context says "treatment: Rehost" and an architecture only supports Refactor/Rebuild, it's excluded. This is a hard constraint—you can't lift-and-shift into a Kubernetes architecture.

#### Security Level Hierarchy

Security levels form a hierarchy:
```
basic < enterprise < regulated < highly_regulated
```

An architecture for `highly_regulated` workloads can handle `regulated` apps, but not vice versa.

#### Operating Model Gap

We allow a 1-level gap:
- Traditional IT team → can use Transitional or DevOps architectures
- Traditional IT team → cannot use SRE architectures (2-level gap)

This reflects realistic organizational growth paths.

#### Platform Compatibility (Authoritative)

When App Mod assessment says a platform is "NotSupported", we trust it completely. If code analysis found incompatibilities with AKS, don't recommend AKS architectures.

## Consequences

1. **Excluded architectures are shown separately** - Users can see what was filtered and why
2. **Empty results are possible** - If nothing passes filters, we say so honestly
3. **Exclusion reasons are detailed** - Not just "excluded" but "excluded: requires SRE operating model"

## Not Suitable For (Manual Exclusions)

Architectures can declare they're unsuitable for certain scenarios:

```yaml
not_suitable_for:
  - greenfield_only      # Only for new projects
  - single_vm_workloads  # Over-engineered for 1 VM
  - no_container_experience  # Requires container skills
```

These are checked against the application context.

## Code Location

```python
# src/architecture_scorer/eligibility_filter.py
class EligibilityFilter:
    def filter(self, architectures, context, intent):
        # Returns (eligible, excluded) tuple
```

## Related

- [ADR-0001: Scoring Weights](./0001-scoring-weights.md) - What happens after eligibility
- Code: `src/architecture_scorer/eligibility_filter.py`
