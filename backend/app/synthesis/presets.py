"""Environment presets: realistic combinations of modules with relative levels (dB), plus
season / time-of-day / weather modifiers. Levels are relative to the scene master level."""
from __future__ import annotations

import copy

PRESETS = {
    "forest_morning": {
        "name": "Forest — Morning", "description": "Moderate birdsong, soft wind, irregular leaf rustle, very light distant insects.",
        "modules": [
            {"type": "birds", "level_db": 0, "params": {"activity": 0.6, "species": ["warbler", "thrush", "finch"]}},
            {"type": "birds", "id": "birds_far", "level_db": -8, "params": {"activity": 0.5, "species": ["distant"], "distance": 0.8}},
            {"type": "wind", "level_db": -8, "params": {"strength": 0.3, "gustiness": 0.5}},
            {"type": "leaves", "level_db": -6, "params": {"activity": 0.45}},
            {"type": "crickets", "level_db": -24, "params": {"individuals": 3, "temperature_c": 16}},
            {"type": "woodpecker", "level_db": -12, "params": {"rate": 0.02}},
            {"type": "ambience", "level_db": -14, "params": {}},
        ]},
    "forest_night": {
        "name": "Forest — Night", "description": "Night insects, owl calls, faint breeze in trees.",
        "modules": [
            {"type": "night_insects", "level_db": -4, "params": {"individuals": 14}},
            {"type": "owl", "level_db": -6, "params": {"rate": 0.04}},
            {"type": "wind", "level_db": -12, "params": {"strength": 0.2, "gustiness": 0.4}},
            {"type": "leaves", "level_db": -12, "params": {"activity": 0.25}},
            {"type": "frogs", "level_db": -16, "params": {"activity": 0.3}},
            {"type": "ambience", "level_db": -14, "params": {}},
        ]},
    "meadow_summer": {
        "name": "Meadow — Summer", "description": "Constant insects, sporadic birds, open-air wind, grass.",
        "modules": [
            {"type": "cicadas", "level_db": -6, "params": {"intensity": 0.5}},
            {"type": "crickets", "level_db": -8, "params": {"individuals": 8, "temperature_c": 27}},
            {"type": "birds", "level_db": -4, "params": {"activity": 0.35, "species": ["finch", "warbler"]}},
            {"type": "wind", "level_db": -8, "params": {"strength": 0.4, "gustiness": 0.6}},
            {"type": "grass", "level_db": -8, "params": {"activity": 0.6}},
            {"type": "ambience", "level_db": -12, "params": {}},
        ]},
    "countryside_afternoon": {
        "name": "Countryside — Afternoon", "description": "Birds, light wind, leaves, distant dove, faint insects.",
        "modules": [
            {"type": "birds", "level_db": -2, "params": {"activity": 0.45, "species": ["thrush", "finch"]}},
            {"type": "birds", "id": "dove", "level_db": -10, "params": {"activity": 0.3, "species": ["dove"], "distance": 0.5}},
            {"type": "wind", "level_db": -6, "params": {"strength": 0.35}},
            {"type": "leaves", "level_db": -8, "params": {"activity": 0.4}},
            {"type": "crickets", "level_db": -18, "params": {"individuals": 4, "temperature_c": 24}},
            {"type": "ambience", "level_db": -10, "params": {}},
        ]},
    "nature_reserve": {
        "name": "Nature Reserve", "description": "Rich bird chorus, stream in the distance, leaves.",
        "modules": [
            {"type": "birds", "level_db": 0, "params": {"activity": 0.8, "species": ["warbler", "thrush", "finch"]}},
            {"type": "stream", "level_db": -8, "params": {"flow": 0.35}},
            {"type": "leaves", "level_db": -8, "params": {"activity": 0.4}},
            {"type": "frogs", "level_db": -18, "params": {"activity": 0.25}},
            {"type": "ambience", "level_db": -12, "params": {}},
        ]},
    "mountain_wind": {
        "name": "Mountain Wind", "description": "Strong gusting wind with low-frequency body, sparse distant birds.",
        "modules": [
            {"type": "wind", "level_db": 0, "params": {"strength": 0.8, "gustiness": 0.8, "low_freq": True}},
            {"type": "grass", "level_db": -8, "params": {"activity": 0.7}},
            {"type": "birds", "level_db": -14, "params": {"activity": 0.2, "species": ["distant"], "distance": 0.8}},
        ]},
    "lakeside": {
        "name": "Lakeside", "description": "Gentle lapping water, frogs, reeds, birds.",
        "modules": [
            {"type": "waves", "level_db": -4, "params": {"size": 0.15}},
            {"type": "drips", "level_db": -14, "params": {"rate": 1.0}},
            {"type": "frogs", "level_db": -6, "params": {"activity": 0.5}},
            {"type": "birds", "level_db": -6, "params": {"activity": 0.4, "species": ["warbler", "thrush"]}},
            {"type": "grass", "level_db": -10, "params": {"activity": 0.4}},
        ]},
    "riverside": {
        "name": "Riverside", "description": "Flowing stream as a broadband bed with birds and leaves.",
        "modules": [
            {"type": "stream", "level_db": 0, "params": {"flow": 0.7}},
            {"type": "birds", "level_db": -4, "params": {"activity": 0.5, "species": ["thrush", "warbler"]}},
            {"type": "leaves", "level_db": -10, "params": {"activity": 0.35}},
            {"type": "ambience", "level_db": -14, "params": {}},
        ]},
    "coastal_breeze": {
        "name": "Coastal Breeze", "description": "Distant waves, sea breeze, grass on the dunes.",
        "modules": [
            {"type": "waves", "level_db": 0, "params": {"size": 0.7}},
            {"type": "wind", "level_db": -6, "params": {"strength": 0.5, "gustiness": 0.5}},
            {"type": "grass", "level_db": -10, "params": {"activity": 0.5}},
            {"type": "birds", "level_db": -16, "params": {"activity": 0.2, "species": ["distant"], "distance": 0.9}},
        ]},
    "rainy_woodland": {
        "name": "Rainy Woodland", "description": "Steady rain on leaves, drips, occasional distant birds.",
        "modules": [
            {"type": "rain", "level_db": 0, "params": {"intensity": 0.55, "surface": "leaves"}},
            {"type": "drips", "level_db": -10, "params": {"rate": 2.0}},
            {"type": "wind", "level_db": -12, "params": {"strength": 0.3}},
            {"type": "birds", "level_db": -18, "params": {"activity": 0.15, "species": ["thrush"], "distance": 0.6}},
        ]},
    "waterfall_glade": {
        "name": "Waterfall Glade", "description": "Small waterfall — strong broadband bed incl. low frequencies.",
        "modules": [
            {"type": "waterfall", "level_db": 0, "params": {"flow": 0.9}},
            {"type": "birds", "level_db": -10, "params": {"activity": 0.4}},
            {"type": "leaves", "level_db": -14, "params": {"activity": 0.3}},
        ]},
    "custom": {"name": "Custom Environment", "description": "Start from scratch.", "modules": []},
}

MODIFIERS = {
    "time_of_day": {
        "dawn": {"birds": +4, "crickets": -6, "night_insects": -20, "owl": -20, "frogs": -4},
        "day": {},
        "dusk": {"birds": -2, "crickets": +3, "frogs": +3},
        "night": {"birds": -20, "woodpecker": -30, "cicadas": -20, "crickets": +4, "owl": +2, "frogs": +3},
    },
    "season": {
        "spring": {"birds": +3, "frogs": +3, "cicadas": -20},
        "summer": {"cicadas": +2, "crickets": +2},
        "autumn": {"birds": -4, "leaves": +2, "cicadas": -20, "crickets": -3},
        "winter": {"birds": -8, "crickets": -40, "cicadas": -40, "night_insects": -40, "frogs": -40, "wind": +2},
    },
    "weather": {
        "calm": {"wind": -6, "leaves": -4, "grass": -4},
        "breezy": {},
        "windy": {"wind": +6, "leaves": +4, "grass": +4, "birds": -3},
        "light_rain": {"birds": -4, "insects": -6},
    },
}

TEMPERATURE_BY_SEASON = {"spring": 16, "summer": 27, "autumn": 14, "winter": 4}


def build_scene_config(preset_id: str, season: str | None = None, time_of_day: str | None = None,
                       weather: str | None = None) -> dict:
    if preset_id not in PRESETS:
        raise ValueError(f"unknown preset {preset_id}")
    p = copy.deepcopy(PRESETS[preset_id])
    mods = p["modules"]
    for i, m in enumerate(mods):
        m.setdefault("id", f"{m['type']}_{i}")
        m.setdefault("enabled", True)
    for group, key in (("season", season), ("time_of_day", time_of_day), ("weather", weather)):
        if key:
            for m in mods:
                m["level_db"] += MODIFIERS[group].get(key, {}).get(m["type"], 0)
    if season and season in TEMPERATURE_BY_SEASON:
        for m in mods:
            if m["type"] in ("crickets", "night_insects"):
                m["params"]["temperature_c"] = TEMPERATURE_BY_SEASON[season]
    for m in mods:
        if m["level_db"] <= -30:
            m["enabled"] = False
    return {"preset": preset_id, "name": p["name"], "description": p["description"], "modules": mods,
            "season": season, "time_of_day": time_of_day, "weather": weather}


def list_presets():
    return [{"id": k, "name": v["name"], "description": v["description"],
             "modules": [m["type"] for m in v["modules"]]} for k, v in PRESETS.items()]
