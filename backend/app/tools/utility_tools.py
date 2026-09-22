"""
"Other Tools / Custom Utility Tools" box -- a small, easy-to-extend
grab-bag of low-risk local utilities. Add whatever your workflows need
here and register it in app/mcp/registry.py.
"""
from __future__ import annotations

import datetime as _dt


def current_datetime(timezone: str = "UTC") -> str:
    """Returns the current date/time. Only UTC is supported out of the box."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def simple_calculator(expression: str) -> str:
    """
    Evaluates a basic arithmetic expression safely (+ - * / ( ) . and digits
    only -- no names, no calls, no attribute access).
    """
    import ast
    import operator

    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported expression")

    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval(tree.body))
    except Exception as exc:  # noqa: BLE001
        return f"error: could not evaluate expression ({exc})"
