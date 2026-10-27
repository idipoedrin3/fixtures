export interface AssistantMessage {
  id: string;
  message_id: string;
  role: "user" | "assistant";
  message: string;
  timestamp: string;
}

export interface AssistantChat {
  chat_id: string;
  title: string;
  messages: AssistantMessage[];
}

export interface AssistantHistory {
  user_id: string;
  chats: AssistantChat[];
}

export interface AssistantPendingRequest {
  type: "QUERY";
  request_id: string;
  chat_id: string;
  question: string;
}

export type AssistantConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "authentication-required";

export interface AssistantEvent {
  type: string;
  request_id?: string;
  chat_id?: string;
  message_id?: string;
  answer?: string;
  token?: string;
  status?: string;
  error?: string;
}
