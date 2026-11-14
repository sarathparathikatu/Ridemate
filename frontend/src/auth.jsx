import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";

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
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  // api.js fires this when any call gets a 401 (e.g. the token expired).
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("ridemate:logout", onLogout);
    return () => window.removeEventListener("ridemate:logout", onLogout);
  }, []);

  const login = useCallback(async (email, password) => {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
