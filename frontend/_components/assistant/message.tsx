"use client";

import {Copy, ThumbsDown, ThumbsUp} from "lucide-react";
import {motion} from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {AssistantMessage} from "./types";

interface Props {
  message: AssistantMessage;
  streaming?: boolean;
  elapsedTime?: number;
  feedbackEnabled?: boolean;
  feedbackPending?: boolean;
  feedbackValue?: boolean;
  onFeedback: (messageId: string, value: boolean) => void;
}

export function AssistantMessageItem({
  message,
  streaming = false,
  elapsedTime = 0,
  feedbackEnabled = false,
  feedbackPending = false,
  feedbackValue,
  onFeedback,
}: Props) {
  const isAssistant = message.role === "assistant";

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.message);
      toast.success("Answer copied");
    } catch {
      toast.error("Could not copy the answer");
    }
  }

  return (
    <article
      aria-label={isAssistant ? "Accounting AI answer" : "Your question"}
      aria-busy={streaming}
      className={
        isAssistant
          ? "min-w-0 space-y-2"
          : "ml-auto max-w-[85%] rounded-2xl rounded-tr-md bg-[#167db6] px-4 py-2.5 text-white shadow-sm [.assistant-expanded_&]:md:max-w-[42%]"
      }
    >
      <p className={`mb-2 text-xs font-medium ${isAssistant ? "text-gray-500" : "text-white/80"}`}>
        {isAssistant ? "Baisoft AI" : "You"}
      </p>
      {isAssistant ? (
        <div className="min-w-0 break-words text-sm leading-relaxed [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 [&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3 [&_code]:text-xs">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              a: ({href, children}) => {
                if (!href || !/^https?:\/\//i.test(href)) {
                  return <span>{children}</span>;
                }
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline underline-offset-2"
                  >
                    {children}
                  </a>
                );
              },
              img: ({alt}) => <span>{alt || "Image"}</span>,
              table: ({children}) => (
                <div className="my-3 overflow-x-auto rounded-md border">
                  <table className="w-full border-collapse text-left text-xs">
                    {children}
                  </table>
                </div>
              ),
              th: ({children}) => (
                <th className="border-b bg-muted px-3 py-2 font-medium">
                  {children}
                </th>
              ),
              td: ({children}) => (
                <td className="border-b px-3 py-2">{children}</td>
              ),
            }}
          >
            {message.message}
          </ReactMarkdown>
          {streaming && (
            <div className="flex items-center space-x-1 py-1" aria-label="Generating answer">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="h-1.5 w-1.5 rounded-full bg-gray-400"
                  animate={{
                    scale: [1, 1.3, 1],
                    opacity: [0.5, 1, 0.5],
                  }}
                  transition={{
                    duration: 0.8,
                    repeat: Number.POSITIVE_INFINITY,
                    ease: "easeInOut",
                    delay: i * 0.15,
                  }}
                />
              ))}
              {elapsedTime >= 5 && (
                <span className="pl-2 text-[10px] tabular-nums text-gray-400">
                  {elapsedTime}s
                </span>
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="whitespace-pre-wrap break-words text-sm">
          {message.message}
        </p>
      )}

      {isAssistant && !streaming && message.message && (
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Copy answer"
                onClick={copy}
              >
                <Copy />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Copy answer</TooltipContent>
          </Tooltip>
          {[true, false].map((value) => (
            <Tooltip key={String(value)}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={value ? "Helpful answer" : "Unhelpful answer"}
                  aria-pressed={feedbackValue === value}
                  disabled={!feedbackEnabled || feedbackPending}
                  className={feedbackValue === value ? "text-primary" : ""}
                  onClick={() => onFeedback(message.message_id, value)}
                >
                  {value ? <ThumbsUp /> : <ThumbsDown />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {value ? "Helpful" : "Not helpful"}
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      )}
    </article>
  );
}
