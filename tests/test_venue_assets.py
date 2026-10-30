"""Sock Heist's venue models, as scripts/sock_heist_venue.py exports them: the giant's nest, the
loose socks on its floor and the playground round the race, read from each GLB's own JSON chunk."""

import json
import struct
from itertools import combinations
from math import atan2, dist, sin
from pathlib import Path

VENUE = Path(__file__).parent.parent / "app" / "public" / "venue"
PLAYGROUND = VENUE / "playground.glb"
GIANT_SEATED_M = 0.93  # the seated giant's height (scripts/sock_heist_venue.py prints it)


def gltf(path: Path) -> dict:
    """The GLB's JSON chunk: after the 12-byte header, the first chunk's length and type."""
    data = path.read_bytes()
    length, kind = struct.unpack("<II", data[12:20])
    assert kind == 0x4E4F534A  # "JSON"
    return json.loads(data[20 : 20 + length])


def mesh(doc: dict, name: str) -> dict:
    return next(m for m in doc["meshes"] if m["name"] == name)


def triangles(doc: dict, name: str) -> int:
    return sum(doc["accessors"][p["indices"]]["count"] // 3 for p in mesh(doc, name)["primitives"])


def bounds(doc: dict, name: str) -> tuple[list[float], list[float]]:
    primitives = mesh(doc, name)["primitives"]
    positions = [doc["accessors"][p["attributes"]["POSITION"]] for p in primitives]
    lo = [min(a["min"][k] for a in positions) for k in range(3)]
    hi = [max(a["max"][k] for a in positions) for k in range(3)]
    return lo, hi


def node(doc: dict, name: str) -> dict:
    return next(n for n in doc["nodes"] if n.get("name") == name)


def children(doc: dict, name: str) -> list[dict]:
    return [doc["nodes"][k] for k in node(doc, name).get("children", [])]


def yaw(spot: dict) -> float:
    """The turn about +y of a spot's rotation quaternion (x, y, z, w)."""
    _, y, _, w = spot.get("rotation", [0, 0, 0, 1])
    return 2 * atan2(y, w)


def drawn(doc: dict) -> int:
    """The triangles every node draws, an instanced node's mesh once per instance."""
    total = 0
    for n in doc["nodes"]:
        if "mesh" in n:
            copies = 1
            if instancing := n.get("extensions", {}).get("EXT_mesh_gpu_instancing"):
                copies = doc["accessors"][instancing["attributes"]["TRANSLATION"]]["count"]
            total += copies * triangles(doc, doc["meshes"][n["mesh"]]["name"])
    return total


def test_the_nest_is_one_mesh_named_nest():
    assert [m["name"] for m in gltf(VENUE / "sock-nest.glb")["meshes"]] == ["nest"]


def test_the_nest_keeps_its_triangle_budget():
    assert triangles(gltf(VENUE / "sock-nest.glb"), "nest") <= 6000


def test_the_socks_are_three_to_five_models_within_budget():
    names = [m["name"] for m in gltf(VENUE / "socks.glb")["meshes"]]
    assert 3 <= len(names) <= 5 and names == [f"sock_{k}" for k in range(len(names))]
    assert all(triangles(gltf(VENUE / "socks.glb"), name) <= 400 for name in names)


def test_the_nest_stands_on_the_floor():
    lo, hi = bounds(gltf(VENUE / "sock-nest.glb"), "nest")
    assert abs(lo[1]) < 0.01 and hi[1] - lo[1] < hi[0] - lo[0]  # on the floor, wider than tall


def test_every_venue_model_is_vertex_coloured():
    for name in ("sock-nest.glb", "socks.glb", "playground.glb"):
        meshes = gltf(VENUE / name)["meshes"]
        assert all("COLOR_0" in p["attributes"] for m in meshes for p in m["primitives"])


def test_the_playground_is_a_yard_two_sides_and_a_park():
    names = [
        n["name"]
        for n in gltf(PLAYGROUND)["nodes"]
        if n.get("name") in {"yard", "left", "right", "park"}
    ]
    assert sorted(names) == ["left", "park", "right", "yard"]


def test_each_side_carries_a_crowd_beyond_the_track_edge_facing_it():
    doc = gltf(PLAYGROUND)
    for side, sign in (("left", -1), ("right", 1)):
        assert "translation" not in node(doc, side)  # the site stands it at the lanes' edge
        spots = [n for n in children(doc, side) if n["name"].startswith("spot_")]
        assert 90 <= len(spots) <= 130
        for spot in spots:
            x, y, z = spot["translation"]
            assert sign * z >= 0.08 and y == 0 and -0.3 <= x <= 7.2
            assert sign * -sin(yaw(spot)) < 0  # its +x turned towards the track
        xz = [(s["translation"][0], s["translation"][2]) for s in spots]
        assert min(dist(a, b) for a, b in combinations(xz, 2)) >= 0.16


def test_nothing_in_the_playground_stands_taller_than_the_seated_giant():
    doc = gltf(PLAYGROUND)
    assert max(bounds(doc, m["name"])[1][1] for m in doc["meshes"]) <= GIANT_SEATED_M


def test_the_playground_instances_its_trees_and_keeps_its_budget():
    doc = gltf(PLAYGROUND)
    assert "EXT_mesh_gpu_instancing" in doc["extensionsUsed"]
    assert sum(triangles(doc, m["name"]) for m in doc["meshes"]) <= 20000  # each model once
    assert drawn(doc) <= 40000  # every instance counted
