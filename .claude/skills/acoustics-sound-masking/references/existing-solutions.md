# Existing Solutions and Libraries

## Sound masking / soundscape products (approaches, not endorsements)
| Approach | Examples | Idea to reuse | Shortcoming for our goal |
|---|---|---|---|
| Office sound masking (shaped broadband noise, ceiling emitters, ~40–48 dBA) | commercial systems (e.g. Cambridge Sound Management QtPro, Biamp/Atlas lines — product details UNVERIFIED) | spectrum shaping to a target curve; zoning; slow ramp-up | targets speech privacy (ISO 3382-3 context), not machine noise; not natural |
| Adaptive masking | systems that raise masker level with measured background | slow-time-constant adaptation | can become conspicuous; "louder" bias |
| Personal noise generators | myNoise (S. Pigeon, 2013): 10 octave sliders, user hearing calibration, shape generator to the nuisance spectrum | user-calibrated per-octave shaping; masking at lower levels by spectral matching | no measurement integration, no objective masking estimate |
| Nature apps | rain/forest loops | — | loops repeat; no masking logic |
| Soundscape augmentation research | water/birdsong added to traffic noise (Jeon 2010; De Coensel 2011; Hao 2016) | evidence on levels and event density | lab listening tests, traffic noise only |
| Procedural audio | Farnell, "Designing Sound" (2010); van den Doel liquid sounds; granular synthesis | physically inspired models | needs careful tuning for realism |
| Audio texture synthesis | McDermott & Simoncelli (2011) statistics-based texture synthesis | textures defined by auditory statistics | heavy; not used in v1 |
| Neural generative audio | text-to-audio models (local) | realism | large models, licensing, non-deterministic, not offline-light → optional future plug-in |

## Libraries evaluated
| Library | License | Use | Decision |
|---|---|---|---|
| NumPy / SciPy | BSD | FFT, Welch, filters, optimization (SLSQP), resample_poly, loadmat/savemat | **core** |
| soundfile (libsndfile) | BSD-3 | WAV PCM16/24/float32 read/write | **core** |
| h5py | BSD | MATLAB v7.3 (HDF5) import | **core** |
| openpyxl / xlrd / pandas | MIT/BSD | xlsx / xls / csv import | **core** |
| FastAPI + uvicorn | MIT/BSD | local REST API | **core** |
| MoSQITo 1.2.1 (2024-04) | Apache-2.0 | ISO 532-1 loudness, DIN 45692 sharpness, roughness, TNR/PR | optional add-on (deps numpy, scipy, pyuff) |
| python-acoustics | BSD | octave helpers | not used (unmaintained) |
| React + TypeScript + Vite | MIT | UI | **core** |
| Plotly.js (react-plotly) | MIT | interactive log-frequency plots | **core** |
| Web Audio API | browser | low-latency preview, A/B | **core** |
| Tailwind CSS | MIT | styling | **core** |
