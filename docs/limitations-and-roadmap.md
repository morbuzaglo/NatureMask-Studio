# Known limitations and roadmap

## Limitations (honest list)
- **No listening-test validation.** NM-PSM v1 and the prominence index are engineering estimates on the
  power-spectrum model; K varies ±3 dB between listeners. No psychoacoustic validity is claimed.
- **Model scope.** Level-independent symmetric auditory filters; no binaural release, comodulation masking
  release or informational masking; temporal masking handled only through 0.5 s frames and slow adaptation.
- **Naturalness** is measured as departure from the preset's own spectrum/balance — a proxy.
- **Sound quality** of the procedural generators was checked objectively (spectrograms, crest factors, tests)
  but has not been evaluated by listeners; recorded assets are not bundled.
- **Calibration.** Physical SPL at a listener requires calibrated playback; the app only provides design levels.
- **Spectrum-only targets** are reconstructed audio (labelled synthetic approximation).
- **Propagation.** Free-field point-source Lw→Lp only; no ISO 9613-2 ground/barrier/meteorology model.
- **Standards.** Weightings and bands are implemented from the standards' published definitions and checked
  against tabulated values; no formal IEC/ISO conformance testing. ISO/TS 20065 and ISO 532-1 loudness are not
  implemented (MoSQITo, Apache-2.0, is the recommended add-on for ISO 532-1).
- **Recordings shorter than the soundscape** are looped in previews (reported in the UI).
- **Very long renders** (> 10 min) produce large MAT files; `sig` is stored as single precision above
  60 M samples.

## Roadmap
1. Listening-test module (ISO/TS 12913-2 questionnaire, 2/3-AFC detection) to calibrate K and the index.
2. ISO 532-1 / ECMA-418-2 loudness, partial loudness (Moore et al. 1997) and tonality metrics.
3. Level-dependent auditory filters (upward spread of masking).
4. Spatial module: multiple speakers, source/receiver geometry, ISO 9613-2.
5. Licensed recorded asset library with provenance, hybrid granular playback.
6. Optional local generative-audio models as plug-ins (offline, seed-controlled).
7. Packaged installer (embedded Python + prebuilt frontend) so Node.js is not needed.
