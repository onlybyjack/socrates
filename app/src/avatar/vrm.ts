import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import type { AvatarRig } from "./procedural";

/** Load a user-provided .vrm file and drive its mouth ("aa") and blink expressions. */
export async function loadVrm(url: string): Promise<AvatarRig> {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  const gltf = await loader.loadAsync(url);
  const vrm: VRM = gltf.userData.vrm;
  VRMUtils.rotateVRM0(vrm);
  vrm.scene.traverse((o) => (o.frustumCulled = false));

  // Frame the face like a video call: move the model so the head sits near the origin.
  const head = vrm.humanoid?.getNormalizedBoneNode("head");
  const headPos = new THREE.Vector3();
  head?.getWorldPosition(headPos);
  const root = new THREE.Group();
  vrm.scene.position.set(-headPos.x, -headPos.y, -headPos.z);
  root.add(vrm.scene);
  root.scale.setScalar(5.2);

  // Relax the T-pose arms.
  const arm = (name: "leftUpperArm" | "rightUpperArm", z: number) => {
    const b = vrm.humanoid?.getNormalizedBoneNode(name);
    if (b) b.rotation.z = z;
  };
  arm("leftUpperArm", -1.2);
  arm("rightUpperArm", 1.2);

  let nextBlink = 2;
  let mouthOpen = 0;
  let last = 0;
  const update = (t: number, level: number, speaking: boolean) => {
    const target = speaking ? Math.min(1, level * 1.8) : 0;
    mouthOpen += (target - mouthOpen) * 0.35;
    const em = vrm.expressionManager;
    em?.setValue("aa", mouthOpen);
    const blinkPhase = t - nextBlink;
    em?.setValue("blink", blinkPhase > 0 && blinkPhase < 0.12 ? 1 : 0);
    if (blinkPhase >= 0.12) nextBlink = t + 2.5 + Math.random() * 3;
    if (head) {
      head.rotation.y = Math.sin(t * 0.5) * 0.06;
      head.rotation.x = speaking ? Math.sin(t * 3.1) * 0.03 : 0;
    }
    vrm.update(Math.max(0, t - last));
    last = t;
  };
  return { root, update };
}
