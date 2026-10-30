"""Sock Heist's venue: the giant microduck's nest woven from socks, the loose socks on its floor,
and the school playground at the microducks' scale that the race runs in.

Run headless from the repository root, in Blender 5.2.2:

    blender -b -P scripts/sock_heist_venue.py -- app/public/venue [--render <dir>]

It writes `sock-nest.glb` (one mesh `nest`), `socks.glb` (meshes `sock_0` ... `sock_4`) and
`playground.glb`: glTF Y up, metres, vertex colours on one plain material. The playground's origin
is on the start line at the lanes' centre line, and it has four nodes: `yard`, the concrete ground
and the park's grass; `left`, the school, and `right`, the wooden fence, each built out from the
lanes' edge with its crowd's spots `spot_<k>`; and `park`, the trees behind the giant. Its trees
and fence panels are instanced. It prints the giant's seated pose, the joint angles and the trunk
height the site seats it with, and the playground's models, the triangles it draws and its spots.

With `--render` it also sits the racers' own microduck, GIANT_SCALE times their size, in the nest,
stands four life-size racers on the start line and lays socks between the finish line and the
nest. On a grey floor it renders chase.png, nest-three-quarter.png, close.png and turned.png for
the owner. Then it lays the playground round them, a duck of the crowd on each spot, and renders
page.png, three-quarter.png, crowd.png and park.png.

The nest's sizes come from the seated giant: its inside fits the giant's footprint plus 10 % and
its rim rises over the giant's folded legs. The socks are a person's socks. Everything random is
drawn from random.Random(0), the playground's from random.Random(1), so a rebuild gives the same
files.
"""

import argparse
import json
import random
import sys
from dataclasses import dataclass
from functools import cache
from itertools import count, pairwise
from math import ceil, cos, dist, hypot, pi, radians, sin, tan, tau
from pathlib import Path

import bpy
import numpy as np
from mathutils import Color, Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from arena.constants import DEFAULT_POSE, JOINT_NAMES

ROBOT = ROOT / "app" / "public" / "robot"
# The racers' standing pose.
STAND = dict(zip(JOINT_NAMES, DEFAULT_POSE.tolist()))

GIANT_SCALE = 4.5
FOLD = 0.95  # how far into its range each hip pitch and knee folds for the giant to sit
FOOTPRINT_MARGIN = 1.1
NEST_TRIANGLES = 6000

# The render's layout, as the site lays the race out: a 6 m lane, four lanes LANE_SPACING_M apart
# (a lane's 0.8 m and its 0.05 m wall, app/src/course.js laneSpacing), their edge EDGE_M from the
# centre line, the giant's and the nest's centre GIANT_BEHIND_M past the finish line, the loose
# socks SOCKS_PER_M per metre across the lanes, between SOCK_FIELD metres past the line.
LENGTH_M = 6.0  # arena/events/sock-heist-6m.toml's length_m
LANE_SPACING_M = 0.85
LANES = tuple(LANE_SPACING_M * (k - 1.5) for k in range(4))  # ±0.425 and ±1.275
EDGE_M = 2 * LANE_SPACING_M
GIANT_BEHIND_M = 1.95  # app/src/giant.js
SOCK_FIELD = (0.15, 0.95)  # giant.js
SOCKS_PER_M = 7  # giant.js
# The race camera at the start, as app/src/viewer.js poses it: the event's [clip.camera] (3.0 m
# back, 1.2 m up, 0.1 m to the side, a 42° lens) looking at the start line 0.5 m up, backed off
# and raised by packChase until the four lanes and its 0.3 m margin fit across a 16:9 picture.
CHASE_BACK_M, CHASE_HEIGHT_M, CHASE_SIDE_M, CHASE_FOV = 3.0, 1.2, 0.1, 42
CHASE_TARGET_M, PACK_MARGIN_M = 0.5, 0.3

RACER_MODEL = ROBOT / "microduck.glb"
CROWD_MODEL = ROBOT / "microduck-crowd.glb"  # the same parts, decimated: the site's crowd
# The crowd's sitting pose (app/src/stadium.js SIT): STAND with the hips, knees and ankles folded,
# the trunk level SIT_TRUNK_M over the floor; and its shells' colours (app/src/palette.js SHELLS).
SIT = STAND | {
    "left_hip_pitch": -1.3, "left_knee": 1.5, "left_ankle": -0.2,
    "right_hip_pitch": 1.3, "right_knee": -1.5, "right_ankle": 0.2,
}
SIT_TRUNK_M = 0.055
SHELLS = ("#f7e6cb", "#8fb8dc", "#2ff0e6", "#ff2fa8", "#ffd23f")
SKY = "#b8dce7"  # app/src/viewer.js's scene.background by day

PALETTE = {
    "lime": "#c8ff2e",
    "white": "#ffffff",
    "charcoal": "#2b2d33",
    "red": "#ff2b2b",
    "sky": "#87ceeb",
}


@dataclass(frozen=True)
class Sock:
    """One sock model: its lengths along the centreline, its colour and the second colour of its
    cuff, stripes, heel and toe, its stripes (spans along the leg, in metres from the cuff), and
    its curl: how far it wanders either way as it lies, in radians per metre, and from where."""

    leg: float
    foot: float
    colour: str
    second: str
    stripes: tuple[tuple[float, float], ...]
    curl: tuple[float, float]


SOCKS = (
    Sock(0.10, 0.21, "charcoal", "lime", (), (2.5, 0.0)),  # an ankle sock
    Sock(0.22, 0.22, "white", "red", ((0.06, 0.08), (0.10, 0.12)), (2.0, 1.3)),  # a sports sock
    Sock(0.40, 0.23, "lime", "charcoal", (), (2.2, 2.6)),  # a knee sock, the longest
    Sock(0.17, 0.21, "red", "white", (), (2.8, 4.0)),
    Sock(0.28, 0.22, "sky", "white", (), (2.4, 5.2)),
)
RADIUS = 0.035  # a sock laid flat is twice this wide
FLAT = 0.5  # a sock lying down keeps this much of its height
HEEL_TURN = radians(45)  # how far the foot turns from the leg
BEND = 0.09  # the length of the heel's soft turn
HEEL_BULGE = 0.7  # how far the heel's cup stands out, in radii
CURL_WAVE = 1.0  # the length of a sock's curl, longer than the sock: a gentle bend
CUFF_BAND = 0.035
CUFF_FLARE = 1.15  # the cuff's rib, wider than the leg
CUFF_STEP = 0.012  # how short the cuff's rib narrows to the leg, with Detail.rib
TOE_BAND = 0.055
TOE_LENGTH = 0.9  # the toe cap's length, in radii


@dataclass(frozen=True)
class Detail:
    """How finely a sock is swept: sides round the tube, steps round the heel, the longest step
    along it, the rings of its toe cap, and whether the cuff's rib narrows sharply to the leg
    (rib) or tapers to the next ring."""

    sides: int
    bend: int
    step: float
    toe: int
    rib: bool


FINE = Detail(sides=8, bend=4, step=0.06, toe=2, rib=True)  # a loose sock, instanced
COARSE = Detail(sides=6, bend=2, step=0.2, toe=1, rib=False)  # a sock of the nest


class Soup:
    """Vertices, faces and a colour per face corner, gathered before they become one mesh."""

    def __init__(self):
        self.verts: list[Vector] = []
        self.faces: list[tuple[int, ...]] = []
        self.colours: list[tuple[float, ...]] = []

    def add(self, other: "Soup"):
        base = len(self.verts)
        self.verts += other.verts
        self.faces += [tuple(base + i for i in face) for face in other.faces]
        self.colours += other.colours

    def face(self, indices: tuple[int, ...], colours: list[tuple[float, ...]]):
        self.faces.append(indices)
        self.colours += colours

    def polygon(self, points: list[Vector], colour: tuple[float, ...]):
        """A flat face on vertices of its own, in one colour: a facet, sharp against its
        neighbours however the mesh is shaded."""
        base = len(self.verts)
        self.verts += points
        self.face(tuple(range(base, base + len(points))), [colour] * len(points))

    @property
    def triangles(self) -> int:
        return sum(len(face) - 2 for face in self.faces)


def srgb(code: str) -> tuple[float, float, float, float]:
    return (*(int(code[k : k + 2], 16) / 255 for k in (1, 3, 5)), 1.0)


def linear(code: str) -> tuple[float, float, float, float]:
    """An sRGB hex code in linear light, as three.js reads a hex colour."""
    return (*Color(srgb(code)[:3]).from_srgb_to_scene_linear(), 1.0)


def link(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    return obj


@cache
def kinematics() -> dict:
    return json.loads((ROBOT / "kinematics.json").read_text())


@cache
def part_meshes(model: Path) -> dict[str, bpy.types.Mesh]:
    """The model's part meshes by file name, in the rig's own frame. The GLB holds the raw MJCF
    meshes, Z up, and the site hangs them as they are under its one Y-up root (app/src/rig.js); the
    glTF importer took them for Y up and turned them, so they are turned back."""
    bpy.ops.import_scene.gltf(filepath=str(model))
    material = racer_material()
    meshes = {}
    for obj in list(bpy.context.selected_objects):
        mesh = obj.data
        mesh.transform(Matrix.Rotation(-pi / 2, 4, "X"))
        mesh.shade_smooth()
        mesh.set_sharp_from_angle(angle=pi / 5)  # rig.js's crease
        mesh.materials.append(material)
        meshes[obj["meshFile"]] = mesh
        bpy.data.objects.remove(obj)
    return meshes


def racer_material() -> bpy.types.Material:
    """Each part takes its kinematics colour, carried as its object's colour."""
    material = bpy.data.materials.new("racer")
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes["Principled BSDF"]
    shader.inputs["Roughness"].default_value = 0.55
    links.new(nodes.new("ShaderNodeObjectInfo").outputs["Color"], shader.inputs["Base Color"])
    return material


def racer(
    angles: dict[str, float], model: Path = RACER_MODEL, shell: str | None = None
) -> bpy.types.Object:
    """A microduck assembled as app/src/rig.js assembles it: an empty per body of kinematics.json at
    its pos and quat (w, x, y, z) under its parent, a hinge turning on top of the body's rest
    orientation about its axis, and each geom a linked copy of its part mesh at its own pos and
    quat. Blender is Z up like the MJCF, so the root needs none of rig.js's turn to Y up. A shell
    colour paints its shells, as the crowd's are."""
    meshes = part_meshes(model)
    painted = linear(shell) if shell else None
    root = link(bpy.data.objects.new("racer", None))
    bodies = {}
    for body in kinematics()["bodies"]:
        empty = link(bpy.data.objects.new(body["name"], None))
        empty.parent = bodies.get(body["parent"], root)
        empty.location = body["pos"]
        empty.rotation_mode = "QUATERNION"
        rotation = Quaternion(body["quat"])
        joint = body["joint"]
        if joint:
            rotation = rotation @ Quaternion(joint["axis"], angles.get(joint["name"], 0.0))
        empty.rotation_quaternion = rotation
        bodies[body["name"]] = empty
        for geom in body["geoms"]:
            part = link(bpy.data.objects.new(geom["mesh"], meshes[geom["mesh"]]))
            part.parent = empty
            part.location = geom["pos"]
            part.rotation_mode = "QUATERNION"
            part.rotation_quaternion = Quaternion(geom["quat"])
            part.color = painted if painted and "shell" in geom["mesh"] else geom["color"]
    return root


def joint_body(name: str) -> dict:
    return next(b for b in kinematics()["bodies"] if (b["joint"] or {}).get("name") == name)


def head_turned() -> float:
    """head_yaw's own lower limit: round over the shoulder, the face back at the lanes."""
    return joint_body("head_yaw")["joint"]["range"][0]


@cache
def sitting() -> dict[str, float]:
    """STAND with the legs folded under the lowered trunk, as a duck sits on its nest: each hip
    pitch and knee FOLD of the way to the end of its range, the left toward its upper end and the
    right, mirrored as at STAND, toward its lower; each ankle at knee - hip, which keeps the foot
    level as it is at STAND. The head and neck stay as at STAND."""
    pose = dict(STAND)
    for side, end in (("left", 1), ("right", 0)):
        hip, knee = (
            FOLD * joint_body(f"{side}_{joint}")["joint"]["range"][end]
            for joint in ("hip_pitch", "knee")
        )
        pose |= {f"{side}_hip_pitch": hip, f"{side}_knee": knee, f"{side}_ankle": knee - hip}
    return pose


@dataclass(frozen=True)
class Measure:
    """A racer in a pose, its trunk where kinematics.json puts it: its world box in Blender axes
    (Z up), and the top of its legs, the meshes its hip pitch joints carry."""

    lo: Vector
    hi: Vector
    legs: float

    @property
    def size(self) -> tuple[float, float, float]:
        """Width, height and depth, in glTF axes: along the lane, up, across it."""
        x, y, z = self.hi - self.lo
        return x, z, y

    @property
    def footprint(self) -> float:
        """How far the racer reaches from its own vertical axis: its box's farthest corner."""
        return max(hypot(x, y) for x in (self.lo.x, self.hi.x) for y in (self.lo.y, self.hi.y))

    @property
    def trunk(self) -> float:
        """The trunk's height once the racer rests on the floor."""
        return rig_trunk() - self.lo.z


def rig_trunk() -> float:
    """The trunk's height over the rig's origin: its root body's, in kinematics.json."""
    return next(b for b in kinematics()["bodies"] if b["parent"] is None)["pos"][2]


def racer_box(angles: dict[str, float]) -> Measure:
    duck = racer(angles)
    bpy.context.view_layer.update()
    hips = {joint_body(f"{side}_hip_pitch")["name"] for side in ("left", "right")}
    legs = {p for b in duck.children_recursive if b.name in hips for p in b.children_recursive}
    points, leg_points = [], []
    for part in duck.children_recursive:
        if part.type == "MESH":
            co = np.empty(len(part.data.vertices) * 3)
            part.data.vertices.foreach_get("co", co)
            world = np.array(part.matrix_world)
            points.append(co.reshape(-1, 3) @ world[:3, :3].T + world[:3, 3])
            if part in legs:
                leg_points.append(points[-1])
    points = np.concatenate(points)
    measure = Measure(
        Vector(points.min(0)), Vector(points.max(0)), float(np.concatenate(leg_points)[:, 2].max())
    )
    bpy.data.batch_remove([duck, *duck.children_recursive])
    return measure


def length(sock: Sock) -> float:
    return sock.leg + BEND + sock.foot


def integral(values: np.ndarray, s: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum((values[1:] + values[:-1]) / 2 * np.diff(s))])


@cache
def centreline_table(sock: Sock) -> np.ndarray:
    """The flat sock's centreline from its cuff, as rows (s, a, b): it runs along a, curling gently
    either way, and turns HEEL_TURN softly over the heel's BEND, the turn's rate rising and falling
    like a sine, toward b."""
    s = np.linspace(0.0, length(sock), 241)
    heel = np.sin(pi * np.clip((s - sock.leg) / BEND, 0, 1)) * pi / 2 / BEND  # integrates to 1
    amount, start = sock.curl
    heading = integral(HEEL_TURN * heel + amount * np.sin(tau * s / CURL_WAVE + start), s)
    return np.stack([s, integral(np.cos(heading), s), integral(np.sin(heading), s)], 1)


def centreline(sock: Sock, s: float) -> tuple[float, float]:
    along, a, b = centreline_table(sock).T
    return float(np.interp(s, along, a)), float(np.interp(s, along, b))


def span(sock: Sock) -> tuple[float, float]:
    """Where a flat sock lies along a: the middle of its reach, and its reach with the tube's
    ends."""
    a = centreline_table(sock)[:, 1]
    return (a.min() + a.max()) / 2, a.max() - a.min() + 2 * RADIUS


def stations(sock: Sock, detail: Detail) -> list[float]:
    """Where the tube's rings go along the centreline: round the heel, at the cuff's, the toe's and
    the stripes' edges, where the cuff's rib narrows with detail.rib, and never further apart
    than detail.step."""
    end = length(sock)
    marks = {0.0, CUFF_BAND, end - TOE_BAND, end}
    if detail.rib:
        marks.add(CUFF_BAND + CUFF_STEP)
    marks |= {sock.leg + BEND * k / detail.bend for k in range(detail.bend + 1)}
    marks |= {edge for stripe in sock.stripes for edge in stripe}
    marks = sorted(marks)
    out = [marks[0]]
    for s in marks[1:]:
        steps = ceil((s - out[-1]) / detail.step)
        out += [out[-1] + (s - out[-1]) * k / steps for k in range(1, steps + 1)]
    return out


def flat(a: float, b: float) -> tuple[Vector, Vector]:
    """A sock's own frame: lying on the floor, its centreline in the plane z = 0."""
    return Vector((a, b, 0.0)), Vector((0, 0, 1))


def sock_soup(sock: Sock, detail: Detail, place=flat) -> Soup:
    """A sock lying on something: a tube of detail.sides swept round its centreline, set in the
    world by place(a, b) -> (point, up), and flattened to FLAT of its height along up. The cuff is
    a wider rib round an opening, dark inside; the heel's outer side bulges into a cup; the toe is
    a rounded cap. The cuff, the stripes, the heel's cup and the toe take the second colour."""
    end = length(sock)
    colour, second = srgb(PALETTE[sock.colour]), srgb(PALETTE[sock.second])
    along = stations(sock, detail)
    points, ups = zip(*(place(*centreline(sock, s)) for s in along))
    last = len(points) - 1
    tangents = [
        (points[min(k + 1, last)] - points[max(k - 1, 0)]).normalized() for k in range(len(points))
    ]
    heel = [place(*centreline(sock, sock.leg + BEND * f))[0] for f in (0, 0.5, 1)]
    outward = (heel[1] - (heel[0] + heel[2]) / 2).normalized()

    # Each ring: its centre, its tangent, its up, its radius and where it is along the sock.
    rings = [
        (p, t, u, RADIUS * (CUFF_FLARE if s <= CUFF_BAND else 1.0), s)
        for p, t, u, s in zip(points, tangents, ups, along)
    ]
    for k in range(1, detail.toe + 1):
        angle = pi / 2 * k / (detail.toe + 1)
        toe = points[-1] + tangents[-1] * RADIUS * TOE_LENGTH * sin(angle)
        rings.append((toe, tangents[-1], ups[-1], RADIUS * cos(angle), end))

    soup = Soup()
    loops = []
    for centre, tangent, up, radius, s in rings:
        normal = (up - tangent * up.dot(tangent)).normalized()
        binormal = tangent.cross(normal)
        cup = sin(pi * (s - sock.leg) / BEND) if sock.leg < s < sock.leg + BEND else 0.0
        loop = []
        for j in range(detail.sides):
            # Half a side round from up, so that the flattened sock has a face, not an edge, on top.
            around = tau * (j + 0.5) / detail.sides
            direction = normal * cos(around) + binormal * sin(around)
            loop.append(len(soup.verts))
            bulge = 1 + HEEL_BULGE * cup * max(0.0, direction.dot(outward)) ** 2
            squashed = normal * FLAT * cos(around) + binormal * sin(around)
            soup.verts.append(centre + squashed * radius * bulge)
        loops.append(loop)

    def paint(s: float, facing: Vector) -> tuple[float, ...]:
        if s < CUFF_BAND or s > end - TOE_BAND or any(a < s < b for a, b in sock.stripes):
            return second
        if sock.leg < s < sock.leg + BEND and facing.dot(outward) > -0.2:
            return second
        return colour

    for k in range(len(loops) - 1):
        s = (rings[k][4] + rings[k + 1][4]) / 2
        axis = (rings[k][0] + rings[k + 1][0]) / 2
        for j in range(detail.sides):
            quad = (loops[k][j - 1], loops[k][j], loops[k + 1][j], loops[k + 1][j - 1])
            facing = sum((soup.verts[i] for i in quad), Vector()) / 4 - axis
            soup.face(quad, [paint(s, facing.normalized())] * 4)
    tip = len(soup.verts)
    soup.verts.append(points[-1] + tangents[-1] * RADIUS * TOE_LENGTH)
    for j in range(detail.sides):
        soup.face((loops[-1][j - 1], loops[-1][j], tip), [second] * 3)
    opening = len(soup.verts)
    soup.verts.append(points[0] + tangents[0] * RADIUS * 0.6)
    inside = (*(c * 0.3 for c in colour[:3]), 1.0)
    for j in range(detail.sides):
        soup.face((loops[0][j], loops[0][j - 1], opening), [second, second, inside])
    return soup


def mesh_object(name: str, soup: Soup, material: bpy.types.Material) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in soup.verts], [], soup.faces)
    mesh.shade_smooth()
    colours = mesh.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
    colours.data.foreach_set("color_srgb", [c for corner in soup.colours for c in corner])
    mesh.materials.append(material)
    return link(bpy.data.objects.new(name, mesh))


def venue_material() -> bpy.types.Material:
    """The one plain material of both GLBs: the vertex colours, rough as cotton, no metal, and
    single-sided, as every model here is closed."""
    material = bpy.data.materials.new("socks")
    material.use_backface_culling = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes["Principled BSDF"]
    shader.inputs["Roughness"].default_value = 0.9
    shader.inputs["Metallic"].default_value = 0.0
    colours = nodes.new("ShaderNodeVertexColor")
    colours.layer_name = "Color"
    links.new(colours.outputs["Color"], shader.inputs["Base Color"])
    return material


def sock(variant: int, material: bpy.types.Material) -> bpy.types.Object:
    """A loose sock lying on the floor, its origin there under its middle."""
    soup = sock_soup(SOCKS[variant], FINE)
    lo, hi = np.min(soup.verts, 0), np.max(soup.verts, 0)
    shift = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
    soup.verts = [v - shift for v in soup.verts]
    return mesh_object(f"sock_{variant}", soup, material)


# The heap the nest's socks lie on, in parts of its rim's height: how far its cross-section reaches
# in from its crest and out to its foot. The cross-section is a mound, flat on its crest and flaring
# onto the floor on either side.
INSIDE = 0.2
OUTSIDE = 0.5
ACROSS = 0.15  # the share of socks laid across a row, over those laid along it end to end
FEET_DOWN = 0.7  # the share of socks along a row whose foot hangs down the heap's outside
TOES_UP = 0.2  # the share of socks along the crest's row whose foot rises off the heap
DRAPE = 0.2  # how much every foot rises off the heap per metre it runs: over the next row
SHADE = 0.3  # how much light reaches the socks deep in the heap, between those of the weave
RIM_OVER = 0.05  # how far the rim rises over the giant's folded legs: a look from above the
# lanes, over the rim, meets socks, not knees


@dataclass(frozen=True)
class Heap:
    """The heap's cross-section, sampled by arc length v from inside its inner foot, over its crest
    and out along the floor past its outer foot: radius, height and outward normal at each v."""

    v: np.ndarray
    radius: np.ndarray
    height: np.ndarray
    normal: np.ndarray
    inner_foot: float
    crest: float
    foot: float

    def at(self, v: float) -> tuple[float, float, float, float]:
        radius, height, nr, nz = (
            float(np.interp(v, self.v, values))
            for values in (self.radius, self.height, *self.normal.T)
        )
        length = hypot(nr, nz)
        return radius, height, nr / length, nz / length


def heap(inner: float, rim: float) -> Heap:
    """The mound under the weave: the socks lying on its crest reach the rim, its inner foot is half
    a sock's width outside the giant's footprint."""
    top = rim - 2 * FLAT * RADIUS
    crest = inner + RADIUS + INSIDE * rim
    x = np.linspace(-1.8, 1.8, 181)
    radius = crest + np.where(x < 0, INSIDE, OUTSIDE) * rim * x
    height = top * np.cos(pi / 2 * np.clip(x, -1, 1)) ** 2
    d_radius, d_height = np.gradient(radius), np.gradient(height)
    v = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(radius), np.diff(height)))])
    normal = np.stack([-d_height, d_radius], 1)
    inner_foot, crest, foot = (float(np.interp(at, x, v)) for at in (-1, 0, 1))
    return Heap(v, radius, height, normal, inner_foot, crest, foot)


def heap_soup(ground: Heap, rng: random.Random, sides: int = 16, rings: int = 8) -> Soup:
    """The heap as a lathe sunk a little under the socks, each of its vertices a sock's colour in
    SHADE, blending across its faces: what shows between the weave's socks is more socks, deeper
    in the dark."""
    soup, shades = Soup(), []
    for v in np.linspace(ground.inner_foot, ground.foot, rings):
        radius, height, nr, nz = ground.at(v)
        radius, height = radius - 0.3 * RADIUS * nr, height - 0.3 * RADIUS * nz
        for j in range(sides):
            angle = tau * j / sides
            soup.verts.append(Vector((radius * cos(angle), radius * sin(angle), height)))
            shades.append((*(c * SHADE for c in srgb(rng.choice(list(PALETTE.values())))[:3]), 1.0))
    for k in range(rings - 1):
        for j in range(sides):
            a, b = k * sides + j, k * sides + (j + 1) % sides
            quad = (a, a + sides, b + sides, b)
            soup.face(quad, [shades[i] for i in quad])
    return soup


def rim_height(seated: Measure) -> float:
    return GIANT_SCALE * (seated.legs - seated.lo.z) + RIM_OVER


def nest(measure: Measure, material: bpy.types.Material, rng: random.Random) -> bpy.types.Object:
    """Socks woven over a heap in rows, from its crest down to its foot. Along each row its socks
    lie end to end, their feet hanging over the next row or, on the crest, some toes up; a few
    more lie across the rows above the two lowest, over them. Each is a random model, turned a
    little but on the bottom row, either side up. As many socks as the triangle budget carries,
    in as many rows as they fill end to end, shared between the rows by their length."""
    inner = GIANT_SCALE * measure.footprint * FOOTPRINT_MARGIN
    rim = rim_height(measure)
    ground = heap(inner, rim)
    soup = heap_soup(ground, rng)
    costs = [sock_soup(s, COARSE).triangles for s in SOCKS]
    models, spent = [], soup.triangles
    for pick in dealt(rng):
        if spent + costs[pick] > NEST_TRIANGLES:
            break
        models.append(pick)
        spent += costs[pick]
    first, last = ground.crest - RADIUS, ground.foot - RADIUS
    mean = tau * (ground.at((first + last) / 2)[0] + RADIUS)
    reach = (1 - ACROSS) * sum(span(SOCKS[m])[1] for m in models)
    rows = np.linspace(first, last, max(2, round(reach / mean)))
    lengths = [ground.at(v)[0] for v in rows]
    counts = [round(len(models) * length / sum(lengths)) for length in lengths]
    counts[-1] = len(models) - sum(counts[:-1])
    for row, (v, n) in enumerate(zip(rows, counts)):
        bottom = row == len(rows) - 1
        low = row >= len(rows) - 2
        laid = [(SOCKS[models.pop()], not low and rng.random() < ACROSS) for _ in range(n)]
        across = [model for model, over in laid if over]
        along = [model for model, over in laid if not over]
        rho = ground.at(v)[0] + RADIUS
        spans = [span(m)[1] for m in along]
        gap = (tau * rho - sum(spans)) / len(along)
        angle = rng.uniform(0, tau)
        for model, extent in zip(along, spans):
            angle += (extent + gap) / 2 / rho
            place = draped(ground, model, v, angle, rng, crest=row == 0, climb=bottom)
            soup.add(sock_soup(model, COARSE, place))
            angle += (extent + gap) / 2 / rho
        for model in across:
            place = draped(ground, model, v, rng.uniform(0, tau), rng, across=True)
            soup.add(sock_soup(model, COARSE, place))
    # A sock pressed on the floor lies flat on it rather than through it.
    for vert in soup.verts:
        vert.z = max(vert.z, 0.0)
    woven = mesh_object("nest", soup, material)
    woven["socks"], woven["rows"] = sum(counts), len(rows)
    return woven


def dealt(rng: random.Random):
    """The sock models in rounds, each a shuffle of all of them: as many of each, and neighbours
    unlike."""
    while True:
        yield from rng.sample(range(len(SOCKS)), len(SOCKS))


def draped(ground: Heap, model: Sock, v: float, angle: float, rng, *, across=False, crest=False,
           climb=False):
    """place(a, b) for a sock of the weave: the middle of its reach on the heap at row v and
    angle, laid along the row or across it, turned a little and either side up, lying on the heap;
    across, it lies over the socks along the row. Its foot hangs down the heap or, on the bottom
    row (climb), lies straight along it and climbs it; the foot rises as it runs, DRAPE per
    metre, to lie over the next row rather than through it; on the crest's row some rise more,
    toes up."""
    turn = 0.0
    if not climb:
        turn = rng.uniform(-0.2, 0.2) + (rng.choice((-pi / 2, pi / 2)) if across else 0.0)
    side = -1 if climb else 1 if rng.random() < FEET_DOWN else -1
    lift = DRAPE + (rng.uniform(0.2, 0.5) if crest and rng.random() < TOES_UP else 0.0)
    rise = RADIUS * (FLAT + (rng.uniform(0.9, 1.3) if across else rng.uniform(0.0, 0.3)))
    middle = span(model)[0]

    def place(a: float, b: float) -> tuple[Vector, Vector]:
        da, db = a - middle, side * b
        radius, height, nr, nz = ground.at(v + da * sin(turn) + db * cos(turn))
        off = rise + lift * max(0.0, b)
        rho = radius + nr * off
        theta = angle + (da * cos(turn) - db * sin(turn)) / rho
        out = Vector((cos(theta), sin(theta), 0.0))
        return out * rho + Vector((0, 0, height + nz * off)), out * nr + Vector((0, 0, nz))

    return place


def export(objects: list[bpy.types.Object], path: Path):
    """A GLB of these objects alone: Y up, modifiers applied, vertex colours, their one material,
    no animation. Each node bears its object's name, which is its mesh's. Linked duplicates of one
    mesh under one empty become one node drawing it at each of them (EXT_mesh_gpu_instancing)."""
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_animations=False,
        export_materials="EXPORT",
        export_vertex_color="MATERIAL",
        export_gpu_instances=True,
    )


# The playground round the race, at the microducks' scale: a racer stands 0.27 m and the seated
# giant 0.93 m, and nothing here stands taller. A yard under everything, its top YARD_TOP_M under
# the site's course ground, over YARD_X along the track and YARD_Y either side of it, in slabs no
# longer than SLAB_M: concrete, and the park's grass from GRASS_PAST_M past the nest's far edge.
# Behind each side's crowd, SIDE_OUT_M out from the lanes' edge and over SIDE_X along the track,
# the school on the left and a wooden fence on the right.
YARD_TOP_M = -0.003
YARD_X, YARD_Y = (-6.0, 20.0), 14.0
SLAB_M = 1.0
GRASS_PAST_M = 1.2
SIDE_OUT_M = 1.1
SIDE_X = (-1.0, 8.0)
PAINT = {
    "concrete": "#a9a8a3",
    "grass": "#63a548",
    "brick": "#b5583b",
    "trim": "#eee6d4",
    "roof": "#535962",
    "glass": "#45667f",
    "door": "#2a9d8f",
    "board": "#24456b",
    "ink": "#2b2d33",
    "wood": "#b97c45",
    "bark": "#6e4b30",
    "leaves": "#4f9c3d",
    "needles": "#2f7046",
}
# A side's crowd, as along a street race: ragged rows CROWD_ROWS metres out from the lanes' edge,
# from just behind the start line to the end of the sock field. Along the front row a duck every
# CROWD_STEP metres, each row behind CROWD_THIN times sparser, and after a duck, at CROWD_BREAK[0]
# odds, a gap of CROWD_BREAK[1] metres. Each duck is shifted across its row by up to CROWD_SHIFT_M,
# never nearer another than CROWD_GAP_M, and turned by up to CROWD_TURN either way from facing the
# track.
CROWD_ROWS = (0.13, 0.32, 0.51, 0.7, 0.88)
CROWD_X = (-0.2, LENGTH_M + SOCK_FIELD[1])
CROWD_STEP = (0.18, 0.26)
CROWD_THIN = 1.1
CROWD_BREAK = (0.1, (0.3, 0.7))
CROWD_SHIFT_M = 0.03
CROWD_GAP_M = 0.17
CROWD_TURN = 0.35
# The school: one storey for microducks, SCHOOL_DEPTH_M deep, its walls WALL_M high under a gable
# roof ROOF_M thick to RIDGE_M, overhanging them by EAVES_M. Front and back, a classroom's window
# every CLASSROOM_M: WINDOW (width, height, sill) in PANES panes under a transom. On the front, at
# DOOR_X along the track, an entrance porch PORCH (width, depth out of the front, ridge) with a
# gable of its own to the track: a double door a microduck fits through, DOOR (width, height), a
# board over it and a clock CLOCK_M wide in the gable.
SCHOOL_DEPTH_M = 0.7
WALL_M, RIDGE_M, ROOF_M, EAVES_M = 0.5, 0.68, 0.02, 0.05
CLASSROOM_M = 1.0
WINDOW = (0.6, 0.24, 0.13)
PANES = 3
DOOR_X = 3.5
PORCH = (0.56, 0.1, 0.66)
DOOR = (0.22, 0.35)
CLOCK_M = 0.09
# The fence: panels PANEL_M long of PLANKS upright planks, PLANK_M high, on two rails behind them.
PANEL_M = 0.6
PLANKS = 6
PLANK_M = 0.4
# The park: TREES trees of three models in turn, each scaled down to TREE_SCALE of its model at
# most, no two nearer than TREE_GAP_M, on the grass up to PARK_X along the track and PARK_Y either
# side of it; the first NEAR_TREES within NEAR_Y of the centre line, behind the giant.
TREES = 30
TREE_SCALE = 0.85
TREE_GAP_M = 0.7
PARK_X, PARK_Y = 14.0, 8.0
NEAR_TREES, NEAR_Y = 4, 1.5


def tint(paint: str, rng: random.Random, spread: float = 0.03) -> tuple[float, ...]:
    """A paint a little lighter or darker at random: a slab, a plank or a leaf unlike the next."""
    factor = rng.uniform(1 - spread, 1 + spread)
    return (*(min(1.0, c * factor) for c in srgb(PAINT[paint])[:3]), 1.0)


def prism(soup: Soup, outline: list[Vector], depth: Vector, colour: tuple[float, ...]):
    """A faceted solid: the convex outline, counter-clockwise seen from where depth points, swept
    along depth."""
    far = [p + depth for p in outline]
    for k in range(len(outline)):
        soup.polygon([outline[k - 1], outline[k], far[k], far[k - 1]], colour)
    soup.polygon(outline[::-1], colour)
    soup.polygon(far, colour)


def box(soup: Soup, lo, hi, colour: tuple[float, ...]):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    outline = [Vector((x, y, z0)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    prism(soup, outline, Vector((0, 0, z1 - z0)), colour)


def cuts(start: float, end: float) -> list[float]:
    """From start to end in equal steps no longer than SLAB_M."""
    n = ceil((end - start) / SLAB_M)
    return [start + (end - start) * k / n for k in range(n + 1)]


def yard(material: bpy.types.Material, grass_from: float, rng) -> bpy.types.Object:
    """The ground under everything: concrete slabs up to grass_from, each its own grey, and the
    park's grass on past it, in patches of green."""
    soup = Soup()
    for x0, x1 in pairwise([*cuts(YARD_X[0], grass_from)[:-1], *cuts(grass_from, YARD_X[1])]):
        ground = "concrete" if x1 <= grass_from else "grass"
        for y0, y1 in pairwise(cuts(-YARD_Y, YARD_Y)):
            corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
            soup.polygon([Vector((x, y, YARD_TOP_M)) for x, y in corners], tint(ground, rng))
    return mesh_object("yard", soup, material)


def around(centre: float, half: float) -> tuple[float, float]:
    return centre - half, centre + half


def plaque(soup: Soup, wall: float, out: int, stand: float, x, z, colour: tuple[float, ...]):
    """A box on the wall at y = wall, over x = (lo, hi) along it and z = (lo, hi) up it, standing
    stand off it towards out (+1 or -1 along y): a frame, a pane, a sill, a door, a board."""
    lo, hi = sorted((wall - out * 0.002, wall + out * stand))
    box(soup, (x[0], lo, z[0]), (x[1], hi, z[1]), colour)


def gabled(soup: Soup, place, across, ridge: float, length: float, wall, roof):
    """A block under a gable roof: its cross-section across = (lo, hi), walls WALL_M high and a
    gable to ridge, swept length along; and two roof slabs ROOF_M thick on it, overhanging it by
    EAVES_M all round. place(u, z, s) puts the cross-section's point (u, z) in the world, s along
    the sweep, the cross-section counter-clockwise seen from where the sweep goes."""
    lo, hi = across
    middle = (lo + hi) / 2
    sweep = place(0, 0, length) - place(0, 0, 0)
    house = ((lo, 0), (hi, 0), (hi, WALL_M), (middle, ridge), (lo, WALL_M))
    prism(soup, [place(u, z, 0) for u, z in house], sweep, wall)
    eave = WALL_M - EAVES_M * (ridge - WALL_M) / (middle - lo)
    low, top, high = (lo - EAVES_M, eave), (middle, ridge), (hi + EAVES_M, eave)
    for a, b in ((low, top), (top, high)):
        slope = (a, b, (b[0], b[1] + ROOF_M), (a[0], a[1] + ROOF_M))
        outline = [place(u, z, -EAVES_M) for u, z in slope]
        prism(soup, outline, sweep * (1 + 2 * EAVES_M / length), roof)


def window(soup: Soup, x: float, wall: float, out: int, trim, glass):
    """A classroom's window centred at x on the wall at y = wall, facing out: a white frame
    standing off the wall, its glass in PANES panes under a transom, and a sill."""
    width, height, sill = WINDOW
    pane = (sill + 0.016, sill + height - 0.016)
    inside = around(x, width / 2 - 0.016)
    plaque(soup, wall, out, 0.008, around(x, width / 2), (sill, sill + height), trim)
    plaque(soup, wall, out, 0.011, inside, pane, glass)
    for k in range(1, PANES):
        mullion = around(x - width / 2 + width * k / PANES, 0.005)
        plaque(soup, wall, out, 0.013, mullion, pane, trim)
    plaque(soup, wall, out, 0.013, inside, around(sill + 0.7 * height, 0.005), trim)
    plaque(soup, wall, out, 0.02, around(x, width / 2 + 0.012), (sill - 0.012, sill), trim)


def clock(soup: Soup, x: float, wall: float, z: float, face, ink):
    """A round clock CLOCK_M wide centred at (x, z) on the wall at y = wall, facing -y: a dark rim
    round a white face, and its hands at three o'clock."""
    for radius, stand, colour in ((CLOCK_M / 2, 0.008, ink), (CLOCK_M / 2 - 0.007, 0.011, face)):
        rim = [
            Vector((x + radius * cos(tau * k / 12), wall + 0.002, z + radius * sin(tau * k / 12)))
            for k in range(12)
        ]
        prism(soup, rim, Vector((0, -stand - 0.002, 0)), colour)
    plaque(soup, wall, -1, 0.014, around(x, 0.003), (z, z + 0.03), ink)
    plaque(soup, wall, -1, 0.014, (x, x + 0.022), around(z, 0.003), ink)


def school(material: bpy.types.Material) -> bpy.types.Object:
    """The school, in the left side's frame (+y away from the track): its front SIDE_OUT_M out from
    the lanes' edge, over SIDE_X. Brick walls on a cream plinth under a slate roof, a classroom's
    window every CLASSROOM_M front and back, and on the front the entrance porch, its ridge running
    back into the main roof: a teal double door, a board over it and a clock in its gable."""
    soup = Soup()
    paint = {name: srgb(code) for name, code in PAINT.items()}
    (x0, x1), y0 = SIDE_X, SIDE_OUT_M
    y1 = y0 + SCHOOL_DEPTH_M
    width, out, ridge = PORCH
    porch, front = around(DOOR_X, width / 2), y0 - out
    back = y0 + (ridge - WALL_M) / (RIDGE_M - WALL_M) * SCHOOL_DEPTH_M / 2
    brick, roof, trim = paint["brick"], paint["roof"], paint["trim"]
    box(soup, (x0 - 0.008, y0 - 0.008, 0), (x1 + 0.008, y1 + 0.008, 0.05), trim)
    box(soup, (porch[0] - 0.008, front - 0.008, 0), (porch[1] + 0.008, y0, 0.05), trim)
    gabled(soup, lambda u, z, s: Vector((x0 + s, u, z)), (y0, y1), RIDGE_M, x1 - x0, brick, roof)
    gabled(soup, lambda u, z, s: Vector((u, back - s, z)), porch, ridge, back - front, brick, roof)
    for k in range(round((x1 - x0) / CLASSROOM_M)):
        x = x0 + (k + 0.5) * CLASSROOM_M
        for wall, side in ((y0, -1), (y1, 1)):
            if side > 0 or abs(x - DOOR_X) >= (width + WINDOW[0]) / 2:
                window(soup, x, wall, side, trim, paint["glass"])
    half, door_height = DOOR[0] / 2, DOOR[1]
    plaque(soup, front, -1, 0.008, around(DOOR_X, half + 0.018), (0, door_height + 0.018), trim)
    for leaf in ((DOOR_X - half, DOOR_X - 0.003), (DOOR_X + 0.003, DOOR_X + half)):
        plaque(soup, front, -1, 0.012, leaf, (0, door_height), paint["door"])
    board = (door_height + 0.04, door_height + 0.1)
    plaque(soup, front, -1, 0.01, around(DOOR_X, 0.17), board, paint["board"])
    clock(soup, DOOR_X, front, (WALL_M + ridge) / 2 + 0.002, trim, paint["ink"])
    return mesh_object("school", soup, material)


def fence_panel(material: bpy.types.Material, rng) -> bpy.types.Object:
    """A panel of the fence, its origin on the ground at its start on the fence's line, the track
    towards +y: PLANKS upright planks, each its own shade of the wood, on two darker rails behind
    them."""
    soup = Soup()
    width = PANEL_M / PLANKS
    for k in range(PLANKS):
        lo, hi = (k * width + 0.006, -0.012, 0), ((k + 1) * width - 0.006, 0, PLANK_M)
        box(soup, lo, hi, tint("wood", rng, 0.12))
    rail = (*(c * 0.75 for c in srgb(PAINT["wood"])[:3]), 1.0)
    for z in (0.06, 0.28):
        box(soup, (0, -0.026, z), (PANEL_M, -0.012, z + 0.03), rail)
    return mesh_object("fence_panel", soup, material)


def trunk(soup: Soup, height: float, radius: float, rng):
    ring = [Vector((radius * cos(tau * k / 6), radius * sin(tau * k / 6), 0)) for k in range(6)]
    prism(soup, ring, Vector((0, 0, height)), tint("bark", rng))


def crown(soup: Soup, centre, radii, rng, sides: int = 8, rings: int = 5):
    """A lump of leaves: a sphere of these radii round centre, sides round and rings from top to
    bottom, each vertex pushed in or out a little at random and each facet its own green."""
    middle = Vector(centre)
    top, bottom = middle + Vector((0, 0, radii[2])), middle - Vector((0, 0, radii[2]))
    bands = [
        [
            middle + Vector((
                radii[0] * sin(pi * i / rings) * cos(tau * j / sides),
                radii[1] * sin(pi * i / rings) * sin(tau * j / sides),
                radii[2] * cos(pi * i / rings),
            )) * rng.uniform(0.9, 1.1)
            for j in range(sides)
        ]
        for i in range(1, rings)
    ]
    for j in range(sides):
        soup.polygon([top, bands[0][j - 1], bands[0][j]], tint("leaves", rng, 0.12))
        for upper, lower in pairwise(bands):
            quad = [upper[j - 1], lower[j - 1], lower[j], upper[j]]
            soup.polygon(quad, tint("leaves", rng, 0.12))
        soup.polygon([bottom, bands[-1][j], bands[-1][j - 1]], tint("leaves", rng, 0.12))


def cone(soup: Soup, base: float, radius: float, height: float, rng, sides: int = 8):
    """A tier of a pine's needles: a cone on a ring of sides round its foot, each facet its own
    green."""
    ring = [
        Vector((radius * cos(tau * k / sides), radius * sin(tau * k / sides), base))
        for k in range(sides)
    ]
    apex = Vector((0, 0, base + height))
    for k in range(sides):
        soup.polygon([ring[k - 1], ring[k], apex], tint("needles", rng, 0.12))
    soup.polygon(ring[::-1], tint("needles", rng, 0.12))


def oak(rng) -> Soup:
    """A broad tree, 0.8 m: three lumps of leaves on a trunk."""
    soup = Soup()
    trunk(soup, 0.34, 0.03, rng)
    lumps = (((0, 0, 0.58), 0.21), ((0.12, 0.07, 0.47), 0.15), ((-0.11, -0.06, 0.49), 0.16))
    for centre, radius in lumps:
        crown(soup, centre, (radius,) * 3, rng)
    return soup


def pine(rng) -> Soup:
    """A pine, 0.88 m: three tiers of needles on a short trunk."""
    soup = Soup()
    trunk(soup, 0.14, 0.03, rng)
    for base, radius, height in ((0.1, 0.22, 0.34), (0.3, 0.17, 0.32), (0.5, 0.12, 0.38)):
        cone(soup, base, radius, height, rng)
    return soup


def poplar(rng) -> Soup:
    """A slim tree, 0.75 m: one tall lump of leaves on a trunk."""
    soup = Soup()
    trunk(soup, 0.2, 0.025, rng)
    crown(soup, (0, 0, 0.46), (0.12, 0.12, 0.27), rng, rings=6)
    return soup


def scatter(model: bpy.types.Object, holder: bpy.types.Object, placements):
    """The model at each (location, turn about z, scale) under holder: linked duplicates of one
    mesh, which export writes once and instances."""
    for k, (location, turn, scale) in enumerate(placements):
        copy = model if k == 0 else link(bpy.data.objects.new(model.name, model.data))
        copy.parent = holder
        copy.location, copy.rotation_euler, copy.scale = location, (0, 0, turn), (scale,) * 3


def park(material: bpy.types.Material, grass_from: float, rng) -> bpy.types.Object:
    """The park's trees on the grass, the three models in turn, each turned at random and scaled
    down a little."""
    holder = link(bpy.data.objects.new("park", None))
    models = [mesh_object(grow.__name__, grow(rng), material) for grow in (oak, pine, poplar)]
    placed = []
    while len(placed) < TREES:
        across = NEAR_Y if len(placed) < NEAR_TREES else PARK_Y
        here = (rng.uniform(grass_from + TREE_GAP_M / 2, PARK_X), rng.uniform(-across, across))
        if all(dist(here, there) >= TREE_GAP_M for there in placed):
            placed.append(here)
    for k, model in enumerate(models):
        trees = placed[k :: len(models)]
        turns = [(rng.uniform(0, tau), rng.uniform(TREE_SCALE, 1.0)) for _ in trees]
        scatter(model, holder, [((x, y, 0), *turn) for (x, y), turn in zip(trees, turns)])
    return holder


def crowd(rng) -> list[tuple[float, float, float]]:
    """Where a side's crowd sits: (along the track, out from the lanes' edge, turn from facing the
    track), row by row from the front."""
    placed = []
    for row, out in enumerate(CROWD_ROWS):
        x = CROWD_X[0] + rng.uniform(0, CROWD_STEP[0])
        while x <= CROWD_X[1]:
            here = (x, out + rng.uniform(-CROWD_SHIFT_M, CROWD_SHIFT_M))
            if all(dist(here, (a, b)) >= CROWD_GAP_M for a, b, _ in placed):
                placed.append((*here, rng.uniform(-CROWD_TURN, CROWD_TURN)))
            x += rng.uniform(*CROWD_STEP) * CROWD_THIN**row
            if rng.random() < CROWD_BREAK[0]:
                x += rng.uniform(*CROWD_BREAK[1])
    return placed


def playground(material: bpy.types.Material, nest_object) -> dict[str, bpy.types.Object]:
    """The playground round the race, its origin on the start line at the lanes' centre line, as
    four nodes: the yard; left, the school and its crowd's spots, and right, the fence and its
    crowd's spots, each built out from the lanes' edge (+y on the left, -y on the right, in
    Blender) for the site to stand at the edge of the lanes it draws; and the park. A spot is an
    empty, spot_<k>, turned about z from +x to face the track. Everything random is drawn from
    random.Random(1), which leaves the nest's and the socks' draws as they were."""
    rng = random.Random(1)
    far_edge = max(corner[0] for corner in nest_object.bound_box)
    grass_from = LENGTH_M + GIANT_BEHIND_M + far_edge + GRASS_PAST_M
    nodes = {"yard": yard(material, grass_from, rng)}
    nodes |= {name: link(bpy.data.objects.new(name, None)) for name in ("left", "right")}
    school(material).parent = nodes["left"]
    fence = link(bpy.data.objects.new("fence", None))
    fence.parent = nodes["right"]
    panels = round((SIDE_X[1] - SIDE_X[0]) / PANEL_M)
    along = [((SIDE_X[0] + k * PANEL_M, -SIDE_OUT_M, 0), 0.0, 1.0) for k in range(panels)]
    scatter(fence_panel(material, rng), fence, along)
    number = count()
    for side, sign in ((nodes["left"], 1), (nodes["right"], -1)):
        for x, out, turn in crowd(rng):
            spot = link(bpy.data.objects.new(f"spot_{next(number)}", None))
            spot.parent = side
            spot.location = (x, sign * out, 0)
            spot.rotation_euler = (0, 0, -sign * pi / 2 + turn)
    nodes["park"] = park(material, grass_from, rng)
    return nodes


def spots(side: bpy.types.Object) -> list[bpy.types.Object]:
    return [child for child in side.children if child.name.startswith("spot_")]


def laid_out(grounds: dict[str, bpy.types.Object]) -> list[bpy.types.Object]:
    """The playground's four nodes and everything under them."""
    return [obj for node in grounds.values() for obj in (node, *node.children_recursive)]


def aim(camera: bpy.types.Object, location, target, fov: float):
    camera.location = location
    camera.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    camera.data.sensor_fit = "VERTICAL"
    camera.data.angle_y = radians(fov)


def render(out: Path, seated: Measure, nest_object, socks: list[bpy.types.Object], grounds, rng):
    """The venue, Eevee at 1600 x 900. First on a grey floor, without the playground: chase.png
    from the race camera behind the start line, nest-three-quarter.png, close.png on the rim, and
    turned.png with the head round. Then in the playground, laid as the site lays it on four lanes,
    a duck of the crowd sitting on each spot: page.png from the same race camera,
    three-quarter.png over the whole playground from behind and left of the start, crowd.png low
    on the right side's crowd before the fence, and park.png from past the nest, back down the
    track over the giant."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    scene.eevee.taa_render_samples = 64
    world = bpy.data.worlds.new("sky")
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.68, 0.75, 1)
    scene.world = world
    sun = link(bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")))
    sun.data.energy = 3.5
    sun.data.angle = radians(8)
    sun.rotation_euler = (radians(50), 0, radians(-35))

    floor = plane((0.22, 0.22, 0.23), (4, 0, 0), (30, 20))
    for x in (0.0, LENGTH_M):
        plane((0.9, 0.9, 0.9), (x, 0, 0.001), (0.05, 2 * EDGE_M))

    centre = Vector((LENGTH_M + GIANT_BEHIND_M, 0, 0))
    nest_object.location = centre
    giants = {}
    for name, angles in (("still", sitting()), ("turned", sitting() | {"head_yaw": head_turned()})):
        giant = racer(angles)
        giant.location = centre - Vector((0, 0, GIANT_SCALE * seated.lo.z))
        giant.scale = (GIANT_SCALE,) * 3
        giants[name] = giant
    for y in LANES:
        racer(STAND).location = (0, y, 0)
    for obj in socks:
        obj.hide_render = True
    reach = min(LENGTH_M + SOCK_FIELD[1], centre.x - nest_object.dimensions.x / 2 - 0.05)
    for k in range(round(SOCKS_PER_M * 2 * EDGE_M)):
        loose = link(bpy.data.objects.new(f"loose_{k}", socks[k % len(socks)].data))
        x, y = rng.uniform(LENGTH_M + SOCK_FIELD[0], reach), rng.uniform(-EDGE_M, EDGE_M)
        loose.location = (x, y, 0)
        loose.rotation_euler = (0, 0, rng.uniform(0, tau))

    camera = link(bpy.data.objects.new("camera", bpy.data.cameras.new("camera")))
    scene.camera = camera
    wide = tan(radians(CHASE_FOV) / 2) * 16 / 9
    distance = max(1.0, (max(LANES) + PACK_MARGIN_M) / wide / CHASE_BACK_M)
    chase = Vector((-CHASE_BACK_M, -CHASE_SIDE_M, CHASE_HEIGHT_M)) * distance
    start = (0, 0, CHASE_TARGET_M)
    giant_middle = centre + Vector((0, 0, GIANT_SCALE * (seated.hi.z - seated.lo.z) / 2))

    def shoot(views: dict):
        for name, (location, target, fov) in views.items():
            for pose, giant in giants.items():
                for part in [giant, *giant.children_recursive]:
                    part.hide_render = (pose == "turned") != (name == "turned")
            aim(camera, location, target, fov)
            scene.render.filepath = str(out / f"{name}.png")
            bpy.ops.render.render(write_still=True)

    for obj in laid_out(grounds):
        obj.hide_render = True
    shoot({
        "chase": (chase, start, CHASE_FOV),
        "nest-three-quarter": (
            centre + Vector((-2.6, -2.2, 1.3)), centre + Vector((0, 0, 0.4)), 38
        ),
        "close": (centre + Vector((-1.45, -1.0, 0.7)), centre + Vector((-0.5, -0.3, 0.3)), 40),
        "turned": (centre + Vector((-3.3, -1.2, 0.85)), giant_middle, 32),
    })

    # The playground under the site's sky, untoned, as the site draws it.
    world.node_tree.nodes["Background"].inputs["Color"].default_value = linear(SKY)
    scene.view_settings.view_transform = "Standard"
    floor.hide_render = True
    for obj in laid_out(grounds):
        obj.hide_render = False
    grounds["left"].location.y, grounds["right"].location.y = EDGE_M, -EDGE_M
    for k, spot in enumerate(spots(grounds["left"]) + spots(grounds["right"])):
        duck = racer(SIT, CROWD_MODEL, SHELLS[k % len(SHELLS)])
        duck.parent = spot
        duck.location.z = SIT_TRUNK_M - rig_trunk()
    shoot({
        "page": (chase, start, CHASE_FOV),
        "three-quarter": ((-4.0, 7.5, 5.5), (4.5, 0, 0), 50),
        "crowd": ((1.2, -0.7, 0.3), (2.8, -EDGE_M - 0.6, 0.12), 45),
        "park": ((PARK_X + 0.5, -2.0, 2.2), (4.5, 0.3, 0.15), 50),
    })


def plane(colour, centre, size) -> bpy.types.Object:
    """A flat rectangle on the floor, in one plain colour: the floor itself, or a line on it."""
    material = bpy.data.materials.new("plane")
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*colour, 1)
    w, d = size[0] / 2, size[1] / 2
    mesh = bpy.data.meshes.new("plane")
    mesh.from_pydata([(-w, -d, 0), (w, -d, 0), (w, d, 0), (-w, d, 0)], [], [(0, 1, 2, 3)])
    mesh.materials.append(material)
    flat = link(bpy.data.objects.new("plane", mesh))
    flat.location = centre
    return flat


def main():
    parser = argparse.ArgumentParser(prog="sock_heist_venue.py")
    parser.add_argument("out", type=Path)
    parser.add_argument("--render", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(0)
    standing, seated = racer_box(STAND), racer_box(sitting())
    material = venue_material()
    socks = [sock(k, material) for k in range(len(SOCKS))]
    nest_object = nest(seated, material, rng)
    args.out.mkdir(parents=True, exist_ok=True)
    export([nest_object], args.out / "sock-nest.glb")
    export(socks, args.out / "socks.glb")

    width, height, depth = standing.size
    print(f"racer at STAND: {width:.3f} x {height:.3f} x {depth:.3f} m")
    print("giant sitting:", {name: round(angle, 6) + 0.0 for name, angle in sitting().items()})
    width, height, depth = seated.size
    print(
        f"giant seated: {GIANT_SCALE * height:.3f} m tall, {GIANT_SCALE * width:.3f} x "
        f"{GIANT_SCALE * depth:.3f} m, trunk at {seated.trunk:.4f} m on a racer, "
        f"{GIANT_SCALE * seated.trunk:.3f} m on the giant, legs below "
        f"{GIANT_SCALE * (seated.legs - seated.lo.z):.3f} m"
    )
    lo, hi = Vector(nest_object.bound_box[0]), Vector(nest_object.bound_box[6])
    inside = GIANT_SCALE * seated.footprint * FOOTPRINT_MARGIN
    print(
        f"nest: {nest_object['socks']} socks in {nest_object['rows']} rows, "
        f"{triangles(nest_object)} triangles, inside radius {inside:.3f} m, rim "
        f"{rim_height(seated):.3f} m, x {lo.x:.3f}..{hi.x:.3f}, "
        f"y {lo.y:.3f}..{hi.y:.3f}, up {lo.z:.3f}..{hi.z:.3f} m"
    )
    for obj in socks:
        x, y, z = obj.dimensions
        print(f"{obj.name}: {triangles(obj)} triangles, {x:.3f} x {y:.3f} x {z:.3f} m")

    grounds = playground(material, nest_object)
    laid = laid_out(grounds)
    export(laid, args.out / "playground.glb")
    drawn = 0
    for mesh in dict.fromkeys(obj.data for obj in laid if obj.type == "MESH"):
        users = [obj for obj in laid if obj.data == mesh]
        drawn += triangles(users[0]) * len(users)
        print(
            f"{mesh.name}: {triangles(users[0])} triangles, {len(users)} drawn, "
            f"{max(v.co.z for v in mesh.vertices):.3f} m tall"
        )
    left, right = (spots(grounds[side]) for side in ("left", "right"))
    print(
        f"playground: {drawn} triangles drawn, {len(left)} crowd spots on the left, "
        f"{len(right)} on the right"
    )
    if args.render:
        args.render.mkdir(parents=True, exist_ok=True)
        render(args.render, seated, nest_object, socks, grounds, rng)


def triangles(obj: bpy.types.Object) -> int:
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


main()
