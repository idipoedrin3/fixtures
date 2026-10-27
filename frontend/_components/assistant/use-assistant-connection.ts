"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {getAssistantSocketUrl, isStandaloneAssistant} from "./api";
import type {
  AssistantConnectionState,
  AssistantEvent,
  AssistantPendingRequest,
} from "./types";

interface Options {
  enabled: boolean;
  accessToken: string;
  identityKey: string;
  onEvent: (event: AssistantEvent) => void;
}

export function useAssistantConnection({
  enabled,
  accessToken,
  identityKey,
  onEvent,
}: Options) {
  const [connection, setConnection] =
    useState<AssistantConnectionState>("disconnected");
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const eventRef = useRef(onEvent);
  const pendingRef = useRef<AssistantPendingRequest | null>(null);
  const stopRef = useRef(false);
  const acknowledgedRef = useRef(false);
  const identityRef = useRef(identityKey);
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    eventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (identityRef.current !== identityKey) {
      pendingRef.current = null;
      stopRef.current = false;
      acknowledgedRef.current = false;
      identityRef.current = identityKey;
    }
    if (!enabled || !isStandaloneAssistant || !identityKey) {
      setConnection("disconnected");
      return;
    }
    if (!accessToken) {
      setConnection("authentication-required");
      return;
    }

    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;

    const connect = () => {
      if (disposed) return;
      setConnection(attempts ? "reconnecting" : "connecting");
      let socket: WebSocket;
      try {
        socket = new WebSocket(getAssistantSocketUrl(accessToken));
      } catch {
        setError("Unable to configure the accounting assistant connection.");
        setConnection("disconnected");
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        if (disposed) return;
        attempts = 0;
        setError(null);
        setConnection("connected");
        const pending = pendingRef.current;
        if (pending) {
          acknowledgedRef.current = false;
          socket.send(JSON.stringify(pending));
        }
      };

      socket.onmessage = (message) => {
        if (disposed) return;
        let event: AssistantEvent;
        try {
          const parsed: unknown = JSON.parse(message.data);
          if (
            typeof parsed !== "object" ||
            parsed === null ||
            !("type" in parsed) ||
            typeof parsed.type !== "string"
          ) return;
          event = parsed as AssistantEvent;
        } catch {
          setError("The assistant returned an unreadable response.");
          return;
        }

        const pending = pendingRef.current;
        const matches = pending && event.request_id === pending.request_id;
        if (matches && event.type === "REQUEST_ID") {
          acknowledgedRef.current = true;
        }
        if (matches && event.type === "REQUEST_ID" && stopRef.current) {
          socket.send(JSON.stringify({
            type: "STOP",
            request_id: pending.request_id,
          }));
        }
        if (
          matches &&
          ["FINAL_ANSWER", "STOPPED", "ERROR"].includes(event.type)
        ) {
          pendingRef.current = null;
          stopRef.current = false;
          acknowledgedRef.current = false;
        }
        eventRef.current(event);
      };

      socket.onerror = () => {
        if (!disposed) setError("The assistant connection was interrupted.");
      };
      socket.onclose = (event) => {
        if (disposed) return;
        socketRef.current = null;
        if ([4401, 4403, 1008].includes(event.code)) {
          setConnection("authentication-required");
          setError("Refresh your accounting session to reconnect.");
          return;
        }
        setConnection("reconnecting");
        const delay = Math.min(1000 * 2 ** attempts, 30000);
        attempts += 1;
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      const socket = socketRef.current;
      socketRef.current = null;
      socket?.close();
    };
  }, [enabled, accessToken, identityKey, retryVersion]);

  const submit = useCallback((request: AssistantPendingRequest) => {
    if (
      !enabled ||
      !isStandaloneAssistant ||
      !accessToken ||
      identityRef.current !== identityKey ||
      pendingRef.current
    ) return false;
    pendingRef.current = request;
    stopRef.current = false;
    acknowledgedRef.current = false;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(request));
    } else if (!socket || socket.readyState >= WebSocket.CLOSING) {
      setRetryVersion((version) => version + 1);
    }
    return true;
  }, [enabled, accessToken, identityKey]);

  const stop = useCallback(() => {
    const pending = pendingRef.current;
    if (!pending || identityRef.current !== identityKey) return;
    stopRef.current = true;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN && acknowledgedRef.current) {
      socket.send(JSON.stringify({
        type: "STOP",
        request_id: pending.request_id,
      }));
    }
  }, [identityKey]);

  const feedback = useCallback((messageId: string, value: boolean) => {
    const socket = socketRef.current;
    if (
      !enabled ||
      !isStandaloneAssistant ||
      identityRef.current !== identityKey ||
      socket?.readyState !== WebSocket.OPEN
    ) return false;
    socket.send(JSON.stringify({
      type: "FEEDBACK",
      message_id: messageId,
      value,
    }));
    return true;
  }, [enabled, identityKey]);

  const reconnect = useCallback(() => {
    setRetryVersion((version) => version + 1);
  }, []);

  return {connection, error, submit, stop, feedback, reconnect};
}
