# Procedural Natural-Sound Synthesis

All generators are deterministic given a seed (`numpy.random.default_rng(seed)` per module,
derived seeds `seed ⊕ hash(module_id)`), stream in chunks, and expose a long-term spectral
envelope for the optimizer. Typical parameters are `ENGINEERING_HEURISTIC` unless cited.

## Shared building blocks
- **Ornstein–Uhlenbeck (OU) process** for slow natural modulation:
  `dx = θ(μ − x) dt + σ √(2θ) dW` — mean-reverting, time constant 1/θ (e.g. 3–15 s for wind).
- **Poisson event scheduler** with time-varying rate λ(t) (thinning algorithm); refractory period;
  bursts via a two-state Markov (active/quiet) chain — avoids metronomic repetition.
- **Envelopes**: attack–decay (exponential), raised-cosine; all events windowed to avoid clicks.
- **Spatialization**: constant-power pan `gL = cos(θ), gR = sin(θ)`, distance via level (−6 dB per
  doubling) + air-absorption low-pass (ISO 9613-1 α(f)·r) + optional small inter-channel delay.
  Beds: two decorrelated noise streams (coherence < 0.2) for width.

## Wind
Broadband noise shaped by a low-pass/band-pass whose cutoff follows gust intensity:
`g(t) = OU(θ=1/6 s⁻¹)`, intensity `I = exp(g)`; level ∝ 20log10 I; spectral centroid rises with I
(fc ≈ 300 Hz · I^0.7). Add "whistle/howl" resonances (narrow band-pass 300–1200 Hz, slowly gliding)
at low weight; leaf layer modulated by the same gust signal (coherence = realism).

## Leaves / vegetation rustle
Granular: many short (5–40 ms) bursts of high-pass noise (1–8 kHz) with random spectral tilt;
grain density λ(t) = λ0·I(t)^2 driven by the wind gust process. Grass: denser, softer, lower
amplitude, low-pass at 6 kHz.

## Water: stream, waterfall, drips, rain
- **Bubble resonance** (Minnaert 1933, `TEXTBOOK`): `f0 ≈ 3.26 / a` Hz for bubble radius a in m
  (a = 3 mm → ≈ 1.09 kHz). Each bubble = decaying sinusoid with upward pitch glide (~10–30 %):
  `s(t) = A e^{−t/τ} sin(2π ∫ f0(1+ε t/τ) dt)`, τ ≈ 5–30 ms (van den Doel 2005 "Physically-based
  models for liquid sounds").
- **Stream** = Poisson bubble cloud (radius log-normal, 100–2000 events/s) + broadband turbulence
  noise shaped 200 Hz–4 kHz. **Waterfall** = very dense cloud + strong low-frequency noise.
- **Drips** = sparse single bubbles + resonant body (cave/rock) filter.
- **Rain**: drop impacts as Poisson (rate ∝ intensity), each a short noise burst + small bubble
  ping; surface type (leaves/ground/water) sets filter; distant rain = smooth pink-ish bed.
- **Waves**: noise with 6–14 s swell envelope (asymmetric: fast rise, slow decay), low-pass sweep
  following the envelope (wash), plus fizzing high band on the decay.

## Birds (avoid "random noise called birdsong")
- Syllable = tonal sweep with harmonics: `f(t) = f0 + Δf·shape(t/T)` (shapes: up, down, ∩, ∪,
  trill (sinusoidal FM 15–40 Hz)), T = 20–250 ms, f0 ∈ 1.5–8 kHz, harmonics at −10…−25 dB.
  Amplitude envelope smooth; slight AM; phase-continuous oscillator.
- Song = sequence of syllables from a per-"species" grammar (first-order Markov over 3–6
  syllable types, repetition counts), song duration 1–4 s, inter-song interval drawn from a
  species-specific gamma distribution; dawn chorus raises rate.
- Species-like presets (generic, not real species claims): warbler-like (fast trills 4–7 kHz),
  thrush-like (fluty phrases 1.5–4 kHz), finch-like (short chirp series 3–6 kHz), dove-like coo
  (300–600 Hz, low density). Distance: level + low-pass + reverb tail.

## Insects
- **Cricket**: carrier 3.5–5.5 kHz (tonal), pulses 10–30 ms grouped into chirps (3–5 pulses);
  chirp rate depends on temperature — Dolbear's law (1897) for the snowy tree cricket:
  `T(°F) = 50 + (N − 40)/4`, N chirps/min (used as a plausible temperature→rate mapping, labelled).
- **Cicada**: dense buzz, carrier 4–8 kHz with fast AM (100–500 Hz), slow swells over 5–30 s.
- **Night insects**: many detuned cricket-like voices with jitter and random phases.

## Frogs
Pulsed croaks: carrier 300 Hz–2 kHz with formant filters, pulse rate 5–60 Hz, call bouts; chorus
of several voices with mutual timing offsets.

## Ambience and details
Distant broadband "air" bed (pink, −35 dB rel.), occasional distant animal calls, branch creaks
(low-frequency resonant scrape), and reverberation (Schroeder/FDN, RT 0.3–1.5 s outdoors is short:
use early reflections + diffuse tail low level).

## Recorded assets (optional)
Only CC0/public-domain or self-recorded files with a provenance record (`assets/LICENSES.md`:
source URL, author, license, date, processing). The engine never requires assets.
