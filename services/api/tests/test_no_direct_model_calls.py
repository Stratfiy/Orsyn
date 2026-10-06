"""Test that model SDKs are only imported in app/ai/."""

import ast
from pathlib import Path


def find_python_files(root: Path) -> list[Path]:
    """Recursively find all Python files."""
    return sorted(root.rglob("*.py"))


def get_banned_imports(file_path: Path) -> list[tuple[int, str]]:
    """Return (line_no, module_name) for banned imports."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    banned_modules = {"anthropic", "openai", "sarvam", "boto3"}
    found: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in banned_modules:
                    found.append((node.lineno, module_name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_name = node.module.split(".")[0]
            if module_name in banned_modules:
                found.append((node.lineno, node.module))

    return found


def test_no_direct_model_calls() -> None:
    """Done when: anthropic, openai, sarvam, boto3 only imported in app/ai/."""
    app_dir = Path(__file__).parent.parent / "app"
    ai_dir = app_dir / "ai"

    violations: list[str] = []

    for file_path in find_python_files(app_dir):
        # Skip files inside app/ai/
        try:
            if file_path.relative_to(ai_dir):
                continue
        except ValueError:
            pass

        banned_imports = get_banned_imports(file_path)
        for line_no, module_name in banned_imports:
            rel_path = file_path.relative_to(app_dir.parent)
            violations.append(f"{rel_path}:{line_no} imports {module_name}")

    assert not violations, "\n".join(violations)
