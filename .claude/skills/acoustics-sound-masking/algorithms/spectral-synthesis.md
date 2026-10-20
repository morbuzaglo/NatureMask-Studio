# Algorithm: Spectral Synthesis (target reconstruction + masker shaping)

## A. Synthetic target from a spectrum (spectrum-only inputs)
Purpose: an *audible approximation* for preview — always labelled `SYNTHETIC APPROXIMATION`.
1. Convert band levels → smooth PSD G(f) (octave-bands.md).
2. Broadband part: frequency-domain shaped Gaussian noise. For each block of N = 2^16 samples:
   `X[k] = √(G(f_k)·fs·N/2) · (a_k + j b_k)/√2`, a,b ~ N(0,1); x = irfft(X); overlap-add with a
   periodic Hann² (constant-overlap) window at 50 % hop for streaming; scale check: Welch PSD of
   output matches G within ±0.5 dB per third-octave (tested).
3. Tonal peaks (user-marked or detected): add sinusoids `√2 p_tone sin(2πft+φ)` with optional
   slow jitter (±0.2 %) and the tone's energy removed from the broadband part to keep band totals.
4. Temporal behaviour: stationary, or intermittent (on/off Markov with on-ramp 50 ms), or
   time-varying (OU modulation of level).

## B. Masker shaping
Each module m renders signal `y_m` with natural long-term spectrum `S_m(b)` (measured on a 20 s
analysis render at unit gain, cached by preset+seed). The mix is
`y = Σ_m g_m · EQ_m(y_m)`, with module gains `g_m` and an optional smooth per-band EQ applied to
**broadband bed modules only** (wind, leaves, stream, rain, waves) via a zero-phase-equivalent
streaming FIR (linear-phase, 2048 taps at 48 kHz designed with `firwin2` on ERB-band gains).
Event modules (birds, insects, frogs) receive gain and density changes, never EQ (EQ would make
them unnatural).

Predicted masker band spectrum: `L_m,b = 10 log10 Σ_m 10^((S_m,b + 20log10 g_m + EQ_m,b)/10)`.
Verification after rendering: recompute from the actual audio and report the prediction error.

## C. Level referencing between target and masker
- Calibrated target (Pa): masker is designed in Pa at the listener position; exported WAV gets a
  playback calibration note: "digital full-scale X dBFS corresponds to Y dB SPL at listener if
  playback calibrated with reference tone".
- Uncalibrated target: target and masker share the *digital* reference; mix preview is correct
  relative to each other; no SPL claims.
