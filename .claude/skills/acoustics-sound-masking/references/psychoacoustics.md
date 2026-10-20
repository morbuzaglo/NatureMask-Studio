# Psychoacoustics (for masking design)

## Auditory frequency scales
- **Critical bands (Bark)** — Zwicker & Terhardt (1980): `z = 13 atan(0.00076 f) + 3.5 atan((f/7500)²)`;
  Traunmüller (1990): `z = 26.81 f/(1960+f) − 0.53`. 24 critical bands span 20 Hz–15.5 kHz.
  Critical bandwidth ≈ `25 + 75(1 + 1.4 (f/kHz)²)^0.69` Hz (≈100 Hz below 500 Hz, ≈0.2 f above).
- **ERB** — Glasberg & Moore (1990): `ERB_N(f) = 24.7 (4.37 f/1000 + 1)` Hz; ERB-number
  `E = 21.4 log10(4.37 f/1000 + 1)` (Cams). At 1 kHz ERB = 132.6 Hz, E = 15.6. ERB is narrower than
  the classical critical band at low frequencies (based on notched-noise data) — `PEER_REVIEWED`.
- Auditory filter shape: roex(p) `W(g) = (1+pg) e^{−pg}`, `g = |f−fc|/fc`, `p = 4fc/ERB` (symmetric,
  level-independent simplification; real filters broaden on the low-frequency side at high levels,
  producing **upward spread of masking**).

## Loudness
- Loudness (sone) ≠ level: +10 dB ≈ doubling of loudness above ~40 phon (Stevens' power law
  N ∝ p^0.6). Loudness of a broadband sound exceeds that of a narrowband sound at equal SPL
  (spectral loudness summation across critical bands).
- ISO 532-1 (Zwicker) gives total loudness N (sone) and specific loudness N'(z) (sone/Bark) for
  calibrated signals. Time-varying version for fluctuating sounds (N5 = loudness exceeded 5 %).
- **Partial loudness:** a target in a masker sounds softer than alone (Moore, Glasberg & Baer 1997).
  This is the perceptual mechanism behind "reducing prominence without full masking".

## Tonality and prominence
- Tones in noise are more annoying and far more easily heard than broadband components at equal
  level. Screening metrics (ECMA-418-1 / ANSI S1.13 style):
  - **TNR** `= 10 log10(P_tone / P_noise in the critical band around the tone)`; prominent if
    ≥ 8 dB for f ≥ 1 kHz, ≥ `8 + 8.33 log10(1000/f)` below (250 Hz → 13.0 dB).
  - **PR** `= L_cb(tone) − ½(L_cb(lower) + L_cb(upper))` (adjacent critical bands); prominent if
    ≥ 9 dB for f ≥ 1 kHz, ≥ `9 + 10 log10(1000/f)` below (250 Hz → 15.0 dB).
  - ISO/TS 20065:2022 is the engineering standard for tone audibility (ΔL above masking threshold of
    the surrounding noise); not fully implemented here.
- Masking a tone needs masker energy **within the tone's critical band**. Tones are masked more
  effectively by noise than noise is by tones (asymmetry of masking; tone-masking-noise needs
  ~15–25 dB more masker level than noise-masking-tone in codec models, Johnston 1988).

## Sharpness, roughness, fluctuation strength
- **Sharpness** (acum; DIN 45692): weighted centroid of specific loudness toward high Bark. High
  sharpness (e.g. grinders, insects) ⇒ perceived harshness. Insect maskers raise sharpness.
- **Roughness** (asper): AM at ~15–300 Hz (max ≈ 70 Hz) — gear whine sidebands, cicada buzz.
- **Fluctuation strength** (vacil): slow AM ~0.5–20 Hz (max ≈ 4 Hz) — wind gusts, waves. Natural
  maskers should fluctuate slowly (< 1 Hz for broadband beds) to remain unobtrusive.
- Implementations: MoSQITo (Apache-2.0) offers loudness ISO 532-1, sharpness DIN 45692, roughness,
  TNR/PR; SQAT (MATLAB) and ECMA-418-2 implementations exist.

## Auditory scene analysis (Bregman 1990)
- The auditory system groups components by harmonicity, common onset/offset, common modulation,
  spatial location and continuity. A machine sound remains a separate "stream" when its tones,
  onsets or modulations differ from the scene — even if partially masked.
- Design consequences: (1) cover the target's tonal bands with noise-like natural components;
  (2) avoid masker events that are time-locked to target events; (3) give the scene its own
  plausible temporal texture so attention is drawn to natural events (birds) — "informational"
  rather than purely energetic masking (De Coensel 2011; Hao 2016).

## Naturalness, pleasantness, fatigue
- Natural sounds (birdsong, water) increase pleasantness and perceived naturalness of noisy scenes
  even when they do not reduce loudness (`PEER_REVIEWED`, see soundscape-design.md).
- Continuous broadband maskers that are too loud or too bright increase annoyance and fatigue;
  insect textures above ~4 kHz add sharpness. Keep masker spectral tilt natural (falling ≥ 3 dB/oct
  above ~1 kHz for wind/water beds; `ENGINEERING_HEURISTIC`).
