# Measurement and Calibration

## Signal domains (always declare one)
| Domain | Meaning | SPL allowed? |
|---|---|---|
| `PASCAL` | samples are sound pressure in Pa (e.g. from a calibrated DAQ / MATLAB `sig` in Pa) | yes |
| `DIGITAL_CALIBRATED` | digital full-scale samples + factor `k` Pa/FS (or sensitivity) | yes, via p = k·x |
| `DIGITAL_UNCALIBRATED` | digital samples, unknown gain | **no** — relative dB (dBFS) only |
| `SPECTRUM_ONLY` | only band levels / PSD given (no waveform) | levels as given; waveform is synthetic |

## Calibration methods
1. **Acoustic calibrator**: record a 94.0 dB (1 Pa rms) or 114 dB (10 Pa) 1 kHz tone through the
   same chain; `k = p_cal / x_rms,cal` Pa/FS. Uncertainty: class 1 calibrator ±0.3–0.4 dB typical
   (`UNVERIFIED` typical figure; use the calibrator certificate).
2. **Microphone sensitivity + ADC full-scale voltage**: `k = V_FS / (S_mic · gain)` with S in V/Pa.
3. **Known reference level**: user states "this recording is L_Aeq = 78 dB at 1 m" ⇒ scale so the
   computed L_Aeq equals 78 dB; record as `REFERENCE_LEVEL` calibration (lower confidence:
   propagates the meter's uncertainty and assumes the same weighting/time interval).

## Combining uncertainty (GUM-style, `TEXTBOOK`)
Independent dB-domain contributions combine as `u_c = √Σ u_i²`: e.g. calibrator 0.3, microphone
0.5, positioning 1.0 dB ⇒ u_c ≈ 1.2 dB; expanded (k=2) ≈ 2.4 dB. Show uncertainty with reported SPL.

## Distance and directivity
Levels are only meaningful with the measurement position. Free-field correction to another
distance: `ΔL = −20 log10(r2/r1)` (point source, far field). Directivity index DI(θ) adds
`+DI` dB in the measured direction. Without measured directivity: don't extrapolate directions.

## Playback (what the app cannot guarantee)
The level at a listener depends on playback gain, loudspeaker sensitivity, placement, room or
outdoor propagation. The app can only state **digital levels** of the masker and, if the user
calibrates playback (play the generated 1 kHz/pink reference and measure with a meter), map
digital dBFS → dB SPL at that position: `L_SPL = L_dBFS + C_play` with C_play measured.

## Export rule
Export SPL quantities (`L_Aeq`, `Lp_oct`, `Lp_third`) only when the domain is PASCAL or
DIGITAL_CALIBRATED; otherwise export relative levels as `Lrel_*` in dBFS and set
`metadata.calibration_status = 'uncalibrated'`.
