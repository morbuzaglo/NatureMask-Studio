# Architecture

```
Browser (React + TS, Tailwind, Plotly, Web Audio)
   │  fetch /api/*, WAV previews            served from frontend/dist by the same server
   ▼
FastAPI (backend/app/main.py, api/routes.py)  ── jobs.py (thread pool, progress polling)
   │
   ├─ io/importers.py           MAT v5/v7.3 (scipy/h5py), audio (soundfile), tables (pandas/openpyxl/xlrd)
   ├─ engine.py                 target model (domain + provenance), Lw→Lp, templates, analysis
   │    ├─ acoustics/levels.py      SPL, A/C/Z (IEC 61672-1 analytic + linear-phase FIR), time weighting, statistics
   │    ├─ acoustics/bands.py       IEC 61260-1 bands, PSD↔band conversions, octave↔third
   │    ├─ acoustics/propagation.py Lw→Lp, ISO 9613-1 absorption
   │    └─ dsp/spectral.py          Welch PSD, spectrogram, TNR/PR tone screening, temporal class
   ├─ psychoacoustics/          ERB/Bark/roex, NM-PSM v1 masking estimator
   ├─ synthesis/                block-based deterministic generators, presets, scene mixer, synthetic targets
   ├─ optimization/optimizer.py SLSQP multi-start, constraints, Pareto, adaptation curve
   ├─ generation.py             chunked render → float32 memmap, common-gain previews, evaluation from audio
   ├─ exports/exporters.py      WAV/MAT/CSV/JSON/HTML with read-back validation
   └─ storage/projects.py       data/projects/<id>/{project.json, target.npz, render/, exports/}
```

## Key design decisions
- **Units are explicit.** Every target carries `domain` (PASCAL, DIGITAL_CALIBRATED, DIGITAL_UNCALIBRATED,
  SPECTRUM_ONLY) and `provenance` (MEASURED, ESTIMATED_*, SYNTHETIC). Calibrated designs are computed in Pa;
  uncalibrated designs share the recording's digital reference and never produce SPL.
- **Deterministic block synthesis.** Modules render fixed 1-second blocks seeded by (module seed, block
  index) with carried filter/oscillator state and an event tail buffer. Chunked rendering is bit-identical to
  one-shot rendering (tested for every module) and independent of the requested duration.
- **Prediction = render.** The optimizer analyses each module over the exact seeded window
  (`generation.ANALYSIS_WINDOW_S`, ≤ 60 s) that generation renders and evaluation analyses; module spectra
  are pre-reduced to ERB/third-octave powers so the objective evaluates in microseconds.
- **Common normalisation.** Previews and "relative" exports share one gain across target/masker/mix,
  preserving the designed level relations; the factor (Pa per full scale) is stored in metadata.
- **Long renders** stream to a float32 memmap in 5 s chunks; peaks and evaluation are computed chunk-wise.
- **Offline.** Fonts are bundled (@fontsource); no CDN, telemetry or external API.

## Extension points
- New sound module: subclass `synthesis.core.Module`, implement `_block(k, rng)`, register in
  `synthesis/scene.py:MODULE_TYPES`, add to presets.
- New masking model: implement a function with the `psychoacoustics.masking.estimate` signature and
  expose it via `MaskingParams` / the optimizer.
- Spatial module (future): `acoustics/propagation.py` already provides Lw→Lp and ISO 9613-1; an ISO 9613-2
  ground/barrier model needs geometry inputs (not implemented).
- Recorded assets: add files with provenance in `assets/audio/LICENSES.md` and a module that streams them.
