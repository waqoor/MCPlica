import { api, jsonBody } from "./client";
import type { User } from "./contracts";
import type { components } from "./generated/schema";
import { endpointResponses } from "./generated/zod";

export type LoginPayload = { email: string; password: string };
export type AuthResponse = components["schemas"]["AuthResponse"];

export const authApi = {
  login: async (payload: LoginPayload) => {
    const response = await api<AuthResponse>(
      "/api/v1/auth/login",
      endpointResponses["post /api/v1/auth/login"],
      {
        method: "POST",
        body: jsonBody(payload),
      },
    );
    return response.user;
  },
  me: (signal?: AbortSignal) =>
    api<User>("/api/v1/auth/me", endpointResponses["get /api/v1/auth/me"], {
      signal,
    }),
  refresh: () =>
    api<AuthResponse>(
      "/api/v1/auth/refresh",
      endpointResponses["post /api/v1/auth/refresh"],
      { method: "POST" },
    ),
  logout: () =>
    api<void>(
      "/api/v1/auth/logout",
      endpointResponses["post /api/v1/auth/logout"],
      { method: "POST" },
    ),
};
