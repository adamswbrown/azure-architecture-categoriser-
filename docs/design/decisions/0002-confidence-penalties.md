# ADR-0002: Confidence Penalties

**Status:** Accepted
**Date:** January 2025

## Context

Not all input signals are equally reliable. A declared treatment from an architect is more trustworthy than an inference from server count. We needed to account for this uncertainty.

## Decision

We apply penalties to scores based on signal confidence:

| Confidence Level | Penalty | Example Source |
|------------------|---------|----------------|
| HIGH | 0% | Declared treatment, App Mod results |
| MEDIUM | 5% | Inferred from technology stack |
| LOW | 15% | Heuristic based on server count |
| UNKNOWN | 25% | No data available, using defaults |

**Maximum total penalty: 25%** (capped)

## Rationale

### Why Penalize Uncertainty?

When we're guessing, we should be honest about it. A score of 85 based on solid data is more meaningful than 85 based on assumptions.

### Why These Specific Values?

- **0% for HIGH**: If we have authoritative data, use it fully
- **5% for MEDIUM**: Small discount for reasonable inferences
- **15% for LOW**: Significant discount—we're pattern matching
- **25% for UNKNOWN**: Major discount—we're essentially guessing

### Why Cap at 25%?

Without a cap, an architecture could score 0 just because the input was sparse. We still want to surface recommendations, just with appropriate caution.

## Consequences

1. **Sparse context files get lower scores** - This is intentional
2. **"Confidence" appears in match details** - Users see why scores differ
3. **Not configurable** - These are fundamental to honest scoring

## How It Works

```python
# From scorer.py
CONFIDENCE_PENALTIES = {
    SignalConfidence.HIGH: 0.0,
    SignalConfidence.MEDIUM: 0.05,
    SignalConfidence.LOW: 0.15,
    SignalConfidence.UNKNOWN: 0.25,
}
```

Each derived signal carries a confidence level. The penalty is calculated from the weighted average of all signal confidences.

## Example

Context file has:
- Declared treatment: Refactor (HIGH confidence)
- Inferred availability: Multi-region (LOW confidence)
- Unknown cost posture (UNKNOWN confidence)

The overall confidence penalty reduces the final score proportionally, ensuring users understand this recommendation has some uncertainty.

## Related

- [ADR-0001: Scoring Weights](./0001-scoring-weights.md)
- Code: `src/architecture_scorer/scorer.py:86-92`
