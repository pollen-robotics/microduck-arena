import { readFileSync } from "node:fs";
import { Box3, Matrix4, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { creasedGeometries } from "./rig.js";
import { buildPlayground } from "./playground.js";

/**
 * A GLB of the app's public folder, parsed as the browser's loader would fetch it: copied into an
 * ArrayBuffer of jsdom's own realm, which GLTFLoader's `instanceof` check wants (rig.test.js).
 */
async function parse(path) {
  const bytes = readFileSync(path);
  const buffer = new ArrayBuffer(bytes.length);
  new Uint8Array(buffer).set(bytes);
  return (await new GLTFLoader().parseAsync(buffer, "")).scene;
}

const SIDES = ["left", "right"];
const nodesOf = (model) => Object.values(model).flatMap((root) => {
  const nodes = [];
  root.traverse((node) => nodes.push(node));
  return nodes;
});
const geometriesOf = (model) => new Set(nodesOf(model).filter((node) => node.isMesh).map((mesh) => mesh.geometry));
const materialsOf = (model) => new Set(nodesOf(model).filter((node) => node.isMesh).map((mesh) => mesh.material));
const spotCount = (model) => SIDES.flatMap((side) => model[side].children)
  .filter((node) => node.name.startsWith("spot_")).length;

/** Every crowd seat's z, read off its instanced meshes. */
function spotsOf(playground) {
  playground.group.updateMatrixWorld(true);
  const matrix = new Matrix4();
  return playground.crowd.group.children.flatMap((mesh) => Array.from({ length: mesh.count }, (_, k) => {
    mesh.getMatrixAt(k, matrix);
    return new Vector3().setFromMatrixPosition(matrix.premultiply(mesh.matrixWorld)).z;
  }));
}

describe("buildPlayground", () => {
  let model;
  let spectators;
  beforeAll(async () => {
    // jsdom draws nothing: the crowd's speech bubbles paint into a context that takes it all.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(new Proxy({}, { get: (ctx, key) => ctx[key] ?? (() => {}) }));
    const playground = await parse("public/venue/playground.glb");
    model = Object.fromEntries(["yard", ...SIDES, "park"].map((name) => [name, playground.getObjectByName(name)]));
    const kinematics = JSON.parse(readFileSync("public/robot/kinematics.json", "utf8"));
    spectators = { kinematics, geometries: creasedGeometries(await parse("public/robot/microduck-crowd.glb")) };
  });

  it.each([[0.425], [1.7], [4.25]])("stands each side at the lanes' edge %f m out, its crowd beyond it", (edge) => {
    const playground = buildPlayground(model, spectators, edge);
    const seats = spotsOf(playground); // every crowd seat's z, read off its instanced meshes
    expect(seats.length).toBe(spotCount(model));
    expect(seats.every((z) => Math.abs(z) > edge)).toBe(true);
    expect(seats.some((z) => z < 0) && seats.some((z) => z > 0)).toBe(true);
    const box = (name) => new Box3().setFromObject(playground.group.getObjectByName(name));
    expect(box("left").max.z).toBeLessThan(-edge);
    expect(box("right").min.z).toBeGreaterThan(edge);
  });

  it("frees what it made and never the playground's model nor the crowd's", () => {
    const spies = [...geometriesOf(model), ...materialsOf(model), ...spectators.geometries.values()]
      .map((resource) => vi.spyOn(resource, "dispose"));
    buildPlayground(model, spectators, 1.7).dispose();
    spies.forEach((spy) => expect(spy).not.toHaveBeenCalled());
  });
});
