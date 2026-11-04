import { useEffect, useRef } from "react";
import * as THREE from "three";
import { buildProceduralInterviewer, type AvatarRig } from "./procedural";
import { loadVrm } from "./vrm";

interface Props {
  getLevel: () => number;
  speaking: boolean;
  vrmUrl?: string;
  onVrmError?: (msg: string) => void;
}

export function Avatar({ getLevel, speaking, vrmUrl, onVrmError }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const speakingRef = useRef(speaking);
  speakingRef.current = speaking;
  const levelRef = useRef(getLevel);
  levelRef.current = getLevel;

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 50);
    camera.position.set(0, -0.15, 4.2);
    scene.add(new THREE.HemisphereLight("#dfe9ee", "#2a3a42", 1.6));
    const key = new THREE.DirectionalLight("#fff3e2", 2.2);
    key.position.set(1.5, 2, 3);
    scene.add(key);
    const rim = new THREE.DirectionalLight("#9fd3e0", 1.2);
    rim.position.set(-2, 1, -2);
    scene.add(rim);

    let rig: AvatarRig = buildProceduralInterviewer();
    scene.add(rig.root);
    let cancelled = false;
    if (vrmUrl) {
      loadVrm(vrmUrl)
        .then((r) => {
          if (cancelled) return;
          scene.remove(rig.root);
          rig = r;
          scene.add(rig.root);
        })
        .catch(() => onVrmError?.("VRM 파일을 불러오지 못했어요. 기본 면접관으로 진행할게요."));
    }

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = el;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    const clock = new THREE.Clock();
    let raf = 0;
    const loop = () => {
      rig.update(clock.getElapsedTime(), levelRef.current(), speakingRef.current);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [vrmUrl, onVrmError]);

  return <div ref={host} style={{ width: "100%", height: "100%" }} />;
}
