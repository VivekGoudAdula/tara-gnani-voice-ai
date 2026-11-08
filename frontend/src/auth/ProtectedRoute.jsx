import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { user, token, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-hairline-strong border-t-ink rounded-full animate-spin" />
          <p className="t-caption text-muted">Loading workspace...</p>
        </div>
      </div>
    );
  }

  if (!user || !token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export function PublicAuthRoute({ children }) {
  const { user, token, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-hairline-strong border-t-ink rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (user && token) {
    return <Navigate to="/app/dashboard" replace />;
  }

  return children || <Outlet />;
}
