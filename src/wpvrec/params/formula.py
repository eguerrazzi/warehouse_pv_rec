"""Safe evaluation of the formulas of derived registry entries.

A formula is a Python-like arithmetic expression on registry ids and on the unit
constants of :mod:`wpvrec.units`, e.g. ``e_mission_gross * (1 - regen_share / PERCENT)``.
Only numbers, names, + - * / **, parentheses, comparisons, ``and`` and the
functions ``min``, ``max``, ``round`` and ``abs`` are accepted; anything else is
rejected before evaluation.
"""

from __future__ import annotations

import ast
import operator

from wpvrec import units

UNIT_CONSTANTS: dict[str, float] = {
    name: getattr(units, name) for name in dir(units) if name.isupper()
}

_FUNCTIONS = {"min": min, "max": max, "round": round, "abs": abs}
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class FormulaError(ValueError):
    """Raised for a malformed formula or an unknown name."""


def parse(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as err:
        raise FormulaError(f"cannot parse formula {expr!r}: {err.msg}") from err
    for node in ast.walk(tree):
        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Compare,
            ast.BoolOp,
            ast.And,
            ast.Constant,
            ast.Name,
            ast.Load,
            ast.Call,
            *_BINOPS,
            *_UNARY,
            *_COMPARE,
        )
        if not isinstance(node, allowed):
            raise FormulaError(f"{type(node).__name__} not allowed in formula {expr!r}")
        if isinstance(node, ast.Call) and not (
            isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords
        ):
            raise FormulaError(f"only {sorted(_FUNCTIONS)} may be called in {expr!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, int | float):
            raise FormulaError(f"only numeric constants allowed in {expr!r}")
    return tree


def names(expr: str) -> set[str]:
    """Registry ids referenced by ``expr`` (unit constants and functions excluded)."""
    return {
        n.id
        for n in ast.walk(parse(expr))
        if isinstance(n, ast.Name) and n.id not in UNIT_CONSTANTS and n.id not in _FUNCTIONS
    }


def evaluate(expr: str, values: dict[str, object]):
    """Evaluate ``expr`` with registry ``values`` (unit constants are always available)."""
    env = {**UNIT_CONSTANTS, **values}

    def ev(node):
        match node:
            case ast.Expression(body=body):
                return ev(body)
            case ast.Constant(value=v):
                return v
            case ast.Name(id=name):
                if name not in env:
                    raise FormulaError(f"unknown name {name!r} in formula {expr!r}")
                return env[name]
            case ast.BinOp(left=lhs, op=op, right=rhs):
                return _BINOPS[type(op)](ev(lhs), ev(rhs))
            case ast.UnaryOp(op=op, operand=x):
                return _UNARY[type(op)](ev(x))
            case ast.Call(func=ast.Name(id=fname), args=args):
                return _FUNCTIONS[fname](*(ev(a) for a in args))
            case ast.BoolOp(values=vals):
                return all(ev(v) for v in vals)
            case ast.Compare(left=lhs, ops=ops, comparators=rhs_list):
                left = ev(lhs)
                for op, comp in zip(ops, rhs_list, strict=True):
                    right = ev(comp)
                    if not _COMPARE[type(op)](left, right):
                        return False
                    left = right
                return True
        raise FormulaError(f"unsupported expression in {expr!r}")  # pragma: no cover

    return ev(parse(expr))
