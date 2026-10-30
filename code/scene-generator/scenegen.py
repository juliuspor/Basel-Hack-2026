"""Shared Blender helpers for building parking-area scenes.

Coordinate convention (Blender, Z up, metres):
  X runs along the shelter length, Y runs from the open front (y=0) to the
  rear, Z is up. Bikes face +Y. The USD export rotates only the root prim to
  Y-up, so every object keeps these local coordinates inside the file.
"""

import math
import sys

import bmesh
import bpy


def script_args():
    """Arguments after `--` on the Blender command line."""
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def material(name, rgba, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgba[:3], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    alpha = rgba[3] if len(rgba) > 3 else 1.0
    bsdf.inputs["Alpha"].default_value = alpha
    mat.diffuse_color = rgba if len(rgba) > 3 else (*rgba, 1.0)
    if alpha < 1.0:
        mat.surface_render_method = "BLENDED"
    return mat


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def tube_mesh(points, radius, closed=False):
    """Mesh datablock for a round tube following `points`."""
    curve = bpy.data.curves.new("tube", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1.0)
    spline.use_cyclic_u = closed
    obj = _link(bpy.data.objects.new("tube", curve))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    bpy.data.objects.remove(obj)
    bpy.data.curves.remove(curve)
    return mesh


def box_mesh(size, center=(0, 0, 0)):
    mesh = bpy.data.meshes.new("box")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def torus_mesh(major, minor, center, axis="X", segments=32):
    """Torus around `axis` (a wheel when axis is X)."""
    mesh = bpy.data.meshes.new("torus")
    bm = bmesh.new()
    rings = 8
    grid = []
    for i in range(segments):
        u = 2 * math.pi * i / segments
        ring = []
        for j in range(rings):
            v = 2 * math.pi * j / rings
            r = major + minor * math.cos(v)
            a, b, c = r * math.cos(u), r * math.sin(u), minor * math.sin(v)
            co = {"X": (c, a, b), "Y": (a, c, b), "Z": (a, b, c)}[axis]
            ring.append(bm.verts.new((co[0] + center[0], co[1] + center[1], co[2] + center[2])))
        grid.append(ring)
    for i in range(segments):
        for j in range(rings):
            bm.faces.new((grid[i][j], grid[(i + 1) % segments][j],
                          grid[(i + 1) % segments][(j + 1) % rings], grid[i][(j + 1) % rings]))
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def merge_object(name, meshes, mat, parent=None):
    """Join mesh datablocks into one object with a single material."""
    bm = bmesh.new()
    for mesh in meshes:
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    data = bpy.data.meshes.new(name)
    bm.to_mesh(data)
    bm.free()
    for poly in data.polygons:
        poly.use_smooth = True
    data.materials.append(mat)
    obj = _link(bpy.data.objects.new(name, data))
    obj.parent = parent
    return obj


def surface_object(name, rows, mat, parent=None):
    """Quad surface from a grid of points (list of rows of equal length)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    grid = [[bm.verts.new(co) for co in row] for row in rows]
    for r in range(len(grid) - 1):
        for c in range(len(grid[r]) - 1):
            bm.faces.new((grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]))
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = _link(bpy.data.objects.new(name, mesh))
    obj.parent = parent
    return obj


def polygon_object(name, points, mat, parent=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, [], [list(range(len(points)))])
    mesh.materials.append(mat)
    obj = _link(bpy.data.objects.new(name, mesh))
    obj.parent = parent
    return obj


def empty(name, location, parent=None, **props):
    obj = _link(bpy.data.objects.new(name, None))
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.3
    obj.location = location
    obj.parent = parent
    for key, value in props.items():
        obj[key] = value
    return obj


def export_usdz(path):
    bpy.ops.wm.usd_export(
        filepath=path,
        convert_orientation=True,
        export_global_forward_selection="NEGATIVE_Z",
        export_global_up_selection="Y",
        export_materials=True,
        generate_preview_surface=True,
        export_lights=False,
        export_cameras=False,
        export_custom_properties=True,
    )


def build_bike(name="bike", color=(0.1, 0.1, 0.12), parent=None):
    """Low-poly bike, origin on the ground between the wheels, facing +Y."""
    frame_mat = material(f"bike_frame_{name}", color, roughness=0.4, metallic=0.3)
    rubber = material("bike_rubber", (0.02, 0.02, 0.02), roughness=0.9)
    r, hub_y = 0.34, 0.53
    rear, front = (0, -hub_y, r), (0, hub_y, r)
    bb, seat, head_top, head_low = (0, -0.08, 0.3), (0, -0.2, 0.86), (0, 0.36, 0.84), (0, 0.4, 0.66)
    frame = [
        tube_mesh([rear, bb, seat, rear], 0.018),
        tube_mesh([seat, head_top], 0.02),
        tube_mesh([bb, head_low, head_top], 0.022),
        tube_mesh([head_low, front], 0.015),
        tube_mesh([head_top, (0, 0.34, 1.0)], 0.015),
        tube_mesh([(-0.3, 0.32, 1.0), (0.3, 0.32, 1.0)], 0.014),
        tube_mesh([seat, (0, -0.23, 0.94)], 0.014),
        box_mesh((0.14, 0.26, 0.05), center=(0, -0.24, 0.96)),
    ]
    obj = merge_object(name, frame, frame_mat, parent)
    wheels = [torus_mesh(r - 0.02, 0.02, rear), torus_mesh(r - 0.02, 0.02, front),
              tube_mesh([(0, -hub_y, 0.1), (0, -hub_y, r * 2 - 0.1)], 0.004),
              tube_mesh([(0, hub_y, 0.1), (0, hub_y, r * 2 - 0.1)], 0.004),
              tube_mesh([(0, -hub_y - r + 0.1, r), (0, -hub_y + r - 0.1, r)], 0.004),
              tube_mesh([(0, hub_y - r + 0.1, r), (0, hub_y + r - 0.1, r)], 0.004)]
    merge_object(f"{name}_wheels", wheels, rubber, obj)
    return obj
