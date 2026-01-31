# ADR-0003: Catalog Quality Tiers

**Status:** Accepted
**Date:** January 2025

## Context

The Azure Architecture Center contains different types of content:
- Reference architectures (production-ready patterns)
- Example scenarios (learning/POC implementations)
- Solution ideas (conceptual designs)

We needed to distinguish these so users get appropriate recommendations.

## Decision

We classify catalog entries into four quality tiers:

| Tier | Count* | Source | Use Case |
|------|--------|--------|----------|
| **curated** | ~42 | YamlMime:Architecture metadata | Production recommendations |
| **ai_enriched** | ~1 | AI-enhanced with validation | Production recommendations |
| **ai_suggested** | ~8 | Heuristic classification | Use with review |
| **example_only** | ~120 | ms.topic: example-scenario | Learning/exploration |

*Counts are approximate and vary by build

## Rationale

### Why Distinguish Quality?

Not all architectures are created equal:

1. **Reference architectures** go through Microsoft's architecture review process
2. **Example scenarios** are illustrative implementations—they show *how* to build something, not necessarily the *best* way
3. **Solution ideas** are conceptual starting points

Recommending an example scenario for a production migration could lead users astray.

### Quality Weights in Scoring

Higher quality entries get score multipliers:

```yaml
quality_weights:
  curated: 1.0        # Full score
  ai_enriched: 0.95   # Slight discount
  ai_suggested: 0.85  # Needs human review
  example_only: 0.70  # Significant discount
```

### Quick Build vs Full Build

- **Quick Build** (`exclude_examples: true`): ~51 entries, 82% curated
- **Full Build** (`exclude_examples: false`): ~171 entries, 25% curated

## Consequences

1. **Quick Build is recommended for production use** - Higher signal-to-noise ratio
2. **Full Build is useful for exploration** - See more patterns, including edge cases
3. **Example-only entries aren't excluded** - They're deprioritized, not hidden

## How Quality Is Determined

1. Check for `YamlMime:Architecture` browse metadata → `curated`
2. Check `ms.topic` field:
   - `reference-architecture` → `curated`
   - `example-scenario` → `example_only`
   - `solution-idea` → `example_only`
3. AI classification of remaining content → `ai_suggested`

## Related

- [Catalog Comparison](../catalog-comparison.md)
- Code: `src/catalog_builder/schema.py:142-154`
