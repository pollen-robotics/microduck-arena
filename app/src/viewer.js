// The 3D scene: a lane per entry, all playing the same clock.
//
// Axis mapping, measured and pinned by rig.test.js:
//   MJCF +x (forward) -> three.js +x   the duck advances along +x
//   MJCF +y (left)    -> three.js -z   lanes are separated along z
//   MJCF +z (up)      -> three.js +y
// An earlier version of this file assumed forward was -z. That put lanes on the
// forward axis, so a head-to-head raced in single file, and made the camera
// track an axis the duck never moved along.

import {
  ACESFilmicToneMapping,
  Box3,
  CanvasTexture,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  HemisphereLight,
  Color,
  DirectionalLight,
  PerspectiveCamera,
  PCFSoftShadowMap,
  PMREMGenerator,
  Scene,
  Vector3,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
  MODEL_DIR,
  attachMeshes,
  buildRigTree,
  jawPivot,
  loadKinematics,
  rigGeometries,
} from "./rig.js";
import { MOUTH_TRAVEL, mouthTrack } from "./duck-voice.js";
import { createStageVoice } from "./stage-voice.js";
import { loadCalls } from "./live/voice.js";
import { isMuted } from "./sound.js";
import { buildCourse, buildMarker, laneOffsetZ, laneSpacing } from "./course.js";
import { attachStadium } from "./stadium.js";
import { isStage } from "./format.js";
import { buildJudges } from "./judges.js";
import { buildTalentStage, stageCameraPose, placeStageDuck, stageCameraTarget } from "./talent-stage.js";
import { loadGymBranding } from "./gym-branding.js";
import { stadiumDirection } from "./clip/direction.js";
import { buildGym } from "./gym.js";
import { buildRollerHall } from "./roller-hall.js";
import { buildFootballVenue, isFootball } from "./football-venue.js";
import { nameplate } from "./plate.js";
import { Player, applyFrame, frameAt, frameCount, CTRL_DT } from "./replay.js";
import { readBrightness, writeBrightness } from "./brightness.js";
import { SWEEP_TURN, sweepAt } from "./sweep.js";

// The sun supplies shape and the shadows; the room only soft reflections. Much
// more of the room and the racers' shadows wash out on the parquet, which
// reflects it, and the shells read as flat white.
const EXPOSURE = 0.9;
const ENV_INTENSITY = 0.2;
// The stage is lit by its own rig, against the room as it always had it.
const STAGE_ENV_INTENSITY = 0.6;
const KEY = 3.2;
const FILL = 0.25;
const RIM = 0.3;
const HEMI = 0.25;
const GHOST_OPACITY = 0.5;
// The sun behind the start line, high, on the camera's side: the racers'
// shadows run ahead of them across the frame, and the far stand faces it.
// From the far side, it left the crowd and the camera side of every duck dark.
const SUN = new Vector3(-1.6, 2.6, 0.5).normalize();

/**
 * Put one lane's rig where its trace says it is.
 *
 * Lateral offset ONLY. It is tempting to also tilt the placer by the course's
 * slope so the duck "sits on the hill", and that line was here — but a trace
 * frame carries WORLD coordinates that already include the slope, so tilting
 * the placer applies it a SECOND time and the duck climbs away from the ramp it
 * is walking on. Measured on hill-climb-1m5: the physics puts the trunk 0.1182 m
 * above the ramp; the extra rotation drew it at 0.1515 m, the gap widening with
 * distance.
 *
 * The duck's lean was never the problem either: its orientation comes from the
 * trace's quaternion, not from the course.
 *
 * Extracted from createViewer so the rule has somewhere to be tested — the
 * viewer itself needs WebGL and has none in the suite.
 */
/**
 * How far to the side the camera must sit to frame this many lanes.
 *
 * A fixed 1.15 m framed three lanes when they were packed at 0.45 m apart. They
 * are now drawn at the course's true width, so three of them span 2.6 m rather
 * than 1.35 and the outer two fell out of frame. Pure, so the arithmetic is
 * testable without a renderer.
 */
export function cameraSideOffset(lanes, spacing) {
  const halfArena = (Math.max(1, lanes) * spacing) / 2;
  // 1.15 is the framing that has always worked for a single lane; a wider
  // arena is backed away from in proportion to how much wider it is.
  return Math.max(1.15, 0.75 + halfArena * 1.35);
}

/** Attach the visible floor and lane markings to the replay scene. */
export function attachCourse(scene, event, lanes, stripes) {
  const course = buildCourse(event, lanes, stripes);
  scene.add(course);
  return course;
}

export function placeLane(rig, laneZ) {
  rig.placer.position.z = laneZ;
  rig.placer.rotation.set(0, 0, 0);
}

/**
 * The lanes a stage draws: one per duck of the performance it plays (cast.js stageDucks), in duck
 * order, the star first. Every duck is drawn solid, and the plate over the star alone names the
 * entry. Pure, so it is testable.
 */
export function stageLanes(entries) {
  return entries.flatMap((entry) => entry.ducks
    .map((duck) => ({ ...duck, opacity: 1, name: duck.star ? entry.name : undefined })));
}

/**
 * A stage's broadcast camera over its lanes, a duck each, at `seconds` of the broadcast clock and
 * `replay` of the replay: talent-stage.js plans each shot once, at its first frame, from where the
 * troupe stands throughout it, the replay running `lag()` behind the clock (a clip's titles). Made
 * once for each set of lanes, so that every later frame of a shot finds that plan. Needs no
 * renderer, so it is testable.
 */
export function stageCamera(lanes, layout, lag) {
  const placesAt = (at) => lanes.map((lane) => stageCameraTarget(lane.trace, at - lag(), lane.rig.placer));
  return (seconds, replay, aspect, fov) => stageCameraPose(seconds,
    lanes.map((lane) => stageCameraTarget(lane.trace, replay, lane.rig.placer)),
    aspect, fov, layout.depth, layout.width, placesAt);
}

// Project the midpoint of the feet vertically onto the course. Parenting the
// ring to the course also aligns its plane with the ramp.
export function placeMarker(marker, ground, feet, slopeDeg) {
  if (marker.parent !== ground) ground.add(marker);
  const angle = slopeDeg * Math.PI / 180;
  marker.position.set((feet.x + 0.004 * Math.sin(angle)) / Math.cos(angle), 0.004, feet.z);
}

const leftFoot = new Vector3();
const rightFoot = new Vector3();

export function feetPosition(rig, target) {
  rig.joints.get("left_ankle").body.getWorldPosition(leftFoot);
  rig.joints.get("right_ankle").body.getWorldPosition(rightFoot);
  return target.copy(leftFoot).add(rightFoot).multiplyScalar(0.5);
}

// A nameplate's height in metres and how far above the trunk it floats. Tuned
// by eye on the clip page; the football page's stamp clears the plate by them.
export const PLATE_HEIGHT = 0.05;
export const PLATE_LIFT = 0.16;

/**
 * Where the camera stands and what it looks at, for one frame.
 *
 * `null` is the close chase camera used on the race page:
 * behind the leader, trackside, the side offset widening with the arena. An
 * event's `[clip.camera]` spec overrides its constants or fixes the camera
 * outright; `distance` scales a chase's offsets, which is how the vertical
 * clip fits the same picture in a narrower frame. `rise` is the ramp's height
 * under the leader: a chase climbs a hill with its duck instead of watching it
 * walk out of the top of the frame. Pure, so it is testable.
 */
export function cameraPose(spec, lead, sideOffset, rise) {
  if (spec?.kind === "fixed") return { position: [...spec.position], target: [...spec.target] };
  const back = spec?.back ?? 0.35;
  const height = spec?.height ?? 0.34;
  const side = spec?.side ?? sideOffset;
  const distance = spec?.distance ?? 1;
  return {
    position: [lead - back * distance, height * distance + rise, side * distance],
    target: [lead, (spec?.target_height ?? 0.12) + rise, 0],
  };
}

// Where a clip's opening travel starts, relative to the chase it ends on: turned
// this far round towards the front of the line, this much farther out and higher.
const TRAVEL_TURN = (30 * Math.PI) / 180;
const TRAVEL_REACH = 1.3;
const TRAVEL_LIFT = 8;
// How far beyond the camera's farthest stand the near stand starts.
const STAND_CLEARANCE = 0.3;

/**
 * The camera `u` of the way through a clip's opening travel, 0 to 1: an orbit
 * round the chase's target, from ahead of the line where the waiting ducks face
 * it, to the chase itself. An orbit rather than a straight line, so it never
 * cuts through the lanes. Pure, so it is testable.
 */
export function travelPose(chase, u) {
  if (u >= 1) return chase;
  const left = 1 - u * u * (3 - 2 * u);
  const [x, y, z] = chase.target;
  const dx = chase.position[0] - x;
  const dz = chase.position[2] - z;
  const turn = TRAVEL_TURN * left;
  const out = 1 + (TRAVEL_REACH - 1) * left;
  return {
    position: [
      x + out * (dx * Math.cos(turn) + dz * Math.sin(turn)),
      y + (chase.position[1] - y) * (1 + (TRAVEL_LIFT - 1) * left),
      z + out * (dz * Math.cos(turn) - dx * Math.sin(turn)),
    ],
    target: chase.target,
  };
}

/**
 * `pose` turned round its target as OrbitControls turns it for a drag `angle`
 * radians to the right, so the swing teaches the gesture the right way round.
 * Pure, so it is testable.
 */
export function dragPose(pose, angle) {
  if (!angle) return pose;
  const [x, , z] = pose.target;
  const dx = pose.position[0] - x;
  const dz = pose.position[2] - z;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return {
    position: [x + dx * cos - dz * sin, pose.position[1], z + dz * cos + dx * sin],
    target: pose.target,
  };
}

// The racers' model, 1.3 MB, and the crowd's: the same GLB decimated to a
// tenth of its triangles, 154 KB, made with
//   npx @gltf-transform/cli@4 simplify --ratio 0.05 --error 0.02 microduck.glb microduck-crowd.glb
// Measured on a 1080p clip frame under SwiftShader, the Space's renderer:
// 300 ms alone, 1050 ms with the far stand's fifty-four spectators at full
// detail, 350 ms with the whole stadium in this model and the skin filter in
// rig.js. Two metres off they look the same.
const MODEL = "microduck.glb";
const CROWD_MODEL = "microduck-crowd.glb";

// Each GLB is memoised on its own and never re-fetched when you move between
// a walking race and a roller race.
const glbs = new Map();

function loadGlb(model) {
  if (!glbs.has(model)) {
    glbs.set(
      model,
      new GLTFLoader().loadAsync(`${MODEL_DIR}/${model}`).then((gltf) => gltf.scene),
    );
  }
  return glbs.get(model);
}

// Per-rig assets, memoised per rig and model: the roller rig has its own
// kinematic tree and five STLs the GLB does not carry. Exported for the booth,
// which builds its own scene from the same rig.
const rigAssets = new Map();

export function loadAssets(rig, model = MODEL) {
  const key = `${rig}:${model}`;
  if (!rigAssets.has(key)) {
    rigAssets.set(
      key,
      (async () => {
        const [kinematics, glbScene] = await Promise.all([loadKinematics(rig), loadGlb(model)]);
        return { kinematics, geometries: await rigGeometries(kinematics, glbScene) };
      })(),
    );
  }
  return rigAssets.get(key);
}

export async function createViewer(
  canvas,
  { onChaseChange, rig: rigName = "legs", manual = false, camera: spec = null, hushed = () => false } = {},
) {
  // `rigName` and not `rig`, because setLanes below names each lane's built
  // tree `rig` — the two would shadow.
  //
  // A race's lanes all stand on `rigName`, which matches the page: one race
  // page shows one event, and an event declares one rig. A stage's troupe may
  // mix legs and rollers, each duck on its own, so both rigs are loaded. The
  // crowd is always on foot, in its own lighter model.
  const [legs, rollers, spectators, reachy, branding] = await Promise.all([
    loadAssets("legs"),
    loadAssets("rollers"),
    loadAssets("legs", CROWD_MODEL),
    loadGlb("reachy-mini/reachy-mini.glb"),
    loadGymBranding(),
  ]);
  const rigs = { legs, rollers };

  // Under SwiftShader MSAA cost 2.7× per frame (401 → 151 ms at 1080p), and a
  // clip is encoded by x264 anyway, which softens edges; the interactive pages keep it.
  const renderer = new WebGLRenderer({ canvas, antialias: !manual });
  // A clip is exactly its layout's pixels: the recorder wants the drawing
  // buffer to match the frame it is composing, not a device's own ratio.
  renderer.setPixelRatio(manual ? 1 : Math.min(devicePixelRatio, 2));
  // The liveries' colours are linear and deliberately oversaturated because the
  // simulator tone-maps with ACES; without this every robot reads too hot.
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false;
  let brightness = readBrightness();

  // A procedural room, generated once — no asset, no network. This is what
  // gives the metallic parts something to reflect; without it they are black.
  const pmrem = new PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, 0.02);
  room.dispose();
  pmrem.dispose();

  // A shared contact shadow grounds racers without another scene render.
  const shadowCanvas = document.createElement("canvas");
  shadowCanvas.width = shadowCanvas.height = 64;
  const shadowContext = shadowCanvas.getContext("2d");
  const gradient = shadowContext.createRadialGradient(32, 32, 3, 32, 32, 32);
  gradient.addColorStop(0, "rgba(0,0,0,0.3)");
  gradient.addColorStop(0.45, "rgba(0,0,0,0.16)");
  gradient.addColorStop(1, "rgba(0,0,0,0)");
  shadowContext.fillStyle = gradient;
  shadowContext.fillRect(0, 0, 64, 64);
  const shadowMap = new CanvasTexture(shadowCanvas);
  const shadowMaterial = new MeshBasicMaterial({
    map: shadowMap, transparent: true, depthWrite: false, toneMapped: false,
  });
  const shadowGeometry = new PlaneGeometry(0.26, 0.18);

  const scene = new Scene();
  scene.environment = environment.texture;

  // Reflected light stays fixed (setLanes): scaling it with exposure washes out pale surfaces.
  function setBrightness(value) {
    brightness = writeBrightness(value);
    renderer.toneMappingExposure = EXPOSURE * brightness;
    return brightness;
  }
  scene.background = new Color(0xb8dce7);

  // A warm window key, a quiet fill and a cool back light.
  const key = new DirectionalLight(0xfff1dc, KEY);
  key.position.copy(SUN);
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.normalBias = 0.003;
  key.shadow.bias = -0.0001;
  scene.add(key, key.target);
  const fill = new DirectionalLight(0xbfd2ff, FILL);
  // Low, from the camera's side: it opens the shaded side of a duck and the
  // crowd's faces without lifting the shadows on the floor.
  fill.position.set(1.0, 0.6, 1.8);
  scene.add(fill);
  const rim = new DirectionalLight(0xdceaff, RIM);
  rim.position.set(0.8, 1.8, -2.2);
  scene.add(rim);
  // Sky above, ground bounce below.
  scene.add(new HemisphereLight(0xcfe0ff, 0x70604c, HEMI));
  const raceLights = scene.children.filter(child => child.isLight);

  const camera = new PerspectiveCamera(spec?.fov ?? 42, 1, 0.02, 100);
  camera.position.set(-0.35, 0.34, 1.15);

  // Chase camera on by default; the first drag hands control to the user, the
  // same bargain the original sandbox makes.
  let chase = true;
  // When the chase last swung to show it can be moved (sweep); never, so far.
  let swept = -Infinity;

  // A clip drives the camera from cameraPose alone: no controls to fight, no
  // "start" drag to hand chase away.
  const controls = manual ? null : new OrbitControls(camera, canvas);
  if (controls) {
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 0.25;
    controls.maxDistance = 8;
    controls.target.set(0, 0.12, 0);
    controls.addEventListener("start", () => {
      if (!chase) return;
      chase = false;
      onChaseChange?.(false);
    });
  }

  let lanes = [];
  // The stage's camera over those lanes (stageCamera); null on a race.
  let broadcast = null;
  let course = null;
  // A football match's venue (football-venue.js), when the course is one: its
  // group is the course, and in draw it puts the ball and the keepers where they were.
  let venue = null;
  let gym = null;
  let judges = null;
  let stage = null;
  // The stadium's crowd, rebuilt with the course: posed in draw, disposed
  // with the course in clearScene.
  let audience = null;
  let sideOffset = 1.15;
  let slopeDeg = 0;
  let courseLength = 2;
  let player = new Player([]);
  // The performer's voice, live: a clip renders its own soundtrack and stays silent here. It holds
  // its tongue while the Arena is muted or the page says `hushed` — the run page, while its clip
  // plays, so the two soundtracks never mix.
  const voice = manual ? null : createStageVoice(loadCalls, { muted: () => isMuted() || hushed() });
  let crowdDirection = stadiumDirection();

  // Whichever sets are up, each crowd draws only the seats the camera about to
  // render can see — the chase camera's and each roller-hall screen feed's
  // alike — and has them all back once that render is done (stadium.js crowd).
  // A football venue seats its own behind the goals (football-venue.js).
  const crowds = () => [audience, gym, stage, venue].map((set) => set?.crowd).filter(Boolean);
  scene.onBeforeRender = (_renderer, _scene, view) => crowds().forEach((one) => one.cull(view));
  scene.onAfterRender = () => crowds().forEach((one) => one.restore());

  function clearScene() {
    stage?.dispose();
    stage = null;
    judges?.dispose();
    judges = null;
    gym?.dispose();
    gym = null;
    for (const lane of lanes) {
      scene.remove(lane.rig.placer);
      lane.marker?.removeFromParent();
      lane.plate?.dispose();
      if (lane.plate) scene.remove(lane.plate.sprite);
    }
    lanes = [];
    if (course) {
      audience?.dispose();
      audience = null;
      venue?.dispose();
      venue = null;
      scene.remove(course);
      course = null;
    }
  }

  function setLanes(entries, event, playerOptions = {}) {
    clearScene();
    const talent = isStage(event);
    if (talent) entries = stageLanes(entries);
    raceLights.forEach(light => { light.visible = !talent; });
    scene.background.set(talent ? 0x050716 : 0xb8dce7);
    scene.environmentIntensity = talent ? STAGE_ENV_INTENSITY : ENV_INTENSITY;
    const spacing = laneSpacing(event || {});
    sideOffset = cameraSideOffset(entries.length, spacing);
    slopeDeg = event?.slope_deg ?? 0;
    venue = isFootball(event) ? buildFootballVenue(event, reachy, spectators) : null;
    courseLength = venue?.length ?? event?.length_m ?? 2;
    if (talent) {
      slopeDeg = 0;
      stage = buildTalentStage(event, spectators, reachy, entries.length);
      course = stage.group;
      scene.add(course);
    } else if (event) {
      // A football pitch stands where a race's lanes would, and the stadium,
      // the hall and the jury are built round it the same way.
      if (venue) scene.add((course = venue.group));
      else {
        course = attachCourse(
          scene,
          event,
          Math.max(1, entries.length),
          entries.map((entry) => entry.colour),
        );
      }
      // The near stand starts a stride beyond where the chase camera stands,
      // clip travel included, so the lens is never inside it.
      const chase = cameraPose(spec ?? venue?.camera, 0, sideOffset, 0).position[2];
      const clearance = chase * TRAVEL_REACH + STAND_CLEARANCE;
      const ground = course.getObjectByName("ground");
      const { width, height } = ground.geometry.parameters;
      const roller = event.id === "roller-sprint-2m";
      if (roller) {
        gym = buildRollerHall(courseLength, height, branding, spectators);
      } else {
        audience = attachStadium(course, spectators, clearance);
        course.updateMatrixWorld(true);
        const stadiumBounds = new Box3().setFromObject(course);
        gym = buildGym(courseLength, stadiumBounds.min.z, stadiumBounds.max.z, branding, height);
      }
      scene.add(gym.group);
      judges = buildJudges(reachy, courseLength, venue?.edge ?? Math.max(1, entries.length) * spacing / 2, gym.sponsorMaps, roller ? 3 : 4);
      scene.add(judges.group);
      if (!slopeDeg) {
        ground.material.dispose();
        ground.material = gym.floorMaterial(width, height);
      }
    }
    key.castShadow = Boolean(gym);
    if (gym) {
      // Whatever of the stadium stands in the sun's frame casts too; the room's
      // walls and roof stay out, or the sun would never get in.
      audience?.group.traverse(node => {
        if (node.isMesh) node.castShadow = true;
      });
      for (const root of [course, gym.group]) root.traverse(node => {
        if (node.isMesh) node.receiveShadow = true;
      });
      // The sun's shadow frames the track and the jury, where the camera
      // looks: 2 mm a texel, where the whole stadium gave 5 and blurred a
      // duck's shadow into a smudge.
      const bounds = new Box3().setFromObject(course.getObjectByName("ground"));
      bounds.union(new Box3().setFromObject(judges.group));
      bounds.max.y += 0.4;
      const centre = bounds.getCenter(new Vector3());
      const radius = bounds.getSize(new Vector3()).length() / 2;
      key.target.position.copy(centre);
      key.position.copy(SUN).multiplyScalar(radius * 2).add(centre);
      Object.assign(key.shadow.camera, {
        left: -radius, right: radius, top: radius, bottom: -radius,
        near: 0.1, far: radius * 4,
      });
      key.shadow.camera.updateProjectionMatrix();
    }
    lanes = entries.map((entry, i) => {
      const tier = entry.tier ?? "ghost";
      // A duck of a troupe stands on its own rig; a race's lanes on the event's.
      const { kinematics, geometries } = rigs[entry.rig ?? rigName];
      const rig = buildRigTree(kinematics);
      // No colour override: each geom keeps its own colour from the kinematics.
      // Painting the whole duck one lane colour erased every seam between shell,
      // legs and head and left an unreadable silhouette. A ghost is DIMMED
      // instead — the treatment the simulator gives its multiplayer peers.
      attachMeshes(rig, kinematics, geometries, {
        livery: entry.livery ?? "classic",
        // A rival on a publication page is a real entry, drawn solid: an
        // explicit `opacity` overrides what the tier would give it.
        opacity: entry.opacity ?? (tier === "ghost" ? GHOST_OPACITY : 1),
      });
      // The same spacing buildCourse used: the ducks must stand between their
      // own walls, not between someone else's.
      const z = laneOffsetZ(i, entries.length, spacing);
      rig.placer.traverse(node => {
        if (node.isMesh) Object.assign(node, { receiveShadow: true, castShadow: true });
      });
      if (talent) placeStageDuck(rig, entry, stage.layout.centre);
      else if (venue) venue.place(rig);
      else placeLane(rig, z);
      // How the performance sounds (duck-voice.js): the beak follows its triggers and its song.
      const mouth = talent ? mouthTrack(entry.sound, frameCount(entry.trace), entry.lead) : null;
      const jaw = mouth ? jawPivot(rig) : null;
      scene.add(rig.placer);

      // The follow-spot, on the course so it climbs a slope with it (placeMarker).
      // A football match's ducks have none: the ball is what the eye follows there.
      const marker = talent
        ? new Mesh(shadowGeometry, shadowMaterial)
        : venue ? null : buildMarker(tier, entry.colour ?? null);
      if (talent) marker.rotation.x = -Math.PI / 2;
      else if (marker) {
        const shadow = new Mesh(shadowGeometry, shadowMaterial);
        shadow.position.z = -0.001; // Below the ring, above the course, including slopes.
        marker.add(shadow);
      }

      // The duck's name, hung over its head in its lane's colour: there is
      // no legend over the picture, so the name rides the duck.
      let plate = null;
      if (entry.name) {
        const tint = marker ? marker.material.color : new Color(entry.colour ?? 0xfaf8f2);
        plate = nameplate(entry.name, `#${tint.getHexString()}`, "#08080c");
        plate.sprite.scale.set(PLATE_HEIGHT * plate.ratio, PLATE_HEIGHT, 1);
        scene.add(plate.sprite);
      }
      return { ...entry, rig, marker, plate, tier, gazeTarget: new Vector3(), mouth, jaw };
    });
    broadcast = talent ? stageCamera(lanes, stage.layout, () => lag) : null;
    player = new Player(lanes.map((lane) => lane.trace), playerOptions);
    // Every duck on the stage sounds for as long as the troupe's traces perform: a cut-short
    // performance falls silent with them. A race makes no sound.
    voice?.set(talent ? lanes : [], player.duration);
    const progress = [];
    if (event?.length_m && lanes.length) {
      for (let second = 0; second < player.duration; second += .1) {
        const value = Math.max(...lanes.map(lane => {
          const index = Math.min(frameCount(lane.trace) - 1, Math.floor(second / CTRL_DT));
          return Math.max(0, Math.min(1, frameAt(lane.trace, index)[0] / courseLength));
        }));
        progress.push({ second, value });
      }
      progress.push({ second: player.duration, value: Math.max(...lanes.map(lane =>
        Math.max(0, Math.min(1, frameAt(lane.trace, frameCount(lane.trace) - 1)[0] / courseLength)),
      )) });
    }
    // A football crowd follows the play, which it is told: a duck's x says nothing of it.
    crowdDirection = venue ? venue.direction() : stadiumDirection({ end: player.duration, progress,
      verdict: progress.some(sample => sample.value === 1) ? "pass" : null });
    player.play();
  }

  function follow() {
    chase = true;
    onChaseChange?.(true);
  }

  /** Swing the chase once from side to side, as a hand dragging it would. */
  function sweep() {
    swept = performance.now();
  }

  function resize() {
    const width = canvas.clientWidth || 800;
    const height = canvas.clientHeight || 450;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  const _target = new Vector3();
  const _trunk = new Vector3();
  const _feet = new Vector3();
  let raf = null;
  let crowdStart = null;
  // How far the replay runs behind the stage camera's broadcast clock: not at all on a page, where
  // the camera keeps the replay's own; by a clip's titles in a clip (frame).
  let lag = 0;

  function draw(travel = 1, seconds = player.time, mood = time => crowdDirection(player.time + time - seconds)) {
    const indices = player.frameIndices();
    lanes.forEach((lane, i) => {
      const frame = frameAt(lane.trace, indices[i]);
      applyFrame(lane.rig, frame);
      if (lane.jaw) lane.jaw.rotation.y = lane.mouth[indices[i]] * MOUTH_TRAVEL;
      // Follow both feet, including sideways drift and the lane offset.
      if (lane.marker) placeMarker(lane.marker, course ?? scene, feetPosition(lane.rig, _feet), slopeDeg);
      if (lane.plate) {
        lane.rig.bodies.get("trunk_base").getWorldPosition(_trunk);
        lane.plate.sprite.position.set(_trunk.x, _trunk.y + PLATE_LIFT, _trunk.z);
      }
    });
    // The ball and the keepers, where they were.
    venue?.pose(lanes.map((lane) => lane.rig), indices[0] ?? 0);
    audience?.pose(seconds, mood);
    venue?.crowd?.pose(seconds, mood);
    gym?.pose?.(seconds, mood);
    const subjects = lanes.map((lane) =>
      lane.rig.bodies.get("trunk_base").getWorldPosition(lane.gazeTarget),
    );
    judges?.pose(seconds, subjects);
    stage?.pose(seconds, subjects, mood);

    if (chase && course) {
      // Follow the leader along +x, the direction of travel, from behind and
      // slightly to one side so the gait is visible rather than end-on.
      const lead = lanes.length
        ? Math.max(...lanes.map((lane, i) => frameAt(lane.trace, indices[i])[0]))
        : courseLength / 2;
      const rise = lead * Math.tan((slopeDeg * Math.PI) / 180);
      const pose = dragPose(stage
        ? broadcast(manual ? seconds : player.time, player.time, camera.aspect, camera.fov)
        : travelPose(cameraPose(spec ?? venue?.camera ?? gym?.camera, lead, sideOffset, rise), travel),
      SWEEP_TURN * sweepAt((performance.now() - swept) / 1000));
      camera.position.set(...pose.position);
      _target.set(...pose.target);
      if (controls) controls.target.copy(_target);
      else camera.lookAt(_target);
    }
    controls?.update();
    const lead = lanes.length ? Math.max(...lanes.map((lane, i) => frameAt(lane.trace, indices[i])[0])) : courseLength / 2;
    gym?.renderScreens?.(renderer, scene, seconds, lead);
    // Racers, judges and spectators move: their shadows are redrawn for every
    // picture, once, here — a roller hall's screen feeds reuse the last one.
    renderer.shadowMap.needsUpdate = true;
    renderer.render(scene, camera);
  }

  function tick(now) {
    player.advance(now);
    voice?.follow(player.playing ? player.time : null);
    // The crowd on the wall clock: it fidgets before a lane is ticked and after
    // a publication's race has run out, when the replay's clock stands still.
    crowdStart ??= now;
    const crowdSeconds = (now - crowdStart) / 1000;
    draw(1, crowdSeconds);
    raf = requestAnimationFrame(tick);
  }

  /** Manual mode: pose every lane — and the crowd, so a clip's frames come out
   * the same every render — at `seconds`, and render once, the camera `travel`
   * of the way through its opening travel (travelPose). */
  function frame(seconds, travel = 1, crowdSeconds = seconds, mood) {
    lag = crowdSeconds - seconds;
    player.seek(seconds);
    draw(travel, crowdSeconds, mood);
  }

  /** Where lane `i`'s duck stood in the last frame drawn, as fractions of the
   * canvas from its top left: what a clip hangs its stamp on. `lift` metres
   * straight above its trunk instead, for a stamp that must clear its plate. */
  function spot(i, lift = 0) {
    lanes[i].rig.bodies.get("trunk_base").getWorldPosition(_trunk);
    _trunk.y += lift;
    _trunk.project(camera);
    return { x: (_trunk.x + 1) / 2, y: (1 - _trunk.y) / 2 };
  }

  resize();
  // The canvas, not the window: on the publication page the stage is a grid
  // row that gives its height to the sections appearing under it, so the box
  // changes size while the window never does. Watching the window alone left
  // the drawing buffer 36% taller than the box it was painted into.
  const watcher = new ResizeObserver(resize);
  watcher.observe(canvas);
  if (!manual) raf = requestAnimationFrame(tick);

  setBrightness(brightness);

  return {
    setLanes,
    follow,
    sweep,
    setBrightness,
    frame,
    spot,
    get brightness() {
      return brightness;
    },
    get chasing() {
      return chase;
    },
    get player() {
      return player;
    },
    dispose() {
      voice?.dispose();
      if (raf) cancelAnimationFrame(raf);
      watcher.disconnect();
      controls?.dispose();
      clearScene();
      environment.dispose();
      key.shadow.dispose();
      shadowMap.dispose();
      shadowMaterial.dispose();
      shadowGeometry.dispose();
      renderer.dispose();
    },
  };
}
