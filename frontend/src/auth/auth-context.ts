import { createContext } from "react";
import type { LoginPayload } from "@/api/auth";
import type { User } from "@/api/contracts";

export type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  error: Error | null;
  login: (payload: LoginPayload) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
