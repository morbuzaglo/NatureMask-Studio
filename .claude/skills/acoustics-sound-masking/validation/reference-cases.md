# Reference Cases

All target signals here are **synthetic** (clearly labelled); no real machine measurements are
bundled. Spectra are plausible engineering shapes, not measurements of a specific product.

| ID | Case | Target definition | Natural masker hypothesis | Expected outcome |
|---|---|---|---|---|
| RC-1 | Electric drill (synthetic) | broadband motor noise peaking 1–4 kHz + tonal whine ~ 2.4 kHz (+harmonic 4.8 kHz) + 120 Hz hum, ~80 dBA at 1 m (assumed) | countryside/forest: stream + leaves + birds | partial masking of broadband part feasible with ~0–3 dB masker-to-target ratio; whine needs narrowband energy → residual audibility likely; ΔL_A ≈ +2–4 dB |
| RC-2 | High-frequency mechanical (synthetic grinder-like) | energy 4–10 kHz, tonal 6.3 kHz | insects (cicada) + rain | insects overlap well; sharpness increases; feasible at moderate levels |
| RC-3 | Low-frequency (fan/generator, synthetic) | 50/100/150 Hz harmonics + broadband < 500 Hz | wind, waterfall, waves | **likely ineffective**: masking 100 Hz tones requires strong LF masker that sounds like a storm; expect infeasible report |
| RC-4 | Manual octave spectrum | 63…8k Hz: 70, 72, 75, 78, 80, 77, 72, 65 dB (L_Z 84.62, L_A 83.48 dB) | meadow/riverside | generation directly from bands; synthetic target labelled |
| RC-5 | MATLAB round-trip | `.mat` with `sig` (Pa), `fs` = 48000 | any preset | WAV + MAT export, `load` in MATLAB returns sig N×C, fs, t N×1, metadata struct |

## Listening-evaluation methodology (for future validation; not yet performed)
- Participants ≥ 20 normal-hearing adults (screened); headphones calibrated with an artificial ear
  or playback at calibrated level; randomized presentation.
- Stimuli: target alone, masker alone, mix at 3–5 masker levels, for each preset.
- Tasks: (1) 2-AFC / 3-AFC detection of target in mix → psychometric function, threshold;
  (2) ratings on ISO/TS 12913-2 attributes (pleasant…annoying), perceived loudness of target,
  naturalness; (3) MUSHRA-style blind comparison of masker variants; blind A/B in the app is a
  quick informal version.
- Analysis per ISO/TS 12913-3 (ISOPleasant/ISOEventful), mixed-effects models.
- Use results to calibrate K and the prominence index. Until then, all predictions remain
  `ENGINEERING_HEURISTIC`.
