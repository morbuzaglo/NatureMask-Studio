# Signal Processing

## DFT / FFT
`X[k] = Σ x[n] e^{−j2πkn/N}`, bin spacing Δf = fs/N. Amplitude of a sine of amplitude A with
window w: `|X[k]| = A · Σw / 2` ⇒ amplitude-correct scaling divides by `Σw/2` (coherent gain).
Windows trade leakage vs resolution: Hann (ENBW 1.5 bins) is the default; flat-top for tone
amplitudes (ENBW 3.77 bins); rectangular only for bin-centred periodic signals.

## Power spectral density (Welch)
`G(f) = (2 / (fs · Σw²)) · ⟨|X_w(f)|²⟩` (one-sided; DC & Nyquist not doubled) — Pa²/Hz for Pa input.
`scipy.signal.welch(x, fs, window='hann', nperseg=N, noverlap=N/2, scaling='density')`.
Parseval check: `Σ G Δf = var(x)` (tested). Segment length: resolution Δf = fs/N vs variance
(more segments ⇒ smoother). Default 0.5 s segments (Δf = 2 Hz) for 1/3-octave analysis down to
20 Hz; ≥ 1 s for tonal analysis below 100 Hz.

**Do not mix**: a tone's level is read from the *peak bin power × ENBW·Δf* or from band
integration; reading PSD values as levels of a tone is wrong by `10 log10(ENBW·Δf)`.

## STFT / spectrogram
`scipy.signal.stft` or `spectrogram`, Hann, 50–75 % overlap. Display in dB re p0²/Hz (calibrated)
or dBFS²/Hz. Frame energy over time gives short-time band levels for temporal analysis (125 ms ≈
"Fast").

## Band analysis
Two valid approaches:
1. **PSD integration** over ideal band edges (fast, accurate for stationary signals; used here).
2. **Filter bank** (IEC 61260-1 class-1 IIR, e.g. Butterworth order 6 with sos, decimation for low
   bands) for time-domain band levels.
Low bands need long records: the 25 Hz third-octave band (≈ 5.8 Hz wide) requires ≥ ~1 s segments.

## Exponential time weighting
`y[n] = α y[n−1] + (1−α) x²[n]`, `α = e^{−1/(τ fs)}`, τ = 0.125 s (F), 1 s (S).

## Spectral shaping of noise (masker beds)
Frequency-domain: generate complex Gaussian spectrum with magnitude `√G_target(f)` and random phase,
IFFT, overlap-add with constant-power windows for streaming. Or time-domain: filter white noise
with a minimum-phase FIR designed by `scipy.signal.firwin2` on a log-frequency grid. Pink noise:
−3 dB/octave (equal energy per octave); brown: −6 dB/octave.

## Resampling & anti-aliasing
Use `scipy.signal.resample_poly` (polyphase, Kaiser window). Synthesize at the output rate;
oscillator frequencies must stay < 0.45 fs; FM bird chirps: limit carrier + deviation.

## Clipping and gain staging
Mix in float64; normalize to a **true-peak-safe** headroom (e.g. peak ≤ −1 dBFS) via a single
global gain (never per-chunk); optional soft limiter (tanh above −3 dBFS) reported in metadata.
Check for NaN/Inf before export.

## Chunked rendering
Render in blocks (e.g. 10 s) with state carried across blocks (filter `zi`, oscillator phases,
event schedulers) — no restart artefacts. Event generators schedule from a global timeline so an
event spanning a boundary is rendered by both blocks consistently (render into an overlap buffer).
Test: concatenation of chunked renders equals a single render (bit-exact or < −120 dB difference).
