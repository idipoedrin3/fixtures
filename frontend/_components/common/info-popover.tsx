"use client";

import type React from "react";

import {Icon} from "@iconify/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {Button} from "@/components/ui/button";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";

const isSafeUrl = (href?: string) => !!href && /^https?:\/\//i.test(href);

const MarkdownMessage = ({content}: {content: string}) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({children}) => <p className="leading-relaxed mb-2 last:mb-0 break-words">{children}</p>,
        ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
        ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
        li: ({children}) => <li className="leading-relaxed">{children}</li>,
        strong: ({children}) => <strong className="font-semibold">{children}</strong>,
        em: ({children}) => <em className="italic">{children}</em>,
        blockquote: ({children}) => <div className="mb-0">{children}</div>,
        h1: ({children}) => <h1 className="text-base font-semibold mb-2">{children}</h1>,
        h2: ({children}) => <h2 className="text-sm font-semibold mb-2">{children}</h2>,
        h3: ({children}) => <h3 className="text-sm font-semibold mb-1">{children}</h3>,
        code: ({className, children, ...props}) => {
          const inline = !className;

          return inline ? (
            <code className="bg-background/20 px-1 py-0.5 rounded text-xs font-mono" {...props}>
              {children}
            </code>
          ) : (
            <pre className="bg-background/20 p-2 rounded text-xs font-mono overflow-x-auto mb-2 max-w-full">
              <code className={className}>{children}</code>
            </pre>
          );
        },
        a: ({href, children}) => (
          <a
            href={isSafeUrl(href) ? href : "#"}
            className="underline text-blue-500 hover:text-blue-600"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
};

interface InfoPopoverProps {
  children?: React.ReactNode;
  markdown?: string;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
  width?: "sm" | "md" | "lg";
}

const WIDTHS = {
  sm: "w-72",
  md: "w-96 max-w-[90vw]",
  lg: "w-[560px] max-w-[90vw]",
};

export default function InfoPopover({
  children,
  markdown,
  side = "top",
  className,
  width = "sm",
}: InfoPopoverProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="ml-1 mr-2 size-4 min-w-3 shrink-0 p-0 text-muted-foreground hover:bg-transparent hover:text-muted-foreground [&_svg]:!size-3"
        >
          <Icon icon="hugeicons:information-circle" />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        side={side}
        className={`bg-background text-foreground border-border shadow-xl ${WIDTHS[width]} max-h-[400px] overflow-y-auto whitespace-normal break-words text-sm p-4 leading-relaxed ${className ?? ""}`}
      >
        {markdown ? <MarkdownMessage content={markdown} /> : children}
      </PopoverContent>
    </Popover>
  );
}
