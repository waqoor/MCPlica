import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { projectApi } from "@/api/projects";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FieldError, FieldHelp, Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useProject } from "@/features/projects/project-context";

const schema = z.object({
  name: z.string().trim().min(1).max(160),
  description: z.string().max(10_000),
  default_base_url: z.union([z.literal(""), z.string().url()]),
});
type Values = z.infer<typeof schema>;

export function ProjectSettingsPage() {
  const project = useProject();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: project.name,
      description: project.description ?? "",
      default_base_url: project.default_base_url ?? "",
    },
  });
  const update = useMutation({
    mutationFn: (values: Values) =>
      projectApi.update(project.id, {
        ...values,
        description: values.description || null,
        default_base_url: values.default_base_url || null,
      }),
    onSuccess: (value) => {
      queryClient.setQueryData(["projects", project.id], value);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const toggle = useMutation({
    mutationFn: () =>
      projectApi.update(project.id, { is_enabled: !project.is_enabled }),
    onSuccess: (value) =>
      queryClient.setQueryData(["projects", project.id], value),
  });
  const remove = useMutation({
    mutationFn: () => projectApi.remove(project.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate("/projects", { replace: true });
    },
  });
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">
          Project settings
        </h2>
        <p className="mt-1 text-sm text-muted">
          The slug and deployed hostname remain immutable after first successful
          deployment.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Project identity and server</CardTitle>
        </CardHeader>
        <form
          className="space-y-5"
          noValidate
          onSubmit={form.handleSubmit((values) => update.mutate(values))}
        >
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="settings-project-name">Name</Label>
              <Input id="settings-project-name" {...form.register("name")} />
              {form.formState.errors.name && (
                <FieldError>{form.formState.errors.name.message}</FieldError>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="settings-project-slug">Slug</Label>
              <Input disabled id="settings-project-slug" value={project.slug} />
              <FieldHelp>Immutable after deployment.</FieldHelp>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="settings-base-url">
                Selected upstream base URL
              </Label>
              <Input
                id="settings-base-url"
                type="url"
                {...form.register("default_base_url")}
              />
              {form.formState.errors.default_base_url && (
                <FieldError>
                  {form.formState.errors.default_base_url.message}
                </FieldError>
              )}
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="settings-description">Description</Label>
              <Textarea
                id="settings-description"
                {...form.register("description")}
              />
            </div>
          </div>
          {update.error && <Alert tone="danger">{update.error.message}</Alert>}
          {update.isSuccess && (
            <Alert tone="success">Project settings saved.</Alert>
          )}
          <Button disabled={update.isPending} type="submit">
            <Save aria-hidden="true" className="size-4" />
            Save changes
          </Button>
        </form>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Lifecycle controls</CardTitle>
            <p className="mt-1 text-xs text-muted">
              Backend state checks remain authoritative for every destructive
              action.
            </p>
          </div>
        </CardHeader>
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-medium text-foreground">
              {project.is_enabled ? "Project enabled" : "Project disabled"}
            </p>
            <p className="mt-1 text-xs text-muted">
              Disabling prevents new lifecycle work but does not silently orphan
              runtime resources.
            </p>
          </div>
          <Button
            disabled={toggle.isPending}
            onClick={() => toggle.mutate()}
            variant="outline"
          >
            {project.is_enabled ? "Disable project" : "Enable project"}
          </Button>
        </div>
        <div className="mt-5 flex flex-col justify-between gap-4 border-t border-danger/25 pt-5 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-medium text-danger-soft">
              Delete project
            </p>
            <p className="mt-1 text-xs text-muted">
              Deletion is blocked while an active deployment exists.
            </p>
          </div>
          <Button onClick={() => setDeleteOpen(true)} variant="destructive">
            <Trash2 aria-hidden="true" className="size-4" />
            Delete project
          </Button>
        </div>
        {(toggle.error || remove.error) && (
          <Alert className="mt-4" tone="danger">
            {toggle.error?.message ?? remove.error?.message}
          </Alert>
        )}
      </Card>
      <Dialog
        description="This action is allowed only after active runtime resources have been stopped and removed through the controlled flow."
        onClose={() => setDeleteOpen(false)}
        open={deleteOpen}
        title={`Delete ${project.name}`}
      >
        <div className="space-y-4">
          <Alert tone="danger">
            Project deletion removes control-plane records according to the
            configured retention policy. It cannot silently orphan an active
            runtime.
          </Alert>
          <div className="space-y-2">
            <Label htmlFor="delete-confirmation">
              Type{" "}
              <code className="font-mono text-danger-soft">{project.slug}</code>{" "}
              to confirm
            </Label>
            <Input
              autoFocus
              id="delete-confirmation"
              onChange={(event) => setConfirmation(event.target.value)}
              value={confirmation}
            />
          </div>
          <Button
            className="w-full"
            disabled={confirmation !== project.slug || remove.isPending}
            onClick={() => remove.mutate()}
            variant="destructive"
          >
            Permanently delete project
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
