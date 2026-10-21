import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Each test starts with a clean page and no fake API responses left over.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
