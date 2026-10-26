// @vitest-environment node
// The football match's venue, in the course's frame as the viewer lays every
// course out: +x from end 0's goal to end 1's, +y up from the hall's floor, +z
// the camera's side and -z the jury's. The physics' frame, the pitch's, has +y
// where three.js has -z.

import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { Box3, BoxGeometry, Group, Matrix4, PerspectiveCamera, Triangle, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OVERRUN } from "./course.js";
import { olaAt } from "./crowd-behaviour.js";
import { meshNames } from "./rig.js";
import { attachStadium } from "./stadium.js";
import {
  KEEPER_TINTS,
  PROP_WIDTH,
  ballGeometry,
  ballProgress,
  buildFootballVenue,
  followTrack,
  footballCamera,
  footballDirection,
  footballLayout,
  isFootball,
  keeperGaze,
  keeperRobot,
  netStrings,
  pitchOutline,
  propsAt,
  stripeOutline,
  turfHalfWidth,
} from "./football-venue.js";

// arena/football.toml's pitch, goals, ball and keepers, as
// arena/football_watch.py football_summary serves them.
const box = (name, pos, half, yaw_rad = 0) => ({ name, pos, half, yaw_rad });
const PITCH = {
  length_m: 2.2,
  width_m: 1.5,
  corner_m: 0.25,
  board_height_m: 0.2,
  board_thickness_m: 0.05,
  boards: [
    box("side0", [0, 0.775, 0.1], [0.85, 0.025, 0.1]),
    box("side1", [0, -0.775, 0.1], [0.85, 0.025, 0.1]),
    box("end00", [-1.125, 0.4, 0.1], [0.025, 0.1, 0.1]),
    box("end01", [-1.125, -0.4, 0.1], [0.025, 0.1, 0.1]),
    box("end10", [1.125, 0.4, 0.1], [0.025, 0.1, 0.1]),
    box("end11", [1.125, -0.4, 0.1], [0.025, 0.1, 0.1]),
    box("corner00", [-0.992678, 0.642678, 0.1], [0.201777, 0.025, 0.1], -2.356194),
    box("corner01", [-0.992678, -0.642678, 0.1], [0.201777, 0.025, 0.1], 2.356194),
    box("corner10", [0.992678, 0.642678, 0.1], [0.201777, 0.025, 0.1], -0.785398),
    box("corner11", [0.992678, -0.642678, 0.1], [0.201777, 0.025, 0.1], 0.785398),
  ],
  nets: [
    box("goal0_back", [-1.305, 0, 0.15], [0.005, 0.31, 0.15]),
    box("goal0_side0", [-1.2, 0.305, 0.15], [0.1, 0.005, 0.15]),
    box("goal0_side1", [-1.2, -0.305, 0.15], [0.1, 0.005, 0.15]),
    box("goal0_roof", [-1.2, 0, 0.305], [0.1, 0.31, 0.005]),
    box("goal1_back", [1.305, 0, 0.15], [0.005, 0.31, 0.15]),
    box("goal1_side0", [1.2, 0.305, 0.15], [0.1, 0.005, 0.15]),
    box("goal1_side1", [1.2, -0.305, 0.15], [0.1, 0.005, 0.15]),
    box("goal1_roof", [1.2, 0, 0.305], [0.1, 0.31, 0.005]),
  ],
};
const FOOTBALL = {
  pitch: PITCH,
  goal: { width_m: 0.6, height_m: 0.3, depth_m: 0.2 },
  ball: { radius_m: 0.035 },
  keeper: { diameter_m: 0.16, height_m: 0.26, x_m: 1.08, rail_m: 0.14 },
};
const DT = 0.02;
// The ball on the centre spot and both keepers in the middle of their rails.
const KICKOFF = [0, 0, 0.035, 1, 0, 0, 0, 0, 0];

/**
 * A play's event as football/plays.js playEvent makes it: `settle` frames at
 * kick-off, then a props row for each of `rows`, [x, y] the ball's place on the
 * pitch and k0, k1 the keepers' along their rails.
 */
function event({ rows = [], settle = 3, ...more } = {}) {
  const props = new Float32Array(rows.length * PROP_WIDTH);
  rows.forEach(([x, y, k0 = 0, k1 = 0], f) => props.set([x, y, 0.035, 1, 0, 0, 0, k0, k1], f * PROP_WIDTH));
  const horn = (settle - 1) * DT;
  return {
    course: "football",
    id: "football",
    football: FOOTBALL,
    ctrl_dt: DT,
    settle_frames: settle,
    kickoff: [...KICKOFF],
    props: rows.length ? props : null,
    horn_s: horn,
    decided_s: horn + rows.length * DT,
    scorer: null,
    end: "whistle",
    ...more,
  };
}
const still = (count, x = 0, y = 0, k0 = 0, k1 = 0) => Array.from({ length: count }, () => [x, y, k0, k1]);
const bounds = (object) => new Box3().setFromObject(object);
const area = (corners) =>
  Math.abs(corners.reduce((sum, [x, y], i) => {
    const [nx, ny] = corners[(i + 1) % corners.length];
    return sum + x * ny - nx * y;
  }, 0)) / 2;

describe("footballLayout", () => {
  it("lays the pitch along x from 0, its goals and an apron beyond each end, the centre spot in the middle", () => {
    const layout = footballLayout(FOOTBALL);
    // Half the pitch, a goal's depth and the apron behind it.
    expect(layout.half).toBeCloseTo(1.1 + 0.2 + 0.2);
    expect(layout.length).toBeCloseTo(3);
    expect(layout.origin).toEqual([expect.closeTo(1.5), 0, 0]);
    expect(layout.lift).toBe(0);
  });

  it("sets the stadium out from beyond the side boards and the apron outside them", () => {
    const layout = footballLayout(FOOTBALL);
    expect(layout.edge).toBeCloseTo(0.75 + 0.05 + 0.25);
    expect(layout.span).toBeCloseTo(2 * layout.edge);
  });
});

describe("isFootball", () => {
  it("knows a football match's event from a race's or a stage's", () => {
    expect(isFootball(event())).toBe(true);
    expect(isFootball({ course: "lane" })).toBe(false);
    expect(isFootball({ course: "stage" })).toBe(false);
    expect(isFootball({ id: "sprint" })).toBe(false);
    expect(isFootball(null)).toBe(false);
  });
});

describe("the pitch's outline", () => {
  it("narrows the turf at 45° over each corner's cut", () => {
    for (const [x, width] of [[0, 0.75], [0.85, 0.75], [-0.85, 0.75], [1, 0.6], [-1.1, 0.5], [1.1, 0.5]]) {
      expect(turfHalfWidth(PITCH, x)).toBeCloseTo(width);
    }
  });

  it("runs round the boards' inner faces, its corners cut as they stand", () => {
    const expected = [[1.1, -0.5], [1.1, 0.5], [0.85, 0.75], [-0.85, 0.75], [-1.1, 0.5], [-1.1, -0.5], [-0.85, -0.75], [0.85, -0.75]];
    pitchOutline(PITCH).forEach((corner, i) => expect(corner).toEqual(expected[i].map((v) => expect.closeTo(v))));
  });

  it("moves every side in by the inset, the cut ones too, which stay at 45°", () => {
    const [outer, inner] = [pitchOutline(PITCH), pitchOutline(PITCH, 0.01)];
    outer.forEach((a, i) => {
      const b = outer[(i + 1) % outer.length];
      const [c, d] = [inner[i], inner[(i + 1) % inner.length]];
      const [ux, uy] = [b[0] - a[0], b[1] - a[1]].map((v) => v / Math.hypot(b[0] - a[0], b[1] - a[1]));
      const [vx, vy] = [d[0] - c[0], d[1] - c[1]].map((v) => v / Math.hypot(d[0] - c[0], d[1] - c[1]));
      // Parallel, and the inset apart: inward is to the left of a counterclockwise side.
      expect(ux * vy - uy * vx).toBeCloseTo(0);
      expect(-uy * (c[0] - a[0]) + ux * (c[1] - a[1])).toBeCloseTo(0.01);
      if (ux !== 0 && uy !== 0) expect(Math.abs(ux)).toBeCloseTo(Math.SQRT1_2);
    });
  });

  it("mows stripes that tile the turf, bent where one crosses the start of a cut", () => {
    const stripes = Array.from({ length: 10 }, (_, s) => stripeOutline(PITCH, -1.1 + 0.22 * s, -1.1 + 0.22 * (s + 1)));
    expect(stripes.reduce((sum, stripe) => sum + area(stripe), 0)).toBeCloseTo(2.2 * 1.5 - 4 * (0.25 * 0.25) / 2);
    expect(stripes[4]).toHaveLength(4);
    // 0.66 to 0.88 crosses 0.85, where the cut starts.
    expect(stripes[8]).toHaveLength(6);
    expect(stripes[8]).toContainEqual([expect.closeTo(0.85), expect.closeTo(0.75)]);
    expect(stripes[9][1]).toEqual([expect.closeTo(1.1), expect.closeTo(-0.5)]);
  });
});

describe("netStrings", () => {
  it("strings each net across its two broad sides, through its middle, as far as it reaches", () => {
    for (const net of PITCH.nets) {
      const thin = net.half.indexOf(Math.min(...net.half));
      const segments = netStrings(net);
      expect(segments.length).toBeGreaterThan(10);
      for (const point of segments.flat()) {
        point.forEach((v, axis) => {
          if (axis === thin) expect(v).toBeCloseTo(net.pos[axis]);
          else expect(Math.abs(v - net.pos[axis])).toBeLessThanOrEqual(net.half[axis] + 1e-9);
        });
      }
    }
  });

  it("knots the strings a mesh apart, 3 cm on a pitch this size", () => {
    // The back of a goal: 30 cm high, 62 cm across.
    const back = netStrings(PITCH.nets[0]);
    expect(back).toHaveLength(11 + 22);
    expect(netStrings(PITCH.nets[0], 0.1)).toHaveLength(4 + 7);
  });

  it("turns with its box", () => {
    const [[a, b]] = netStrings(box("net", [1, 2, 3], [0.1, 0.005, 0.2], Math.PI / 2), 0.4);
    // Along the box's own x, which is the world's y once it is turned a quarter.
    expect(a).toEqual([expect.closeTo(1), expect.closeTo(1.9), expect.closeTo(2.8)]);
    expect(b).toEqual([expect.closeTo(1), expect.closeTo(2.1), expect.closeTo(2.8)]);
  });
});

describe("propsAt", () => {
  it("has the props at kick-off through the settle, then the play's, the last held", () => {
    const play = event({ rows: [[0.1, 0.2, 0.05, -0.05], [0.3, 0.4]] });
    for (const index of [0, 1, 2]) expect([...propsAt(play, index)]).toEqual(KICKOFF);
    expect(propsAt(play, 3)[0]).toBeCloseTo(0.1);
    expect([propsAt(play, 3)[7], propsAt(play, 3)[8]]).toEqual([expect.closeTo(0.05), expect.closeTo(-0.05)]);
    expect(propsAt(play, 4)[0]).toBeCloseTo(0.3);
    expect(propsAt(play, 400)[0]).toBeCloseTo(0.3);
  });

  it("stays at kick-off for a play with no props, and lends its rows rather than copying them", () => {
    expect([...propsAt(event(), 40)]).toEqual(KICKOFF);
    const play = event({ rows: [[0.1, 0.2]] });
    expect(propsAt(play, 3).buffer).toBe(play.props.buffer);
  });
});

describe("followTrack", () => {
  it("holds at the centre spot for a ball that stays there", () => {
    const play = event({ rows: still(100) });
    expect([...followTrack(play, 103, DT)].every((x) => x === 0)).toBe(true);
  });

  it("follows the ball some of the way, and no farther than a goal's half fills the picture", () => {
    const track = (x) => followTrack(event({ rows: still(200, x) }), 203, DT)[150];
    expect(track(0.2)).toBeCloseTo(0.15);
    expect(track(1)).toBeCloseTo(0.55);
    expect(track(-1)).toBeCloseTo(-0.55);
  });

  it("glides after a ball struck from one place to another", () => {
    const track = followTrack(event({ rows: [...still(100), ...still(100, 0.4)] }), 203, DT);
    const steps = track.slice(1).map((x, i) => x - track[i]);
    expect(Math.min(...steps)).toBeGreaterThanOrEqual(0);
    // Smoothed over 0.6 s either side: 61 frames to cover three quarters of the way.
    expect(Math.max(...steps)).toBeLessThan(0.006);
    expect(track[202]).toBeCloseTo(0.3);
  });
});

describe("ballProgress", () => {
  // Toward end 0's goal, 6.05 cm every sample (5 frames), over its line by the last.
  const rows = Array.from({ length: 100 }, (_, f) => [-0.0121 * (f + 1), 0.1]);

  it("samples from the horn to the decision, the ball's way to either goal line from the halfway line", () => {
    const play = event({ rows });
    const samples = ballProgress(play, play, 1.1, DT);
    expect(samples[0]).toEqual({ second: expect.closeTo(play.horn_s), value: 0 });
    samples.slice(1).forEach((sample, i) => expect(sample.second).toBeGreaterThan(samples[i].second));
    expect(samples.at(-1).second).toBeLessThanOrEqual(play.decided_s);
    expect(samples.every(({ value }) => value >= 0 && value <= 1)).toBe(true);
    // A second in, 60.5 cm from the halfway line of the 1.1 m to the goal line; then over it.
    expect(samples[10].value).toBeCloseTo(0.55);
    expect(samples.at(-1).value).toBe(1);
  });

  it("feeds the crowd a direction it takes", () => {
    const play = event({ rows, scorer: 1, end: "goal" });
    const mood = footballDirection({ ...play, progress: ballProgress(play, play, 1.1, DT) });
    expect(Number.isFinite(mood(play.decided_s - 0.1).action)).toBe(true);
  });
});

describe("footballCamera", () => {
  it("watches from the near side, square to the pitch, as far along it as it follows the ball", () => {
    const layout = footballLayout(FOOTBALL);
    const camera = footballCamera(layout);
    expect(camera.kind).toBe("fixed");
    expect(camera.position[0]).toBeCloseTo(1.5);
    expect(camera.position[2]).toBeGreaterThan(layout.edge);
    expect(camera.target).toEqual([expect.closeTo(1.5), expect.any(Number), 0]);
    const along = footballCamera(layout, 0.3);
    expect([along.position[0], along.target[0]]).toEqual([expect.closeTo(1.8), expect.closeTo(1.8)]);
  });
});

describe("keeperGaze", () => {
  it("looks straight up the pitch at a ball in front of its goal, and down at the turf", () => {
    const front = keeperGaze(0, { x: 0.42, y: 0.2, z: 0 }, { x: 1.5, y: 0.035, z: 0 });
    expect(front.yaw).toBeCloseTo(0);
    expect(front.pitch).toBeLessThan(0);
    const other = keeperGaze(1, { x: 2.58, y: 0.2, z: 0 }, { x: 1.5, y: 0.035, z: 0 });
    expect(other.yaw).toBeCloseTo(0);
    expect(other.pitch).toBeCloseTo(front.pitch);
  });

  it("turns its head the way the ball is, in its own frame, both keepers alike", () => {
    // A keeper's forward in the venue once its head turns `yaw` (judges.js): +x
    // turned about +y, and keeper 1's turned round to face -x.
    const forward = (k, yaw) => new Vector3(Math.cos(yaw), 0, -Math.sin(yaw)).multiplyScalar(k === 0 ? 1 : -1);
    for (const [k, eye] of [[0, { x: 0.42, y: 0.2, z: 0.1 }], [1, { x: 2.58, y: 0.2, z: -0.1 }]]) {
      for (const ball of [{ x: 1.2, y: 0.035, z: -0.4 }, { x: 1.9, y: 0.035, z: 0.5 }, { x: 1.5, y: 0.035, z: 0 }]) {
        const { yaw } = keeperGaze(k, eye, ball);
        const toBall = new Vector3(ball.x - eye.x, 0, ball.z - eye.z).normalize();
        expect(forward(k, yaw).angleTo(toBall)).toBeLessThan(1e-6);
      }
    }
  });

  it("never turns farther than its neck lets it", () => {
    const eye = { x: 0.42, y: 0.2, z: 0 };
    for (const ball of [{ x: 0.1, y: 0.035, z: 0.3 }, { x: 0.1, y: 0.035, z: -0.3 }, { x: 0.45, y: 3, z: 0 }]) {
      for (const k of [0, 1]) {
        const { yaw, pitch } = keeperGaze(k, eye, ball);
        expect(Math.abs(yaw)).toBeLessThanOrEqual(1);
        expect(Math.abs(pitch)).toBeLessThanOrEqual(0.5);
      }
    }
  });
});

describe("ballGeometry", () => {
  it("is the ball's size, white but for a black panel round each of twelve points, a face one colour", () => {
    const geometry = ballGeometry(0.035);
    geometry.computeBoundingSphere();
    expect(geometry.boundingSphere.radius).toBeCloseTo(0.035, 4);
    const [colours, position] = [geometry.getAttribute("color"), geometry.getAttribute("position")];
    expect(colours.count).toBe(position.count);
    const corner = (i) => new Vector3().fromBufferAttribute(position, i);
    let [black, total] = [0, 0];
    for (let f = 0; f < colours.count / 3; f++) {
      const shades = [0, 1, 2].map((v) => colours.getX(3 * f + v));
      expect(new Set(shades).size).toBe(1);
      const area = new Triangle(corner(3 * f), corner(3 * f + 1), corner(3 * f + 2)).getArea();
      total += area;
      if (shades[0] < 0.1) black += area;
    }
    // A football's twelve pentagons are 28% of it.
    expect(black / total).toBeCloseTo(0.28, 2);
    geometry.dispose();
  });
});

// The official Reachy Mini the jury is (judges.test.js), which the keepers are clones of.
const SHELL = ["body_down_3dprint_material", "body_top_3dprint_material"];
let model;
beforeAll(async () => {
  const bytes = readFileSync("public/robot/reachy-mini/reachy-mini.glb");
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  model = (await new GLTFLoader().parseAsync(buffer, "")).scene;
});
const meshes = (object) => {
  const found = [];
  object.traverse((node) => node.isMesh && found.push(node));
  return found;
};
const shells = (object) => meshes(object).filter((mesh) => SHELL.includes(mesh.material.name));

describe("keeperRobot", () => {
  it("is the Reachy Mini with its shell in the keeper's colour, the model's own left as it was", () => {
    const before = shells(model).map((mesh) => mesh.material.color.getHex());
    const materials = [];
    const robot = keeperRobot(model, KEEPER_TINTS[1], materials);
    expect(materials).toHaveLength(2);
    expect(shells(robot).map((mesh) => mesh.material.color.getHex())).toEqual([KEEPER_TINTS[1], KEEPER_TINTS[1]]);
    expect(shells(robot).every((mesh) => materials.includes(mesh.material))).toBe(true);
    expect(shells(model).map((mesh) => mesh.material.color.getHex())).toEqual(before);
    materials.forEach((material) => material.dispose());
  });

  it("shares the model's geometry and the rest of its materials, as the jury's clones do, and its head", () => {
    const robot = keeperRobot(model, KEEPER_TINTS[0], []);
    const [mine, its] = [meshes(robot), meshes(model)];
    expect(mine).toHaveLength(its.length);
    mine.forEach((mesh, i) => {
      expect(mesh.geometry).toBe(its[i].geometry);
      if (!SHELL.includes(mesh.material.name)) expect(mesh.material).toBe(its[i].material);
    });
    const head = robot.getObjectByName("reachy_head");
    expect(head).not.toBe(model.getObjectByName("reachy_head"));
    expect(head.getObjectByName("antenna_right")).toBeTruthy();
    expect(head.getObjectByName("antenna_left")).toBeTruthy();
  });
});

describe("buildFootballVenue", () => {
  const at = (v) => v.toArray().map((x) => expect.closeTo(x));
  const worldOf = (object) => object.getWorldPosition(new Vector3());

  it("lays the boards and the nets where the physics has them, its +y the venue's -z", () => {
    const venue = buildFootballVenue(event());
    venue.group.updateMatrixWorld(true);
    const far = bounds(venue.group.getObjectByName("side0"));
    expect([far.min.x, far.max.x, far.min.z, far.max.z]).toEqual([0.65, 2.35, -0.8, -0.75].map((x) => expect.closeTo(x)));
    // Glass, under its cap.
    expect(far.max.y).toBeCloseTo(0.2 - 0.012);
    const back = bounds(venue.group.getObjectByName("goal1_back"));
    expect([back.min.x, back.max.x, back.max.y]).toEqual([2.8, 2.81, 0.3].map((x) => expect.closeTo(x)));
    for (let s = 0; s < 10; s++) expect(venue.group.getObjectByName(`turf-${s}`)).toBeTruthy();
    expect([venue.length, venue.edge, venue.lift]).toEqual([expect.closeTo(3), expect.closeTo(1.05), 0]);
    venue.dispose();
  });

  it("gives the stadium a ground the length of the course and its overrun, the floor's span wide", () => {
    const venue = buildFootballVenue(event());
    const ground = venue.group.getObjectByName("ground");
    expect(ground.geometry.parameters.width).toBeCloseTo(3 + 2 * OVERRUN);
    expect(ground.geometry.parameters.height).toBeCloseTo(2 * venue.edge);
    expect(ground.position.x).toBeCloseTo(1.5);
    venue.dispose();
  });

  it("keeps the pitch, its goals and its keepers on the floor the stadium is built round", () => {
    const venue = buildFootballVenue(event({ rows: [[0, 0, 0.14, -0.14]] }), model);
    venue.pose([], 3);
    venue.group.updateMatrixWorld(true);
    venue.group.traverse((node) => {
      if (!(node.isMesh || node.isLineSegments) || node.name === "ground") return;
      const { min, max } = bounds(node);
      expect(min.x).toBeGreaterThanOrEqual(-1e-6);
      expect(max.x).toBeLessThanOrEqual(3 + 1e-6);
      expect(min.z).toBeGreaterThanOrEqual(-venue.edge);
      expect(max.z).toBeLessThanOrEqual(venue.edge);
    });
    venue.dispose();
  });

  it("puts the ball where the props have it: on the centre spot through the settle, then where the play took it", () => {
    const venue = buildFootballVenue(event({ rows: [[0.5, -0.3], [0.6, 0.2]] }));
    const ball = venue.group.getObjectByName("ball");
    const after = (index) => {
      venue.pose([], index);
      venue.group.updateMatrixWorld(true);
      return worldOf(ball).toArray();
    };
    expect(after(2)).toEqual(at(new Vector3(1.5, 0.035, 0)));
    expect(after(3)).toEqual(at(new Vector3(2, 0.035, 0.3)));
    expect(after(90)).toEqual(at(new Vector3(2.1, 0.035, -0.2)));
    venue.dispose();
  });

  it("stands a keeper on a rail across each goal's mouth, in its colour, facing up the pitch", () => {
    const venue = buildFootballVenue(event({ rows: [[0, 0, 0.1, -0.05]] }), model);
    venue.pose([], 3);
    venue.group.updateMatrixWorld(true);
    const keepers = [0, 1].map((k) => venue.group.getObjectByName(`keeper-${k}`));
    // Along its rail: the physics' +y is the venue's -z.
    expect(worldOf(keepers[0]).toArray()).toEqual(at(new Vector3(0.42, 0.004, -0.1)));
    expect(worldOf(keepers[1]).toArray()).toEqual(at(new Vector3(2.58, 0.004, 0.05)));
    keepers.forEach((keeper, k) => {
      const ahead = new Vector3(1, 0, 0).transformDirection(keeper.matrixWorld);
      expect(ahead.x).toBeCloseTo(k === 0 ? 1 : -1);
      expect(shells(keeper).map((mesh) => mesh.material.color.getHex())).toEqual([KEEPER_TINTS[k], KEEPER_TINTS[k]]);
      const [body, rail] = [bounds(keeper), bounds(venue.group.getObjectByName(`rail-${k}`))];
      expect(body.min.y).toBeCloseTo(rail.max.y, 3);
      expect([rail.min.z, rail.max.z]).toEqual([-0.22, 0.22].map((x) => expect.closeTo(x)));
      // Between the posts, in front of the net and astride the goal line.
      expect(body.min.z).toBeGreaterThan(-0.3);
      expect(body.max.z).toBeLessThan(0.3);
      const line = k === 0 ? 0.4 : 2.6;
      expect(body.min.x).toBeLessThan(line);
      expect(body.max.x).toBeGreaterThan(line);
      expect(k === 0 ? body.min.x : 3 - body.max.x).toBeGreaterThan(0.2);
    });
    venue.dispose();
  });

  it("turns each keeper's head to watch the ball", () => {
    const venue = buildFootballVenue(event({ rows: [[0.5, -0.3, 0.05, -0.05]] }), model);
    venue.pose([], 3);
    venue.group.updateMatrixWorld(true);
    const ball = worldOf(venue.group.getObjectByName("ball"));
    const level = (v) => new Vector3(v.x, 0, v.z).normalize();
    for (const k of [0, 1]) {
      const head = venue.group.getObjectByName(`keeper-${k}`).getObjectByName("reachy_head");
      const ahead = new Vector3(1, 0, 0).transformDirection(head.matrixWorld);
      expect(level(ahead).angleTo(level(ball.clone().sub(worldOf(head))))).toBeLessThan(0.05);
    }
    venue.dispose();
  });

  it("follows the ball along the pitch with the camera", () => {
    const venue = buildFootballVenue(event({ rows: [...still(100), ...still(100, 1)] }));
    expect(venue.camera.position[0]).toBeCloseTo(1.5);
    venue.pose([], 150);
    expect([venue.camera.position[0], venue.camera.target[0]]).toEqual([expect.closeTo(2.05), expect.closeTo(2.05)]);
    venue.pose([], 0);
    expect(venue.camera.position[0]).toBeCloseTo(1.5);
    venue.dispose();
  });

  it("stands the ducks' world frame on the centre spot", () => {
    const venue = buildFootballVenue(event());
    const rig = { placer: new Group() };
    rig.placer.rotation.set(0.1, 0.2, 0.3);
    venue.place(rig);
    expect(rig.placer.position.toArray()).toEqual([expect.closeTo(1.5), 0, 0]);
    expect([rig.placer.rotation.x, rig.placer.rotation.y, rig.placer.rotation.z]).toEqual([0, 0, 0]);
    venue.dispose();
  });

  it("builds without the Reachy Mini's model: the rails, but no keepers", () => {
    const venue = buildFootballVenue(event({ rows: [[0, 0]] }));
    expect(venue.group.getObjectByName("keeper-0")).toBeUndefined();
    expect(venue.group.getObjectByName("rail-1")).toBeTruthy();
    expect(() => venue.pose([], 3)).not.toThrow();
    venue.dispose();
  });

  it("has the crowd cheer a goal", () => {
    const play = event({ rows: Array.from({ length: 100 }, (_, f) => [0.0121 * (f + 1), 0]), scorer: 0, end: "goal" });
    const mood = buildFootballVenue(play).direction();
    expect(mood(play.horn_s - 0.02).action).toBe(0);
    expect(mood(play.decided_s + 0.2).joy).toBeGreaterThan(0.9);
  });

  it("disposes of everything it made and leaves the scene, but not the model the jury shares", () => {
    const venue = buildFootballVenue(event(), model);
    const scene = new Group();
    scene.add(venue.group);
    const keepers = new Set();
    for (const k of [0, 1]) venue.group.getObjectByName(`keeper-${k}`).traverse((node) => keepers.add(node));
    const [owned, shared] = [[], []];
    venue.group.traverse((node) => {
      if (!(node.isMesh || node.isLineSegments)) return;
      const keeper = keepers.has(node);
      (keeper ? shared : owned).push(vi.spyOn(node.geometry, "dispose"));
      for (const material of [node.material].flat()) {
        (keeper && !SHELL.includes(material.name) ? shared : owned).push(vi.spyOn(material, "dispose"));
      }
    });
    venue.dispose();
    expect(venue.group.parent).toBe(null);
    owned.forEach((dispose) => expect(dispose).toHaveBeenCalled());
    shared.forEach((dispose) => expect(dispose).not.toHaveBeenCalled());
  });
});

// The crowd's lighter model as the viewer hands it on (viewer.js), a box for
// each of its meshes, as the stadium's own tests seat their crowd.
const kinematics = JSON.parse(readFileSync("public/robot/kinematics.json", "utf8"));
const spectators = () => ({
  kinematics,
  geometries: new Map(meshNames(kinematics).map((name) => [name, new BoxGeometry(0.01, 0.01, 0.01)])),
});

describe("the stands behind the goals", () => {
  // A crowd draws its speech bubbles on canvases (crowd-bubbles.js), which node has none of.
  beforeAll(() => {
    const pen = { beginPath() {}, roundRect() {}, fill() {}, stroke() {}, moveTo() {}, lineTo() {}, fillText() {} };
    vi.stubGlobal("document", { createElement: () => ({ getContext: () => pen }) });
  });
  afterAll(() => vi.unstubAllGlobals());

  const built = (seated = spectators()) => {
    const venue = buildFootballVenue(event(), null, seated);
    venue.group.updateMatrixWorld(true);
    return venue;
  };
  const ends = (venue) => venue.group.getObjectByName("end-stands");
  const stands = (venue) => ends(venue).children.filter((child) => child.name === "stand");
  const solids = (root) => {
    const found = [];
    root.traverse((node) => node.isMesh && !node.isInstancedMesh && found.push(bounds(node)));
    return found;
  };
  /** Every spectator the crowd draws, where it stands in the venue. */
  const crowdOf = (venue) =>
    venue.crowd.group.children.flatMap((mesh) =>
      Array.from({ length: mesh.count }, (_, k) => {
        const matrix = new Matrix4();
        mesh.getMatrixAt(k, matrix);
        matrix.premultiply(mesh.matrixWorld);
        return { mesh, k, matrix, at: new Vector3().setFromMatrixPosition(matrix) };
      }),
    );
  const standing = ({ mesh, k }) => mesh.morphTexture.source.data.data[2 * k + 1];
  const end = ({ at }) => Math.sign(at.x - 1.5);

  it("seats no one behind the goals without the crowd's model", () => {
    const venue = buildFootballVenue(event(), model);
    expect(ends(venue)).toBeUndefined();
    expect(venue.crowd).toBeUndefined();
    venue.dispose();
  });

  it("stands one beyond each end, mirrored, wider than the pitch and inside the floor, short of the hall's end walls", () => {
    const venue = built();
    expect(stands(venue)).toHaveLength(2);
    const [low, high] = stands(venue).map(bounds).sort((a, b) => a.min.x - b.min.x);
    expect(low.max.x).toBeLessThan(0);
    expect(high.min.x).toBeGreaterThan(3);
    expect(high.min.x).toBeCloseTo(3 - low.max.x);
    expect(high.max.x).toBeCloseTo(3 - low.min.x);
    for (const one of [low, high]) {
      expect(one.min.z).toBeCloseTo(-one.max.z);
      // Past the boards, which wall the pitch in at 0.8 either side of its axis.
      expect(one.max.z).toBeGreaterThan(0.8);
      expect(one.max.z).toBeLessThan(venue.edge);
    }
    // gym.js: the hall's end walls are 2 m beyond the course's ends, and the
    // timber rail along them stands 0.105 proud of their line.
    expect(high.max.x).toBeLessThan(3 + 2 - 0.105);
    expect(low.min.x).toBeGreaterThan(-2 + 0.105);
    ends(venue).traverse((node) => node.isMesh && expect(node.castShadow).toBe(true));
    venue.dispose();
  });

  it("keeps clear of the stadium the viewer hangs round the venue, whose rails and cones run on past its ends", () => {
    const venue = built();
    const stadium = attachStadium(venue.group, spectators(), venue.camera.position[2]);
    venue.group.updateMatrixWorld(true);
    const theirs = solids(stadium.group);
    expect(theirs.length).toBeGreaterThan(0);
    for (const part of stands(venue).flatMap(solids)) {
      for (const other of theirs) expect(part.intersectsBox(other)).toBe(false);
    }
    stadium.dispose();
    venue.dispose();
  });

  it("seats a crowd on every tier, none on the pitch's axis, each spectator facing the pitch", () => {
    const venue = built();
    const all = crowdOf(venue);
    expect(all).toHaveLength(96);
    const tiers = stands(venue).flatMap((stand) => stand.children.filter((child) => child.name === "tier").map(bounds));
    expect(tiers).toHaveLength(12);
    const seated = new Set();
    for (const { matrix, at } of all) {
      // crowd splits its flocks by which side of the axis a seat is on.
      expect(Math.abs(at.z)).toBeGreaterThan(0.05);
      const under = tiers.findIndex(({ min, max }) => min.x < at.x && at.x < max.x && min.z < at.z && at.z < max.z);
      expect(under).toBeGreaterThanOrEqual(0);
      seated.add(under);
      // On the deck, bobbing no higher than a seated spectator does.
      expect(at.y - tiers[under].max.y).toBeGreaterThan(-1e-6);
      expect(at.y - tiers[under].max.y).toBeLessThan(0.0061);
      const ahead = new Vector3(1, 0, 0).transformDirection(matrix);
      expect(ahead.x * -end({ at })).toBeGreaterThan(0.99);
    }
    expect(seated.size).toBe(12);
    venue.dispose();
  });

  it("rises in the wave as it sweeps the stadium along the pitch, one end and then the other", () => {
    const venue = built();
    const risen = {};
    for (let t = 0; t <= 14; t += 0.05) {
      venue.crowd.pose(t);
      const up = crowdOf(venue).filter((one) => standing(one) > 0.9);
      for (const side of [-1, 1]) {
        // Most of an end at once: a spectator having its say rises alone (crowdStanding).
        if (risen[side] === undefined && up.filter((one) => end(one) === side).length >= 24) risen[side] = t;
      }
    }
    expect(risen[-1]).toBeDefined();
    expect(risen[1]).toBeDefined();
    // The first wave runs from the low end of x to the high, or back (olaAt).
    const first = olaAt(0).reverse ? 1 : -1;
    expect(risen[first]).toBeLessThan(risen[-first]);
    venue.dispose();
  });

  it("keeps, for the camera about to render, only the seats it can see, and gives every seat back after", () => {
    const venue = built();
    const before = crowdOf(venue);
    const camera = new PerspectiveCamera(40, 16 / 9, 0.02, 50);
    camera.position.set(1.5, 0.5, 0);
    camera.lookAt(10, 0.5, 0);
    camera.updateMatrixWorld();
    venue.crowd.cull(camera);
    const shown = crowdOf(venue);
    expect(shown).toHaveLength(48);
    for (const one of shown) expect(end(one)).toBe(1);
    venue.crowd.restore();
    const after = crowdOf(venue);
    expect(after).toHaveLength(96);
    after.forEach(({ matrix }, i) => expect(matrix.equals(before[i].matrix)).toBe(true));
    venue.dispose();
  });

  it("disposes of the stands and their crowd, but not the model the viewer seats every crowd with", () => {
    const seated = spectators();
    const venue = built(seated);
    const owned = [];
    ends(venue).traverse((node) => {
      if (node.isMesh) owned.push(vi.spyOn(node.geometry, "dispose"), vi.spyOn(node.material, "dispose"));
    });
    const shared = [...seated.geometries.values()].map((geometry) => vi.spyOn(geometry, "dispose"));
    venue.dispose();
    owned.forEach((dispose) => expect(dispose).toHaveBeenCalled());
    shared.forEach((dispose) => expect(dispose).not.toHaveBeenCalled());
  });
});

describe("footballDirection", () => {
  const horn = 0.48;
  const decided = 4.5;
  it("is silent before the horn and up once it has gone", () => {
    const mood = footballDirection({ horn_s: horn, decided_s: decided, scorer: 0, end: "goal" });
    expect(mood(0.2).action).toBe(0);
    expect(mood(horn + 0.5).action).toBeGreaterThan(0.7);
  });

  it("cheers a goal, and one given for a fault, and mourns a play both ducks went down in", () => {
    for (const end of ["goal", "fault"]) {
      const scored = footballDirection({ horn_s: horn, decided_s: decided, scorer: 1, end })(decided + 0.2);
      expect(scored.joy).toBeGreaterThan(0.9);
      expect(scored.sadness).toBe(0);
    }
    const down = footballDirection({ horn_s: horn, decided_s: decided, scorer: null, end: "down" })(decided + 0.2);
    expect(down.sadness).toBeGreaterThan(0.9);
    expect(down.joy).toBe(0);
  });

  it("feels nothing about the whistle, two faults or a void play", () => {
    for (const end of ["whistle", "fault", "void"]) {
      const mood = footballDirection({ horn_s: horn, decided_s: decided, scorer: null, end });
      for (const second of [decided - 0.5, decided, decided + 1]) {
        expect(mood(second).joy).toBe(0);
        expect(mood(second).sadness).toBe(0);
      }
    }
  });

  it("builds as the ball nears a goal", () => {
    const near = (value) =>
      footballDirection({ horn_s: horn, decided_s: decided, end: "whistle", progress: [{ second: horn, value }, { second: decided, value }] })(2);
    expect(near(1).action).toBeGreaterThan(near(0).action);
  });

  it("never asks the stadium for a decision before the horn", () => {
    const early = { horn_s: 1, decided_s: 0.5, scorer: 0, end: "goal", progress: [{ second: 1, value: 0.5 }] };
    expect(() => footballDirection(early)(1)).not.toThrow();
    expect(() => footballDirection()(0)).not.toThrow();
  });
});
