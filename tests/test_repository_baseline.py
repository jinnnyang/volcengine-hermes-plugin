from pathlib import Path


def test_refactor_docs_are_present():
    root = Path(__file__).resolve().parents[1]

    assert (root / "docs" / "refactor" / "README.md").is_file()
    assert (root / "docs" / "refactor" / "11-development-priority-task-map.md").is_file()


def test_no_local_hermes_plans_are_tracked_by_default():
    root = Path(__file__).resolve().parents[1]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert ".hermes/" in gitignore
