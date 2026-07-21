# Contributing

Contributions that improve correctness, clarity, compatibility, or measurable project outcomes are welcome.

## Before opening a change

1. Open an issue for a substantial behavioral or architectural proposal.
2. Keep each pull request focused on one problem.
3. Preserve backward compatibility unless the change explicitly documents and justifies a breaking release.
4. Do not add secrets, private project data, generated caches, or machine-local paths.

## Development setup

```bash
python -m pip install -e ".[dev]"
```

Run the same checks used by CI:

```bash
python validate.py
python -m pytest -q
python scripts/validate_publication.py
python scripts/build_release.py --version 1.0.0-rc.1 --output dist
```

When changing a skill:

- keep its `SKILL.md` concise and put detailed guidance in `references/`;
- update relevant trigger cases and executable project trials;
- preserve the distinction between observed evidence and inferred conclusions;
- run the promotion gate and explain any metric change;
- update `docs/ARCHITECTURE.md` when public architecture, data flow, configuration, or important commands change.

## Pull requests

Describe the problem, the chosen solution, risks, validation commands, and any checks that could not be run. Documentation and tests should change together with user-visible behavior.

By contributing, you agree that your contribution is licensed under Apache License 2.0.
