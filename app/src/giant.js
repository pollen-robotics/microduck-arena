// Sock Heist's giant: the racers' own microduck, assembled from the same kinematics and meshes at
// GIANT_SCALE, sitting in its nest woven from socks past the finish line, its back to the lanes,
// loose socks lying on the floor between the line and the nest. Only its head moves: it turns
// round over its shoulder to the lanes on red and back on green, as lights.js lightAt's `facing`
// says. When the first duck crosses the line, the socks near its lane fly up and fall back. Both
// are pure functions of the replay's clock, and every spread is drawn from a fixed hash of the
// sock's index, so a clip's frames come out the same on every render.

import { Euler, Group, InstancedMesh, Matrix4, Quaternion, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { attachMeshes, buildRigTree, setJoint } from "./rig.js";

export const GIANT_SCALE = 4.5;
// How far past the finish line the giant and its nest sit, on the lanes' centre line: the least, to
// the 5 cm, that keeps the nest's lane-side edge, 0.992 m from its centre, past SOCK_FIELD's 0.95 m.
export const GIANT_BEHIND_M = 1.95;
// The giant's seat, as scripts/sock_heist_venue.py printed it for the renders the owner approved
// on 2026-10-29: every hip pitch and knee folded nearly to its end, the legs under the trunk, and
// the trunk this high over the floor on a racer, where the folded duck rests on it.
const SEATED = {
  left_hip_yaw: 0.0,
  left_hip_roll: -0.087266,
  left_hip_pitch: 1.492257,
  left_knee: 1.492257,
  left_ankle: 0.0,
  neck_pitch: 0.349066,
  head_pitch: 0.349066,
  head_yaw: 0.0,
  head_roll: 0.0,
  right_hip_yaw: 0.0,
  right_hip_roll: 0.087266,
  right_hip_pitch: -1.492257,
  right_knee: -1.492257,
  right_ankle: 0.0,
};
const SEATED_TRUNK_M = 0.0522;

// Where the loose socks lie, in metres past the finish line, and how many to a metre across the
// lanes.
export const SOCK_FIELD = [0.15, 0.95];
export const SOCKS_PER_M = 7;
// How near a diver's point a sock lies to fly, and how it flies: its lift and its spread along the
// floor in m/s, its whole turns end over end, and its spin round the vertical in rad/s.
export const DIVE_REACH_M = 0.8;
const LIFT = [2.8, 4.2];
const SPREAD = [0.4, 1.2];
const TURNS = [1, 2];
const SPIN = [-3, 3];
const GRAVITY = 9.81;

/** The `n`th draw of `k`, in [0, 1): the venue's fixed integer hash, for sock `k`'s throw and a seed's quacks, the same on every frame. */
export function draw(k, n) {
  let h = Math.imul(k + 1, 0x9e3779b1) ^ Math.imul(n + 1, 0x85ebca77);
  h = Math.imul(h ^ (h >>> 16), 0x7feb352d);
  h = Math.imul(h ^ (h >>> 15), 0x846ca68b);
  return ((h ^ (h >>> 16)) >>> 0) / 2 ** 32;
}

const within = ([lo, hi], u) => lo + (hi - lo) * u;

let venue = null;

/**
 * Plan B's nest and its sock models, `sock_0` first, and the playground the race is run in, its
 * four nodes by name (playground.js), fetched once.
 */
export function loadHeistVenue() {
  venue ??= Promise.all(["sock-nest", "socks", "playground"]
    .map((name) => new GLTFLoader().loadAsync(`/venue/${name}.glb`)))
    .then(([nest, socks, playground]) => ({
      nest: nest.scene.getObjectByName("nest"),
      socks: socks.scene.children
        .filter((node) => node.isMesh)
        .sort((a, b) => a.name.localeCompare(b.name, "en", { numeric: true })),
      playground: Object.fromEntries(["yard", "left", "right", "park"]
        .map((name) => [name, playground.scene.getObjectByName(name)])),
    }));
  return venue;
}

/**
 * The loose socks over a `length` metre race whose lanes reach `edge` either side of its centre
 * line: SOCKS_PER_M to the metre across them, sock k in its own slice of it, anywhere in
 * SOCK_FIELD along it, turned any way, a model of `kinds` each in turn.
 */
export function laySocks(kinds, length, edge) {
  const count = Math.round(SOCKS_PER_M * 2 * edge);
  return Array.from({ length: count }, (_, k) => ({
    kind: k % kinds,
    x: length + within(SOCK_FIELD, draw(k, 0)),
    z: -edge + (2 * edge * (k + draw(k, 1))) / count,
    yaw: 2 * Math.PI * draw(k, 2),
  }));
}

/**
 * Each of `socks` `seconds` after the first duck crossed the line at `divers`' points [x, z]: one
 * within DIVE_REACH_M of a diver flies from the nearest, up and away from it along the floor,
 * turning end over end, and lands flat; the rest lie as they were laid.
 */
export function diveAt(socks, divers, seconds) {
  return socks.map(({ x, z, yaw }, k) => {
    const rest = { x, y: 0, z, yaw, pitch: 0 };
    let from = null;
    let reach = DIVE_REACH_M;
    for (const diver of divers) {
      const d = Math.hypot(x - diver[0], z - diver[1]);
      if (d <= reach) [from, reach] = [diver, d];
    }
    if (!from || !(seconds > 0)) return rest;
    const lift = within(LIFT, draw(k, 3));
    const flight = (2 * lift) / GRAVITY;
    const t = Math.min(seconds, flight);
    const along = within(SPREAD, draw(k, 4)) * t;
    const [ux, uz] = reach > 0 ? [(x - from[0]) / reach, (z - from[1]) / reach] : [1, 0];
    const flying = t < flight;
    const turns = TURNS[Math.floor(draw(k, 5) * TURNS.length)];
    return {
      x: x + ux * along,
      y: flying ? lift * t - (GRAVITY * t * t) / 2 : 0,
      z: z + uz * along,
      yaw: yaw + within(SPIN, draw(k, 6)) * t,
      pitch: flying ? (2 * Math.PI * turns * t) / flight : 0,
    };
  });
}

const _matrix = new Matrix4();
const _position = new Vector3();
const _turn = new Quaternion();
const _euler = new Euler();
const _one = new Vector3(1, 1, 1);

/**
 * The giant over a `length` metre race whose lanes reach `edge` either side of its centre line,
 * from the racers' rig `model` ({ kinematics, geometries }), seated in `venue`'s nest
 * (loadHeistVenue), its loose socks before it. Drawn as its skin, sharing the racers' geometries,
 * the nest and the socks the venue's own: `dispose` frees only what it made.
 */
export function buildGiant({ kinematics, geometries }, { nest, socks }, length, edge) {
  const rig = buildRigTree(kinematics);
  attachMeshes(rig, kinematics, geometries, { livery: "classic", skin: true });
  // Unrotated, facing +x, away from the lanes.
  rig.bodies.get("trunk_base").position.set(0, 0, SEATED_TRUNK_M);
  for (const [name, angle] of Object.entries(SEATED)) setJoint(rig, name, angle);
  const centre = length + GIANT_BEHIND_M;
  rig.placer.position.set(centre, 0, 0);
  rig.placer.scale.setScalar(GIANT_SCALE);
  const woven = nest.clone();
  woven.position.set(centre, 0, 0);
  // One instanced mesh per sock model, holding the socks laid of it, in the order they were laid.
  const laid = laySocks(socks.length, length, edge);
  const loose = socks.map((model, kind) =>
    new InstancedMesh(model.geometry, model.material, laid.filter((sock) => sock.kind === kind).length));
  function place(poses) {
    const slots = loose.map(() => 0);
    poses.forEach(({ x, y, z, yaw, pitch }, k) => {
      const kind = laid[k].kind;
      _matrix.compose(_position.set(x, y, z), _turn.setFromEuler(_euler.set(pitch, yaw, 0)), _one);
      loose[kind].setMatrixAt(slots[kind]++, _matrix);
    });
    for (const mesh of loose) {
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
  }
  place(diveAt(laid, [], 0));
  const group = new Group();
  group.name = "giant";
  group.add(rig.placer, woven, ...loose);
  group.traverse((node) => {
    if (node.isMesh) Object.assign(node, { castShadow: true, receiveShadow: true });
  });
  // Round by +z, the chase camera's side, as far as the neck goes.
  const [round] = rig.joints.get("head_yaw").range;
  return {
    group,
    /** Turn the head `facing` of the way round, 0 away from the lanes and 1 facing them. */
    pose(facing) {
      setJoint(rig, "head_yaw", facing * round);
    },
    /** The socks `seconds` after the first duck crossed the line at `divers` (diveAt). */
    dive(divers, seconds) {
      place(diveAt(laid, divers, seconds));
    },
    dispose() {
      group.removeFromParent();
      rig.placer.traverse((node) => {
        if (node.isMesh) node.material.dispose();
      });
      loose.forEach((mesh) => mesh.dispose());
    },
  };
}
