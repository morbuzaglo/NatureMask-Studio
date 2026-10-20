# Acoustic methodology (summary)

The authoritative, sourced reference is the skill `.claude/skills/acoustics-sound-masking/` (equations,
standards with verified editions, evidence labels, validation). This page summarises what the app computes.

1. **Levels.** `Lp = 20·log10(p_rms/20 µPa)`; A/C weighting per IEC 61672-1:2013 analytic response, applied
   in the time domain with a linear-phase FIR (16383 taps at 48 kHz: ≤ 0.12 dB from 31.6 Hz to 16 kHz;
   a plain bilinear IIR was 1.2 dB off at 10 kHz and is not used). Leq values in exports are time integrals.
2. **Bands.** IEC 61260-1:2014 base-10 mid-band frequencies `fm = 1000·10^(0.3x/b)`; band levels by integrating
   the Welch PSD (Hann, 0.5 s, 50 %) over ideal band edges. Octave→third subdivision is labelled an estimate.
3. **Sound power.** `Lp = Lw + DI − 10·log10(Ω r²)`, Ω = 4π (free) or 2π (on the ground); optional ISO 9613-1
   absorption (formula reproduces ISO 9613-2 Table 2 within 0.03 dB/km). Lp at another distance: −20·log10(r/d).
4. **Tonality screening.** TNR and PR with ECMA-418-1-style criteria (8 / 9 dB above 1 kHz, frequency-dependent
   below). Screening only — not ISO/TS 20065.
5. **Masking estimate NM-PSM v1.** ERB-spaced roex(p) auditory filters (Glasberg & Moore 1990); masked threshold
   `T_b = 10log10(10^((L_m,b + K − 10τ_b)/10) + 10^(Tq/10))`, K = −4 dB (power-spectrum model), τ_b = tonal
   fraction of the masker in the band, Tq = threshold in quiet (calibrated only). Margin `d_b = L_t,b − T_b`;
   prominence index `10·log10 √Σ(10^(d_b/10))²`. An engineering estimate, not validated by listening tests.
6. **Optimisation.** Variables: master level, module offsets, smooth bed EQ. `J = w1·ML + w2·AL + w3·UN` with ML =
   weighted RMS excess (dB), AL = added A-weighted level (dB), UN = EQ deviation/roughness + balance change (dB);
   SLSQP with L_A caps. Default cap: soundscape ≤ machine + 3 dB (listening tests found water sounds about 3 dB
   below road traffic preferred — Jeon et al. 2010).
7. **Synthesis.** Physically inspired procedural generators (Minnaert bubbles, OU gust processes, Markov bird
   song, Dolbear cricket rate), deterministic and chunk-invariant.
8. **Evaluation.** Always recomputed from the rendered audio; the optimizer's prediction agrees within ≈ 0.1 dB.

Key behaviour on synthetic demonstrations (`docs/validation/demonstration-results.md`): partial masking at
+3 dB soundscape-over-machine costs ≈ +5 dB total level; full masking of a tonal drill would need ≈ +15 dB;
low-frequency generators remain largely unmasked — natural masking is the wrong tool there.
