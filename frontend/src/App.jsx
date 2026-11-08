import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute, { PublicAuthRoute } from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import DataImport from "./pages/DataImport";
import Leads from "./pages/Leads";
import Customers from "./pages/Customers";
import Products from "./pages/Products";
import ProductMatches from "./pages/ProductMatches";
import ExplainableAI from "./pages/ExplainableAI";
import Models from "./pages/Models";
import Campaigns from "./pages/Campaigns";
import CampaignWizard from "./pages/CampaignWizard";
import CampaignDetail from "./pages/CampaignDetail";
import LiveCalls from "./pages/LiveCalls";
import Conversations from "./pages/Conversations";
import Analytics from "./pages/Analytics";
import Outcomes from "./pages/Outcomes";
import Settings from "./pages/Settings";
import Governance from "./pages/Governance";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Landing Page */}
          <Route path="/" element={<Landing />} />

          {/* Public Auth Routes (Redirects to /app if already logged in) */}
          <Route element={<PublicAuthRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
          </Route>

          {/* Protected App Routes */}
          <Route path="/app" element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="data-import" element={<DataImport />} />
              <Route path="leads" element={<Leads />} />
              <Route path="customers" element={<Customers />} />
              <Route path="matches" element={<ProductMatches />} />
              <Route path="explainable-ai" element={<ExplainableAI />} />
              <Route path="products" element={<Products />} />
              <Route path="models" element={<Models />} />
              <Route path="campaigns" element={<Campaigns />} />
              <Route path="campaigns/new" element={<CampaignWizard />} />
              <Route path="campaigns/:id/edit" element={<CampaignWizard />} />
              <Route path="campaigns/:id" element={<CampaignDetail />} />
              <Route path="live-calls" element={<LiveCalls />} />
              <Route path="live-monitor" element={<Navigate to="/app/live-calls" replace />} />
              <Route path="conversations" element={<Conversations />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="outcomes" element={<Outcomes />} />
              <Route path="settings" element={<Settings />} />
              <Route path="governance" element={<Governance />} />
            </Route>
          </Route>

          {/* Catch-all 404 Page */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
