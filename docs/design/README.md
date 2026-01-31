# Design Decisions

This folder documents the key design decisions behind the Azure Architecture Recommender. If you're wondering **"why does it work this way?"**, start here.

## Quick Links

| Topic | Description |
|-------|-------------|
| [Glossary](./glossary.md) | Key terms and concepts |
| [Scoring Weights](./decisions/0001-scoring-weights.md) | Why recommendations are ranked the way they are |
| [Confidence Penalties](./decisions/0002-confidence-penalties.md) | How uncertainty affects scores |
| [Catalog Quality Tiers](./decisions/0003-catalog-quality-tiers.md) | Why some architectures are weighted higher |
| [Azure Service Whitelist](./decisions/0004-azure-service-whitelist.md) | Which services are recognized and why |
| [Eligibility Filter Rules](./decisions/0005-eligibility-filter-rules.md) | What excludes an architecture from consideration |

## Philosophy

The recommender is designed around these principles:

1. **Transparency over magic** - Users should understand why an architecture was recommended
2. **Conservative matching** - Better to show fewer, high-confidence matches than flood users with noise
3. **App Mod is authoritative** - When assessment tools provide platform compatibility data, trust it
4. **Never force a recommendation** - If nothing fits well, say so

## How Decisions Are Made

Each Architecture Decision Record (ADR) follows this structure:

- **Context** - What problem we were solving
- **Decision** - What we chose to do
- **Rationale** - Why we made that choice
- **Consequences** - What users should know

## Customization

Most decisions documented here can be overridden via configuration:

- **Scoring weights**: `scorer-config.yaml` → `scoring_weights`
- **Quality weights**: `scorer-config.yaml` → `quality_weights`
- **Catalog filters**: `catalog-config.yaml` → `filters`

See [Configuration Guide](../configuration.md) for details.

---

*Last updated: January 2025*
