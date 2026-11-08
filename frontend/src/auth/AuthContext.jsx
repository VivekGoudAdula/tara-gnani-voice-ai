import React, { createContext, useContext, useState, useEffect } from "react";
import { api } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = sessionStorage.getItem("tara_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => sessionStorage.getItem("tara_token"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Verify token validity on initial mount
    async function verifyAuth() {
      if (token) {
        try {
          const profile = await api.get("/auth/me");
          setUser(profile);
          sessionStorage.setItem("tara_user", JSON.stringify(profile));
        } catch {
          logout();
        }
      }
      setLoading(false);
    }
    verifyAuth();
  }, [token]);

  const login = async (email, password) => {
    const data = await api.post("/auth/login", { email, password });
    sessionStorage.setItem("tara_token", data.access_token);
    sessionStorage.setItem("tara_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const signup = async (workspaceName, name, email, password) => {
    const data = await api.post("/auth/signup", {
      workspace_name: workspaceName,
      name,
      email,
      password,
    });
    sessionStorage.setItem("tara_token", data.access_token);
    sessionStorage.setItem("tara_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    sessionStorage.removeItem("tara_token");
    sessionStorage.removeItem("tara_user");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, signup, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );

}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
