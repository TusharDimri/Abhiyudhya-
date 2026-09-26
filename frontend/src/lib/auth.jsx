import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import api, { tokens, setUnauthorizedHandler } from "./api";

// Everything the previous user loaded - their permissions, lists, their
// location fix - must be gone before the next one sees a single screen.
function forgetSession(queryClient) {
  queryClient.clear();
  try { sessionStorage.removeItem("rnaf.location"); } catch { /* nothing kept */ }
}

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [roleLabel, setRoleLabel] = useState("");
  const [organisation, setOrganisation] = useState(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    tokens.clear();
    forgetSession(queryClient);
    setUser(null);
    setOrganisation(null);
  }, [queryClient]);

  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);

  const loadMe = useCallback(async () => {
    if (!tokens.access) { setLoading(false); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user);
      setRoleLabel(data.role_label);
      setOrganisation(data.organisation || null);
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => { loadMe(); }, [loadMe]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    forgetSession(queryClient);
    tokens.set({ access: data.access_token, refresh: data.refresh_token });
    setUser(data.user);
    await loadMe();
    return data.user;
  };

  return (
    <AuthCtx.Provider value={{ user, roleLabel, organisation, loading, login, logout, refreshMe: loadMe }}>
      {children}
    </AuthCtx.Provider>
  );
}
