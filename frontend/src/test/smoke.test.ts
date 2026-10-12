import { expect, test } from "vitest";

test("测试环境提供 DOM", () => {
  const node = document.createElement("main");
  expect(node.tagName).toBe("MAIN");
});
