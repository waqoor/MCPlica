import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  ChevronRight,
  Gauge,
  Hammer,
  LogOut,
  Menu,
  Rocket,
  Settings,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { systemApi } from "@/api/system";
import { useAuth } from "@/auth/use-auth";
import { cn } from "@/lib/utils";
import { HealthBadge } from "./status-badge";
import { Button } from "./ui/button";

const links = [
  { to: "/", label: "Dashboard", icon: Gauge, end: true },
  { to: "/projects", label: "Projects", icon: Boxes },
  { to: "/builds", label: "Builds", icon: Hammer },
  { to: "/deployments", label: "Deployments", icon: Rocket },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const readiness = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: ({ signal }) => systemApi.readiness(signal),
    refetchInterval: 60_000,
  });

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-5 py-5">
        <NavLink
          aria-label="MCPlica dashboard"
          className="group flex items-center gap-3"
          onClick={onNavigate}
          to="/"
        >
          <span className="grid size-9 place-items-center rounded-lg border border-accent/40 bg-accent/10 font-mono text-sm font-bold text-accent transition group-hover:bg-accent/15">
            M
          </span>
          <span>
            <span className="block text-base font-semibold tracking-tight text-foreground">
              MCPlica
            </span>
            <span className="block font-mono text-[0.62rem] uppercase tracking-[0.13em] text-muted">
              API → MCP control plane
            </span>
          </span>
        </NavLink>
      </div>

      <nav
        aria-label="Primary"
        className="flex-1 space-y-1 overflow-y-auto px-3 py-4"
      >
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            className={({ isActive }) =>
              cn(
                "group flex min-h-11 items-center gap-3 rounded-md border border-transparent px-3 text-sm font-medium text-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                "hover:bg-panel-hover hover:text-foreground",
                isActive && "border-border bg-panel-raised text-foreground",
              )
            }
            end={end}
            key={to}
            onClick={onNavigate}
            to={to}
          >
            <Icon
              aria-hidden="true"
              className="size-4 shrink-0 text-muted transition group-aria-[current=page]:text-accent"
            />
            <span>{label}</span>
            <ChevronRight
              aria-hidden="true"
              className="ml-auto size-3.5 opacity-0 transition group-hover:opacity-60 group-aria-[current=page]:opacity-100"
            />
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="text-xs text-muted">Control plane</span>
          {readiness.data ? (
            <HealthBadge status={readiness.data.status} />
          ) : (
            <HealthBadge status="unknown" />
          )}
        </div>
        <p className="truncate text-sm font-medium text-foreground">
          {user?.display_name}
        </p>
        <p className="truncate text-xs text-muted">{user?.email}</p>
      </div>
    </div>
  );
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();

  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <div className="min-h-screen text-foreground">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-canvas/95 backdrop-blur lg:block">
        <Sidebar />
      </aside>

      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 cursor-default bg-black/65"
            onClick={() => setMenuOpen(false)}
            type="button"
          />
          <aside className="relative h-full w-[min(19rem,88vw)] border-r border-border bg-canvas shadow-dialog">
            <Button
              aria-label="Close navigation"
              className="absolute right-3 top-3 z-10"
              onClick={() => setMenuOpen(false)}
              size="icon"
              variant="ghost"
            >
              <X aria-hidden="true" className="size-5" />
            </Button>
            <Sidebar onNavigate={() => setMenuOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-border bg-canvas/88 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <Button
              aria-label="Open navigation"
              className="lg:hidden"
              onClick={() => setMenuOpen(true)}
              size="icon"
              variant="ghost"
            >
              <Menu aria-hidden="true" className="size-5" />
            </Button>
            <div>
              <p className="text-sm font-medium text-foreground">
                {user?.display_name}
              </p>
              <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted">
                {user?.role} access
              </p>
            </div>
          </div>
          <Button onClick={() => void logout()} size="sm" variant="ghost">
            <LogOut aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </header>
        <main
          className="mx-auto w-full max-w-[100rem] p-4 sm:p-6 lg:p-8"
          id="main-content"
          tabIndex={-1}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
