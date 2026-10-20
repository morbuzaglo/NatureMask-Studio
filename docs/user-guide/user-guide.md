# User guide

## 0. Start
Double-click `start.bat`. The browser opens at http://127.0.0.1:8765. Create a project on the
**Dashboard**, or click **Try the drill demo** for a ready-made synthetic example.
Use **Beginner** mode for a simple interface and **Expert** for all engineering controls (sidebar).

## 1. Target noise
Pick one input mode:
- **Import file** — drop a `.mat`, `.wav/.flac`, `.csv`, `.xlsx` or `.xls`.
  - Recordings: choose the **signal domain**. *Pascals* gives real dB SPL. *Digital + calibration* needs
    either a factor k (Pa per unit, e.g. from a 94 dB calibrator recording) or the LAeq measured with a meter.
    *Uncalibrated* keeps all levels relative (dB re full scale).
  - Tables: check the detected frequency/level columns, band type and quantity. Choose **Lw** for sound
    power data and enter the **listener distance** (and whether the source sits on the ground).
    Tick "A-weighted" if the table contains dBA band levels.
- **Spectrum / Lw editor** — draw octave or third-octave bars, or a continuous curve (spectrum level
  in dB/Hz). Add tonal peaks, an uncertainty band, paste frequency/level pairs, smooth, undo.
- **Manual values** — enter LA (plus optional LZ/LC). Because one dBA number does not define a spectrum,
  a machine template shapes it; the result is labelled **ESTIMATED**.
- **Demo machines** — synthetic drill, grinder, generator, fan.

The analysis shows levels, spectra (1/3, 1/1, PSD), tonal components, temporal behaviour, a waveform and
spectrogram (recordings), and a **masking difficulty** indicator with reasons.

## 2. Soundscape designer
Choose an environment preset; optionally season, time of day and weather. Sources can be enabled,
levelled, removed or added; Expert mode exposes parameters (bird activity, gustiness, cricket temperature…).
Set duration (≥ 10 s), sample rate, seed (same seed → identical audio), loop, and adaptation.

## 3. Masking laboratory
1. Pick an objective — *Balance* (default), *Maximum predicted masking*, *Minimum additional SPL*,
   *Maximum naturalness*, or *Custom weights*.
2. Set limits — by default the soundscape may be at most **3 dB louder (A-weighted) than the machine**.
3. **Run optimisation** (a few seconds). Read the tiles: soundscape − machine, total level change,
   **prominence index** (model index in dB; ≤ 0 ≈ predicted masked), bands above goal. The chart shows the
   machine, the predicted soundscape and the estimated masked threshold per auditory (ERB) band; the bar
   chart shows the margin per band (red = predicted audible).
4. **Generate soundscape**. The evaluation is then recomputed from the actual rendered audio.

If the app reports that low-frequency components remain audible, natural masking is not a realistic
solution for that machine — consider noise control at the source instead.

## 4. Audio studio
Play and switch instantly between *Machine only*, *Soundscape only* and *Machine + soundscape* (keys
1/2/3, Space). Use the **blind test** to check whether you can still detect the machine inside the
soundscape; about 50 % correct means it is effectively masked for you.
If the target came from spectrum data, the machine stream is a **synthetic approximation**.

## 5. Export center
Choose the stream (soundscape for playback; mix for listening tests), channels, formats and — for
calibrated designs — whether the MAT `sig` is normalised digital or **pressure in Pa**. "Keep levels relative"
uses one gain for all streams so their relation is preserved. Every file is re-read and validated.

## Calibrating playback
The exported soundscape is designed for a level at the listener (see report). Play it on the real
system, measure LAeq at the listener with a sound level meter, and adjust the amplifier until it matches.

## Safety
Masking increases total sound exposure. The app warns when a calibrated design exceeds the configured
limit (default 80 dBA; Settings). Never mask alarms, warnings or important speech.
