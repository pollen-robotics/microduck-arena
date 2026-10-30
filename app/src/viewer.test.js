import { Object3D, Spherical, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { CTRL_DT, TRACE_WIDTH } from "./replay.js";
import { tugPose } from "./tug.js";
import {
  cameraPose, chaseAcross, dragPose, inRoom, packChase, placeMarker, stageCamera, stageLanes, travelPose,
} from "./viewer.js";

describe("placeMarker", () => {
  it("lays a lane's ring on the course, just over it, under the feet", () => {
    const [ground, marker] = [new Object3D(), new Object3D()];
    placeMarker(marker, ground, new Vector3(0.05, 0.02, 0.01), 0);
    expect(marker.parent).toBe(ground);
    expect(marker.position.toArray()).toEqual([0.05, 0.004, 0.01]);
  });
});

describe("cameraPose", () => {
  it("chases the leader from behind and trackside by default, at the original close distance", () => {
    expect(cameraPose(null, 1.2, 1.15, 0)).toEqual({
      position: [1.2 - 0.35, 0.34, 1.15],
      target: [1.2, 0.12, 0],
    });
  });

  it("takes an event's chase constants and a pinned side", () => {
    const spec = { kind: "chase", back: 0.5, height: 0.6, side: 2, target_height: 0.2, fov: 40 };
    expect(cameraPose(spec, 0, 1.15, 0)).toEqual({ position: [-0.5, 0.6, 2], target: [0, 0.2, 0] });
  });

  it("backs a chase off by a distance factor for a narrower frame", () => {
    expect(cameraPose({ kind: "chase", distance: 2 }, 1, 1.15, 0).position).toEqual([1 - 0.7, 0.68, 2.3]);
  });

  it("climbs with the ramp under the leader, the chase and what it looks at alike", () => {
    expect(cameraPose(null, 1.2, 1.15, 0.17)).toEqual({ position: [1.2 - 0.35, 0.34 + 0.17, 1.15], target: [1.2, 0.12 + 0.17, 0] });
  });

  it("holds a fixed camera where the event put it", () => {
    const spec = { kind: "fixed", position: [1, 0.6, 2.2], target: [1, 0.1, 0], fov: 40 };
    expect(cameraPose(spec, 5, 1.15, 0.3)).toEqual({ position: [1, 0.6, 2.2], target: [1, 0.1, 0] });
  });

  it("centres a tracking chase across the lanes where it is told, the side offset kept", () => {
    expect(cameraPose(null, 1.2, 1.15, 0, -0.3)).toEqual({
      position: [1.2 - 0.35, 0.34, -0.3 + 1.15],
      target: [1.2, 0.12, -0.3],
    });
  });

  it("backs off to fit its lanes, rising with it so it looks down at them as steeply, never closer", () => {
    const spec = { kind: "chase", back: 2, height: 0.8, side: 0.1, target_height: 0.4, distance: 0.7 };
    const fitted = cameraPose(spec, 5, 1.15, 0, 0.2, 3);
    expect(fitted.position[0]).toBeCloseTo(5 - 3, 9);
    expect(fitted.position[1]).toBeCloseTo(0.8 * 1.5, 9);
    expect(fitted.position[2]).toBeCloseTo(0.2 + 0.1 * 1.5, 9);
    expect(fitted.target).toEqual([5, 0.4, 0.2]);
    expect(cameraPose(spec, 5, 1.15, 0, 0.2, 1)).toEqual(cameraPose(spec, 5, 1.15, 0, 0.2));
  });
});

describe("packChase", () => {
  const LANES = [-1.275, -0.425, 0.425, 1.275];
  const tan = (aspect) => Math.tan((42 * Math.PI) / 360) * aspect;
  // How far either side of its centre a pack chase sees across, where its hindmost duck walks.
  const sees = (pack, aspect) => pack.fit * tan(aspect);

  it("follows the hindmost duck, but leaves one more than 0.6 m behind the leader", () => {
    expect(packChase([3.9, 3.7, 4.2, 4], LANES, 16 / 9, 42).rear).toBe(3.7);
    expect(packChase([2, 3.5, 4.2, 2.6], LANES, 16 / 9, 42).rear).toBeCloseTo(3.6, 9);
    expect(packChase([5.9, 9.5, 9.1, 8.7], LANES, 16 / 9, 42).rear).toBeCloseTo(8.9, 9);
    // Left behind by a pan: the leader a step farther, the camera a step farther.
    const before = packChase([5.9, 8.9, 8.6, 8.7], LANES, 16 / 9, 42).rear;
    const after = packChase([5.9, 8.91, 8.6, 8.7], LANES, 16 / 9, 42).rear;
    expect(after - before).toBeCloseTo(0.01, 9);
  });

  it("stands back just far enough for a landscape picture to hold every lane, centred on them", () => {
    const pack = packChase([4, 5, 6, 4.5], LANES, 16 / 9, 42);
    expect(pack.across).toBeCloseTo(0, 9);
    expect(sees(pack, 16 / 9)).toBeCloseTo(1.275 + 0.3, 9);
    expect(pack.fit).toBeLessThan(3);
  });

  it("in a narrower picture stands no farther than three metres, and keeps the last lane's duck in it", () => {
    const aspect = 1080 / 1260;
    const pack = packChase([4, 5, 6, 4.5], LANES, aspect, 42);
    expect(pack.fit).toBe(3);
    expect(sees(pack, aspect)).toBeLessThan(1.275 + 0.3);
    expect(pack.across).toBeGreaterThan(0);
    expect(1.275 + 0.3 - pack.across).toBeCloseTo(sees(pack, aspect), 9);
  });
});

describe("inRoom", () => {
  const room = { back: -1.7, ceiling: 2 };
  const pitch = ({ position, target }) =>
    Math.atan2(position[1] - target[1], Math.hypot(position[0] - target[0], position[2] - target[2]));

  it("leaves a camera inside the room where it is, and any camera of a hall without one", () => {
    const pose = { position: [-1.4, 0.6, 0.1], target: [0, 0.4, 0] };
    expect(inRoom(pose, room)).toBe(pose);
    expect(inRoom({ position: [-9, 9, 0], target: [0, 0, 0] }, undefined).position).toEqual([-9, 9, 0]);
  });

  it("draws a camera beyond the wall behind the start in, looking at the same spot as steeply", () => {
    const pose = { position: [-2.4, 0.9, 0.3], target: [0, 0.4, 0] };
    const kept = inRoom(pose, room);
    expect(kept.position[0]).toBeCloseTo(-1.7, 9);
    expect(kept.target).toBe(pose.target);
    expect(pitch(kept)).toBeCloseTo(pitch(pose), 9);
  });

  it("draws a camera above the lamps down, and stops at whichever it meets first", () => {
    const kept = inRoom({ position: [-1.2, 4.4, 2], target: [0, 0.4, 0] }, room);
    expect(kept.position[1]).toBeCloseTo(2, 9);
    expect(kept.position[0]).toBeGreaterThan(-1.7);
    const both = inRoom({ position: [-3.4, 4.4, 0], target: [0, 0.4, 0] }, room);
    expect(both.position[0]).toBeGreaterThanOrEqual(-1.7 - 1e-9);
    expect(both.position[1]).toBeLessThanOrEqual(2 + 1e-9);
  });
});

describe("chaseAcross", () => {
  // A lane as the viewer holds it: a duck's trace, x and y at each step, and the placer that stands
  // its rig on the lane.
  const lane = (laneZ, at, seconds = 12) => {
    const frames = Math.round(seconds / CTRL_DT), trace = new Float32Array(frames * TRACE_WIDTH);
    for (let i = 0; i < frames; i++) {
      [trace[i * TRACE_WIDTH], trace[i * TRACE_WIDTH + 1]] = at(i * CTRL_DT);
      trace[i * TRACE_WIDTH + 3] = 1;
    }
    const placer = new Object3D();
    placer.position.z = laneZ;
    placer.updateMatrixWorld();
    return { trace, rig: { placer } };
  };

  it("centres on the line its leader walks: the trace's +y is the scene's -z, from its lane", () => {
    const walker = lane(0.85, (t) => [0.5 * t, 0.2]);
    for (const seconds of [0, 4, 12, 30]) expect(chaseAcross([walker], seconds)).toBeCloseTo(0.85 - 0.2, 6);
  });

  it("sees through a stride's sway, and follows a drift across the lane", () => {
    const swaying = lane(0, (t) => [0.5 * t, 0.1 + 0.04 * Math.sin((2 * Math.PI * t) / 0.37 + 1)]);
    for (const seconds of [2, 2.13, 2.27, 4.05]) expect(chaseAcross([swaying], seconds)).toBeCloseTo(-0.1, 2);
    const drifting = lane(0, (t) => [0.5 * t, 0.05 * t]);
    expect(chaseAcross([drifting], 4)).toBeCloseTo(-0.2, 2);
    expect(chaseAcross([drifting], 8)).toBeCloseTo(-0.4, 2);
  });

  it("follows the duck in the lead, and pans rather than cuts when another takes it", () => {
    // The near duck leads for five seconds, then the far one passes it.
    const near = lane(-0.425, (t) => [2.5 + 0.5 * t, 0]);
    const far = lane(0.425, (t) => [t, 0]);
    expect(chaseAcross([near, far], 2)).toBeCloseTo(-0.425, 6);
    expect(chaseAcross([near, far], 8)).toBeCloseTo(0.425, 6);
    const pan = [4.2, 4.6, 5, 5.4, 5.8].map((seconds) => chaseAcross([near, far], seconds));
    pan.forEach((z, i) => {
      expect(z).toBeGreaterThan(-0.425);
      expect(z).toBeLessThan(0.425);
      if (i) expect(z).toBeGreaterThan(pan[i - 1]);
    });
  });
});

describe("travelPose", () => {
  const chase = cameraPose({ kind: "chase", distance: 0.7 }, 0, 3.1, 0);
  const reach = (pose) => Math.hypot(pose.position[0] - pose.target[0], pose.position[2] - pose.target[2]);

  it("ends on the chase itself", () => {
    expect(travelPose(chase, 1)).toBe(chase);
  });

  it("starts ahead of the line, farther out, looking at the same spot", () => {
    const start = travelPose(chase, 0);
    expect(start.position[0]).toBeGreaterThan(chase.target[0]);
    expect(reach(start)).toBeGreaterThan(reach(chase));
    expect(start.target).toEqual(chase.target);
  });

  it("starts a race's travel eight times the chase's height over what it looks at, as it always has", () => {
    for (const distance of [0.7, 0.8]) {
      const race = cameraPose({ kind: "chase", distance }, 0, 1.15, 0);
      expect(travelPose(race, 0).position[1]).toBeCloseTo(0.12 + (0.34 * distance - 0.12) * 8, 12);
    }
  });

  it("keeps a tug's travel under the hall's lights, however far its fit stands out", () => {
    // The portrait clip's fit over a bout's first frame: about 2.3 m out (tug.js tugPose).
    const tug = tugPose(cameraPose({ kind: "chase" }, 0, 1.324, 0), 1.35, 1080 / 1233, 42);
    const start = travelPose(tug, 0).position[1];
    expect(start).toBeLessThanOrEqual(2);
    expect(start).toBeGreaterThan(tug.position[1]);
  });

  it("never comes closer to the ducks than the chase does", () => {
    for (let u = 0; u < 1; u += 0.1) expect(reach(travelPose(chase, u))).toBeGreaterThanOrEqual(reach(chase) - 1e-9);
  });
});

describe("dragPose", () => {
  const pose = cameraPose(null, 1.2, 1.15, 0.1);

  it("leaves the camera alone when nothing drags it", () => {
    expect(dragPose(pose, 0)).toBe(pose);
  });

  it("turns the camera round what it looks at, the way dragging right does", () => {
    const target = new Vector3(...pose.target);
    const orbit = new Spherical().setFromVector3(new Vector3(...pose.position).sub(target));
    orbit.theta -= 0.3; // OrbitControls' rotateLeft for a drag to the right
    const expected = new Vector3().setFromSpherical(orbit).add(target).toArray();
    const turned = dragPose(pose, 0.3);
    turned.position.forEach((value, i) => expect(value).toBeCloseTo(expected[i], 9));
    expect(turned.target).toBe(pose.target);
  });
});

describe("stageLanes", () => {
  const trace = new Float32Array(21);
  const duck = { trace, lead: 0, sound: null, rig: "legs", livery: "purple", start: { x: 0, y: 0, yaw: 0 }, star: false };

  it("puts every duck of the performance on the stage in duck order, each on its own rig, the star alone named", () => {
    const ducks = [{ ...duck, star: true }, { ...duck, rig: "rollers", livery: "classic", start: { x: 0.4, y: -0.6, yaw: 90 } }, duck];
    const lanes = stageLanes([{ runId: "r1", name: "alice", livery: "purple", tier: "ghost", colour: "#ff7a2f", ducks }]);
    expect(lanes.map((lane) => [lane.rig, lane.livery, lane.start, lane.name, lane.opacity])).toEqual([
      ["legs", "purple", duck.start, "alice", 1],
      ["rollers", "classic", { x: 0.4, y: -0.6, yaw: 90 }, undefined, 1],
      ["legs", "purple", duck.start, undefined, 1],
    ]);
  });
});

describe("stageCamera", () => {
  // A duck wandering about the stage as the runner traces it, every 20 ms after a 0.5 s settle: its
  // trunk upright at x, y, which sway with its gait, kept on the stage.
  const wander = ([x, y, ax, ay, wx, wy, px, py]) => {
    const frames = Math.round((0.5 + 20) / CTRL_DT), trace = new Float32Array(frames * TRACE_WIDTH);
    for (let i = 0; i < frames; i++) {
      const t = Math.max(0, i * CTRL_DT - 0.5);
      trace[i * TRACE_WIDTH] = x + ax * Math.sin(wx * t + px) + 0.02 * Math.sin(4 * Math.PI * t);
      trace[i * TRACE_WIDTH + 1] = Math.min(1.8, y + ay * Math.sin(wy * t + py)) + 0.03 * Math.sin(2 * Math.PI * t);
      trace[i * TRACE_WIDTH + 3] = 1;
    }
    return trace;
  };
  // Placed as a duck with a start is (talent-stage.js placeStageDuck).
  const placer = new Object3D();
  placer.rotation.set(0, Math.PI / 2, 0);
  placer.updateMatrixWorld();
  // A pair found among sixty random troupes: fitted to where it stands at each frame alone, the jury
  // shot's camera jumped 2.6 m at 11.1 s.
  const lanes = [[-0.73, 1.46, 0.18, 0.65, 0.31, 0.19, 0.64, 1.12], [-0.46, -0.97, 0.24, 0.7, 0.18, 0.33, 5.92, 1.06]]
    .map((path) => ({ trace: wander(path), rig: { placer } }));
  const layout = { depth: 2.6, width: 3.8 };

  it.each([16 / 9, 9 / 16])("glides within every shot of a troupe on the move, at aspect %s", (aspect) => {
    const shoot = stageCamera(lanes, layout, () => 0);
    let previous = shoot(0, 0, aspect, 42);
    for (let frame = 1; frame <= 24 * 30; frame++) {
      const pose = shoot(frame / 30, frame / 30, aspect, 42);
      if (pose.shot === previous.shot) {
        expect(new Vector3(...pose.position).distanceTo(new Vector3(...previous.position))).toBeLessThan(0.05);
      }
      previous = pose;
    }
  });

  it("reads where the troupe stands only as a shot begins: each shot is planned once", () => {
    let asked = 0;
    const shoot = stageCamera(lanes, layout, () => {
      asked += 1;
      return 0;
    });
    let shot = null;
    for (let frame = 0; frame <= 24 * 30; frame++) {
      const before = asked;
      const pose = shoot(frame / 30, frame / 30, 16 / 9, 42);
      if (pose.shot === shot) expect(asked).toBe(before);
      shot = pose.shot;
    }
    expect(asked).toBeGreaterThan(0);
  });
});
