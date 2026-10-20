"""Importers: MATLAB .mat (v4-v7 via scipy, v7.3 via h5py), WAV/FLAC, CSV/XLSX/XLS spectral tables."""
from __future__ import annotations

import io
import re

import numpy as np

from ..acoustics.bands import NOMINAL_THIRD

SIG_NAMES = ["sig", "signal", "x", "y", "p", "data", "audio", "pressure"]
FS_NAMES = ["fs", "Fs", "FS", "samplerate", "sample_rate", "sr"]
CAL_NAMES = ["cal", "calibration", "calib", "sens", "sensitivity", "k", "cal_factor", "units", "unit"]


class ImportErrorUser(ValueError):
    """Error with a message that is safe and useful to show to the user."""


# ----------------------------------------------------------------------------- MAT

def _mat_scalar(v):
    a = np.asarray(v).squeeze()
    if a.dtype.kind in "US":
        return str(a)
    if a.dtype.kind == "O":
        return a
    return float(a) if a.size == 1 else a


def _matstruct_to_dict(v):
    out = {}
    try:
        names = v.dtype.names
    except AttributeError:
        return v
    if names is None:
        return v
    el = v.squeeze()
    if el.shape != ():
        el = el.flat[0]
    for n in names:
        try:
            out[n] = _mat_scalar(el[n])
        except Exception:  # pragma: no cover - defensive
            out[n] = str(el[n])
    return out


def _load_mat_v73(raw: bytes) -> dict:
    import h5py
    out = {}
    with h5py.File(io.BytesIO(raw), "r") as h:
        def walk(g, prefix=""):
            for k, v in g.items():
                if k.startswith("#"):
                    continue
                if isinstance(v, h5py.Dataset):
                    a = v[()]
                    if v.attrs.get("MATLAB_class", b"") == b"char":
                        a = "".join(chr(c) for c in np.asarray(a).ravel())
                    elif isinstance(a, np.ndarray):
                        a = a.T  # HDF5 stores MATLAB arrays column-major transposed
                    out[prefix + k] = a
                elif isinstance(v, h5py.Group):
                    walk(v, prefix + k + ".")
        walk(h)
    return out


def load_mat(raw: bytes) -> dict:
    """Return {'variables': {name: summary}, 'sig': ndarray (N x C), 'fs': float|None, ...}."""
    from scipy import io as sio
    version = "v5/v7"
    try:
        d = sio.loadmat(io.BytesIO(raw), squeeze_me=False, struct_as_record=True)
        d = {k: v for k, v in d.items() if not k.startswith("__")}
    except NotImplementedError:
        d = _load_mat_v73(raw)
        version = "v7.3 (HDF5)"
    except Exception as e:  # scipy raises ValueError for non-MAT data
        try:
            d = _load_mat_v73(raw)
            version = "v7.3 (HDF5)"
        except Exception:
            raise ImportErrorUser(f"Not a readable MATLAB file ({e}).")
    variables = {}
    for k, v in d.items():
        a = np.asarray(v) if not isinstance(v, str) else v
        variables[k] = {"shape": list(getattr(a, "shape", [])), "dtype": str(getattr(a, "dtype", "str"))}
    sig_name = next((n for n in SIG_NAMES if n in d), None)
    if sig_name is None:
        # largest numeric array
        cands = [(k, np.asarray(v)) for k, v in d.items() if isinstance(v, np.ndarray) and v.dtype.kind in "fiu"]
        cands.sort(key=lambda kv: -kv[1].size)
        sig_name = cands[0][0] if cands and cands[0][1].size > 100 else None
    if sig_name is None:
        raise ImportErrorUser("No signal variable found. Expected a variable named 'sig' (N x C samples).")
    sig = np.asarray(d[sig_name], dtype=float)
    if sig.ndim == 1:
        sig = sig[:, None]
    if sig.ndim != 2:
        raise ImportErrorUser(f"'{sig_name}' must be a vector or N x C matrix, got shape {sig.shape}.")
    if sig.shape[0] < sig.shape[1]:
        sig = sig.T  # assume more samples than channels
    fs = None
    fs_name = next((n for n in FS_NAMES if n in d), None)
    if fs_name is not None:
        fs = float(np.asarray(d[fs_name]).ravel()[0])
    t = None
    if "t" in d and fs is None:
        tt = np.asarray(d["t"], float).ravel()
        if tt.size > 1:
            fs = float(1.0 / np.median(np.diff(tt)))
    meta = {}
    for n in ["dist", "line", *CAL_NAMES]:
        if n in d:
            v = d[n]
            meta[n] = _matstruct_to_dict(v) if hasattr(v, "dtype") and getattr(v.dtype, "names", None) else _mat_scalar(v)
            if isinstance(meta[n], np.ndarray):
                meta[n] = meta[n].tolist()
    if not np.all(np.isfinite(sig)):
        bad = int(np.sum(~np.isfinite(sig)))
        sig = np.nan_to_num(sig)
        meta["warning_nonfinite_samples_zeroed"] = bad
    return {"format": f"MAT {version}", "variables": variables, "sig_name": sig_name, "sig": sig, "fs": fs,
            "fs_name": fs_name, "meta": meta, "suggested_domain": suggest_domain(sig, meta)}


def suggest_domain(sig: np.ndarray, meta: dict) -> dict:
    units = str(meta.get("units", meta.get("unit", ""))).strip().lower()
    peak = float(np.max(np.abs(sig))) if sig.size else 0.0
    if units in ("pa", "pascal", "pascals"):
        return {"domain": "PASCAL", "reason": "metadata 'units' says Pa"}
    for n in ("cal", "calibration", "cal_factor", "k", "sens", "sensitivity"):
        if n in meta and isinstance(meta[n], (int, float)):
            return {"domain": "DIGITAL_CALIBRATED", "k_pa_per_unit": float(meta[n]),
                    "reason": f"found scalar calibration variable '{n}' (please confirm it is Pa per unit)"}
    if peak <= 1.0:
        return {"domain": "DIGITAL_UNCALIBRATED", "reason": f"peak |sig| = {peak:.3g} <= 1: looks like normalised digital samples"}
    return {"domain": "PASCAL", "reason": f"peak |sig| = {peak:.3g} > 1: could be pressure in Pa (please confirm)",
            "needs_confirmation": True}


# ----------------------------------------------------------------------------- audio

def load_audio(raw: bytes) -> dict:
    import soundfile as sf
    try:
        data, fs = sf.read(io.BytesIO(raw), always_2d=True, dtype="float64")
    except Exception as e:
        raise ImportErrorUser(f"Could not read audio file ({e}). Supported: WAV, FLAC, OGG.")
    return {"format": "audio", "sig": data, "fs": float(fs), "meta": {},
            "suggested_domain": {"domain": "DIGITAL_UNCALIBRATED", "reason": "audio files store digital full-scale samples"}}


# ----------------------------------------------------------------------------- tables

_FREQ_PAT = re.compile(r"(freq|hz|^f$|^f_|band|centre|center)", re.I)
_LEVEL_PAT = re.compile(r"(spl|db|level|^l|lp|lw|leq|dba|dbz|pwl|swl)", re.I)


def load_table(raw: bytes, filename: str) -> dict:
    import pandas as pd
    name = filename.lower()
    try:
        if name.endswith(".csv") or name.endswith(".txt"):
            text = raw.decode("utf-8-sig", errors="replace")
            sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep)
        elif name.endswith(".xlsx") or name.endswith(".xlsm"):
            df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
        elif name.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(raw), engine="xlrd")
        else:
            raise ImportErrorUser("Unsupported table type. Use .csv, .xlsx or .xls.")
    except ImportErrorUser:
        raise
    except Exception as e:
        raise ImportErrorUser(f"Could not read the table ({e}).")
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)
    freq_col = next((c for c in cols if _FREQ_PAT.search(c)), None)
    num = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if freq_col is None and num:
        freq_col = num[0]
    level_cols = [c for c in num if c != freq_col]
    guess_quantity = "Lp"
    joined = " ".join(level_cols).lower()
    if re.search(r"\blw\b|pwl|swl|power", joined):
        guess_quantity = "Lw"
    a_weighted = bool(re.search(r"dba|\(a\)|_a\b|l_?a", joined))
    rep = None
    if freq_col is not None:
        fr = pd.to_numeric(df[freq_col], errors="coerce").dropna().to_numpy()
        rep = detect_representation(fr)
    preview = df.head(40).astype(object).where(df.head(40).notna(), None).values.tolist()
    return {"columns": cols, "preview": preview, "row_count": int(len(df)),
            "suggested": {"frequency_column": freq_col, "level_columns": level_cols,
                          "representation": rep, "quantity": guess_quantity, "a_weighted": a_weighted},
            "_df": df}


def detect_representation(freqs) -> str:
    """'octave', 'third' or 'continuous' from the set of frequencies (matches nominal labels)."""
    f = np.asarray(freqs, float)
    f = f[f > 0]
    if f.size == 0:
        return "continuous"
    noms = np.array(NOMINAL_THIRD, float)
    near = np.array([np.min(np.abs(np.log(noms / x))) < 0.03 for x in f])
    if not near.all() or f.size > 40:
        return "continuous"
    ratios = np.diff(np.log2(np.sort(f)))
    if ratios.size and np.median(ratios) > 0.8:
        return "octave"
    return "third"


def table_to_spectrum(df, frequency_column: str, level_column: str, representation: str | None = None,
                      a_weighted: bool = False) -> dict:
    """Clean a two-column table into a spectrum: drops invalid rows, merges duplicates energetically."""
    import pandas as pd
    from ..acoustics.levels import a_weighting_db
    f = pd.to_numeric(df[frequency_column], errors="coerce").to_numpy(float)
    L = pd.to_numeric(df[level_column], errors="coerce").to_numpy(float)
    warnings = []
    ok = np.isfinite(f) & np.isfinite(L) & (f > 0)
    if (~ok).sum():
        warnings.append(f"{int((~ok).sum())} row(s) with missing/invalid values were ignored")
    f, L = f[ok], L[ok]
    if np.any((L < -20) | (L > 200)):
        warnings.append("levels outside -20..200 dB found; check units")
    if f.size == 0:
        raise ImportErrorUser("No valid frequency/level rows.")
    order = np.argsort(f)
    f, L = f[order], L[order]
    uf, inv = np.unique(f, return_inverse=True)
    if uf.size < f.size:
        warnings.append(f"{f.size - uf.size} duplicated frequency row(s) were energy-averaged")
        L = np.array([10 * np.log10(np.mean(10 ** (L[inv == i] / 10))) for i in range(uf.size)])
        f = uf
    rep = representation or detect_representation(f)
    if a_weighted:
        L = L - a_weighting_db(snap_to_exact(f) if rep != "continuous" else f)
        warnings.append("A-weighting removed from band levels (levels converted to Z/unweighted)")
    return {"f": f.tolist(), "L": L.tolist(), "representation": rep, "warnings": warnings}


def snap_to_exact(f_nominal):
    """Nominal band label -> exact base-10 mid-band frequency."""
    f = np.asarray(f_nominal, float)
    x = np.round(10 * np.log10(f / 1000.0))
    return 1000.0 * 10 ** (x / 10)
