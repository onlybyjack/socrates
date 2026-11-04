/** Plays interviewer audio clips in order and exposes a live loudness level for lip-sync. */
export class AudioQueue {
  private ctx = new AudioContext();
  private analyser: AnalyserNode;
  private data: Float32Array<ArrayBuffer>;
  private chain: Promise<void> = Promise.resolve();
  private endAt = 0;
  private pending = 0;
  private idleCb: (() => void) | null = null;

  constructor() {
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.analyser.connect(this.ctx.destination);
    this.data = new Float32Array(this.analyser.fftSize);
  }

  get isPlaying(): boolean {
    return this.pending > 0;
  }

  onIdle(cb: () => void) {
    this.idleCb = cb;
  }

  /** Clips are decoded asynchronously but always scheduled in the order they were enqueued. */
  enqueue(buf: ArrayBuffer) {
    this.pending++;
    const decoded = this.ctx.decodeAudioData(buf.slice(0)).catch(() => null);
    this.chain = this.chain.then(async () => {
      const audio = await decoded;
      if (!audio) return this.finishOne();
      if (this.ctx.state === "suspended") await this.ctx.resume();
      const src = this.ctx.createBufferSource();
      src.buffer = audio;
      src.connect(this.analyser);
      const start = Math.max(this.ctx.currentTime + 0.02, this.endAt);
      src.start(start);
      this.endAt = start + audio.duration;
      src.onended = () => this.finishOne();
    });
  }

  private finishOne() {
    this.pending = Math.max(0, this.pending - 1);
    if (this.pending === 0) this.idleCb?.();
  }

  /** 0..1 RMS loudness of what is playing right now. */
  level(): number {
    if (!this.pending) return 0;
    this.analyser.getFloatTimeDomainData(this.data);
    let sum = 0;
    for (let i = 0; i < this.data.length; i++) sum += this.data[i] * this.data[i];
    return Math.min(1, Math.sqrt(sum / this.data.length) * 4);
  }

  close() {
    this.ctx.close();
  }
}
