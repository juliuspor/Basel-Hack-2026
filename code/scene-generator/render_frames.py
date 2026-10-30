"""Render simulated camera frames of an area filling up over a morning.

Usage:
  blender -b --factory-startup -P render_frames.py -- LAYOUT.json OUT_DIR \
      [--frames 11] [--fill 0.9] [--seed 1]

Writes OUT_DIR/<id>/empty.jpg, frame_NN.jpg and camera.json. camera.json holds
the calibration the backend needs (slot label points and regions in pixels)
and the ground truth per frame, which only the simulator uses for scoring.
"""

import argparse
import json
import math
import os
import random
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_area as ga  # noqa: E402
import scenegen as sg  # noqa: E402

WIDTH, HEIGHT = 800, 600  # ESP32-CAM SVGA
# Share of the morning's peak occupancy at each step from 07:00 to 09:30.
ARRIVALS = [0.0, 0.05, 0.15, 0.3, 0.5, 0.68, 0.82, 0.9, 0.95, 1.0, 1.0]
BIKE_COLOURS = [(0.1, 0.1, 0.12), (0.7, 0.1, 0.1), (0.85, 0.85, 0.85), (0.1, 0.25, 0.6),
                (0.15, 0.4, 0.2), (0.9, 0.5, 0.1), (0.3, 0.3, 0.32)]


def setup_camera_and_light(layout):
    scene = bpy.context.scene
    length, depth = layout["shelter"]["length"], layout["shelter"]["depth"]
    paving = bpy.data.materials["paving"]
    facade = sg.material("facade", (0.78, 0.79, 0.8), roughness=0.8)
    sg.surface_object("wall", [[(-3, depth + 0.4, 0), (length + 3, depth + 0.4, 0)],
                               [(-3, depth + 0.4, 5), (length + 3, depth + 0.4, 5)]], facade)
    sg.surface_object("forecourt", [[(-3, -6, -0.01), (length + 3, -6, -0.01)],
                                    [(-3, depth + 0.4, -0.01), (length + 3, depth + 0.4, -0.01)]], paving)

    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(cam)
    # Mounted across the forecourt, slightly off-centre, framing the whole shelter.
    cam.location = (length / 2 + 0.4, -2.8, 3.2)
    target = Vector((length / 2, depth * 0.55, 0.35))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 18 * (target - cam.location).length / (length / 2 + 0.7)
    scene.camera = cam

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    scene.collection.objects.link(sun)
    # Light from the camera side so bike shadows fall along the bike, not onto neighbours.
    sun.rotation_euler = (math.radians(50), 0, math.radians(8))
    sun.data.energy = 3.5
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.7, 0.74, 0.8, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world
    scene.view_settings.view_transform = "Standard"

    engines = {item.identifier for item in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = next(e for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH")
                               if e in engines)
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 85
    return cam


def to_pixels(scene, cam, co):
    v = world_to_camera_view(scene, cam, Vector(co))
    return [round(v.x * WIDTH, 1), round((1 - v.y) * HEIGHT, 1)]


def calibrate(scene, cam, slots):
    """Label point and front-wheel region of every slot, in image pixels."""
    bpy.context.view_layer.update()
    result = {}
    for n, slot in enumerate(slots, start=1):
        m = slot.matrix_world
        corners = [to_pixels(scene, cam, m @ Vector((x, y, z)))
                   for x in (-0.07, 0.07) for y in (0.1, 0.6) for z in (0.05, 0.72)]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        result[slot.name.removeprefix("slot_")] = {
            "label": n,
            "label_px": to_pixels(scene, cam, m @ Vector((0, -0.95, 0))),
            "roi": [min(xs), min(ys), max(xs), max(ys)],
        }
    rois = [s["roi"] for s in result.values()] + [[*s["label_px"], *s["label_px"]] for s in result.values()]
    pad = 40
    area_roi = [max(0, min(r[0] for r in rois) - pad), max(0, min(r[1] for r in rois) - pad * 3),
                min(WIDTH, max(r[2] for r in rois) + pad), min(HEIGHT, max(r[3] for r in rois) + pad)]
    return result, [round(v, 1) for v in area_roi]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("layout")
    parser.add_argument("out_dir")
    parser.add_argument("--frames", type=int, default=len(ARRIVALS))
    parser.add_argument("--fill", type=float, default=0.9, help="peak share of slots taken")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(sg.script_args())

    with open(args.layout) as f:
        layout = json.load(f)
    out = os.path.join(os.path.abspath(args.out_dir), layout["id"])
    os.makedirs(out, exist_ok=True)

    scene = sg.reset_scene()
    root = sg.empty(layout["id"], (0, 0, 0))
    ga.build_curved_shelter(layout["shelter"], root)
    slots = []
    for rack in layout["racks"]:
        slots += ga.build_rack(rack, layout["shelter"]["depth"], root)
    cam = setup_camera_and_light(layout)
    slot_cal, area_roi = calibrate(scene, cam, slots)

    rng = random.Random(args.seed)
    order = [s.name.removeprefix("slot_") for s in slots]
    rng.shuffle(order)
    colours = {key: rng.choice(BIKE_COLOURS) for key in order}

    def render(path, occupied):
        for obj in [o for o in bpy.data.objects if o.name.startswith("bike_")]:
            bpy.data.objects.remove(obj)
        for slot in slots:
            key = slot.name.removeprefix("slot_")
            if key in occupied:
                sg.build_bike(f"bike_{key}", colours[key], slot)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)

    render(os.path.join(out, "empty.jpg"), set())
    frames = []
    for i in range(args.frames):
        share = ARRIVALS[round(i * (len(ARRIVALS) - 1) / max(1, args.frames - 1))]
        occupied = sorted(order[:round(share * args.fill * len(order))])
        minutes = 7 * 60 + round(i * 150 / max(1, args.frames - 1))
        name = f"frame_{i:02d}.jpg"
        render(os.path.join(out, name), set(occupied))
        frames.append({"file": name, "time": f"{minutes // 60:02d}:{minutes % 60:02d}",
                       "occupied": occupied})
        print(f"rendered {layout['id']} {name} ({len(occupied)}/{len(order)} taken)")

    with open(os.path.join(out, "camera.json"), "w") as f:
        json.dump({"area": layout["id"], "image_size": [WIDTH, HEIGHT], "reference": "empty.jpg",
                   "area_roi": area_roi, "slots": slot_cal, "frames": frames}, f, indent=2)


if __name__ == "__main__":
    main()
