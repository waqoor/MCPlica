import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import type { User, UserRole } from "@/api/contracts";
import { userApi } from "@/api/settings";
import { QueryError, QueryPending } from "@/components/query-state";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { formatDate } from "@/lib/format";

export function UsersPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const users = useQuery({
    queryKey: ["users"],
    queryFn: ({ signal }) => userApi.list(signal),
  });
  const update = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: Partial<Pick<User, "role" | "is_active">>;
    }) => userApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
  if (users.isPending)
    return <QueryPending label="Loading installation users" />;
  if (users.error)
    return (
      <QueryError error={users.error} onRetry={() => void users.refetch()} />
    );
  return (
    <div className="space-y-7">
      <PageHeader
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" className="size-4" />
            Create user
          </Button>
        }
        description="Installation-level identities only. There is no public registration, organization membership, or SaaS tenancy model."
        eyebrow="Settings"
        title="Users and roles"
      />
      {users.data.length === 0 ? (
        <EmptyState
          action={
            <Button onClick={() => setCreateOpen(true)}>
              Create administrator
            </Button>
          }
          description="Use the secure bootstrap process for the first administrator, then manage users here."
          icon={UsersIcon}
          title="No users returned"
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {users.data.map((user) => (
            <Card key={user.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-foreground">
                    {user.display_name}
                  </p>
                  <p className="mt-1 text-sm text-muted">{user.email}</p>
                </div>
                <Badge tone={user.is_active ? "success" : "danger"}>
                  {user.is_active ? "Active" : "Disabled"}
                </Badge>
              </div>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor={`role-${user.id}`}>Role</Label>
                  <Select
                    id={`role-${user.id}`}
                    onChange={(event) =>
                      update.mutate({
                        id: user.id,
                        payload: { role: event.target.value as UserRole },
                      })
                    }
                    value={user.role}
                  >
                    <option value="admin">Admin</option>
                    <option value="builder">Builder</option>
                  </Select>
                </div>
                <div>
                  <p className="text-xs text-muted">Last sign in</p>
                  <p className="mt-2 text-sm text-foreground">
                    {formatDate(user.last_login_at)}
                  </p>
                </div>
              </div>
              <Button
                className="mt-4"
                disabled={update.isPending}
                onClick={() =>
                  update.mutate({
                    id: user.id,
                    payload: { is_active: !user.is_active },
                  })
                }
                size="sm"
                variant={user.is_active ? "destructive" : "outline"}
              >
                {user.is_active ? "Disable access" : "Enable access"}
              </Button>
            </Card>
          ))}
        </div>
      )}
      {update.error && <Alert tone="danger">{update.error.message}</Alert>}
      <Dialog
        description="The user signs in locally. Passwords are never emailed or exposed through audit metadata."
        onClose={() => setCreateOpen(false)}
        open={createOpen}
        title="Create installation user"
      >
        <CreateUserForm
          onCreated={() => {
            setCreateOpen(false);
            void queryClient.invalidateQueries({ queryKey: ["users"] });
          }}
        />
      </Dialog>
    </div>
  );
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<UserRole>("builder");
  const [password, setPassword] = useState("");
  const create = useMutation({
    mutationFn: () =>
      userApi.create({ email, display_name: displayName, role, password }),
    onSuccess: onCreated,
  });
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="new-user-name">Display name</Label>
        <Input
          autoFocus
          id="new-user-name"
          onChange={(event) => setDisplayName(event.target.value)}
          value={displayName}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="new-user-email">Email</Label>
        <Input
          id="new-user-email"
          onChange={(event) => setEmail(event.target.value)}
          type="email"
          value={email}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="new-user-role">Role</Label>
        <Select
          id="new-user-role"
          onChange={(event) => setRole(event.target.value as UserRole)}
          value={role}
        >
          <option value="builder">Builder</option>
          <option value="admin">Admin</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="new-user-password">Temporary password</Label>
        <Input
          autoComplete="new-password"
          id="new-user-password"
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          value={password}
        />
      </div>
      {create.error && <Alert tone="danger">{create.error.message}</Alert>}
      <Button
        className="w-full"
        disabled={
          !email || !displayName || password.length < 12 || create.isPending
        }
        onClick={() => create.mutate()}
      >
        {create.isPending ? "Creating…" : "Create user"}
      </Button>
    </div>
  );
}
