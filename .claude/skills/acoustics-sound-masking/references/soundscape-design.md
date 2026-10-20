# Soundscape Design for Masking

## Framework
ISO 12913-1:2014 defines soundscape as the acoustic environment *as perceived/understood by people
in context*. Evaluation (ISO/TS 12913-2/-3) uses perceived affective attributes (pleasant,
chaotic, vibrant, uneventful, calm, annoying, eventful, monotonous) projected to
**ISOPleasant / ISOEventful** coordinates. These guide *evaluation* of a generated scene — they do
not specify how to synthesize it.

## Design principles (evidence-tagged)
1. **Plausibility first** (`ENGINEERING_HEURISTIC`): every component must belong to the chosen
   environment, time of day and season (no crickets at noon in winter; no gulls in a forest).
2. **Broadband bed + events** (`PEER_REVIEWED` basis): a continuous, slowly fluctuating bed (wind,
   leaves, stream, rain) supplies energetic masking; sparse foreground events (birds, frogs, drips)
   attract attention and raise pleasantness (Hao 2016; De Coensel 2011).
3. **Match the target's spectral region with a natural source of that region**:
   | Target region | Natural candidates | Notes |
   |---|---|---|
   | < 200 Hz (fans, generators, motors) | strong wind, surf, waterfall | natural sources rarely have much energy < 100 Hz without sounding like a storm → often **ineffective or impractically loud** |
   | 200 Hz–1 kHz | stream, rain on leaves, wind in trees | good |
   | 1–4 kHz (drills, saws, whine) | stream/rain highs, dense leaves, bird song | birds partially mask narrowband tones at their call frequency, intermittently |
   | 4–10 kHz (grinders, hiss) | insects (crickets 4–5 kHz, cicadas 4–8 kHz), rain, leaf rustle | sharpness ↑ |
4. **Keep fluctuation natural**: broadband modulation < 1 Hz, gust time scales 2–20 s; avoid
   pumping that tracks the machine (conspicuous). Adaptation time constants ≥ 1–3 s attack,
   4–10 s release (`ENGINEERING_HEURISTIC`).
5. **Level budget**: aim for the minimum masker level that reaches the masking goal; water sounds
   ~3 dB below the noise were preferred in listening tests (Jeon 2010). Expect total L_A to rise
   ≥ 1–3 dB when masking is substantial; report it.
6. **Stereo/space**: decorrelated beds (wide), localized events (panned, distance-filtered) improve
   realism; spatial separation between masker and target *reduces* energetic masking (binaural
   release) — a trade-off to document.

## When natural masking is expected to fail
- Strong low-frequency tones (< 150 Hz) with TNR > 15 dB.
- Impulsive/intermittent high-level events (hammer drill impacts) — peaks exceed any plausible
  steady masker; temporal masking only covers ~100–200 ms afterwards.
- Targets louder than ~70–75 dBA at the listener: the masker level needed is itself a noise
  exposure problem.
- Speech or alarms that must remain audible: masking is inappropriate.
