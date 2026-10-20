"""Sound power -> sound pressure at a listener, and ISO 9613-1 atmospheric absorption.

See skill: algorithms/sound-power-to-receiver.md. Free-field point-source model only; ground effect,
barriers and meteorology (ISO 9613-2) are NOT modelled.
"""
from __future__ import annotations

import math

import numpy as np

OMEGA = {"free": 4 * math.pi, "hemispherical": 2 * math.pi, "quarter": math.pi}


def atmospheric_absorption_db_per_m(f, t_c: float = 20.0, rh: float = 70.0, pa_kpa: float = 101.325):
    """ISO 9613-1 pure-tone attenuation coefficient (dB/m)."""
    T0, T01, pr = 293.15, 273.16, 101.325
    T = t_c + 273.15
    psat_pr = 10 ** (-6.8346 * (T01 / T) ** 1.261 + 4.6151)
    h = rh * psat_pr * (pr / pa_kpa)
    pa_pr = pa_kpa / pr
    frO = pa_pr * (24.0 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    frN = pa_pr * (T / T0) ** -0.5 * (9.0 + 280.0 * h * np.exp(-4.170 * ((T / T0) ** (-1 / 3) - 1)))
    f = np.asarray(f, float)
    return 8.686 * f ** 2 * (1.84e-11 / pa_pr * (T / T0) ** 0.5 + (T / T0) ** -2.5 * (
        0.01275 * np.exp(-2239.1 / T) / (frO + f ** 2 / frO) + 0.1068 * np.exp(-3352.0 / T) / (frN + f ** 2 / frN)))


def lw_to_lp(fm, lw, distance_m: float, field: str = "hemispherical", directivity_db=0.0,
             air_absorption: bool = False, t_c: float = 20.0, rh: float = 70.0):
    """Lp,b = Lw,b + DI - 10 log10(Omega r^2) - alpha(f) r. Returns (Lp, details)."""
    if distance_m <= 0:
        raise ValueError("distance must be > 0")
    if field not in OMEGA:
        raise ValueError(f"field must be one of {list(OMEGA)}")
    fm = np.asarray(fm, float)
    lw = np.asarray(lw, float)
    geo = 10 * math.log10(OMEGA[field] * distance_m ** 2)
    di = np.broadcast_to(np.asarray(directivity_db, float), fm.shape)
    att = atmospheric_absorption_db_per_m(fm, t_c, rh) * distance_m if air_absorption else np.zeros_like(fm)
    lp = lw + di - geo - att
    return lp, {"geometric_divergence_db": geo, "omega_sr": OMEGA[field], "field": field,
                "distance_m": distance_m, "air_absorption_db": att.tolist(), "directivity_db": di.tolist(),
                "model": "free-field point source; ISO 9613-1 air absorption optional; no ground/barrier effects",
                "provenance": "ESTIMATED_FROM_LW"}


def lp_to_lw(fm, lp, distance_m: float, field: str = "hemispherical", directivity_db=0.0):
    geo = 10 * math.log10(OMEGA[field] * distance_m ** 2)
    return np.asarray(lp, float) - np.asarray(directivity_db, float) + geo


def distance_correction_db(r_from: float, r_to: float) -> float:
    return -20 * math.log10(r_to / r_from)
