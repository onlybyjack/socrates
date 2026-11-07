import { useEffect, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";

export type MicAccess = "asking" | "ok" | "denied";
export const BARS = 28;
const HEARD_LEVEL = 0.18;

export async function openMicSettings() {
  const url = "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone";
  try {
    await openUrl(url);
  } catch {
    window.open(url, "_blank");
  }
}

/**
 * Opens the mic (macOS asks for permission the first time), lists inputs and reports a live,
 * center-mirrored voice spectrum. Does nothing while `enabled` is false.
 */
export function useMic(initialId: string | undefined, enabled = true) {
  const [access, setAccess] = useState<MicAccess>("asking");
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [micId, setMicId] = useState<string | undefined>(initialId);
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(0));
  const [heard, setHeard] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let stop = false;
    let raf = 0;
    let ctx: AudioContext | null = null;
    let stream: MediaStream | null = null;

    (async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ audio: micId ? { deviceId: { exact: micId } } : true });
        if (stop) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        setAccess("ok");
        const all = await navigator.mediaDevices.enumerateDevices();
        setDevices(all.filter((d) => d.kind === "audioinput" && d.deviceId !== "default"));
        if (!micId) setMicId(s.getAudioTracks()[0]?.getSettings().deviceId);

        ctx = new AudioContext();
        // A context created without a user gesture can start suspended and would read silence.
        if (ctx.state === "suspended") {
          const c = ctx;
          c.resume().catch(() => {});
          window.addEventListener("pointerdown", () => c.resume().catch(() => {}), { once: true });
        }
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.7;
        ctx.createMediaStreamSource(s).connect(analyser);
        const wave = new Float32Array(analyser.fftSize);
        const freq = new Uint8Array(analyser.frequencyBinCount);
        // Voice range ~90Hz–4kHz, split into log-spaced bands; shown mirrored from the center.
        const hz = ctx.sampleRate / analyser.fftSize;
        const half = BARS / 2;
        const edges = Array.from({ length: half + 1 }, (_, i) => Math.round((90 * Math.pow(4000 / 90, i / half)) / hz));
        let last = 0;
        const tick = (now: number) => {
          raf = requestAnimationFrame(tick);
          if (now - last < 33) return;
          last = now;
          analyser.getFloatTimeDomainData(wave);
          let sum = 0;
          for (let i = 0; i < wave.length; i++) sum += wave[i] * wave[i];
          if (Math.min(1, Math.sqrt(sum / wave.length) * 6) > HEARD_LEVEL) setHeard(true);
          analyser.getByteFrequencyData(freq);
          const bands = edges.slice(0, half).map((lo, i) => {
            const hi = Math.max(lo + 1, edges[i + 1]);
            let peak = 0;
            for (let b = lo; b < hi; b++) peak = Math.max(peak, freq[b]);
            // Quiet room noise stays flat; speech fills the bars.
            return Math.max(0, Math.min(1, (peak / 255 - 0.35) / 0.5));
          });
          // Low frequencies in the middle, spreading outwards both ways.
          setLevels([...bands.slice().reverse(), ...bands]);
        };
        raf = requestAnimationFrame(tick);
      } catch {
        if (!stop) setAccess("denied");
      }
    })();

    return () => {
      stop = true;
      cancelAnimationFrame(raf);
      ctx?.close();
      stream?.getTracks().forEach((t) => t.stop());
      setLevels(Array(BARS).fill(0));
    };
  }, [micId, attempt, enabled]);

  const choose = (id: string) => {
    setHeard(false);
    setMicId(id);
  };
  const label = devices.find((d) => d.deviceId === micId)?.label;

  return { access, devices, micId, label, choose, levels, heard, retry: () => setAttempt((n) => n + 1) };
}
