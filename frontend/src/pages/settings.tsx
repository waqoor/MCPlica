import { Card } from "@/components/ui/card"

export function SettingsPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <Card className="mt-6">
        <h2 className="font-medium">Build intelligence</h2>
        <p className="mt-2 text-sm text-zinc-400">OpenRouter and Milvus belong only to the builder/review pipeline. They are never runtime dependencies of generated MCP servers.</p>
      </Card>
    </div>
  )
}
