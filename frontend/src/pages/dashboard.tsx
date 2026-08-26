import { Card } from "@/components/ui/card"

export function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-sm text-zinc-400">Build and operate isolated MCP equivalents for your product APIs.</p>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Card><div className="text-sm text-zinc-500">Builder plane</div><div className="mt-2 font-medium">FastAPI + PostgreSQL + Redis + Milvus</div></Card>
        <Card><div className="text-sm text-zinc-500">AI build intelligence</div><div className="mt-2 font-medium">OpenRouter, build/review only</div></Card>
        <Card><div className="text-sm text-zinc-500">Serving plane</div><div className="mt-2 font-medium">Isolated manifest-driven MCP runtimes</div></Card>
      </div>
    </div>
  )
}
