#!/usr/bin/env python3
"""Keep sibling CLAUDE.md and AGENTS.md files identical in staged commits."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DOC_NAMES = {"AGENTS.md", "CLAUDE.md"}


class SyncError(RuntimeError):
    """Raised when the staged agent docs cannot be synced automatically."""


def run_git(
    root: Path | None,
    args: list[str],
    *,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        command = "git " + " ".join(args)
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SyncError(f"{command} failed: {detail}")
    return completed


def repo_root() -> Path:
    output = run_git(None, ["rev-parse", "--show-toplevel"]).stdout
    return Path(output.decode("utf-8").strip())


def staged_agent_doc_changes(root: Path) -> dict[str, dict[str, str]]:
    completed = run_git(
        root,
        [
            "diff",
            "--cached",
            "--name-status",
            "--diff-filter=ACMDR",
            "--",
            "AGENTS.md",
            "CLAUDE.md",
            ":(glob)**/AGENTS.md",
            ":(glob)**/CLAUDE.md",
        ],
    )
    grouped: dict[str, dict[str, str]] = {}
    for raw_line in completed.stdout.decode("utf-8").splitlines():
        columns = raw_line.split("\t")
        if len(columns) < 2:
            continue
        status = columns[0]
        path = columns[-1]
        name = Path(path).name
        if name not in DOC_NAMES:
            continue
        directory = str(Path(path).parent)
        if directory == ".":
            directory = ""
        grouped.setdefault(directory, {})[name] = status
    return grouped


def sibling_path(directory: str, name: str) -> str:
    sibling = "AGENTS.md" if name == "CLAUDE.md" else "CLAUDE.md"
    return str(Path(directory) / sibling) if directory else sibling


def staged_blob(root: Path, path: str) -> bytes:
    return run_git(root, ["show", f":{path}"]).stdout


def has_unstaged_changes(root: Path, path: str) -> bool:
    completed = run_git(root, ["diff", "--quiet", "--", path], check=False)
    if completed.returncode == 0:
        return False
    if completed.returncode == 1:
        return True
    detail = completed.stderr.decode("utf-8", errors="replace").strip()
    raise SyncError(f"git diff failed for {path}: {detail}")


def ensure_sync(root: Path, grouped_changes: dict[str, dict[str, str]]) -> list[str]:
    messages: list[str] = []
    errors: list[str] = []

    for directory, changes in sorted(grouped_changes.items()):
        unsupported = {name: status for name, status in changes.items() if status.startswith("D")}
        if unsupported:
            rendered = ", ".join(
                f"{name} ({status})" for name, status in sorted(unsupported.items())
            )
            errors.append(f"{directory or '.'}: cannot auto-sync deleted agent docs: {rendered}")
            continue

        staged_names = sorted(changes)
        if staged_names == ["AGENTS.md", "CLAUDE.md"]:
            agents_path = str(Path(directory) / "AGENTS.md") if directory else "AGENTS.md"
            claude_path = str(Path(directory) / "CLAUDE.md") if directory else "CLAUDE.md"
            if staged_blob(root, agents_path) != staged_blob(root, claude_path):
                errors.append(
                    f"{directory or '.'}: staged AGENTS.md and CLAUDE.md differ. "
                    "Make them identical, then stage both files again."
                )
            continue

        source_name = staged_names[0]
        source_path = str(Path(directory) / source_name) if directory else source_name
        target_path = sibling_path(directory, source_name)
        target_full_path = root / target_path

        if target_full_path.exists() and has_unstaged_changes(root, target_path):
            errors.append(
                f"{target_path} has unstaged changes. Stage it too, or resolve it before "
                f"auto-syncing from {source_path}."
            )
            continue

        target_full_path.parent.mkdir(parents=True, exist_ok=True)
        target_full_path.write_bytes(staged_blob(root, source_path))
        run_git(root, ["add", "--", target_path])
        messages.append(f"Synced {target_path} from staged {source_path}.")

    if errors:
        raise SyncError("\n".join(errors))
    return messages


def main() -> int:
    try:
        root = repo_root()
        messages = ensure_sync(root, staged_agent_doc_changes(root))
    except SyncError as exc:
        print(f"Agent doc sync failed:\n{exc}", file=sys.stderr)
        return 1

    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
