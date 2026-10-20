// Synchronised three-stream player (target / soundscape / mix) on the Web Audio API.
// All three buffers play from the same start time; switching streams only changes gains (20 ms ramps),
// so comparisons are sample-aligned and click-free.

export type StreamName = "target" | "masker" | "mix";

export class TriPlayer {
  ctx: AudioContext;
  buffers: Partial<Record<StreamName, AudioBuffer>> = {};
  private sources: Partial<Record<StreamName, AudioBufferSourceNode>> = {};
  private gains: Record<StreamName, GainNode>;
  private master: GainNode;
  active: StreamName = "mix";
  playing = false;
  private startedAt = 0;
  private offset = 0;
  loop = true;
  onEnded?: () => void;

  constructor() {
    this.ctx = new AudioContext();
    this.master = this.ctx.createGain();
    this.master.connect(this.ctx.destination);
    this.gains = { target: this.ctx.createGain(), masker: this.ctx.createGain(), mix: this.ctx.createGain() };
    (Object.keys(this.gains) as StreamName[]).forEach((k) => {
      this.gains[k].gain.value = k === this.active ? 1 : 0;
      this.gains[k].connect(this.master);
    });
  }

  async load(urls: Record<StreamName, string>) {
    this.stop();
    const entries = await Promise.all((Object.keys(urls) as StreamName[]).map(async (k) => {
      const res = await fetch(urls[k]);
      if (!res.ok) throw new Error(`Could not load ${k} audio (${res.status})`);
      const buf = await this.ctx.decodeAudioData(await res.arrayBuffer());
      return [k, buf] as const;
    }));
    this.buffers = Object.fromEntries(entries);
    this.offset = 0;
  }

  get duration() { return this.buffers.mix?.duration ?? 0; }

  get position(): number {
    if (!this.playing) return this.offset;
    const p = this.ctx.currentTime - this.startedAt;
    return this.loop ? p % Math.max(this.duration, 1e-6) : Math.min(p, this.duration);
  }

  setVolume(v: number) { this.master.gain.setTargetAtTime(v, this.ctx.currentTime, 0.02); }

  select(name: StreamName) {
    this.active = name;
    const t = this.ctx.currentTime;
    (Object.keys(this.gains) as StreamName[]).forEach((k) => this.gains[k].gain.setTargetAtTime(k === name ? 1 : 0, t, 0.02));
  }

  async play(from?: number) {
    if (!this.buffers.mix) return;
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.stopSources();
    const off = from ?? this.offset;
    const when = this.ctx.currentTime + 0.05;
    (Object.keys(this.buffers) as StreamName[]).forEach((k) => {
      const s = this.ctx.createBufferSource();
      s.buffer = this.buffers[k]!;
      s.loop = this.loop;
      s.connect(this.gains[k]);
      s.start(when, off % this.duration);
      if (k === "mix") s.onended = () => { if (this.playing && !this.loop) { this.playing = false; this.offset = 0; this.onEnded?.(); } };
      this.sources[k] = s;
    });
    this.startedAt = when - off;
    this.playing = true;
  }

  pause() {
    if (!this.playing) return;
    this.offset = this.position;
    this.stopSources();
    this.playing = false;
  }

  stop() {
    this.stopSources();
    this.playing = false;
    this.offset = 0;
  }

  seek(t: number) {
    const wasPlaying = this.playing;
    this.offset = Math.max(0, Math.min(t, this.duration));
    if (wasPlaying) this.play(this.offset);
  }

  private stopSources() {
    (Object.values(this.sources) as AudioBufferSourceNode[]).forEach((s) => { try { s.onended = null; s.stop(); } catch { /* already stopped */ } });
    this.sources = {};
  }

  peaks(name: StreamName, n = 900): { min: number[]; max: number[] } {
    const b = this.buffers[name];
    if (!b) return { min: [], max: [] };
    const d = b.getChannelData(0);
    const w = Math.max(1, Math.floor(d.length / n));
    const mn: number[] = [], mx: number[] = [];
    for (let i = 0; i < n && i * w < d.length; i++) {
      let lo = 1, hi = -1;
      for (let j = i * w; j < Math.min(d.length, (i + 1) * w); j++) { const v = d[j]; if (v < lo) lo = v; if (v > hi) hi = v; }
      mn.push(lo); mx.push(hi);
    }
    return { min: mn, max: mx };
  }
}
