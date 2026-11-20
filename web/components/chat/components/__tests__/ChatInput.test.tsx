import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatInput } from "../ChatInput";

// ── Module mocks ──────────────────────────────────────────────────────────────

// Stub out VoiceInputModal — it is not the focus of these tests
vi.mock("../VoiceInputModal", () => ({
  VoiceInputModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="voice-modal" /> : null,
}));

// Stub out the file-upload hook so ChatInput renders without network calls
vi.mock("../../hooks/useFileUpload", () => ({
  useFileUpload: () => ({
    uploadFiles: vi.fn().mockResolvedValue([]),
    uploadProgress: [],
    isUploading: false,
    clearProgress: vi.fn(),
  }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderInput(props: Partial<React.ComponentProps<typeof ChatInput>> = {}) {
  const onSend = vi.fn();
  const utils = render(<ChatInput onSend={onSend} {...props} />);
  const textarea = utils.getByRole("textbox") as HTMLTextAreaElement;
  const sendButton = utils.getByTitle("Send message (Enter)") as HTMLButtonElement;
  return { ...utils, onSend, textarea, sendButton };
}

function typeIntoTextarea(textarea: HTMLTextAreaElement, text: string) {
  fireEvent.change(textarea, { target: { value: text } });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ChatInput, rendering", () => {
  it("renders a textarea with the default placeholder", () => {
    const { textarea } = renderInput();
    expect(textarea.placeholder).toBe("Type your message…");
  });

  it("renders with a custom placeholder when chatConfig provides one", () => {
    const { textarea } = renderInput({
      chatConfig: { chat_placeholder: "Ask me anything…" },
    });
    expect(textarea.placeholder).toBe("Ask me anything…");
  });

  it("renders with a custom placeholder prop when chatConfig is absent", () => {
    const { textarea } = renderInput({ placeholder: "Custom placeholder" });
    expect(textarea.placeholder).toBe("Custom placeholder");
  });

  it("renders the send button", () => {
    const { sendButton } = renderInput();
    expect(sendButton).toBeInTheDocument();
  });

  it("renders the attach file button", () => {
    renderInput();
    expect(screen.getByTitle("Attach file")).toBeInTheDocument();
  });

  it("renders the voice input button", () => {
    renderInput();
    expect(screen.getByTitle("Voice input")).toBeInTheDocument();
  });
});

describe("ChatInput, input state", () => {
  it("updates the textarea value when the user types", () => {
    const { textarea } = renderInput();
    typeIntoTextarea(textarea, "Hello world");
    expect(textarea.value).toBe("Hello world");
  });

  it("clears the input after a message is sent via the send button", async () => {
    const { textarea, sendButton } = renderInput();

    typeIntoTextarea(textarea, "Send this");
    fireEvent.click(sendButton);

    await waitFor(() => expect(textarea.value).toBe(""));
  });

  it("clears the input after pressing Enter (non-shift)", async () => {
    const { textarea } = renderInput();

    typeIntoTextarea(textarea, "Enter message");
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter", shiftKey: false });

    await waitFor(() => expect(textarea.value).toBe(""));
  });

  it("does NOT submit on Shift+Enter (new line intent)", () => {
    const { textarea, onSend } = renderInput();

    typeIntoTextarea(textarea, "line one");
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter", shiftKey: true });

    // onSend must not have been called
    expect(onSend).not.toHaveBeenCalled();
    // Text should remain
    expect(textarea.value).toBe("line one");
  });
});

describe("ChatInput, send button disabled state", () => {
  it("send button is disabled when the input is empty", () => {
    const { sendButton } = renderInput();
    expect(sendButton).toBeDisabled();
  });

  it("send button is enabled once the user types something", () => {
    const { textarea, sendButton } = renderInput();
    typeIntoTextarea(textarea, "x");
    expect(sendButton).not.toBeDisabled();
  });

  it("send button is disabled when the disabled prop is true, even with text", () => {
    const { textarea, sendButton } = renderInput({ disabled: true });
    typeIntoTextarea(textarea, "Hello");
    expect(sendButton).toBeDisabled();
  });

  it("does not call onSend when disabled and Enter is pressed", () => {
    const { textarea, onSend } = renderInput({ disabled: true });

    typeIntoTextarea(textarea, "Blocked");
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter", shiftKey: false });

    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("ChatInput, onSend callback", () => {
  it("calls onSend with the trimmed message content", async () => {
    const { textarea, sendButton, onSend } = renderInput();

    typeIntoTextarea(textarea, "  Hello!  ");
    fireEvent.click(sendButton);

    await waitFor(() =>
      expect(onSend).toHaveBeenCalledWith("Hello!", undefined)
    );
  });

  it("does not call onSend for a whitespace-only message", () => {
    const { textarea, sendButton, onSend } = renderInput();

    typeIntoTextarea(textarea, "   ");
    fireEvent.click(sendButton);

    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend when the input is empty and send button is clicked", () => {
    const { sendButton, onSend } = renderInput();
    fireEvent.click(sendButton);
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("ChatInput, formatting toolbar", () => {
  it("formatting toolbar is hidden by default", () => {
    renderInput();
    expect(screen.queryByTitle("Bold (Ctrl+B)")).not.toBeInTheDocument();
  });
});

describe("ChatInput, voice modal", () => {
  it("voice modal is not visible initially", () => {
    renderInput();
    expect(screen.queryByTestId("voice-modal")).not.toBeInTheDocument();
  });

  it("opens the voice modal when the microphone button is clicked", () => {
    renderInput();
    const micButton = screen.getByTitle("Voice input");
    fireEvent.click(micButton);
    expect(screen.getByTestId("voice-modal")).toBeInTheDocument();
  });
});
