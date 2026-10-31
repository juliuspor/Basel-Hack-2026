"""Kenney models for the app's spot view, as plain vertex-coloured geometry.

The spot view runs three.js r149 from the app bundle, where neither GLTFLoader nor
loading image files is available. This reads the Kenney CC0 glTF models that the
three.js prototype in assets/ uses, bakes each material (or its palette texture) into
vertex colours, flattens the node tree, and writes the meshes into Spot/models.js.
Crowns, bark and shrubs get the same colours as in the prototype.

Run: code/backend/.venv/bin/python code/scene-generator/kenney_models.py  (needs Pillow)
"""

import base64
import json
import math
import struct
from array import array
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[2]
KENNEY = ROOT / "assets/threejs-prototype-3d-world-of-endress-hauser/kenney"
OUT = ROOT / "code/ios/BikeSlot/Spot/models.js"

# name: (kit, crown colour or None). Crown and bark colours as in the prototype's main.js.
MODELS = {
    "tree_default_fall": ("nature-kit", (84, 134, 60)),
    "tree_detailed_fall": ("nature-kit", (150, 156, 62)),
    "tree_oak_fall": ("nature-kit", (70, 116, 52)),
    "tree_fat_fall": ("nature-kit", (110, 48, 58)),
    "plant_bushLarge": ("nature-kit", None),
    "plant_bushDetailed": ("nature-kit", None),
    "light-curved": ("city-kit-roads", None),
    "sedan": ("car-kit", None),
    "suv": ("car-kit", None),
    "hatchback-sports": ("car-kit", None),
    "van": ("car-kit", None),
}
BARK, SHRUB = (110, 88, 70), (78, 118, 62)
COMPONENTS = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2), 5121: ("B", 1)}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def linear(c):  # sRGB 0..255 to linear 0..1, the space three.js expects for vertex colours
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def matrix(node):
    if "matrix" in node:
        m = node["matrix"]
        return [m[0], m[4], m[8], m[12], m[1], m[5], m[9], m[13], m[2], m[6], m[10], m[14]]
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = node.get("scale", [1, 1, 1])
    tx, ty, tz = node.get("translation", [0, 0, 0])
    return [(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y - z * w) * sy, 2 * (x * z + y * w) * sz, tx,
            2 * (x * y + z * w) * sx, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z - x * w) * sz, ty,
            2 * (x * z - y * w) * sx, 2 * (y * z + x * w) * sy, (1 - 2 * (x * x + y * y)) * sz, tz]


def multiply(a, b):  # 3x4 affine matrices, row-major
    out = []
    for r in range(3):
        for c in range(4):
            v = sum(a[r * 4 + k] * b[k * 4 + c] for k in range(3))
            out.append(v + (a[r * 4 + 3] if c == 3 else 0))
    return out


def convert(name, kit, crown):
    path = KENNEY / kit / f"{name}.glb"
    data = path.read_bytes()
    size = struct.unpack("<I", data[12:16])[0]
    gltf, binary = json.loads(data[20:20 + size]), data[28 + size:]

    def accessor(index):
        a = gltf["accessors"][index]
        view = gltf["bufferViews"][a["bufferView"]]
        kind, bytes_ = COMPONENTS[a["componentType"]]
        width = WIDTH[a["type"]]
        start = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = view.get("byteStride", width * bytes_)
        return [struct.unpack_from("<" + kind * width, binary, start + i * stride) for i in range(a["count"])]

    palette = {}

    def colour(material, uv):
        m = gltf["materials"][material]
        label = m.get("name", "")
        if crown and label.startswith("leafs"):
            return [linear(v) for v in crown]
        if label.startswith("wood"):
            return [linear(v) for v in BARK]
        if label.startswith("grass"):
            return [linear(v) for v in SHRUB]
        pbr = m.get("pbrMetallicRoughness", {})
        factor = pbr.get("baseColorFactor", [1, 1, 1, 1])[:3]
        if "baseColorTexture" not in pbr or uv is None:
            return factor
        source = gltf["textures"][pbr["baseColorTexture"]["index"]]["source"]
        if source not in palette:
            palette[source] = Image.open(path.parent / gltf["images"][source]["uri"]).convert("RGB")
        image = palette[source]
        px = image.getpixel((min(int(uv[0] % 1 * image.width), image.width - 1),
                             min(int(uv[1] % 1 * image.height), image.height - 1)))
        return [f * linear(v) for f, v in zip(factor, px)]

    positions, normals, colours, indices = array("f"), array("f"), array("B"), []

    def visit(index, parent):
        node = gltf["nodes"][index]
        m = multiply(parent, matrix(node))
        for primitive in gltf["meshes"][node["mesh"]]["primitives"] if "mesh" in node else []:
            attributes = primitive["attributes"]
            points, ns = accessor(attributes["POSITION"]), accessor(attributes["NORMAL"])
            uvs = accessor(attributes["TEXCOORD_0"]) if "TEXCOORD_0" in attributes else [None] * len(points)
            base = len(positions) // 3
            for p, n, uv in zip(points, ns, uvs):
                positions.extend(sum(m[r * 4 + k] * p[k] for k in range(3)) + m[r * 4 + 3] for r in range(3))
                nx, ny, nz = (sum(m[r * 4 + k] * n[k] for k in range(3)) for r in range(3))
                length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
                normals.extend((nx / length, ny / length, nz / length))
                colours.extend(round(max(0, min(1, v)) * 255) for v in colour(primitive.get("material", 0), uv))
            ids = [i[0] for i in accessor(primitive["indices"])] if "indices" in primitive else range(len(points))
            indices.extend(base + i for i in ids)
        for child in node.get("children", []):
            visit(child, m)

    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]
    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visit(root, identity)
    index = array("H" if len(positions) // 3 < 65536 else "I", indices)
    encode = lambda a: base64.b64encode(a.tobytes()).decode()
    return {"p": encode(positions), "n": encode(normals), "c": encode(colours), "i": encode(index),
            "wide": index.typecode == "I"}


def main():
    models = {name: convert(name, kit, crown) for name, (kit, crown) in MODELS.items()}
    OUT.write_text("// Generated by code/scene-generator/kenney_models.py from Kenney's CC0 Nature Kit,\n"
                   "// City Kit (Roads) and Car Kit (www.kenney.nl). Do not edit by hand.\n"
                   f"window.MODELS = {json.dumps(models, separators=(',', ':'))};\n")
    print(f"wrote {len(models)} models, {OUT.stat().st_size // 1024} KB, to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
