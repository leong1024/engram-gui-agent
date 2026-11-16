import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "quality_ratchet.py"
BASELINE = {
    "broad_exception_handlers": 0,
    "silent_broad_exception_handlers": 0,
    "type_ignore_comments": 0,
    "long_functions": 0,
    "app_memory_long_functions": 0,
}


def _function(name: str, lines: int) -> str:
    body = "".join(f"    value_{i} = {i}\n" for i in range(lines - 1))
    return f"def {name}():\n{body}"


def _run(root: Path, files: dict[str, str], baseline: dict[str, int] | None = None):
    for relative, source in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    (root / ".quality-baseline.json").write_text(json.dumps(baseline or BASELINE))
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True
    )


def test_101_line_function_under_app_memory_fails(tmp_path):
    result = _run(tmp_path, {"artemis/app_memory/big.py": _function("big", 101)})
    assert result.returncode == 1
    assert "app_memory_long_functions increased from 0 to 1" in result.stdout
    assert "long_functions increased from 0 to 1" in result.stdout


def test_100_line_function_under_app_memory_passes(tmp_path):
    result = _run(tmp_path, {"artemis/app_memory/ok.py": _function("ok", 100)})
    assert result.returncode == 0, result.stdout


def test_long_function_elsewhere_is_counted_but_not_as_app_memory(tmp_path):
    files = {"artemis/other/big.py": _function("big", 101)}
    failing = _run(tmp_path, files)
    assert failing.returncode == 1
    assert "app_memory_long_functions" not in failing.stdout

    allowed = _run(tmp_path, files, {**BASELINE, "long_functions": 1})
    assert allowed.returncode == 0, allowed.stdout
    assert "long_functions: 1" in allowed.stdout


def test_existing_debt_is_ratcheted_per_metric(tmp_path):
    source = "try:\n    pass\nexcept Exception:\n    pass\n"
    result = _run(tmp_path, {"artemis/handlers.py": source})
    assert result.returncode == 1
    assert "broad_exception_handlers increased from 0 to 1" in result.stdout
