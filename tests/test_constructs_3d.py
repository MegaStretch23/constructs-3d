import json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from constructs_3d import yamlite
from constructs_3d.cli import main
from constructs_3d.model import ConstructError, load, resolve, validate
from constructs_3d.viewer import render, SCENE_JS, VENDOR

LAMP = ROOT / "examples" / "desk-lamp.json"
SHELF = ROOT / "examples" / "bookshelf.yaml"
BAD = ROOT / "examples" / "invalid.json"


def part(**kw):
    d = {"id": "p", "shape": "box", "size": [1, 2, 3]}
    d.update(kw); return d


def doc(*parts):
    return {"name": "t", "parts": list(parts)}


# --- yaml subset
def test_yaml_mapping_and_list():
    d = yamlite.loads("name: X\nparts:\n  - id: a\n    size: [1, 2.5, -3]\n  - id: b\n")
    assert d == {"name": "X", "parts": [{"id": "a", "size": [1, 2.5, -3]}, {"id": "b"}]}

def test_yaml_scalars_and_comments():
    d = yamlite.loads('a: true  # c\nb: "x # y"\nc: null\nd: 1e3\ne: hello world\n')
    assert d == {"a": True, "b": "x # y", "c": None, "d": 1000.0, "e": "hello world"}

def test_yaml_rejects_anchor_and_tabs():
    with pytest.raises(ValueError, match="unsupported"): yamlite.loads("a: &x 1\n")
    with pytest.raises(ValueError, match="tabs"): yamlite.loads("a:\n\tb: 1\n")

def test_yaml_duplicate_key_and_bad_line():
    with pytest.raises(ValueError, match="duplicate"): yamlite.loads("a: 1\na: 2\n")
    with pytest.raises(ValueError, match="line 2"): yamlite.loads("a: 1\njust text\n")

def test_yaml_matches_json_for_same_data(tmp_path):
    y = load(SHELF)
    assert y["name"] == "Bookshelf" and len(y["parts"]) == 7 and y["parts"][0]["size"] == [2, 120, 30]


# --- validation
def test_examples_valid():
    assert validate(load(LAMP)) == [] and validate(load(SHELF)) == []

def test_invalid_example_reports_every_problem():
    errs = validate(load(BAD))
    text = "\n".join(errs)
    assert "size" in text and "duplicate id 'a'" in text and "shape must be one of" in text
    assert "parent 'zzz'" in text and "color" in text

def test_top_level_not_mapping():
    assert validate([1]) and validate({"parts": []}) and validate({"parts": "x"})

@pytest.mark.parametrize("bad", [
    part(size=[1, 2]), part(size=[1, -2, 3]), part(size=[1, True, 3]), part(position=[0, 0]),
    part(color="#fff"), part(label=3), part(rotation="x"),
])
def test_bad_fields(bad):
    assert validate(doc(bad))

def test_round_shapes_need_radius_height():
    assert validate(doc({"id": "c", "shape": "cylinder", "radius": 1}))
    assert validate(doc({"id": "s", "shape": "sphere", "radius": 0}))
    assert not validate(doc({"id": "s", "shape": "sphere", "radius": 1}))

def test_nan_rejected():
    assert validate(doc(part(position=[float("nan"), 0, 0])))

def test_parent_cycle():
    errs = validate(doc(part(id="a", parent="b"), part(id="b", parent="a")))
    assert any("loops" in e for e in errs)

def test_self_parent_cycle():
    assert any("loops" in e for e in validate(doc(part(id="a", parent="a"))))


# --- resolve
def test_parent_offsets_accumulate():
    s = resolve(doc(part(id="a", position=[1, 0, 0]), part(id="b", parent="a", position=[0, 5, 0]), part(id="c", parent="b", position=[0, 0, 2])))
    assert [p["position"] for p in s["parts"]] == [[1, 0, 0], [1, 5, 0], [1, 5, 2]]

def test_bounds_box_and_sphere():
    s = resolve(doc(part(id="a", size=[2, 2, 2]), {"id": "s", "shape": "sphere", "radius": 1, "position": [10, 0, 0]}))
    assert s["bounds"]["min"] == [-1, -1, -1] and s["bounds"]["max"] == [11, 1, 1] and s["bounds"]["size"] == [12, 2, 2]

def test_defaults_and_counts():
    s = resolve(doc(part(id="a"), part(id="b")))
    assert s["parts"][0]["color"] == "#8899aa" and s["parts"][0]["label"] == "a" and s["counts"] == {"box": 2}

def test_resolve_raises_with_errors():
    with pytest.raises(ConstructError) as e: resolve(doc(part(size=[0, 0, 0])))
    assert e.value.errors


# --- viewer / html
def test_render_contains_scene_and_three():
    html = render(resolve(load(LAMP)))
    assert '"Desk lamp"' in html and "WebGLRenderer" in html
    assert html.count('id="scene"') == 1 and "5 parts" in html

def test_render_escapes_script_end_and_title():
    d = doc(part(label="</script><b>"))
    d["name"] = "<img src=x>"
    html = render(resolve(d))
    assert "<img src=x>" not in html.split("<script")[0] and "&lt;img" in html
    scene = html.split('id="scene" type="application/json">')[1].split("</script>")[0]
    assert "<\\/script" in scene and json.loads(scene)["parts"][0]["label"] == "</script><b>"

def test_vendored_three_has_license():
    assert (VENDOR / "LICENSE-three.txt").read_text().startswith("The MIT License")


# --- cli
def test_cli_validate_ok_and_fail(capsys):
    assert main(["validate", str(LAMP)]) == 0
    assert main(["validate", str(BAD)]) == 1
    assert "invalid:" in capsys.readouterr().err

def test_cli_missing_file(capsys):
    assert main(["validate", "/nonexistent/x.json"]) == 2

def test_cli_bad_json(tmp_path, capsys):
    p = tmp_path / "x.json"; p.write_text("{nope")
    assert main(["validate", str(p)]) == 1

def test_cli_info_json(capsys):
    assert main(["info", str(LAMP), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "Desk lamp" and out["counts"] == {"cylinder": 2, "box": 1, "cone": 1, "sphere": 1}

def test_cli_build_writes_file(tmp_path, capsys):
    o = tmp_path / "o.html"
    assert main(["build", str(SHELF), "-o", str(o), "--title", "Mine"]) == 0
    t = o.read_text(encoding="utf-8")
    assert t.startswith("<!doctype html>") and "<title>Mine</title>" in t and "7 parts" in t

def test_cli_build_invalid_writes_nothing(tmp_path):
    o = tmp_path / "o.html"
    assert main(["build", str(BAD), "-o", str(o)]) == 1 and not o.exists()

def test_module_entrypoint():
    r = subprocess.run([sys.executable, "-m", "constructs_3d", "info", str(LAMP)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "Desk lamp: 5 parts" in r.stdout


# --- scene JS under node (no browser needed: geometry + meshes only)
@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_scene_js_builds_meshes_in_node(tmp_path):
    scene = resolve(load(LAMP))
    (tmp_path / "scene.mjs").write_text(SCENE_JS)
    (tmp_path / "three.mjs").write_text((VENDOR / "three.module.min.js").read_text())
    (tmp_path / "data.json").write_text(json.dumps(scene))
    (tmp_path / "run.mjs").write_text(
        "import * as THREE from './three.mjs'; import {buildScene, frame} from './scene.mjs'; import fs from 'fs';\n"
        "const d = JSON.parse(fs.readFileSync(new URL('./data.json', import.meta.url)));\n"
        "const s = new THREE.Scene(); const r = buildScene(THREE, s, d); const f = frame(d);\n"
        "console.log(JSON.stringify({n: r.meshes.length, types: r.meshes.map(m => m.geometry.type), id: r.meshes[4].userData.id, y: r.meshes[1].position.y, r: f.radius > 0}));\n")
    r = subprocess.run(["node", str(tmp_path / "run.mjs")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["n"] == 5 and out["types"] == ["CylinderGeometry", "CylinderGeometry", "BoxGeometry", "ConeGeometry", "SphereGeometry"]
    assert out["id"] == "bulb" and out["y"] == 17 and out["r"]
