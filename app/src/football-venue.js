// The football match's venue (arena/football.py): a small pitch walled in by
// glass boards, a goal netted at each end, the ball, a Reachy Mini in each
// goal on its rail, and a stand of microducks behind each goal. The viewer
// builds the rest round it as it does round a race's lanes (viewer.js
// setLanes): the hall, the side stands and their crowd, the jury. A match is
// played in the same stadium, before the same spectators, as every challenge
// on the programme.
//
// The physics has the turf at z = 0 and the centre spot at its origin
// (arena/football.py compile_football). Here the venue is laid along three.js
// +x as a race's course is, from x = 0, `length` in all, the centre spot at
// `origin`. The pitch's own group stands there, turned so that its axes are
// MuJoCo's (rig.js: MJCF +y is three.js -z, +z is +y), and everything on it —
// the turf, its lines, the boards, the nets, the ball — is placed with the
// numbers the server sends (arena/football_watch.py football_summary), where
// the physics has it. The keepers stand in the venue's own frame, the Reachy
// Mini's model being upright in three.js's.

import {
  BoxGeometry,
  BufferGeometry,
  CircleGeometry,
  Color,
  CylinderGeometry,
  Float32BufferAttribute,
  Group,
  IcosahedronGeometry,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshStandardMaterial,
  PlaneGeometry,
  RingGeometry,
  Shape,
  ShapeGeometry,
  Vector3,
} from "three";
import { stadiumDirection } from "./clip/direction.js";
import { OVERRUN } from "./course.js";
import { PALETTE, flat } from "./palette.js";
import { buildStand, crowd, seats } from "./stadium.js";

/** Whether an event is a football match's (football/main.js makes it), for which the viewer builds this venue. */
export const isFootball = (event) => event?.course === "football";

// Floor beyond the side boards, inside the stadium's rails, and beyond the
// goals' backs: the stands and the jury are set out from the side's edge.
const APRON = 0.25;
const END_APRON = 0.2;
// A stand behind each goal, the stadium's own turned end on, so the crowd is
// round the whole pitch. Its first tier is END_STAND_OUT beyond the venue's
// end, its back as far short of the hall's end wall (gym.js) whatever the
// pitch's length; across, it stops END_STAND_INSET inside the floor's edge,
// clear of the far side's rail and cones, which run on past the venue's ends
// (stadium.js attachStadium). END_SEATS a tier, about as close as the
// stadium's, and even, so none sits on the pitch's axis, which crowd splits
// its flocks by.
const END_STAND_OUT = 0.1;
const END_STAND_INSET = 0.1;
const END_SEATS = 8;
// The turf over the hall's parquet, and its paint over the turf.
const TURF_LIFT = 0.0015;
const PAINT_LIFT = 0.003;
// The pitch's paint: its lines, the centre circle and spot, each penalty area
// and its spot, in metres. The goal line is the end line, its outer edge on the
// line the referee rules a goal over (the ball wholly past x = ±length/2).
const LINE = 0.02;
const CENTRE_CIRCLE = 0.2;
const SPOT = 0.016;
const AREA_DEPTH = 0.3;
const AREA_HALF = 0.45;
const PENALTY_SPOT = 0.4;
// Mown stripes across the pitch, two greens about as far apart as a stadium's.
const STRIPES = 10;
const GRASS = [0x2e8a45, 0x379c50];
const GOAL_GRASS = 0x2a7a3d;
// The boards: glass, so a duck by the near board is not hidden from the camera,
// under a cyan cap.
const GLASS = 0xbfe6ef;
const CAP = 0.012;
// The goals: a frame round each mouth, just outside it, and their nets as a
// mesh of strings over a veil the camera can see through.
const POST_RADIUS = 0.009;
const NET_MESH = 0.03;
const NET = 0xf4f4ef;
// The ball: an icosahedron with each edge split in six (`BALL_DETAIL`), so the
// faces within two of those steps of a vertex — all within `PATCH_RAD` of it,
// the next ring 0.36 out — are the pentagon a truncated icosahedron cuts there,
// a third of the way along each edge: black, as a football's panels are.
const BALL_DETAIL = 5;
const PATCH_RAD = 0.31;
const BALL_WHITE = [0.9, 0.9, 0.88];
const BALL_BLACK = [0.035, 0.035, 0.045];
// The keepers, each in its own colour and in neither duck's (football/plays.js
// LIVERIES: A cream on orange, B sky): lime keeps end 0's goal, magenta end 1's.
export const KEEPER_TINTS = [0xc8ff2e, 0xff2fa8];
// The Reachy Mini's shell, as its model names the materials: tinted, while its
// head stays white, so it still reads as the robot the jury is.
const SHELL = new Set(["body_down_3dprint_material", "body_top_3dprint_material"]);
// The rail a keeper slides along, a steel strip across its goal's mouth.
const STEEL = 0x8a949b;
const RAIL_WIDTH = 0.03;
const RAIL_HEIGHT = 0.004;
// Where a keeper's eyes are over the turf, and how far its head turns and tips
// to follow the ball.
const EYE_HEIGHT = 0.2;
const GAZE_YAW = 1.0;
const GAZE_PITCH = 0.5;
// The broadcast camera, on the near side: how far out, how high, how far above
// the turf it aims. Far enough out and aimed high enough that the near board
// sits on the frame's foot and the far stand's crowd, all six tiers of it, fills
// the top over the jury; closer in, the crowd was a row of heads at the top
// edge. It follows the ball along the pitch, smoothed over FOLLOW_S either
// side, by FOLLOW_GAIN of the way, and no farther than FOLLOW_LIMIT from the
// centre spot, so a goal and the half it is in fill the picture. Tuned by eye
// on the football page.
const CAMERA_BACK = 2.15;
const CAMERA_RISE = 1.2;
const CAMERA_AIM = 0.37;
const FOLLOW_S = 0.6;
const FOLLOW_GAIN = 0.75;
const FOLLOW_LIMIT = 0.55;
// The crowd's ear on the ball: sampled this often, its excitement building as
// the ball nears either goal.
const PROGRESS_STEP = 0.1;
// A frame of props (arena/football.py PROP_WIDTH): the ball's position and
// quaternion (w, x, y, z), then each keeper's place along its rail.
export const PROP_WIDTH = 9;

/**
 * Where everything stands, from the pitch and the goals as the server
 * describes them: the venue `length` long along x from 0, its centre spot at
 * `origin`, `half` from either end; the floor `span` wide across it, boards and
 * aprons included, whose `edge` the stadium and the jury are set out from.
 * Pure, so it is testable.
 */
export function footballLayout({ pitch, goal }) {
  const half = pitch.length_m / 2 + goal.depth_m + END_APRON;
  const edge = pitch.width_m / 2 + pitch.board_thickness_m + APRON;
  return { length: 2 * half, half, span: 2 * edge, edge, lift: 0, origin: [half, 0, 0] };
}

/** How far the turf reaches either side of the pitch's middle line at `x`: the corners are cut at 45°. */
export function turfHalfWidth(pitch, x) {
  const cut = Math.max(0, Math.abs(x) - (pitch.length_m / 2 - pitch.corner_m));
  return pitch.width_m / 2 - cut;
}

/**
 * The pitch's outline `inset` in from its boards, counterclockwise from the
 * near end of the +x end line, as [x, y] corners in the physics' frame: a
 * rectangle with its corners cut, as the boards stand. Pure, so it is testable.
 */
export function pitchOutline(pitch, inset = 0) {
  const x = pitch.length_m / 2 - inset;
  const y = pitch.width_m / 2 - inset;
  // An edge at 45° moved in by `inset` cuts each side that much less, less the diagonal's share.
  const cut = pitch.corner_m - inset * (2 - Math.SQRT2);
  return [
    [x, -(y - cut)], [x, y - cut], [x - cut, y], [-(x - cut), y],
    [-x, y - cut], [-x, -(y - cut)], [-(x - cut), -y], [x - cut, -y],
  ];
}

/**
 * The stripe of turf from x0 to x1, as [x, y] corners round it, bent where it
 * crosses the start of a corner's cut. Pure, so it is testable.
 */
export function stripeOutline(pitch, x0, x1) {
  const bend = pitch.length_m / 2 - pitch.corner_m;
  const xs = [x0, ...[-bend, bend].filter((x) => x > x0 && x < x1), x1];
  return [
    ...xs.map((x) => [x, -turfHalfWidth(pitch, x)]),
    ...[...xs].reverse().map((x) => [x, turfHalfWidth(pitch, x)]),
  ];
}

/**
 * The strings of a net, as line segments [[x, y, z], [x, y, z]] in the
 * physics' frame: a grid every `mesh` metres across the box's two broad sides,
 * through its middle. Pure, so it is testable.
 */
export function netStrings({ pos, half, yaw_rad: yaw = 0 }, mesh = NET_MESH) {
  const thin = half.indexOf(Math.min(...half));
  const [u, v] = [0, 1, 2].filter((axis) => axis !== thin);
  const cos = Math.cos(yaw);
  const sin = Math.sin(yaw);
  const world = (local) => [
    pos[0] + cos * local[0] - sin * local[1],
    pos[1] + sin * local[0] + cos * local[1],
    pos[2] + local[2],
  ];
  const segments = [];
  for (const [along, across] of [[u, v], [v, u]]) {
    const count = Math.max(1, Math.round((2 * half[across]) / mesh));
    for (let i = 0; i <= count; i++) {
      const a = [0, 0, 0];
      const b = [0, 0, 0];
      a[across] = b[across] = -half[across] + (2 * half[across] * i) / count;
      a[along] = -half[along];
      b[along] = half[along];
      segments.push([world(a), world(b)]);
    }
  }
  return segments;
}

/**
 * The props on the replay's frame `index`, a lane's frame (replay.js leadIn:
 * the settle, then the play): where the ball and the keepers stood at kick-off
 * through the settle, then the play's own, the last held once they run out. A
 * view, not a copy, so it is cheap inside a render loop. Pure, so it is testable.
 */
export function propsAt({ props, kickoff, settle_frames: settle }, index) {
  const count = props ? Math.floor(props.length / PROP_WIDTH) : 0;
  if (index < settle || count === 0) return kickoff;
  const f = Math.min(index - settle, count - 1);
  return props.subarray(f * PROP_WIDTH, (f + 1) * PROP_WIDTH);
}

/**
 * Where the camera stands along the pitch on each of a play's `frames` replay
 * frames, from the centre spot: the ball's x smoothed over FOLLOW_S either
 * side, so the camera glides where a strike would jerk it, FOLLOW_GAIN of the
 * way and no farther than FOLLOW_LIMIT. Pure, so it is testable.
 */
export function followTrack(play, frames, ctrlDt) {
  const reach = Math.max(0, Math.round(FOLLOW_S / ctrlDt));
  const sums = new Float64Array(frames + 1);
  for (let i = 0; i < frames; i++) sums[i + 1] = sums[i] + propsAt(play, i)[0];
  return Float32Array.from({ length: frames }, (_, i) => {
    const [from, to] = [Math.max(0, i - reach), Math.min(frames, i + reach + 1)];
    const mean = (sums[to] - sums[from]) / (to - from);
    return Math.max(-FOLLOW_LIMIT, Math.min(FOLLOW_LIMIT, FOLLOW_GAIN * mean));
  });
}

/**
 * How near the ball was to either goal while the play was on, as the crowd
 * follows it (clip/direction.js stadiumDirection's progress): every
 * PROGRESS_STEP of the replay from the horn to the decision, from 0 on the
 * halfway line to 1 on a goal line. Pure, so it is testable.
 */
export function ballProgress(play, { horn_s, decided_s }, halfLength, ctrlDt) {
  const samples = [];
  for (let k = 0; horn_s + k * PROGRESS_STEP <= decided_s + 1e-9; k++) {
    const second = Math.min(decided_s, horn_s + k * PROGRESS_STEP);
    const x = propsAt(play, Math.floor(second / ctrlDt + 1e-9))[0];
    samples.push({ second, value: Math.min(1, Math.abs(x) / halfLength) });
  }
  return samples;
}

/**
 * Where the camera watches a play from (viewer.js cameraPose): the broadcast's,
 * from the near side, square to the pitch, `follow` metres along it from the
 * centre spot (followTrack). Pure, so it is testable.
 */
export function footballCamera({ half }, follow = 0) {
  const x = half + follow;
  return { kind: "fixed", position: [x, CAMERA_RISE, CAMERA_BACK], target: [x, CAMERA_AIM, 0] };
}

/**
 * The crowd's direction over a play (clip/direction.js stadiumDirection), in
 * the replay's seconds: up at the horn, building as the ball nears a goal
 * (`progress`, ballProgress), then a goal cheered — one given for the other's
 * fault too — and a play both ducks went down in mourned. The whistle, two faults and a void play
 * leave it no result to feel.
 */
export function footballDirection({ horn_s = 0, decided_s = 0, scorer = null, end = null, progress = [] } = {}) {
  const start = Math.max(0, horn_s);
  const verdict = scorer === 0 || scorer === 1 ? "pass" : end === "down" ? "fail" : null;
  const decided = Math.max(start, decided_s);
  return stadiumDirection({ start, end: decided, progress: progress.filter((s) => s.second <= decided), verdict });
}

/**
 * How keeper `k`'s head turns to watch the ball, in its own frame (judges.js
 * poses the jury's heads the same way): its yaw and pitch, from its eyes and
 * the ball, both in the venue's frame. Keeper 0 faces +x, up the pitch from
 * the goal at -x; keeper 1 faces -x. Pure, so it is testable.
 */
export function keeperGaze(k, eye, ball) {
  const facing = k === 0 ? 1 : -1;
  const dx = (ball.x - eye.x) * facing;
  const dz = (ball.z - eye.z) * facing;
  const clamp = (value, limit) => Math.max(-limit, Math.min(limit, value));
  return {
    yaw: clamp(Math.atan2(-dz, dx), GAZE_YAW),
    pitch: clamp(Math.atan2(ball.y - eye.y, Math.hypot(dx, dz)), GAZE_PITCH),
  };
}

// An icosahedron's twelve vertices, as IcosahedronGeometry has them: where a
// football's pentagons are centred.
const ICOSAHEDRON = (() => {
  const t = (1 + Math.sqrt(5)) / 2;
  return [
    [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t],
    [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
  ].map(([x, y, z]) => new Vector3(x, y, z).normalize());
})();

/** The ball's sphere, `radius` round, its faces coloured white or, round each icosahedron vertex, black. */
export function ballGeometry(radius) {
  const geometry = new IcosahedronGeometry(radius, BALL_DETAIL);
  const position = geometry.getAttribute("position");
  const colours = new Float32Array(position.count * 3);
  const [a, b, c] = [new Vector3(), new Vector3(), new Vector3()];
  for (let f = 0; f + 2 < position.count; f += 3) {
    a.fromBufferAttribute(position, f);
    b.fromBufferAttribute(position, f + 1);
    c.fromBufferAttribute(position, f + 2);
    const centre = a.add(b).add(c).normalize();
    const shade = ICOSAHEDRON.some((vertex) => vertex.angleTo(centre) < PATCH_RAD) ? BALL_BLACK : BALL_WHITE;
    for (let v = 0; v < 3; v++) colours.set(shade, (f + v) * 3);
  }
  geometry.setAttribute("color", new Float32BufferAttribute(colours, 3));
  return geometry;
}

/**
 * A keeper: a clone of the Reachy Mini's model (sharing its geometry, as the
 * jury's clones do), its shell in `tint`. The tinted materials are pushed onto
 * `materials`, for the venue to dispose of; the model's own are left alone.
 */
export function keeperRobot(model, tint, materials) {
  const robot = model.clone(true);
  const painted = new Map();
  const paint = (material) => {
    if (!SHELL.has(material.name)) return material;
    if (!painted.has(material)) {
      const copy = material.clone();
      copy.color = new Color(tint);
      painted.set(material, copy);
      materials.push(copy);
    }
    return painted.get(material);
  };
  robot.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = node.receiveShadow = true;
    node.material = Array.isArray(node.material) ? node.material.map(paint) : paint(node.material);
  });
  return robot;
}

/**
 * A stand behind each goal, from the venue's `half` and its floor's `edge`
 * (footballLayout), and in its seats the viewer's `spectators` (the crowd's
 * lighter model, viewer.js): one crowd for both ends, so its wave sweeps along
 * x with the side stands' (stadium.js crowd).
 */
function endStands({ kinematics, geometries }, { half, edge }) {
  const group = new Group();
  group.name = "end-stands";
  const inner = half + END_STAND_OUT;
  // buildStand runs on OVERRUN and 0.1 past either end of its run, and seats
  // spectators to OVERRUN less 0.1 (stadium.js): the run that leaves it so wide.
  const run = 2 * (edge - END_STAND_INSET - OVERRUN - 0.1);
  const reach = run / 2 + OVERRUN - 0.1;
  // Each tier's height by how far out it is, as the stadium seats its own.
  const rows = new Map(seats(run, inner, 1).map(({ y, z }) => [z, y]));
  const across = Array.from({ length: END_SEATS }, (_, i) => -reach + (2 * reach * i) / (END_SEATS - 1));
  const stand = buildStand(run, inner, 1);
  const placed = [];
  for (const [s, built] of [[-1, stand.clone()], [1, stand]]) {
    // buildStand runs along x and steps out along +z: a quarter turn and it
    // steps out along x, beyond the end at -x or +x, centred on the axis.
    built.rotation.y = (s * Math.PI) / 2;
    built.position.set(half, 0, (s * run) / 2);
    group.add(built);
    for (const [out, y] of rows) {
      for (const z of across) placed.push({ x: half + s * out, y, z, yaw: ((1 + s) * Math.PI) / 2 });
    }
  }
  const audience = crowd(kinematics, geometries, placed);
  // Its talk is left unhung: crowdBubbles times each word by the clock alone,
  // so it would pop up here at the very moment the side stands' does. As on
  // the talent stage (talent-stage.js), these spectators only cheer.
  group.add(audience.group);
  group.traverse((node) => {
    if (node.isMesh) node.castShadow = true;
  });
  return {
    group,
    crowd: audience,
    dispose() {
      audience.dispose();
      // The two stands share their geometry and paint.
      const own = new Set();
      group.traverse((node) => {
        if (!node.isMesh || node.isInstancedMesh) return;
        own.add(node.geometry);
        own.add(node.material);
      });
      own.forEach((thing) => thing.dispose());
    },
  };
}

/**
 * The venue for a football match's event (football/main.js): `event.football`
 * is the pitch, the goals, the ball and the keepers as the server describes
 * them, `event.props` the play's props, and its horn, decision and end set the
 * crowd's direction. `reachy` is the Reachy Mini's model the jury is cloned
 * from; `spectators` is the crowd's lighter model (viewer.js), seated in a
 * stand behind each goal (none without it). `place` stands a duck's rig where
 * its trace's world frame is; `pose` puts the ball and the keepers where they
 * were on the replay's frame `index`, once a frame, and moves the camera along
 * the pitch with the ball.
 */
export function buildFootballVenue(event, reachy, spectators) {
  const { pitch, goal, keeper } = event.football;
  const layout = footballLayout(event.football);
  const { length, half, span } = layout;
  const length_m = pitch.length_m;
  const group = new Group();
  group.name = "course";
  const geometries = [];
  const materials = [];
  const own = (list, thing) => {
    list.push(thing);
    return thing;
  };
  const paint = (color, options = {}) => own(materials, new MeshStandardMaterial({ color, roughness: 0.8, ...options }));

  // The hall's floor under the venue: the viewer lays the gym's parquet on it,
  // and the stadium reads its size (stadium.js).
  const ground = new Mesh(own(geometries, new PlaneGeometry(length + 2 * OVERRUN, span)), paint(0x2a2c31, { roughness: 1 }));
  ground.name = "ground";
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(half, 0, 0);
  group.add(ground);

  // The pitch, in the physics' frame: x along it, y across, z up.
  const field = new Group();
  field.name = "pitch";
  field.rotation.x = -Math.PI / 2;
  field.position.set(...layout.origin);
  group.add(field);

  function lay(corners, material, lift) {
    const shape = new Shape();
    corners.forEach(([x, y], i) => (i ? shape.lineTo(x, y) : shape.moveTo(x, y)));
    const mesh = new Mesh(own(geometries, new ShapeGeometry(shape)), material);
    mesh.position.z = lift;
    field.add(mesh);
    return mesh;
  }
  function box([w, d, h], [x, y, z], yaw, material, shadow = true) {
    const mesh = new Mesh(own(geometries, new BoxGeometry(w, d, h)), material);
    mesh.position.set(x, y, z);
    mesh.rotation.z = yaw;
    mesh.castShadow = shadow;
    field.add(mesh);
    return mesh;
  }

  // The turf, mown in stripes across the pitch, and each goal's floor behind its line.
  const greens = GRASS.map((color) => paint(color, { roughness: 1 }));
  for (let s = 0; s < STRIPES; s++) {
    const [x0, x1] = [s, s + 1].map((i) => -length_m / 2 + (length_m * i) / STRIPES);
    lay(stripeOutline(pitch, x0, x1), greens[s % 2], TURF_LIFT).name = `turf-${s}`;
  }
  const pocket = paint(GOAL_GRASS, { roughness: 1 });
  for (const sx of [-1, 1]) {
    const [x0, x1] = [length_m / 2, length_m / 2 + goal.depth_m].map((x) => sx * x);
    const y = goal.width_m / 2;
    lay([[x0, -y], [x1, -y], [x1, y], [x0, y]], pocket, TURF_LIFT);
  }

  // The paint: the pitch's outline, the halfway line, the centre circle and
  // spot, and at each end the penalty area and its spot.
  const white = own(materials, flat(PALETTE.paper));
  function line([ax, ay], [bx, by]) {
    // As long again as the line is wide, so it meets its neighbours at a corner.
    const mesh = new Mesh(own(geometries, new PlaneGeometry(Math.hypot(bx - ax, by - ay) + LINE, LINE)), white);
    mesh.position.set((ax + bx) / 2, (ay + by) / 2, PAINT_LIFT);
    mesh.rotation.z = Math.atan2(by - ay, bx - ax);
    field.add(mesh);
  }
  function disc(geometry, x) {
    const mesh = new Mesh(own(geometries, geometry), white);
    mesh.position.set(x, 0, PAINT_LIFT);
    field.add(mesh);
  }
  const outline = pitchOutline(pitch, LINE / 2);
  outline.forEach((corner, i) => line(corner, outline[(i + 1) % outline.length]));
  line([0, -(pitch.width_m - LINE) / 2], [0, (pitch.width_m - LINE) / 2]);
  disc(new RingGeometry(CENTRE_CIRCLE - LINE / 2, CENTRE_CIRCLE + LINE / 2, 64), 0);
  disc(new CircleGeometry(SPOT, 20), 0);
  for (const sx of [-1, 1]) {
    const [inner, outer] = [length_m / 2 - LINE / 2, length_m / 2 - AREA_DEPTH].map((x) => sx * x);
    for (const sy of [-1, 1]) line([inner, sy * AREA_HALF], [outer, sy * AREA_HALF]);
    line([outer, -AREA_HALF], [outer, AREA_HALF]);
    disc(new CircleGeometry(SPOT, 20), sx * (length_m / 2 - PENALTY_SPOT));
  }

  // The boards, as the physics has them, glass under a cyan cap.
  const glass = paint(GLASS, { roughness: 0.1, transparent: true, opacity: 0.22, depthWrite: false });
  const cap = own(materials, flat(PALETTE.rail));
  for (const { name, pos, half: h, yaw_rad: yaw } of pitch.boards) {
    const [base, height] = [pos[2] - h[2], 2 * h[2]];
    box([2 * h[0], 2 * h[1], height - CAP], [pos[0], pos[1], base + (height - CAP) / 2], yaw, glass, false).name = name;
    box([2 * h[0], 2 * h[1], CAP], [pos[0], pos[1], base + height - CAP / 2], yaw, cap);
  }

  // The goals: the nets where the physics has them, a veil and its strings,
  // and a white frame round each mouth.
  const veil = paint(NET, { roughness: 1, transparent: true, opacity: 0.12, depthWrite: false });
  for (const { name, pos, half: h, yaw_rad: yaw } of pitch.nets) {
    box(h.map((v) => 2 * v), pos, yaw, veil, false).name = name;
  }
  const strings = own(geometries, new BufferGeometry());
  strings.setAttribute("position", new Float32BufferAttribute(pitch.nets.flatMap((net) => netStrings(net)).flat(2), 3));
  const strung = new LineSegments(strings, own(materials, new LineBasicMaterial({ color: NET, transparent: true, opacity: 0.7 })));
  strung.name = "net-strings";
  field.add(strung);
  for (const sx of [-1, 1]) {
    const x = sx * (length_m / 2 + POST_RADIUS);
    const top = goal.height_m + POST_RADIUS;
    for (const sy of [-1, 1]) {
      const post = new Mesh(own(geometries, new CylinderGeometry(POST_RADIUS, POST_RADIUS, top + POST_RADIUS, 12)), white);
      post.rotation.x = Math.PI / 2;
      post.position.set(x, sy * (goal.width_m / 2 + POST_RADIUS), (top + POST_RADIUS) / 2);
      post.castShadow = true;
      field.add(post);
    }
    const bar = new Mesh(own(geometries, new CylinderGeometry(POST_RADIUS, POST_RADIUS, goal.width_m + 4 * POST_RADIUS, 12)), white);
    bar.position.set(x, 0, top);
    bar.castShadow = true;
    field.add(bar);
  }

  // The ball, where the props have it.
  const ball = new Mesh(
    own(geometries, ballGeometry(event.football.ball.radius_m)),
    own(materials, new MeshStandardMaterial({ vertexColors: true, roughness: 0.5 })),
  );
  ball.name = "ball";
  ball.castShadow = true;
  field.add(ball);

  // The keepers, each on its rail across its goal's mouth, and the rail under it.
  const steel = paint(STEEL, { roughness: 0.5, metalness: 0.4 });
  const keepers = KEEPER_TINTS.map((tint, k) => {
    const sx = k === 0 ? -1 : 1;
    const x = sx * keeper.x_m;
    box([RAIL_WIDTH, 2 * keeper.rail_m + keeper.diameter_m, RAIL_HEIGHT], [x, 0, RAIL_HEIGHT / 2], 0, steel, false)
      .name = `rail-${k}`;
    if (!reachy) return null;
    const robot = keeperRobot(reachy, tint, materials);
    robot.name = `keeper-${k}`;
    robot.rotation.y = k === 0 ? 0 : Math.PI;
    group.add(robot);
    return {
      robot,
      x: half + x,
      head: robot.getObjectByName("reachy_head"),
      right: robot.getObjectByName("antenna_right"),
      left: robot.getObjectByName("antenna_left"),
    };
  });

  // A stand of spectators behind each goal; the side stands are the stadium's,
  // which the viewer hangs on the venue as on a race's course (attachStadium).
  const ends = spectators ? endStands(spectators, layout) : null;
  if (ends) group.add(ends.group);

  const frames = event.settle_frames + (event.props ? Math.floor(event.props.length / PROP_WIDTH) : 0);
  const track = followTrack(event, Math.max(1, frames), event.ctrl_dt);
  let shown = 0;
  const _eye = new Vector3();
  const _ball = new Vector3();

  function pose(index) {
    shown = Math.max(0, Math.min(track.length - 1, index));
    const row = propsAt(event, index);
    ball.position.set(row[0], row[1], row[2]);
    ball.quaternion.set(row[4], row[5], row[6], row[3]);
    _ball.set(half + row[0], row[2], -row[1]);
    keepers.forEach((keeperRig, k) => {
      if (!keeperRig) return;
      const { robot, x, head, right, left } = keeperRig;
      robot.position.set(x, RAIL_HEIGHT, -row[7 + k]);
      const gaze = keeperGaze(k, _eye.set(x, EYE_HEIGHT, -row[7 + k]), _ball);
      const phase = index * event.ctrl_dt * 1.3 + k * 2.4;
      head?.rotation.set(0.03 * Math.sin(phase * 0.63), gaze.yaw, gaze.pitch, "YXZ");
      if (right) right.rotation.x = 0.13 * Math.sin(phase * 1.7) + 0.06 * Math.sin(phase * 3.1);
      if (left) left.rotation.x = 0.12 * Math.sin(phase * 1.4 + 1.8);
    });
  }
  pose(0);

  return {
    group,
    length,
    edge: layout.edge,
    lift: 0,
    /** The broadcast camera, where the ball last put it (pose). */
    get camera() {
      return footballCamera(layout, track[shown]);
    },
    /** Stand a duck's rig where its trace's world frame is: the centre spot. */
    place(rig) {
      rig.placer.position.set(...layout.origin);
      rig.placer.rotation.set(0, 0, 0);
    },
    /** The ball and the keepers as they were on the replay's frame `index`. */
    pose(rigs, index = 0) {
      pose(index);
    },
    direction: () =>
      footballDirection({ ...event, progress: ballProgress(event, event, length_m / 2, event.ctrl_dt) }),
    /** The spectators behind the goals, for the viewer to pose and cull with the stadium's. */
    crowd: ends?.crowd,
    dispose() {
      ends?.dispose();
      group.removeFromParent();
      geometries.forEach((geometry) => geometry.dispose());
      // The keepers' tinted shells are in `materials`; the rest of them is the model's, shared.
      materials.forEach((material) => material.dispose());
    },
  };
}
