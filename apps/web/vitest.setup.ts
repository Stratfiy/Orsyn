import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";

// Clear DOM after each test
afterEach(() => {
  cleanup();
});

// Clear localStorage before and after each test
beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});
