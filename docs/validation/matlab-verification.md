# MATLAB verification of MAT exports

Date: 2026-10-20 · MATLAB R2021b (Windows) · `matlab -batch` · script `tests/acoustic_validation/verify_mat_in_matlab.m`

File: `examples/sample-projects/example5_masker_pascal.mat` (Example 5: synthetic drill-like Pa recording →
Countryside preset → balanced optimisation → masker exported in Pa, 15 s, 48 kHz, stereo).

| Check | Result |
|---|---|
| `load` succeeds; `sig, fs, t, duration, channels, f_oct, f_third, f_psd, metadata` present | PASS |
| `sig` 720000 × 2 double, `t` 720000 × 1, `fs` = 48000, `duration` = 15.00 s | PASS |
| `metadata.signal_domain = pressure_Pa`, `calibration_status = calibrated` | PASS |
| L_Zeq exported vs recomputed in MATLAB from `sig` | 81.18 dB vs 81.18 dB — PASS |
| SPL fields present for calibrated export | PASS |

Finding during verification: the first export computed L_Zeq from Welch-PSD integration and differed from
MATLAB's time-domain value by 0.18 dB (Hann segment weighting biases fluctuating sounds). Exported L_Aeq/L_Zeq
are now time-domain integrals over the full signal.

Uncalibrated exports are checked by `tests/integration/test_workflow.py::test_example5_mat_import_export_uncalibrated_never_spl`
(no `L_Aeq`/`Lp_*`; `Lrel_*` instead).
