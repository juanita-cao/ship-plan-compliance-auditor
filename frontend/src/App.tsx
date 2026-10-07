import { Spin } from "antd";
import { Suspense, useEffect, useState } from "react";
import { I18nextProvider } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthLayout } from "./layouts/AuthLayout";
import { ProtectedLayout } from "./layouts/ProtectedLayout";
import { GuidePage } from "./pages/GuidePage";
import { LoginPage } from "./pages/LoginPage";
import { AuditorPage, type AutoAnalyze } from "./pages/AuditorPage";
import { VesselOverviewPage } from "./pages/VesselOverviewPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { HistoryPage } from "./pages/HistoryPage";
import { AskPage } from "./pages/AskPage";
import { AuthContext, loadAuth, makeAuthActions } from "./state/authContext";
import { AppDispatchContext, AppStateContext, useAppStore } from "./state/store";
import { createI18n } from "./i18n";
import type { i18n } from "i18next";
import type { AuthState } from "./state/authContext";

function AuditorShell() {
  const [state, dispatch] = useAppStore();
  const loc = useLocation();
  const [auto, setAuto] = useState<AutoAnalyze | null>(null);

  // Navigation state from Overview / Queue / "Next in queue": select vessel (+ deck) and optionally auto-run analysis
  useEffect(() => {
    const st = loc.state as { projectId?: string; imageStem?: string; autoAnalyze?: boolean } | null;
    if (!st?.projectId) return;
    const projectDiffers = st.projectId !== state.projectId;
    if (projectDiffers || st.imageStem) dispatch({ type: "newAnalysisClicked" });
    if (projectDiffers) dispatch({ type: "projectChanged", projectId: st.projectId });
    if (st.imageStem) dispatch({ type: "imageChanged", imageStem: st.imageStem });
    if (st.autoAnalyze && st.imageStem) setAuto({ projectId: st.projectId, imageStem: st.imageStem, key: loc.key });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.key]);

  return (
    <AppStateContext.Provider value={state}>
      <AppDispatchContext.Provider value={dispatch}>
        <AuditorPage auto={auto} />
      </AppDispatchContext.Provider>
    </AppStateContext.Provider>
  );
}

export function App() {
  const [i18nInstance, setI18nInstance] = useState<i18n | null>(null);
  const [auth, setAuth] = useState<AuthState>(loadAuth);
  const actions = makeAuthActions(setAuth);

  useEffect(() => {
    createI18n().then(setI18nInstance);
  }, []);

  if (!i18nInstance) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <I18nextProvider i18n={i18nInstance}>
      <AuthContext.Provider value={{ auth, ...actions }}>
        <BrowserRouter>
          <Suspense fallback={<Spin />}>
            <Routes>
              <Route element={<AuthLayout />}>
                <Route path="/" element={<LoginPage />} />
                <Route path="/login" element={<LoginPage />} />
              </Route>
              <Route element={<ProtectedLayout />}>
                <Route path="/app" element={<VesselOverviewPage />} />
                <Route path="/app/vessel" element={<AuditorShell />} />
                <Route path="/app/queue" element={<ReviewQueuePage />} />
                <Route path="/app/history" element={<HistoryPage />} />
                <Route path="/app/ask" element={<AskPage />} />
                <Route path="/guide" element={<GuidePage />} />
              </Route>
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthContext.Provider>
    </I18nextProvider>
  );
}
