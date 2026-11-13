"""A small YAML subset reader (standard library only).

Supported: block mappings, block lists ("- item", "- key: value" mappings), indentation with spaces,
scalars (int, float, true/false/null, quoted and plain strings), inline lists like [1, 2, 3], "#" comments.
Not supported: anchors, tags, multi-line scalars, flow mappings, multiple documents. Anything it cannot read
raises ValueError with a line number rather than guessing."""
from __future__ import annotations
import re

_NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def _strip_comment(s: str) -> str:
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_flow(s: str) -> list[str]:
    parts, cur, q, depth = [], [], None, 0
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch; cur.append(ch)
        elif ch == "[":
            depth += 1; cur.append(ch)
        elif ch == "]":
            depth -= 1; cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def scalar(tok: str, ln: int = 0):
    t = tok.strip()
    if t == "":
        return None
    if t[0] in "\"'":
        if len(t) < 2 or t[-1] != t[0]:
            raise ValueError(f"line {ln}: unterminated quoted string")
        return t[1:-1]
    if t[0] == "[":
        if t[-1] != "]":
            raise ValueError(f"line {ln}: unterminated inline list")
        return [scalar(p, ln) for p in _split_flow(t[1:-1])]
    if t[0] in "{&*!|>":
        raise ValueError(f"line {ln}: unsupported YAML syntax {t[0]!r}")
    low = t.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    if _NUM.match(t):
        return float(t) if any(c in t for c in ".eE") else int(t)
    return t


def _lines(text: str):
    for n, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError(f"line {n}: tabs are not allowed for indentation")
        s = _strip_comment(raw)
        if s.strip() == "" or s.strip() == "---":
            continue
        yield n, len(s) - len(s.lstrip(" ")), s.strip()


def _key_split(body: str, ln: int):
    m = re.match(r"""^("[^"]*"|'[^']*'|[^:\s][^:]*?)\s*:(?:\s+(.*))?$""", body)
    if not m:
        return None
    k = m.group(1)
    if k[0] in "\"'":
        k = k[1:-1]
    return k.strip(), (m.group(2) or "")


def loads(text: str):
    items = list(_lines(text))
    if not items:
        raise ValueError("empty document")
    pos = [0]

    def block(indent: int):
        n, ind, body = items[pos[0]]
        if body.startswith("- ") or body == "-":
            return seq(ind)
        return mapping(ind)

    def seq(indent: int):
        out = []
        while pos[0] < len(items):
            n, ind, body = items[pos[0]]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError(f"line {n}: unexpected indentation")
            if not (body.startswith("- ") or body == "-"):
                break
            rest = body[1:].strip()
            if rest == "":
                pos[0] += 1
                if pos[0] < len(items) and items[pos[0]][1] > indent:
                    out.append(block(items[pos[0]][1]))
                else:
                    out.append(None)
                continue
            kv = _key_split(rest, n) if rest[0] not in "[\"'" or _key_split(rest, n) else None
            if kv and not rest.startswith("["):
                # mapping item: rewrite the line as a mapping line at the inner indent
                inner = indent + (len(body) - len(body[1:].lstrip()))
                items[pos[0]] = (n, inner, rest)
                out.append(mapping(inner))
            else:
                out.append(scalar(rest, n)); pos[0] += 1
        return out

    def mapping(indent: int):
        out = {}
        while pos[0] < len(items):
            n, ind, body = items[pos[0]]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError(f"line {n}: unexpected indentation")
            if body.startswith("- "):
                break
            kv = _key_split(body, n)
            if not kv:
                raise ValueError(f"line {n}: expected 'key: value', got {body!r}")
            k, v = kv
            if k in out:
                raise ValueError(f"line {n}: duplicate key {k!r}")
            pos[0] += 1
            if v.strip() == "":
                if pos[0] < len(items) and (items[pos[0]][1] > indent or (items[pos[0]][1] == indent and items[pos[0]][2].startswith("- "))):
                    out[k] = block(items[pos[0]][1])
                else:
                    out[k] = None
            else:
                out[k] = scalar(v, n)
        return out

    first = items[0]
    res = block(first[1])
    if pos[0] < len(items):
        raise ValueError(f"line {items[pos[0]][0]}: could not parse (unexpected content)")
    return res
