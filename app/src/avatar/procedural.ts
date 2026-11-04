import * as THREE from "three";

export interface AvatarRig {
  root: THREE.Object3D;
  update: (t: number, level: number, speaking: boolean) => void;
}

/**
 * A code-drawn interviewer (no bundled assets, so no license questions):
 * head, short grey hair, glasses, jacket and collar. Mouth opens with audio level, eyes blink, head idles.
 */
export function buildProceduralInterviewer(): AvatarRig {
  const root = new THREE.Group();
  const mat = (color: string, roughness = 0.8) => new THREE.MeshStandardMaterial({ color, roughness });

  // body
  const jacket = new THREE.Mesh(new THREE.CapsuleGeometry(0.62, 0.5, 8, 24), mat("#2c3e48"));
  jacket.scale.set(1.25, 1, 0.7);
  jacket.position.y = -1.25;
  root.add(jacket);
  const shirt = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.42, 3), mat("#e9edee"));
  shirt.rotation.x = Math.PI;
  shirt.position.set(0, -0.62, 0.38);
  root.add(shirt);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.3, 20), mat("#d9a98a"));
  neck.position.y = -0.48;
  root.add(neck);

  // head
  const head = new THREE.Group();
  head.position.y = 0.05;
  root.add(head);
  const skull = new THREE.Mesh(new THREE.SphereGeometry(0.5, 40, 32), mat("#e2b394", 0.7));
  skull.scale.set(0.92, 1.05, 0.95);
  head.add(skull);
  const hair = new THREE.Mesh(new THREE.SphereGeometry(0.515, 40, 32, 0, Math.PI * 2, 0, Math.PI * 0.42), mat("#8d9599", 0.95));
  hair.scale.set(0.95, 1.05, 0.98);
  hair.position.y = 0.04;
  hair.rotation.x = -0.25;
  head.add(hair);
  for (const side of [-1, 1]) {
    const ear = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 16), mat("#d9a98a"));
    ear.scale.set(0.5, 1, 0.7);
    ear.position.set(side * 0.46, 0, 0);
    head.add(ear);
  }

  // eyes + brows
  const eyes: THREE.Mesh[] = [];
  for (const side of [-1, 1]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 16), mat("#1d2a31", 0.3));
    eye.position.set(side * 0.16, 0.06, 0.44);
    head.add(eye);
    eyes.push(eye);
    const brow = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.025, 0.02), mat("#6f777b"));
    brow.position.set(side * 0.16, 0.19, 0.46);
    brow.rotation.z = side * -0.08;
    head.add(brow);
  }

  // glasses
  const frame = mat("#20262a", 0.4);
  for (const side of [-1, 1]) {
    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.012, 8, 32), frame);
    rim.scale.set(1.15, 0.85, 1);
    rim.position.set(side * 0.16, 0.06, 0.49);
    head.add(rim);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.012, 0.42), frame);
    arm.position.set(side * 0.28, 0.07, 0.29);
    head.add(arm);
  }
  const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.012, 0.012), frame);
  bridge.position.set(0, 0.08, 0.5);
  head.add(bridge);

  // nose + mouth
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.04, 0.12, 12), mat("#d9a98a"));
  nose.rotation.x = Math.PI / 2.4;
  nose.position.set(0, -0.04, 0.5);
  head.add(nose);
  const mouth = new THREE.Mesh(new THREE.SphereGeometry(0.08, 24, 16), mat("#5a2e2a", 0.6));
  mouth.scale.set(1, 0.12, 0.4);
  mouth.position.set(0, -0.2, 0.44);
  head.add(mouth);

  let nextBlink = 2;
  let mouthOpen = 0;

  const update = (t: number, level: number, speaking: boolean) => {
    // smooth mouth toward level
    const target = speaking ? Math.min(1, level * 1.6) : 0;
    mouthOpen += (target - mouthOpen) * 0.35;
    mouth.scale.y = 0.12 + mouthOpen * 0.75;

    // blink
    const blinkPhase = t - nextBlink;
    const closed = blinkPhase > 0 && blinkPhase < 0.12;
    eyes.forEach((e) => (e.scale.y = closed ? 0.1 : 1));
    if (blinkPhase >= 0.12) nextBlink = t + 2.5 + Math.random() * 3;

    // idle sway, breathing; small nods while speaking
    head.rotation.y = Math.sin(t * 0.5) * 0.06;
    head.rotation.z = Math.sin(t * 0.37) * 0.025;
    head.rotation.x = speaking ? Math.sin(t * 3.1) * 0.03 * (0.4 + mouthOpen) : Math.sin(t * 0.8) * 0.01;
    root.position.y = Math.sin(t * 1.4) * 0.008;
  };

  return { root, update };
}
