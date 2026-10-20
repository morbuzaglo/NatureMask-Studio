# Demonstration results

Generated 2026-10-20 19:38 by `examples/run_demonstrations.py` (duration 30 s, 48 kHz, seed 1).
All machine targets are **synthetic** engineering shapes, not measurements. Levels in dB(A) re 20 µPa at the listener.
PI = prominence index of NM-PSM v1 (model index; 0 dB ≈ at estimated threshold in one band; not a probability).

## Example 1 — Electric drill (synthetic: broadband 1–4 kHz, 2.4 kHz whine, 120 Hz hum, intermittent)

| Environment | Objective | Cap (dB) | L_A machine | L_A soundscape (pred.) | (rendered) | ΔL_A | PI pred. | PI eval. | bands above goal |
|---|---|---|---|---|---|---|---|---|---|
| countryside_afternoon | balanced | +3 | 75.5 | 78.5 | 78.5 | +4.8 | +10.3 | +9.8 | 17/38 |
| forest_morning | balanced | +3 | 75.5 | 78.5 | 78.5 | +4.8 | +10.2 | +10.1 | 19/38 |
| countryside_afternoon | min_added_spl | +3 | 75.5 | 68.5 | 68.5 | +0.8 | +20.2 | +19.9 | 26/38 |
| countryside_afternoon | max_masking | none | 75.5 | 90.2 | — | +14.8 | -1.3 | — | 1/38 |

Reading: with the default cap the soundscape partially masks the drill (+3 dB above the machine, ≈ +5 dB total). The 2.4 kHz whine remains the most audible component. Full masking would need the soundscape ≈ 15 dB above the machine — not a sensible design.

## Example 2 — High-frequency mechanical noise (synthetic: 4–10 kHz, 6.3 kHz tone)

| Environment | Objective | Cap (dB) | L_A machine | L_A soundscape (pred.) | (rendered) | ΔL_A | PI pred. | PI eval. | bands above goal |
|---|---|---|---|---|---|---|---|---|---|
| meadow_summer | balanced | +3 | 71.2 | 74.2 | 74.2 | +4.8 | +9.1 | +8.6 | 18/29 |
| forest_night | balanced | +3 | 71.2 | 74.2 | 74.2 | +4.8 | +9.1 | +9.1 | 18/29 |
| meadow_summer | min_added_spl | +3 | 71.2 | 64.4 | 64.4 | +0.8 | +19.6 | +19.1 | 25/29 |

Reading: insect textures (cicadas, crickets) put energy in the target's bands. Masking is partial at equal level; insects are partly tonal so they mask noise less efficiently than a broadband bed (modelled by K_eff).

## Example 3 — Low-frequency machine (synthetic generator: 50/100/150 Hz harmonics)

| Environment | Objective | Cap (dB) | L_A machine | L_A soundscape (pred.) | (rendered) | ΔL_A | PI pred. | PI eval. | bands above goal |
|---|---|---|---|---|---|---|---|---|---|
| mountain_wind | balanced | +3 | 69.4 | 72.1 | 72.1 | +4.5 | +12.2 | +12.2 | 13/20 |
| waterfall_glade | balanced | +3 | 69.4 | 72.2 | 72.2 | +4.7 | +13.4 | +12.9 | 13/20 |
| coastal_breeze | balanced | +3 | 69.4 | 72.3 | 72.3 | +4.7 | +10.7 | +10.6 | 14/20 |
| waterfall_glade | max_masking | none | 69.4 | 82.7 | — | +13.5 | +1.7 | — | 3/20 |

App notes: “3 band(s) remain above the masking goal; consider raising the masker limit or accepting partial masking (reduced prominence).” “Combined level 82.9 dBA exceeds the warning limit (80.0 dBA). Consider hearing-health implications.” “Low-frequency target components (< 200 Hz) remain audible: natural sounds rarely carry enough energy there without sounding like a storm — natural masking is expected to be ineffective or impractically loud for these bands.”

Reading: **natural-sound masking is expected to be ineffective here.** Even unconstrained, the low harmonics need a soundscape >10 dB louder than the generator; the remaining-audible list is dominated by bands < 200 Hz.

## Example 4 — Manually defined octave spectrum (63 Hz–8 kHz: 70, 72, 75, 78, 80, 77, 72, 65 dB)

Computed from the bands: L_Z = 84.62 dB, L_A = 83.50 dB (hand calculation 84.62 / 83.48 dB). Audio of the target is a synthetic approximation.

| Environment | Objective | Cap (dB) | L_A machine | L_A soundscape (pred.) | (rendered) | ΔL_A | PI pred. | PI eval. | bands above goal |
|---|---|---|---|---|---|---|---|---|---|
| riverside | balanced | +3 | 83.5 | 86.5 | 86.5 | +4.8 | +18.9 | +17.4 | 27/34 |
| meadow_summer | balanced | +3 | 83.5 | 86.5 | 86.5 | +4.8 | +8.4 | +8.4 | 25/34 |

## Example 5 — MATLAB import and export

Input `examples/sample-noise/synthetic_drill_Pa.mat` (MAT v5/v7, sig 384000×1, fs 48000 Hz, domain suggested: PASCAL — metadata 'units' says Pa). Analysis: L_Aeq 81.6 dB, temporal class time-varying, tones 120 Hz, 2399 Hz, 4800 Hz.

| Environment | Objective | Cap (dB) | L_A machine | L_A soundscape (pred.) | (rendered) | ΔL_A | PI pred. | PI eval. | bands above goal |
|---|---|---|---|---|---|---|---|---|---|
| countryside_afternoon | balanced | +3 | 81.8 | 83.6 | 83.6 | +4.0 | +14.1 | +13.8 | 20/38 |

Exports (each re-read and validated):

- `Example_5___MATLAB_round_trip_masker_48k_stereo_wav16.wav` — wav16 — valid: True
- `Example_5___MATLAB_round_trip_masker_48k_stereo_wav24.wav` — wav24 — valid: True
- `Example_5___MATLAB_round_trip_masker_48k_stereo_wav32f.wav` — wav32f — valid: True
- `Example_5___MATLAB_round_trip_masker_48k_stereo.mat` — mat — valid: True
- `Example_5___MATLAB_round_trip_third_octave.csv` — csv — valid: True
- `Example_5___MATLAB_round_trip_octave.csv` — csv — valid: True
- `Example_5___MATLAB_round_trip_spectrum.csv` — csv — valid: True
- `Example_5___MATLAB_round_trip_masking_erb.csv` — csv — valid: True
- `Example_5___MATLAB_round_trip_report.html` — report — valid: True

MATLAB R2021b `load` verification: see `docs/validation/matlab-verification.md`.
