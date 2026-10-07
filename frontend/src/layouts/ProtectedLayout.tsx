import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../state/authContext";

export function ProtectedLayout() {
  const { auth } = useAuth();
  if (!auth.authed) return <Navigate to="/login" replace />;

  // Pages render their own sidebar + content-area header so the sidebar reaches the top
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#f0f2f5" }}>
      <Outlet />
    </div>
  );
}
