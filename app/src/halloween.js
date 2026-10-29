// Halloween week, 2026: the ducks in costume, their venues haunted, the pages decorated. The clip
// page never asks for any of it, so no video wears it, and it all goes away by itself when the
// week does. The costumes and the props are modelled by scripts/halloween_wardrobe.py into
// /robot/halloween.glb: each costume a node over one child per body it rides (extras `body`), each
// prop a node standing on its origin, facing its own +x, z up.

import { Group } from "three";

export const HALLOWEEN = Date.now() < Date.UTC(2026, 10, 7);

/** The pages' decorations: halloween.css dresses them under `html.halloween`, and what flies over
 * every view — three bats now and then, a spider down its thread — is a layer of its own. */
export function decoratePage() {
  document.documentElement.classList.add("halloween");
  const make = (tag, className, ...children) => {
    const made = document.createElement(tag);
    made.className = className;
    made.append(...children);
    return made;
  };
  const layer = make("div", "haunt");
  layer.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 3; i++) {
    const beat = make("span", "haunt-flap", ...["haunt-wing-left", "haunt-body", "haunt-wing-right"].map((part) => make("i", part)));
    layer.append(make("span", "haunt-bat", make("span", "haunt-flight", beat)));
  }
  layer.append(make("span", "haunt-spider"));
  document.body.append(layer);
}

const node = (wardrobe, kind, name) => wardrobe.children.find((child) => child.userData[kind] === name);

/** Hang one of the wardrobe's costumes on a rig: each piece rides the body it was fitted to. A
 * ghost's costume is dimmed with it. */
export function dress(rig, wardrobe, costume, opacity = 1) {
  for (const holder of node(wardrobe, "costume", costume).children) {
    for (const piece of holder.children) {
      const worn = piece.clone();
      if (opacity < 1) {
        worn.material = worn.material.clone();
        Object.assign(worn.material, { transparent: true, opacity });
      }
      rig.bodies.get(holder.userData.body).add(worn);
    }
  }
}

/** A prop at `at`, turned `turn` about the vertical: on a y-up scene 0 faces +x and -π/2 faces +z;
 * `upright` on a z-up set, the booth's, where it stands as modelled. */
function prop(wardrobe, name, at, { scale = 1, turn = 0, upright = false } = {}) {
  const made = node(wardrobe, "prop", name).clone();
  made.position.set(...at);
  made.scale.setScalar(scale);
  // Turned about its own vertical first, then stood y up; the booth's set is z up already.
  made.rotation.set(upright ? 0 : -Math.PI / 2, 0, turn);
  made.traverse((part) => {
    if (part.isMesh) part.castShadow = part.receiveShadow = true;
  });
  return made;
}

/** Bats circling round `centre` and flapping as they go, level in a y-up scene or an `upright` set;
 * `squash` flattens the circle across into an ellipse, `phase` starts the flock further round it and
 * `pace` hurries it. */
function bats(wardrobe, group, centre, count, { radius = 0.5, squash = 1, scale = 1.3, upright = false, phase: start = 0, pace = 1 } = {}) {
  const flock = Array.from({ length: count }, (_, i) => {
    const bat = prop(wardrobe, "bat", centre, { scale, upright });
    group.add(bat);
    const wings = [];
    bat.traverse((part) => part.userData.wing && wings.push(part));
    return { bat, wings, phase: start + (2 * Math.PI * i) / count, reach: radius * (0.7 + 0.3 * ((i * 7) % 3) / 2), speed: pace * (0.7 + 0.1 * (i % 3)) };
  });
  return (seconds) => {
    for (const { bat, wings, phase, reach, speed } of flock) {
      const angle = phase + seconds * speed;
      const lift = 0.05 * Math.sin(seconds * 1.7 + phase) * (upright ? 0.6 : 1);
      const [along, across] = [reach * Math.cos(angle), reach * squash * Math.sin(angle)];
      // Heading along the path: its tangent, turned into the bat's own +x.
      const heading = Math.atan2(squash * Math.cos(angle), -Math.sin(angle));
      if (upright) {
        bat.position.set(centre[0] + along, centre[1] + across, centre[2] + lift);
        bat.rotation.z = heading;
      } else {
        bat.position.set(centre[0] + along, centre[1] + lift, centre[2] + across);
        bat.rotation.z = -heading;
      }
      for (const wing of wings) wing.rotation.x = wing.userData.wing * 0.7 * Math.sin(seconds * 14 + phase);
    }
  };
}

// Facing the camera, which stands on the +z side of every venue but the stage.
const NEAR = -Math.PI / 2;

/** A ghost floating at `at`, bobbing and swaying, facing `turn`. */
function ghost(wardrobe, group, at, phase, turn = NEAR) {
  const made = prop(wardrobe, "ghost", at, { scale: 1.2, turn });
  made.traverse((part) => { part.castShadow = false; });
  group.add(made);
  return (seconds) => {
    made.position.y = at[1] + 0.04 * Math.sin(seconds * 1.3 + phase);
    made.rotation.z = turn + 0.25 * Math.sin(seconds * 0.6 + phase);
  };
}

function haunted(group, movers) {
  return { group, pose: (seconds) => movers.forEach((move) => move(seconds)) };
}

/**
 * A race's track, `length` along +x from the start line and `span` across: lanterns along its far
 * side and at both its lines, gravestones among them, ghosts over the far stand, bats over the
 * track at `flight` up — in a hall, over a camera at a duck's height; under a playground's sky, over
 * one that films from behind the ducks and higher than they are. On the floor, so a ramp climbs past.
 */
export function hauntTrack(wardrobe, length, span, flight = 0.75) {
  const group = new Group();
  // Just off the track's far edge, in front of the stadium's barrier.
  const far = -span / 2 - 0.07;
  for (let x = -0.3, k = 0; x <= length + 0.31; x += 0.5, k++) {
    group.add(prop(wardrobe, "jack", [x, 0, far - (k % 2) * 0.03], { scale: k % 2 ? 1.6 : 1.15, turn: NEAR + 0.3 * Math.sin(k * 2.1) }));
  }
  for (const x of [-0.25, length + 0.25]) {
    group.add(prop(wardrobe, "jack", [x, 0, span / 2 + 0.14], { scale: 1.3, turn: NEAR }));
  }
  [0.2, length / 2 + 0.05, length - 0.25].forEach((x, k) => {
    group.add(prop(wardrobe, "tombstone", [x, 0, far - 0.12], { scale: 1.4, turn: NEAR + 0.25 * (k - 1) }));
  });
  return haunted(group, [
    ghost(wardrobe, group, [length * 0.3, 0.55, far - 0.5], 0),
    ghost(wardrobe, group, [length * 0.8, 0.65, far - 0.6], 2),
    bats(wardrobe, group, [length * 0.25, flight, -0.2], 4),
    bats(wardrobe, group, [length * 0.75, flight + 0.1, -0.3], 4),
  ]);
}

/** The talent stage, `width` across and `depth` deep, the audience towards -z: lanterns and candles
 * at its front corners, a cauldron and a grave at the back ones, a ghost and bats over it. */
export function hauntStage(wardrobe, { width, depth }) {
  const group = new Group();
  const [x, z] = [width / 2 - 0.2, depth / 2 - 0.2];
  const audience = Math.PI / 2;
  for (const side of [-1, 1]) {
    group.add(prop(wardrobe, "jack", [side * x, 0, -z], { scale: 1.6, turn: audience - side * 0.3 }));
    group.add(prop(wardrobe, "jack", [side * (x - 0.17), 0, -z + 0.05], { scale: 1.0, turn: audience }));
    group.add(prop(wardrobe, "candles", [side * (x + 0.05), 0, -z + 0.16], { scale: 1.6 }));
  }
  group.add(prop(wardrobe, "cauldron", [-x, 0, z], { scale: 1.8 }));
  group.add(prop(wardrobe, "tombstone", [x, 0, z], { scale: 1.5, turn: audience - 0.3 }));
  group.add(prop(wardrobe, "tombstone", [x - 0.28, 0, z + 0.06], { scale: 1.2, turn: audience + 0.2 }));
  return haunted(group, [
    ghost(wardrobe, group, [x - 0.1, 0.6, z - 0.1], 1, audience),
    bats(wardrobe, group, [0, 1.3, 0], 5, { radius: 0.9 }),
  ]);
}

/** The tug's ring, its canvas at y 0, `half` to its posts, the hall's floor `floor` below: a
 * lantern at each corner of the apron, graves ringside on the far side, a ghost and bats over all. */
export function hauntRing(wardrobe, half, floor) {
  const group = new Group();
  const corner = half + 0.05;
  for (const x of [-1, 1]) {
    for (const z of [-1, 1]) group.add(prop(wardrobe, "jack", [x * corner, 0, z * corner], { scale: 1.3, turn: NEAR - x * 0.4 }));
  }
  [-0.9, 0.15, 1.0].forEach((x, k) => {
    group.add(prop(wardrobe, "tombstone", [x, floor, -half - 0.45], { scale: 1.6, turn: NEAR + 0.2 * (k - 1) }));
  });
  return haunted(group, [
    ghost(wardrobe, group, [-0.5, 0.75, -half - 0.6], 0),
    bats(wardrobe, group, [0, 1.1, 0], 6, { radius: 1.1, scale: 1.6 }),
  ]);
}

/**
 * Peter and Ray's booth, in its set's own frame, z up, the cameras towards -y: a lantern, candles and
 * a string of lights on the desk, another lantern on the case; skulls, potions and cauldrons on the
 * two shelves behind the duo, HAPPY HALLOWEEN on the `pegboard` between them (hidden with it when the
 * cup's screen stands there), webs in the wall's top corners, a bat hanging asleep under each shelf,
 * a spider going up and down its thread, and a bat flitting in front of each shelf, clear of the
 * sign, the duo's heads and the wall.
 */
export function hauntBooth(wardrobe, pegboard) {
  const group = new Group();
  const front = -Math.PI / 2;
  const on = (name, at, { turn = 0, ...rest } = {}) => {
    const made = prop(wardrobe, name, at, { upright: true, turn: front + turn, ...rest });
    group.add(made);
    return made;
  };
  // The desk's top is at z 0.084, its apron's face at y -0.171 and its top edge at z 0.064.
  on("jack", [0, -0.12, 0.084], { scale: 0.75 });
  for (const x of [-0.26, 0.26]) on("candles", [x, -0.13, 0.084], { scale: 0.75, turn: x * 2 });
  on("garland", [0, -0.173, 0.063]);
  on("jack", [0.45, 0.24, 0.152], { scale: 0.9, turn: 0.4 });
  // The shelves: the light brackets' tops, z 0.355, y 0.205 to 0.275, from 0.21 to 0.51 either side.
  for (const side of [-1, 1]) {
    on("skull", [side * 0.465, 0.24, 0.355], { scale: 0.85, turn: -side * 0.35 });
    on("potions", [side * 0.36, 0.24, 0.355], { scale: 0.95, turn: side * 0.25 });
    on("cauldron", [side * 0.255, 0.245, 0.355], { scale: 0.32 });
    // The web's corner sits where the back wall meets a wall return, under the top of the set.
    on("cobweb", [side * 0.645, 0.42, 0.47], { scale: 1.4, turn: Math.PI + side * Math.PI / 4 });
  }
  pegboard.add(prop(wardrobe, "lettering", [0, -0.011, 0], { upright: true, turn: front }));
  // Asleep under the brackets' outer ends, upside down, wings folded, swaying a little.
  const sleepers = [-1, 1].map((side) => {
    const bat = on("bat", [side * 0.5, 0.235, 0.324], { scale: 0.75 });
    bat.rotation.order = "ZYX";
    bat.rotation.x = Math.PI;
    bat.traverse((part) => { if (part.userData.wing) part.rotation.x = part.userData.wing * 1.35; });
    return bat;
  });
  // Under the right tube, clear of Ray: the thread hangs from the tube's underside.
  const spider = on("spider", [0.3, 0.225, 0.3]);
  const thread = spider.children.find((part) => part.userData.thread);
  return haunted(group, [
    bats(wardrobe, group, [-0.36, 0.1, 0.33], 1, { radius: 0.12, squash: 0.35, scale: 0.8, upright: true, pace: 2.2 }),
    bats(wardrobe, group, [0.36, 0.1, 0.33], 1, { radius: 0.12, squash: 0.35, scale: 0.8, upright: true, pace: 2.6, phase: 2 }),
    (seconds) => sleepers.forEach((bat, i) => { bat.rotation.y = 0.12 * Math.sin(seconds * 0.9 + i * 2); }),
    (seconds) => {
      const drop = 0.035 + 0.03 * (1 + Math.sin(seconds * 0.7));
      spider.position.z = 0.3215 - drop;
      thread.scale.z = drop;
    },
  ]);
}
