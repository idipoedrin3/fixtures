import {Button} from "@/components/ui/button";
import {Icon} from "@iconify/react";
import {useState, useEffect, useRef, ReactNode} from "react";
import {createPortal} from "react-dom";

interface SlideOverPanelProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: string;
  children: ReactNode;
  width?: "sm" | "md" | "lg" | "xl" | "xxl";
  allowRezize?: boolean;
  onSubmit?: () => void;
  submitLabel?: string;
  isSubmitting?: boolean;
  footer?: ReactNode;
  hideFooter?: boolean;
  side?: "left" | "right";
  onBodyRef?: (el: HTMLDivElement | null) => void;
  height?: string;
  submitDisabled?: boolean;
  closeOnOutsideClick?: boolean;
  portalContainer?: HTMLElement | null;
  animate?: boolean;
}

export function SlideOverPanel({
  open,
  onClose,
  title,
  description,
  children,
  width = "md",
  allowRezize = false,
  onSubmit,
  submitLabel = "Save",
  isSubmitting = false,
  footer,
  hideFooter = false,
  onBodyRef,
  side = "right",
  height,
  submitDisabled = false,
  closeOnOutsideClick = true,
  portalContainer,
  animate = true,
}: SlideOverPanelProps) {
  const [visible, setVisible] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [dynamicWidth, setDynamicWidth] = useState<number | null>(null);

  const panelRef = useRef<HTMLDivElement>(null);
  const firstFocusableRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      setMounted(true);
      if (animate) {
        requestAnimationFrame(() => requestAnimationFrame(() => setVisible(true)));
      } else {
        setVisible(true);
      }
    } else {
      setVisible(false);
      const t = setTimeout(() => setMounted(false), animate ? 450 : 0);
      return () => clearTimeout(t);
    }
  }, [animate, open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      onClose();
    };

    if (open) window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !panelRef.current) return;

    firstFocusableRef.current?.focus();

    const panel = panelRef.current;
    const selectors =
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(selectors)).filter(
        (el) => el.offsetParent !== null,
      );

      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    panel.addEventListener("keydown", handleTab);
    return () => panel.removeEventListener("keydown", handleTab);
  }, [open, mounted]);

  if (!mounted) return null;

  const baseWidth =
    width === "sm"
      ? 320
      : width === "lg"
        ? 448
        : width === "xl"
          ? 560
          : width === "xxl"
            ? 1700
            : 384;

  const finalWidth = dynamicWidth ?? baseWidth;

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();

    const startX = e.clientX;
    const startWidth = panelRef.current?.offsetWidth || 0;

    const onMove = (moveEvent: MouseEvent) => {
      const delta = side === "right" ? startX - moveEvent.clientX : moveEvent.clientX - startX;

      let newWidth = startWidth + delta;

      const min = baseWidth;
      const max = (portalContainer?.clientWidth ?? window.innerWidth) - 100;

      if (newWidth < min) newWidth = min;
      if (newWidth > max) newWidth = max;

      setDynamicWidth(newWidth);
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      data-state={open ? "open" : "closed"}
      style={{
        position: portalContainer ? "absolute" : "fixed",
        inset: 0,
        zIndex: 999,
      }}
    >
      {/* Backdrop */}
      <div
        onClick={() => closeOnOutsideClick && onClose()}
        style={{
          position: "absolute",
          inset: 0,
          background: visible ? "rgba(0,0,0,0.1)" : "transparent",
          opacity: visible ? 1 : 0,
          transition: "opacity 380ms ease",
        }}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        style={{
          position: portalContainer ? "absolute" : "fixed",
          top: 0,
          [side]: 0,
          width: `${finalWidth}px`,
          //height: height ?? "70vh",
          height: height ?? (portalContainer ? "100%" : "100dvh"),
          display: "flex",
          flexDirection: "column",
          background: "#fff",
          boxShadow: "0 25px 50px -12px rgba(0,0,0,0.25)",
          transform: visible
            ? "translateX(0)"
            : `translateX(${side === "right" ? "100%" : "-100%"})`,
          transition: animate ? "transform 430ms cubic-bezier(0.22, 1, 0.36, 1)" : "none",
        }}
      >
        {/* RESIZE HANDLE */}
        {allowRezize && (
          <div
            onMouseDown={handleResizeStart}
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              width: "6px",
              cursor: "col-resize",
              [side === "right" ? "left" : "right"]: 0,
            }}
          />
        )}

        <button
          ref={firstFocusableRef}
          onClick={onClose}
          aria-label="Close"
          style={{
            position: "absolute",
            top: 24,
            [side === "right" ? "left" : "right"]: 0,
            transform: side === "right" ? "translateX(-50%)" : "translateX(50%)",
            width: 32,
            height: 32,
            borderRadius: "9999px",
            border: "none",
            background: "#111827",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 8,
            lineHeight: 1,
            cursor: "pointer",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            zIndex: 2,
          }}
        >
          <Icon icon="hugeicons:cancel-01" className="!size-5" />
        </button>

        {/* Header */}
        <div style={{padding: 24, borderBottom: "1px solid #eee"}}>
          <div style={{display: "flex", justifyContent: "space-between"}}>
            <div>
              <h2>{title}</h2>
              {description && <p>{description}</p>}
            </div>
          </div>
        </div>

        {/* Body */}
        <div ref={(el) => onBodyRef?.(el)} style={{flex: 1, overflow: "auto", padding: 24}}>
          {children}
        </div>

        {!hideFooter && (
          <div style={{padding: 24}}>
            {footer ?? (
              <Button
                onClick={onSubmit}
                disabled={isSubmitting || submitDisabled}
                className="w-full rounded-full"
              >
                {isSubmitting ? "Saving..." : submitLabel}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>,
    portalContainer ?? document.body,
  );
}
