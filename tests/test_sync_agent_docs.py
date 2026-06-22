from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import copy2

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_agent_docs.py"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=check,
    )


def run_sync(repo: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=repo,
        text=True,
        capture_output=True,
        check=check,
    )


def init_repo(repo: Path) -> None:
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")


def commit_initial_pair(repo: Path, directory: str = ".") -> None:
    base = repo if directory == "." else repo / directory
    base.mkdir(parents=True, exist_ok=True)
    (base / "CLAUDE.md").write_text("original\n", encoding="utf-8")
    (base / "AGENTS.md").write_text("original\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")


def staged_text(repo: Path, path: str) -> str:
    return git(repo, "show", f":{path}").stdout


def test_syncs_sibling_from_single_staged_doc(tmp_path: Path) -> None:
    init_repo(tmp_path)
    commit_initial_pair(tmp_path)

    (tmp_path / "CLAUDE.md").write_text("updated\n", encoding="utf-8")
    git(tmp_path, "add", "CLAUDE.md")

    result = run_sync(tmp_path)

    assert "Synced AGENTS.md from staged CLAUDE.md." in result.stdout
    assert staged_text(tmp_path, "AGENTS.md") == "updated\n"
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "updated\n"


def test_allows_both_docs_when_staged_content_matches(tmp_path: Path) -> None:
    init_repo(tmp_path)
    commit_initial_pair(tmp_path, "src/project")

    for name in ("CLAUDE.md", "AGENTS.md"):
        (tmp_path / "src" / "project" / name).write_text("same\n", encoding="utf-8")
    git(tmp_path, "add", "src/project/CLAUDE.md", "src/project/AGENTS.md")

    result = run_sync(tmp_path)

    assert result.stdout == ""
    assert staged_text(tmp_path, "src/project/CLAUDE.md") == "same\n"
    assert staged_text(tmp_path, "src/project/AGENTS.md") == "same\n"


def test_rejects_both_docs_when_staged_content_differs(tmp_path: Path) -> None:
    init_repo(tmp_path)
    commit_initial_pair(tmp_path)

    (tmp_path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    git(tmp_path, "add", "CLAUDE.md", "AGENTS.md")

    result = run_sync(tmp_path, check=False)

    assert result.returncode == 1
    assert "staged AGENTS.md and CLAUDE.md differ" in result.stderr


def test_rejects_overwriting_unstaged_sibling_changes(tmp_path: Path) -> None:
    init_repo(tmp_path)
    commit_initial_pair(tmp_path)

    (tmp_path / "CLAUDE.md").write_text("staged update\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("unstaged sibling edit\n", encoding="utf-8")
    git(tmp_path, "add", "CLAUDE.md")

    result = run_sync(tmp_path, check=False)

    assert result.returncode == 1
    assert "AGENTS.md has unstaged changes" in result.stderr
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "unstaged sibling edit\n"


def test_pre_commit_framework_runs_sync_hook(tmp_path: Path) -> None:
    init_repo(tmp_path)
    commit_initial_pair(tmp_path)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copy2(SCRIPT, scripts_dir / "sync_agent_docs.py")
    (tmp_path / ".pre-commit-config.yaml").write_text(
        """
repos:
  - repo: local
    hooks:
      - id: sync-agent-docs
        name: Sync sibling AGENTS.md and CLAUDE.md files
        entry: scripts/sync_agent_docs.py
        language: script
        pass_filenames: false
        files: (^|/)(AGENTS|CLAUDE)\\.md$
""".lstrip(),
        encoding="utf-8",
    )

    (tmp_path / "CLAUDE.md").write_text("framework update\n", encoding="utf-8")
    git(tmp_path, "add", "CLAUDE.md")
    result = subprocess.run(
        ["pre-commit", "run", "sync-agent-docs"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert staged_text(tmp_path, "AGENTS.md") == "framework update\n"
