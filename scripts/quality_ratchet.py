"""Fail CI when quality debt counts exceed the baseline.

Tracked: broad exception handlers, type-ignore comments and functions over
MAX_FUNCTION_LINES lines (everywhere, and under artemis/app_memory).
Lower the committed baseline when removing existing debt.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterator
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = (
    Path("artemis"),
    Path("mcp_server"),
    Path("apps") / "admin_console",
    Path("third_party"),
)
APP_MEMORY_DIR = Path("artemis") / "app_memory"
BASELINE_NAME = ".quality-baseline.json"
MAX_FUNCTION_LINES = 100
BROAD_EXCEPTIONS = {"Exception", "BaseException", "bare-except"}
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b")


def _exception_names(node: ast.expr | None) -> set[str]:
    if node is None:
        return {"bare-except"}
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.Tuple):
        names: set[str] = set()
        for child in node.elts:
            names.update(_exception_names(child))
        return names
    return set()


def _parse(path: Path) -> tuple[str, ast.Module]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return text, ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise RuntimeError(f"Cannot inspect invalid Python file {path}: {exc}") from exc


def _python_files(root: Path, directories: tuple[Path, ...]) -> Iterator[Path]:
    for directory in directories:
        yield from (root / directory).rglob("*.py")


def _function_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return (node.end_lineno or node.lineno) - node.lineno + 1


def _count_long_functions(tree: ast.Module) -> int:
    functions = (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef))
    return sum(1 for node in functions if _function_length(node) > MAX_FUNCTION_LINES)


def _count_handlers(tree: ast.Module) -> tuple[int, int]:
    broad = silent = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if not _exception_names(node.type) & BROAD_EXCEPTIONS:
            continue
        broad += 1
        if node.body and all(isinstance(statement, ast.Pass) for statement in node.body):
            silent += 1
    return broad, silent


def _app_memory_long_functions(root: Path) -> int:
    return sum(_count_long_functions(_parse(p)[1]) for p in _python_files(root, (APP_MEMORY_DIR,)))


def collect_metrics(root: Path = ROOT) -> dict[str, int]:
    metrics = dict.fromkeys(
        (
            "broad_exception_handlers",
            "silent_broad_exception_handlers",
            "type_ignore_comments",
            "long_functions",
        ),
        0,
    )
    for path in _python_files(root, SOURCE_DIRS):
        text, tree = _parse(path)
        broad, silent = _count_handlers(tree)
        metrics["broad_exception_handlers"] += broad
        metrics["silent_broad_exception_handlers"] += silent
        metrics["type_ignore_comments"] += len(TYPE_IGNORE.findall(text))
        metrics["long_functions"] += _count_long_functions(tree)
    metrics["app_memory_long_functions"] = _app_memory_long_functions(root)
    return metrics


def find_regressions(
    baseline: dict[str, int], current: dict[str, int]
) -> dict[str, tuple[int, int]]:
    return {
        name: (int(baseline[name]), value)
        for name, value in current.items()
        if value > int(baseline[name])
    }


def _report_pass(baseline: dict[str, int], current: dict[str, int]) -> None:
    print("quality ratchet passed")
    for name, value in current.items():
        improvement = int(baseline[name]) - value
        suffix = f" ({improvement} below baseline)" if improvement else ""
        print(f"  {name}: {value}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-current", action="store_true", help="print metrics as JSON")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to inspect")
    args = parser.parse_args()

    current = collect_metrics(args.root)
    if args.print_current:
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0

    baseline = json.loads((args.root / BASELINE_NAME).read_text(encoding="utf-8"))
    regressions = find_regressions(baseline, current)
    for name, (allowed, actual) in regressions.items():
        print(f"quality regression: {name} increased from {allowed} to {actual}")
    if regressions:
        return 1
    _report_pass(baseline, current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
