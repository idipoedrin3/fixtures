import apiRequest, {baseURL} from "#/_api/api-request";
import type {AssistantHistory} from "./types";

export const isStandaloneAssistant =
  process.env.NEXT_PUBLIC_SUPRALEDGER_SYSTEM_MODE === "STANDALONE";

export async function getAssistantHistory(
  signal?: AbortSignal,
): Promise<AssistantHistory> {
  if (!isStandaloneAssistant) {
    throw new Error("Accounting assistant is available only in standalone mode.");
  }
  const response = await apiRequest.get(
    "/assistant/user-chats/",
    null,
    {},
    {signal},
  );
  return response.data as AssistantHistory;
}

export function getAssistantSocketUrl(accessToken: string): string {
  if (!isStandaloneAssistant || !accessToken) {
    throw new Error("Standalone accounting authentication is required.");
  }
  const configuredUrl = process.env.NEXT_PUBLIC_ASSISTANT_WEBSOCKET_URL;
  if (!configuredUrl && !baseURL) {
    throw new Error("Accounting API URL is not configured.");
  }
  const url = configuredUrl
    ? new URL(configuredUrl, window.location.origin)
    : new URL("/ws/assistant/", new URL(baseURL, window.location.origin));

  if (url.protocol === "https:") url.protocol = "wss:";
  if (url.protocol === "http:") url.protocol = "ws:";
  if (!["ws:", "wss:"].includes(url.protocol)) {
    throw new Error("Invalid assistant WebSocket URL.");
  }
  if (window.location.protocol === "https:" && url.protocol !== "wss:") {
    throw new Error("A secure assistant connection is required.");
  }
  url.searchParams.set("token", accessToken);
  return url.toString();
}
