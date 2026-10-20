# Auditory Masking

## Established effects (`PEER_REVIEWED` / `TEXTBOOK`)
- **Simultaneous masking**: the threshold of a signal rises in the presence of a masker.
- **Power-spectrum model** (Fletcher 1940; Patterson & Moore 1986): the listener uses the auditory
  filter centred on the signal; threshold is reached when signal power at that filter's output is
  a constant fraction K of the masker power through the same filter: `P_s = K · ∫ W(f) N(f) df`.
  For a tone in broadband noise, K ≈ −2 to −6 dB (frequency dependent; "critical ratio" data).
  We default K = −4 dB and expose it.
- **Excitation pattern**: masker energy spreads to neighbouring frequencies through the filter
  skirts. The spread is asymmetric and level dependent: **upward spread of masking** — intense low
  frequency maskers mask higher frequencies better than vice-versa. Schroeder et al. (1979) spreading
  function in Bark: `SF(Δz) = 15.81 + 7.5(Δz+0.474) − 17.5 √(1+(Δz+0.474)²)` dB (level-independent
  approximation used in codecs).
- **Threshold in quiet** limits masking at very low levels (Terhardt approximation:
  `Tq = 3.64 f_k^−0.8 − 6.5 e^{−0.6(f_k−3.3)²} + 10⁻³ f_k⁴`, f_k in kHz).
- **Temporal masking**: forward (post-) masking lasts ~100–200 ms after masker offset;
  backward (pre-) masking ~5–20 ms. A masker that dips between target events lets the target be
  "glimpsed" — **dip listening**; fluctuating maskers mask less than steady ones at equal Leq.
- **Tone vs noise asymmetry**: noise masks tones better than tones mask noise (codec models use
  offsets ≈ 5.5 dB for noise-masking-tone vs 14.5 + z dB for tone-masking-noise, Johnston 1988).
- **Informational masking**: beyond energetic overlap, uncertainty and attention (e.g. birdsong
  events) reduce target salience; large inter-listener variability.
- **Partial masking**: target remains audible but quieter (partial loudness, Moore et al. 1997).

## What the evidence says about natural maskers (`PEER_REVIEWED`)
- Water sounds over road traffic: preferred when about **3 dB below** the traffic level; water
  sounds with more low-frequency energy mask traffic better (Jeon et al. 2010, JASA 127(3)).
- Fountain sound reduced traffic loudness only when traffic had **low temporal variability**;
  birdsong increased pleasantness/eventfulness more than fountains (De Coensel et al. 2011, JASA 129(4)).
- Birdsong masking more effective at lower traffic levels (< 52.5 dBA) or larger distances; more
  bird events per 30 s increased pleasantness (Hao, Kang & Wörtche 2016, JASA 140(2)).
- Galbrun & Ali (2013, JASA 133(1)), "Acoustical and perceptual assessment of water sounds and their
  use over road traffic noise": compares water-feature sounds as maskers (title verified; detailed
  findings **not re-verified** in this research pass — read before citing specifics).
⇒ Natural maskers are effective mostly for **moderate**, broadband, steady targets; they work
partly by reducing *annoyance/salience* rather than audibility.

## Heuristic engineering estimate used in NatureMask Studio (`ENGINEERING_HEURISTIC`)
Per ERB band b (centre f_b, 1-Cam spacing, 50 Hz–16 kHz ≈ 38 bands):
1. Target band power `P_t,b = ∫ W_b(f) G_t(f) df`; masker band power `P_m,b` likewise
   (roex filters; spread across bands is carried by the filter skirts).
2. Masked threshold `T_b = 10log10(10^((L_m,b + K)/10) + 10^(Tq(f_b)/10))`.
3. **Masking margin** `d_b = L_t,b − T_b` (dB). d_b < 0 ⇒ predicted masked in that band.
4. **Tonal correction**: if a tonal peak in band b passed TNR/PR screening, require extra margin
   `ΔK_tone` (default 0 dB, since the power-spectrum model is defined for tone-in-noise; for
   narrowband/tonal *maskers* (birds, insects) lower K by up to 10 dB (K_eff = K − 10·τ) — they
   mask noise poorly, so the threshold they produce is lower).
5. **Detectability index** (multiband energy detector, SDT combination): `d'_b = 10^(d_b/10)`
   (=1 at threshold), `d'_total = √Σ d'_b²`. Report `10 log10 d'_total` as "prominence index" (dB
   above the estimated detection threshold). This is a model index, **not** a probability of
   detection; we do not convert it to percentages.
6. **Temporal**: compute on short-time frames (e.g. 0.5 s) and report the distribution (median,
   90th percentile) of the prominence index — a fluctuating target is judged by its peaks.

Validation status: unit-tested against analytic cases (white noise vs tone at threshold); **not**
validated by listening tests. Known biases: ignores level-dependent filter broadening (under-
estimates upward spread at > 70 dB), ignores comodulation masking release, binaural unmasking
(BMLD up to ~15 dB for spatially separated sources), and informational masking.
