"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {useSelector} from "react-redux";
import {ArrowUp, Square} from "lucide-react";
import {Icon} from "@iconify/react";
import {AnimatePresence, motion} from "framer-motion";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {
  selectAccessToken, selectSelectedInstitution, selectUser,
} from "@/store/auth/selectors";
import {AssistantPanel} from "./panel";
import {getAssistantHistory, isStandaloneAssistant} from "./api";
import {AssistantMessageItem} from "./message";
import {useAssistantConnection} from "./use-assistant-connection";
import type {
  AssistantChat, AssistantEvent, AssistantMessage, AssistantPendingRequest,
} from "./types";

export function AccountingAssistantWidget() {
  const token = useSelector(selectAccessToken);
  const user = useSelector(selectUser);
  const institution = useSelector(selectSelectedInstitution);
  if (!isStandaloneAssistant || !user || !institution || !token) return null;
  const identityKey = `${user.id}:${institution.base_uuid}`;
  return (
    <AssistantWidget
      key={identityKey}
      identityKey={identityKey}
      accessToken={token}
    />
  );
}

function AssistantWidget({
  identityKey, accessToken,
}: {identityKey: string; accessToken: string}) {
  const [open, setOpen] = useState(false);
  const [started, setStarted] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<AssistantChat[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [chatId, setChatId] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (!busy) return;
    const startedAt = Date.now();
    setElapsedTime(0);
    const timer = window.setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  const [status, setStatus] = useState("");
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [feedbackValues, setFeedbackValues] = useState<Record<string, boolean>>({});
  const [feedbackPending, setFeedbackPending] = useState<Record<string, boolean>>({});
  const active = useRef<AssistantPendingRequest | null>(null);
  const feedbackQueue = useRef<Record<string, boolean>>({});
  const end = useRef<HTMLDivElement>(null);

  const onEvent = useCallback((event: AssistantEvent) => {
    if (event.type === "FEEDBACK_SUCCESS" || event.type === "FEEDBACK_FAILURE") {
      const id = event.message_id;
      if (!id || !(id in feedbackQueue.current)) return;
      if (event.type === "FEEDBACK_SUCCESS") {
        const value = feedbackQueue.current[id];
        setFeedbackValues((previous) => ({...previous, [id]: value}));
        toast.success("Feedback received");
      } else {
        toast.error("Feedback could not be sent");
      }
      delete feedbackQueue.current[id];
      setFeedbackPending((previous) => ({...previous, [id]: false}));
      return;
    }
    const request = active.current;
    if (!request || event.request_id !== request.request_id) return;
    if (event.type === "STOP_REQUESTED") {
      setStatus("Stopping…");
      return;
    }
    if (event.type === "STATUS") setStatus(event.status || "Working…");
    if (["ANSWER_RESET", "ANSWER_CHUNK", "FINAL_ANSWER"].includes(event.type)) {
      setMessages((previous) => previous.map((message) => {
        if (
          message.role !== "assistant" ||
          message.message_id !== request.request_id
        ) return message;
        return {
          ...message,
          message: event.type === "ANSWER_RESET"
            ? ""
            : event.type === "FINAL_ANSWER"
              ? event.answer || ""
              : message.message + (event.token || ""),
        };
      }));
    }
    if (event.type === "FINAL_ANSWER") {
      setCompleted((previous) => new Set([...previous, request.request_id]));
      setHistoryVersion((value) => value + 1);
    }
    if (["FINAL_ANSWER", "STOPPED", "ERROR"].includes(event.type)) {
      setBusy(false);
      setStatus(event.type === "STOPPED" ? "Stopped" : "");
      if (event.type === "ERROR") {
        toast.error(event.error || "The assistant request failed");
      }
      active.current = null;
    }
  }, []);

  const transport = useAssistantConnection({
    enabled: started, accessToken, identityKey, onEvent,
  });

  useEffect(() => {
    if (!started) return;
    const controller = new AbortController();
    setHistoryLoading(true);
    setHistoryError(false);
    getAssistantHistory(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setHistory(result.chats);
      })
      .catch(() => {
        if (!controller.signal.aborted) setHistoryError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [started, historyVersion, accessToken]);

  useEffect(() => {
    if (open && !historyOpen) end.current?.scrollIntoView({block: "end"});
  }, [messages, open, historyOpen]);

  useEffect(() => {
    if (transport.connection === "connected") return;
    feedbackQueue.current = {};
    setFeedbackPending({});
  }, [transport.connection]);

  function send() {
    const text = question.trim();
    if (!text || busy) return;
    const request: AssistantPendingRequest = {
      type: "QUERY",
      request_id: crypto.randomUUID(),
      chat_id: chatId || crypto.randomUUID(),
      question: text,
    };
    if (!transport.submit(request)) {
      toast.error("Reconnect before sending another question");
      return;
    }
    active.current = request;
    setChatId(request.chat_id);
    setQuestion("");
    setBusy(true);
    setStatus("Working…");
    if (!expanded) setHistoryOpen(false);
    const timestamp = new Date().toISOString();
    setMessages((previous) => [
      ...previous,
      {
        id: `${request.request_id}:user`,
        message_id: request.request_id,
        role: "user",
        message: text,
        timestamp,
      },
      {
        id: `${request.request_id}:assistant`,
        message_id: request.request_id,
        role: "assistant",
        message: "",
        timestamp,
      },
    ]);
  }

  function selectChat(chat: AssistantChat) {
    if (busy) return;
    setChatId(chat.chat_id);
    setMessages(chat.messages);
    setCompleted(new Set(
      chat.messages.filter((item) => item.role === "assistant")
        .map((item) => item.message_id),
    ));
    setStatus("");
    setHistoryOpen(false);
  }

  function feedback(messageId: string, value: boolean) {
    if (!transport.feedback(messageId, value)) {
      toast.error("Reconnect to send feedback");
      return;
    }
    feedbackQueue.current[messageId] = value;
    setFeedbackPending((previous) => ({...previous, [messageId]: true}));
  }

  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <AssistantPanel
        open={open}
        expanded={expanded}
        historyOpen={historyOpen}
        onExpandedChange={(value) => {
          setExpanded(value);
          setHistoryOpen(value);
        }}
        onOpenChange={(value) => {
          if (value) setStarted(true);
          else {
            setExpanded(false);
            setHistoryOpen(false);
          }
          setOpen(value);
        }}
        onHistory={() => setHistoryOpen((value) => !value)}
      >
          <AnimatePresence>
          {historyOpen && (
          <motion.aside
            key="history"
            initial={{x: "-100%"}}
            animate={{x: 0}}
            exit={{x: "-100%"}}
            transition={{type: "spring", damping: 25, stiffness: 300}}
            className={`absolute bottom-0 left-0 z-[25] flex w-3/4 flex-col border-r border-gray-100 bg-white shadow-xl ${expanded ? "top-0 md:w-[312px] md:shadow-none" : "top-[65px]"}`}
          >
            <div className={`flex shrink-0 items-center justify-between border-b border-gray-100 px-4 sm:px-6 ${expanded ? "py-6" : "py-4"}`}>
              <h4 className="text-base font-semibold text-gray-900 sm:text-lg">
                History
              </h4>
              <div className="flex items-center space-x-2">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Refresh history"
                  disabled={historyLoading}
                  onClick={() => setHistoryVersion((value) => value + 1)}
                  className="h-10 w-10 rounded-lg p-0 hover:bg-gray-100"
                >
                  <Icon icon="hugeicons:reload" className={`!size-6 ${historyLoading ? "animate-spin" : ""}`} />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Close history sidebar"
                  onClick={() => setHistoryOpen(false)}
                  className="h-10 w-10 rounded-lg p-0 hover:bg-gray-100"
                >
                  <Icon icon="hugeicons:menu-03" className="!size-6" />
                </Button>
              </div>
            </div>
          <div className="shrink-0 border-b border-gray-100 px-3 py-3 sm:px-6">
            <Button
              variant="outline"
              className="h-11 w-full rounded-xl border-gray-300 bg-transparent text-sm transition-colors duration-200 hover:border-gray-400 hover:bg-gray-50"
              disabled={busy}
              onClick={() => {
                setChatId("");
                setMessages([]);
                setQuestion("");
                setCompleted(new Set());
                setStatus("");
                if (!expanded) setHistoryOpen(false);
              }}
            >
              <Icon icon="hugeicons:ai-chat-02" className="!size-6" />
              New Chat
            </Button>
          </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 sm:p-4">
                <>
                  {historyLoading && <p role="status">Loading chats…</p>}
                  {historyError && (
                    <Button variant="outline" onClick={() => setHistoryVersion((v) => v + 1)}>
                      Retry loading chats
                    </Button>
                  )}
                  {!historyLoading && !historyError && !history.length && (
                    <div className="py-8 text-center">
                      <p className="text-sm text-gray-500">No chat history yet</p>
                      <p className="mt-1 text-xs text-gray-400">
                        Start a conversation to see your chats here
                      </p>
                    </div>
                  )}
                  {history.map((chat) => (
                    <Button
                      key={chat.chat_id}
                      variant="ghost"
                      className={`h-auto w-full justify-start rounded-lg p-2.5 text-left hover:bg-gray-50 sm:p-3 ${chatId === chat.chat_id ? "bg-gray-50" : ""}`}
                      disabled={busy}
                      onClick={() => {
                        selectChat(chat);
                        if (expanded) setHistoryOpen(true);
                      }}
                    >
                      <span className="w-full space-y-2">
                        <span className="block truncate font-medium">{chat.title}</span>
                        <span className="flex items-center justify-between gap-2 text-xs font-normal">
                          <span className="text-gray-500">{chat.messages.length} messages</span>
                          <span className="text-gray-400">
                            {chat.messages.length > 0 && new Date(
                              chat.messages[chat.messages.length - 1].timestamp,
                            ).toLocaleDateString("en-GB", {
                              weekday: "short", day: "numeric", month: "short", year: "numeric",
                            })}
                          </span>
                        </span>
                      </span>
                    </Button>
                  ))}
                </>
            </div>
          </motion.aside>
          )}
          </AnimatePresence>
          <div className={`relative flex h-full min-w-0 flex-col ${expanded ? "pt-[81px]" : "pt-[65px]"} ${expanded && historyOpen ? "md:ml-[312px]" : ""}`}>
          {transport.error && (
            <div className="flex shrink-0 items-center gap-2 border-b px-4 py-2 text-sm" role="alert">
              <span className="flex-1">{transport.error}</span>
              <Button variant="outline" size="sm" onClick={transport.reconnect}>
                Reconnect
              </Button>
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className={messages.length ? "space-y-6 p-4" : "flex min-h-full flex-col"}>
                <>
                  {!messages.length && (
                    <div className="flex flex-1 flex-col items-center justify-center p-4 text-center sm:p-6">
                      <div className="mb-4 flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-[#1175AF] bg-gradient-to-br from-[#1175AF]/20 to-white sm:mb-6 sm:h-16 sm:w-16">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#1175AF]/70 to-[#1175AF] sm:h-10 sm:w-10">
                          <Icon icon="hugeicons:chat-bot" className="h-4 w-4 animate-pulse text-white sm:h-5 sm:w-5" />
                        </div>
                      </div>
                      <p className="mb-2 text-lg font-semibold text-gray-900 sm:mb-3 sm:text-xl">
                        What Can I Help You With?
                      </p>
                      <p className="max-w-2xl text-xs leading-relaxed text-gray-600 sm:text-sm">
                        Ask me anything about your accounting system, from invoices
                        and expenses to balances, financial reports, and analytics.
                      </p>
                    </div>
                  )}
                  {messages.map((message) => (
                    <AssistantMessageItem
                      key={message.id}
                      message={message}
                      elapsedTime={elapsedTime}
                      streaming={busy && message.role === "assistant" &&
                        message.message_id === active.current?.request_id}
                      feedbackEnabled={completed.has(message.message_id) &&
                        transport.connection === "connected"}
                      feedbackPending={feedbackPending[message.message_id]}
                      feedbackValue={feedbackValues[message.message_id]}
                      onFeedback={feedback}
                    />
                  ))}
                  <div ref={end} />
                </>
            </div>
          </div>
          {historyOpen && (
            <button
              type="button"
              aria-label="Close history sidebar"
              className={`absolute bottom-0 right-0 z-[24] w-1/4 bg-black/30 ${expanded ? "top-[81px] md:hidden" : "top-[65px]"}`}
              onClick={() => setHistoryOpen(false)}
            />
          )}
          <form
            className={`relative shrink-0 bg-white ${!messages.length && expanded ? "px-4 pb-4 pt-1" : "p-3 sm:p-4"}`}
            onSubmit={(event) => {event.preventDefault(); send();}}
          >
            <p className="sr-only" role="status">
              {status}
            </p>
            {!messages.length && (
              <div className="mb-4 flex flex-wrap justify-start gap-2 [.assistant-expanded_&]:justify-center">
                {[
                  "What is our cash position today?",
                  "Which customer invoices are overdue?",
                  "Summarize income and expenses this month.",
                  "Which suppliers have unpaid bills?",
                  "Compare this month’s profit with last month.",
                ].map((suggestion, index) => (
                  <Button
                    key={suggestion}
                    type="button"
                    variant="outline"
                    disabled={busy}
                    className={`h-auto whitespace-normal rounded-full border-0 bg-gray-100 px-3 py-2 text-xs text-gray-800 hover:bg-gray-200 ${index > 2 ? "hidden [.assistant-expanded_&]:inline-flex" : ""}`}
                    onClick={() => setQuestion(suggestion)}
                  >
                    {suggestion}
                  </Button>
                ))}
              </div>
            )}
            <div className="flex items-center space-x-2 sm:space-x-3">
            <Input
              aria-label="Ask accounting AI"
              placeholder="Type your question here..."
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  send();
                }
              }}
              disabled={busy}
              className="h-9 flex-1 overflow-hidden rounded-xl border-gray-200 px-3 text-xs transition-colors duration-200 placeholder:text-gray-400 focus:border-[#1175AF] focus:ring-[#1175AF] focus-visible:border-[#1175AF] focus-visible:ring-[#1175AF] sm:h-12 sm:px-4 sm:text-sm"
            />
            <div className="shrink-0">
              {busy ? (
                <Button type="button" size="icon" aria-label="Stop response"
                  className="!h-10 !w-10 shrink-0 rounded-full bg-gray-700 !p-0 text-white shadow-sm transition-all duration-200 hover:scale-105 hover:bg-gray-800 hover:shadow-md sm:!h-12 sm:!w-12"
                  onClick={() => {
                  transport.stop();
                  setStatus("Stopping…");
                }}>
                  <Square className="!size-5 fill-current sm:!size-6" />
                </Button>
              ) : (
                <Button type="submit" size="icon" aria-label="Send question"
                  className="!h-10 !w-10 shrink-0 rounded-2xl bg-[#1175AF] !p-0 text-white shadow-sm transition-all duration-200 hover:scale-105 hover:bg-[#0f6699] hover:shadow-md disabled:transform-none disabled:bg-gray-200 disabled:text-gray-400 sm:!h-12 sm:!w-12"
                  disabled={!question.trim() ||
                  transport.connection !== "connected"}>
                  <ArrowUp className="!size-5 sm:!size-6" />
                </Button>
              )}
            </div>
            </div>
          </form>
          </div>
      </AssistantPanel>
    </>
  );
}
