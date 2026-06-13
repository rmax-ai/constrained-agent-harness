"""Repository structure and relevance helpers for context reconstruction."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path


class RepositoryMap:
    """Build a compact repository map and locate likely relevant files."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root

    def build(self, path: Path) -> str:
        """Return an indented file tree for the repository root."""
        if not path.exists():
            return f"{path.name}/ (missing)"

        lines = [f"{path.name}/"]
        self._append_tree(path, lines, depth=1)
        return "\n".join(lines)

    def find_relevant_files(
        self,
        failing_tests: list[str],
        search_patterns: list[str],
    ) -> list[Path]:
        """Find likely relevant files using lightweight structural heuristics."""
        root = self._require_root()
        if not root.exists():
            return []

        python_files = self._python_files(root)
        scores: dict[Path, int] = defaultdict(int)
        symbol_index = self._symbol_index(python_files)

        trace_paths = self._extract_trace_paths([*failing_tests, *search_patterns])
        for relative_path in trace_paths:
            candidate = root / relative_path
            if candidate.exists():
                scores[candidate] += 8

        tokens = self._tokens_from_inputs(failing_tests, search_patterns)
        for file_path in python_files:
            stem = file_path.stem.lower()
            relative_text = str(file_path.relative_to(root)).lower()
            for token in tokens:
                if token in stem:
                    scores[file_path] += 5
                elif token in relative_text:
                    scores[file_path] += 3

        for test_path in self._resolve_test_paths(root, failing_tests):
            scores[test_path] += 6
            self._score_import_relationships(root, test_path, scores)
            self._score_symbol_relationships(test_path, symbol_index, scores)

        ranked = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
        return [path for path, score in ranked if score > 0]

    def read_file_content(self, path: Path, max_chars: int) -> str:
        """Read file content with truncation to keep prompts bounded."""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return f"[unreadable] {path}"

        if len(content) <= max_chars:
            return content
        return content[: max_chars - len("\n... [truncated]\n")] + "\n... [truncated]\n"

    def _append_tree(self, path: Path, lines: list[str], depth: int) -> None:
        try:
            children = sorted(path.iterdir(), key=lambda child: (child.is_file(), child.name))
        except OSError:
            lines.append(f"{'  ' * depth}[unreadable]")
            return

        for child in children:
            if child.name in {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".venv"}:
                continue
            prefix = "  " * depth
            suffix = "/" if child.is_dir() else ""
            lines.append(f"{prefix}{child.name}{suffix}")
            if child.is_dir():
                self._append_tree(child, lines, depth + 1)

    def _require_root(self) -> Path:
        if self._root is None:
            raise ValueError("repository root is not configured")
        return self._root

    def _python_files(self, root: Path) -> list[Path]:
        return sorted(
            path
            for path in root.rglob("*.py")
            if not any(part in {".git", "__pycache__", ".venv"} for part in path.parts)
        )

    def _symbol_index(self, python_files: list[Path]) -> dict[str, set[Path]]:
        index: dict[str, set[Path]] = defaultdict(set)
        for file_path in python_files:
            try:
                tree = ast.parse(file_path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    index[node.name.lower()].add(file_path)
        return index

    def _extract_trace_paths(self, items: list[str]) -> set[Path]:
        paths: set[Path] = set()
        for item in items:
            for match in re.findall(r"([A-Za-z0-9_./-]+\.py)", item):
                paths.add(Path(match))
        return paths

    def _tokens_from_inputs(self, failing_tests: list[str], search_patterns: list[str]) -> set[str]:
        tokens: set[str] = set()
        for item in [*failing_tests, *search_patterns]:
            basename = Path(item).stem.lower()
            text = basename.replace("test_", "").replace("tests_", "")
            for token in re.split(r"[^a-z0-9]+", text):
                if len(token) >= 3:
                    tokens.add(token)
        return tokens

    def _resolve_test_paths(self, root: Path, failing_tests: list[str]) -> list[Path]:
        resolved: list[Path] = []
        for item in failing_tests:
            candidate = root / item
            if candidate.exists():
                resolved.append(candidate)
                continue
            basename = Path(item).name
            for path in root.rglob(basename):
                resolved.append(path)
        return resolved

    def _score_import_relationships(
        self,
        root: Path,
        test_path: Path,
        scores: dict[Path, int],
    ) -> None:
        try:
            tree = ast.parse(test_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            else:
                continue
            for module in modules:
                resolved = root / Path(module.replace(".", "/")).with_suffix(".py")
                if resolved.exists():
                    scores[resolved] += 4

    def _score_symbol_relationships(
        self,
        test_path: Path,
        symbol_index: dict[str, set[Path]],
        scores: dict[Path, int],
    ) -> None:
        try:
            tree = ast.parse(test_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return

        for node in ast.walk(tree):
            symbol_name: str | None = None
            if isinstance(node, ast.Name):
                symbol_name = node.id
            elif isinstance(node, ast.Attribute):
                symbol_name = node.attr
            if symbol_name is None:
                continue
            for file_path in symbol_index.get(symbol_name.lower(), set()):
                scores[file_path] += 2
