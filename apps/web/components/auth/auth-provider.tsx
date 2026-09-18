"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  endSession,
  createCsrfToken,
  loginAccount,
  registerAccount,
  restoreSession,
  type Session,
  type User,
} from "@/lib/auth-api";

interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (displayName: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function hydrate() {
      try {
        const csrf = await createCsrfToken();
        const restored = await restoreSession(csrf);
        if (active) setSession(restored);
      } catch {
        if (active) setSession(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    void hydrate();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (session === null) return;
    const refreshInMilliseconds = Math.max((session.expires_in - 60) * 1000, 30_000);
    const timer = window.setTimeout(async () => {
      try {
        const refreshed = await restoreSession(session.csrf_token);
        setSession(refreshed);
      } catch {
        setSession(null);
      }
    }, refreshInMilliseconds);
    return () => window.clearTimeout(timer);
  }, [session]);

  const login = useCallback(async (email: string, password: string) => {
    setSession(await loginAccount({ email, password }));
  }, []);

  const register = useCallback(
    async (displayName: string, email: string, password: string) => {
      setSession(
        await registerAccount({
          display_name: displayName,
          email,
          password,
        }),
      );
    },
    [],
  );

  const logout = useCallback(async () => {
    const csrf = session?.csrf_token ?? (await createCsrfToken());
    try {
      await endSession(csrf);
    } finally {
      setSession(null);
    }
  }, [session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      accessToken: session?.access_token ?? null,
      loading,
      login,
      register,
      logout,
    }),
    [loading, login, logout, register, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
