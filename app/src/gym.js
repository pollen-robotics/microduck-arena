// A daylight gym around the miniature arena. World-space architecture stays
// level when the event's course climbs; all surfaces belong to this room.
import {
  BoxGeometry, CanvasTexture, DataTexture, Group, LinearFilter, LinearMipmapLinearFilter, Mesh,
  MeshBasicMaterial, MeshStandardMaterial, PlaneGeometry, RepeatWrapping,
  RingGeometry, SphereGeometry, SRGBColorSpace,
} from "three";
import { floorLogoTexture, sponsorTexture } from "./gym-branding.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

export function parquet() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1024;
  const ctx = canvas.getContext("2d");
  let seed = 41;
  const random = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  ctx.fillStyle = "#926437";
  ctx.fillRect(0, 0, 1024, 1024);
  for (let row = 0; row < 32; row++) {
    for (let column = -1; column < 4; column++) {
      const x = column * 256 + (row % 4) * 64;
      const y = row * 32;
      const light = 59 + random() * 13;
      ctx.fillStyle = `hsl(34 48% ${light}%)`;
      ctx.fillRect(x + 1, y + 1, 254, 30);
      for (let grain = 0; grain < 16; grain++) {
        ctx.strokeStyle = `rgba(98,57,22,${0.035 + random() * 0.09})`;
        ctx.beginPath();
        const gy = y + 2 + random() * 27;
        ctx.moveTo(x, gy);
        ctx.bezierCurveTo(x + 70, gy - 2, x + 180, gy + 2, x + 256, gy);
        ctx.stroke();
      }
    }
  }
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.wrapS = texture.wrapT = RepeatWrapping;
  texture.anisotropy = 4;
  return texture;
}

// One 256² linear-data map: varnish varies gently across boards, while
// joints remain matte. The layout matches parquet(), at a quarter resolution.
export function parquetRoughness() {
  const size = 256;
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) {
    const row = Math.floor(y / 8);
    for (let x = 0; x < size; x++) {
      const shifted = (x - (row % 4) * 16 + size) % size;
      const board = Math.floor(shifted / 64);
      const joint = y % 8 === 0 || shifted % 64 === 0;
      const value = joint ? 255 : 170 + ((row * 13 + board * 17) % 35) + (y % 3) * 2;
      const pixel = (y * size + x) * 4;
      data[pixel] = data[pixel + 1] = data[pixel + 2] = value;
      data[pixel + 3] = 255;
    }
  }
  const texture = new DataTexture(data, size, size);
  texture.flipY = true;
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.anisotropy = 4;
  texture.wrapS = texture.wrapT = RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

// A knee brace runs from the wall post up to the roof beam, toward the room.
export function buildRoofBrace(x, wallZ, side, material) {
  const reach = 0.9;
  const brace = new Mesh(new BoxGeometry(0.12, 0.12, Math.hypot(reach, reach)), material);
  brace.position.set(x, 3.87 - reach / 2, side * (wallZ - 0.13 - reach / 2));
  brace.rotation.x = side * Math.PI / 4;
  return brace;
}

export function buildGym(length, minZ, maxZ, branding, trackSpan) {
  const group = new Group();
  group.name = "gym";
  const centre = length / 2;
  // A compact robot sports hall, with 65 cm of circulation behind the stands.
  // Its asymmetric footprint follows the stands, including camera clearance.
  const width = length + 4;
  const depth = maxZ - minZ + 1.3;
  const centreZ = (minZ + maxZ) / 2;
  group.position.z = centreZ;
  group.scale.y = 0.65; // 2.7 m roof rather than a human-scale 4.2 m hall.
  const wallZ = depth / 2;
  const left = centre - width / 2;
  const right = centre + width / 2;
  const textures = new Set();
  const material = (color, roughness = 0.85) => new MeshStandardMaterial({ color, roughness });
  const plaster = material(0xeee8d6);
  const teal = material(0x287775);
  const timber = material(0xb48049, 0.58);
  const frame = material(0x477274, 0.42);
  const white = material(0xf4f0dc);
  const dark = material(0x213d43);
  const sky = new MeshBasicMaterial({ color: 0xb8dce7, toneMapped: false });
  const leaf = [material(0x55866a), material(0x729460), material(0x8aa879)];
  const lamp = new MeshBasicMaterial({ color: 0xfff7d4 });
  const wood = parquet();
  textures.add(wood);
  const varnish = parquetRoughness();
  textures.add(varnish);
  const floors = [];

  function floorMaterial(w, d, z = 0) {
    const map = wood.clone();
    map.repeat.set(w / 4, d / 4);
    map.offset.set((centre - w / 2) / 4, (-z - d / 2) / 4);
    textures.add(map);
    const roughnessMap = varnish.clone();
    roughnessMap.repeat.copy(map.repeat);
    roughnessMap.offset.copy(map.offset);
    textures.add(roughnessMap);
    const made = new MeshStandardMaterial({ map, roughnessMap, roughness: 0.58, metalness: 0, envMapIntensity: 0.85 });
    floors.push(made);
    return made;
  }
  function box(x, y, z, w, h, d, paint, name) {
    const mesh = new Mesh(new BoxGeometry(w, h, d), paint);
    mesh.position.set(x, y, z);
    if (name) mesh.name = name;
    group.add(mesh);
    return mesh;
  }
  function label(text, x, y, z, w, h, bg = "#246e70", fg = "#faf3dc") {
    const canvas = document.createElement("canvas");
    canvas.width = 4096;
    canvas.height = Math.round(4096 * h * group.scale.y / w);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = fg;
    ctx.font = `bold ${Math.round(canvas.height * 0.64)}px "DM Sans"`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, canvas.width / 2, canvas.height / 2, canvas.width - 160);
    const map = new CanvasTexture(canvas);
    map.colorSpace = SRGBColorSpace;
    map.anisotropy = 16;
    textures.add(map);
    const mesh = new Mesh(new PlaneGeometry(w, h), new MeshBasicMaterial({ map }));
    mesh.position.set(x, y, z);
    group.add(mesh);
    return mesh;
  }

  const floor = new Mesh(new PlaneGeometry(width, depth), floorMaterial(width, depth, centreZ));
  floor.name = "parquet";
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(centre, -0.015, 0);
  group.add(floor);
  // Actual openings in both side walls: the outdoors is geometry behind them.
  const bays = 4;
  const bayWidth = width / bays;
  for (const side of [-1, 1]) {
    const z = side * wallZ;
    box(centre, 0.32, z, width, 0.64, 0.16, teal);
    box(centre, 0.7, z, width, 0.12, 0.18, timber);
    box(centre, 3.58, z, width, 1.04, 0.16, plaster);
    box(centre, 3.11, z, width, 0.13, 0.2, timber);
    for (let i = 0; i <= bays; i++) {
      const x = left + i * bayWidth;
      box(x, 1.9, z, 0.23, 2.32, 0.2, plaster);
      box(x, 2.02, z - side * 0.13, 0.07, 4.03, 0.1, timber);
    }
    for (let i = 0; i < bays; i++) {
      const x = left + (i + 0.5) * bayWidth;
      for (const y of [0.79, 1.91, 3.02]) box(x, y, z, bayWidth - 0.2, 0.045, 0.12, frame);
      box(x, 1.91, z, 0.045, 2.24, 0.12, frame);
      box(x, 0.75, z - side * 0.07, bayWidth - 0.18, 0.07, 0.35, white);
    }
    box(centre, 3.4, side * (wallZ + 5), width + 20, 10, 0.08, sky);
    box(centre, -0.09, side * (wallZ + 3), width + 16, 0.1, 6, leaf[2]);
    for (let i = 0; i < 14; i++) {
      const x = left - 2 + i * (width + 4) / 13;
      const zTree = side * (wallZ + 1.7 + (i % 3) * 0.65);
      const h = 1.5 + (i % 4) * 0.3;
      box(x, h / 2, zTree, 0.12, h, 0.12, timber);
      // Overlapping crowns keep the trees from reading as a row of balloons.
      for (let crown = 0; crown < 3; crown++) {
        const tree = new Mesh(new SphereGeometry(0.48, 8, 6), leaf[(i + crown) % 3]);
        tree.position.set(x + (crown - 1) * 0.3, h + (crown === 1 ? 0.3 : 0), zTree + (crown % 2) * 0.2);
        tree.scale.set(1, 1.15, 1);
        group.add(tree);
      }
    }
  }
  // End walls, timber roof trusses and suspended light fittings.
  for (const x of [left, right]) {
    box(x, 2.03, 0, 0.16, 4.1, depth, plaster);
    box(x, 0.35, 0, 0.18, 0.7, depth, teal);
    box(x, 0.73, 0, 0.21, 0.08, depth, timber);
  }
  box(centre, 4.18, 0, width, 0.12, depth, white);
  for (let i = 0; i <= bays; i++) {
    const x = left + i * bayWidth;
    box(x, 3.87, 0, 0.15, 0.28, depth, timber);
    for (const side of [-1, 1]) {
      group.add(buildRoofBrace(x, wallZ, side, timber));
    }
    for (const z of [-depth / 4, depth / 4]) {
      box(x, 3.65, z, 0.018, 0.3, 0.018, dark);
      box(x, 3.47, z, 0.8, 0.06, 0.16, white);
      box(x, 3.43, z, 0.73, 0.015, 0.13, lamp);
    }
  }
  label("MICRODUCK  /  ATHLETIC CLUB", centre, 3.56, -wallZ + 0.11, width * 0.64, 0.49);
  label("PLAY • RACE • REPEAT", centre, 3.56, wallZ - 0.11, width * 0.55, 0.49).rotation.y = Math.PI;
  // Sponsor boards on both end walls. All images
  // are preloaded locally, so video capture never sees unfinished signs.
  const brands = ["pollen", "arena", "huggingFace"];
  const sponsorMaps = brands.map((brand) => {
    const map = sponsorTexture(brand, branding);
    textures.add(map);
    return map;
  });
  function sponsor(index, x, y, z, yaw, w = 1.6) {
    const panel = new Mesh(new PlaneGeometry(w, w / 4 / group.scale.y),
      new MeshBasicMaterial({ map: sponsorMaps[index] }));
    panel.position.set(x, y, z);
    panel.rotation.y = yaw;
    group.add(panel);
  }
  for (const side of [-1, 1]) {
    const x = side === -1 ? left + 0.115 : right - 0.115;
    for (let i = 0; i < 3; i++) sponsor(i, x, 2.4, -wallZ + 1.1 + i * 1.85, -side * Math.PI / 2);
  }
  // Emblems only, printed on the parquet beside the near edge of the track.
  brands.forEach((brand, i) => {
    const map = floorLogoTexture(branding[brand]);
    textures.add(map);
    const decal = new Mesh(new PlaneGeometry(0.42, 0.42), new MeshBasicMaterial({
      map, transparent: true, opacity: 0.9, depthWrite: false,
      polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
    }));
    decal.name = `floor-logo-${brand}`;
    decal.rotation.x = -Math.PI / 2;
    decal.position.set(centre + (i - 1) * 0.7, 0.004, trackSpan / 2 + 0.32 - centreZ);
    group.add(decal);
  });
  // Gym equipment is outside the course and its spectator stands.
  for (const x of [left + 0.15, right - 0.15]) {
    for (let rung = 0; rung < 12; rung++) box(x, 0.18 + rung * 0.15, -wallZ + 1.1, 0.08, 0.04, 1.4, timber);
    for (const z of [-wallZ + 0.38, -wallZ + 1.82]) box(x, 1, z, 0.08, 2, 0.06, timber);
    box(x, 1.25, 1.4, 0.1, 0.7, 1.1, white);
    box(x, 1.25, 1.4, 0.12, 0.38, 0.5, teal);
    const hoop = new Mesh(new RingGeometry(0.16, 0.18, 24), new MeshBasicMaterial({ color: 0xdf6b39, side: 2 }));
    hoop.rotation.x = -Math.PI / 2;
    hoop.position.set(x + (x < centre ? 0.32 : -0.32), 0.98, 1.4);
    group.add(hoop);
  }
  for (const side of [-1, 1]) {
    box(left + 1.25, 0.25, side * (wallZ - 0.42), 2.1, 0.09, 0.35, timber);
    for (const dx of [-0.85, 0.85]) box(left + 1.25 + dx, 0.1, side * (wallZ - 0.42), 0.08, 0.25, 0.3, frame);
  }
  // Painted court markings on the parquet surrounding the miniature track. The centre line stops at
  // the track's edges: the track hides it there, and a tug's pit opens under it.
  const linePaint = new MeshBasicMaterial({ color: 0xf4efd9 });
  const courtX = width - 2;
  const courtZ = depth - 2;
  for (const z of [-courtZ / 2, courtZ / 2]) box(centre, -0.012, z, courtX, 0.002, 0.035, linePaint);
  for (const x of [centre - courtX / 2, centre + courtX / 2]) box(x, -0.012, 0, 0.035, 0.002, courtZ, linePaint);
  for (const side of [-1, 1]) {
    const reach = courtZ / 2 + side * centreZ - trackSpan / 2;
    box(centre, -0.012, side * (courtZ / 2 - reach / 2), 0.035, 0.002, reach, linePaint);
  }
  const circle = new Mesh(new RingGeometry(1.05, 1.085, 64), linePaint);
  circle.rotation.x = -Math.PI / 2;
  circle.position.set(centre, -0.012, 0);
  group.add(circle);
  // Soft, geometric daylight pools; no per-frame shadow maps in software clips.
  const sunlight = new MeshBasicMaterial({ color: 0xffefba, transparent: true, opacity: 0.12, depthWrite: false });
  for (let i = 0; i < bays; i++) {
    const patch = new Mesh(new PlaneGeometry(bayWidth - 0.3, 2.4), sunlight);
    patch.rotation.set(-Math.PI / 2, 0, -0.25);
    patch.position.set(left + (i + 0.5) * bayWidth + 0.6, -0.01, -wallZ + 1.6);
    group.add(patch);
  }

  // Batch fixed opaque architecture by material. Keep only the finished meshes.
  const batches = new Map();
  for (const mesh of [...group.children]) {
    if (mesh.material.transparent || mesh.material.map) continue;
    mesh.updateMatrix();
    const geometry = mesh.geometry.clone().applyMatrix4(mesh.matrix);
    if (!batches.has(mesh.material)) batches.set(mesh.material, []);
    batches.get(mesh.material).push(geometry);
    mesh.geometry.dispose();
    group.remove(mesh);
  }
  for (const [paint, parts] of batches) {
    group.add(new Mesh(mergeGeometries(parts), paint));
    parts.forEach((part) => part.dispose());
  }
  return {
    group, floorMaterial, sponsorMaps,
    // Where a camera may stand, in world metres: clear of the wall bars on the end wall behind the
    // start, and under the lamps.
    room: { back: left + 0.3, ceiling: 3.43 * group.scale.y - 0.2 },
    dispose() {
      const materials = new Set(floors);
      group.traverse((node) => {
        if (!node.isMesh) return;
        node.geometry.dispose();
        materials.add(node.material);
      });
      materials.forEach((paint) => paint.dispose());
      textures.forEach((texture) => texture.dispose());
      group.removeFromParent();
    },
  };
}
