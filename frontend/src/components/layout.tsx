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
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { systemApi } from "@/api/system";
import { useCapabilities } from "@/auth/capabilities";
import { useAuth } from "@/auth/use-auth";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/use-media-query";
import { BrandLogo } from "./brand-logo";
import { ErrorNotice } from "./error-notice";
import { HealthBadge } from "./status-badge";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";

const links = [
  { to: "/", label: "Dashboard", icon: Gauge, end: true },
  { to: "/projects", label: "Projects", icon: Boxes },
  { to: "/builds", label: "Builds", icon: Hammer },
  { to: "/deployments", label: "Deployments", icon: Rocket },
  { to: "/activity", label: "Activity", icon: Activity, adminOnly: true },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const capabilities = useCapabilities();
  const readiness = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: ({ signal }) => systemApi.readiness(signal),
    refetchInterval: 60_000,
  });

  return (
    <div className="flex h-full flex-col">
      <div aria-hidden="true" className="brand-flow h-0.5 shrink-0" />
      <div className="border-b border-border px-5 pb-4 pt-5">
        <NavLink
          aria-label="MCPlica dashboard"
          className="group block w-fit rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
          onClick={onNavigate}
          to="/"
        >
          <BrandLogo
            alt=""
            className="h-10 w-[10.5rem] transition duration-200 group-hover:border-accent/45 group-hover:shadow-action"
            loading="eager"
          />
          <span className="mt-2 block font-mono text-[0.6rem] uppercase tracking-[0.13em] text-muted">
            API → MCP control plane
          </span>
        </NavLink>
      </div>

      <nav
        aria-label="Primary"
        className="flex-1 space-y-1 overflow-y-auto px-3 py-4"
      >
        {links
          .filter((link) => !link.adminOnly || capabilities.canViewAudit)
          .map(({ to, label, icon: Icon, end }) => (
            <NavLink
              className={({ isActive }) =>
                cn(
                  "group flex min-h-11 items-center gap-3 rounded-md border border-transparent px-3 text-sm font-medium text-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                  "hover:bg-panel-hover hover:text-foreground",
                  isActive &&
                    "nav-active border-border bg-panel-raised text-foreground",
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
        <p className="mt-2 font-mono text-[0.62rem] text-muted">
          MCPlica v{__MCPLICA_VERSION__}
        </p>
      </div>
    </div>
  );
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout, logoutError, isLoggingOut } = useAuth();
  const desktop = useMediaQuery("(min-width: 1024px)");

  return (
    <div className="min-h-screen text-foreground">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      {desktop && (
        <aside className="fixed inset-y-0 left-0 z-30 w-64 border-r border-border bg-canvas/92 backdrop-blur-xl">
          <Sidebar />
        </aside>
      )}

      <Dialog
        description="Primary application navigation"
        onClose={() => setMenuOpen(false)}
        open={menuOpen}
        title="Navigation"
        variant="sheet"
      >
        <Sidebar onNavigate={() => setMenuOpen(false)} />
      </Dialog>

      <div className={desktop ? "pl-64" : undefined}>
        <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-border bg-canvas/82 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            {!desktop && (
              <>
                <Button
                  aria-label="Open navigation"
                  onClick={() => setMenuOpen(true)}
                  size="icon"
                  variant="ghost"
                >
                  <Menu aria-hidden="true" className="size-5" />
                </Button>
                <NavLink
                  aria-label="MCPlica dashboard"
                  className="-m-1.5 rounded-lg p-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  to="/"
                >
                  <BrandLogo
                    alt=""
                    className="h-8 w-[3.25rem]"
                    loading="eager"
                    variant="compact"
                  />
                </NavLink>
              </>
            )}
            <div className="hidden sm:block">
              <p className="text-sm font-medium text-foreground">
                {user?.display_name}
              </p>
              <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted">
                {user?.role} access
              </p>
            </div>
          </div>
          <Button
            aria-label="Sign out"
            disabled={isLoggingOut}
            onClick={() => void logout().catch(() => undefined)}
            size="sm"
            variant="ghost"
          >
            <LogOut aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </header>
        {logoutError && (
          <div className="px-4 pt-4 sm:px-6 lg:px-8">
            <ErrorNotice
              error={logoutError}
              nextStep="Your server session remains active. Retry sign out before leaving this device."
              onRetry={() => void logout().catch(() => undefined)}
              title="Sign out was not confirmed"
            />
          </div>
        )}
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
