"use client";

import type {Approval} from "#/_types/approvals.types";
import {RefreshCw} from "lucide-react";

import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {formatTransactionDate} from "#/_api/helpers";

const MAX_DOTS = 5;

interface SendBackIndicatorProps {
  approvals?: Approval[];
  className?: string;
}

export function SendBackIndicator({approvals, className}: SendBackIndicatorProps) {
  const sendBacks = (approvals ?? [])
    .flatMap((approval) => approval.tasks ?? [])
    .flatMap((task) => task.actions ?? [])
    .filter((action) => action.action === "sent_back")
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  if (sendBacks.length === 0) return null;

  const dots = Math.min(sendBacks.length, MAX_DOTS);
  const overflow = sendBacks.length - dots;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Sent back ${sendBacks.length} ${sendBacks.length === 1 ? "time" : "times"}`}
          className={`inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-100 ${
            className ?? ""
          }`}
        >
          <RefreshCw className="size-3.5 shrink-0" />
          <span className="whitespace-nowrap">
            Sent back {sendBacks.length} {sendBacks.length === 1 ? "time" : "times"}
          </span>
          <span className="flex items-center gap-1">
            {Array.from({length: dots}).map((_, index) => (
              <span key={index} className="size-1.5 rounded-full bg-amber-500" />
            ))}
            {overflow > 0 && <span className="text-[10px] leading-none">+{overflow}</span>}
          </span>
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-0 text-xs text-gray-700">
        <div className="border-b border-gray-100 px-3 py-2.5">
          <p className="text-sm font-semibold text-gray-900">Send-back history</p>
          <p className="mt-0.5 text-[11px] text-gray-500">
            This requisition was returned to an earlier approval level {sendBacks.length}{" "}
            {sendBacks.length === 1 ? "time" : "times"}.
          </p>
        </div>

        <div className="max-h-72 overflow-y-auto">
          {sendBacks.map((action, index) => (
            <div key={action.id} className="border-b border-gray-100 px-3 py-2.5 last:border-b-0">
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-gray-900">
                  {index + 1}. Level {action.from_level} → Level {action.to_level}
                </span>
                <time className="shrink-0 text-right text-[11px] text-gray-500">
                  {formatTransactionDate(action.created_at)}
                </time>
              </div>

              {action.acted_by_fullname && (
                <p className="mt-0.5 text-[11px] text-gray-500">
                  by <span className="font-medium text-gray-700">{action.acted_by_fullname}</span>
                </p>
              )}

              {action.comment && (
                <p className="mt-1.5 leading-relaxed text-gray-700">"{action.comment}"</p>
              )}
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
