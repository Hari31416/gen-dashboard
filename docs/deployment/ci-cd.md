# CI/CD & Linting Pathways

Automated integration checks enforce code formatting and security scanning before accepting source code updates.

---

## 1. Local Pre-Commit Hooks (`.pre-commit-config.yaml`)

To catch code-style issues early, developers configure local Git hooks using the provided root configuration:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

### Setup Command
```bash
pre-commit install
```

---

## 2. Automated Integration Pathways

Continuous integration build nodes run standardized verification checks across both codebases before merging pull requests:
1. **Python Format & Typings**: Runs `black` across all backend modules and validates type safety using linting suites.
2. **Frontend Type Checking**: Invokes `pnpm run build` to verify typescript compilation contracts (`tsc --noEmit`).
3. **Test Suite Execution**: Executes `pytest` unit suites to ensure core logic and SQL sanitization layers remain unbroken.
