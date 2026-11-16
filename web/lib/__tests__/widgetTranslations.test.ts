import { describe, expect, it } from "vitest";
import {
  normalizeLanguageCode,
  pruneTranslations,
  readTranslations,
} from "../widgetTranslations";

describe("normalizeLanguageCode", () => {
  it("lowercases the language and keeps the region", () => {
    expect(normalizeLanguageCode("DE")).toBe("de");
    expect(normalizeLanguageCode(" pt_BR ")).toBe("pt-BR");
    expect(normalizeLanguageCode("zh-Hans-CN")).toBe("zh-Hans-CN");
  });

  it("rejects anything that is not a language code", () => {
    for (const bad of ["", "  ", "d", "german", "de; x", "de\nx", "x".repeat(30), "../a"]) {
      expect(normalizeLanguageCode(bad)).toBeNull();
    }
  });
});

describe("readTranslations", () => {
  it("returns {} for missing or malformed data", () => {
    expect(readTranslations(undefined)).toEqual({});
    expect(readTranslations("nope")).toEqual({});
    expect(readTranslations([1, 2])).toEqual({});
  });

  it("keeps valid languages and drops the rest", () => {
    const result = readTranslations({
      DE: { title: "Hilfe" },
      "not a code": { title: "x" },
      fr: "broken",
    });

    expect(result).toEqual({ de: { title: "Hilfe" } });
  });
});

describe("pruneTranslations", () => {
  it("trims text and removes blank fields", () => {
    const result = pruneTranslations({
      de: { title: "  Hilfe  ", welcome_message: "   ", placeholder: "" },
    });

    expect(result).toEqual({ de: { title: "Hilfe" } });
  });

  it("drops languages with nothing in them", () => {
    expect(pruneTranslations({ de: { title: " " }, en: {} })).toEqual({});
  });

  it("keeps prompts that have a title and text, trimmed", () => {
    const result = pruneTranslations({
      de: {
        suggestion_prompts: [
          { title: " Preise ", description: " Was kostet es? ", icon: "", prompt: " Preise? " },
          { title: "", description: "x", icon: "", prompt: "no title" },
          { title: "no prompt", description: "x", icon: "", prompt: "  " },
        ],
      },
    });

    expect(result.de.suggestion_prompts).toEqual([
      { title: "Preise", description: "Was kostet es?", icon: "", prompt: "Preise?" },
    ]);
  });

  it("removes the prompt list when no prompt is usable", () => {
    const result = pruneTranslations({
      de: { title: "Hilfe", suggestion_prompts: [{ title: "", description: "", icon: "", prompt: "" }] },
    });

    expect(result).toEqual({ de: { title: "Hilfe" } });
  });

  it("keeps fields it does not edit", () => {
    const entry = { title: "Hilfe", future_field: "keep me" } as never;

    expect(pruneTranslations({ de: entry })).toEqual({ de: { title: "Hilfe", future_field: "keep me" } });
  });
});
