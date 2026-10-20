# Algorithm: Masking Optimization

## Decision variables
`x = [G_1 … G_M, Q_1 … Q_B']` — module gains in dB (G_m ∈ [−40, +20] dB relative to preset level)
and smooth EQ gains in dB for bed modules on B' ≈ 10 control bands (octave-spaced, interpolated
to ERB bands), Q ∈ [−12, +12] dB.

## Terms (all dimensionless or in dB, documented meaning)
1. **MaskingLoss** (dB²): mean over ERB bands of squared positive excess over the goal,
   weighted by target importance `w_b` (A-weighting-derived relevance + tonal emphasis ×2):
   `ML = Σ_b w_b · max(0, d_b + margin)² / Σ_b w_b`. ML = 0 ⇔ every band meets the margin.
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
   | Balance masking/naturalness (default) | (1, 0.5, 0.5) |
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
Compute target ERB-band levels per 0.5 s frame → optimal per-frame broadband gain offset
`ΔG(t) = clip(required − static, 0, ΔG_max)` → smooth with asymmetric one-pole filter
(attack τa = 2 s, release τr = 6 s defaults) → applied as a slowly varying gain on bed modules and
as event-rate multiplier `(1 + 0.5·ΔG/ΔG_max)` on event modules. Limits: |dG/dt| ≤ 3 dB/s.
