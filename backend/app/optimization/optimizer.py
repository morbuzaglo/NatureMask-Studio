"""Constrained masking optimization (skill: algorithms/optimization.md).

Decision variables x = [master_db, G_1..G_M (module offsets dB), Q_{m,1..10} (bed EQ dB, beds only)].
Objective  J = w1*ML + w2*AL + w3*UN   (definitions below, all documented in the skill)
  ML  masking loss (dB): weighted RMS of max(0, d_b + margin) over ERB bands (all terms share the unit dB,
      so weights are directly interpretable; a dB^2 version was tried and drowned the level penalty)
  AL  added level (dB): max(0, L_A,mix - L_A,target)
  UN  unnaturalness (dB): rms(EQ) + 2 rms(2nd diff EQ) + 0.3 rms(G - mean G)
Constraints: L_A,masker <= max_masker_la ; L_A,mix <= max_mix_la (when given).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize

from ..acoustics.bands import band_centres, band_power_from_psd
from ..acoustics.levels import P0, a_weighting_db
from ..psychoacoustics.auditory import roex_matrix, threshold_in_quiet_db
from ..psychoacoustics.masking import MaskingParams, band_set
from ..synthesis.scene import EQ_BANDS_HZ, MODULE_TYPES, module_psd

OBJECTIVES = {
    "max_masking": (1.0, 0.05, 0.05),
    "min_added_spl": (0.2, 1.0, 0.1),
    "balanced": (1.0, 1.0, 0.5),
    "max_naturalness": (0.3, 0.3, 2.0),
}


@dataclass
class OptimizeRequest:
    f: np.ndarray                    # PSD grid (Hz)
    target_psd: np.ndarray           # units^2/Hz (Pa^2/Hz if calibrated)
    calibrated: bool
    scene_config: dict
    fs: int = 48000
    seed: int = 1
    objective: str = "balanced"
    weights: tuple | None = None     # custom (w1, w2, w3)
    margin_db: float = 3.0
    k_db: float = -4.0
    max_masker_la: float | None = None   # dB (SPL if calibrated, else relative)
    max_mix_la: float | None = None
    allow_eq: bool = True
    tonal_bands_hz: list = field(default_factory=list)  # prominent target tones (extra weight)
    analysis_s: float = 30.0         # module analysis window = evaluation window (see generation.ANALYSIS_WINDOW_S)


def _interp_eq_db(q, freqs):
    """Bed EQ gain (dB) at arbitrary frequencies from 10 octave control gains (log interpolation)."""
    return np.interp(np.log10(freqs), np.log10(EQ_BANDS_HZ), q)


class MaskingProblem:
    def __init__(self, req: OptimizeRequest):
        self.req = req
        self.ref = P0 if req.calibrated else 1.0
        params = MaskingParams(k_db=req.k_db, margin_db=req.margin_db)
        bs = band_set(req.fs, params)
        self.fb = bs.centres
        W = roex_matrix(req.f, self.fb)
        self.Pt = W @ req.target_psd
        self.Lt = 10 * np.log10(np.maximum(self.Pt, 1e-300) / self.ref ** 2)
        # third-octave target powers (for A-weighted totals)
        self.f3, _, _ = band_centres(3, 20, min(20000, 0.45 * req.fs))
        f3_, self.T3t = band_power_from_psd(req.f, req.target_psd, 3, 20, min(20000, 0.45 * req.fs))
        self.f3 = f3_
        self.Aw3 = 10 ** (a_weighting_db(self.f3) / 10)
        self.LA_target = 10 * math.log10(max(np.sum(self.T3t * self.Aw3), 1e-300) / self.ref ** 2)
        # band relevance: ignore bands more than 45 dB below the strongest target band; A-ish importance
        rel = np.clip((self.Lt - (self.Lt.max() - 45)) / 15, 0, 1)
        self.w = bs.importance * rel
        for ft in req.tonal_bands_hz:
            self.w[int(np.argmin(np.abs(np.log(self.fb / ft))))] *= 2.0
        self.Tq = threshold_in_quiet_db(self.fb) if req.calibrated else None
        # modules
        self.mods = [m for m in req.scene_config.get("modules", []) if m.get("enabled", True)]
        self.M = len(self.mods)
        self.Pm, self.T3m, self.tonal = [], [], []
        for m in self.mods:
            fm_, pm_ = module_psd(m, req.fs, req.seed, req.analysis_s)
            pm_ = np.interp(req.f, fm_, pm_)
            self.Pm.append(W @ pm_)
            self.T3m.append(band_power_from_psd(req.f, pm_, 3, 20, min(20000, 0.45 * req.fs))[1])
            self.tonal.append(MODULE_TYPES[m["type"]].tonal_fraction)
        self.Pm = np.array(self.Pm) if self.M else np.zeros((0, len(self.fb)))
        self.T3m = np.array(self.T3m) if self.M else np.zeros((0, len(self.f3)))
        self.tonal = np.array(self.tonal)
        self.level0 = np.array([float(m.get("level_db", 0)) for m in self.mods])
        self.beds = [i for i, m in enumerate(self.mods) if MODULE_TYPES[m["type"]].is_bed] if req.allow_eq else []
        self.nq = 10 * len(self.beds)
        # initial master: masker LA = target LA - 3 dB (Jeon 2010: water ~3 dB below traffic preferred)
        la0 = self._la_masker(0.0, np.zeros(self.M), np.zeros(self.nq))
        self.master0 = self.LA_target - 3.0 - la0 if np.isfinite(la0) else 0.0

    # -- model pieces
    def _mod_lin(self, master, G):
        return 10 ** ((master + self.level0 + G) / 10)

    def _eq_lin(self, Q, freqs):
        eq = np.ones((self.M, len(freqs)))
        for j, i in enumerate(self.beds):
            eq[i] = 10 ** (_interp_eq_db(Q[10 * j:10 * j + 10], freqs) / 10)
        return eq

    def masker_band_power(self, master, G, Q):
        g = self._mod_lin(master, G)[:, None]
        return np.sum(g * self._eq_lin(Q, self.fb) * self.Pm, axis=0), g

    def _la_masker(self, master, G, Q):
        g = self._mod_lin(master, G)[:, None]
        p3 = np.sum(g * self._eq_lin(Q, self.f3) * self.T3m, axis=0)
        return 10 * math.log10(max(np.sum(p3 * self.Aw3), 1e-300) / self.ref ** 2)

    def _la_mix(self, master, G, Q):
        g = self._mod_lin(master, G)[:, None]
        p3 = np.sum(g * self._eq_lin(Q, self.f3) * self.T3m, axis=0) + self.T3t
        return 10 * math.log10(max(np.sum(p3 * self.Aw3), 1e-300) / self.ref ** 2)

    def margins(self, master, G, Q):
        pm, g = self.masker_band_power(master, G, Q)
        contrib = g * self._eq_lin(Q, self.fb) * self.Pm
        tau = np.sum(contrib * self.tonal[:, None], axis=0) / np.maximum(contrib.sum(axis=0), 1e-300)
        Lm = 10 * np.log10(np.maximum(pm, 1e-300) / self.ref ** 2)
        thr = 10 ** ((Lm + self.req.k_db - 10 * tau) / 10)
        if self.Tq is not None:
            thr = thr + 10 ** (self.Tq / 10)
        T = 10 * np.log10(thr)
        return self.Lt - T, Lm, T, tau

    def unpack(self, x):
        return x[0], x[1:1 + self.M], x[1 + self.M:]

    def terms(self, x):
        master, G, Q = self.unpack(x)
        d, *_ = self.margins(master, G, Q)
        ml = math.sqrt(float(np.sum(self.w * np.maximum(0, d + self.req.margin_db) ** 2) / max(np.sum(self.w), 1e-12)) + 1e-9)
        al = max(0.0, self._la_mix(master, G, Q) - self.LA_target)
        un = 0.0
        if self.nq:
            qq = Q.reshape(-1, 10)
            un += float(np.sqrt(np.mean(qq ** 2)))
            un += 2.0 * float(np.sqrt(np.mean(np.diff(qq, n=2, axis=1) ** 2)))
        if self.M > 1:
            un += 0.3 * float(np.sqrt(np.mean((G - G.mean()) ** 2)))
        return ml, al, un

    def J(self, x, w):
        ml, al, un = self.terms(x)
        return w[0] * ml + w[1] * al + w[2] * un


def optimize_masking(req: OptimizeRequest, pareto: bool = False) -> dict:
    t0 = time.time()
    prob = MaskingProblem(req)
    if prob.M == 0:
        raise ValueError("The scene has no enabled sound modules.")
    w = req.weights if (req.objective == "custom" and req.weights) else OBJECTIVES.get(req.objective, OBJECTIVES["balanced"])
    nvar = 1 + prob.M + prob.nq
    lb = np.concatenate([[prob.master0 - 40], np.full(prob.M, -20.0), np.full(prob.nq, -12.0)])
    ub = np.concatenate([[prob.master0 + 40], np.full(prob.M, 12.0), np.full(prob.nq, 12.0)])
    bounds = list(zip(lb, ub))
    cons = []
    if req.max_masker_la is not None:
        cons.append({"type": "ineq", "fun": lambda x: req.max_masker_la - prob._la_masker(*prob.unpack(x))})
    if req.max_mix_la is not None:
        cons.append({"type": "ineq", "fun": lambda x: req.max_mix_la - prob._la_mix(*prob.unpack(x))})

    def solve(weights, starts):
        best = None
        for s in starts:
            x0 = np.zeros(nvar)
            x0[0] = prob.master0 + s
            x0 = np.clip(x0, lb, ub)
            r = optimize.minimize(prob.J, x0, args=(weights,), method="SLSQP", bounds=bounds, constraints=cons,
                                  options={"maxiter": 300, "ftol": 1e-6})
            feas = all(c["fun"](r.x) >= -1e-3 for c in cons)
            key = (not feas, float(prob.J(r.x, weights)))
            if best is None or key < best[0]:
                best = (key, r, feas)
        return best

    (_, res, feasible) = solve(w, [0.0, 6.0, -6.0, -15.0])
    x = res.x
    master, G, Q = prob.unpack(x)
    d, Lm, T, tau = prob.margins(master, G, Q)
    ml, al, un = prob.terms(x)
    la_m, la_mix = prob._la_masker(master, G, Q), prob._la_mix(master, G, Q)
    dprime = 10 ** (d / 10)
    pi = 10 * math.log10(max(float(np.sqrt(np.sum((dprime * (prob.w > 0)) ** 2))), 1e-30))
    relevant = prob.w > 0
    audible = (d > -req.margin_db) & relevant
    # infeasibility analysis: masker level required per still-audible band
    remaining = []
    for i in np.where(audible)[0]:
        need = prob.Lt[i] + req.margin_db - req.k_db
        remaining.append({"band_hz": float(prob.fb[i]), "target_db": float(prob.Lt[i]),
                          "masker_db": float(Lm[i]), "required_masker_db": float(need),
                          "shortfall_db": float(need - Lm[i])})
    remaining.sort(key=lambda r: -r["shortfall_db"])
    lf_problem = [r for r in remaining if r["band_hz"] < 200 and r["shortfall_db"] > 6]
    notes = []
    if lf_problem:
        notes.append("Low-frequency target components (< 200 Hz) remain audible: natural sounds rarely carry enough "
                     "energy there without sounding like a storm — natural masking is expected to be ineffective "
                     "or impractically loud for these bands.")
    if not feasible:
        notes.append("Level constraints could not all be satisfied; the closest solution is shown.")
    if remaining and not lf_problem:
        notes.append(f"{len(remaining)} band(s) remain above the masking goal; consider raising the masker limit or "
                     "accepting partial masking (reduced prominence).")
    out = {
        "model": "NM-PSM v1 + objective J (engineering estimate; not validated by listening tests)",
        "objective": req.objective, "weights": list(w),
        "solution": {"master_db": float(master),
                     "module_offsets_db": {m["id"]: float(g) for m, g in zip(prob.mods, G)},
                     "bed_eq_db": {prob.mods[i]["id"]: Q[10 * j:10 * j + 10].tolist() for j, i in enumerate(prob.beds)},
                     "eq_bands_hz": EQ_BANDS_HZ},
        "terms": {"masking_loss_db": ml, "added_level_db": al, "unnaturalness_db": un},
        "levels": {"LA_target": prob.LA_target, "LA_masker": la_m, "LA_mix": la_mix,
                   "delta_LA": la_mix - prob.LA_target, "masker_to_target_LA": la_m - prob.LA_target,
                   "unit": "dB(A) re 20 uPa" if req.calibrated else "dB(A) relative (uncalibrated, dBFS-based)"},
        "bands": {"f_hz": prob.fb.tolist(), "L_target": prob.Lt.tolist(), "L_masker": Lm.tolist(),
                  "threshold": T.tolist(), "margin": d.tolist(), "weight": prob.w.tolist(), "masker_tonal_fraction": tau.tolist()},
        "prominence_index_db": pi,
        "audible_band_count": int(audible.sum()), "relevant_band_count": int(relevant.sum()),
        "remaining_audible": remaining[:12], "feasible": bool(feasible), "notes": notes,
        "solver": {"success": bool(res.success), "message": str(res.message), "iterations": int(res.nit),
                   "seconds": round(time.time() - t0, 3)},
        "constraints": {"max_masker_la": req.max_masker_la, "max_mix_la": req.max_mix_la},
    }
    if pareto:
        pts = []
        for w2 in np.geomspace(0.02, 5, 8):
            ww = (w[0], float(w2), w[2])
            (_, r2, f2) = solve(ww, [0.0, -10.0])
            ml2, al2, un2 = prob.terms(r2.x)
            pts.append({"w2": float(w2), "masking_loss": ml2, "added_level": al2, "unnaturalness": un2,
                        "LA_masker": prob._la_masker(*prob.unpack(r2.x)), "feasible": bool(f2)})
        nd = [p for p in pts if not any((q["masking_loss"] <= p["masking_loss"] and q["added_level"] <= p["added_level"]
                                          and (q["masking_loss"] < p["masking_loss"] or q["added_level"] < p["added_level"]))
                                         for q in pts)]
        out["pareto"] = {"points": pts, "non_dominated": nd}
    return out


def adaptation_curve(frame_t, frame_la, depth_db: float = 6.0, attack_s: float = 2.0, release_s: float = 6.0,
                     slew_db_s: float = 3.0, rate_hz: int = 10, duration_s: float | None = None):
    """Slow gain offset (dB) following the target's A-weighted short-time level around its median.
    Heuristic: louder target -> masker up (<= depth), quieter -> down; asymmetric smoothing + slew limit."""
    frame_t = np.asarray(frame_t, float)
    la = np.asarray(frame_la, float)
    dur = duration_s or (frame_t[-1] + 0.5)
    t = np.arange(0, dur, 1 / rate_hz)
    raw = np.clip(np.interp(t, frame_t, la - np.median(la)), -depth_db, depth_db)
    y = np.zeros_like(raw)
    a_att, a_rel = math.exp(-1 / (attack_s * rate_hz)), math.exp(-1 / (release_s * rate_hz))
    prev = 0.0
    for i, r in enumerate(raw):
        a = a_att if r > prev else a_rel
        nxt = a * prev + (1 - a) * r
        step = np.clip(nxt - prev, -slew_db_s / rate_hz, slew_db_s / rate_hz)
        prev = prev + step
        y[i] = prev
    return t, y
