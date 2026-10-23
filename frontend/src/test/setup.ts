import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom does not implement scrollIntoView; stub it so components that call it
// (e.g. focusing the action panel) don't throw during tests.
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = vi.fn();
} else {
  vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(() => {});
}

// Unmount React trees and reset the DOM between tests.
afterEach(() => {
  cleanup();
});
