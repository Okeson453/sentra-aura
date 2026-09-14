"""Audit FastAPI route handlers for path-template parameters that the handler
never binds.

A route declared as ``/render/jobs/{job_id}/cancel`` whose handler does not
accept a ``job_id`` parameter is a latent ``NameError`` at request time (or a
silently wrong call). FastAPI does not validate this at import time, so the
defect survives startup, health checks and any test that never exercises the
route.

Usage:
    python tools/path_param_audit.py [root ...]

Exit code 1 if any unbound path parameter is found.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
PATH_PARAM_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]*)?\}")


def _decorator_route(dec: ast.expr) -> tuple[str | None, str | None]:
    """Return (http_method, path) for a FastAPI route decorator, else (None, None)."""
    if not isinstance(dec, ast.Call):
        return None, None
    func = dec.func
    if not isinstance(func, ast.Attribute):
        return None, None
    method = func.attr.lower()
    if method not in HTTP_METHODS:
        return None, None
    if not dec.args:
        return None, None
    first = dec.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return method, first.value
    return None, None


def _bound_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    a = fn.args
    names: set[str] = set()
    for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
        names.add(arg.arg)
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def audit_file(path: pathlib.Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # surfaced separately by the syntax sweep
        return [f"{path}: SYNTAX ERROR: {exc}"]

    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            method, route = _decorator_route(dec)
            if not method or not route:
                continue
            params = PATH_PARAM_RE.findall(route)
            if not params:
                continue
            bound = _bound_names(node)
            missing = [p for p in params if p not in bound]
            if missing:
                findings.append(
                    f"{path}:{node.lineno}: {method.upper()} {route} -> handler "
                    f"'{node.name}' does not bind path param(s) {missing}"
                )
    return findings


def main(argv: list[str]) -> int:
    roots = [pathlib.Path(a) for a in argv[1:]] or [pathlib.Path("services"), pathlib.Path("packages")]
    files: list[pathlib.Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
        else:
            files.extend(sorted(root.rglob("*.py")))

    findings: list[str] = []
    for f in files:
        findings.extend(audit_file(f))

    if findings:
        print(f"UNBOUND PATH PARAMETERS: {len(findings)}")
        for line in findings:
            print("  " + line)
        return 1
    print(f"OK: no unbound path parameters across {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
