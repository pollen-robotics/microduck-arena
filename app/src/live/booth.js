// Peter and Ray in their booth: two of the viewer's rigs in the STAND pose,
// only neck and head moving, a beak on a pivot, on the booth's set, lit like
// a studio. The set is authored z up under one root turned like the rig's
// own; the camera and the lights are converted out of that frame. One booth
// serves the page: a run's airing puts the run's poster on the CRT, the cup's
// desk stands the cup screen on the back wall in place of the pegboard.

import {
  ACESFilmicToneMapping,
  AmbientLight,
  DirectionalLight,
  Group,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  MeshLambertMaterial,
  PCFSoftShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Scene,
  ShadowMaterial,
  SpotLight,
  SRGBColorSpace,
  TextureLoader,
  WebGLRenderer,
} from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { HALLOWEEN, dress, hauntBooth } from "../halloween.js";
import { applyFrame } from "../replay.js";
import { STAND, TRUNK_HEIGHT, attachMeshes, buildRigTree, jawPivot, setJoint } from "../rig.js";
import { loadAssets, loadGlb } from "../viewer.js";
import { BOOTH_TURN, direct } from "./direction.js";
import { poseAt } from "./score.js";
import { SCREEN_PX, drawCupScreen } from "./screen.js";
import { booth as buildSet, checkerboard, standScreen, token } from "./set.js";

// Which joint holds which index of a trace frame's fourteen angles. A glance's
// yaw is signed so Peter looks toward Ray and Ray toward Peter.
const HEAD = { neck: ["neck_pitch", 5], pitch: ["head_pitch", 6], yaw: ["head_yaw", 7], roll: ["head_roll", 8] };
// Where each duck stands along the desk, and which livery it wears.
const SEATS = { peter: { x: -0.16, livery: "classic" }, ray: { x: 0.16, livery: "blue" } };
// Facing the auditorium: a quarter turn out of the booth's own bearing.
const FACING = BOOTH_TURN - Math.PI / 2;
const JAW_OPEN = 0.32;
const PIXEL_RATIO_CAP = 1.5;

/** A trace frame that stands at booth-local x, turned to face the camera. */
function standFrame(x) {
  const yaw = FACING;
  return Float32Array.from([
    x * Math.cos(BOOTH_TURN), x * Math.sin(BOOTH_TURN), TRUNK_HEIGHT,
    Math.cos(yaw / 2), 0, 0, Math.sin(yaw / 2),
    ...STAND,
  ]);
}

// The set's frame is z up; three.js is y up.
const toY = ([x, y, z]) => [x, z, -y];

export async function createBooth(canvas) {
  const [{ kinematics, geometries }, wardrobe] = await Promise.all([
    loadAssets("legs"),
    // Halloween week: Peter and Ray in costume, the set haunted.
    HALLOWEEN ? loadGlb("halloween.glb") : null,
  ]);
  const renderer = new WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, PIXEL_RATIO_CAP));
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFSoftShadowMap;
  const pmrem = new PMREMGenerator(renderer);
  const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();

  const scene = new Scene();
  scene.environment = environment;
  scene.environmentIntensity = 0.25;
  scene.background = token("deep-ink");
  // A studio's three lights, placed in the booth's own bearing: x along the
  // desk, y up, +z towards the cameras. A warm key spot high on the right
  // pools on the duo and throws their shadows on the set, a cool fill low on
  // the left opens the shaded side, a back light rims the shells off the wall.
  const lights = new Group();
  lights.rotation.y = BOOTH_TURN;
  scene.add(lights);
  scene.add(new AmbientLight(0xffffff, 0.06));
  const key = new SpotLight(0xfff1dc, 10, 0, 0.34, 0.8, 2);
  key.position.set(0.9, 1.3, 1.1);
  key.target.position.set(0, 0.15, 0);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  Object.assign(key.shadow.camera, { near: 0.5, far: 4 });
  key.shadow.bias = -0.0002;
  key.shadow.normalBias = 0.002;
  lights.add(key, key.target);
  const fill = new DirectionalLight(0xbfd2ff, 0.25);
  fill.position.set(-1.2, 0.5, 1.0);
  lights.add(fill);
  const rim = new DirectionalLight(0xffe2c0, 0.6);
  rim.position.set(-0.3, 1.2, -1.0);
  lights.add(rim);
  scene.add(new HemisphereLight(0xcfe0ff, 0x2b2b30, 0.15));

  // The set, z up under a root turned like the rig's duck_root.
  const root = new Group();
  root.rotation.x = -Math.PI / 2;
  scene.add(root);
  const screen = document.createElement("canvas");
  [screen.width, screen.height] = SCREEN_PX;
  const set = buildSet({ screen });
  const screenMap = set.getObjectByName("cup screen").material[3].map;
  root.add(set);
  const haunt = wardrobe ? hauntBooth(wardrobe, set.getObjectByName("pegboard")) : null;
  if (haunt) set.add(haunt.group);
  const floor = new Mesh(new PlaneGeometry(1.3, 0.9), new MeshLambertMaterial({ map: checkerboard() }));
  floor.rotation.z = BOOTH_TURN;
  floor.position.set(-0.04, 0.069, 0.0001);
  root.add(floor);
  // A transparent shadow receiver keeps the checkerboard's paint.
  const shade = new Mesh(floor.geometry, new ShadowMaterial({ opacity: 0.22 }));
  shade.rotation.copy(floor.rotation);
  shade.position.copy(floor.position);
  shade.position.z += 0.0001;
  shade.receiveShadow = true;
  root.add(shade);
  // The CRT's glass shows the poster of the run under discussion. A box's
  // faces are +x, -x, +y, -y, +z, -z; the screen is the -y face, toward the desk.
  const glass = set.getObjectByName("CRT glass");
  const crt = new MeshBasicMaterial({ color: token("deep-ink") });
  glass.material = [glass.material, glass.material, glass.material, crt, glass.material, glass.material];

  const actors = Object.fromEntries(
    Object.entries(SEATS).map(([speaker, seat]) => {
      const rig = buildRigTree(kinematics);
      attachMeshes(rig, kinematics, geometries, { livery: seat.livery });
      if (wardrobe) dress(rig, wardrobe, speaker);
      rig.placer.traverse((object) => {
        if (object.isMesh) object.castShadow = object.receiveShadow = true;
      });
      const jaw = jawPivot(rig);
      scene.add(rig.placer);
      return [speaker, { rig, jaw, frame: standFrame(seat.x) }];
    }),
  );

  const camera = new PerspectiveCamera(32, 16 / 9, 0.05, 50);
  const loader = new TextureLoader();
  let plan = null;
  let cameraAt = null;
  let poster = null;

  return {
    /** A desk segment's commentary carries the cup screen's view; a run's airing, a poster. */
    prepare(commentary, posterUrl) {
      plan = commentary.plan;
      cameraAt = direct(plan);
      if (commentary.screen) {
        drawCupScreen(screen, commentary.screen);
        screenMap.needsUpdate = true;
      }
      standScreen(set, Boolean(commentary.screen));
      poster?.dispose();
      poster = null;
      crt.map = null;
      crt.color.copy(token("deep-ink"));
      crt.needsUpdate = true;
      if (!posterUrl) return;
      loader.loadAsync(posterUrl).then((texture) => {
        if (plan !== commentary.plan) return;
        texture.colorSpace = SRGBColorSpace;
        poster = texture;
        crt.map = texture;
        crt.color.set(0xffffff);
        crt.needsUpdate = true;
      }).catch(() => {});
    },
    draw(ms) {
      if (!plan) return null;
      const framing = cameraAt(ms, camera.aspect);
      camera.position.set(...toY(framing.position));
      camera.lookAt(...toY(framing.target));
      for (const [speaker, actor] of Object.entries(actors)) {
        const pose = poseAt(plan, speaker, ms);
        applyFrame(actor.rig, actor.frame);
        for (const [key, [joint, index]] of Object.entries(HEAD)) {
          setJoint(actor.rig, joint, actor.frame[7 + index] + pose[key]);
        }
        actor.jaw.rotation.y = pose.mouth * JAW_OPEN;
      }
      haunt?.pose(ms / 1000);
      renderer.render(scene, camera);
      return plan.captions.find((c) => c.start_ms <= ms && ms < c.end_ms) ?? null;
    },
    resize(width, height) {
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    },
    dispose() {
      poster?.dispose();
      scene.traverse((object) => {
        object.geometry?.dispose();
        for (const material of [].concat(object.material ?? [])) {
          material.map?.dispose();
          material.dispose();
        }
      });
      key.shadow.dispose();
      environment.dispose();
      renderer.dispose();
    },
  };
}
