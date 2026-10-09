import { useTranslation } from "react-i18next";
import { COPYRIGHT_OWNER, COPYRIGHT_YEAR } from "../config";

// Every page ends with the AI-error notice and the copyright line (design: pre-launch gate).
export function AppFooter({ onDark = false }: { onDark?: boolean }) {
  const { t } = useTranslation();
  return (
    <footer className="app-footer" style={onDark ? { color: "rgba(255,255,255,0.55)" } : undefined}>
      <div>{t("footer.aiNotice")}</div>
      <div style={{ marginTop: 4, opacity: 0.85 }}>
        © {COPYRIGHT_YEAR} {COPYRIGHT_OWNER}. {t("footer.rights")} · {t("footer.copyright")}
      </div>
    </footer>
  );
}
