// AOI Tool - Auth context
// Holds the current user + permissions, restores the session from a stored
// token on load, and exposes login / logout / can().
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import * as api from "../api.js";

const AuthCtx = createContext(null);

export function useAuth() {
  return useContext(AuthCtx);
}

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    api.setToken(null);
    setUser(null);
  }, []);

  // Any 401 from the API (expired token) drops us back to the login screen.
  useEffect(() => {
    api.setOnAuthError(() => setUser(null));
    return () => api.setOnAuthError(null);
  }, []);

  // Restore a session if a token is already stored.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = api.getToken();
      if (!token) { setLoading(false); return; }
      try {
        const u = await api.me();
        if (!cancelled) setUser(u);
      } catch {
        api.setToken(null);
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (username, password) => {
    const { token, user: u } = await api.login(username, password);
    api.setToken(token);
    setUser(u);
    return u;
  }, []);

  // Re-fetch the current user (e.g. after a forced password change).
  const refresh = useCallback(async () => {
    const u = await api.me();
    setUser(u);
    return u;
  }, []);

  const can = useCallback(
    (perm) => !!user && Array.isArray(user.permissions) && user.permissions.includes(perm),
    [user],
  );

  const value = { user, loading, login, logout, refresh, can };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
