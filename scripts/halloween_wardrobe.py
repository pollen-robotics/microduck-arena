"""The Halloween wardrobe: the ducks' costumes and the venues' props, built in Blender.

    blender -b -P scripts/halloween_wardrobe.py                    # writes app/public/robot/halloween.glb
    blender -b -P scripts/halloween_wardrobe.py -- --preview DIR   # and renders each costume on a duck

A costume is modelled on the walking duck standing in the STAND keyframe, in the
MJCF frame (z up, metres, the beak towards +x), then each piece is carried into
the frame of the body it rides — the head (`jaw_soft`) or the trunk
(`trunk_base`) — so the viewer only has to hang it there. The file is exported z
up as modelled (export_yup off): the rig's bodies are MJCF groups.
"""

import json
import math
import random
import struct
import sys
from itertools import pairwise
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent.parent
ROBOT = ROOT / "app" / "public" / "robot"
OUT = ROBOT / "halloween.glb"

# rig.js JOINT_NAMES and STAND.
JOINT_NAMES = [
    "left_hip_yaw",
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee",
    "left_ankle",
    "neck_pitch",
    "head_pitch",
    "head_yaw",
    "head_roll",
    "right_hip_yaw",
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee",
    "right_ankle",
]
STAND = [
    0,
    -0.08726646259971647,
    -0.457924,
    -0.00494,
    0.452984,
    0.3490658503988659,
    0.3490658503988659,
    0,
    0,
    0,
    0.08726646259971647,
    0.457924,
    0.00494,
    -0.452984,
]
HEAD, TRUNK = "jaw_soft", "trunk_base"
# The lower beak opens on a pivot (rig.js jawPivot): nothing is fitted to it.
JAW = {"jaw.stl", "jaw_soft.stl"}


def read_glb(path):
    """microduck.glb's meshes by STL filename, as (vertices, triangles)."""
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20 : 20 + length])
    blob = data[20 + length + 8 :]

    def accessor(index):
        a = doc["accessors"][index]
        view = doc["bufferViews"][a["bufferView"]]
        width = {"VEC3": 3, "SCALAR": 1}[a["type"]]
        kind = {5126: "f", 5123: "H", 5125: "I"}[a["componentType"]]
        values = struct.unpack_from(
            f"<{a['count'] * width}{kind}", blob, view.get("byteOffset", 0) + a.get("byteOffset", 0)
        )
        return (
            [values[i : i + width] for i in range(0, len(values), width)] if width > 1 else values
        )

    meshes = {}
    for node in doc["nodes"]:
        primitive = doc["meshes"][node["mesh"]]["primitives"][0]
        indices = accessor(primitive["indices"])
        meshes[node["extras"]["meshFile"]] = (
            accessor(primitive["attributes"]["POSITION"]),
            [indices[i : i + 3] for i in range(0, len(indices), 3)],
        )
    return meshes


def stand_frames(kinematics):
    """Each body's world matrix with the duck standing in the STAND keyframe."""
    angles = dict(zip(JOINT_NAMES, STAND))
    world = {}
    for body in kinematics["bodies"]:
        local = Matrix.Translation(body["pos"]) @ Quaternion(body["quat"]).to_matrix().to_4x4()
        joint = body.get("joint")
        if joint:
            local = local @ Matrix.Rotation(angles[joint["name"]], 4, Vector(joint["axis"]))
        world[body["name"]] = (
            world[body["parent"]] if body["parent"] else Matrix.Identity(4)
        ) @ local
    return world


def geom_matrix(frames, body, geom):
    return (
        frames[body["name"]]
        @ Matrix.Translation(geom["pos"])
        @ Quaternion(geom.get("quat", (1, 0, 0, 0))).to_matrix().to_4x4()
    )


class Duck:
    """The standing duck the costumes are fitted to: its head and trunk, ray-castable."""

    def __init__(self, kinematics, meshes, frames):
        self.parts = {}
        for body in kinematics["bodies"]:
            for geom in body.get("geoms", []):
                if geom.get("mesh") in meshes and geom["mesh"] not in JAW:
                    points, triangles = meshes[geom["mesh"]]
                    matrix = geom_matrix(frames, body, geom)
                    self.parts.setdefault(body["name"], []).append(
                        (geom["mesh"], [matrix @ Vector(p) for p in points], triangles)
                    )
        self.head = self.surface(HEAD)
        self.trunk = self.surface(TRUNK)

    def surface(self, body):
        vertices, polygons = [], []
        for _, points, triangles in self.parts[body]:
            base = len(vertices)
            vertices += points
            polygons += [[base + i for i in t] for t in triangles]
        return BVHTree.FromPolygons(vertices, polygons)

    def skin(self, body, mesh, offset):
        """A copy of one shell pushed out along its normals: paint that sits on it."""
        _, points, triangles = next(part for part in self.parts[body] if part[0] == mesh)
        bm = bmesh.new()
        verts = [bm.verts.new(p) for p in points]
        for t in triangles:
            try:
                bm.faces.new([verts[i] for i in t])
            except ValueError:
                pass
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * offset
        return bm


# ── Materials ────────────────────────────────────────────────────────────


def material(name, colour, roughness=0.6, metallic=0.0, emission=None, strength=1.0, sheet=False):
    """A glTF material. Colours are LINEAR, like liveries.js. A sheet shows both faces."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*colour, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    m.use_backface_culling = not sheet
    return m


def glass(name, tint):
    """Clear glass: a pale tint, mostly see-through, drawn blended."""
    m = material(name, tint, 0.05)
    m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.3
    m.surface_render_method = "BLENDED"
    return m


def paints():
    return {
        "linen": material("linen", (0.42, 0.34, 0.21), 0.95),
        "cape": material("cape", (0.008, 0.008, 0.012), 0.35, sheet=True),
        "lining": material("lining", (0.45, 0.004, 0.012), 0.3, sheet=True),
        "hat": material("witch hat", (0.03, 0.012, 0.05), 0.85),
        "band": material("hat band", (1.0, 0.144, 0.008), 0.5),
        "gold": material("gold", (0.85, 0.55, 0.12), 0.3, 0.9),
        "pumpkin": material("pumpkin", (1.0, 0.2, 0.008), 0.55),
        "glow": material("glow", (1.0, 0.45, 0.02), 0.5, emission=(1.0, 0.42, 0.03), strength=2.5),
        "stem": material("stem", (0.09, 0.07, 0.015), 0.8),
        "leaf": material("leaf", (0.04, 0.2, 0.02), 0.6, sheet=True),
        "hair": material("hair", (0.02, 0.02, 0.026), 0.8),
        "green skin": material("green skin", (0.1, 0.28, 0.07), 0.6),
        "steel": material("steel", (0.45, 0.45, 0.47), 0.35, 0.85),
        "scar": material("scar", (0.08, 0.01, 0.02), 0.7),
        "white hair": material("white hair", (0.8, 0.8, 0.82), 0.8),
        "leather": material("leather", (0.08, 0.035, 0.012), 0.7),
        "brass": material("brass", (0.8, 0.45, 0.1), 0.3, 0.9),
        "goggle glass": material("goggle glass", (0.02, 0.08, 0.05), 0.05),
        "coat": material("lab coat", (0.85, 0.85, 0.86), 0.7, sheet=True),
        "bow": material("bow tie", (0.6, 0.01, 0.02), 0.5),
        "pen blue": material("pen blue", (0.02, 0.08, 0.5), 0.4),
        "jacket": material("monster jacket", (0.028, 0.032, 0.026), 0.9, sheet=True),
        "patch": material("monster patch", (0.12, 0.09, 0.05), 0.95),
        "spark": material("spark", (0.4, 0.9, 1.0), 0.5, emission=(0.4, 0.9, 1.0), strength=4.0),
        "bone": material("bone", (0.72, 0.65, 0.5), 0.7),
        "fang": material("fang", (0.9, 0.88, 0.8), 0.25),
        "glass": glass("glass", (0.75, 0.85, 0.9)),
        "potion green": material(
            "potion green", (0.2, 1.0, 0.1), 0.3, emission=(0.2, 1.0, 0.08), strength=1.6
        ),
        "potion purple": material(
            "potion purple", (0.45, 0.1, 0.9), 0.3, emission=(0.45, 0.08, 0.9), strength=1.6
        ),
        "potion orange": material(
            "potion orange", (1.0, 0.3, 0.02), 0.3, emission=(1.0, 0.3, 0.02), strength=1.6
        ),
        "cork": material("cork", (0.32, 0.18, 0.08), 0.9),
        "paper": material("paper", (0.8, 0.74, 0.58), 0.9),
        "letters": material("letters", (0.06, 0.02, 0.13), 0.6),
        "letters shadow": material("letters shadow", (1.0, 0.144, 0.008), 0.5),
        "cord": material("cord", (0.01, 0.01, 0.012), 0.7),
        "stone": material("stone", (0.16, 0.16, 0.18), 0.9),
        "engraving": material("engraving", (0.02, 0.02, 0.025), 0.9),
        "earth": material("earth", (0.045, 0.025, 0.012), 1.0),
        "wax": material("wax", (0.75, 0.68, 0.5), 0.5),
        "flame": material("flame", (1.0, 0.6, 0.1), 0.5, emission=(1.0, 0.55, 0.08), strength=4.0),
        "iron": material("iron", (0.02, 0.02, 0.022), 0.45, 0.6),
        "brew": material("brew", (0.15, 0.9, 0.05), 0.3, emission=(0.2, 1.0, 0.05), strength=1.5),
        "sheet": material(
            "ghost sheet",
            (0.85, 0.87, 0.92),
            0.7,
            emission=(0.55, 0.6, 0.75),
            strength=0.35,
            sheet=True,
        ),
        "ink": material("ink", (0.005, 0.005, 0.008), 0.6),
        "bat": material("bat", (0.015, 0.01, 0.012), 0.8),
        "bat wing": material("bat wing", (0.03, 0.015, 0.02), 0.85, sheet=True),
        "bat eye": material(
            "bat eye", (1.0, 0.5, 0.02), 0.5, emission=(1.0, 0.45, 0.02), strength=3.0
        ),
        "web": material("web", (0.75, 0.75, 0.78), 0.8),
    }


# ── Geometry ────────────────────────────────────────────────────────────


def mesh_object(name, bm, mat, smooth=True, sharp=35):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth:
        mesh.shade_smooth()
        mesh.set_sharp_from_angle(angle=math.radians(sharp))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def lathe(profile, segments=32, lobes=0, depth=0.0, closed=False):
    """Turn a (radius, z) profile about z. `lobes` ribs dent the radius like a pumpkin's;
    a radius of 0 is a pole; a closed profile is a loop (a ring's cross-section)."""
    bm = bmesh.new()

    def dent(a):
        return 1 - depth * (1 - abs(math.cos(lobes * a / 2)) ** 0.5) if lobes else 1

    rings = []
    for r, z in profile:
        if r == 0:
            rings.append([bm.verts.new((0, 0, z))] * segments)
        else:
            rings.append(
                [
                    bm.verts.new((r * dent(a) * math.cos(a), r * dent(a) * math.sin(a), z))
                    for a in (2 * math.pi * i / segments for i in range(segments))
                ]
            )
    pairs = list(pairwise(rings)) + ([(rings[-1], rings[0])] if closed else [])
    for low, high in pairs:
        for i in range(segments):
            j = (i + 1) % segments
            quad = [low[i], low[j], high[j], high[i]]
            unique = list(dict.fromkeys(quad))
            if len(unique) >= 3:
                bm.faces.new(unique)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def sweep(points, radius, segments=8, taper=None):
    """A tube along `points`; `taper(t)` scales the radius along it, 0 closes the tip."""
    bm = bmesh.new()
    rings = []
    count = len(points)
    for k, p in enumerate(points):
        p = Vector(p)
        ahead = Vector(points[min(k + 1, count - 1)]) - Vector(points[max(k - 1, 0)])
        tangent = ahead.normalized()
        side = tangent.cross(
            Vector((0, 0, 1)) if abs(tangent.z) < 0.9 else Vector((1, 0, 0))
        ).normalized()
        up = side.cross(tangent)
        r = radius * (taper(k / (count - 1)) if taper else 1)
        if r <= 1e-6:
            rings.append([bm.verts.new(p)] * segments)
            continue
        rings.append(
            [
                bm.verts.new(p + r * (math.cos(a) * side + math.sin(a) * up))
                for a in (2 * math.pi * i / segments for i in range(segments))
            ]
        )
    for low, high in pairwise(rings):
        for i in range(segments):
            j = (i + 1) % segments
            unique = list(dict.fromkeys([low[i], low[j], high[j], high[i]]))
            if len(unique) >= 3:
                bm.faces.new(unique)
    for end in (rings[0], rings[-1]):
        if len(set(end)) == segments:
            bm.faces.new(end)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def strip(points, across, outward, width, thickness, closed=False):
    """A flat band: a box section of `width` along `across` and `thickness` along `outward`."""
    bm = bmesh.new()
    sections = []
    for p, a, o in zip(points, across, outward):
        a, o = a * width / 2, o * thickness / 2
        sections.append(
            [
                bm.verts.new(p - a - o),
                bm.verts.new(p + a - o),
                bm.verts.new(p + a + o),
                bm.verts.new(p - a + o),
            ]
        )
    pairs = list(pairwise(sections)) + ([(sections[-1], sections[0])] if closed else [])
    for s, t in pairs:
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new([s[i], s[j], t[j], t[i]])
    if not closed:
        bm.faces.new(sections[0])
        bm.faces.new(list(reversed(sections[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def box(centre, size, matrix=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.transform(
        bm, matrix=(matrix or Matrix.Identity(4)) @ Matrix.Translation(centre), verts=bm.verts
    )
    return bm


def merge(target, piece):
    """Add one bmesh's geometry to another, freeing it."""
    scratch = bpy.data.meshes.new("scratch")
    piece.to_mesh(scratch)
    piece.free()
    target.from_mesh(scratch)
    bpy.data.meshes.remove(scratch)


def place(bm, matrix):
    bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    return bm


def facing(direction, origin):
    """A matrix carrying +z onto `direction` at `origin`."""
    return (
        Matrix.Translation(origin)
        @ Vector((0, 0, 1)).rotation_difference(direction.normalized()).to_matrix().to_4x4()
    )


def hug(bvh, centre, u, v, angles, offset):
    """Points on a body's surface, a plane through `centre` spanned by u, v cut at `angles`:
    each ray comes in from outside, so the band sits on the outermost shell."""
    u, v = u.normalized(), v.normalized()
    points, outward = [], []
    for a in angles:
        d = math.cos(a) * u + math.sin(a) * v
        hit = bvh.ray_cast(centre + d * 0.3, -d, 0.3)
        reach = (hit[0] - centre).length if hit[0] else 0.02
        points.append(centre + d * (reach + offset))
        outward.append(d)
    return points, outward


def band(
    bvh, centre, normal, start, stop, offset, width, thickness, mat, name, steps=48, closed=False
):
    """A band hugging a body in the plane through `centre` normal to `normal`, from angle
    `start` to `stop` (degrees, from the plane's own +u)."""
    normal = normal.normalized()
    u = (Vector((0, 0, 1)) if abs(normal.z) < 0.9 else Vector((1, 0, 0))).cross(normal).normalized()
    v = normal.cross(u)
    count = steps if closed else steps + 1
    angles = [math.radians(start + (stop - start) * k / steps) for k in range(count)]
    points, outward = hug(bvh, centre, u, v, angles, offset)
    return mesh_object(
        name, strip(points, [normal] * len(points), outward, width, thickness, closed), mat
    )


def sheet(rows, cols, at, mat, name):
    """A cloth: `at(s, t)` gives its point for s and t from 0 to 1, rows down and columns across."""
    bm = bmesh.new()
    grid = [
        [bm.verts.new(at(i / (rows - 1), j / (cols - 1))) for j in range(cols)] for i in range(rows)
    ]
    for i in range(rows - 1):
        for j in range(cols - 1):
            bm.faces.new([grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, mat)


def round_trunk(theta, flare=0.0):
    """A point round the trunk at angle `theta` from the beak's side: a squircle, so the shells'
    corners stay inside it."""
    c, s_ = math.cos(theta), math.sin(theta)
    return Vector(
        (
            -0.006 + (0.05 + flare) * math.copysign(abs(c) ** 0.5, c),
            (0.044 + flare) * math.copysign(abs(s_) ** 0.5, s_),
            0,
        )
    )


def coat(opening, hem, mat, name, rag=0.0, flare=0.006):
    """A coat round the trunk, open by `opening` degrees over the chest, its shoulders sloping in to
    the neck and its hem at `hem`, torn into points `rag` deep."""

    def at(s, t):
        theta = math.radians(opening / 2 + (360 - opening) * t)
        # The top fifth is the shoulders, drawn in towards the neck.
        if s < 0.2:
            u = s / 0.2
            point = round_trunk(theta) * (0.6 + 0.4 * u)
            point.x += -0.006 * (1 - (0.6 + 0.4 * u))
            point.z = 0.172 - 0.008 * u
            return point
        u = (s - 0.2) / 0.8
        point = round_trunk(theta, flare * u)
        point.z = 0.164 - (0.164 - hem) * u
        if s == 1 and rag:
            point.z += rag * abs(math.sin(theta * 9))
        return point

    return sheet(10, 64, at, mat, name)


# ── The costumes ─────────────────────────────────────────────────────────
# Each returns {body: [objects]}, modelled on the standing duck.


def mummy(duck, p):
    """Cream: old linen wound round the head above the eye and round the trunk, two ends loose."""
    rng = random.Random(3)
    head, trunk = duck.head, duck.trunk
    on_head = [
        band(
            head,
            Vector((0.012, 0, 0.262)),
            Vector((-0.13, 0, 1)),
            0,
            360,
            0.0015,
            0.011,
            0.002,
            p["linen"],
            "mummy brow",
            closed=True,
        ),
        band(
            head,
            Vector((0.03, 0, 0.232)),
            Vector((1, 0, 0.25)),
            -15,
            195,
            0.0025,
            0.012,
            0.002,
            p["linen"],
            "mummy crown",
        ),
        band(
            head,
            Vector((-0.012, 0, 0.232)),
            Vector((0.85, 0.35, -0.2)),
            -10,
            190,
            0.0035,
            0.011,
            0.002,
            p["linen"],
            "mummy cross",
        ),
        band(
            head,
            Vector((0.0, 0, 0.236)),
            Vector((0.12, 0, 1)),
            70,
            290,
            0.003,
            0.01,
            0.002,
            p["linen"],
            "mummy nape",
        ),
        band(
            head,
            Vector((-0.02, 0, 0.232)),
            Vector((0.9, -0.4, 0.1)),
            -10,
            190,
            0.003,
            0.011,
            0.002,
            p["linen"],
            "mummy back cross",
        ),
        band(
            head,
            Vector((0.012, 0, 0.247)),
            Vector((0.1, 0.25, 1)),
            60,
            300,
            0.0025,
            0.01,
            0.002,
            p["linen"],
            "mummy temple",
        ),
    ]
    on_trunk = [
        band(
            trunk,
            Vector((-0.006, 0, z)),
            Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.1, 0.1), 1)),
            0,
            360,
            0.0015,
            0.011,
            0.002,
            p["linen"],
            f"mummy waist {k}",
            closed=True,
        )
        for k, z in enumerate((0.128, 0.141, 0.155))
    ]

    def tail(start, drop, sway, name):
        # A loose end hanging off the back, swaying a little sideways.
        points = [
            Vector(start)
            + Vector((-0.004 * k - 0.0015 * math.sin(k * 0.9), sway * 0.003 * k, -drop * k / 8))
            for k in range(9)
        ]
        n = len(points)
        return mesh_object(
            name,
            strip(
                points,
                [Vector((0.2, 1, 0)).normalized()] * n,
                [Vector((-1, 0.2, 0)).normalized()] * n,
                0.01,
                0.0015,
            ),
            p["linen"],
        )

    on_head.append(tail((-0.05, 0.004, 0.255), 0.05, 1.0, "mummy loose head"))
    on_trunk.append(tail((-0.048, 0.02, 0.127), 0.045, -1.0, "mummy loose waist"))
    return {HEAD: on_head, TRUNK: on_trunk}


def vampire(duck, p):
    """Graphite: a black cape lined blood red, its collar stood up behind the head."""
    cx = -0.006

    def cape(s, t, inset):
        # s: 0 at the shoulders, 1 at the hem; t: across, from the left front round the back.
        theta = math.radians(65 + 230 * t)
        rx = 0.047 + 0.028 * s**1.2 - inset
        ry = 0.041 + 0.036 * s**1.1 - inset
        hem = 0.004 * math.sin(theta * 7) * s**3
        rx, ry = rx + hem, ry + hem
        z = 0.168 - 0.085 * s + 0.004 * math.cos(theta * 7) * s**3
        return (cx + rx * math.cos(theta), ry * math.sin(theta), z)

    def collar(s, t, inset):
        theta = math.radians(112 + 136 * t)
        flare = 0.048 + 0.03 * s**1.4 - inset
        z = 0.164 + 0.058 * s * (0.75 + 0.25 * math.cos((t - 0.5) * math.pi))
        return (cx + flare * 1.05 * math.cos(theta), flare * math.sin(theta), z)

    return {
        TRUNK: [
            sheet(10, 40, lambda s, t: cape(s, t, 0), p["cape"], "vampire cape"),
            sheet(10, 40, lambda s, t: cape(s, t, 0.0012), p["lining"], "vampire lining"),
            sheet(6, 30, lambda s, t: collar(s, t, 0), p["cape"], "vampire collar"),
            sheet(6, 30, lambda s, t: collar(s, t, 0.0012), p["lining"], "vampire collar lining"),
        ]
    }


def count(duck, p):
    """Sock Heist's giant: Count Dracula — two fangs over its lower beak, a cape lined blood red down
    to the floor it sits on, a tall collar behind its head, piped red so it reads from behind."""
    cx = -0.006

    def cape(s, t, inset):
        # Wider and longer than a racer's vampire cape: it drapes over the folded legs to the nest.
        theta = math.radians(55 + 250 * t)
        hem = 0.005 * math.sin(theta * 7) * s**3
        rx = 0.05 + 0.045 * s**1.2 - inset + hem
        ry = 0.044 + 0.05 * s - inset + hem
        z = 0.172 - 0.102 * s + 0.004 * math.cos(theta * 7) * s**3
        return (cx + rx * math.cos(theta), ry * math.sin(theta), z)

    def collar(s, t, inset):
        # Two points either side of the head, clear of it as it turns round; low between them, under
        # the fangs, so a camera behind the giant still sees its whole head over it.
        theta = math.radians(125 + 110 * t)
        flare = 0.05 + 0.05 * s**1.4 - inset
        z = 0.164 + s * (0.032 + 0.05 * abs(2 * t - 1) ** 2.5)
        return Vector((cx + flare * 1.05 * math.cos(theta), flare * math.sin(theta), z))

    piping = sweep([collar(1, k / 40, 0) for k in range(41)], 0.0018, 8)
    # Hung from the upper beak's edge in front of the lower beak (the jaw, 6.87 cm forward), so they
    # show over it as a vampire's do over its lip.
    fangs = bmesh.new()
    for side in (1, -1):
        hit = duck.head.ray_cast(Vector((0.068, 0.017 * side, 0.18)), Vector((0, 0, 1)), 0.1)
        root = Vector((0.0705, 0.017 * side, hit[0].z))
        merge(
            fangs,
            place(
                lathe([(0.0032, 0.001), (0.0026, -0.008), (0, -0.018)], 12),
                Matrix.Translation(root),
            ),
        )
    return {
        HEAD: [mesh_object("count fangs", fangs, p["fang"])],
        TRUNK: [
            sheet(12, 48, lambda s, t: cape(s, t, 0), p["cape"], "count cape"),
            sheet(12, 48, lambda s, t: cape(s, t, 0.0012), p["lining"], "count lining"),
            sheet(8, 40, lambda s, t: collar(s, t, 0), p["cape"], "count collar"),
            sheet(8, 40, lambda s, t: collar(s, t, 0.0012), p["lining"], "count collar lining"),
            mesh_object("count collar piping", piping, p["lining"]),
        ],
    }


def witch(duck, p):
    """Lavender: a crooked pointed hat, orange band, gold buckle."""
    tilt = (
        Matrix.Translation((0.008, 0.0, 0.262))
        @ Matrix.Rotation(math.radians(-12), 4, "Y")
        @ Matrix.Rotation(math.radians(6), 4, "X")
    )
    brim = lathe(
        [
            (0, 0.006),
            (0.04, 0.0055),
            (0.066, 0.004),
            (0.078, 0.011),
            (0.079, 0.008),
            (0.066, 0.001),
            (0.04, 0.0025),
            (0, 0.003),
        ],
        40,
    )
    # The cone climbs and its tip flops back: rings stacked along a bent spine.
    bm = bmesh.new()
    rings = []
    n = 16
    for k in range(n):
        t = k / (n - 1)
        r = 0.036 * (1 - t) ** 0.95
        spine = Vector((-0.05 * t**3, 0.006 * math.sin(t * 3), 0.004 + 0.12 * t - 0.025 * t**4))
        if r < 1e-4:
            rings.append([bm.verts.new(spine)] * 24)
        else:
            rings.append(
                [
                    bm.verts.new(spine + Vector((r * math.cos(a), r * math.sin(a), 0)))
                    for a in (2 * math.pi * i / 24 for i in range(24))
                ]
            )
    for low, high in pairwise(rings):
        for i in range(24):
            j = (i + 1) % 24
            bm.faces.new(list(dict.fromkeys([low[i], low[j], high[j], high[i]])))
    bm.faces.new(rings[0])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cone = place(bm, tilt)
    hat_band = place(
        lathe(
            [(0.0352, 0.006), (0.0334, 0.017), (0.0318, 0.017), (0.0336, 0.006)], 32, closed=True
        ),
        tilt,
    )
    buckle = bmesh.new()
    for centre, size in (
        ((0, -0.0055, 0), (0.002, 0.0015, 0.011)),
        ((0, 0.0055, 0), (0.002, 0.0015, 0.011)),
        ((0, 0, 0.0048), (0.002, 0.011, 0.0015)),
        ((0, 0, -0.0048), (0.002, 0.011, 0.0015)),
    ):
        merge(buckle, box(centre, size))
    place(
        buckle,
        tilt @ Matrix.Translation((0.0345, 0, 0.0115)) @ Matrix.Rotation(math.radians(-3), 4, "Y"),
    )
    return {
        HEAD: [
            mesh_object("witch brim", place(brim, tilt), p["hat"], sharp=60),
            mesh_object("witch cone", cone, p["hat"], sharp=70),
            mesh_object("witch band", hat_band, p["band"]),
            mesh_object("witch buckle", buckle, p["gold"], smooth=False),
        ]
    }


def jack(p, radius=0.044, height=0.058, name="pumpkin"):
    """A jack-o'-lantern standing on the origin, its carved face towards +x, glowing."""
    profile = []
    for k in range(13):
        phi = math.pi * k / 12
        r = radius * math.sin(phi)
        z = height / 2 * (1 - math.cos(phi))
        # A dimple round the stem and under the base.
        z += -0.18 * height * math.exp(-(((phi - math.pi) / 0.35) ** 2)) + 0.1 * height * math.exp(
            -((phi / 0.3) ** 2)
        )
        profile.append((r, z))
    profile[0] = (0, 0.06 * height)
    profile[-1] = (0, height * 0.86)
    body = mesh_object(name, lathe(profile, 48, lobes=10, depth=0.14), p["pumpkin"], sharp=50)
    shell = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())

    def carve(outline, label):
        bm = bmesh.new()
        verts = []
        for y, z in outline:
            hit = shell.ray_cast(
                Vector((radius * 2, y * radius, z * height)), Vector((-1, 0, 0)), radius * 3
            )
            verts.append(bm.verts.new(hit[0] + hit[1] * 0.0006 * radius / 0.044))
        bm.faces.new(verts)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return mesh_object(f"{name} {label}", bm, p["glow"], smooth=False)

    eye = [(0.12, 0.52), (0.42, 0.52), (0.27, 0.74)]
    face = [
        carve(eye, "left eye"),
        carve([(-y, z) for y, z in reversed(eye)], "right eye"),
        carve([(-0.07, 0.42), (0.07, 0.42), (0, 0.52)], "nose"),
        carve(
            [
                (-0.5, 0.33),
                (-0.32, 0.27),
                (-0.22, 0.31),
                (-0.12, 0.22),
                (0.0, 0.25),
                (0.12, 0.22),
                (0.22, 0.31),
                (0.32, 0.27),
                (0.5, 0.33),
                (0.3, 0.18),
                (0.0, 0.13),
                (-0.3, 0.18),
            ],
            "mouth",
        ),
    ]
    stem_path = [
        Vector((0.0005 * k * k, 0.0003 * k, height * 0.8 + 0.0035 * k * radius / 0.044))
        for k in range(8)
    ]
    stem = mesh_object(
        f"{name} stem",
        sweep(stem_path, 0.0055 * radius / 0.044, 10, lambda t: 1 - 0.35 * t),
        p["stem"],
    )
    leaf_bm = bmesh.new()
    leaf_points = [
        (0, 0),
        (0.008, 0.006),
        (0.018, 0.007),
        (0.026, 0.003),
        (0.03, -0.001),
        (0.024, -0.006),
        (0.012, -0.007),
        (0.004, -0.004),
    ]
    leaf_bm.faces.new(
        [leaf_bm.verts.new((x * radius / 0.044, y * radius / 0.044, 0.0)) for x, y in leaf_points]
    )
    leaf = mesh_object(
        f"{name} leaf",
        place(
            leaf_bm,
            Matrix.Translation((0.002, -0.002, height * 0.82))
            @ Matrix.Rotation(math.radians(-150), 4, "Z")
            @ Matrix.Rotation(math.radians(-25), 4, "X"),
        ),
        p["leaf"],
        smooth=False,
    )
    return [body, *face, stem, leaf]


def pumpkin_hat(duck, p):
    """Sky: a jack-o'-lantern worn as a hat."""
    parts = jack(p, name="pumpkin hat")
    for obj in parts:
        obj.data.transform(
            Matrix.Translation((0.014, 0, 0.262)) @ Matrix.Rotation(math.radians(-8), 4, "Y")
        )
    return {HEAD: parts}


def monster(duck, p):
    """Peter: Frankenstein's monster — green skin, a black flat top with a jagged fringe, a stitched scar, neck bolts."""
    head = duck.head
    skin = mesh_object(
        "monster skin", duck.skin(HEAD, "top_head_shell.stl", 0.0005), p["green skin"], sharp=60
    )
    top = 0.287
    outline = []
    for k in range(128):
        a = 2 * math.pi * k / 128
        # A squared-off ellipse a little wider than the head.
        c, s_ = math.cos(a), math.sin(a)
        x = 0.012 + 0.067 * math.copysign(abs(c) ** 0.6, c)
        y = 0.052 * math.copysign(abs(s_) ** 0.6, s_)
        # The fringe: teeth hanging over the brow at the front, the hairline higher there.
        front = max(0.0, c) ** 4
        tooth = 0.009 * abs((y / 0.012) % 2 - 1) * front
        outline.append((x, y, 0.251 + 0.016 * front - tooth))
    bm = bmesh.new()
    low = [bm.verts.new(v) for v in outline]
    high = [bm.verts.new((x, y, top)) for x, y, _ in outline]
    for i in range(128):
        j = (i + 1) % 128
        bm.faces.new([low[i], low[j], high[j], high[i]])
    bm.faces.new(high)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    hair = mesh_object("monster hair", bm, p["hair"], sharp=30)

    # A scar across each temple, stitched, the right one lower and tilted.
    scars, stitches = bmesh.new(), bmesh.new()
    for side, z, tilt in ((1, 0.248, 0.0), (-1, 0.24, 0.0012)):
        points, out = [], []
        for k in range(9):
            x = -0.018 + 0.006 * k
            hit = head.ray_cast(
                Vector((x, 0.2 * side, z + 0.002 * math.sin(k) + tilt * k)),
                Vector((0, -side, 0)),
                0.3,
            )
            points.append(hit[0] + hit[1] * 0.0008)
            out.append(hit[1])
        merge(scars, strip(points, [Vector((0, 0, 1))] * 9, out, 0.0018, 0.001))
        for k in range(1, 9, 2):
            merge(
                stitches,
                box((0, 0, 0), (0.0012, 0.0012, 0.009), facing(Vector((0, 0, 1)), points[k])),
            )
    scar = mesh_object("monster scars", scars, p["scar"])
    stitch = mesh_object("monster stitches", stitches, p["scar"], smooth=False)

    bolts = []
    for side in (1, -1):
        hit = head.ray_cast(Vector((-0.008, 0.2 * side, 0.228)), Vector((0, -side, 0)), 0.3)
        axis = Vector((0, side, 0))
        shaft = place(
            lathe([(0, 0), (0.0045, 0), (0.0045, 0.02), (0, 0.02)], 16),
            facing(axis, hit[0] - axis * 0.004),
        )
        nut = place(
            lathe([(0, 0.014), (0.0085, 0.014), (0.0085, 0.023), (0, 0.023)], 6),
            facing(axis, hit[0] - axis * 0.004),
        )
        bolts += [
            mesh_object(f"monster bolt {side}", shaft, p["steel"], sharp=40),
            mesh_object(f"monster nut {side}", nut, p["steel"], smooth=False),
        ]
        if side == 1:
            # The current still crackling off the left bolt.
            tip = hit[0] + axis * 0.02
            sparks = bmesh.new()
            for zig in ((0.006, 0.004), (-0.003, 0.007)):
                path = [
                    tip,
                    tip + Vector((zig[0], 0.004, zig[1])),
                    tip + Vector((zig[0] * 0.3, 0.007, zig[1] * 1.6)),
                    tip + Vector((zig[0] * 1.3, 0.011, zig[1] * 2.2)),
                ]
                merge(sparks, sweep(path, 0.0007, 4))
            bolts.append(mesh_object("monster spark", sparks, p["spark"], smooth=False))

    # The monster's jacket: too small, square-shouldered, its hem torn, a patch sewn on the chest.
    jacket = coat(50, 0.119, p["jacket"], "monster jacket", rag=0.007)
    at = round_trunk(math.radians(52), 0.0035)
    at.z = 0.14
    normal = Vector((at.x + 0.006, at.y, 0)).normalized()
    patch = place(box((0, 0, 0), (0.016, 0.014, 0.0015)), facing(normal, at))
    seams = bmesh.new()
    for k in range(4):
        step = (k - 1.5) * 0.0035
        merge(
            seams,
            place(
                box((0, 0, 0), (0.0007, 0.005, 0.0008)),
                facing(normal, at + normal * 0.0012)
                @ Matrix.Translation((step, 0.007, 0))
                @ Matrix.Rotation(0.5, 4, "Z"),
            ),
        )
    return {
        HEAD: [skin, hair, scar, stitch, *bolts],
        TRUNK: [
            jacket,
            mesh_object("monster patch", patch, p["patch"], smooth=False),
            mesh_object("monster patch seams", seams, p["scar"], smooth=False),
        ],
    }


def scientist(duck, p):
    """Ray: the mad scientist who built Peter — wild white hair and one bushy eyebrow, goggles up on
    the brow, a lab coat over a bow tie, a pen and a glowing test tube in its pocket."""
    head = duck.head
    rng = random.Random(7)
    tufts = bmesh.new()
    # A bald crown, a cloud of white round the back and over the ears, and a few wisps sticking out of it.
    for k in range(60):
        a = math.radians(rng.uniform(80, 280))
        z = rng.uniform(0.236, 0.268)
        d = Vector((math.cos(a), math.sin(a), 0))
        hit = head.ray_cast(Vector((0.012, 0, z)) + d * 0.3, -d, 0.3)
        if not hit[0]:
            continue
        out = (hit[1] + Vector((0, 0, rng.uniform(0.2, 0.8)))).normalized()
        if k < 48:
            puff = bmesh.new()
            bmesh.ops.create_icosphere(puff, subdivisions=2, radius=rng.uniform(0.008, 0.012))
            merge(tufts, place(puff, Matrix.Translation(hit[0] + out * 0.004)))
        else:
            length = rng.uniform(0.014, 0.024)
            bend = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.5, 1.5))) * 0.008
            path = [hit[0] + out * length * t + bend * t * t for t in (i / 5 for i in range(6))]
            merge(tufts, sweep(path, 0.006, 8, lambda t: (1 - t) ** 0.7))
    # One bushy white eyebrow arching over the eye ring (centred 0.248 up, 15 mm round), its tufts
    # bristling out of the arch.
    for k in range(11):
        phi = math.radians(30 + 12 * k)
        y, z = 0.0195 * math.cos(phi), 0.248 + 0.0195 * math.sin(phi)
        hit = head.ray_cast(Vector((0.2, y, z)), Vector((-1, 0, 0)), 0.3)
        if not hit[0]:
            continue
        out = Vector((0.35, math.cos(phi) * 1.4, math.sin(phi))).normalized()
        path = [hit[0] + Vector((0.002, 0, 0)) + out * 0.01 * t for t in (i / 3 for i in range(4))]
        merge(tufts, sweep(path, 0.0036, 6, lambda t: (1 - t) ** 0.7))
    hair = mesh_object("scientist hair", tufts, p["white hair"], sharp=80)
    strap = band(
        head,
        Vector((0.012, 0, 0.263)),
        Vector((-0.2, 0, 1)),
        0,
        360,
        0.0015,
        0.008,
        0.0018,
        p["leather"],
        "scientist strap",
        closed=True,
    )
    goggles, lenses = [], []
    for side in (1, -1):
        hit = head.ray_cast(
            Vector((0.135, 0.019 * side, 0.45)), Vector((-0.5, 0, -1)).normalized(), 0.6
        )
        axis = (hit[1] + Vector((0.9, 0, 0))).normalized()
        frame = facing(axis, hit[0] - axis * 0.002)
        lenses.append(frame @ Vector((0, 0, 0.006)))
        rim = lathe(
            [(0.0125, 0.0), (0.0125, 0.009), (0.0105, 0.009), (0.0105, 0.002)], 24, closed=True
        )
        glass = lathe([(0, 0.0065), (0.0108, 0.0065), (0.0108, 0.0055), (0, 0.0055)], 24)
        goggles += [
            mesh_object(f"scientist rim {side}", place(rim, frame), p["brass"], sharp=50),
            mesh_object(
                f"scientist glass {side}", place(glass, frame), p["goggle glass"], sharp=50
            ),
        ]
    middle = (lenses[0] + lenses[1]) / 2 + Vector((0.001, 0, 0.002))
    goggles.append(
        mesh_object(
            "scientist bridge", sweep([lenses[0], middle, lenses[1]], 0.0015, 6), p["brass"]
        )
    )

    # The lab coat, open over the bow tie, a pen and a test tube in its breast pocket.
    on_trunk = [coat(72, 0.11, p["coat"], "scientist coat", flare=0.009)]
    at = round_trunk(math.radians(58), 0.003)
    at.z = 0.142
    normal = Vector((at.x + 0.006, at.y, 0)).normalized()
    on_trunk.append(
        mesh_object(
            "scientist pocket",
            place(box((0, 0, 0), (0.017, 0.014, 0.0016)), facing(normal, at)),
            p["coat"],
            smooth=False,
        )
    )
    in_pocket = Matrix.Translation(at + normal * 0.0035)
    for points, radius, mat, name in (
        ([(-0.004, 0, 0.002), (-0.004, 0, 0.017)], 0.0013, p["pen blue"], "scientist pen blue"),
        ([(0.0, 0.001, 0.002), (0.0, 0.001, 0.015)], 0.0012, p["bow"], "scientist pen red"),
        ([(0.0045, 0, 0.0), (0.0045, 0, 0.02)], 0.0022, p["glass"], "scientist test tube"),
        ([(0.0045, 0, 0.0), (0.0045, 0, 0.011)], 0.0018, p["brew"], "scientist test tube brew"),
    ):
        on_trunk.append(mesh_object(name, place(sweep(points, radius, 10), in_pocket), mat))
    for side in (1, -1):
        bm = bmesh.new()
        tri = [
            (0.037, 0.003 * side, 0.163),
            (0.037, 0.03 * side, 0.162),
            (0.039, 0.012 * side, 0.135),
        ]
        bm.faces.new([bm.verts.new(v) for v in tri])
        on_trunk.append(mesh_object(f"scientist lapel {side}", bm, p["coat"], smooth=False))
    bow = bmesh.new()
    for side in (1, -1):
        wing = [(0.041, 0.0, 0.152), (0.043, 0.014 * side, 0.159), (0.043, 0.014 * side, 0.145)]
        bow.faces.new([bow.verts.new(v) for v in wing])
    merge(bow, box((0.043, 0, 0.152), (0.004, 0.005, 0.005)))
    on_trunk.append(mesh_object("scientist bow tie", bow, p["bow"], smooth=False))
    return {HEAD: [hair, strap, *goggles], TRUNK: on_trunk}


# Which costume each livery wears, and the commentators' and Sock Heist's giant's own.
COSTUMES = {
    "classic": mummy,
    "charcoal": vampire,
    "purple": witch,
    "blue": pumpkin_hat,
    "peter": monster,
    "ray": scientist,
    "giant": count,
}


# ── The venues' props ────────────────────────────────────────────────────
# Each stands on the origin facing +x, z up, at a size the scenes scale from.


def slab(outline, depth):
    """A flat outline in the y-z plane, extruded to `depth` along x, centred on x = 0."""
    bm = bmesh.new()
    back = [bm.verts.new((-depth / 2, y, z)) for y, z in outline]
    front = [bm.verts.new((depth / 2, y, z)) for y, z in outline]
    count = len(outline)
    for i in range(count):
        j = (i + 1) % count
        bm.faces.new([back[i], back[j], front[j], front[i]])
    bm.faces.new(back)
    bm.faces.new(list(reversed(front)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def text_mesh(text, font, size, depth):
    """Text as a mesh, standing in the y-z plane and reading towards +x; `font` None is Blender's own."""
    curve = bpy.data.curves.new("text", type="FONT")
    curve.body = text
    if font:
        curve.font = font
    curve.size = size
    curve.extrude = depth / 2
    curve.align_x = "CENTER"
    obj = bpy.data.objects.new("text", curve)
    bpy.context.scene.collection.objects.link(obj)
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(obj)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bpy.data.meshes.remove(mesh)
    # The font lies in x-y facing +z: stand it up facing +x.
    bmesh.ops.transform(
        bm,
        matrix=Matrix.Rotation(math.radians(90), 4, "Z")
        @ Matrix.Rotation(math.radians(90), 4, "X"),
        verts=bm.verts,
    )
    return bm


def tombstone(p):
    """A rounded slab with RIP cut into it, leaning a little on its mound."""
    outline = (
        [(-0.06, 0.0), (0.06, 0.0), (0.06, 0.12)]
        + [
            (0.06 * math.cos(a), 0.12 + 0.06 * math.sin(a))
            for a in (math.pi * k / 16 for k in range(1, 16))
        ]
        + [(-0.06, 0.12)]
    )
    lean = Matrix.Rotation(math.radians(-6), 4, "Y") @ Matrix.Rotation(math.radians(4), 4, "X")
    stone = mesh_object("tombstone", place(slab(outline, 0.03), lean), p["stone"], sharp=40)
    rip = mesh_object(
        "tombstone rip",
        place(text_mesh("RIP", None, 0.045, 0.003), lean @ Matrix.Translation((0.0155, 0, 0.1))),
        p["engraving"],
        smooth=False,
    )
    mound = mesh_object(
        "tombstone mound",
        place(
            lathe([(0, 0.018), (0.04, 0.014), (0.07, 0.006), (0.085, -0.002), (0, -0.002)], 20),
            Matrix.Diagonal((1.4, 1.0, 1.0, 1.0)),
        ),
        p["earth"],
    )
    return [stone, rip, mound]


def candles(p):
    """Three candles of three heights, each with a flame."""
    parts = []
    for k, (x, y, height) in enumerate(((0, 0, 0.07), (0.018, 0.016, 0.05), (-0.012, 0.02, 0.038))):
        wax = lathe(
            [
                (0, 0),
                (0.009, 0),
                (0.0092, height * 0.6),
                (0.0088, height),
                (0.006, height - 0.002),
                (0, height - 0.003),
            ],
            16,
        )
        parts.append(
            mesh_object(f"candle {k}", place(wax, Matrix.Translation((x, y, 0))), p["wax"])
        )
        flame = lathe([(0, 0), (0.003, 0.003), (0.0035, 0.007), (0.002, 0.012), (0, 0.019)], 10)
        parts.append(
            mesh_object(
                f"candle flame {k}",
                place(flame, Matrix.Translation((x, y, height + 0.002))),
                p["flame"],
            )
        )
    return parts


def cauldron(p):
    """A black pot on three legs, a green brew bubbling in it."""
    pot = lathe(
        [
            (0, 0.02),
            (0.05, 0.022),
            (0.07, 0.05),
            (0.072, 0.075),
            (0.06, 0.1),
            (0.064, 0.106),
            (0.068, 0.1),
            (0.057, 0.096),
            (0, 0.096),
        ],
        32,
    )
    parts = [mesh_object("cauldron", pot, p["iron"], sharp=50)]
    parts.append(
        mesh_object("cauldron brew", lathe([(0, 0.098), (0.057, 0.098), (0, 0.098)], 32), p["brew"])
    )
    rng = random.Random(5)
    bubbles = bmesh.new()
    for _ in range(7):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0, 0.045)
        bubble = bmesh.new()
        bmesh.ops.create_icosphere(bubble, subdivisions=1, radius=rng.uniform(0.006, 0.012))
        merge(bubbles, place(bubble, Matrix.Translation((r * math.cos(a), r * math.sin(a), 0.1))))
    parts.append(mesh_object("cauldron bubbles", bubbles, p["brew"]))
    legs = bmesh.new()
    for k in range(3):
        a = 2 * math.pi * k / 3
        merge(
            legs,
            sweep(
                [
                    (0.045 * math.cos(a), 0.045 * math.sin(a), 0.03),
                    (0.055 * math.cos(a), 0.055 * math.sin(a), 0.0),
                ],
                0.006,
                8,
            ),
        )
    parts.append(mesh_object("cauldron legs", legs, p["iron"]))
    return parts


def ghost(p):
    """A sheet ghost, its hem waving, two black eyes and an O of a mouth."""
    bm = bmesh.new()
    rings = []
    n = 32
    profile = [
        (0.0, 0.25),
        (0.03, 0.245),
        (0.05, 0.225),
        (0.06, 0.19),
        (0.062, 0.14),
        (0.068, 0.08),
        (0.08, 0.03),
        (0.09, 0.0),
    ]
    for k, (r, z) in enumerate(profile):
        if r == 0:
            rings.append([bm.verts.new((0, 0, z))] * n)
            continue
        hem = k == len(profile) - 1
        rings.append(
            [
                bm.verts.new(
                    (r * math.cos(a), r * math.sin(a), z + (0.015 * math.sin(5 * a) if hem else 0))
                )
                for a in (2 * math.pi * i / n for i in range(n))
            ]
        )
    for low, high in zip(rings[1:], rings):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new(list(dict.fromkeys([low[i], low[j], high[j], high[i]])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    sheet = mesh_object("ghost", bm, p["sheet"], sharp=60)
    face = bmesh.new()
    for y, z, w, h in (
        (0.02, 0.19, 0.009, 0.014),
        (-0.02, 0.19, 0.009, 0.014),
        (0.0, 0.155, 0.011, 0.013),
    ):
        dot = bmesh.new()
        bmesh.ops.create_uvsphere(dot, u_segments=12, v_segments=8, radius=1.0)
        merge(
            face,
            place(dot, Matrix.Translation((0.058, y, z)) @ Matrix.Diagonal((0.004, w, h, 1.0))),
        )
    return [sheet, mesh_object("ghost face", face, p["ink"])]


def bat(p):
    """A bat, its two wings hung at the shoulders so the scene can flap them (extras `wing`)."""
    body = bmesh.new()
    bmesh.ops.create_uvsphere(body, u_segments=12, v_segments=8, radius=1.0)
    place(body, Matrix.Diagonal((0.022, 0.014, 0.014, 1.0)))
    for side in (1, -1):
        merge(
            body,
            place(
                lathe([(0, 0), (0.005, 0), (0, 0.014)], 8),
                Matrix.Translation((0.012, 0.007 * side, 0.008))
                @ Matrix.Rotation(math.radians(-15 * side), 4, "X"),
            ),
        )
    parts = [mesh_object("bat", body, p["bat"], sharp=60)]
    eyes = bmesh.new()
    for side in (1, -1):
        eye = bmesh.new()
        bmesh.ops.create_icosphere(eye, subdivisions=1, radius=0.0025)
        merge(eyes, place(eye, Matrix.Translation((0.02, 0.005 * side, 0.004))))
    parts.append(mesh_object("bat eyes", eyes, p["bat eye"], smooth=False))
    # A wing: a fan of three fingers from the shoulder, the membrane scalloped between them.
    tips = [(0.03, 0.03), (0.0, 0.085), (-0.03, 0.07), (-0.035, 0.03)]
    for side, label in ((1, "left"), (-1, "right")):
        wing = bmesh.new()
        outline = [(0.008, 0.0)]
        for (x0, y0), (x1, y1) in pairwise(tips):
            outline.append((x0, y0))
            outline.append(((x0 + x1) / 2 + 0.006, (y0 + y1) / 2 - 0.012))
        outline += [tips[-1], (-0.012, 0.0)]
        wing.faces.new([wing.verts.new((x, y * side, 0)) for x, y in outline])
        obj = mesh_object(f"bat wing {label}", wing, p["bat wing"], smooth=False)
        obj["wing"] = side
        parts.append(obj)
    return parts


def cobweb(p):
    """A web in a corner: threads fanning from it, sagging rings across them, a spider waiting."""
    threads = bmesh.new()
    spokes = 7
    reach = 0.16
    for k in range(spokes):
        a = math.radians(90 * k / (spokes - 1))
        merge(
            threads, sweep([(0, 0, 0), (0, -reach * math.cos(a), -reach * math.sin(a))], 0.0007, 4)
        )
    for ring in (0.04, 0.075, 0.11, 0.145):
        points = []
        for k in range(spokes - 1):
            for t in (0, 0.5):
                a = math.radians(90 * (k + t) / (spokes - 1))
                r = ring * (0.86 if t else 1)
                points.append((0, -r * math.cos(a), -r * math.sin(a)))
        points.append((0, 0, -ring))
        merge(threads, sweep(points, 0.0006, 4))
    return [
        mesh_object("cobweb", threads, p["web"], smooth=False),
        mesh_object(
            "cobweb spider", spider_body(Vector((0, -0.08, -0.093))), p["ink"], smooth=False
        ),
    ]


def spider_body(at):
    """A spider's abdomen and head over eight bent legs, centred on `at`."""
    spider = bmesh.new()
    for lift, radius in ((0.003, 0.009), (-0.007, 0.006)):
        ball = bmesh.new()
        bmesh.ops.create_icosphere(ball, subdivisions=2, radius=radius)
        merge(spider, place(ball, Matrix.Translation(at + Vector((0, 0, lift)))))
    for side in (1, -1):
        for k in range(4):
            a = math.radians(-40 + 27 * k)
            knee = at + Vector((0.004, side * 0.014, 0.012 * math.sin(a)))
            foot = at + Vector((0.0, side * 0.022, 0.022 * math.sin(a)))
            merge(spider, sweep([at, knee, foot], 0.0012, 4))
    return spider


def spider(p):
    """A spider hanging under its origin on a thread a metre long, which the scene shortens: the
    thread its own child (extras `thread`), along +z from the origin."""
    thread = mesh_object(
        "spider thread", sweep([(0, 0, 0), (0, 0, 1)], 0.0005, 4), p["web"], smooth=False
    )
    thread["thread"] = 1
    return [
        mesh_object("spider", spider_body(Vector((0, 0, -0.012))), p["ink"], smooth=False),
        thread,
    ]


def skull(p):
    """A skull about 5 cm high facing +x: one smooth bone — a round cranium over a brow ridge,
    cheekbones, the teeth's arch and the chin — with deep sockets, the nose's upturned heart, a grin
    and a crack over the right eye carved into it, the carving dark."""
    # Blended balls, each given by where its surface stands (a ball's surface is 0.575 of its
    # radius), built ten times over so the mesh is fine enough, then brought down to size.
    meta = bpy.data.metaballs.new("skull")
    meta.resolution = meta.render_resolution = 0.024
    for centre, surface in (
        ((-0.005, 0, 0.034), 0.027),
        ((-0.012, 0, 0.03), 0.022),
        ((0.01, 0, 0.033), 0.02),
        ((0.02, 0.011, 0.034), 0.0075),
        ((0.02, -0.011, 0.034), 0.0075),
        ((0.019, 0.014, 0.019), 0.0105),
        ((0.019, -0.014, 0.019), 0.0105),
        ((0.02, 0, 0.012), 0.012),
        ((0.016, 0.008, 0.005), 0.011),
        ((0.016, -0.008, 0.005), 0.011),
        ((0.022, 0, 0.003), 0.009),
        ((0.023, 0, 0.0075), 0.0085),
    ):
        element = meta.elements.new(type="BALL")
        element.co = Vector(centre) * 10
        element.radius = surface * 10 / 0.575
    blob = bpy.data.objects.new("skull blob", meta)
    bpy.context.scene.collection.objects.link(blob)
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(
        blob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    )
    bpy.data.objects.remove(blob)
    bpy.data.metaballs.remove(meta)
    # Down to size, a little narrower than long, standing on z = 0.
    mesh.transform(Matrix.Diagonal((0.1, 0.088, 0.1, 1.0)))
    mesh.transform(Matrix.Translation((0, 0, -min(v.co.z for v in mesh.vertices))))
    bone = bpy.data.objects.new("skull", mesh)
    bpy.context.scene.collection.objects.link(bone)
    bone.data.materials.append(p["bone"])
    surface = BVHTree.FromObject(bone, bpy.context.evaluated_depsgraph_get())

    def front(y, z):
        """Where the face is at height z and y across, seen from straight ahead."""
        return surface.ray_cast(Vector((0.2, y, z)), Vector((-1, 0, 0)), 0.3)[0].x

    # What is carved out, each cutter in the dark it leaves behind.
    cuts = bpy.data.collections.new("skull cuts")
    bpy.context.scene.collection.children.link(cuts)

    def cut(bm, name):
        obj = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.materials.append(p["ink"])
        cuts.objects.link(obj)

    # The sockets a little wider than tall, their outer corners drooping.
    eyes = 0.027
    for side in (1, -1):
        socket = bmesh.new()
        bmesh.ops.create_uvsphere(socket, u_segments=24, v_segments=16, radius=1.0)
        at = Vector((front(0.0108 * side, eyes) + 0.0035, 0.0108 * side, eyes))
        turn = Matrix.Rotation(-0.3 * side, 4, "Z") @ Matrix.Rotation(-0.28 * side, 4, "X")
        cut(
            place(
                socket,
                Matrix.Translation(at) @ turn @ Matrix.Diagonal((0.0088, 0.0094, 0.0078, 1.0)),
            ),
            f"socket {side}",
        )
    nose = front(0, 0.0165)
    cut(
        place(
            slab(
                [
                    (-0.0038, 0.0132),
                    (0.0038, 0.0132),
                    (0.0011, 0.0186),
                    (0, 0.0198),
                    (-0.0011, 0.0186),
                ],
                0.012,
            ),
            Matrix.Translation((nose + 0.003, 0, 0)),
        ),
        "nose",
    )
    mouth = front(0, 0.0075)
    cut(box((mouth + 0.004, 0, 0.0075), (0.012, 0.02, 0.0018)), "mouth")
    for k in range(5):
        y = (k - 2) * 0.0034
        cut(box((front(y, 0.0075) + 0.004, y, 0.0075), (0.0095, 0.0009, 0.0098)), f"tooth gap {k}")
    # A crack running down from the crown to the right brow, grooved along the bone.
    path = [
        surface.ray_cast(Vector((0.2, y, z)), Vector((-1, 0, 0)), 0.3)
        for y, z in (
            (-0.002, 0.056),
            (-0.0075, 0.052),
            (-0.005, 0.047),
            (-0.011, 0.043),
            (-0.0095, 0.039),
        )
    ]
    for k, ((a, normal, _, _), (b, _, _, _)) in enumerate(pairwise(path)):
        along = (b - a).normalized()
        across = along.cross(
            normal
        ).normalized()  # right-handed with normal and along, or the box turns inside out
        basis = Matrix((normal, across, along)).transposed().to_4x4()
        cut(
            place(
                box((0, 0, 0), (0.004, 0.0009, (b - a).length + 0.0008)),
                Matrix.Translation((a + b) / 2) @ basis,
            ),
            f"crack {k}",
        )
    carve = bone.modifiers.new("carve", "BOOLEAN")
    carve.operation = "DIFFERENCE"
    carve.operand_type = "COLLECTION"
    carve.collection = cuts
    carve.solver = "EXACT"
    carve.material_mode = "TRANSFER"
    bpy.context.view_layer.update()
    carved = bpy.data.meshes.new_from_object(
        bone.evaluated_get(bpy.context.evaluated_depsgraph_get())
    )
    bone.modifiers.clear()
    bone.data = carved
    bpy.data.meshes.remove(mesh)
    for obj in list(cuts.objects):
        bpy.data.meshes.remove(obj.data)
    bpy.data.collections.remove(cuts)
    carved.shade_smooth()
    carved.set_sharp_from_angle(angle=math.radians(50))
    return [bone]


def potions(p):
    """Three bottles of glowing brew: a round flask, a square bottle with a label, a thin vial."""
    parts = []
    bottles = (
        # (at, glass profile, segments, brew profile, brew, cork height)
        (
            (0, 0, 0),
            [
                (0, 0),
                (0.012, 0.002),
                (0.017, 0.014),
                (0.012, 0.027),
                (0.0045, 0.032),
                (0.0045, 0.05),
                (0, 0.05),
            ],
            24,
            [(0, 0.0015), (0.0112, 0.0032), (0.0155, 0.014), (0.012, 0.022), (0, 0.022)],
            "potion green",
            0.05,
        ),
        (
            (-0.006, 0.03, 0),
            [(0, 0), (0.012, 0), (0.012, 0.04), (0.005, 0.047), (0.005, 0.056), (0, 0.056)],
            4,
            [(0, 0.0015), (0.0108, 0.0015), (0.0108, 0.03), (0, 0.03)],
            "potion purple",
            0.056,
        ),
        (
            (0.006, -0.026, 0),
            [(0, 0), (0.0055, 0), (0.0055, 0.036), (0, 0.036)],
            16,
            [(0, 0.0015), (0.0047, 0.0015), (0.0047, 0.022), (0, 0.022)],
            "potion orange",
            0.036,
        ),
    )
    for k, (at, profile, segments, brew_profile, brew, top) in enumerate(bottles):
        turn = Matrix.Translation(at) @ Matrix.Rotation(
            math.radians(45 if segments == 4 else 0), 4, "Z"
        )
        parts.append(
            mesh_object(
                f"potion glass {k}",
                place(lathe(profile, segments), turn),
                p["glass"],
                smooth=segments > 4,
            )
        )
        parts.append(
            mesh_object(
                f"potion brew {k}",
                place(lathe(brew_profile, segments), turn),
                p[brew],
                smooth=segments > 4,
            )
        )
        neck = profile[-2][0]
        parts.append(
            mesh_object(
                f"potion cork {k}",
                place(
                    lathe(
                        [
                            (0, top - 0.002),
                            (neck * 0.9, top - 0.002),
                            (neck * 1.15, top + 0.007),
                            (0, top + 0.007),
                        ],
                        12,
                    ),
                    turn,
                ),
                p["cork"],
            )
        )
    # On the square bottle's front face, half a millimetre proud of it.
    parts.append(
        mesh_object(
            "potion label",
            box((0.0031, 0.03, 0.019), (0.0012, 0.014, 0.016)),
            p["paper"],
            smooth=False,
        )
    )
    return parts


def lettering(p):
    """HAPPY over HALLOWEEN in the site's Anton, in deep purple over an orange shadow, standing in
    the y-z plane and reading towards +x, centred on the origin: 0.3 m wide."""
    font = bpy.data.fonts.load(
        str(ROOT / "app" / "public" / "design" / "fonts" / "anton-400-latin.woff2")
    )
    parts = []
    for word, size, lift, tilt in (("HAPPY", 0.085, 0.031, -3), ("HALLOWEEN", 0.123, -0.03, 2)):
        for colour, shift in (
            ("letters shadow", Vector((-0.003, 0.0022, -0.0022))),
            ("letters", Vector((0, 0, 0))),
        ):
            bm = text_mesh(word, font, size, 0.004)
            # Centred on its own box, then hung at its height with a little tilt, as if pinned by hand.
            low = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
            high = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
            bmesh.ops.translate(bm, vec=-(low + high) / 2, verts=bm.verts)
            place(
                bm,
                Matrix.Translation(Vector((0, 0, lift)) + shift)
                @ Matrix.Rotation(math.radians(tilt), 4, "X"),
            )
            parts.append(mesh_object(f"{word.lower()} {colour}", bm, p[colour], smooth=False))
    return parts


def garland(p):
    """A string of little lights hung in three swags across 0.56 m of its own y, from anchors at
    z 0, the bulbs on its +x side: orange, purple and green in turn."""
    anchors = [-0.28, -0.0933, 0.0933, 0.28]
    path = []
    for a, b in pairwise(anchors):
        for k in range(12):
            t = k / 12
            path.append(Vector((0.002, a + (b - a) * t, -0.02 * math.sin(math.pi * t))))
    path.append(Vector((0.002, anchors[-1], 0)))
    parts = [mesh_object("garland cord", sweep(path, 0.0009, 5), p["cord"])]
    bulbs = {name: bmesh.new() for name in ("potion orange", "potion purple", "potion green")}
    sockets = bmesh.new()
    for k, point in enumerate(path[2:-1:3]):
        colour = list(bulbs)[k % 3]
        bulb = bmesh.new()
        bmesh.ops.create_icosphere(bulb, subdivisions=2, radius=1.0)
        merge(
            bulbs[colour],
            place(
                bulb,
                Matrix.Translation(point + Vector((0.004, 0, -0.008)))
                @ Matrix.Diagonal((0.0042, 0.0042, 0.006, 1.0)),
            ),
        )
        merge(
            sockets,
            place(
                lathe([(0, 0), (0.0025, 0), (0.0025, 0.004), (0, 0.004)], 8),
                Matrix.Translation(point + Vector((0.004, 0, -0.004))),
            ),
        )
    parts += [mesh_object(f"garland bulbs {name}", bm, p[name]) for name, bm in bulbs.items()]
    parts.append(mesh_object("garland sockets", sockets, p["cord"], smooth=False))
    return parts


PROPS = {
    "jack": lambda p: jack(p, name="jack"),
    "tombstone": tombstone,
    "candles": candles,
    "cauldron": cauldron,
    "ghost": ghost,
    "bat": bat,
    "cobweb": cobweb,
    "spider": spider,
    "skull": skull,
    "potions": potions,
    "lettering": lettering,
    "garland": garland,
}


# ── The reference duck (previews only) ───────────────────────────────────

LIVERY = {
    "classic": (0.888, 0.86, 0.798),
    "charcoal": (0.017, 0.017, 0.019),
    "purple": (0.462, 0.367, 0.688),
    "blue": (0.441, 0.613, 0.723),
}
WEARS = {"peter": "classic", "ray": "blue", "giant": "classic"}
SHELLS = {
    "top_head_shell.stl",
    "trunk_base.stl",
    "left_shell.stl",
    "right_shell.stl",
    "upper_leg_left.stl",
    "upper_leg_right.stl",
}


def reference_duck(kinematics, meshes, frames, livery):
    shell = material(f"ref shell {livery}", LIVERY[livery], 0.4)
    face = material("ref face", (0.328, 0.312, 0.283), 0.35)
    beak = material("ref beak", (1.0, 0.144, 0.008), 0.45)
    dark = material("ref dark", (0.03, 0.03, 0.035), 0.5)
    lens = material("ref lens", (0.01, 0.012, 0.02), 0.05)
    paint = {
        "jaw.stl": beak,
        "foot_left.stl": beak,
        "foot_right.stl": beak,
        "noenoeil.stl": beak,
        "bottom_head_shell.stl": beak,
        "lens.stl": lens,
        "face_part.stl": face,
    }
    parts = []
    for body in kinematics["bodies"]:
        for geom in body.get("geoms", []):
            if geom.get("mesh") not in meshes:
                continue
            vertices, faces = meshes[geom["mesh"]]
            mesh = bpy.data.meshes.new(f"ref {geom['mesh']}")
            mesh.from_pydata([tuple(v) for v in vertices], [], [tuple(f) for f in faces])
            obj = bpy.data.objects.new(mesh.name, mesh)
            bpy.context.scene.collection.objects.link(obj)
            obj.data.materials.append(
                shell if geom["mesh"] in SHELLS else paint.get(geom["mesh"], dark)
            )
            obj.matrix_world = geom_matrix(frames, body, geom)
            parts.append(obj)
    return parts


def preview(directory, kinematics, meshes, frames, wardrobe):
    """One picture per costume, on a duck of its colour, from the front three-quarter and the back."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 720
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("world")
    world.color = (0.02, 0.02, 0.03)
    scene.world = world
    for kind, energy, rotation in (("SUN", 3.0, (0.7, 0.2, 0.9)), ("SUN", 1.0, (1.1, 0.0, -2.4))):
        light = bpy.data.objects.new(kind, bpy.data.lights.new(kind, kind))
        light.data.energy = energy
        light.rotation_euler = rotation
        scene.collection.objects.link(light)
    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    camera.data.lens = 60
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, pieces in wardrobe.items():
        duck = reference_duck(kinematics, meshes, frames, WEARS.get(name, name))
        for objs in pieces.values():
            for obj in objs:
                obj.hide_render = False
        for view, at, target in (
            ("front", (0.55, 0.32, 0.3), (0, 0, 0.19)),
            ("back", (-0.5, -0.3, 0.32), (0, 0, 0.19)),
            ("head", (0.3, 0.16, 0.32), (0.01, 0, 0.24)),
        ):
            camera.location = at
            camera.rotation_euler = (
                (Vector(target) - Vector(at)).to_track_quat("-Z", "Y").to_euler()
            )
            scene.render.filepath = str(Path(directory) / f"{name}-{view}.png")
            bpy.ops.render.render(write_still=True)
        for objs in pieces.values():
            for obj in objs:
                obj.hide_render = True
        for obj in duck:
            bpy.data.objects.remove(obj)


def preview_props(directory, props):
    """The props side by side, in one picture."""
    scene = bpy.context.scene
    for k, objs in enumerate(props.values()):
        for obj in objs:
            obj.location = (0, 0.22 * (k - (len(props) - 1) / 2), 0)
            obj.hide_render = False
    eye = Vector((0.36 * len(props), 0.3, 0.7))
    scene.camera.location = eye
    scene.camera.rotation_euler = (Vector((0, 0, 0.08)) - eye).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = 1600
    scene.render.filepath = str(Path(directory) / "props.png")
    bpy.ops.render.render(write_still=True)
    for objs in props.values():
        for obj in objs:
            obj.location = (0, 0, 0)


def export(wardrobe, frames, props):
    """Each costume a node, each body a child carrying `body` in its extras, each piece in that body's
    frame; each prop a node over its pieces."""
    bpy.ops.object.select_all(action="DESELECT")
    for name, objs in props.items():
        prop = bpy.data.objects.new(f"prop {name}", None)
        prop["prop"] = name
        bpy.context.scene.collection.objects.link(prop)
        prop.select_set(True)
        for obj in objs:
            # A wing hangs at its shoulder, so the scene turns it about there.
            if "wing" in obj:
                obj.location = (0.0, 0.006 * obj["wing"], 0.004)
            obj.parent = prop
            obj.hide_render = False
            obj.select_set(True)
    for name, pieces in wardrobe.items():
        costume = bpy.data.objects.new(f"costume {name}", None)
        costume["costume"] = name
        bpy.context.scene.collection.objects.link(costume)
        costume.select_set(True)
        for body, objs in pieces.items():
            holder = bpy.data.objects.new(f"{name} {body}", None)
            holder["body"] = body
            holder.parent = costume
            bpy.context.scene.collection.objects.link(holder)
            holder.select_set(True)
            inverse = frames[body].inverted()
            for obj in objs:
                obj.data.transform(inverse)
                obj.parent = holder
                obj.hide_render = False
                obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT),
        export_format="GLB",
        use_selection=True,
        export_yup=False,
        export_extras=True,
        export_apply=True,
        export_texcoords=False,
    )


def main():
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    kinematics = json.loads((ROBOT / "kinematics.json").read_text())
    meshes = read_glb(ROBOT / "microduck.glb")
    frames = stand_frames(kinematics)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    duck = Duck(kinematics, meshes, frames)
    p = paints()
    wardrobe = {name: dress(duck, p) for name, dress in COSTUMES.items()}
    props = {name: make(p) for name, make in PROPS.items()}
    if "--preview" in args:
        directory = args[args.index("--preview") + 1]
        for obj in bpy.context.scene.objects:
            obj.hide_render = True
        preview(directory, kinematics, meshes, frames, wardrobe)
        preview_props(directory, props)
    export(wardrobe, frames, props)


if __name__ == "__main__":
    main()
