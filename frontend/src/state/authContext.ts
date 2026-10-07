import { createContext, useContext } from "react";

export interface AuthState {
  authed: boolean;
  username: string | null;
}

export interface AuthContextValue {
  auth: AuthState;
  login: (email: string, password: string) => boolean;
  loginDemo: () => void;
  logout: () => void;
}

const DEMO_EMAIL = "demo@pvcb.org";
const DEMO_PASSWORD = "demo1234";
const STORAGE_KEY = "pvcb_authed";

const USERNAME_KEY = "pvcb_username";

function loadAuth(): AuthState {
  try {
    const authed = localStorage.getItem(STORAGE_KEY) === "1";
    const username = localStorage.getItem(USERNAME_KEY) ?? null;
    return { authed, username };
  } catch {
    return { authed: false, username: null };
  }
}

function saveAuth(authed: boolean, username: string | null = null): void {
  try {
    if (authed) {
      localStorage.setItem(STORAGE_KEY, "1");
      if (username) localStorage.setItem(USERNAME_KEY, username);
    } else {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(USERNAME_KEY);
    }
  } catch {}
}

export const AuthContext = createContext<AuthContextValue>({
  auth: { authed: false, username: null },
  login: () => false,
  loginDemo: () => {},
  logout: () => {},
});

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

export function makeAuthActions(
  setAuth: (a: AuthState) => void,
): Pick<AuthContextValue, "login" | "loginDemo" | "logout"> {
  return {
    login(email, password) {
      const ok = email.trim().toLowerCase() === DEMO_EMAIL && password === DEMO_PASSWORD;
      if (ok) {
        const username = email.trim().toLowerCase();
        saveAuth(true, username);
        setAuth({ authed: true, username });
      }
      return ok;
    },
    loginDemo() {
      saveAuth(true, "demo@pvcb.org");
      setAuth({ authed: true, username: "demo@pvcb.org" });
    },
    logout() {
      saveAuth(false);
      setAuth({ authed: false, username: null });
    },
  };
}

export { loadAuth };
