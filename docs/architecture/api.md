# Local REST API

Base URL `http://127.0.0.1:8765/api` (bound to localhost only). Interactive OpenAPI docs: `http://127.0.0.1:8765/docs`.
Errors return HTTP 4xx with `{"detail": "<user-readable message>"}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | server status |
| GET | `/catalog` | presets, modules, modifiers, machine templates, demo targets, objectives, band centres |
| GET / POST | `/projects` | list / create (`{"name"}`) |
| GET / PATCH / DELETE | `/projects/{id}` | read / update name, notes, settings / delete |
| POST | `/projects/{id}/upload` | multipart file → signal summary (format, variables, fs, suggested domain) or table preview (columns, detected mapping) |
| POST | `/projects/{id}/target/signal` | `{domain, k_pa_per_unit?, reference_la?, channel, fs?}` → target + analysis |
| POST | `/projects/{id}/target/table` | `{frequency_column, level_column, representation?, quantity Lp|Lw, a_weighted, distance_m?, measured_at_m?, field}` |
| POST | `/projects/{id}/target/spectrum` | `{f[], L[], representation octave|third|continuous, quantity, distance_m?, measured_at_m?, field, directivity_db, air_absorption, tones[], pattern, uncertainty_db}` |
| POST | `/projects/{id}/target/manual` | `{la, lz?, lc?, template, distance_m?, listener_m?, pattern, uncertainty_db?}` (labelled ESTIMATED) |
| POST | `/projects/{id}/target/demo` | `{kind: drill|grinder_hf|generator_lf|fan}` (labelled SYNTHETIC) |
| GET | `/projects/{id}/target/analysis` | full analysis |
| PUT | `/projects/{id}/scene` | `{preset?, season?, time_of_day?, weather?, modules?[]}` |
| POST | `/projects/{id}/audition` | `{modules[], solo?}` → 20 s 16-bit WAV of the (unsaved) sources: mix of enabled ones, or `solo` alone at the mix's gain; header `X-Audition-Silent` |
| POST | `/projects/{id}/optimize` | `{objective, weights?, margin_db?, k_db?, masker_cap_rel_db? (null = no cap), max_mix_la?, allow_eq?, pareto?}` |
| POST | `/projects/{id}/generate` | start render job → `{job}` |
| GET | `/jobs/{job}` | `{status, progress, message, result, error}` |
| GET | `/projects/{id}/evaluation` | evaluation computed from the rendered audio |
| GET | `/projects/{id}/audio/{target|masker|mix}` | 16-bit preview WAV (common gain) |
| POST | `/projects/{id}/export` | `{formats[], stream, channels, mat_signal_domain digital|pascal, preserve_relative_level}` → job |
| GET | `/projects/{id}/exports`, `/projects/{id}/exports/{file}` | list / download |
