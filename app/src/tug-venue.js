// The tug of war's own venue: a wrestling ring, the bout's whole floor, in a dark arena. Grey canvas,
// white ropes, black posts and skirt; ringside floor inside a black barricade, the jury's desk on it;
// the crowd dim on all four sides under glowing screens; a round truss of lamps over the ring, whose
// spots make the ring the brightest thing in the hall.
//
// Course frame (course.js): +x along the old lane, +y up, +z the camera's side; the origin is the
// pit's middle on the canvas, the floor the ducks stand on.

import {
  AmbientLight, BoxGeometry, CanvasTexture, CircleGeometry, CylinderGeometry, ExtrudeGeometry, Group, Mesh,
  MeshBasicMaterial, MeshStandardMaterial, Path, PlaneGeometry, Quaternion, Shape, ShapeGeometry, SphereGeometry,
  SpotLight, SRGBColorSpace, TorusGeometry, Vector2, Vector3,
} from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { toThree } from "./tug.js";
import { sponsorTexture } from "./gym-branding.js";
import { buildJudges } from "./judges.js";
import { crowd } from "./stadium.js";

// The ring at a duck's scale (a wrestler's ring stands 1.2 m for 1.8 m wrestlers; a duck is 25 cm):
// its size, ropes and posts are the physics' own, served with the event; its canvas stands RING_RISE
// over the hall's floor, its apron APRON past the ropes.
export const RING_RISE = 0.14;
export const APRON = 0.1;
// The ringside floor between the apron and the barricade, the barricade's height and thickness.
const RINGSIDE = 0.9;
const BARRICADE = [0.13, 0.03];
// The stands, one on each side, a stride behind the barricade.
const TIERS = 4;
const TIER_DEPTH = 0.3;
const TIER_RISE = 0.1;
const SEAT = 0.3;
const AISLE = 0.2;
// The round truss: its radius, its height (over the clip's opening travel, 2 m at most), its section.
const TRUSS = 2.3;
const TRUSS_HEIGHT = 2.3;
const TRUSS_SECTION = 0.14;
const NODES = 96;
const CANS = 20;

const UP = new Vector3(0, 1, 0);
const rectangle = (x0, y0, x1, y1) => [new Vector2(x0, y0), new Vector2(x1, y0), new Vector2(x1, y1), new Vector2(x0, y1)];

/** The skirt's print, `length` by `height` metres: the Arena's mark and name in white on black. */
function skirtPrint(length, height, mark) {
  const canvas = document.createElement("canvas");
  canvas.height = 128;
  canvas.width = Math.round((canvas.height * length) / height);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#08080c";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#f4f4f6";
  ctx.font = '400 84px "Anton"';
  ctx.textBaseline = "middle";
  const markWidth = 84 * (mark.naturalWidth / mark.naturalHeight);
  const panels = 3;
  for (let i = 0; i < panels; i += 1) {
    const x = ((i + 0.5) * canvas.width) / panels - 380;
    ctx.drawImage(mark, x, 22, markWidth, 84);
    ctx.fillText("MICRODUCK ARENA", x + markWidth + 28, 68);
  }
  const map = new CanvasTexture(canvas);
  map.colorSpace = SRGBColorSpace;
  map.anisotropy = 8;
  return map;
}

/**
 * The venue round a tug, its ring `ring_m` square, crossed by the pit from rope to rope, its ropes
 * and posts the served capsules.
 * `clearance` is how far out on +z the near stand may start, behind the chase camera and its
 * opening travel (viewer.js). Returns the group, the crowd for the viewer to cull, `pose` for the
 * crowd and the jury, and `dispose`; the shared models (spectators, Reachy) are left alone.
 */
export function buildTugVenue({ ring_m, pit_m, pit_depth_m, ropes, posts }, spectators, reachy, branding, clearance) {
  const group = new Group();
  group.name = "course";
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set();
  const own = (set, thing) => (set.add(thing), thing);
  const surface = (color, metalness = 0, roughness = 0.8) =>
    own(materials, new MeshStandardMaterial({ color, metalness, roughness, envMapIntensity: 0.15 }));
  const glow = (parameters) => own(materials, new MeshBasicMaterial({ toneMapped: false, ...parameters }));
  const mesh = (geometry, material, name = "") => {
    own(geometries, geometry);
    const made = new Mesh(geometry, material);
    made.name = name;
    group.add(made);
    return made;
  };
  // Many parts in one paint, drawn as one.
  const merged = (parts, material, name) => {
    const made = mesh(mergeGeometries(parts), material, name);
    parts.forEach((part) => part.dispose());
    return made;
  };
  const box = (w, h, d, [x, y, z]) => new BoxGeometry(w, h, d).translate(x, y, z);
  const strut = (a, b, radius, sides = 4) => {
    const [from, to] = [new Vector3(...a), new Vector3(...b)];
    const geometry = new CylinderGeometry(radius, radius, from.distanceTo(to), sides, 1, true);
    geometry.applyQuaternion(new Quaternion().setFromUnitVectors(UP, to.clone().sub(from).normalize()));
    return geometry.translate(...from.add(to).multiplyScalar(0.5).toArray());
  };

  const half = ring_m / 2;
  const edge = half + APRON;
  const floor = -RING_RISE;
  const black = surface(0x0b0c10, 0, 0.7);

  // The ring: the canvas, cut open over the pit from rope to rope, its body down to the pit's floor.
  const outline = new Shape(rectangle(-edge, -edge, edge, edge));
  outline.holes.push(new Path(rectangle(-pit_m / 2, -half, pit_m / 2, half)));
  const body = new ExtrudeGeometry(outline, { depth: pit_depth_m, bevelEnabled: false }).rotateX(-Math.PI / 2).translate(0, -pit_depth_m, 0);
  mesh(body, [surface(0xa4a7ae, 0, 0.9), black], "ring").receiveShadow = true;
  mesh(new PlaneGeometry(pit_m, half * 2).rotateX(-Math.PI / 2).translate(0, -pit_depth_m, 0), black, "pit_floor");
  mesh(box(0.02, 0.002, half * 2, [0, 0.001 - pit_depth_m, 0]), surface(0xf4f4f6), "centre_line");
  const print = own(textures, skirtPrint(edge * 2, RING_RISE, branding.arena));
  const skirt = own(materials, new MeshBasicMaterial({ map: print }));
  for (let side = 0; side < 4; side += 1) {
    const turn = (side * Math.PI) / 2;
    const plane = new PlaneGeometry(edge * 2, RING_RISE).translate(0, floor / 2, edge + 0.002).rotateY(turn);
    mesh(plane, skirt, "skirt");
  }
  merged(ropes.map(({ from, to, radius }) => strut(toThree(from), toThree(to), radius, 8)), surface(0xf2f2f4, 0, 0.45), "ropes");
  // The posts, from the hall's floor up to the physics' top; the canvas hides what is below it.
  const top = Math.max(...ropes.map(({ from }) => from[2]));
  merged(posts.map(({ from, to, radius }) => {
    const [x, , z] = toThree(from);
    return new CylinderGeometry(radius, radius, to[2] - floor, 12).translate(x, (to[2] + floor) / 2, z);
  }), black, "posts");
  // The turnbuckles' pads, one tall pad on each post's side facing the ring's middle.
  merged(posts.map(({ from }) => {
    const [x, , z] = toThree(from);
    return new BoxGeometry(0.05, top + 0.03, 0.05).rotateY(Math.PI / 4)
      .translate(x - Math.sign(x) * 0.03, (top + 0.03) / 2 + 0.01, z - Math.sign(z) * 0.03);
  }), surface(0xff7a2f, 0, 0.6), "pads");
  // Steel steps up to the apron, by the near west corner.
  merged([1, 2, 3].map((step) => box(0.3, (RING_RISE * step) / 3, 0.08, [-half + 0.25, floor + (RING_RISE * step) / 6, edge + (3 - step) * 0.08 + 0.04])),
    surface(0x9aa1ab, 0.8, 0.35), "steps");

  // The hall's floor round the ring, ringside inside a black barricade.
  const barricade = edge + RINGSIDE;
  // Each stand an aisle behind the barricade; the near one (+z) behind the camera too.
  const behind = barricade + AISLE;
  const sides = [0, 1, 2, 3].map((side) => ({ turn: (side * Math.PI) / 2, inner: side ? behind : Math.max(behind, clearance) }));
  const room = Math.max(behind, clearance) + TIERS * TIER_DEPTH + 0.4;
  const ground = new Shape(rectangle(-room, -room, room, room));
  ground.holes.push(new Path(rectangle(-edge, -edge, edge, edge)));
  mesh(new ShapeGeometry(ground).rotateX(-Math.PI / 2).translate(0, floor, 0), surface(0x24262d, 0, 0.95), "floor").receiveShadow = true;
  const [height, thickness] = BARRICADE;
  merged(sides.map(({ turn }) => box(barricade * 2, height, thickness, [0, floor + height / 2, barricade]).rotateY(turn)), black, "barricade");
  merged(sides.map(({ turn }) => box(barricade * 2, 0.012, thickness + 0.01, [0, floor + height, barricade]).rotateY(turn)), surface(0x3a3d46, 0.4, 0.5));

  // The stands: stepped tiers in black, a wall behind, a ribbon of light along it and a screen.
  const tiers = [];
  const walls = [];
  const ribbons = [];
  const seats = [];
  const screens = [];
  const length = barricade * 2;
  const across = Math.round(length / SEAT / 2) * 2; // even: no seat on an axis, where the crowd's sides split
  for (const { turn, inner } of sides) {
    const at = (x, y, z) => new Vector3(x, y, z).applyAxisAngle(UP, turn);
    for (let row = 0; row < TIERS; row += 1) {
      const rise = TIER_RISE * (row + 1);
      const out = inner + TIER_DEPTH * (row + 0.5);
      tiers.push(box(length, rise, TIER_DEPTH, [0, floor + rise / 2, out]).rotateY(turn));
      for (let i = 0; i < across; i += 1) {
        const { x, z } = at(((i + 0.5) / across - 0.5) * length, 0, out);
        seats.push({ x, y: floor + rise, z, yaw: Math.PI / 2 + turn });
      }
    }
    // Facing the ring only: from outside, an orbiting camera sees in.
    const back = inner + TIERS * TIER_DEPTH + 0.1;
    walls.push(new PlaneGeometry(length + 0.8, 2.6).rotateY(Math.PI).translate(0, floor + 1.3, back).rotateY(turn));
    ribbons.push(new PlaneGeometry(length + 0.8, 0.025).rotateY(Math.PI).translate(0, floor + 0.8, back - 0.01).rotateY(turn));
    const shown = turn === Math.PI ? [-1.25, 1.25] : [0];
    for (const x of shown) {
      screens.push(new PlaneGeometry(1.9, 0.475).rotateY(Math.PI).translate(x, floor + 1.17, back - 0.02).rotateY(turn));
    }
  }
  merged(tiers, surface(0x15161c, 0, 0.9), "tiers");
  merged(walls, surface(0x0c0d12, 0, 0.95), "walls");
  merged(ribbons, glow({ color: 0x2ff0e6 }), "ribbons");
  const logo = own(textures, sponsorTexture("arena", branding));
  merged(screens, glow({ map: logo }), "screens");
  const audience = crowd(spectators.kinematics, spectators.geometries, seats);
  group.add(audience.group, audience.bubbles);

  // The jury at its desk on the ringside floor, across the ring from the camera.
  const maps = ["pollen", "arena", "huggingFace"].map((brand) => (brand === "arena" ? logo : own(textures, sponsorTexture(brand, branding))));
  const jury = buildJudges(reachy, 0, edge + 0.15, maps);
  jury.group.position.y = floor;
  group.add(jury.group);

  // The round truss: four chords, laced on every face, hung over the ring.
  const truss = [];
  for (const dr of [-1, 1]) {
    for (const dy of [-1, 1]) {
      truss.push(new TorusGeometry(TRUSS + (dr * TRUSS_SECTION) / 2, 0.008, 4, NODES).rotateX(Math.PI / 2)
        .translate(0, TRUSS_HEIGHT + (dy * TRUSS_SECTION) / 2, 0));
    }
  }
  const node = (i, dr, dy) => {
    const angle = (i / NODES) * Math.PI * 2;
    const r = TRUSS + (dr * TRUSS_SECTION) / 2;
    return [r * Math.cos(angle), TRUSS_HEIGHT + (dy * TRUSS_SECTION) / 2, r * Math.sin(angle)];
  };
  for (let i = 0; i < NODES; i += 1) {
    const zig = i % 2 ? 1 : -1;
    for (const dr of [-1, 1]) {
      truss.push(strut(node(i, dr, -1), node(i, dr, 1), 0.005));
      truss.push(strut(node(i, dr, zig), node(i + 1, dr, -zig), 0.005));
    }
    for (const dy of [-1, 1]) truss.push(strut(node(i, zig, dy), node(i + 1, -zig, dy), 0.005));
  }
  // Six cables up into the dark.
  for (let i = 0; i < NODES; i += NODES / 6) {
    const [x, y, z] = node(i, 0, 1);
    truss.push(strut([x, y, z], [x, 3.6, z], 0.004));
  }
  merged(truss, surface(0xb8bec8, 0.85, 0.35), "truss");
  // Par cans under it, each aimed somewhere on the ring, their lenses lit; a row of bulbs on its lower chords.
  const cans = [];
  const lenses = [];
  for (let i = 0; i < CANS; i += 1) {
    const [x, y, z] = node((i + 0.5) * (NODES / CANS), 0, -1);
    const hang = new Vector3(x, y - 0.07, z);
    const aim = new Vector3(Math.cos(i * 2.4) * 0.9, 0, Math.sin(i * 2.4) * 0.9).sub(hang).normalize();
    const turn = new Quaternion().setFromUnitVectors(UP, aim);
    cans.push(new CylinderGeometry(0.04, 0.046, 0.12, 12).applyQuaternion(turn).translate(...hang.toArray()));
    cans.push(strut([x, y, z], hang.toArray(), 0.006));
    const lens = new CircleGeometry(0.04, 16).applyQuaternion(new Quaternion().setFromUnitVectors(new Vector3(0, 0, 1), aim));
    lenses.push(lens.translate(...hang.clone().addScaledVector(aim, 0.061).toArray()));
  }
  merged(cans, black, "cans");
  merged(lenses, glow({ color: 0xfff4e0 }), "lenses");
  const bulbs = [];
  for (let i = 0; i < NODES; i += 2) {
    for (const dr of [-1, 1]) bulbs.push(new SphereGeometry(0.011, 6, 4).translate(...node(i, dr, -1)).translate(0, -0.012, 0));
  }
  merged(bulbs, glow({ color: 0xdfe9ff }), "bulbs");

  // The light: the crowd in a dim wash; the ring under two spots from the truss, cut to the ring:
  // the key, high on the camera's side, casting the ducks' shadows on the canvas, and a rim from
  // across the ring that lifts the ducks off the dark.
  group.add(new AmbientLight(0x6878a8, 0.75));
  const spot = (color, intensity, from, angle) => {
    const light = new SpotLight(color, intensity, 0, angle, 0.4, 2);
    light.position.set(...from);
    group.add(light, light.target);
    return light;
  };
  const key = spot(0xffffff, 16, [0, TRUSS_HEIGHT - 0.1, 0.6], 0.8);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.far = TRUSS_HEIGHT + 1;
  key.shadow.bias = -0.0002;
  const rim = spot(0xd8e4ff, 10, [0, TRUSS_HEIGHT - 0.1, -TRUSS], 0.5);

  return {
    group,
    crowd: audience,
    pose(seconds, subjects, mood) {
      audience.pose(seconds, mood);
      jury.pose(seconds, subjects);
    },
    dispose() {
      jury.dispose();
      audience.dispose();
      key.dispose();
      rim.dispose();
      geometries.forEach((geometry) => geometry.dispose());
      materials.forEach((material) => material.dispose());
      textures.forEach((texture) => texture.dispose());
      group.removeFromParent();
    },
  };
}
