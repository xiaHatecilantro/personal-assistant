/** 模块职责：通过 Fetch 消费知识问答 SSE，并把增量 token 暴露为异步迭代器。 */

import type { ModelConfig } from "../store/modelStore";
import { useAuthStore } from "../store/authStore";

export interface ChatOptions {
  modelConfig?: ModelConfig;
  fileContent?: string;
  filePath?: string;
}

/** SSE 流式聊天，返回 AsyncGenerator */
export async function* streamChat(
  message: string,
  options?: ChatOptions,
): AsyncGenerator<string, void, undefined> {
  const token = localStorage.getItem("token");
  const response = await fetch("/api/v1/knowledge/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      message,
      provider_config: options?.modelConfig
        ? {
            provider: options.modelConfig.provider,
            baseUrl: options.modelConfig.baseUrl,
            apiKey: options.modelConfig.apiKey,
            model: options.modelConfig.model,
          }
        : undefined,
      file_content: options?.fileContent,
      file_path: options?.filePath,
    }),
  });

  if (!response.ok) {
    if (response.status === 401) useAuthStore.getState().logout();
    const err = await response.text();
    throw new Error(err || `HTTP ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  // 网络 chunk 不保证按 SSE 行边界切分，残缺行必须留到下一 chunk 再解析。
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.done) return;
          if (data.token) yield data.token;
        } catch {
          // 跳过无法解析的行
        }
      }
    }
  } finally {
    reader.cancel();
  }
}
