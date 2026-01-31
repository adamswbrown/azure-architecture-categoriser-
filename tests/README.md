# Test Suite Documentation

This directory contains comprehensive test suites for the Azure Architecture Recommender.

## Overview

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `test_e2e.py` | 36 | End-to-end tests covering security, pipeline, and integration |
| `test_architecture_scorer.py` | 173 | Scoring engine unit and integration tests |
| `test_catalog_builder.py` | 24 | Catalog building and classification tests |
| `test_sanitize.py` | 44 | Security utility tests (XSS, SSRF, temp files) |

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src/ --cov-report=html

# Run specific test file
pytest tests/test_e2e.py -v

# Run specific test class
pytest tests/test_e2e.py::TestEndToEndScoringPipeline -v

# Run tests matching a pattern
pytest tests/ -k "security" -v
```

## Test Suites

### End-to-End Tests (`test_e2e.py`)

Comprehensive tests validating the complete application pipeline.

#### Security Utilities

**`TestSafePathUtility`** - Tests for `safe_path()` function:
- Valid path resolution (absolute, relative, home expansion)
- Null byte injection prevention
- Path traversal attack prevention (`../`, `..\\`)
- Base directory containment enforcement
- Existence validation

**`TestValidateRepoPath`** - Tests for repository path validation:
- Empty/nonexistent path rejection
- File vs directory validation
- Repository structure verification (`docs/` folder)

**`TestValidateOutputPath`** - Tests for output path validation:
- Parent directory creation
- Path traversal prevention
- Base directory constraints

#### Scoring Pipeline

**`TestEndToEndScoringPipeline`** - Full pipeline tests with synthetic data:
- Cloud-native Java context processing
- Legacy .NET context processing
- Recommendation generation
- Result structure validation
- JSON serialization/deserialization
- Score verification

#### Integration

**`TestIntegrationWithModifiedFiles`** - Component integration tests:
- Security utility imports
- GUI component imports
- Cross-component functionality

#### Scenario Testing

**`TestSyntheticScenarios`** - Real-world scenario validation:
- Java refactor → AKS
- .NET replatform → App Service
- Greenfield cloud-native
- VM lift-and-shift
- Regulated healthcare

### Architecture Scorer Tests (`test_architecture_scorer.py`)

Unit and integration tests for the scoring engine.

**`TestContextFileValidation`** - Validates all 25 example context files:
- JSON structure validation
- Required field verification

**`TestScorerBasicFunctionality`** - Core scoring tests:
- Context processing
- Output structure validation

**`TestTreatmentScenarios`** - Treatment-specific tests:
- Rehost, Retire, Replace, Retain scenarios
- Treatment-appropriate recommendations

**`TestComplexityScenarios`** - Complexity level tests:
- Low to extra-high complexity handling

**`TestAppModBlockers`** - Migration blocker handling:
- Blocker detection and filtering

**`TestClarificationQuestions`** - Question generation tests

**`TestSummary`** - Coverage verification

### Catalog Builder Tests (`test_catalog_builder.py`)

Tests for catalog building and architecture classification.

**`TestMarkdownParser`** - Document parsing tests:
- Frontmatter extraction
- Heading detection
- Image detection
- Azure service extraction

**`TestArchitectureDetector`** - Detection algorithm tests:
- Section-based detection
- Guide folder exclusion

**`TestMetadataExtractor`** - Metadata extraction tests:
- ID generation
- URL building

**`TestArchitectureClassifier`** - Classification tests:
- Domain suggestion
- Family suggestion

**`TestEnhancedClassifier`** - Enhanced classification tests:
- Treatment suggestion
- Security level detection
- Operating model detection
- Cost profile detection

### Security Tests (`test_sanitize.py`)

Tests for security utilities and protections.

**`TestSafeHtml`** - XSS prevention:
- Script tag escaping
- Event handler escaping
- Quote escaping

**`TestValidateUrl`** - SSRF prevention:
- Domain allowlisting
- Private IP blocking
- Metadata endpoint blocking
- Protocol validation

**`TestSecureTempFile`** - Temporary file security:
- Random filename generation
- Restrictive permissions
- Automatic cleanup

**`TestSecureTempDirectory`** - Temporary directory security

**`TestSanitizeFilename`** - Path traversal prevention:
- Separator removal
- Null byte removal
- Dot prefix removal

## Synthetic Test Data

The test suite includes synthetic context data for testing without external dependencies.

### Cloud-Native Java Application
```json
{
  "application": "E2ETestApp",
  "treatment": "Refactor",
  "technologies": ["Java 17", "Spring Boot", "PostgreSQL", "Redis"],
  "container_ready": true
}
```

### Legacy .NET Application
```json
{
  "application": "LegacyERPApp",
  "treatment": "Replatform",
  "technologies": [".NET Framework 4.8", "SQL Server", "IIS"],
  "container_ready": false
}
```

## Example Context Files

The `examples/context_files/` directory contains 25 pre-built context files representing various migration scenarios:

| File | Scenario |
|------|----------|
| `01-java-refactor-aks.json` | Java app refactoring to AKS |
| `02-dotnet-replatform-appservice.json` | .NET replatform to App Service |
| `07-greenfield-cloud-native-perfect.json` | New cloud-native application |
| `09-rehost-vm-lift-shift.json` | VM lift-and-shift |
| `10-retire-end-of-life.json` | Application retirement |
| `13-highly-regulated-healthcare.json` | Regulated industry scenario |
| ... | ... |

## Prerequisites

1. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Ensure catalog exists**:
   ```bash
   ls architecture-catalog.json
   ```

3. **Generate catalog if missing**:
   ```bash
   catalog-builder build-catalog --repo-path ~/architecture-center --out architecture-catalog.json
   ```

## CI/CD Integration

The tests are designed for CI/CD integration:

```yaml
# Example GitHub Actions step
- name: Run Tests
  run: |
    pip install -e ".[dev]"
    pytest tests/ -v --cov=src/ --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: coverage.xml
```

## Adding New Tests

When adding new tests:

1. **Security tests** → Add to `test_sanitize.py` or `test_e2e.py::TestSafePathUtility`
2. **Scoring tests** → Add to `test_architecture_scorer.py`
3. **Catalog tests** → Add to `test_catalog_builder.py`
4. **Integration tests** → Add to `test_e2e.py::TestIntegrationWithModifiedFiles`
5. **Scenario tests** → Add context file to `examples/context_files/` and test to `test_e2e.py::TestSyntheticScenarios`
