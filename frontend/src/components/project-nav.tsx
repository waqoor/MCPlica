import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const tabs = [
  { label: "Overview", path: "" },
  { label: "Sources", path: "sources" },
  { label: "Operations", path: "tools" },
  { label: "Documentation", path: "documentation" },
  { label: "Builds", path: "builds" },
  { label: "Deployment", path: "deployment" },
  { label: "Credentials", path: "credentials" },
  { label: "Settings", path: "settings" },
];

export function ProjectNav() {
  return (
    <nav
      aria-label="Project sections"
      className="scrollbar-thin -mx-1 overflow-x-auto px-1"
    >
      <div className="flex min-w-max gap-1 border-b border-border">
        {tabs.map((tab) => (
          <NavLink
            className={({ isActive }) =>
              cn(
                "relative min-h-11 px-3 py-3 text-sm font-medium text-muted transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                isActive &&
                  "text-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-accent",
              )
            }
            end={tab.path === ""}
            key={tab.path}
            to={tab.path}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
