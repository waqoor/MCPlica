import { lazy, Suspense } from "react";
import { createBrowserRouter, Outlet, RouterProvider } from "react-router-dom";
import { AuthProvider } from "@/auth/auth-provider";
import { AdminRoute, ProtectedRoute } from "@/auth/protected-route";
import { Layout } from "@/components/layout";
import { PageSpinner } from "@/components/ui/spinner";
import { RouteErrorPage } from "@/pages/route-error";

const lazyPage = <T extends Record<string, unknown>>(
  loader: () => Promise<T>,
  name: keyof T,
) =>
  lazy(async () => ({
    default: (await loader())[name] as React.ComponentType,
  }));

const LoginPage = lazyPage(() => import("@/pages/login"), "LoginPage");
const DashboardPage = lazyPage(
  () => import("@/pages/dashboard"),
  "DashboardPage",
);
const ProjectsPage = lazyPage(() => import("@/pages/projects"), "ProjectsPage");
const NewProjectPage = lazyPage(
  () => import("@/pages/new-project"),
  "NewProjectPage",
);
const ProjectLayout = lazyPage(
  () => import("@/pages/project-layout"),
  "ProjectLayout",
);
const ProjectOverviewPage = lazyPage(
  () => import("@/pages/project-overview"),
  "ProjectOverviewPage",
);
const ProjectSourcesPage = lazyPage(
  () => import("@/pages/project-sources"),
  "ProjectSourcesPage",
);
const ProjectOperationsPage = lazyPage(
  () => import("@/pages/project-operations"),
  "ProjectOperationsPage",
);
const ProjectDocumentationPage = lazyPage(
  () => import("@/pages/project-documentation"),
  "ProjectDocumentationPage",
);
const ProjectBuildsPage = lazyPage(
  () => import("@/pages/project-builds"),
  "ProjectBuildsPage",
);
const BuildDetailPage = lazyPage(
  () => import("@/pages/build-detail"),
  "BuildDetailPage",
);
const ValidationPage = lazyPage(
  () => import("@/pages/validation"),
  "ValidationPage",
);
const ProjectDeploymentPage = lazyPage(
  () => import("@/pages/project-deployment"),
  "ProjectDeploymentPage",
);
const ProjectCredentialsPage = lazyPage(
  () => import("@/pages/project-credentials"),
  "ProjectCredentialsPage",
);
const ProjectSettingsPage = lazyPage(
  () => import("@/pages/project-settings"),
  "ProjectSettingsPage",
);
const BuildsPage = lazyPage(() => import("@/pages/builds"), "BuildsPage");
const DeploymentsPage = lazyPage(
  () => import("@/pages/deployments"),
  "DeploymentsPage",
);
const ActivityPage = lazyPage(() => import("@/pages/activity"), "ActivityPage");
const SettingsPage = lazyPage(() => import("@/pages/settings"), "SettingsPage");
const ModelSettingsPage = lazyPage(
  () => import("@/pages/model-settings"),
  "ModelSettingsPage",
);
const UsersPage = lazyPage(() => import("@/pages/users"), "UsersPage");
const NotFoundPage = lazyPage(
  () => import("@/pages/not-found"),
  "NotFoundPage",
);

function AppProviders() {
  return (
    <AuthProvider>
      <Suspense fallback={<PageSpinner />}>
        <Outlet />
      </Suspense>
    </AuthProvider>
  );
}

const router = createBrowserRouter([
  {
    element: <AppProviders />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/login", element: <LoginPage /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: "/projects/new", element: <NewProjectPage /> },
          {
            element: <Layout />,
            children: [
              { index: true, element: <DashboardPage /> },
              { path: "projects", element: <ProjectsPage /> },
              {
                path: "projects/:projectId",
                element: <ProjectLayout />,
                children: [
                  { index: true, element: <ProjectOverviewPage /> },
                  { path: "sources", element: <ProjectSourcesPage /> },
                  { path: "tools", element: <ProjectOperationsPage /> },
                  {
                    path: "documentation",
                    element: <ProjectDocumentationPage />,
                  },
                  { path: "builds", element: <ProjectBuildsPage /> },
                  { path: "builds/:buildId", element: <BuildDetailPage /> },
                  { path: "validation/:buildId", element: <ValidationPage /> },
                  { path: "deployment", element: <ProjectDeploymentPage /> },
                  { path: "credentials", element: <ProjectCredentialsPage /> },
                  { path: "settings", element: <ProjectSettingsPage /> },
                ],
              },
              { path: "builds", element: <BuildsPage /> },
              { path: "deployments", element: <DeploymentsPage /> },
              { path: "settings", element: <SettingsPage /> },
              {
                element: <AdminRoute />,
                children: [
                  { path: "activity", element: <ActivityPage /> },
                  { path: "settings/models", element: <ModelSettingsPage /> },
                  { path: "settings/users", element: <UsersPage /> },
                ],
              },
              { path: "*", element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
