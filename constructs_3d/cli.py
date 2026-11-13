"""constructs-3d command line: validate | info | build."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from . import __version__
from .model import ConstructError, load, resolve, validate
from .viewer import render


def _scene(path):
    data = load(path)
    return resolve(data)


def cmd_validate(a) -> int:
    try:
        errs = validate(load(a.file))
    except ConstructError as e:
        errs = e.errors
    except OSError as e:
        print(f"error: {e}", file=sys.stderr); return 2
    if errs:
        for e in errs:
            print(f"invalid: {e}", file=sys.stderr)
        return 1
    print(f"ok: {a.file}")
    return 0


def cmd_info(a) -> int:
    try:
        s = _scene(a.file)
    except ConstructError as e:
        for x in e.errors:
            print(f"invalid: {x}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"error: {e}", file=sys.stderr); return 2
    if a.json:
        print(json.dumps({k: s[k] for k in ("name", "units", "counts", "bounds")}, indent=2))
    else:
        b = s["bounds"]
        print(f"{s['name']}: {len(s['parts'])} parts " + ", ".join(f"{n} {k}" for k, n in sorted(s["counts"].items())))
        print("bounds min " + str([round(v, 4) for v in b["min"]]) + " max " + str([round(v, 4) for v in b["max"]]) + " size " + str([round(v, 4) for v in b["size"]]))
    return 0


def cmd_build(a) -> int:
    try:
        s = _scene(a.file)
    except ConstructError as e:
        for x in e.errors:
            print(f"invalid: {x}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"error: {e}", file=sys.stderr); return 2
    if a.title:
        s["name"] = a.title
    out = Path(a.output or Path(a.file).with_suffix(".html"))
    out.write_text(render(s), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(s['parts'])} parts)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="constructs-3d", description="Validate a construct description (JSON or YAML subset) and write a standalone interactive 3D HTML file.")
    ap.add_argument("--version", action="version", version="constructs-3d " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check the file, print every problem"); v.add_argument("file"); v.set_defaults(fn=cmd_validate)
    i = sub.add_parser("info", help="part counts and bounding box"); i.add_argument("file"); i.add_argument("--json", action="store_true"); i.set_defaults(fn=cmd_info)
    b = sub.add_parser("build", help="write a standalone HTML viewer"); b.add_argument("file"); b.add_argument("-o", "--output"); b.add_argument("--title"); b.set_defaults(fn=cmd_build)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
