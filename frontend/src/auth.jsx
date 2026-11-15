import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setTokens } from "./api.js";

// Context = app-wide state any component can read without passing props down every level.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  // On page load, a saved token is only a claim: ask the API who it belongs to.
  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => setTokens(null))
      .finally(() => setLoading(false));
  }, []);

  // api.js fires this when a 401 can't be fixed by refreshing (the login really ended).
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("ridemate:logout", onLogout);
    return () => window.removeEventListener("ridemate:logout", onLogout);
  }, []);

  const login = useCallback(async (email, password) => {
    setTokens(await api.login(email, password));
    setUser(await api.me());
  }, []);

  // After the profile changes on the server (e.g. phone verified), reload it.
  const refreshUser = useCallback(async () => setUser(await api.me()), []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => {}); // revoke the refresh token server-side (best effort)
    setTokens(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>{children}</AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
