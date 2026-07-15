import type { ModelConfig } from "../store/modelStore";

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
    const err = await response.text();
    throw new Error(err || `HTTP ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
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
