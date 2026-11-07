"""
NOVA Safe Tools Framework - Calculator & Math Evaluation Tool
Safely evaluates arithmetic expressions, percentages, and GST calculations
via AST parsing without arbitrary code execution risk.
"""

from __future__ import annotations

import ast
import logging
import operator
import re
from typing import Any, Dict, List, Optional

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("nova.tools.calculator")


class CalculatorTool(BaseTool):
    """Safely evaluates arithmetic expressions, percentages, and conversational voice math."""

    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(self):
        super().__init__(
            name="calculator_tool",
            description="Safely evaluates math expressions, percentages, and arithmetic.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="expression",
                type="string",
                description="The math expression (e.g. '25 * 4', '20% of 1500', '18% GST on 5000').",
                required=True,
            )
        ]

    def _safe_eval(self, node: ast.AST) -> float:
        """Recursively evaluate an AST expression using allowlisted operators only."""
        if isinstance(node, ast.Expression):
            return self._safe_eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Disallowed operator: {op_type.__name__}")
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            if op_type == ast.Div and right == 0:
                raise ZeroDivisionError("Division by zero is undefined.")
            return self._OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Disallowed unary operator: {op_type.__name__}")
            operand = self._safe_eval(node.operand)
            return self._OPERATORS[op_type](operand)
        else:
            raise ValueError(f"Disallowed expression syntax: {type(node).__name__}")

    def execute(self, **kwargs: Any) -> ToolResult:
        raw_expr = str(kwargs.get("expression", "")).strip()
        if not raw_expr:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Math expression missing.",
                error="Empty expression parameter",
            )

        expr = raw_expr.lower().strip()

        # Handle percentage:
        # Case A: "20% of 1500" or "18% GST on 5000"
        m1 = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:gst\s+on|of|pe|par)\s+(\d+(?:\.\d+)?)", expr)
        # Case B: "500 ka 10 percent"
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*(?:ka|pe|par)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)", expr)

        if m1:
            p = float(m1.group(1))
            total = float(m1.group(2))
            val = (p / 100.0) * total
            disp_p = int(p) if p.is_integer() else p
            disp_t = int(total) if total.is_integer() else total
            disp_v = int(val) if val.is_integer() else val
            output_msg = f"{disp_p}% of {disp_t} is {disp_v}."
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output_msg,
                data={"result": disp_v},
                verification=VerificationResult(
                    verified=True,
                    method="ast_percentage_eval",
                    details="Percentage calculated successfully.",
                ),
            )

        if m2:
            total = float(m2.group(1))
            p = float(m2.group(2))
            val = (p / 100.0) * total
            disp_p = int(p) if p.is_integer() else p
            disp_t = int(total) if total.is_integer() else total
            disp_v = int(val) if val.is_integer() else val
            output_msg = f"{disp_p}% of {disp_t} is {disp_v}."
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output_msg,
                data={"result": disp_v},
                verification=VerificationResult(
                    verified=True,
                    method="ast_percentage_eval",
                    details="Percentage calculated successfully.",
                ),
            )

        # Normalize conversational operators
        clean_expr = expr
        replacements = [
            (r"\braise\s+to\b|\bpower\b", "**"),
            (r"\bplus\b|\bjodo\b", "+"),
            (r"\bminus\b|\bghatao\b", "-"),
            (r"\bmultiplied\s+by\b|\btimes\b|\binto\b|\bguna\b", "*"),
            (r"\bdivided\s+by\b|\bdivide\b|\bbhaga\b", "/"),
            (r"\bx\b", "*"),
        ]
        for pattern, sym in replacements:
            clean_expr = re.sub(pattern, sym, clean_expr)

        # Strip prefixes like "calculate", "solve", "hisab karo"
        clean_expr = re.sub(r"\b(?:calculate|solve|hisab\s+karo|batao|karo|what\s+is)\b", "", clean_expr).strip()

        # Check if contains only valid math characters
        if not re.search(r"\d", clean_expr) or re.search(r"[a-zA-Z_]", clean_expr):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Could not calculate expression '{raw_expr}'.",
                error="Invalid characters or expression syntax",
            )

        try:
            parsed = ast.parse(clean_expr, mode="eval")
            val = self._safe_eval(parsed)
            disp_val = int(val) if val.is_integer() else round(val, 4)
            output_msg = f"{raw_expr} is {disp_val}."
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output_msg,
                data={"result": disp_val},
                verification=VerificationResult(
                    verified=True,
                    method="safe_ast_eval",
                    details="Expression evaluated successfully.",
                ),
            )
        except ZeroDivisionError:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Division by zero is undefined.",
                error="ZeroDivisionError",
            )
        except Exception as exc:
            logger.warning("Calculator evaluation error on '%s': %s", raw_expr, exc)
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Could not calculate expression '{raw_expr}'.",
                error=str(exc),
            )
