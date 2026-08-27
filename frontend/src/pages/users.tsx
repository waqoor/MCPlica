import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import type { User, UserRole } from "@/api/contracts";
import { userApi } from "@/api/settings";
import { useAuth } from "@/auth/use-auth";
import { MutationError } from "@/components/error-notice";
import { QueryError, QueryPending } from "@/components/query-state";
import { PageHeader } from "@/components/page-header";
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
            <UserCard
              key={user.id}
              onChanged={() =>
                queryClient.invalidateQueries({ queryKey: ["users"] })
              }
              user={user}
            />
          ))}
        </div>
      )}
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

type UserUpdatePayload = {
  display_name?: string;
  role?: UserRole;
  is_active?: boolean;
  password?: string;
};

function UserCard({ user, onChanged }: { user: User; onChanged: () => void }) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState(user.display_name);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState<{
    payload: UserUpdatePayload;
    title: string;
    description: string;
  } | null>(null);
  const update = useMutation({
    mutationFn: (payload: UserUpdatePayload) =>
      userApi.update(user.id, payload),
    onSuccess: async (updated) => {
      setDisplayName(updated.display_name);
      setPassword("");
      setConfirmation(null);
      onChanged();
      if (auth.user?.id === user.id) {
        await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      }
    },
  });
  const pending = update.isPending;
  const self = auth.user?.id === user.id;
  const request = (
    payload: UserUpdatePayload,
    title: string,
    description: string,
  ) => setConfirmation({ payload, title, description });

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-foreground">{user.display_name}</p>
          <p className="mt-1 text-sm text-muted">{user.email}</p>
        </div>
        <div className="flex items-center gap-2">
          {self && <Badge tone="info">You</Badge>}
          <Badge tone={user.is_active ? "success" : "danger"}>
            {user.is_active ? "Active" : "Disabled"}
          </Badge>
        </div>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={`role-${user.id}`}>Role</Label>
          <Select
            disabled={pending}
            id={`role-${user.id}`}
            onChange={(event) => {
              const role = event.target.value as UserRole;
              if (role === user.role) return;
              request(
                { role },
                role === "builder"
                  ? "Demote administrator?"
                  : "Promote builder?",
                `Changing the role revokes this user's active sessions.${
                  self ? " Your own session may end immediately." : ""
                } The backend also prevents removal of the last active administrator.`,
              );
            }}
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
      <form
        className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          const payload: UserUpdatePayload = {
            ...(displayName.trim() !== user.display_name
              ? { display_name: displayName.trim() }
              : {}),
            ...(password ? { password } : {}),
          };
          if (!Object.keys(payload).length) return;
          if (password) {
            request(
              payload,
              "Reset password?",
              `Resetting the password revokes every active session for this user.${
                self ? " Your own session may end immediately." : ""
              }`,
            );
          } else update.mutate(payload);
        }}
      >
        <div className="space-y-2">
          <Label htmlFor={`display-name-${user.id}`}>Display name</Label>
          <Input
            disabled={pending}
            id={`display-name-${user.id}`}
            maxLength={160}
            onChange={(event) => setDisplayName(event.target.value)}
            value={displayName}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`password-${user.id}`}>New password (optional)</Label>
          <Input
            autoComplete="new-password"
            disabled={pending}
            id={`password-${user.id}`}
            minLength={12}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </div>
        <Button
          disabled={
            pending ||
            !displayName.trim() ||
            (Boolean(password) && password.length < 12) ||
            (displayName.trim() === user.display_name && !password)
          }
          type="submit"
          variant="outline"
        >
          Save account details
        </Button>
      </form>
      <Button
        className="mt-4"
        disabled={pending}
        onClick={() =>
          request(
            { is_active: !user.is_active },
            user.is_active ? "Disable user access?" : "Enable user access?",
            user.is_active
              ? `Disabling access revokes every active session.${
                  self ? " Your own session may end immediately." : ""
                } The last active administrator cannot be disabled.`
              : "Enabling access allows this identity to sign in with its current password.",
          )
        }
        size="sm"
        variant={user.is_active ? "destructive" : "outline"}
      >
        {user.is_active ? "Disable access" : "Enable access"}
      </Button>
      {update.error && <MutationError error={update.error} />}
      <Dialog
        description={confirmation?.description}
        onClose={() => setConfirmation(null)}
        open={Boolean(confirmation)}
        title={confirmation?.title ?? "Confirm account change"}
      >
        <div className="flex justify-end gap-2">
          <Button
            disabled={pending}
            onClick={() => setConfirmation(null)}
            variant="outline"
          >
            Cancel
          </Button>
          <Button
            disabled={pending}
            onClick={() => {
              if (!update.isPending && confirmation)
                update.mutate(confirmation.payload);
            }}
            variant="destructive"
          >
            Confirm and revoke sessions
          </Button>
        </div>
      </Dialog>
    </Card>
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
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
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
      {create.error && <MutationError error={create.error} />}
      <Button
        className="w-full"
        disabled={
          !email || !displayName || password.length < 12 || create.isPending
        }
        type="submit"
      >
        {create.isPending ? "Creating…" : "Create user"}
      </Button>
    </form>
  );
}
