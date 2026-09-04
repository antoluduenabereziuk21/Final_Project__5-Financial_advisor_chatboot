"""Check that an edited Python module is actually intact — not merely that
it parses.

Two real failures on 2026-09-03, both of which compiled cleanly and both of
which `ast.parse` reported as fine:

  1. A guard clause was inserted one indent level too deep, landing after a
     `continue`. Everything below it, including the line that populated the
     return value, became unreachable. The function silently returned an
     empty dict and a resume that should have reused 27 rows reused none.

  2. A slice that cut from one `def` to the next `\\n\\ndef ` ran straight past
     an `async def` and deleted a 99-line function. NameError at runtime,
     after the expensive setup had already run.

Neither is a syntax error. Both are caught below.

    python verify_patch.py path/to/module.py [--baseline saved.json]
    python verify_patch.py path/to/module.py --save baseline.json

Checks:
  defs        every top-level def/async def/class, so a diff against a saved
              baseline shows anything deleted or renamed
  unreachable statements following return/continue/break/raise in the same
              block — the signature of a mis-indented insertion
  duplicates  two defs with the same name (a patch applied twice)
  import      the module actually imports (catches NameError, bad indent at
              runtime, missing imports for names a patch introduced)

Exit code is non-zero if anything fails, so it drops into a shell one-liner
before an expensive run.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

TERMINAL = (ast.Return, ast.Continue, ast.Break, ast.Raise)


def top_level_defs(tree: ast.Module) -> list[str]:
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(("async def " if isinstance(node, ast.AsyncFunctionDef)
                        else "def ") + node.name)
        elif isinstance(node, ast.ClassDef):
            out.append("class " + node.name)
    return out


def unreachable(tree: ast.Module) -> list[tuple[int, str]]:
    """Any statement that follows a return/continue/break/raise inside the
    same block can never execute."""
    found = []
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            for i, stmt in enumerate(block[:-1]):
                if isinstance(stmt, TERMINAL):
                    nxt = block[i + 1]
                    found.append((getattr(nxt, "lineno", 0),
                                  f"after {type(stmt).__name__.lower()} "
                                  f"on line {stmt.lineno}"))
    return found


def duplicate_defs(names: list[str]) -> list[str]:
    seen, dupes = set(), []
    for n in names:
        if n in seen:
            dupes.append(n)
        seen.add(n)
    return dupes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--baseline", help="json written by --save, to diff against")
    ap.add_argument("--save", help="write the current definition list here")
    ap.add_argument("--no-import", action="store_true",
                    help="skip the import check (use if importing has side effects)")
    a = ap.parse_args()

    path = Path(a.module).resolve()
    src = path.read_text(encoding="utf-8")
    ok = True

    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        print(f"FAIL  syntax error: {exc}")
        return 1
    print("OK    parses")

    defs = top_level_defs(tree)
    print(f"OK    {len(defs)} top-level definitions")

    dupes = duplicate_defs(defs)
    if dupes:
        ok = False
        print(f"FAIL  duplicate definitions: {dupes}")

    dead = unreachable(tree)
    if dead:
        ok = False
        print(f"FAIL  {len(dead)} unreachable statement(s):")
        for line, why in dead:
            print(f"        line {line}: {why}")
    else:
        print("OK    no unreachable statements")

    if a.baseline:
        prev = json.loads(Path(a.baseline).read_text())
        gone = [d for d in prev if d not in defs]
        added = [d for d in defs if d not in prev]
        if gone:
            ok = False
            print(f"FAIL  definitions removed since baseline: {gone}")
        if added:
            print(f"NOTE  definitions added: {added}")
        if not gone and not added:
            print("OK    definition list unchanged from baseline")

    if a.save:
        Path(a.save).write_text(json.dumps(defs, indent=2))
        print(f"OK    baseline written to {a.save}")

    if not a.no_import:
        sys.path.insert(0, str(path.parent))
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print("OK    imports cleanly")
        except Exception as exc:
            ok = False
            print(f"FAIL  import raised {type(exc).__name__}: {exc}")

    print("\nPASS" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
