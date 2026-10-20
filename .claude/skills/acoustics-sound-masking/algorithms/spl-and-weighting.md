# Algorithm: SPL, Weighting, Integrated Levels

**Inputs:** `x[n]` (N×C), `fs` (Hz), `domain` ∈ {PASCAL, DIGITAL_CALIBRATED(k), DIGITAL_UNCALIBRATED}.
**Outputs:** per channel `L_Zeq`, `L_Aeq`, `L_Ceq`, `L_AFmax`, `L_AF(t)`, `L10/L50/L90`, crest factor.

## Steps
1. Pressure: `p = x` (PASCAL) or `p = k·x` (calibrated). Uncalibrated: compute the same quantities
   with reference 1.0 (dBFS) and name them `*_rel`.
2. Z: `L_Zeq = 10 log10(mean(p²)/p0²)`.
3. A / C weighting in the time domain: bilinear-transformed IEC analog filters
   (zeros at 0, poles at 20.6 Hz (×2), 107.7, 737.9, 12194 Hz (×2)); normalise gain at 1 kHz.
   Implementation: `scipy.signal.zpk2tf → bilinear_zpk → sosfilt`. At fs = 48 kHz the bilinear
   warping error near 10–16 kHz is small (< 0.5 dB at 16 kHz typical); alternatively weight in the
   frequency domain from the PSD: `L_Aeq = 10 log10(∫ G(f) 10^(A(f)/10) df / p0²)` — exact for
   stationary signals; used for spectrum-only inputs.
4. Fast time weighting on the weighted signal (τ = 0.125 s): `L_AF(t)`; `L_AFmax = max`.
5. Percentiles from L_AF(t) sampled every 10 ms: `L_N = percentile(L_AF, 100−N)`.

## Spectrum-only input (bands)
`L_Z = 10 log10 Σ 10^(Lb/10)`; `L_A = 10 log10 Σ 10^((Lb + A(fm))/10)` using exact mid-band f.
If only a single dBA value is known, the spectrum is **not unique**: pick a template shape S_b
(dB, relative), solve offset c so that `10 log10 Σ 10^((S_b + c + A(fm))/10) = L_A,given`, label
`ESTIMATED_FROM_TEMPLATE`.

## Numerical example (checked)
Octave bands 63…8k: [70, 72, 75, 78, 80, 77, 72, 65] dB ⇒ L_Z = 84.62 dB, L_A = 83.48 dB
(computed by tests in the app; see validation/reference-cases.md RC-4).
