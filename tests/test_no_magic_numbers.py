"""Spec Sect. 3.3: no numeric literals in the model, REC and economics code.

Allowed literals: 0, 1, 24, 100. Unit conversions must be imported from
``wpvrec.units`` (names, not literals). Every other number comes from the registry.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "wpvrec"
ALLOWED = {0, 1, 24, 100}


def _scanned_files():
    yield from sorted((SRC / "model").rglob("*.py"))
    yield SRC / "rec.py"
    yield SRC / "economics.py"


def test_no_magic_numbers():
    offenders = []
    for path in _scanned_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, int | float | complex)
                and not isinstance(node.value, bool)
                and node.value not in ALLOWED
            ):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}: {node.value!r}")
    assert not offenders, "numeric literals found:\n" + "\n".join(offenders)


def test_scanner_catches_literals(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("x = 0.92 * y\nz = 24\n")
    found = [
        n.value
        for n in ast.walk(ast.parse(bad.read_text()))
        if isinstance(n, ast.Constant) and n.value not in ALLOWED
    ]
    assert found == [0.92]
