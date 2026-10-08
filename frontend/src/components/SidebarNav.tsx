import {
  AuditOutlined,
  MessageOutlined,
  HistoryOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { setMobileNavOpen, useMobileNavOpen } from "../state/mobileNav";
import { PvcbLogo } from "./PvcbLogo";
import { SeaLionMascot } from "./SeaLionMascot";
import { getPendingQueue, useReviewStore } from "../state/reviewStore";
import { NAVY } from "../config";
import { IS_STATIC_DEMO } from "../api/client";

const ACTIVE_BG = "rgba(99,136,255,0.18)";
const HOVER_BG  = "rgba(255,255,255,0.06)";

function NavItem({
  icon, label, badge, active, onClick,
}: {
  icon: React.ReactNode; label: string; badge?: number;
  active?: boolean; onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "8px 14px", borderRadius: 6, cursor: "pointer",
        background: active ? ACTIVE_BG : "transparent",
        color: active ? "#fff" : "rgba(255,255,255,0.6)",
        fontWeight: active ? 600 : 400,
        fontSize: 13.5, margin: "1px 6px",
        transition: "background 0.12s, color 0.12s",
      }}
      onMouseEnter={e => { if (!active) (e.currentTarget as HTMLDivElement).style.background = HOVER_BG; }}
      onMouseLeave={e => { if (!active) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
    >
      <span style={{ fontSize: 15, opacity: active ? 1 : 0.7, width: 18, display: "flex", justifyContent: "center" }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span style={{
          background: "#2F54EB", color: "#fff",
          fontSize: 10, fontWeight: 700, borderRadius: 10,
          padding: "1px 7px", minWidth: 20, textAlign: "center",
        }}>
          {badge}
        </span>
      )}
    </div>
  );
}

export function SidebarNav() {
  const { t } = useTranslation();
  const navigate  = useNavigate();
  const { pathname } = useLocation();
  useReviewStore();
  const queue = getPendingQueue();

  const onVessel   = pathname.startsWith("/app/vessel");
  const onQueue    = pathname === "/app/queue";
  const onHistory  = pathname === "/app/history";

  const mobileOpen = useMobileNavOpen();
  useEffect(() => { setMobileNavOpen(false); }, [pathname]);

  return (
    <>
    <div className="pvcb-backdrop" data-open={mobileOpen} onClick={() => setMobileNavOpen(false)} />
    <div className="pvcb-sidebar" data-open={mobileOpen} style={{
      width: 220, flexShrink: 0,
      background: NAVY,
      display: "flex", flexDirection: "column",
      height: "100vh", position: "sticky", top: 0,
      overflowY: "auto",
    }}>

      {/* Brand — 48px to align with AppHeader */}
      <div style={{ height: 48, padding: "0 14px", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <PvcbLogo size={28} />
        <div>
          <div style={{ color: "#fff", fontWeight: 700, fontSize: 13, letterSpacing: "-0.01em", lineHeight: 1.2 }}>PVCB</div>
          <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 10, letterSpacing: "0.02em" }}>{t("nav.sub")}</div>
        </div>
      </div>

      {/* Nav items */}
      <div style={{ padding: "8px 0", flex: 1 }}>
        <NavItem
          icon={<span style={{ fontSize: 12 }}>⊞</span>}
          label={t("nav.overview")}
          active={pathname === "/app"}
          onClick={() => navigate("/app")}
        />
        <NavItem
          icon={<span style={{ fontSize: 14 }}>🚢</span>}
          label={t("nav.vessel")}
          active={onVessel}
          onClick={() => {
            const last = localStorage.getItem("pvcb_last_project") ?? "demo_ship_a";
            navigate("/app/vessel", { state: { projectId: last } });
          }}
        />
        <NavItem
          icon={<AuditOutlined />}
          label={t("nav.queue")}
          badge={queue.length}
          active={onQueue}
          onClick={() => navigate("/app/queue")}
        />
        <NavItem
          icon={<HistoryOutlined />}
          label={t("nav.history")}
          active={onHistory}
          onClick={() => navigate("/app/history")}
        />
        <NavItem
          icon={<MessageOutlined />}
          label={t("nav.ask")}
          active={pathname === "/app/ask"}
          onClick={() => navigate("/app/ask")}
        />
        <NavItem
          icon={<QuestionCircleOutlined />}
          label={t("nav.guide")}
          onClick={() => navigate("/guide")}
        />
      </div>

      {/* Mascot */}
      <div style={{ padding: "12px 0 8px", display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
        <SeaLionMascot pending={queue.length} />
        <span style={{ fontSize: 9.5, color: "rgba(255,255,255,0.25)", letterSpacing: ".03em" }}>{IS_STATIC_DEMO ? t("staticDemo.badge") : t("nav.workspace")}</span>
      </div>
    </div>
    </>
  );
}
