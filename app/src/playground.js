// Sock Heist's own venue: a school playground at the microducks' scale, built in Blender by
// scripts/sock_heist_venue.py as playground.glb. Its four nodes: the concrete yard under everything,
// the school on the left and the wooden fence on the right, each built from the lanes' edge
// outwards with its crowd's spots before it, and the park's trees behind the giant. Each side
// stands at the edge of the lanes drawn, and a crowd of microducks (stadium.js crowd) sits on its
// spots.
//
// Course frame (course.js): +x down the track, +y up, +z the camera's side; the origin is on the
// start line at the lanes' centre line.

import { Euler, Group, MeshStandardMaterial, Quaternion, Vector3 } from "three";
import { crowd } from "./stadium.js";

// The track's concrete, a shade darker than the yard's slabs (#a9a8a3), so the course reads on it.
const TRACK_CONCRETE = 0x8c8b86;

const _position = new Vector3();
const _turn = new Quaternion();
const _scale = new Vector3();
const _euler = new Euler();

/**
 * The playground round a race whose lanes reach `edge` either side of its centre line, from
 * `model`, the GLB's four nodes (giant.js loadHeistVenue), and `spectators`, the crowd's rig
 * ({ kinematics, geometries }). Each node is cloned, sharing the model's geometries and materials,
 * and `dispose` frees only the crowd and what it made.
 */
export function buildPlayground(model, spectators, edge) {
  const { yard, left, right, park } = Object.fromEntries(
    Object.entries(model).map(([name, node]) => [name, node.clone()]),
  );
  left.position.z = -edge;
  right.position.z = edge;
  const group = new Group();
  group.name = "playground";
  group.add(yard, left, right, park);
  // The fence's panels and the park's trees, instanced: their instances are the clones' own.
  const instanced = [];
  group.traverse((node) => {
    if (node.isInstancedMesh) instanced.push(node);
  });
  group.updateMatrixWorld(true);
  const placed = [left, right].flatMap((side) => side.children
    .filter((node) => node.name.startsWith("spot_"))
    .map((spot) => {
      spot.matrixWorld.decompose(_position, _turn, _scale);
      return { x: _position.x, y: _position.y, z: _position.z, yaw: _euler.setFromQuaternion(_turn, "YXZ").y };
    }));
  const audience = crowd(spectators.kinematics, spectators.geometries, placed);
  group.add(audience.group, audience.bubbles);
  group.traverse((node) => {
    if (node.isMesh) Object.assign(node, { castShadow: node !== yard });
  });
  const track = new MeshStandardMaterial({ color: TRACK_CONCRETE, roughness: 0.95, metalness: 0 });
  return {
    group,
    crowd: audience,
    pose: audience.pose,
    /** The course ground's concrete. */
    floorMaterial: () => track,
    dispose() {
      audience.dispose();
      instanced.forEach((mesh) => mesh.dispose());
      track.dispose();
      group.removeFromParent();
    },
  };
}
