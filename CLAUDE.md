# NatureMask Studio — project notes for Claude Code

Local Windows web app that generates natural soundscapes optimised to perceptually mask machine
noise. Backend Python/FastAPI (`backend/app`), frontend React+TS+Vite (`frontend/`).

## Always
- Load the `acoustics-sound-masking` skill (`.claude/skills/acoustics-sound-masking/SKILL.md`) for
  any acoustics, masking, DSP or synthesis work; follow its ground rules (no SPL without
  calibration, estimates labelled, masking ≠ noise reduction, no invented percentages).
- Every dataset carries `domain` (PASCAL / DIGITAL_CALIBRATED / DIGITAL_UNCALIBRATED /
  SPECTRUM_ONLY) and `provenance` (MEASURED / ESTIMATED / SYNTHETIC).
- Keep everything offline; never send user audio anywhere.

## Commands
- Python env: `.venv\Scripts\python.exe` (packages in `requirements.txt`).
- Tests: `.venv\Scripts\python.exe -m pytest -q tests`
- Skill reference checks: `python .claude/skills/acoustics-sound-masking/scripts/reference_impl.py --selftest`
- Run app: `start.bat` (builds frontend if needed, starts backend on http://127.0.0.1:8765).
- MATLAB R2021b is installed (`matlab -batch`) and used to verify MAT exports.

## Machine notes
- Project lives in OneDrive; keep `.venv`, `node_modules`, `data/` out of git (see .gitignore).
- Commit at each milestone; update `docs/implementation-checklist.md`.
