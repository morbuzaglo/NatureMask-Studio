"""Local JSON + NumPy project storage (no database server, no network)."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid

import numpy as np

_LOCK = threading.RLock()


def data_dir() -> str:
    d = os.environ.get("NATUREMASK_DATA_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")
    os.makedirs(os.path.join(d, "projects"), exist_ok=True)
    return d


def projects_root() -> str:
    return os.path.join(data_dir(), "projects")


def project_dir(pid: str) -> str:
    if not pid or any(c in pid for c in "/\\.:"):
        raise KeyError("invalid project id")
    p = os.path.join(projects_root(), pid)
    if not os.path.isdir(p):
        raise KeyError(f"project {pid} not found")
    return p


def _json_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def create(name: str) -> dict:
    pid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = os.path.join(projects_root(), pid)
    os.makedirs(d)
    proj = {"id": pid, "name": name or "Untitled project", "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated": None, "target": None, "scene": None, "optimization": None, "settings": default_settings(),
            "render": None, "notes": ""}
    save(proj)
    return proj


def default_settings() -> dict:
    return {"fs": 48000, "duration_s": 60, "seed": 1, "loop": False, "loop_crossfade_s": 3.0, "preview_s": 60,
            "adaptive": False, "adapt_depth_db": 6.0, "k_db": -4.0, "margin_db": 3.0, "objective": "balanced",
            "weights": [1.0, 1.0, 0.5], "masker_cap_rel_db": 3.0, "max_mix_la": None, "allow_eq": True,
            "max_output_warning_dba": 80.0}


def load(pid: str) -> dict:
    with _LOCK:
        with open(os.path.join(project_dir(pid), "project.json"), encoding="utf-8") as fh:
            return json.load(fh)


def save(proj: dict) -> dict:
    with _LOCK:
        proj["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        p = os.path.join(projects_root(), proj["id"], "project.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(proj, fh, indent=1, default=_json_default)
        os.replace(tmp, p)
    return proj


def list_projects() -> list:
    out = []
    for pid in sorted(os.listdir(projects_root()), reverse=True):
        try:
            p = load(pid)
        except Exception:
            continue
        out.append({"id": p["id"], "name": p["name"], "created": p["created"], "updated": p["updated"],
                    "target": (p["target"] or {}).get("name"), "target_domain": (p["target"] or {}).get("domain"),
                    "preset": (p["scene"] or {}).get("name"), "rendered": bool(p.get("render"))})
    return out


def delete(pid: str):
    shutil.rmtree(project_dir(pid))


def save_arrays(pid: str, name: str, **arrays):
    np.savez_compressed(os.path.join(project_dir(pid), f"{name}.npz"), **arrays)


def load_arrays(pid: str, name: str) -> dict:
    with np.load(os.path.join(project_dir(pid), f"{name}.npz"), allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def has_arrays(pid: str, name: str) -> bool:
    return os.path.exists(os.path.join(project_dir(pid), f"{name}.npz"))
