"""NM-PSM v1 masking estimator (engineering heuristic on the power-spectrum model of masking).

Not validated by listening tests. See skill: algorithms/masking-models.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..acoustics.levels import P0, a_weighting_db
from .auditory import erb_band_centres, filter_powers, threshold_in_quiet_db

MODEL_NAME = "NM-PSM v1 (power-spectrum model, roex ERB filters; engineering estimate)"


@dataclass
class MaskingParams:
    k_db: float = -4.0               # signal-to-masker ratio at threshold within the auditory filter
    margin_db: float = 3.0           # desired safety margin below threshold
    use_threshold_in_quiet: bool = True  # only meaningful when calibrated
    fmin: float = 50.0
    fmax: float = 16000.0


@dataclass
class BandSet:
    centres: np.ndarray
    importance: np.ndarray = field(default=None)


def band_set(fs: float, params: MaskingParams) -> BandSet:
    fmax = min(params.fmax, 0.45 * fs)
    c = erb_band_centres(params.fmin, fmax, 1.0)
    # importance: A-weighting relevance (0 dB -> 1, -20 dB -> 0.1), floor 0.05
    imp = np.clip(10 ** (a_weighting_db(c) / 20.0), 0.05, 1.2)
    return BandSet(c, imp)


def levels_db(power, ref):
    return 10 * np.log10(np.maximum(power, 1e-300) / ref ** 2)


def estimate(f, psd_target, psd_masker, ref: float, calibrated: bool, params: MaskingParams | None = None,
             fs: float = 48000.0, masker_tonal_fraction=None, tonal_bands=None) -> dict:
    """Band-wise masking margins and prominence index.

    psd_target / psd_masker: one-sided PSDs on grid f in the SAME units (Pa^2/Hz or FS^2/Hz).
    masker_tonal_fraction: optional array (per ERB band, 0..1) — tonal maskers mask noise less well.
    """
    params = params or MaskingParams()
    bs = band_set(fs, params)
    pt = filter_powers(f, psd_target, bs.centres)
    pm = filter_powers(f, psd_masker, bs.centres)
    lt, lm = levels_db(pt, ref), levels_db(pm, ref)
    # tonal maskers (bird/insect partials) mask noise-like targets less well -> LOWER effective K
    k_eff = params.k_db - (10.0 * np.asarray(masker_tonal_fraction) if masker_tonal_fraction is not None else 0.0)
    thr_lin = 10 ** ((lm + k_eff) / 10)
    if calibrated and params.use_threshold_in_quiet:
        thr_lin = thr_lin + 10 ** (threshold_in_quiet_db(bs.centres) / 10)
    thr = 10 * np.log10(thr_lin)
    d = lt - thr
    dprime = 10 ** (d / 10)
    pi = 10 * np.log10(max(float(np.sqrt(np.sum(dprime ** 2))), 1e-30))
    audible = d > -params.margin_db
    worst = int(np.argmax(d))
    return {
        "model": MODEL_NAME,
        "bands_hz": bs.centres, "importance": bs.importance,
        "L_target": lt, "L_masker": lm, "threshold": thr, "margin": d,
        "prominence_index_db": float(pi),
        "audible_band_count": int(np.sum(audible)), "band_count": int(len(d)),
        "worst_band_hz": float(bs.centres[worst]), "worst_margin_db": float(d[worst]),
        "masker_to_target_db": lm - lt,
        "params": {"k_db": params.k_db, "margin_db": params.margin_db,
                   "threshold_in_quiet": bool(calibrated and params.use_threshold_in_quiet)},
        "assumptions": [
            "Power-spectrum model: target detectable when filter-output power exceeds K x masker power",
            "Symmetric level-independent roex(p) filters, 1-ERB spacing",
            "No binaural, comodulation or informational masking; K varies about +-3 dB across listeners",
            "Prominence index is a model index in dB, not a probability or percentage",
        ],
    }


def time_varying(frames_target_psd, psd_masker, f, ref, calibrated, params=None, fs=48000.0):
    """Prominence index per frame for a time-varying target against a (stationary) masker."""
    pis = []
    for p in frames_target_psd:
        pis.append(estimate(f, p, psd_masker, ref, calibrated, params, fs)["prominence_index_db"])
    pis = np.array(pis)
    return {"pi_frames": pis, "median": float(np.median(pis)), "p90": float(np.percentile(pis, 90)),
            "max": float(np.max(pis))}
