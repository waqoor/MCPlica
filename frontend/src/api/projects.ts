import { api } from "./client"

export type Project = {
  id: string
  name: string
  slug: string
  description: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export type CreateProject = Pick<Project, "name" | "slug"> & { description?: string }

export const projectApi = {
  list: () => api<Project[]>("/api/v1/projects"),
  create: (payload: CreateProject) =>
    api<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify(payload) }),
}
