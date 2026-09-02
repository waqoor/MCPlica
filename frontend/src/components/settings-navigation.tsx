import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const sections = [
  { label: "Overview", to: "/settings", end: true, adminOnly: false },
  {
    label: "Providers",
    to: "/settings/providers",
    end: false,
    adminOnly: true,
  },
  { label: "Models", to: "/settings/models", end: false, adminOnly: true },
  { label: "Users", to: "/settings/users", end: false, adminOnly: true },
];

export function SettingsNavigation({
  canManageInstallation,
}: {
  canManageInstallation: boolean;
}) {
  return (
    <nav
      aria-label="Settings sections"
      className="scrollbar-thin overflow-x-auto border-b border-border"
    >
      <div className="flex min-w-max gap-1">
        {sections
          .filter((section) => !section.adminOnly || canManageInstallation)
          .map((section) => (
            <NavLink
              className={({ isActive }) =>
                cn(
                  "relative inline-flex min-h-11 items-center rounded-t-md px-4 text-sm font-medium text-muted transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent",
                  "hover:bg-panel-raised hover:text-foreground",
                  isActive &&
                    "bg-panel-raised text-foreground after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-accent",
                )
              }
              end={section.end}
              key={section.to}
              to={section.to}
            >
              {section.label}
            </NavLink>
          ))}
      </div>
    </nav>
  );
}
