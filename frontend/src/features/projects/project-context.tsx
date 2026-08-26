import { createContext, useContext } from "react";
import type { Project } from "@/api/contracts";

export const ProjectContext = createContext<Project | null>(null);

export function useProject(): Project {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("useProject must be used inside ProjectLayout");
  return value;
}
