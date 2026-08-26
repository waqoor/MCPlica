import { createBrowserRouter, RouterProvider } from "react-router-dom"
import { Layout } from "@/components/layout"
import { DashboardPage } from "@/pages/dashboard"
import { ProjectsPage } from "@/pages/projects"
import { SettingsPage } from "@/pages/settings"

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/projects", element: <ProjectsPage /> },
      { path: "/settings", element: <SettingsPage /> },
    ],
  },
])

export function App() { return <RouterProvider router={router} /> }
