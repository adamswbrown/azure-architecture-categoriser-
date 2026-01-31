# Glossary

Key terms used throughout the codebase and documentation.

## Catalog Terms

| Term | Definition |
|------|------------|
| **Architecture Entry** | A single architecture pattern from the Azure Architecture Center, with metadata |
| **Catalog** | The JSON file containing all architecture entries (typically 50-170 entries) |
| **Quick Build** | ~51 curated reference architectures only |
| **Full Build** | ~171 architectures including examples and solution ideas |

## Quality Levels

| Level | Meaning | Source |
|-------|---------|--------|
| **curated** | Highest quality; from official Azure browse metadata | YamlMime:Architecture files |
| **ai_enriched** | AI-enhanced with high confidence | Content analysis + validation |
| **ai_suggested** | AI-generated, may need review | Heuristic classification |
| **example_only** | Example scenarios, not reference patterns | ms.topic: example-scenario |

## Treatment Types (Gartner 7R)

| Treatment | Description |
|-----------|-------------|
| **Retire** | Decommission the application |
| **Retain** | Keep on-premises, possibly with hybrid extension |
| **Rehost** | Lift-and-shift to VMs |
| **Replatform** | Move to PaaS with minimal changes |
| **Refactor** | Modernize code for cloud-native |
| **Rebuild** | Complete re-architecture from scratch |
| **Replace** | Swap for SaaS or different solution |

## Scoring Terms

| Term | Definition |
|------|------------|
| **Eligibility** | Binary check - is architecture even possible for this app? |
| **Score** | 0-100 ranking of how well an architecture fits |
| **Confidence** | How certain we are about the input signals (HIGH/MEDIUM/LOW/UNKNOWN) |
| **Dimension** | One aspect of the match (e.g., treatment alignment, platform compatibility) |

## Operating Models

| Model | Description |
|-------|-------------|
| **traditional_it** | Ops-heavy, change advisory boards, ITIL processes |
| **transitional** | Moving toward DevOps, mixed practices |
| **devops** | CI/CD, infrastructure as code, shared responsibility |
| **sre** | Site Reliability Engineering, error budgets, SLOs |

## Security Levels

| Level | Description |
|-------|-------------|
| **basic** | Standard security controls |
| **enterprise** | Corporate security requirements |
| **regulated** | Industry compliance (PCI-DSS, SOC2) |
| **highly_regulated** | Government/healthcare (FedRAMP, HIPAA) |

## Context File Terms

| Term | Definition |
|------|------------|
| **Context File** | JSON input from Dr. Migrate or similar assessment tool |
| **App Mod Results** | Application modernization assessment data |
| **Server Details** | Infrastructure inventory from discovery |
| **Detected Technology** | Frameworks/platforms found during assessment |

---

*See also: [Design Decisions](./README.md)*
