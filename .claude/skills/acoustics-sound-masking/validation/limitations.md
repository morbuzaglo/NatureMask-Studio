# Limitations and Claims We Must Not Make

## Physical
- Masking never reduces source sound power or the target's physical level. Total exposure rises.
- SPL at a listener cannot be guaranteed without calibrated playback, known placement and
  propagation. Generated files carry digital levels plus an optional playback calibration note.
- ISO 9613-2 propagation needs octave-band sound power, geometry and ground data; not modelled in v1.

## Perceptual / model
- The masking estimator (NM-PSM v1) is an engineering estimate based on the power-spectrum model;
  K varies ±3 dB across listeners/frequencies; no level-dependent filters, no binaural or
  informational masking, no comodulation masking release.
- The prominence index is **not** a probability or percentage; never convert to "x % masked".
- Naturalness penalty measures deviation from the preset's own spectrum and balance — a proxy, not
  a validated naturalness metric.
- Listening tests have not been performed; no psychoacoustic validation is claimed.

## Data
- A single dBA value does not define a spectrum; templates are estimates.
- Octave → third-octave subdivision is an estimate.
- Synthetic targets reconstructed from spectra are approximations, not the machine.
- Uncalibrated recordings support relative analysis only.

## Standards
- No formal conformance with IEC 61672-1 / IEC 61260-1 (software weightings and ideal bands are
  implemented and checked against published values, but class tolerances & tests not performed).
- ISO/TS 20065 tonality not implemented in full; TNR/PR screening only.

## Safety
- Not hearing protection. Must not mask alarms, warnings, or safety-relevant speech.
- Default masker limit; warnings when calibrated mix exceeds 80 dBA (occupational action values
  start at 80 dB(A) under EU Directive 2003/10/EC — `STANDARD`-level regulatory reference, verify
  locally applicable rules).
