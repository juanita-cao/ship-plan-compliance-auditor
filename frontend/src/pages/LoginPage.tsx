import { Alert, Button, Form, Input, message } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { PvcbLogo } from "../components/PvcbLogo";
import { useAuth } from "../state/authContext";

export function LoginPage() {
  const { t } = useTranslation();
  const { login, loginDemo } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState(false);
  const [msgApi, contextHolder] = message.useMessage();

  const onSignUp = () => {
    void msgApi.info("Sign-up is not available in this demo. Contact your PVCB administrator for access.");
  };

  const onFinish = ({ email, password }: { email: string; password: string }) => {
    const ok = login(email, password);
    if (ok) nav("/app", { replace: true });
    else setError(true);
  };

  const onDemo = () => {
    loginDemo();
    nav("/app", { replace: true });
  };

  return (
    <div className="auth-card">
      {contextHolder}
      {/* Logo + name row */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
        <PvcbLogo size={56} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: "#ffffff", letterSpacing: "0.01em" }}>
            {t("app.name")}
          </div>
          <div style={{ fontSize: 11, color: "#c9a84c", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 2 }}>
            {t("app.product")}
          </div>
        </div>
      </div>

      {/* Primary CTA — no login required */}
      <Button
        type="primary"
        block
        size="large"
        onClick={onDemo}
        style={{ fontWeight: 700, height: 46, fontSize: 15, marginBottom: 8 }}
      >
        ▶  {t("auth.enterDemo")}
      </Button>

      <p style={{ margin: "0 0 20px", fontSize: 12, color: "rgba(255,255,255,0.3)", textAlign: "center" }}>
        {t("auth.preloaded")}
      </p>

      {/* Divider */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.12)" }} />
        <span style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", whiteSpace: "nowrap" }}>
          or sign in with credentials
        </span>
        <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.12)" }} />
      </div>

      {error && (
        <Alert
          type="error"
          message={t("auth.invalidCredentials")}
          style={{ marginBottom: 16, background: "rgba(255,77,79,0.15)", border: "1px solid rgba(255,77,79,0.3)", color: "#fff" }}
          closable
          onClose={() => setError(false)}
        />
      )}

      {/* Hidden honeypot inputs — forces browser to stop autofilling the real fields */}
      <input type="email" name="email" style={{ display: "none" }} aria-hidden="true" readOnly />
      <input type="password" name="password" style={{ display: "none" }} aria-hidden="true" readOnly />

      <Form layout="vertical" onFinish={onFinish} requiredMark={false} autoComplete="off">
        <Form.Item name="email" label={<span style={{ color: "rgba(255,255,255,0.7)", fontSize: 13 }}>{t("auth.email")}</span>}
          rules={[{ required: true, type: "email", message: " " }]}>
          <Input placeholder={t("auth.emailPlaceholder")} size="large" autoComplete="new-password" name="pvcb-email" />
        </Form.Item>
        <Form.Item name="password" label={<span style={{ color: "rgba(255,255,255,0.7)", fontSize: 13 }}>{t("auth.password")}</span>}
          rules={[{ required: true, message: " " }]} style={{ marginBottom: 12 }}>
          <Input.Password placeholder={t("auth.passwordPlaceholder")} size="large" autoComplete="new-password" name="pvcb-password" />
        </Form.Item>
        <Button type="default" htmlType="submit" block size="large"
          style={{ fontWeight: 600, background: "rgba(255,255,255,0.06)", borderColor: "rgba(255,255,255,0.18)", color: "#e2e8f0" }}>
          {t("auth.signIn")}
        </Button>
      </Form>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginTop: 16, gap: 6 }}>
        <span style={{ fontSize: 13, color: "rgba(255,255,255,0.3)" }}>Don't have an account?</span>
        <Button type="link" onClick={onSignUp}
          style={{ padding: 0, height: "auto", fontSize: 13, color: "rgba(147,180,255,0.8)" }}>
          Sign Up
        </Button>
      </div>
    </div>
  );
}
