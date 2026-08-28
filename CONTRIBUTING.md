# Contributing to SentraAura

## Branching Strategy

Trunk-based development: short-lived feature branches off `main`, merged via PR.
Release branches (`release/YYYY.MM.DD`) are cut from `main` at a release cadence.

## Commit Conventions

We use Conventional Commits:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `style:` formatting, missing semi colons, etc
- `refactor:` code change that neither fixes a bug nor adds a feature
- `perf:` code change that improves performance
- `test:` adding missing tests
- `chore:` changes to build process or auxiliary tools

## CI Pipeline

1. Lint & Type Check
2. Unit Tests
3. Contract Tests
4. Build & Scan
5. Integration Tests
6. Workflow Tests
7. Media Quality Tests
8. Agent Evaluation (conditional)
9. Security Scan

A PR cannot merge until every stage passes.

## Adding a New Agent

Use the CLI — the only sanctioned way:

```bash
sentra agent create <name> --domain <intelligence|creative|production|clipping|distribution|operations>
```

This scaffolds: agent.py, schemas.py, config.py, state.py, tools.py, tests/, README.md,
evals/<name>/ directory, and prompt-registry entry.

## Code Review

CODEOWNERS enforces review by directory. Architecture changes require ADR review.
