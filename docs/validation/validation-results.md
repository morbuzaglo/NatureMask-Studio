# Validation results (2026-10-20)

| Suite | Scope | Result |
|---|---|---|
| Skill reference checks (`reference_impl.py --selftest`) | SPL, energy sums, A/C weighting vs IEC 61672-1 table, bands, Parseval, ERB/Bark, roex, threshold, TNR/PR criteria, masked threshold, ISO 9613-1 vs ISO 9613-2 Table 2 | 42/42 PASS |
| `tests/unit` | acoustics, importers (MAT v5/v7.3, WAV, CSV/XLSX), masking model (M1–M8 cases), synthesis (all 16 modules: finite, seeded, chunk-invariant; presets; spectra; loop; 2-min stability), optimizer (constraints, infeasibility, objectives, Pareto, adaptation, templates) | PASS |
| `tests/integration` | full API workflow: Example 4 octave spectrum, Example 5 MAT (uncalibrated: no SPL), Pa recording, Lw→Lp, Lp distance correction, CSV/manual, errors, explicit null cap | PASS |
| `tests/acoustic_validation` | predicted vs rendered soundscape level (4 presets), gust duration-independence & unit energy, scene prefix independence | PASS |
| Total pytest | | **102 passed** |
| MATLAB R2021b | `verify_mat_in_matlab.m` on the Pa export | PASS (`matlab-verification.md`) |
| Browser (Edge via Playwright) | `tests/ui/ui_walkthrough.py`: dashboard → demo → analysis → editor → environment → optimise → generate → studio playback → export → light theme | PASS, 0 console errors, 6/6 exported files valid |
| Demonstrations | Examples 1–5 | `demonstration-results.md` |

## Defects found by validation and fixed
1. Tonal-masker offset had the wrong sign (unit test).
2. Bilinear A-weighting IIR 1.2 dB off at 10 kHz → linear-phase FIR (unit test).
3. Band→PSD renormalisation 0.06 dB error at shared edges → iterative renormalisation (unit test).
4. Frog clicks and spiky rain (spectrogram inspection).
5. dB² masking loss drove every objective to the level cap (optimizer study).
6. Welch-based Leq 0.18 dB off for fluctuating sound → time-domain Leq (MATLAB cross-check).
7. Predicted vs rendered soundscape level off by 7.5 dB (browser walkthrough) → exact-window analysis,
   normalised duration-independent gusts.
8. API ignored an explicit `null` level cap (demonstration run).

## Not validated
Perceived masking, naturalness and annoyance (no listening tests yet — protocol in the skill's
`validation/reference-cases.md`).
