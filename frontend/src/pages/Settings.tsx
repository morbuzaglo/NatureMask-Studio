import { useState } from "react";
import { api } from "../services/api";
import { useStudio } from "../hooks/useStudio";
import { Field, Notice, PageHeader, Panel, Tabs } from "../components/ui";

export default function SettingsPage() {
  const { project, theme, setTheme, mode, setMode, refresh, toast } = useStudio();
  const [warn, setWarn] = useState(project?.settings.max_output_warning_dba ?? 80);
  return (
    <div>
      <PageHeader title="Settings" sub="Calibration, safety limits, preferences. Everything is stored locally." />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Calibration: digital samples vs Pascals">
          <div className="space-y-3 text-[13px] leading-relaxed text-muted">
            <p><b className="text-text">Digital audio has no physical unit.</b> A WAV sample of 0.5 means "half of full scale" — it says nothing about loudness in the room until the recording chain or the playback chain is calibrated.</p>
            <p><b className="text-text">Pascals are physical.</b> Sound pressure level is <span className="num text-text">Lp = 20·log10(p_rms / 20 µPa)</span>. Signals in Pa (e.g. from a calibrated measurement system) give real dB SPL.</p>
            <p><b className="text-text">Calibrating a recording.</b> Record a 94 dB (1 Pa) acoustic calibrator through the same chain: <span className="num text-text">k = 1 Pa / x_rms</span>. Or enter a reference LAeq measured with a sound level meter at the same position.</p>
            <p><b className="text-text">Calibrating playback.</b> The app cannot know your speaker gain or placement. To reproduce the design SPL, play the exported soundscape, measure LAeq at the listener with a sound level meter and adjust the gain until it matches the design value shown in the report.</p>
            <p><b className="text-text">Uncertainty.</b> Typical contributions (calibrator, microphone, positioning) combine as the root-sum-square; ±1–3 dB at the listener is common. Treat small predicted differences accordingly.</p>
          </div>
        </Panel>
        <div className="space-y-5">
          <Panel title="Safety">
            <Notice tone="bad">Masking does not reduce the machine's noise; it adds sound. It is not hearing protection, and it must not be used to hide alarms, warnings or speech that matters.</Notice>
            {project && (
              <div className="mt-4 flex items-end gap-3">
                <Field label="Warn when the calibrated combined level exceeds (dBA)"><input className="input" type="number" value={warn} onChange={(e) => setWarn(+e.target.value)} /></Field>
                <button className="btn" onClick={() => api.patchProject(project.id, { settings: { max_output_warning_dba: warn } }).then(refresh).then(() => toast("Saved", "success")).catch((e) => toast(e.message, "error"))}>Save</button>
              </div>
            )}
            <p className="mt-2 text-[12px] text-faint">For reference, EU Directive 2003/10/EC sets the lower exposure action value at 80 dB(A) (daily exposure). Check the rules that apply to you.</p>
          </Panel>
          <Panel title="Preferences">
            <div className="flex flex-wrap gap-6">
              <div><div className="label mb-2">Theme</div><Tabs value={theme} onChange={setTheme} items={[{ id: "dark", label: "Dark" }, { id: "light", label: "Light" }]} /></div>
              <div><div className="label mb-2">Interface</div><Tabs value={mode} onChange={setMode} items={[{ id: "beginner", label: "Beginner" }, { id: "expert", label: "Expert" }]} /></div>
            </div>
          </Panel>
          <Panel title="Local processing">
            <ul className="space-y-1.5 text-[13px] text-muted">
              <li>Server: <span className="num text-text">http://127.0.0.1:8765</span> (this computer only)</li>
              <li>Projects, renders and exports: <span className="num text-text">NatureMask-Studio\data\projects</span></li>
              <li>Logs: <span className="num text-text">NatureMask-Studio\data\logs\naturemask.log</span></li>
              <li>No internet connection, account or cloud service is used after installation.</li>
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
