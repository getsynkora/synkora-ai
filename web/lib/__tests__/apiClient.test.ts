import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import axios from "axios";

// Mock axios before importing the module under test
vi.mock("axios");

const mockedAxios = vi.mocked(axios);

// We test the http module directly since client.ts is a barrel file
// that composes domain modules on top of APIClient from http.ts

describe("APIClient (lib/api/http)", () => {
  // We need a fresh module per-describe to control the axios mock properly.
  // Because axios.create() is called at module construction time we reset
  // between tests using interceptor tracking instead.

  let mockAxiosInstance: {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
    request: ReturnType<typeof vi.fn>;
    interceptors: {
      request: { use: ReturnType<typeof vi.fn> };
      response: { use: ReturnType<typeof vi.fn> };
    };
    defaults: { headers: Record<string, unknown> };
  };

  let requestInterceptor: (config: any) => any;
  let responseSuccessInterceptor: (response: any) => any;
  let responseErrorInterceptor: (error: any) => Promise<any>;

  beforeEach(() => {
    vi.resetModules();

    mockAxiosInstance = {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      request: vi.fn(),
      interceptors: {
        request: {
          use: vi.fn((onFulfilled) => {
            requestInterceptor = onFulfilled;
          }),
        },
        response: {
          use: vi.fn((onFulfilled, onRejected) => {
            responseSuccessInterceptor = onFulfilled;
            responseErrorInterceptor = onRejected;
          }),
        },
      },
      defaults: { headers: {} },
    };

    mockedAxios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("constructor / axios.create", () => {
    it("calls axios.create with the default base URL", async () => {
      await import("../api/http");
      expect(mockedAxios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          baseURL: expect.stringContaining("localhost:5001"),
        })
      );
    });

    it("sets Content-Type to application/json", async () => {
      await import("../api/http");
      const createCall = vi.mocked(axios.create).mock.calls[0][0] as any;
      expect(createCall.headers?.["Content-Type"]).toBe("application/json");
    });

    it("enables withCredentials for cookie-based auth", async () => {
      await import("../api/http");
      const createCall = vi.mocked(axios.create).mock.calls[0][0] as any;
      expect(createCall.withCredentials).toBe(true);
    });

    it("registers a request interceptor", async () => {
      await import("../api/http");
      expect(mockAxiosInstance.interceptors.request.use).toHaveBeenCalled();
    });

    it("registers a response interceptor", async () => {
      await import("../api/http");
      expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalled();
    });
  });

  describe("request interceptor — auth header injection", () => {
    it("attaches Bearer token when secureStorage has a valid token", async () => {
      const { secureStorage } = await import("../auth/secure-storage");
      secureStorage.storeTokens({ access_token: "tok_test_123", expires_in: 3600 });

      await import("../api/http");

      // Simulate the request interceptor being called
      const config = { headers: {} as Record<string, string> };
      const result = requestInterceptor(config);

      expect(result.headers.Authorization).toBe("Bearer tok_test_123");

      secureStorage.clearTokens();
    });

    it("does not attach Authorization header when no token is stored", async () => {
      const { secureStorage } = await import("../auth/secure-storage");
      secureStorage.clearTokens();

      await import("../api/http");

      const config = { headers: {} as Record<string, string> };
      const result = requestInterceptor(config);

      expect(result.headers.Authorization).toBeUndefined();
    });
  });

  describe("response interceptor — 401 handling", () => {
    it("passes through successful responses unchanged", async () => {
      await import("../api/http");

      const mockResponse = { data: { success: true }, status: 200 };
      const result = responseSuccessInterceptor(mockResponse);
      expect(result).toBe(mockResponse);
    });

    it("rejects non-401 errors without attempting a token refresh", async () => {
      const { secureStorage } = await import("../auth/secure-storage");
      secureStorage.storeTokens({ access_token: "tok_abc", expires_in: 3600 });

      await import("../api/http");

      const error = {
        response: { status: 500 },
        config: { url: "/api/v1/agents", headers: {} },
      };

      await expect(responseErrorInterceptor(error)).rejects.toMatchObject({
        response: { status: 500 },
      });

      secureStorage.clearTokens();
    });

    it("does not attempt token refresh for /auth/ endpoints on 401", async () => {
      const refreshSpy = vi.fn().mockResolvedValue(false);
      const { secureStorage } = await import("../auth/secure-storage");
      vi.spyOn(secureStorage, "refreshAccessToken").mockImplementation(refreshSpy);

      await import("../api/http");

      const error = {
        response: { status: 401 },
        config: { url: "/console/api/auth/login", headers: {}, _retry: false },
      };

      await expect(responseErrorInterceptor(error)).rejects.toBeDefined();
      expect(refreshSpy).not.toHaveBeenCalled();
    });

    it("does not attempt token refresh for /login endpoints on 401", async () => {
      const { secureStorage } = await import("../auth/secure-storage");
      const refreshSpy = vi
        .spyOn(secureStorage, "refreshAccessToken")
        .mockResolvedValue(false);

      await import("../api/http");

      const error = {
        response: { status: 401 },
        config: { url: "/console/api/login", headers: {}, _retry: false },
      };

      await expect(responseErrorInterceptor(error)).rejects.toBeDefined();
      expect(refreshSpy).not.toHaveBeenCalled();
    });
  });

  describe("request() method", () => {
    it("returns response.data for successful requests", async () => {
      mockAxiosInstance.request.mockResolvedValue({
        data: { id: "agent-1", name: "Test" },
        status: 200,
      });

      const { apiClient } = await import("../api/http");
      const result = await apiClient.request("GET", "/api/v1/agents");

      expect(result).toEqual({ id: "agent-1", name: "Test" });
    });

    it("forwards method, url, and data to axios.request", async () => {
      mockAxiosInstance.request.mockResolvedValue({ data: {} });

      const { apiClient } = await import("../api/http");
      await apiClient.request("POST", "/api/v1/agents", { name: "new-agent" });

      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "POST",
          url: "/api/v1/agents",
          data: { name: "new-agent" },
        })
      );
    });
  });
});
