# Algorithm: Masking Optimization

## Decision variables
`x = [master, G_1 … G_M, Q_1 … Q_B']` — scene master level (dB, ±40 dB around the start value that puts
the masker 3 dB below the target in L_A), module offsets G_m ∈ [−20, +12] dB relative to the preset
balance, and smooth EQ gains for bed modules on 10 octave-spaced control points (31.6 Hz…15.8 kHz,
log-interpolated), Q ∈ [−12, +12] dB. Module spectra are pre-reduced to ERB-band and third-octave
powers so one objective evaluation costs microseconds; SLSQP from 4 starts.

## Terms (all dimensionless or in dB, documented meaning)
1. **MaskingLoss** (dB): weighted RMS of the positive excess over the goal across ERB bands,
   weights `w_b` = A-weighting-derived importance × relevance (bands > 45 dB below the strongest target
   band ignored) × 2 for prominent tones: `ML = √(Σ_b w_b · max(0, d_b + margin)² / Σ_b w_b)`.
   ML = 0 ⇔ every relevant band meets the margin. **Units matter (tested):** a dB² version made the
   masking term dominate any dB-based level penalty, so *every* objective drove the masker to its cap
   ("louder is better"). With all three terms in dB, weights are directly interpretable.
2. **AddedLevelPenalty** (dB): `AL = max(0, L_A,mix − L_A,target)` — increase of overall
   A-weighted level caused by the masker (equivalently a function of masker-to-target ratio).
3. **UnnaturalnessPenalty** (dB): `UN = √(mean_b Q̃_b²) + λ_s √(mean (Δ²Q̃)²) + λ_r √(mean_m (G_m − Ḡ)²)`
   — EQ deviation from the natural spectrum (RMS dB), EQ roughness (2nd difference), and deviation
   of module balance from the preset's mix (keeps the scene's character). λ_s = 2, λ_r = 0.3.
4. **J** `= w1·ML + w2·AL + w3·UN` with user-selectable weight presets:
   | Objective | (w1, w2, w3) |
   |---|---|
   | Maximum predicted masking | (1, 0.05, 0.05) |
   | Minimum additional SPL | (0.2, 1, 0.1) |
   | Balance masking/naturalness (default) | (1, 1, 0.5) |
   | Maximum naturalness | (0.3, 0.3, 2) |
   | Custom | user |

## Constraints (hard)
- `L_A,masker ≤ Lmax_masker` (user, default target L_A + 3 dB, never > 85 dB when calibrated).
- `L_A,mix ≤ Lmax_mix` (user).
- Bounds on G, Q. Digital headroom handled at render time (global gain), not in the optimizer.

## Solver
SLSQP (scipy.optimize.minimize) from 3 starts (preset, preset+6 dB broadband, preset −6 dB);
keep best feasible. Gradients by finite differences (cheap: model is band-domain, ~38 bands × M
modules). Pareto exploration: sweep w2 over 8 log-spaced values, record (ML, AL) pairs, return
non-dominated set.

## Infeasibility reporting
If the minimum achievable ML under constraints is > 0: report which bands remain audible and the
masker level that *would* be required in those bands (`L_req,b = L_t,b + margin − K`), and whether
that exceeds plausible natural levels or the constraints → "natural masking ineffective/
impractical for these bands". Never silently raise the level.

## Temporal adaptation (time-varying targets)
Implemented (heuristic): A-weighted target level per 0.5 s frame → `ΔG(t) = clip(L_A,frame − median, ±depth)`
(default depth 6 dB) → asymmetric one-pole smoothing (attack 2 s, release 6 s) → slew limit 3 dB/s →
applied as gain to bed modules (full depth) and event modules (half depth). Quieter target ⇒ quieter
masker (saves exposure); louder target ⇒ masker rises slowly, never tracking individual onsets.

## Observed behaviour on synthetic demo targets (2026-10-20, NM-PSM v1, unconstrained)
| Target / preset | Objective | masker − target L_A | ΔL_A total | prominence index |
|---|---|---|---|---|
| drill / countryside | max masking | +14.7 dB | +14.9 dB | −1.2 dB |
| drill / countryside | balanced | +2.9 dB | +4.7 dB | +10.5 dB |
| drill / countryside | min added SPL | −7.0 dB | +0.8 dB | +20.4 dB |
| generator (LF tones) / mountain wind | max masking | +11.8 dB | +12.1 dB | +1.5 dB |
Interpretation: full energetic masking of tonal machinery by natural sound costs ≈ 12–15 dB of extra
level — usually unacceptable; realistic designs give partial masking (reduced prominence) at +1…+5 dB.
Default constraint in the app: `L_A,masker ≤ L_A,target + 3 dB` (editable in Expert mode).
