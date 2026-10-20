# Standards — Editions, Scope, Relevance, Limits

Editions verified 2026-10-20 via ISO/IEC catalogue pages or national-body catalogues (see
`source-bibliography.md`). No standard text is reproduced. "Equations" lists only widely published
forms; the operative requirements (tolerances, test procedures) need the purchased standard.
**No formal compliance is claimed by NatureMask Studio for any of these.**

| Standard | Edition (verified) | Scope (short) | Relevance here | Used for | Limitations |
|---|---|---|---|---|---|
| IEC 61672-1 Sound level meters — Specifications | Ed. 2.0, 2013-09-30 (replaces 2002) | performance specs of SLMs: frequency weightings A, C, Z; time weightings F, S; class 1/2 tolerances | **Direct** | A/C/Z weighting equations, F/S time constants | software weighting ≠ certified SLM; tolerances apply to instruments |
| IEC 61260-1 Octave-band & fractional-octave-band filters | Ed. 1.0, 2014 | base-10 band definitions (G = 10^0.3), filter classes and attenuation masks | **Direct** | exact mid-band and edge frequencies; band integration | our FFT/PSD band integration uses ideal brick-wall edges, not a class-1 filter |
| ISO 1996-1 Environmental noise — Basic quantities & assessment | 2016 (3rd ed.) | descriptors, rating levels, adjustments for tonal/impulsive/low-frequency sound | Background | terminology (L_Aeq, rating level), concept of tonal adjustment | rating levels are for assessment, not masking design |
| ISO 1996-2 Determination of sound pressure levels | 2017 (2nd ed.) | measurement procedures, uncertainty, objective tonality methods (annex) | Background / measurement | measurement guidance, uncertainty reporting | we don't perform field measurement |
| ISO 532-1 Loudness — Zwicker method | 2017 | stationary + time-varying loudness (sone, phon) for otologically normal listeners | **Direct (optional)** | loudness of target/masker/mix (via MoSQITo, Apache-2.0, implements ISO 532-1) | needs calibrated Pa input; partial loudness of target in masker not covered |
| ISO 532-2 Moore-Glasberg | 2017 | stationary loudness | Background | — | — |
| ISO 532-3 Moore-Glasberg-Schlittenlacher | 2023 | stationary + time-varying loudness | Background | future model upgrade | not implemented |
| ISO 226 Equal-loudness contours | 2023 | pure-tone equal-loudness levels 20 Hz–12.5 kHz | Background | justification of A-weighting / threshold | — |
| ISO 389-7 Threshold of hearing (free/diffuse field) | 2019 | reference thresholds | Background | threshold in quiet (we use Terhardt approximation, labelled) | approximation error up to a few dB |
| ISO/TS 20065 Audibility of tones in noise — engineering method | 2022 (Ed. 1) | objective tone audibility for f ≥ 50 Hz | **Direct (concept)** | tonal-target screening & audibility concept | our TNR/PR screening is simpler; not ISO/TS 20065 conformant |
| ECMA-418-1 / ECMA-418-2 | 418-2 4th ed. June 2025 (free PDF) | TNR, PR (418-1); Sottek hearing-model loudness, tonality, roughness (418-2) | **Direct (concept)** | TNR/PR criteria, future tonality model | criteria designed for IT equipment noise |
| ISO 9613-1 Atmospheric absorption | 1993, confirmed (reviewed 2026) | pure-tone absorption coefficient vs f, T, RH, p | Optional spatial module | α(f) (formula reproduces ISO 9613-2 Table 2 within 0.03 dB/km) | — |
| ISO 9613-2 Outdoor propagation — engineering method | Ed. 2, 2024-01 | octave-band prediction of L_Aeq downwind from known L_W | Optional spatial module | future source→receiver attenuation | needs L_W, geometry, ground; **not** a masking algorithm |
| ISO 12913-1 Soundscape — definition & framework | 2014 | definition, conceptual framework (people, acoustic environment, context) | Design framing | vocabulary; perception is contextual | no generation algorithm |
| ISO/TS 12913-2 Data collection & reporting | 2018 | questionnaires, binaural measurement, reporting | Evaluation design | listening-test questionnaire structure | — |
| ISO/TS 12913-3 Data analysis | 2025 (2019 ed. withdrawn 2026-01) | analysis of perceptual data, e.g. pleasantness/eventfulness circumplex | Evaluation design | ISOPleasant/ISOEventful from 8 PAQ attributes | — |
| ISO/TS 12913-4 Design & intervention | in development (FDIS stage 2026) | soundscape intervention | Watch | — | unpublished |
| ISO 3744 / ISO 3746 / ISO 9614 (sound power determination) | editions not verified in this pass | determination of Lw from pressure or intensity measurements | **Input source** | users may supply Lw spectra from these methods; we convert Lw→Lp (algorithms/sound-power-to-receiver.md) | we don't perform these measurements |
| ISO 3382-3 Open-plan offices | 2022 | spatial decay of speech: D2,S, Lp,A,S,4m, comfort distance rC (45 dB), distraction distance rD (STI 0.5) | Related only | conceptual analogy (masking for privacy) | speech privacy, not machine masking |

## Key consequences for the app
- Weightings and bands follow IEC 61672-1 / IEC 61260-1 definitions → testable against tabulated
  values (done in `reference_impl.py`).
- Loudness (ISO 532-1) can be computed when Pa-calibrated; label results "ISO 532-1 via MoSQITo".
- Tonality: screen with TNR/PR criteria (ECMA-418-1 style); state that ISO/TS 20065 is the
  engineering standard for tone audibility and is not implemented in full.
- Soundscape standards guide *evaluation* (questionnaires, pleasantness/eventfulness), not synthesis.
