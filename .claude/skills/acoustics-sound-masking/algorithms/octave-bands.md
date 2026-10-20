# Algorithm: Octave / One-Third-Octave Bands and Spectrum Conversions

## Band definition (IEC 61260-1:2014, base 10)
`G = 10^(3/10)`, reference `fr = 1000 Hz`. For b = 1 (octave) and b = 3 (third-octave), b odd:
`fm(x) = fr · G^(x/b)`, edges `f1 = fm·G^(−1/(2b))`, `f2 = fm·G^(1/(2b))`.
Nominal labels (63, 125, … / 50, 63, 80, 100, …) are for display only; all math uses exact fm.
- Octaves 31.5 Hz–16 kHz: 10 bands; third-octaves 20 Hz–20 kHz: 31 bands.
- Relative bandwidth: octave 70.7 %, third-octave 23.1 %.

## Conversions (never interchange these representations)
| From → To | Operation |
|---|---|
| PSD G(f) [Pa²/Hz] → band level | `Lb = 10 log10(Σ_{f∈band} G Δf / p0²)` (partial bins: weight by overlap fraction) |
| Band levels (1/3) → octave | energy sum of the 3 constituent thirds |
| Octave → thirds (estimate) | **not unique**: distribute each octave's energy over its 3 thirds with an assumed slope (default: interpolate log-level vs log-f between neighbouring octaves, then renormalise each octave to its measured energy). Label `ESTIMATED_SUBDIVISION`. |
| Band levels → PSD (for synthesis) | `G(f) = 10^(Lb/10) p0² / (f2 − f1)` inside each band, then smooth in log-f (cubic in log-f/dB) and renormalise per band so band integrals are preserved. |
| Continuous dB curve (spectrum level dB/Hz) → band | integrate `10^(L(f)/10) p0²` over the band |
| FFT bin magnitude → level | only for tones: `L_tone = 10 log10( Σ_{peak±k} G Δf / p0²)` (integrate the peak's main lobe) |

## Example checks (implemented as tests)
- White noise spectrum level 30 dB/Hz: third-octave at 1 kHz (230.8 Hz wide) = 53.63 dB; octave
  (704.6 Hz) = 58.48 dB; difference 4.85 dB (= 10 log10 3.053).
- Tone 1 kHz at 93.98 dB ⇒ 93.98 dB in the 1 kHz third-octave band (any segment length).
- Thirds → octave sum: 3 × 60 dB ⇒ 64.77 dB.

## Interactive spectral editor rules
The editor stores the representation the user chose (`continuous` in dB/Hz spectrum level, or band
levels for b=1 / b=3). Switching views converts with the operations above and marks derived values.
Undo stack stores (representation, values). Smoothing: moving average in log-f on dB values,
followed by renormalisation of total energy (optional toggle).
