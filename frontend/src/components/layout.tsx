import { Boxes, Gauge, Settings } from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"
import { cn } from "@/lib/utils"

const links = [
  { to: "/", label: "Dashboard", icon: Gauge },
  { to: "/projects", label: "Projects", icon: Boxes },
  { to: "/settings", label: "Settings", icon: Settings },
]

export function Layout() {
  return (
    <div className="min-h-screen bg-[#0b0d10] text-zinc-100">
      <aside className="fixed inset-y-0 left-0 w-64 border-r border-zinc-800 bg-zinc-950 p-5">
        <div className="mb-8">
          <div className="text-xl font-semibold tracking-tight">MCPlica</div>
          <div className="mt-1 text-xs text-zinc-500">API → MCP builder</div>
        </div>
        <nav className="space-y-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-white",
                isActive && "bg-zinc-900 text-white",
              )}
            >
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="ml-64 min-h-screen p-8"><Outlet /></main>
    </div>
  )
}
