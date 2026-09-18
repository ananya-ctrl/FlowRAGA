import { afterEach, describe, expect, it, vi } from "vitest";

import { endSession, loginAccount, restoreSession } from "./auth-api";

describe("browser authentication API", () => {
  afterEach(() => vi.restoreAllMocks());

  it("always includes browser credentials during login", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "access",
          token_type: "bearer",
          expires_in: 900,
          csrf_token: "csrf",
          user: { id: "1", email: "a@example.com", display_name: "A", created_at: "" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await loginAccount({ email: "a@example.com", password: "password" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/login",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
  });

  it("sends CSRF headers when refreshing and logging out", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/logout")) return new Response(null, { status: 204 });
      return new Response(
        JSON.stringify({
          access_token: "access",
          token_type: "bearer",
          expires_in: 900,
          csrf_token: "csrf-value",
          user: { id: "1", email: "a@example.com", display_name: "A", created_at: "" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });

    await restoreSession("csrf-value");
    await endSession("csrf-value");

    for (const call of fetchMock.mock.calls) {
      expect(call[1]?.credentials).toBe("include");
      expect(call[1]?.headers).toMatchObject({ "X-CSRF-Token": "csrf-value" });
    }
  });

  it("never writes tokens to localStorage", async () => {
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    await endSession("csrf-value");
    expect(storageSpy).not.toHaveBeenCalled();
  });
});
