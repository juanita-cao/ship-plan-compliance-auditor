import { LogoutOutlined, MenuOutlined, QuestionCircleOutlined, RedoOutlined } from "@ant-design/icons";
import { Button, Dropdown, Modal, Tooltip, message } from "antd";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../state/authContext";
import { resetDemoData } from "../state/reviewStore";
import { setMobileNavOpen } from "../state/mobileNav";
import { LanguageSwitch } from "./LanguageSwitch";

const NAVY = "#0a1e3d";

export interface Crumb { label: string; to?: string; state?: unknown }

export function AppHeader({ crumbs = [] }: { crumbs?: Crumb[] }) {
  const { t } = useTranslation();
  const { auth, logout } = useAuth();
  const navigate = useNavigate();

  const confirmReset = () => {
    Modal.confirm({
      title: t("header.resetTitle"),
      content: t("header.resetBody"),
      okText: t("header.resetOk"),
      cancelText: t("common.cancel"),
      onOk: () => {
        resetDemoData();
        message.success(t("header.resetDone"));
        navigate("/app");
      },
    });
  };

  return (
    <header className="pvcb-header" style={{
      height: 48, background: NAVY, padding: "0 20px 0 24px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexShrink: 0, borderBottom: "1px solid rgba(255,255,255,0.06)",
    }}>
      <button className="pvcb-burger" aria-label="Menu" onClick={() => setMobileNavOpen(true)}>
        <MenuOutlined />
      </button>
      <nav aria-label="Breadcrumb" className="pvcb-crumbs" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, minWidth: 0, flex: 1 }}>
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <span key={i} style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              {i > 0 && <span style={{ color: "rgba(255,255,255,0.25)" }}>›</span>}
              {c.to && !last
                ? <Link to={c.to} state={c.state} style={{ color: "rgba(255,255,255,0.6)", whiteSpace: "nowrap" }}>{c.label}</Link>
                : <span style={{ color: last ? "#fff" : "rgba(255,255,255,0.6)", fontWeight: last ? 600 : 400, whiteSpace: "nowrap" }}>{c.label}</span>}
            </span>
          );
        })}
      </nav>
      <div className="pvcb-header-actions" style={{ display: "flex", alignItems: "center", gap: 2, flexShrink: 0 }}>
        <LanguageSwitch onDark />
        <Tooltip title={t("header.guide")}>
          <Link to="/guide" style={{ display: "flex", alignItems: "center", padding: "0 8px", height: 40 }}>
            <QuestionCircleOutlined style={{ color: "rgba(255,255,255,0.5)", fontSize: 16 }} />
          </Link>
        </Tooltip>
        <Dropdown
          trigger={["click"]}
          menu={{ items: [
            { key: "reset", icon: <RedoOutlined />, label: t("header.reset"), onClick: confirmReset },
            { key: "logout", icon: <LogoutOutlined />, label: t("header.logout"), onClick: logout },
          ] }}
        >
          <Button type="text" style={{ color: "rgba(255,255,255,0.55)", fontSize: 12 }}>
            <span className="pvcb-user">{auth.username ?? "demo@pvcb.org"}</span> ▾
          </Button>
        </Dropdown>
      </div>
    </header>
  );
}
