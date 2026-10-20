# Fundamental Acoustics

All numbers below are produced/checked by `scripts/reference_impl.py`.

## Sound pressure and level
- Sound pressure p(t) [Pa] = fluctuation about static pressure. RMS over interval T:
  `p_rms = sqrt( (1/T) ∫ p²(t) dt )`.
- Sound pressure level: `Lp = 10 log10(p_rms² / p0²) = 20 log10(p_rms / p0)` dB, **p0 = 20 µPa** in
  air (`TEXTBOOK`; ISO/IEC usage). Examples: 1 Pa rms = 93.98 dB; a 1 Pa-peak sine = 90.97 dB.
- Sound intensity / power are different quantities: sound power level `LW = 10 log10(W / 1 pW)` is a
  *source* property (independent of distance); Lp is a *field* quantity at a point. Free-field point
  source: `Lp = LW − 20 log10(r) − 11 dB` (spherical spreading, r in m, `TEXTBOOK`); hemispherical
  (source on reflecting ground): `− 8 dB`. Inverse-square ⇒ −6 dB per doubling of distance.

## Frequency weightings (IEC 61672-1:2013)
- **A**: approximates the inverse of the 40-phon equal-loudness contour; used for L_A, L_Aeq.
  A(f) = 20 log10 R_A(f) + 2.00 dB, R_A = 12194² f⁴ / [(f²+20.6²) √((f²+107.7²)(f²+737.9²)) (f²+12194²)].
- **C**: flatter; C(f) = 20 log10 R_C(f) + 0.06 dB, R_C = 12194² f² / [(f²+20.6²)(f²+12194²)].
  L_C − L_A > ~15–20 dB is a common *indicator* of strong low-frequency content (`ENGINEERING_HEURISTIC`).
- **Z**: zero weighting (flat), 10 Hz–20 kHz.
- IEC tables tabulate values at the **exact** base-10 frequencies (e.g. 31.62 Hz → −39.4 dB);
  evaluating at the nominal label 31.5 Hz gives −39.5. Use exact frequencies in tests.
- Applying a weighting to band levels: `L_A = 10 log10 Σ 10^((Lb + A(fm))/10)` (band-centre
  approximation; for wide bands integrate W(f)·G(f) instead).

## Time weighting and integrated levels
- Exponential time weightings: F = 125 ms, S = 1 s (I = 35 ms, deprecated). `L_AF(t)`.
- Equivalent continuous level: `L_Aeq,T = 10 log10( (1/T) ∫ p_A²(t) dt / p0² )`.
- Maximum `L_AFmax`, sound exposure level `L_AE = L_Aeq,T + 10 log10(T / 1 s)`.
- Percentile levels `L_N` (level exceeded N % of the time): L10 (events), L50, L90 (background).
  `L10 − L90` quantifies temporal variability → relevant for masking (fluctuating targets are
  harder to mask continuously; De Coensel et al. 2011).

## Combining sources
- Independent (incoherent) sources: energy sum `L = 10 log10 Σ 10^(Li/10)`: 80⊕80 = 83.0 dB,
  80⊕70 = 80.4 dB, 10×60 dB = 70 dB.
- Coherent (same-frequency, phase-locked) sources add as amplitudes — up to +6 dB or cancellation.
  Synthetic masker + recorded target are incoherent ⇒ energy sum is correct per band.
- Level of a masker needed for a given total: `L_total − L_target = ΔL` ⇒
  `L_masker = L_target + 10 log10(10^(ΔL/10) − 1)`: ΔL = 1 dB ⇒ masker 5.87 dB *below* target;
  ΔL = 3 dB ⇒ masker equal to target.

## Spectra
- Narrowband: FFT bins; their level depends on bin width — **not** comparable to band SPL.
- PSD G(f) [Pa²/Hz] (one-sided): `∫₀^{fs/2} G df = p_rms²` (Parseval). Spectrum level
  `10 log10(G / p0²)` [dB re 20 µPa²/Hz].
- Band level from PSD: `Lb = 10 log10(∫_band G df / p0²)`. White noise of spectrum level L0 in a
  band of width B: `Lb = L0 + 10 log10 B`.
- Pure tone of rms p appears entirely in one band ⇒ band level = tone level, independent of
  bandwidth; broadband noise level grows +3 dB per doubling of bandwidth. Hence octave vs 1/3-octave
  levels differ by ~4.8 dB for white noise but ~0 dB for a tone.

## Digital audio vs physical pressure
- Digital samples x[n] ∈ [−1, 1] (dBFS). Physical pressure needs calibration factor S:
  `p[n] = x[n] / S` with S in FS/Pa, or `p = x · k` (Pa per unit). Typical: 94 dB (1 Pa rms)
  calibrator tone recorded at x_rms ⇒ `k = 1 / x_rms` Pa/FS. See `measurement-calibration.md`.
