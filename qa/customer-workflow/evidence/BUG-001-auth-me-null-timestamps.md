# Evidence: BUG-001 — `GET /api/v1/auth/me` returns null timestamps

No secrets in this file. User IDs are non-sensitive UUIDs/emails created for this QA round.

## Request 1 — GET /api/v1/auth/me (authenticated as the seeded admin account)

Response body:
```json
{
  "id": "76e1da4f-b2a7-49b3-883e-0033cc573b3a",
  "email": "admin@admin.com",
  "display_name": "MCPlica Admin",
  "role": "admin",
  "is_active": true,
  "created_at": null,
  "updated_at": null,
  "last_login_at": null
}
```
Reproduced twice, both times identical (not a one-off race).

## Request 2 — GET /api/v1/users (same session, immediately after)

Relevant entry for the same `id`:
```json
{
  "id": "76e1da4f-b2a7-49b3-883e-0033cc573b3a",
  "email": "admin@admin.com",
  "display_name": "MCPlica Admin",
  "role": "admin",
  "is_active": true,
  "created_at": "2026-09-02T10:13:11.926801Z",
  "updated_at": "2026-09-02T11:44:04.932248Z",
  "last_login_at": "2026-09-02T11:44:04.923885Z"
}
```

Same user, same instant, two endpoints, two different results for `created_at`/`updated_at`/`last_login_at`.

## Root cause (verified by reading source)

`backend/app/api/auth.py:128-137`:
```python
@router.get("/me", response_model=UserRead)
async def me(principal: CurrentPrincipal) -> UserRead:
    user = principal.user
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )
```
`UserRead` (`backend/app/schemas/auth.py:24-34`) declares `created_at`/`updated_at`/`last_login_at` as `datetime | None = None`. The `/me` handler constructs `UserRead` manually and never passes these three fields, so they silently default to `None` — Pydantic does not error because they're optional. `GET /users` (`backend/app/api/users.py`) evidently builds `UserRead` from the ORM object directly (`from_attributes=True`), which is why it returns the correct values for the identical row.
