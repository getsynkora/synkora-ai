import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useChatTransport } from "../../components/chat/hooks/useChatTransport";
import type { ChatPayload } from "../../components/chat/hooks/useChatTransport";

// ── Mocks ─────────────────────────────────────────────────────────────────────

// Mock secureStorage so tests are isolated from token state
vi.mock("@/lib/auth/secure-storage", () => ({
  secureStorage: {
    getAccessToken: vi.fn(() => "test-token"),
    clearTokens: vi.fn(),
    storeTokens: vi.fn(),
    isTokenExpired: vi.fn(() => false),
  },
}));

// Mock fetch for SSE tests
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Minimal ReadableStream / reader mock used by SSE tests
function makeSseResponse(lines: string[]) {
  const encoder = new TextEncoder();
  const encoded = encoder.encode(lines.join("\n") + "\n");
  const done = false;
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        return {
          read: vi.fn().mockImplementationOnce(() =>
            Promise.resolve({ done: false, value: encoded })
          ).mockResolvedValue({ done: true, value: undefined }),
          cancel: vi.fn().mockResolvedValue(undefined),
        };
      },
    },
  };
}

const API_URL = "http://localhost:5001";

const basePayload: ChatPayload = {
  agent_slug: "test-agent",
  message: "Hello",
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── SSE mode ──────────────────────────────────────────────────────────────────

describe("useChatTransport — SSE mode (default)", () => {
  it("returns a sendMessage function", () => {
    const { result } = renderHook(() => useChatTransport("sse", API_URL));
    expect(typeof result.current.sendMessage).toBe("function");
  });

  it("sendMessage returns an async iterable", () => {
    const { result } = renderHook(() => useChatTransport("sse", API_URL));
    const iterable = result.current.sendMessage(basePayload);
    expect(typeof iterable[Symbol.asyncIterator]).toBe("function");
  });

  it("makes a POST request to /api/v1/agents/chat/stream with correct headers", async () => {
    // Respond with a single chunk then done
    const sseLines = [
      `data: ${JSON.stringify({ type: "chunk", content: "Hi" })}`,
      "data: [DONE]",
    ];
    mockFetch.mockReturnValue(makeSseResponse(sseLines));

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const events: any[] = [];
    const iterable = result.current.sendMessage(basePayload);
    for await (const event of iterable) {
      events.push(event);
    }

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_URL}/api/v1/agents/chat/stream`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer test-token",
        }),
      })
    );
  });

  it("serialises the payload as the request body", async () => {
    const sseLines = ["data: [DONE]"];
    mockFetch.mockReturnValue(makeSseResponse(sseLines));

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const payload: ChatPayload = { agent_slug: "bot", message: "test", conversation_id: "c-1" };
    const iterable = result.current.sendMessage(payload);
    // Consume without asserting events
    for await (const _ of iterable) { /* drain */ }

    const fetchCall = mockFetch.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(fetchCall.body as string);
    expect(body).toMatchObject({ agent_slug: "bot", message: "test", conversation_id: "c-1" });
  });

  it("yields parsed ChatEvent objects from SSE lines", async () => {
    const chunk = { type: "chunk", content: "Hello!" };
    const done = { type: "done", metadata: {} };
    const sseLines = [
      `data: ${JSON.stringify(chunk)}`,
      `data: ${JSON.stringify(done)}`,
    ];
    mockFetch.mockReturnValue(makeSseResponse(sseLines));

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const events: any[] = [];
    for await (const event of result.current.sendMessage(basePayload)) {
      events.push(event);
    }

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual(chunk);
    expect(events[1]).toEqual(done);
  });

  it("yields terminal SSE error events instead of throwing", async () => {
    const errorEvent = {
      type: "error",
      error: "API key is invalid or expired. Please check your LLM configuration.",
    };
    const sseLines = [
      `data: ${JSON.stringify({ type: "start", agent: "bot" })}`,
      `data: ${JSON.stringify(errorEvent)}`,
      `data: ${JSON.stringify({ type: "chunk", content: "should not render" })}`,
    ];
    mockFetch.mockReturnValue(makeSseResponse(sseLines));

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const events: any[] = [];
    for await (const event of result.current.sendMessage(basePayload)) {
      events.push(event);
    }

    expect(events).toEqual([{ type: "start", agent: "bot" }, errorEvent]);
  });

  it("throws when the server returns HTTP 402", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 402,
      json: async () => ({ detail: { message: "Insufficient credits" } }),
      body: null,
    });

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const collect = async () => {
      for await (const _ of result.current.sendMessage(basePayload)) { /* drain */ }
    };

    await expect(collect()).rejects.toThrow("Insufficient credits");
  });

  it("throws a generic HTTP error for non-402 failures", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      body: null,
    });

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const collect = async () => {
      for await (const _ of result.current.sendMessage(basePayload)) { /* drain */ }
    };

    await expect(collect()).rejects.toThrow("503");
  });

  it("throws when the response has no body", async () => {
    mockFetch.mockResolvedValue({ ok: true, body: null });

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    await expect(async () => {
      for await (const _ of result.current.sendMessage(basePayload)) { /* drain */ }
    }).rejects.toThrow("No response body");
  });

  it("skips lines that are not valid SSE data: lines", async () => {
    const sseLines = [
      ": keep-alive",
      "",
      `data: ${JSON.stringify({ type: "chunk", content: "A" })}`,
      "data: [DONE]",
    ];
    mockFetch.mockReturnValue(makeSseResponse(sseLines));

    const { result } = renderHook(() => useChatTransport("sse", API_URL));

    const events: any[] = [];
    for await (const event of result.current.sendMessage(basePayload)) {
      events.push(event);
    }

    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ type: "chunk", content: "A" });
  });
});

// ── WebSocket mode ────────────────────────────────────────────────────────────

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = MockWebSocket.OPEN;
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    // Simulate the open event asynchronously so the hook has time to attach handlers
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }
}

describe("useChatTransport — WebSocket mode", () => {
  let wsInstances: MockWebSocket[] = [];

  beforeEach(() => {
    wsInstances = [];
    vi.stubGlobal(
      "WebSocket",
      class extends MockWebSocket {
        constructor(url: string) {
          super(url);
          wsInstances.push(this as unknown as MockWebSocket);
        }
      }
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens a WebSocket to the correct URL (http → ws, https → wss)", async () => {
    renderHook(() => useChatTransport("websocket", "http://localhost:5001"));

    await waitFor(() => wsInstances.length > 0);
    expect(wsInstances[0].url).toBe("ws://localhost:5001/api/v1/agents/chat/ws");
  });

  it("converts https base URL to wss", async () => {
    renderHook(() => useChatTransport("websocket", "https://api.example.com"));

    await waitFor(() => wsInstances.length > 0);
    expect(wsInstances[0].url).toBe("wss://api.example.com/api/v1/agents/chat/ws");
  });

  it("sends an auth frame on open", async () => {
    renderHook(() => useChatTransport("websocket", API_URL));

    await waitFor(() => wsInstances.length > 0);
    await waitFor(() => wsInstances[0].sent.length > 0);

    const authFrame = JSON.parse(wsInstances[0].sent[0]);
    expect(authFrame).toEqual({ type: "auth", token: "test-token" });
  });

  it("yields terminal WebSocket error events instead of rejecting the stream", async () => {
    const { result } = renderHook(() =>
      useChatTransport("websocket", API_URL)
    );

    await waitFor(() => wsInstances.length > 0);
    const ws = wsInstances[0];
    ws.onmessage?.({ data: JSON.stringify({ type: "auth_ok" }) });

    const events: any[] = [];
    const collect = async () => {
      for await (const event of result.current.sendMessage(basePayload)) {
        events.push(event);
      }
    };
    const promise = collect();

    ws.onmessage?.({
      data: JSON.stringify({
        type: "error",
        error: "API key is invalid or expired. Please check your LLM configuration.",
      }),
    });

    await expect(promise).resolves.toBeUndefined();
    expect(events).toEqual([
      {
        type: "error",
        error: "API key is invalid or expired. Please check your LLM configuration.",
      },
    ]);
  });

  it("closes the WebSocket on unmount", async () => {
    const { unmount } = renderHook(() =>
      useChatTransport("websocket", API_URL)
    );

    await waitFor(() => wsInstances.length > 0);
    unmount();

    expect(wsInstances[0].readyState).toBe(MockWebSocket.CLOSED);
  });

  it("returns an error iterable when the WebSocket is not yet authenticated", async () => {
    const { result } = renderHook(() =>
      useChatTransport("websocket", API_URL)
    );

    // Not authenticated yet (wsAuthReadyRef is false on mount)
    const iterable = result.current.sendMessage(basePayload);
    expect(typeof iterable[Symbol.asyncIterator]).toBe("function");

    const collect = async () => {
      for await (const _ of iterable) { /* drain */ }
    };

    await expect(collect()).rejects.toThrow("WebSocket is not connected");
  });

  it("does not open a WebSocket connection when transport is 'sse'", () => {
    renderHook(() => useChatTransport("sse", API_URL));
    expect(wsInstances).toHaveLength(0);
  });
});
