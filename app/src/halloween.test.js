import { BoxGeometry, Group, Mesh, MeshStandardMaterial } from "three";
import { describe, expect, it } from "vitest";
import { decoratePage, dress } from "./halloween.js";

/** A wardrobe as halloween.glb loads: a costume over one holder per body, its pieces under them. */
function wardrobe() {
  const piece = () => new Mesh(new BoxGeometry(), new MeshStandardMaterial());
  const holder = (body, ...pieces) => {
    const made = new Group();
    made.userData.body = body;
    made.add(...pieces);
    return made;
  };
  const costume = new Group();
  costume.userData.costume = "classic";
  costume.add(holder("jaw_soft", piece()), holder("trunk_base", piece(), piece()));
  const scene = new Group();
  scene.add(costume);
  return scene;
}

const rig = () => ({ bodies: new Map([["jaw_soft", new Group()], ["trunk_base", new Group()]]) });

describe("dress", () => {
  it("hangs each piece of a costume on the body it was fitted to, leaving the wardrobe whole", () => {
    const worn = rig();
    const closet = wardrobe();
    dress(worn, closet, "classic");
    expect(worn.bodies.get("jaw_soft").children).toHaveLength(1);
    expect(worn.bodies.get("trunk_base").children).toHaveLength(2);
    // Clones: the next duck dressed from the same wardrobe finds every piece still there.
    expect(closet.children[0].children.map((holder) => holder.children.length)).toEqual([1, 2]);
  });

  it("dims a ghost's costume with it, on materials of its own", () => {
    const worn = rig();
    const closet = wardrobe();
    dress(worn, closet, "classic", 0.5);
    const [mesh] = worn.bodies.get("jaw_soft").children;
    expect(mesh.material).toMatchObject({ transparent: true, opacity: 0.5 });
    expect(closet.children[0].children[0].children[0].material.opacity).toBe(1);
  });
});

describe("decoratePage", () => {
  it("marks the page and lays three bats and a spider over it, out of a screen reader's way", () => {
    decoratePage();
    expect(document.documentElement.classList.contains("halloween")).toBe(true);
    const layer = document.querySelector(".haunt");
    expect(layer.getAttribute("aria-hidden")).toBe("true");
    expect(layer.querySelectorAll(".haunt-bat .haunt-flight .haunt-flap > i")).toHaveLength(9);
    expect(layer.querySelectorAll(".haunt-spider")).toHaveLength(1);
  });
});
