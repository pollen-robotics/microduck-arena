// @vitest-environment node
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { Box3, Group, Matrix4, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { creasedGeometries } from "./rig.js";
import { DIVE_REACH_M, SOCKS_PER_M, SOCK_FIELD, buildGiant, diveAt, laySocks, loadHeistVenue } from "./giant.js";

const LENGTH = 6;
const EDGE = 1.9; // four lanes at 0.95 m
const duck = (giant) => giant.group.getObjectByName("duck_placer"); // the rig, not the nest and socks round it

/** A GLB of the app's public folder, parsed as the browser's loader would fetch it. */
function parse(path) {
  const bytes = readFileSync(path);
  return new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), "");
}

/** Where the giant's eye is, seen from its head's own pivot. */
function lensFromPivot(giant) {
  giant.group.updateMatrixWorld(true);
  const lens = new Box3().setFromObject(giant.group.getObjectByName("lens.stl")).getCenter(new Vector3());
  return lens.sub(giant.group.getObjectByName("yaw_roll_motion").getWorldPosition(new Vector3()));
}

describe("the giant", () => {
  let model;
  let venue;
  beforeAll(async () => {
    const kinematics = JSON.parse(readFileSync("public/robot/kinematics.json", "utf8"));
    model = { kinematics, geometries: creasedGeometries((await parse("public/robot/microduck.glb")).scene) };
    vi.spyOn(GLTFLoader.prototype, "loadAsync").mockImplementation((url) => parse(`public${url}`));
    venue = await loadHeistVenue();
  });
  afterEach(() => vi.restoreAllMocks());

  it("loads the nest, the sock models in name order and the playground's four nodes, once", async () => {
    expect(venue.nest.name).toBe("nest");
    expect(venue.socks.map((sock) => sock.name)).toEqual(["sock_0", "sock_1", "sock_2", "sock_3", "sock_4"]);
    const nodes = ["yard", "left", "right", "park"];
    expect(nodes.map((name) => venue.playground[name]?.name)).toEqual(nodes);
    expect(await loadHeistVenue()).toBe(venue);
  });

  it("sits centred behind the line, resting on the floor, as tall as the seated giant of the approved renders", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    // From the vertices, as the script measured it: the folded feet's turned bounding boxes reach
    // 13 mm under the floor they rest on.
    const box = new Box3().setFromObject(duck(giant), true);
    expect(box.min.x).toBeGreaterThan(LENGTH + 1);
    expect((box.min.z + box.max.z) / 2).toBeCloseTo(0, 1);
    expect(box.min.y).toBeCloseTo(0, 3);
    // scripts/sock_heist_venue.py printed 0.930 m, to the millimetre: the skin keeps every outer mesh.
    expect(box.max.y - box.min.y).toBeCloseTo(0.93, 3);
  });

  it("seats the giant in its nest, its feet in the weave, the sock field clear", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    const nest = new Box3().setFromObject(giant.group.getObjectByName("nest"));
    for (const ankle of ["ankle_left", "ankle_right"]) {
      expect(nest.containsPoint(giant.group.getObjectByName(ankle).getWorldPosition(new Vector3()))).toBe(true);
    }
    expect(nest.min.x).toBeGreaterThan(LENGTH + SOCK_FIELD[1]);
  });

  it("lays the socks between the line and the nest across every lane, the same every time", () => {
    const socks = laySocks(3, LENGTH, EDGE);
    expect(socks).toEqual(laySocks(3, LENGTH, EDGE));
    expect(socks).toHaveLength(Math.round(SOCKS_PER_M * 2 * EDGE));
    for (const { x, z } of socks) {
      expect(x).toBeGreaterThanOrEqual(LENGTH + SOCK_FIELD[0]);
      expect(x).toBeLessThanOrEqual(LENGTH + SOCK_FIELD[1]);
      expect(Math.abs(z)).toBeLessThanOrEqual(EDGE);
    }
    expect(new Set(socks.map((s) => s.kind))).toEqual(new Set([0, 1, 2]));
    for (const lane of [-1.425, -0.475, 0.475, 1.425]) {
      expect(socks.some((s) => Math.hypot(s.x - LENGTH, s.z - lane) <= DIVE_REACH_M)).toBe(true);
    }
  });

  it("draws each sock model once, instanced, as many as are laid", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    const instanced = [];
    giant.group.traverse((node) => { if (node.isInstancedMesh) instanced.push(node.count); });
    expect(instanced).toHaveLength(venue.socks.length);
    expect(instanced.reduce((a, b) => a + b)).toBe(laySocks(venue.socks.length, LENGTH, EDGE).length);
  });

  it("throws its instanced socks as diveAt says", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    const divers = [[LENGTH, 0.475]];
    giant.dive(divers, 0.2);
    const heights = [];
    const matrix = new Matrix4();
    giant.group.traverse((node) => {
      if (!node.isInstancedMesh) return;
      for (let i = 0; i < node.count; i += 1) {
        node.getMatrixAt(i, matrix);
        heights.push(new Vector3().setFromMatrixPosition(matrix).y);
      }
    });
    const flown = diveAt(laySocks(venue.socks.length, LENGTH, EDGE), divers, 0.2).map((pose) => pose.y);
    const sorted = (values) => [...values].sort((a, b) => a - b);
    expect(sorted(flown).some((y) => y > 0)).toBe(true);
    sorted(heights).forEach((y, k) => expect(y).toBeCloseTo(sorted(flown)[k], 5));
  });

  it("has its back to the lanes on green, and on red turns its head only, about half a turn over its shoulder by the camera's side", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    const trunk = () => giant.group.getObjectByName("trunk_base").matrixWorld.clone();
    giant.pose(0);
    const away = lensFromPivot(giant);
    const body = trunk();
    giant.pose(1);
    const round = lensFromPivot(giant);
    expect(away.x).toBeGreaterThan(0);
    expect(round.x).toBeLessThan(0);
    expect(round.z).toBeGreaterThan(0);
    const angle = Math.acos(away.setY(0).normalize().dot(round.setY(0).normalize()));
    expect(angle).toBeGreaterThan(2.8); // head_yaw's own limit, 170°
    expect(trunk().equals(body)).toBe(true);
  });

  it("draws only the duck's skin, and every mesh of it, its nest and its socks casts and catches shadows", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    expect(duck(giant).getObjectByName("speaker.stl")).toBeUndefined();
    giant.group.traverse((node) => { if (node.isMesh) expect([node.castShadow, node.receiveShadow]).toEqual([true, true]); });
  });

  it("frees its own materials and leaves the racers' shared geometries whole", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    const scene = new Group();
    scene.add(giant.group);
    const meshes = [];
    duck(giant).traverse((node) => { if (node.isMesh) meshes.push(node); });
    expect(meshes.length).toBeGreaterThan(0);
    const spies = meshes.map((mesh) => [vi.spyOn(mesh.geometry, "dispose"), vi.spyOn(mesh.material, "dispose")]);
    giant.dispose();
    expect(giant.group.parent).toBeNull();
    for (const [geometry, material] of spies) {
      expect(geometry).not.toHaveBeenCalled();
      expect(material).toHaveBeenCalledOnce();
    }
  });

  it("frees its socks' instances and leaves the venue's geometries and materials whole", () => {
    const giant = buildGiant(model, venue, LENGTH, EDGE);
    const instanced = [];
    giant.group.traverse((node) => { if (node.isInstancedMesh) instanced.push(vi.spyOn(node, "dispose")); });
    const shared = new Set([venue.nest, ...venue.socks].flatMap((mesh) => [mesh.geometry, mesh.material]));
    const spies = [...shared].map((resource) => vi.spyOn(resource, "dispose"));
    giant.dispose();
    for (const spy of instanced) expect(spy).toHaveBeenCalledOnce();
    for (const spy of spies) expect(spy).not.toHaveBeenCalled();
  });
});

describe("diveAt", () => {
  const socks = laySocks(3, 6, 1.9);
  const near = (s, z) => Math.hypot(s.x - 6, s.z - z) <= DIVE_REACH_M;
  const rest = socks.map(({ x, z, yaw }) => ({ x, y: 0, z, yaw, pitch: 0 }));
  it("leaves every sock where it was laid before the first duck crosses, and when none crossed", () => {
    expect(diveAt(socks, [[6, 0.475]], -0.1)).toEqual(rest);
    expect(diveAt(socks, [], 0.3)).toEqual(rest);
  });
  it("throws up the socks near the diver's lane, and only those", () => {
    const flown = diveAt(socks, [[6, 0.475]], 0.2);
    socks.forEach((s, k) => expect(flown[k].y > 0).toBe(near(s, 0.475)));
  });
  it("throws up the socks near both lanes when two ducks cross on the same frame", () => {
    const flown = diveAt(socks, [[6, -0.475], [6, 1.425]], 0.2);
    socks.forEach((s, k) => expect(flown[k].y > 0).toBe(near(s, -0.475) || near(s, 1.425)));
  });
  it("drops every sock back flat on the floor, where it stays", () => {
    const landed = diveAt(socks, [[6, 0.475]], 2);
    expect(landed.every((p) => p.y === 0 && p.pitch === 0)).toBe(true);
    expect(diveAt(socks, [[6, 0.475]], 5)).toEqual(landed);
  });
  it("is the same at the same moment, frame after frame", () => {
    expect(diveAt(socks, [[6, 0.475]], 0.31)).toEqual(diveAt(socks, [[6, 0.475]], 0.31));
  });
});
