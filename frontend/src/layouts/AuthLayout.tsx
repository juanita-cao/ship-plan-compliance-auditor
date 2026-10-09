import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { PvcbLogo } from "../components/PvcbLogo";
import { useAuth } from "../state/authContext";
import { AppFooter } from "../components/AppFooter";

export function AuthLayout() {
  const { auth } = useAuth();
  const { t } = useTranslation();

  if (auth.authed) return <Navigate to="/app" replace />;

  return (
    <div className="auth-shell">
      <div className="auth-bg" aria-hidden="true">
        <video autoPlay muted loop playsInline poster="/login-bg-poster.jpg">
          <source src="/login-bg.mp4" type="video/mp4" />
        </video>
        <div className="auth-bg-overlay" />
      </div>

      <header className="auth-topbar">
        <div className="auth-brand">
          <PvcbLogo size={28} />
          <span>{t("app.name")}</span>
        </div>
        <LanguageSwitch onDark />
      </header>

      <main className="auth-center">
        <Outlet />
      </main>

      <AppFooter onDark />
    </div>
  );
}
