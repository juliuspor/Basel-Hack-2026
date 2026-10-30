"""Build a parking-area model from a layout JSON and export it as USDZ.

Usage:
  blender -b --factory-startup -P generate_area.py -- LAYOUT.json OUT_DIR \
      [--occupied r1_02,r1_05] [--no-render]

Writes OUT_DIR/<id>.usdz, OUT_DIR/<id>.blend and OUT_DIR/<id>-preview.png.
The USDZ holds the empty structure plus one `slot_<zone>_<nn>` Xform per
parking spot; the app attaches bikes or status markers to those.
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenegen as sg  # noqa: E402


def arch_profile(depth, height, foot=0.1, steps=16):
    """Quarter ellipse from the rear foot up to the front top edge, as (y, z)."""
    points = []
    for i in range(steps + 1):
        t = math.pi / 2 * i / steps
        points.append((depth * math.cos(t), foot + (height - foot) * math.sin(t)))
    return points


def build_curved_shelter(spec, root):
    length, depth, height = spec["length"], spec["depth"], spec["height"]
    steel = sg.material("galvanised_steel", (0.62, 0.64, 0.66), roughness=0.35, metallic=0.8)
    glass = sg.material("polycarbonate", (0.85, 0.9, 0.95, 0.25), roughness=0.1)
    paving = sg.material("paving", (0.55, 0.54, 0.52), roughness=0.9)

    sg.surface_object("ground", [[(-0.6, -1.5, 0), (length + 0.6, -1.5, 0)],
                                 [(-0.6, depth + 0.4, 0), (length + 0.6, depth + 0.4, 0)]],
                      paving, root)

    profile = arch_profile(depth, height)
    arch_xs = [length * i / (spec["arches"] - 1) for i in range(spec["arches"])]
    post_xs = [length * i / (spec["front_posts"] - 1) for i in range(spec["front_posts"])]
    tubes = []
    for x in arch_xs:
        tubes.append(sg.tube_mesh([(x, depth, 0)] + [(x, y, z) for y, z in profile], 0.03))
    for x in post_xs:
        tubes.append(sg.tube_mesh([(x, 0, 0), (x, 0, height)], 0.035))
    for y, z in [profile[-1], profile[0], profile[6], profile[11]]:
        tubes.append(sg.tube_mesh([(0, y, z), (length, y, z)], 0.025))
    sg.merge_object("frame", tubes, steel, root)

    sg.surface_object("roof", [[(0, y, z), (length, y, z)] for y, z in profile], glass, root)
    for x in (0, length):
        sg.polygon_object(f"end_panel_{'left' if x == 0 else 'right'}",
                          [(x, y, z) for y, z in profile] + [(x, 0, 0.1)], glass, root)


def build_rack(rack, depth, root):
    """Staggered front-wheel rack. Returns the slot empties."""
    steel = bpy.data.materials["galvanised_steel"]
    rack_y = depth - rack["rear_offset"]
    xs = [rack["start"] + i * rack["pitch"] for i in range(rack["slots"])]
    tubes = [sg.tube_mesh([(xs[0] - 0.25, y, 0.04), (xs[-1] + 0.25, y, 0.04)], 0.015)
             for y in (rack_y - 0.25, rack_y + 0.3)]
    slots = []
    for i, x in enumerate(xs):
        high = rack.get("staggered") and i % 2 == 1
        h = 0.62 if high else 0.42
        for dx in (-0.04, 0.04):
            tubes.append(sg.tube_mesh([(x + dx, rack_y - 0.25, 0.04), (x + dx, rack_y - 0.12, h),
                                       (x + dx, rack_y + 0.12, h), (x + dx, rack_y + 0.3, 0.04)],
                                      0.008))
        # Slot origin sits on the ground under the bike's centre, front wheel in the holder.
        slots.append(sg.empty(f"slot_{rack['id']}_{i + 1:02d}", (x, rack_y - 0.53, 0), root,
                              zone=rack["id"], kind="rack_slot"))
    sg.merge_object(f"rack_{rack['id']}", tubes, steel, root)
    return slots


def add_preview(layout, slots, occupied, out_png):
    """Bikes and status discs as the app would show them, then render a still."""
    free_mat = sg.material("status_free", (0.15, 0.75, 0.3))
    taken_mat = sg.material("status_taken", (0.85, 0.2, 0.2))
    colours = [(0.1, 0.1, 0.12), (0.7, 0.1, 0.1), (0.85, 0.85, 0.85), (0.1, 0.25, 0.6)]
    for i, slot in enumerate(slots):
        key = slot.name.removeprefix("slot_")
        taken = key in occupied
        disc = sg.surface_object(f"status_{key}", [[(-0.12, -0.12, 0.005), (0.12, -0.12, 0.005)],
                                                   [(-0.12, 0.12, 0.005), (0.12, 0.12, 0.005)]],
                                 taken_mat if taken else free_mat, slot)
        disc.location = (0, -0.75, 0)
        if taken:
            sg.build_bike(f"bike_{key}", colours[i % len(colours)], slot)

    scene = bpy.context.scene
    length, depth = layout["shelter"]["length"], layout["shelter"]["depth"]
    target = Vector((length / 2, depth / 2, 0.8))
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(cam)
    cam.location = (length * 0.9, -3.4, 2.3)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 22
    scene.camera = cam

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
    sun.data.energy = 4.0
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.68, 0.8, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
    scene.world = world
    scene.view_settings.view_transform = "Standard"

    engines = {item.identifier for item in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = next(e for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH")
                               if e in engines)
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("layout")
    parser.add_argument("out_dir")
    parser.add_argument("--occupied", default="", help="comma-separated slot keys, e.g. r1_02,r1_05")
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(sg.script_args())

    with open(args.layout) as f:
        layout = json.load(f)
    if layout["kind"] != "curved_shelter":
        sys.exit(f"unsupported kind: {layout['kind']}")

    os.makedirs(args.out_dir, exist_ok=True)
    base = os.path.join(os.path.abspath(args.out_dir), layout["id"])

    sg.reset_scene()
    root = sg.empty(layout["id"], (0, 0, 0), area_name=layout["name"])
    build_curved_shelter(layout["shelter"], root)
    slots = []
    for rack in layout["racks"]:
        slots += build_rack(rack, layout["shelter"]["depth"], root)

    sg.export_usdz(base + ".usdz")
    bpy.ops.wm.save_as_mainfile(filepath=base + ".blend")
    print(f"wrote {base}.usdz and {base}.blend ({len(slots)} slots)")

    if not args.no_render:
        occupied = {key for key in args.occupied.split(",") if key}
        add_preview(layout, slots, occupied, base + "-preview.png")
        print(f"wrote {base}-preview.png")


if __name__ == "__main__":
    main()
