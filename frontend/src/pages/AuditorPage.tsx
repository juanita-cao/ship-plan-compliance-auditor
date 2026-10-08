import { Alert, Button, Collapse, Select, Spin } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { CalendarOutlined, FlagOutlined, IdcardOutlined, TagOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { get, post, type DetectResult, type ProjectInfo } from "../api/client";
import { CategoryButton } from "../components/CategoryButton";
import { DeckSelector } from "../components/DeckSelector";
import { CompliancePanel } from "../components/CompliancePanel";
import { ImageCard } from "../components/SpotlightCard";
import { MetricsRow } from "../components/MetricsRow";
import { ReasoningTrace } from "../components/ReasoningTrace";
import { ReviewPanel } from "../components/ReviewPanel";
import { SidebarNav } from "../components/SidebarNav";
import { AppHeader } from "../components/AppHeader";
import { VESSEL_META } from "../config";
import { addAnalyzed, getDeckStatus, getLatestHistory, useReviewStore } from "../state/reviewStore";
import { ReviewCompleteCard } from "../components/ReviewCompleteCard";
import { UploadWorkspace } from "../components/UploadWorkspace";
import { PlanStepper } from "../components/PlanStepper";
import { flagLabel, typeLabel, vesselName } from "../domain/vessels";
import { useAppDispatch, useAppState } from "../state/store";

// ─── Vessel header ────────────────────────────────────────────────────────────

function VesselHeader({ project }: { project: ProjectInfo }) {
  const { t, i18n } = useTranslation();
  const meta = VESSEL_META[project.id];
  const item = (icon: React.ReactNode, text: string) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>{icon}{text}</span>
  );
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#1d2129", marginBottom: 4 }}>{vesselName(project.id, project.label)}</div>
      {meta && (
        <div style={{ display: "flex", gap: 18, fontSize: 12.5, color: "#6b7280", flexWrap: "wrap" }}>
          {item(<TagOutlined />, typeLabel(meta.type, i18n.language))}
          {item(<IdcardOutlined />, meta.imo)}
          {item(<FlagOutlined />, flagLabel(meta.flag, i18n.language))}
          {item(<CalendarOutlined />, t("vessel.built", { year: meta.yearBuilt }))}
        </div>
      )}
    </div>
  );
}

const SECTION: React.CSSProperties = { background: "#fff", border: "1px solid #e5e8ed", borderRadius: 10, padding: "16px 20px", marginTop: 16 };

// ─── Page ─────────────────────────────────────────────────────────────────────

export interface AutoAnalyze { projectId: string; imageStem: string; key: string }

export function AuditorPage({ auto }: { auto?: AutoAnalyze | null }) {
  const { t } = useTranslation();
  const state = useAppState();
  const dispatch = useAppDispatch();
  useReviewStore();
  const ranAuto = useRef<string | null>(null);
  const scrolledAuto = useRef<string | null>(null);
  const [canReview, setCanReview] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);

  // Persist last-opened vessel so sidebar "Vessel" link can restore it
  useEffect(() => {
    try { localStorage.setItem("pvcb_last_project", state.projectId); } catch {}
  }, [state.projectId]);

  const { data: projects = [] } = useQuery<ProjectInfo[]>({
    queryKey: ["projects"],
    queryFn: () => get<ProjectInfo[]>("/projects"),
    staleTime: Infinity,
  });

  const currentProject = projects.find(p => p.id === state.projectId);
  const currentImages  = currentProject?.images ?? [];
  const currentCats    = currentProject?.categories ?? [];
  const imageLabel     = currentImages.find(i => i.stem === state.imageStem)?.label ?? state.imageStem ?? "";

  // Auto-select first deck when project loads
  useEffect(() => {
    if (!state.imageStem && currentImages.length > 0) {
      dispatch({ type: "imageChanged", imageStem: currentImages[0].stem });
    }
  }, [currentImages, state.imageStem, dispatch]);

  // A requested deck that this vessel does not have falls back to its first deck
  useEffect(() => {
    if (state.imageStem && currentImages.length > 0 && !currentImages.some(i => i.stem === state.imageStem)) {
      dispatch({ type: "imageChanged", imageStem: currentImages[0].stem });
    }
  }, [currentImages, state.imageStem, dispatch]);

  const runAnalysis = async (stem: string, record: boolean) => {
    if (!currentProject) return;
    const label = currentImages.find(i => i.stem === stem)?.label ?? stem;
    if (stem !== state.imageStem) dispatch({ type: "imageChanged", imageStem: stem });
    dispatch({ type: "analyzeClicked" });
    try {
      const result = await post<DetectResult>("/detect", { project_id: state.projectId, image_stem: stem });
      if (record) {
        addAnalyzed({
          projectId: state.projectId,
          projectLabel: currentProject.label,
          imageStem: stem,
          imageLabel: label,
          instanceCount: result.instances.length,
          aiVerdict: result.compliance_result?.verdict ?? undefined,
        });
      }
      setCanReview(record || getDeckStatus(state.projectId, stem) !== "reviewed");
      dispatch({ type: "detectComplete", result });
    } catch {
      dispatch({ type: "detectError", message: t("vessel.detectFailed") });
    }
  };

  const handleAnalyze = () => (state.imageStem ? runAnalysis(state.imageStem, true) : Promise.resolve());

  const isRunning = state.stage === "RUNNING";
  useEffect(() => { setUploadOpen(false); }, [state.projectId]);
  const vName = vesselName(state.projectId, currentProject?.label);
  const crumbs = [
    { label: t("nav.overview"), to: "/app" },
    ...(state.stage === "RESULTS"
      ? [{ label: vName, to: "/app/vessel", state: { projectId: state.projectId } }, { label: imageLabel }]
      : [{ label: vName }]),
  ];

  useEffect(() => {
    if (!auto || ranAuto.current === auto.key) return;
    if (state.stage !== "IDLE" || state.projectId !== auto.projectId || state.imageStem !== auto.imageStem || !currentProject) return;
    ranAuto.current = auto.key;
    void handleAnalyze();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, state.stage, state.projectId, state.imageStem, currentProject]);

  useEffect(() => {
    if (!auto || state.stage !== "RESULTS" || scrolledAuto.current === auto.key) return;
    scrolledAuto.current = auto.key;
    window.setTimeout(() => document.getElementById("human-review")?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
  }, [auto, state.stage]);

  return (
    <div style={{ display: "flex", alignItems: "stretch", minHeight: "100vh", flex: 1 }}>
      {/* ── Sidebar (always visible) ──────────────────────────────────────── */}
      <SidebarNav />

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <AppHeader crumbs={crumbs} />

        {/* ═══ IDLE / RUNNING ══════════════════════════════════════════════ */}
        {(state.stage === "IDLE" || state.stage === "RUNNING") && (
          <div style={{ padding: "24px var(--gutter)" }}>
            {/* Vessel selector row */}
            <div className="pvcb-vessel-row">
              <div style={{ flex: 1 }}>
                {currentProject && <VesselHeader project={currentProject} />}
              </div>
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 2 }}>
                {currentProject && currentImages.length > 0 && !uploadOpen && (
                  <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)} disabled={isRunning} title={t("upload.stepsTip")}>{t("upload.button")}</Button>
                )}
                <Select
                  value={state.projectId}
                  onChange={id => dispatch({ type: "projectChanged", projectId: id })}
                  options={projects.map(p => ({ value: p.id, label: vesselName(p.id, p.label) }))}
                  style={{ width: 160 }}
                  size="middle"
                />
              </div>
            </div>

            {currentProject && (currentImages.length === 0 || uploadOpen) && (
              <UploadWorkspace
                key={state.projectId}
                projectId={state.projectId}
                hasDecks={currentImages.length > 0}
                onCancel={currentImages.length > 0 ? () => setUploadOpen(false) : undefined}
                onAdded={images => { setUploadOpen(false); if (images[0]) dispatch({ type: "imageChanged", imageStem: images[0].stem }); }}
              />
            )}

            {currentProject && currentImages.length > 0 && !uploadOpen && <div style={SECTION}><PlanStepper current={4} /></div>}

            {currentProject && currentImages.length > 0 && !uploadOpen && (
              <div style={SECTION}>
                <DeckSelector
                  project={currentProject}
                  selectedStem={state.imageStem}
                  onSelect={stem => dispatch({ type: "imageChanged", imageStem: stem })}
                  onViewResults={stem => runAnalysis(stem, false)}
                  disabled={isRunning}
                />
              </div>
            )}

            {/* Preview + run */}
            {state.imageStem && currentImages.length > 0 && !uploadOpen && (
              <div style={SECTION}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#8c8c8c", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                    {t("vessel.preview", { deck: imageLabel })}
                  </div>
                  <Button
                    type="primary" size="large"
                    disabled={!state.imageStem || isRunning}
                    loading={isRunning}
                    onClick={handleAnalyze}
                    style={{ fontWeight: 600, minWidth: 180 }}
                  >
                    {isRunning ? t("vessel.analyzing") : t("vessel.runAnalysis")}
                  </Button>
                </div>
                <div style={{ border: "1px solid #eef0f3", borderRadius: 8, padding: 12, position: "relative", background: "#fafbfc" }}>
                  {isRunning && (
                    <div style={{ position: "absolute", inset: 0, background: "rgba(255,255,255,0.85)", borderRadius: 8, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", zIndex: 1 }}>
                      <Spin size="large" />
                      <div style={{ marginTop: 14, fontSize: 14, color: "#595959" }}>{t("vessel.analyzingPlan")}</div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#bfbfbf" }}>{t("vessel.runningPipeline")}</div>
                    </div>
                  )}
                  <ImageCard
                    projectId={state.projectId}
                    imageStem={state.imageStem}
                    selectedCategory={null}
                    selectedInstanceId={null}
                    title=""
                    noCard
                  />
                </div>
              </div>
            )}

            {/* Error + Run button */}
            {state.lastError && (
              <Alert type="error" message={state.lastError} style={{ marginTop: 16 }} />
            )}
          </div>
        )}

        {/* ═══ RESULTS ═════════════════════════════════════════════════════ */}
        {state.stage === "RESULTS" && (() => {
          const vm = state.detectResult!;
          const totalAll = Object.values(vm.total_by_category).reduce((a, b) => a + b, 0);
          const isAllActive = !state.selectedCategory && !state.selectedInstanceId;
          const resultCats = vm.is_sample ? (projects.find(p => p.id === "demo_ship_a")?.categories ?? currentCats) : currentCats;

          return (
            <div style={{ padding: "0 var(--gutter) 40px" }}>
              {/* Breadcrumb + vessel selector + New Analysis */}
              <div className="pvcb-results-bar">
                <div>
                  <Select
                    value={state.projectId}
                    onChange={id => { dispatch({ type: "projectChanged", projectId: id }); dispatch({ type: "newAnalysisClicked" }); }}
                    options={projects.map(p => ({ value: p.id, label: vesselName(p.id, p.label) }))}
                    style={{ width: 160, marginRight: 4 }}
                    size="middle"
                  />
                  <span style={{ color: "#8c8c8c", margin: "0 6px" }}>›</span>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>
                    {currentImages.find(i => i.stem === vm.image_stem)?.label ?? vm.image_stem}
                  </span>
                  {getDeckStatus(vm.project_id, vm.image_stem) === "reviewed" && (
                    <span style={{ marginLeft: 10, fontSize: 11, fontWeight: 700, color: "#389e0d", background: "rgba(56,158,13,0.1)", padding: "2px 8px", borderRadius: 8 }}>
                      {t("vessel.reviewedTag")}
                    </span>
                  )}
                </div>
                <Button onClick={() => dispatch({ type: "newAnalysisClicked" })}>{t("vessel.newAnalysis")}</Button>
              </div>

              {vm.is_sample && (
                <Alert type="info" showIcon style={{ marginBottom: 12 }} message={t("vessel.sampleBanner", { label: vm.sample_label ?? "" })} />
              )}

              <MetricsRow totalByCategory={vm.total_by_category} />

              <div className="pvcb-result-grid">
                <ImageCard projectId={vm.project_id} imageStem={vm.image_stem} selectedCategory={null} selectedInstanceId={null} title={t("vessel.originalPlan")} />
                <ImageCard projectId={vm.project_id} imageStem={vm.image_stem} selectedCategory={state.selectedCategory} selectedInstanceId={state.selectedInstanceId} title={vm.is_sample ? t("vessel.highlightSample") : t("vessel.highlight")} spotlight />
                <div style={{ background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: "#1d2129", marginBottom: 10 }}>{t("vessel.inventory")}</div>
                  <Button type={isAllActive ? "primary" : "default"} block style={{ marginBottom: 8 }} onClick={() => dispatch({ type: "showAllClicked" })}>
                    {t("vessel.allFound")} <span style={{ marginLeft: "auto", fontWeight: 600 }}>×{totalAll}</span>
                  </Button>
                  {resultCats.map(cat => (
                    <CategoryButton key={cat.id} categoryId={cat.id} label={cat.label} color={cat.color} count={vm.total_by_category[cat.id] ?? 0} instances={vm.instances.filter(i => i.category === cat.id)} />
                  ))}
                </div>
              </div>

              {vm.compliance_result && (
                <div style={{ marginTop: 16, background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
                  <CompliancePanel result={vm.compliance_result} />
                </div>
              )}

              {vm.raw_response && (
                <Collapse
                  style={{ marginTop: 16 }}
                  items={[{
                    key: "trace",
                    label: <span style={{ fontWeight: 600 }}>{t("vessel.trace")}</span>,
                    children: <ReasoningTrace raw={vm.raw_response} />,
                  }]}
                />
              )}

              {/* Human Review */}
              {canReview ? (
                <ReviewPanel
                  result={vm}
                  projectLabel={currentProject?.label ?? ""}
                  imageLabel={imageLabel}
                  categories={resultCats}
                />
              ) : (() => {
                const last = getLatestHistory(vm.project_id, vm.image_stem);
                return last ? <ReviewCompleteCard entry={last} /> : null;
              })()}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
