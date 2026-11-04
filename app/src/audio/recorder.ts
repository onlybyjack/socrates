import { MicVAD } from "@ricky0123/vad-web";
import { concatFloat32, encodeWav } from "./wav";

/** Silence after the last speech segment that ends the whole answer (people pause while thinking). */
const ANSWER_GAP_MS = 1500;
const SAMPLE_RATE = 16000;

export type MicState = "off" | "waiting" | "speaking";

/**
 * Listens through the browser VAD (silero, runs locally). Speech segments are collected and
 * emitted as one WAV once the candidate has been silent for ANSWER_GAP_MS, or on forceEnd().
 */
export class Recorder {
  private vad: MicVAD | null = null;
  private segments: Float32Array[] = [];
  private gapTimer: number | undefined;
  private active = false;
  private lastLevel = 0;

  onAnswer: (wav: ArrayBuffer | null) => void = () => {};
  onState: (s: MicState) => void = () => {};

  async init() {
    this.vad = await MicVAD.new({
      model: "v5",
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      startOnLoad: false,
      redemptionMs: 800,
      minSpeechMs: 250,
      submitUserSpeechOnPause: true,
      onFrameProcessed: (_p, frame) => {
        let sum = 0;
        for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
        this.lastLevel = Math.min(1, Math.sqrt(sum / frame.length) * 8);
      },
      onSpeechStart: () => {
        if (!this.active) return;
        window.clearTimeout(this.gapTimer);
        this.onState("speaking");
      },
      onSpeechEnd: (audio) => {
        if (!this.active) return;
        this.segments.push(audio);
        this.onState("waiting");
        window.clearTimeout(this.gapTimer);
        this.gapTimer = window.setTimeout(() => this.emit(), ANSWER_GAP_MS);
      },
      onVADMisfire: () => {
        if (this.active) this.onState("waiting");
      },
    });
  }

  level(): number {
    return this.active ? this.lastLevel : 0;
  }

  async start() {
    this.segments = [];
    this.active = true;
    this.onState("waiting");
    try {
      await this.vad?.start();
    } catch (e) {
      this.active = false;
      this.onState("off");
      throw e;
    }
  }

  /** Stop listening and drop anything captured (used while the interviewer is talking). */
  async pause() {
    this.active = false;
    window.clearTimeout(this.gapTimer);
    this.segments = [];
    this.lastLevel = 0;
    this.onState("off");
    await this.vad?.pause();
  }

  /** "답변 완료": submit what has been said so far, including speech in progress. */
  async forceEnd() {
    if (!this.active) return;
    window.clearTimeout(this.gapTimer);
    await this.vad?.pause(); // submitUserSpeechOnPause → onSpeechEnd pushes the in-progress segment
    this.emit();
  }

  private emit() {
    if (!this.active) return;
    const parts = this.segments;
    this.active = false;
    this.segments = [];
    this.lastLevel = 0;
    this.onState("off");
    this.vad?.pause();
    this.onAnswer(parts.length ? encodeWav(concatFloat32(parts), SAMPLE_RATE) : null);
  }

  destroy() {
    this.active = false;
    window.clearTimeout(this.gapTimer);
    this.vad?.destroy();
  }
}
