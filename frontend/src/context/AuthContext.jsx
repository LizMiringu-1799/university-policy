import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi } from "../api/client.js";

const AuthContext = createContext(null);
const TOKEN_KEY = "upman_token";

/**
 * Session state for the whole app: token, current user, and login/register/logout.
 * The token is persisted to localStorage so a page refresh doesn't log the user out;
 * on mount, a stored token is resolved back to a user via GET /auth/me, and cleared if
 * that fails (expired/invalid).
 */
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me(token)
      .then((data) => setUser(data.user))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  // Shared by login() and register(): both endpoints return the same {user, access_token}
  // shape, so there's one place that writes it to state and localStorage.
  const persistSession = useCallback((data) => {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const login = useCallback(
    async (email, password) => {
      const data = await authApi.login({ email, password });
      persistSession(data);
      return data.user;
    },
    [persistSession]
  );

  const register = useCallback(
    async (name, email, password) => {
      const data = await authApi.register({ name, email, password });
      persistSession(data);
      return data.user;
    },
    [persistSession]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Read the current session: { user, token, loading, login, register, logout }. Throws
 * if called outside an AuthProvider, so a missing provider fails loudly during dev. */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
