"""Load, validate and resolve a construct description into a scene dict."""
from __future__ import annotations
import json, math, re
from pathlib import Path
from . import yamlite

SHAPES = {"box": ("size",), "cylinder": ("radius", "height"), "sphere": ("radius",), "cone": ("radius", "height")}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_COLOR = "#8899aa"
MAX_PARTS = 2000


class ConstructError(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def load(path) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            data = yamlite.loads(text)
        except ValueError as e:
            raise ConstructError([f"{p.name}: YAML: {e}"])
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConstructError([f"{p.name}: JSON: {e}"])
    return data


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(v, n=3) -> bool:
    return isinstance(v, list) and len(v) == n and all(_num(x) for x in v)


def validate(data) -> list[str]:
    """Return a list of error strings (empty = valid)."""
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["top level must be a mapping with a 'parts' list"]
    if "name" in data and not isinstance(data["name"], str):
        errs.append("name must be a string")
    if "units" in data and not isinstance(data["units"], str):
        errs.append("units must be a string")
    parts = data.get("parts")
    if not isinstance(parts, list) or not parts:
        return errs + ["'parts' must be a non-empty list"]
    if len(parts) > MAX_PARTS:
        return errs + [f"too many parts ({len(parts)} > {MAX_PARTS})"]
    ids: dict[str, int] = {}
    for i, p in enumerate(parts):
        w = f"parts[{i}]"
        if not isinstance(p, dict):
            errs.append(f"{w}: must be a mapping"); continue
        pid = p.get("id")
        if not isinstance(pid, str) or not pid.strip():
            errs.append(f"{w}: 'id' must be a non-empty string")
        elif pid in ids:
            errs.append(f"{w}: duplicate id {pid!r} (first at parts[{ids[pid]}])")
        else:
            ids[pid] = i
        shape = p.get("shape")
        if shape not in SHAPES:
            errs.append(f"{w}: shape must be one of {sorted(SHAPES)}, got {shape!r}")
        else:
            for f in SHAPES[shape]:
                v = p.get(f)
                if f == "size":
                    if not (_vec(v) and all(x > 0 for x in v)):
                        errs.append(f"{w}: box 'size' must be [width, height, depth], all numbers > 0")
                elif not (_num(v) and v > 0):
                    errs.append(f"{w}: {shape} '{f}' must be a number > 0")
        for f in ("position", "rotation"):
            if f in p and not _vec(p[f]):
                errs.append(f"{w}: '{f}' must be three numbers [x, y, z]")
        if "color" in p and not (isinstance(p["color"], str) and HEX.match(p["color"])):
            errs.append(f"{w}: 'color' must be a hex string like #aabbcc")
        if "label" in p and not isinstance(p["label"], str):
            errs.append(f"{w}: 'label' must be a string")
        if "parent" in p and not isinstance(p["parent"], str):
            errs.append(f"{w}: 'parent' must be a string id")
    for i, p in enumerate(parts):
        if isinstance(p, dict) and isinstance(p.get("parent"), str) and p["parent"] not in ids:
            errs.append(f"parts[{i}]: parent {p['parent']!r} is not the id of any part")
    if not errs:
        for i, p in enumerate(parts):   # cycle check
            seen, cur = set(), p
            while isinstance(cur, dict) and "parent" in cur:
                if cur["id"] in seen:
                    errs.append(f"parts[{i}]: parent chain loops through {cur['id']!r}"); break
                seen.add(cur["id"]); cur = parts[ids[cur["parent"]]]
    return errs


def _half_extents(p: dict) -> tuple[float, float, float]:
    s = p["shape"]
    if s == "box":
        return tuple(x / 2 for x in p["size"])
    if s == "sphere":
        return (p["radius"],) * 3
    return (p["radius"], p["height"] / 2, p["radius"])   # cylinder, cone


def resolve(data: dict) -> dict:
    """Validate, then return {name, units, parts:[... world position ...], bounds, counts}. Raises ConstructError."""
    errs = validate(data)
    if errs:
        raise ConstructError(errs)
    by_id = {p["id"]: p for p in data["parts"]}

    def world(p):
        pos = list(p.get("position", [0, 0, 0]))
        if "parent" in p:
            pp = world(by_id[p["parent"]])
            pos = [a + b for a, b in zip(pos, pp)]
        return pos

    out, lo, hi = [], [math.inf] * 3, [-math.inf] * 3
    for p in data["parts"]:
        w = world(p)
        he = _half_extents(p)   # axis-aligned extents of the unrotated part; rotation is ignored for bounds
        for k in range(3):
            lo[k] = min(lo[k], w[k] - he[k]); hi[k] = max(hi[k], w[k] + he[k])
        row = {"id": p["id"], "shape": p["shape"], "position": w, "rotation": list(p.get("rotation", [0, 0, 0])),
               "color": p.get("color", DEFAULT_COLOR), "label": p.get("label", p["id"])}
        for f in SHAPES[p["shape"]]:
            row[f] = p[f]
        out.append(row)
    counts: dict[str, int] = {}
    for r in out:
        counts[r["shape"]] = counts.get(r["shape"], 0) + 1
    return {"name": data.get("name", "construct"), "units": data.get("units", ""), "parts": out,
            "bounds": {"min": lo, "max": hi, "size": [h - l for l, h in zip(lo, hi)]}, "counts": counts}
