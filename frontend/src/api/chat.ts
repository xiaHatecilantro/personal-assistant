import client from "./client";

export function askChat(message: string, options?: {
  modelConfig?: {
    provider: string;
    baseUrl: string;
    apiKey: string;
    model: string;
  };
  fileContent?: string;
  filePath?: string;
}): Promise<{ reply: string }> {
  return client.post("/knowledge/chat", {
    message,
    model_config: options?.modelConfig,
    file_content: options?.fileContent,
    file_path: options?.filePath,
  });
}
