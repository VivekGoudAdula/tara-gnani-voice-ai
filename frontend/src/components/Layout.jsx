import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Users,
  UserCheck,
  Package,
  Megaphone,
  BarChart3,
  LogOut,
  Building2,
  Menu,
  X,
  Sparkles,
  Cpu,
  LayoutDashboard,
  UploadCloud,
  HelpCircle,
  Radio,
  ShieldCheck,
  MessageSquare,
  Settings,
  History,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { formatRole } from "../utils/format";
import Badge from "./Badge";
import Button from "./Button";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const navGroups = [
    {
      title: "OVERVIEW",
      items: [{ name: "Dashboard", path: "/app/dashboard", icon: LayoutDashboard }],
    },
    {
      title: "DATA & AUDIENCE",
      items: [
        { name: "Data Import", path: "/app/data-import", icon: UploadCloud },
        { name: "Customers", path: "/app/customers", icon: UserCheck },
        { name: "Leads", path: "/app/leads", icon: Users },
      ],
    },
    {
      title: "TARGETING & CAMPAIGNS",
      items: [
        { name: "Product Catalogue", path: "/app/products", icon: Package },
        { name: "Lead Scoring", path: "/app/matches", icon: Sparkles },
        { name: "Campaigns", path: "/app/campaigns", icon: Megaphone },
      ],
    },
    {
      title: "VOICE OPERATIONS",
      items: [
        { name: "Live Calls", path: "/app/live-calls", icon: Radio },
        { name: "Conversations", path: "/app/conversations", icon: MessageSquare },
      ],
    },
    {
      title: "INSIGHTS & OUTCOMES",
      items: [
        { name: "Analytics", path: "/app/analytics", icon: BarChart3 },
        { name: "Interaction History", path: "/app/outcomes", icon: History },
      ],
    },
    {
      title: "ADMINISTRATION",
      items: [
        { name: "Settings & AI Agents", path: "/app/settings", icon: Settings },
        ...(isSuperAdmin
          ? [{ name: "Governance & Audit", path: "/app/governance", icon: ShieldCheck }]
          : []),
      ],
    },
  ];

  const sidebarContent = (
    <div className="h-full flex flex-col justify-between p-3.5 bg-transparent text-ink overflow-hidden">
      {/* Brand - Fixed */}
      <div className="h-14 px-2 flex items-center justify-between border-b border-hairline/60 shrink-0 mb-3">
        <NavLink to="/" className="flex items-center">
          <img
            src="/logo.png"
            alt="TARA"
            className="h-9 w-auto object-contain"
          />
        </NavLink>
        {mobileMenuOpen && (
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="md:hidden p-1.5 rounded-md hover:bg-white/50 text-muted"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation - Internal scrollable if vertical height is constrained */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden space-y-3 pr-1">
        <nav className="space-y-3">
          {navGroups.map((group) => (
            <div key={group.title}>
              <div className="px-3 py-0.5 text-[10px] font-semibold tracking-wider text-muted-soft uppercase">
                {group.title}
              </div>
              <div className="mt-0.5 space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-3 py-1.5 rounded-full t-nav transition-all duration-150 ${
                          isActive
                            ? "bg-white text-ink border border-hairline shadow-sm font-medium"
                            : "text-body hover:text-ink hover:bg-white/40"
                        }`
                      }
                    >
                      <Icon className="w-4 h-4 shrink-0 text-muted" />
                      <span className="text-sm truncate">{item.name}</span>
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Footer Info - Fixed */}
      <div className="pt-3 border-t border-hairline/60 t-caption text-muted flex items-center justify-between shrink-0 mt-2">
        <span className="inline-flex items-center gap-1.5">
          <img src="/gnani-logo.png" alt="Gnani AI" className="h-4 w-auto object-contain" />
          <span className="font-medium text-ink">Gnani Voice AI</span>
        </span>
        <span className="t-caption text-muted-soft">Challenge</span>
      </div>
    </div>
  );

  return (
    <div className="h-screen w-screen overflow-hidden flex bg-canvas text-ink font-sans">
      {/* Desktop Fixed Sidebar with bg-app.png */}
      <aside className="hidden md:flex w-60 h-screen sticky top-0 left-0 bg-[url('/bg-app.png')] bg-cover bg-left-top border-r border-hairline/80 flex-col shrink-0 z-30 overflow-hidden shadow-sm">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden bg-ink/30 backdrop-blur-sm flex">
          <div className="w-64 bg-[url('/bg-app.png')] bg-cover bg-left-top h-full border-r border-hairline/80 shadow-xl">
            {sidebarContent}
          </div>
          <div className="flex-1" onClick={() => setMobileMenuOpen(false)} />
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex flex-col h-screen min-w-0 overflow-hidden">
        {/* Topbar / Navbar Continuation with bg-app.png */}
        <header className="h-14 bg-[url('/bg-app.png')] bg-cover bg-top border-b border-hairline/80 px-4 md:px-6 flex items-center justify-between shrink-0 z-20 shadow-xs">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="md:hidden p-1.5 rounded-md hover:bg-white/50 text-ink"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/80 backdrop-blur-sm border border-hairline t-caption text-body-strong shadow-xs">
              <Building2 className="w-3.5 h-3.5 text-muted" />
              <span>{user?.tenant_name || "Workspace"}</span>
            </div>
          </div>

          {/* User profile & Logout */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 t-caption bg-white/60 backdrop-blur-xs px-2.5 py-1 rounded-full border border-hairline/60">
              <span className="t-body-strong text-ink">{user?.name}</span>
              <Badge variant={user?.role === "SUPER_ADMIN" ? "purple" : "default"}>
                {formatRole(user?.role)}
              </Badge>
            </div>

            <div className="h-4 w-[1px] bg-hairline/80 hidden sm:block" />

            <Button
              id="logout-btn"
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="bg-white/80 hover:bg-white backdrop-blur-sm border-hairline shadow-xs"
            >
              <LogOut className="w-3.5 h-3.5 text-muted" />
              <span>Sign out</span>
            </Button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6 min-w-0 bg-canvas">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
