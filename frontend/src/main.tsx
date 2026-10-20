import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/instrument-serif/400.css";
import "./styles.css";
import { Layout } from "./components/Layout";
import { StudioProvider } from "./hooks/useStudio";
import Dashboard from "./pages/Dashboard";
import TargetNoise from "./pages/TargetNoise";
import Soundscape from "./pages/Soundscape";
import MaskingLab from "./pages/MaskingLab";
import AudioStudio from "./pages/AudioStudio";
import ExportCenter from "./pages/ExportCenter";
import SettingsPage from "./pages/Settings";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <StudioProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/target" element={<TargetNoise />} />
            <Route path="/soundscape" element={<Soundscape />} />
            <Route path="/masking" element={<MaskingLab />} />
            <Route path="/studio" element={<AudioStudio />} />
            <Route path="/export" element={<ExportCenter />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Dashboard />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StudioProvider>
  </React.StrictMode>,
);
