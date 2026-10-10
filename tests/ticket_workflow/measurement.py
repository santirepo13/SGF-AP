"""Measure executed source lines and both exits of ticket-workflow decisions.

Uses Python's trace events and AST; no external coverage executable is needed.
Exceptional calls are witnessed individually by the PE tests and their CSV rows.
"""

import ast
import dis
from pathlib import Path

from tests.ticket_workflow.model import ReferenceTicket


class WorkflowMeasurement:
    def __init__(self):
        self.path = Path(__file__).with_name("model.py").resolve()
        self.functions = {getattr(ReferenceTicket, name).__code__: name
                          for name in ("register", "prioritize", "review_closure")}
        self.lines = set()
        self.arcs = set()
        self.previous = {}
        self.by_case = {}
        self.decisions = {}
        tree = ast.parse(self.path.read_text(encoding="utf-8"))

        def scan(body, after=None):
            for index, statement in enumerate(body):
                following = body[index + 1].lineno if index + 1 < len(body) else after
                if isinstance(statement, (ast.If, ast.While)):
                    alternate = statement.orelse[0].lineno if statement.orelse else following
                    self.decisions[statement.lineno] = (statement.body[0].lineno, alternate)
                    scan(statement.body, statement.lineno if isinstance(statement, ast.While) else following)
                    scan(statement.orelse, following)
                elif isinstance(statement, ast.Try):
                    scan(statement.body, following)
                    for handler in statement.handlers:
                        scan(handler.body, following)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in self.functions.values():
                scan(node.body)

    def trace(self, frame, event, case_id):
        if frame.f_code not in self.functions:
            return
        key = id(frame)
        if event == "call":
            self.previous.pop(key, None)
        elif event == "line":
            line = frame.f_lineno
            self.lines.add(line)
            self.by_case.setdefault(case_id, set()).add(line)
            if key in self.previous:
                self.arcs.add((self.previous[key], line))
            self.previous[key] = line
        elif event == "return":
            self.previous.pop(key, None)

    def result(self):
        methods = {}
        all_measurable = set()
        branches = {(line, destination) for line, exits in self.decisions.items() for destination in exits}
        for code, name in self.functions.items():
            measurable = {line for _, line in dis.findlinestarts(code)
                          if line is not None and line != code.co_firstlineno}
            all_measurable.update(measurable)
            method_branches = {arc for arc in branches if code.co_firstlineno <= arc[0] <= max(measurable)}
            methods[name] = {
                "source_lines": sorted(measurable), "executed_lines": sorted(measurable & self.lines),
                "missing_lines": sorted(measurable - self.lines),
                "branches": sorted(method_branches), "executed_branches": sorted(method_branches & self.arcs),
                "missing_branches": sorted(method_branches - self.arcs),
            }
        return {
            "source": "tests/ticket_workflow/model.py", "scope": "workflow reference model only",
            "measurement": "Python trace line events; AST if/while true and false exits",
            "measurable_lines": len(all_measurable), "executed_lines": len(all_measurable & self.lines),
            "line_percent": round(100 * len(all_measurable & self.lines) / len(all_measurable), 2),
            "branches": len(branches), "executed_branches": len(branches & self.arcs),
            "branch_percent": round(100 * len(branches & self.arcs) / len(branches), 2),
            "missing_lines": sorted(all_measurable - self.lines), "missing_branches": sorted(branches - self.arcs),
            "methods": methods, "exception_witnesses": {key: sorted(value) for key, value in self.by_case.items()},
        }
