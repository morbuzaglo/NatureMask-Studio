# Algorithm: Sound Power Level (Lw) → Sound Pressure Level at the Listener (Lp)

Users often have a tool's **sound power level spectrum** `Lw(f)` (dB re 1 pW, per octave or
third-octave), as produced by ISO 3744 / ISO 3746 / ISO 9614 determinations and quoted in machine
declarations (EU Machinery / Outdoor Noise directives). Masking is perceived at a listener, so
the masker must be designed against `Lp(f)` at the listener position.

## Free-field point-source model (`TEXTBOOK`)
`Lp,b = Lw,b + DI_b − 10 log10(Ω r²) − A_atm,b − A_extra,b`
- Ω = 4π (free field, source away from surfaces): `−10log10(4π r²) = −20 log10 r − 10.99 dB`.
- Ω = 2π (source on a hard reflecting ground plane, hemispherical): `−20 log10 r − 7.98 dB`.
- `DI_b` directivity index toward the listener (dB; 0 if unknown — state the assumption).
- `A_atm,b = α(f_m)·r` with α from ISO 9613-1 (only relevant for r ≳ 50 m at high frequencies).
- `A_extra` (barriers, ground effect, ISO 9613-2) — not modelled in v1; must be 0 with a note.
Example: Lw = 100 dB, r = 5 m, hemispherical ⇒ Lp = 100 − 13.98 − 7.98 = 78.04 dB.

## Indoors (diffuse-field estimate, `TEXTBOOK`)
`Lp = Lw + 10 log10( Q/(4π r²) + 4/R )`, room constant `R = S ᾱ / (1 − ᾱ)`. Requires room data;
optional expert input.

## Validity
- Far field: r > ~2× the largest source dimension and > λ/2π at the lowest band of interest.
- Near-field and reflective surroundings can change Lp by several dB — show as uncertainty.
- The converted Lp spectrum is labelled `ESTIMATED_FROM_LW` with r, Ω, DI recorded.

## Consistency check
Back-conversion `Lw = Lp + 20log10 r + 10.99 (or 7.98)` reproduces the input (unit test).
