"use client";

import {useEffect, useRef, useState, type ReactNode} from "react";
import {Icon} from "@iconify/react";
import {AnimatePresence, motion} from "framer-motion";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {
  Dialog, DialogOverlay, DialogPortal, DialogTitle,
} from "@/components/ui/dialog";
import DraggableFloatingContainer from "@/platform/v1/components/common/hoverable/draggable-floating-container";

interface Props {
  open: boolean;
  expanded: boolean;
  historyOpen: boolean;
  onExpandedChange: (expanded: boolean) => void;
  onOpenChange: (open: boolean) => void;
  onHistory: () => void;
  children: ReactNode;
}

export function AssistantPanel({
  open, expanded, historyOpen, onExpandedChange,
  onOpenChange, onHistory, children,
}: Props) {
  const [placement, setPlacement] = useState({left: 24, top: 24});
  const trigger = useRef<HTMLButtonElement>(null);
  const [portalContainer, setPortalContainer] = useState<HTMLElement>();

  useEffect(() => {
    function updateContainer() {
      const dialogs = Array.from(
        document.querySelectorAll<HTMLElement>(
          '[role="dialog"][data-state="open"]:not([data-floating-owner="accounting-assistant"])',
        ),
      ).filter((dialog) => !dialog.closest(
        '[data-floating-owner="accounting-assistant"]',
      ));
      const activeDialog = dialogs[dialogs.length - 1];
      setPortalContainer((previous) =>
        previous === activeDialog ? previous : activeDialog,
      );
    }

    updateContainer();
    const observer = new MutationObserver(updateContainer);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-state", "role"],
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!open || expanded) return;
    function position() {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(384, window.innerWidth - 32);
      const height = Math.min(530, window.innerHeight - 100);
      setPlacement({
        left: Math.max(16, Math.min(rect.right - width, window.innerWidth - width - 16)),
        top: Math.max(16, Math.min(rect.top - height - 12, window.innerHeight - height - 16)),
      });
    }
    position();
    window.addEventListener("resize", position);
    window.addEventListener("pointerup", position);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("pointerup", position);
    };
  }, [open, expanded]);

  return (
    <>
      <DraggableFloatingContainer
        storageKey="accounting-assistant"
        stackIndex={2}
        boundsMargin={24}
      >
        <Button
          ref={trigger}
          aria-label={open ? "Close Baisoft AI" : "Open Baisoft AI"}
          aria-expanded={open}
          title="Baisoft AI"
          className={`h-14 w-14 rounded-full bg-[#4169e1] p-0 text-white shadow-xl transition hover:scale-110 hover:bg-[#365899] ${expanded && open ? "invisible" : ""}`}
          onClick={() => onOpenChange(!open)}
        >
          <Icon
            icon={open ? "hugeicons:cancel-01" : "hugeicons:chat-bot"}
            className="!size-7"
          />
        </Button>
      </DraggableFloatingContainer>
      <Dialog open={open} onOpenChange={onOpenChange} modal={expanded}>
        <DialogPortal forceMount container={portalContainer}>
          <AnimatePresence>
          {open && (
          <motion.div
            key="assistant-presence"
            popover="manual"
            ref={(node) => {
              if (node && !node.matches(":popover-open")) {
                node.showPopover();
              }
            }}
            style={{
              position: "fixed",
              inset: 0,
              width: "100%",
              height: "100%",
              maxWidth: "none",
              maxHeight: "none",
              margin: 0,
              padding: 0,
              border: 0,
              background: "transparent",
              overflow: "visible",
              pointerEvents: "none",
            }}
          >
          {expanded && <DialogOverlay className="pointer-events-auto z-[60] bg-black/30" />}
          <DialogPrimitive.Content
            forceMount
            data-floating-owner="accounting-assistant"
            aria-describedby={undefined}
            onOpenAutoFocus={(event) => event.preventDefault()}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              trigger.current?.focus();
            }}
            onInteractOutside={(event) => {
              if (!expanded) event.preventDefault();
            }}
            className={
              expanded
                ? "fixed left-1/2 top-1/2 z-[61] h-[calc(100dvh-2rem)] max-h-[732px] w-[calc(100vw-2rem)] max-w-[1144px] -translate-x-1/2 -translate-y-1/2 outline-none"
                : "fixed z-[60] h-[min(530px,calc(100dvh-100px))] w-[calc(100vw-2rem)] max-w-96 outline-none"
            }
            style={{
              ...(expanded ? {} : placement),
              pointerEvents: "auto",
            }}
          >
            <motion.div
              className="h-full"
              initial={{opacity: 0, scale: 0.95, y: 20}}
              animate={{opacity: 1, scale: 1, y: 0}}
              exit={{opacity: 0, scale: 0.95, y: 20}}
              transition={{type: "spring", damping: 28, stiffness: 260}}
            >
            <Card className={`relative h-full overflow-hidden rounded-2xl border-0 bg-white text-gray-950 shadow-2xl ${expanded ? "assistant-expanded" : ""}`}>
              <header className={`absolute inset-x-0 top-0 z-20 flex items-center justify-between border-b border-gray-100 bg-white px-4 sm:px-6 ${expanded ? `py-6 ${historyOpen ? "md:left-[312px]" : ""}` : "py-4"}`}>
                {!historyOpen && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-lg"
                  aria-label="Toggle history sidebar"
                  onClick={onHistory}
                >
                  <Icon icon="hugeicons:menu-03" className="!size-6 text-gray-600" />
                </Button>
                )}
                {historyOpen && <div className={expanded ? "h-8 w-8 md:hidden" : "h-8 w-8"} />}
                <DialogTitle className="text-base font-bold sm:text-lg">
                  Baisoft AI
                </DialogTitle>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-full bg-gray-100 hover:bg-gray-200"
                    aria-label={expanded ? "Exit expanded mode" : "Expand assistant"}
                    onClick={() => onExpandedChange(!expanded)}
                  >
                    <Icon icon={expanded ? "hugeicons:collapse" : "hugeicons:arrow-expand-01"} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-full bg-gray-100 hover:bg-gray-200"
                    aria-label="Close assistant"
                    onClick={() => onOpenChange(false)}
                  >
                    <Icon icon="hugeicons:cancel-01" />
                  </Button>
                </div>
              </header>
              <div className="relative h-full">
                {children}
              </div>
            </Card>
            </motion.div>
          </DialogPrimitive.Content>
          </motion.div>
          )}
          </AnimatePresence>
        </DialogPortal>
      </Dialog>
    </>
  );
}
