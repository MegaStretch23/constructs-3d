"""Regenerate MANIFEST.json: runs the CLI on examples/ and records what it printed (python samples/make_manifest.py)."""
import hashlib, json, subprocess, sys, tempfile, platform
from pathlib import Path
R = Path(__file__).resolve().parent.parent
runs = []
def run(args, html=None):
    r = subprocess.run([sys.executable, "-m", "constructs_3d", *args], cwd=R, capture_output=True, text=True)
    row = {"command": "constructs-3d " + " ".join(args), "exit_code": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    if html and html.exists():
        b = html.read_bytes(); row["html_bytes"] = len(b); row["html_sha256"] = hashlib.sha256(b).hexdigest()
    runs.append(row)
with tempfile.TemporaryDirectory() as td:
    for ex in ("examples/desk-lamp.json", "examples/bookshelf.yaml"):
        run(["validate", ex]); run(["info", ex])
        o = Path(td) / (Path(ex).stem + ".html"); run(["build", ex, "-o", o.name] if False else ["build", ex, "-o", str(o)], o)
    run(["validate", "examples/invalid.json"])
for r in runs:
    r["stdout"] = r["stdout"].replace(td, "<tmp>"); r["command"] = r["command"].replace(td, "<tmp>")
out = {"generated_by": "samples/make_manifest.py", "python": platform.python_version(), "note": "Outputs of the CLI on the files in examples/; the HTML is not stored (about 700 KB each), only its size and SHA-256.", "runs": runs}
(Path(__file__).parent / "MANIFEST.json").write_text(json.dumps(out, indent=2) + "\n")
print(f"{len(runs)} runs written")
