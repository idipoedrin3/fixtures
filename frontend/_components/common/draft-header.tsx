"use client";

import {Icon} from "@iconify/react";
import {useState} from "react";

import type {IDraft} from "#/_api/services/system.service";
import {DeleteConfirmationDialog} from "#/_components/common/dialogs/delete-confirmation-dialog";
import {formatDateTime} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type DraftHeaderProps<TData> = {
  title?: string;
  getDraftLabel?: (draft: IDraft<TData>) => string;
  drafts: IDraft<TData>[];
  isLoading?: boolean;
  isLoadingMore?: boolean;
  hasMore?: boolean;
  discardingDraftId?: string | null;
  isDiscardingAll?: boolean;
  onRestore: (draft: IDraft<TData>) => void;
  onDiscard: (draft: IDraft<TData>) => Promise<void>;
  onDiscardAll: () => Promise<void>;
  onLoadMore?: () => Promise<void>;
};

export function DraftHeader<TData>({
  title = "Customer Drafts",
  getDraftLabel,
  drafts,
  isLoading = false,
  isLoadingMore = false,
  hasMore = false,
  discardingDraftId,
  isDiscardingAll = false,
  onRestore,
  onDiscard,
  onDiscardAll,
  onLoadMore,
}: DraftHeaderProps<TData>) {
  const [draftToDiscard, setDraftToDiscard] = useState<IDraft<TData> | null>(null);
  const [isConfirmingDiscardAll, setIsConfirmingDiscardAll] = useState(false);
  const [isDraftMenuOpen, setIsDraftMenuOpen] = useState(false);

  if (isLoading || drafts.length === 0) return null;

  return (
    <>
      <DropdownMenu open={isDraftMenuOpen} onOpenChange={setIsDraftMenuOpen}>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="outline" className="ml-auto gap-2 rounded-full">
            <Icon icon="hugeicons:file-02" className="size-4" />
            {drafts.length} saved {drafts.length === 1 ? "draft" : "drafts"}
            <Icon icon="hugeicons:arrow-down-01" className="size-4" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-80">
          <DropdownMenuLabel className="flex items-center justify-between gap-4">
            <span>{title}</span>
            <button
              type="button"
              className="text-xs font-medium text-destructive hover:underline"
              onClick={() => {
                setIsDraftMenuOpen(false);
                setIsConfirmingDiscardAll(true);
              }}
            >
              Clear all
            </button>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          <div
            className="max-h-80 overflow-y-auto"
            onScroll={(event) => {
              const element = event.currentTarget;
              const isNearBottom =
                element.scrollHeight - element.scrollTop - element.clientHeight < 40;

              if (isNearBottom && hasMore && !isLoadingMore) {
                void onLoadMore?.();
              }
            }}
          >
            {drafts.map((draft) => (
              <DropdownMenuItem
                key={draft.base_uuid}
                className="flex items-center gap-3 py-3"
                onSelect={(event) => event.preventDefault()}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => {
                    onRestore(draft);
                    setIsDraftMenuOpen(false);
                  }}
                >
                  <span className="block truncate text-sm font-medium">
                    {getDraftLabel?.(draft) || "Untitled draft"}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    Updated {formatDateTime(draft.updated_at)}
                  </span>
                </button>

                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  disabled={discardingDraftId === draft.base_uuid}
                  aria-label="Discard draft"
                  onClick={() => {
                    setDraftToDiscard(draft);
                    setIsDraftMenuOpen(false);
                  }}
                >
                  <Icon icon="hugeicons:delete-02" className="size-4 text-destructive" />
                </Button>
              </DropdownMenuItem>
            ))}

            {isLoadingMore && (
              <div className="flex items-center justify-center gap-2 py-3 text-xs text-muted-foreground">
                <span className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Loading more drafts...
              </div>
            )}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      <DeleteConfirmationDialog
        isOpen={Boolean(draftToDiscard)}
        onClose={() => {
          if (!discardingDraftId) setDraftToDiscard(null);
        }}
        onConfirm={async () => {
          if (!draftToDiscard) return;
          await onDiscard(draftToDiscard);
          setDraftToDiscard(null);
        }}
        title="Discard draft"
        description="Discard this draft permanently? This action cannot be undone."
        isDeleting={discardingDraftId === draftToDiscard?.base_uuid}
      />

      <DeleteConfirmationDialog
        isOpen={isConfirmingDiscardAll}
        onClose={() => {
          if (!isDiscardingAll) setIsConfirmingDiscardAll(false);
        }}
        onConfirm={async () => {
          await onDiscardAll();
          setIsConfirmingDiscardAll(false);
        }}
        title="Clear all drafts"
        description={`Permanently discard all ${drafts.length} saved drafts? This action cannot be undone.`}
        isDeleting={isDiscardingAll}
      />
    </>
  );
}
