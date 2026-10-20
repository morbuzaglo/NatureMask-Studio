# Algorithm: Masking Estimator ("NM-PSM v1")

Label: `ENGINEERING_HEURISTIC` built on the `PEER_REVIEWED` power-spectrum model. Not validated by
listening tests.

## Inputs
- Target PSD `G_t(f)` (Pa²/Hz or FS²/Hz) — stationary, or a sequence of short-time PSDs.
- Masker PSD `G_m(f)` in the **same domain and scale** (both calibrated, or both digital with a
  stated common reference — otherwise the estimate is meaningless and must be refused).
- Parameters: `K_dB` (default −4), `margin_dB` (desired, default 3), band set (ERB, 1-Cam spacing,
  50 Hz–min(16 kHz, 0.45 fs)), tonal masker flags per module, threshold-in-quiet toggle.

## Computation
1. Centres `f_b = erb_number_to_hz(E)` for E = E(50 Hz) … E(f_max) step 1 ⇒ ~38 bands at 48 kHz.
2. Filter powers with roex(p): `P_t,b = Σ G_t W_b Δf`, `P_m,b = Σ G_m W_b Δf`.
3. Effective masker: `K_eff,b = K_dB + 10·τ_b` where τ_b ∈ [0,1] is the tonal fraction of the
   masker in band b (birds/insects partially tonal ⇒ weaker masking of noise-like targets).
4. Threshold `T_b = 10 log10(10^((L_m,b + K_eff,b)/10) + 10^(Tq(f_b)/10))` — Tq only if calibrated.
5. Margin `d_b = L_t,b − T_b`; **masked** if `d_b ≤ −margin_dB`.
6. Prominence index `PI = 10 log10 √Σ_b (10^(d_b/10))²` dB (0 dB ≈ just at estimated threshold in
   a single band). Also report: number of audible bands, worst band, band-wise d_b.
7. Time-varying: frames of 0.5 s (hop 0.25 s) → PI(t); summary median, P90, max.

## Outputs
`{bands: f_b, Lt_b, Lm_b, T_b, d_b}`, `PI`, `audible_band_count`, `worst_band`, `model: "NM-PSM v1"`,
`assumptions: [...]`.

## Reference behaviour (tested)
- Tone at 1 kHz exactly at `L_m,b(1k) + K` ⇒ d = 0 dB in its band (± 0.1 dB).
- Raising masker by 10 dB lowers d_b by 10 dB in all bands where masker dominates Tq.
- Target 30 dB below threshold everywhere ⇒ PI < −25 dB.
- Masker only in 4–8 kHz cannot mask a 200 Hz tone: d_b(200 Hz) unchanged (> 0) — demonstrates
  spectral-overlap requirement.

## Known limitations
Level-independent symmetric filters (no upward spread growth), no temporal integration below
frame size, no binaural/spatial unmasking, no comodulation masking release, no informational
masking, K varies across listeners and frequency (±3 dB). Present results as estimates.
