# constructs-3d

Describe a "construct" (a product or object made of simple parts) in JSON or a small YAML subset, validate it, and write **one standalone HTML file** with an interactive three.js view. The CLI is standard-library Python; the viewer is static and client-side (three.js is bundled inline, MIT license, so the file works from disk with no network).

**What "construct" means here.** The original idea was titled only "Visualize product 'Constructs' in 3D" and I could not find any further context for it, so this is my interpretation: a small developer tool that turns a structured description of a thing into an interactive 3D view. A construct is a list of parts; each part is a box, cylinder, sphere or cone with a position, optional rotation, colour, label and optional parent.

## Quickstart

```bash
git clone https://github.com/MegaStretch23/constructs-3d
cd constructs-3d
python3 -m constructs_3d validate examples/desk-lamp.json
python3 -m constructs_3d info examples/bookshelf.yaml
python3 -m constructs_3d build examples/desk-lamp.json -o desk-lamp.html
# open desk-lamp.html in a browser: drag to orbit, wheel to zoom, click a part to select it
```

Or `pip install .` and use the `constructs-3d` command. Python 3.9+, no dependencies.

## Input format

```yaml
name: Bookshelf          # optional
units: cm                # optional label shown in the viewer, not converted
parts:
  - id: left             # required, unique
    shape: box           # box | cylinder | sphere | cone
    size: [2, 120, 30]   # box: [width, height, depth]; cylinder/cone: radius + height; sphere: radius
    position: [-39, 60, 0]   # optional, y is up
    rotation: [0, 0, 0]      # optional, degrees
    color: "#8b5a2b"         # optional, #rrggbb
    label: Left side         # optional, defaults to id
    parent: other-id         # optional: position is added to the parent's (translation only)
```

JSON uses the same keys. YAML support is a deliberately small subset (block mappings and lists, inline `[a, b]` lists, quoted and plain scalars, `#` comments); anchors, tags, multi-line scalars and flow mappings are rejected with a line number rather than guessed.

Validation reports every problem it finds, not just the first (see the last sample below).

## Sample output (saved run)

These are real outputs from `samples/make_manifest.py`, recorded in `samples/MANIFEST.json` (Python 3.12.3):

```
$ constructs-3d info examples/desk-lamp.json
Desk lamp: 5 parts 1 box, 1 cone, 2 cylinder, 1 sphere
bounds min [-8, 0.0, -8] max [25, 32.6, 8] size [33, 32.6, 16]

$ constructs-3d info examples/bookshelf.yaml
Bookshelf: 7 parts 6 box, 1 sphere
bounds min [-40.0, 0.0, -15.0] max [40.0, 120.0, 15.0] size [80.0, 120.0, 30.0]

$ constructs-3d build examples/desk-lamp.json -o desk-lamp.html
wrote desk-lamp.html (697724 bytes, 5 parts)

$ constructs-3d validate examples/invalid.json        # exit code 1
invalid: parts[0]: box 'size' must be [width, height, depth], all numbers > 0
invalid: parts[1]: duplicate id 'a' (first at parts[0])
invalid: parts[1]: shape must be one of ['box', 'cone', 'cylinder', 'sphere'], got 'torus'
invalid: parts[2]: 'color' must be a hex string like #aabbcc
invalid: parts[2]: parent 'zzz' is not the id of any part
```

## Limits

- Bounds (`info`, camera framing) use the axis-aligned size of each part before rotation; a rotated part can poke outside the reported box.
- `parent` adds positions only; it does not rotate or scale children with the parent.
- Only the four primitive shapes; no meshes, textures or import of CAD formats.
- The WebGL viewer has been checked here by running the scene-building code under Node (part count, geometry types, positions) and syntax-checking the page script. I had no browser on the build machine, so I have not looked at a rendered frame; if the page renders wrongly in yours, please open an issue.
- The generated HTML is about 700 KB because it inlines three.js.

## Tests

`python3 -m pytest` runs 34 tests in `tests/` (YAML subset, validation, parent resolution, bounds, HTML escaping, CLI exit codes, and the scene code under Node when Node is installed).

## Related

I also publish hosted data tools on Apify, for example the pay-per-event [SEC Form 4 insider cluster scanner](https://apify.com/johnveds15/sec-form4-insider-clusters). They are unrelated to this tool; constructs-3d is free and has no paid version.

## License

MIT for this code. The bundled `constructs_3d/vendor/three.module.min.js` is three.js, MIT, license text in `constructs_3d/vendor/LICENSE-three.txt`.
