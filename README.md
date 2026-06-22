# agent-doc-sync

A small `pre-commit` hook that keeps sibling `AGENTS.md` and `CLAUDE.md`
files identical without asking an LLM to remember to update both.

## What It Does

- If only one sibling is staged, copy its staged content to the other file and
  stage that sibling.
- If both siblings are staged and identical, continue.
- If both siblings are staged and differ, stop the commit.
- If the unstaged sibling has local edits, stop instead of overwriting them.
- If either file is deleted or renamed, stop and make the user resolve it
  explicitly.

The hook acts only on staged `AGENTS.md` / `CLAUDE.md` files. It does not scan
or normalize untouched pairs.

## Use

Add this to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/ravi-hq/agent-doc-sync
    rev: v0.1.1
    hooks:
      - id: sync-agent-docs
```

Then install pre-commit in the consuming repo:

```bash
pre-commit install
```

To run manually:

```bash
pre-commit run sync-agent-docs --all-files
```

## Release

Create a version tag and push it:

```bash
git tag v0.1.1
git push origin main --tags
```

Consumers should pin a tag in `rev`, not a moving branch.
