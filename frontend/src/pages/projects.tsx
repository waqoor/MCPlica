import { FormEvent, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { projectApi } from "@/api/projects"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export function ProjectsPage() {
  const queryClient = useQueryClient()
  const projects = useQuery({ queryKey: ["projects"], queryFn: projectApi.list })
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const create = useMutation({
    mutationFn: projectApi.create,
    onSuccess: async () => {
      setName("")
      setSlug("")
      await queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ name, slug })
  }

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-semibold">Projects</h1>
      <p className="mt-2 text-sm text-zinc-400">One project represents one product/API converted into an isolated MCP runtime.</p>

      <Card className="mt-6">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input aria-label="Project name" placeholder="Inventory API" value={name} onChange={(e) => setName(e.target.value)} required />
          <Input aria-label="Project slug" placeholder="inventory" value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())} required />
          <Button disabled={create.isPending}>{create.isPending ? "Creating…" : "Create project"}</Button>
        </form>
        {create.error && <p className="mt-3 text-sm text-red-400">{create.error.message}</p>}
      </Card>

      <div className="mt-6 space-y-3">
        {projects.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
        {projects.error && <p className="text-sm text-red-400">Unable to load projects: {projects.error.message}</p>}
        {projects.data?.map((project) => (
          <Card key={project.id} className="flex items-center justify-between">
            <div><div className="font-medium">{project.name}</div><div className="text-sm text-zinc-500">{project.slug}.mcp.example.com</div></div>
            <span className="rounded-full border border-zinc-700 px-2 py-1 text-xs text-zinc-400">{project.enabled ? "Enabled" : "Disabled"}</span>
          </Card>
        ))}
        {projects.data?.length === 0 && <Card><p className="text-sm text-zinc-500">No projects yet.</p></Card>}
      </div>
    </div>
  )
}
