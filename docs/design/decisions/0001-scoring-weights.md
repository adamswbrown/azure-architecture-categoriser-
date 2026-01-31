# ADR-0001: Scoring Weight Distribution

**Status:** Accepted
**Date:** January 2025

## Context

The scorer evaluates architectures across 10 dimensions. We needed to decide how much each dimension should contribute to the final score.

## Decision

We use the following weight distribution:

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| Treatment Alignment | 20% | Most important - wrong treatment wastes months |
| Platform Compatibility | 15% | App Mod data is authoritative |
| App Mod Recommended | 10% | Direct signal from assessment |
| Runtime Model | 10% | Microservices vs monolith matters |
| Service Overlap | 10% | Validates approved services |
| Availability Alignment | 10% | SLA requirements are hard constraints |
| Operating Model Fit | 8% | Team capability match |
| Complexity Tolerance | 7% | Don't over-engineer |
| Browse Tag Overlap | 5% | Soft signal from categories |
| Cost Posture | 5% | Important but flexible |

**Total: 100%**

## Rationale

### Treatment Alignment (20%)

This is the highest weight because recommending a "Refactor" architecture for a "Rehost" scenario means the customer would:
- Spend months refactoring code unnecessarily
- Require skills they may not have
- Delay their migration significantly

A mismatch here is the most expensive mistake.

### Platform Compatibility (15%)

When App Mod assessment says "Azure App Service: Supported" or "AKS: NotSupported", that data comes from actual code analysis. We trust it more than inferences.

### Lower Weights for Soft Signals

Browse tags (5%) and cost posture (5%) are "nice to have" matches. An architecture isn't wrong just because it's tagged differently or costs more—it may still be the best fit.

## Consequences

1. **Users may see unexpected rankings** - A great platform match can be outweighed by treatment mismatch
2. **Weights are configurable** - Override in `scorer-config.yaml` if your priorities differ
3. **Sum must equal 100%** - Validation enforces this

## Configuration

```yaml
# scorer-config.yaml
scoring_weights:
  treatment_alignment: 0.20
  platform_compatibility: 0.15
  # ... etc
```

## Related

- [ADR-0002: Confidence Penalties](./0002-confidence-penalties.md)
- Code: `src/architecture_scorer/scorer.py:39-50`
