import {ReactNode, useEffect, useRef, useState} from "react";

import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type Props = {
  link: string;
  title: string;
  children: ReactNode;
  onDownload: () => void;
};

export function PreviewDialog({children, link, title = "Document Preview", onDownload}: Props) {
  const [url, setURL] = useState(link);
  const [dynamicWidth, setDynamicWidth] = useState<number | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setURL(link);

    return () => window.URL.revokeObjectURL(url);
  }, [link, url]);

  const handleResizeStart = (edge: "left" | "right") => (e: React.MouseEvent) => {
    e.preventDefault();

    const startX = e.clientX;
    const startWidth = contentRef.current?.offsetWidth || 0;

    setIsResizing(true);

    const onMove = (moveEvent: MouseEvent) => {
      // Dialog is centered: dragging one edge outward should grow both sides,
      // so the delta counts double
      const delta =
        edge === "right" ? (moveEvent.clientX - startX) * 2 : (startX - moveEvent.clientX) * 2;

      let newWidth = startWidth + delta;

      const min = 480;
      const max = window.innerWidth - 40;

      if (newWidth < min) newWidth = min;
      if (newWidth > max) newWidth = max;

      setDynamicWidth(newWidth);
    };

    const onUp = () => {
      setIsResizing(false);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <Dialog onOpenChange={(open) => !open && setDynamicWidth(null)}>
      <form>
        <DialogTrigger asChild>{children}</DialogTrigger>
        <DialogContent
          ref={contentRef}
          className="h-[90vh] p-0 overflow-hidden"
          style={{
            width: dynamicWidth ? `${dynamicWidth}px` : "64rem",
            maxWidth: "calc(100vw - 40px)",
          }}
        >
          {/* RESIZE HANDLES — invisible strips on both edges */}
          <div
            onMouseDown={handleResizeStart("left")}
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: 0,
              width: "6px",
              cursor: "col-resize",
              zIndex: 10,
            }}
          />
          <div
            onMouseDown={handleResizeStart("right")}
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              right: 0,
              width: "6px",
              cursor: "col-resize",
              zIndex: 10,
            }}
          />

          <DialogHeader className="hidden">
            <DialogTitle />
          </DialogHeader>
          <div className="p-4 flex flex-col gap-2 h-full">
            <div className="flex items-center">
              <Button onClick={onDownload}>Download</Button>
              <span className="flex-grow text-center">{title}</span>
            </div>
            <iframe
              src={url}
              title={title}
              className="w-full flex-1 border-0"
              style={isResizing ? {pointerEvents: "none"} : undefined}
            />
          </div>
        </DialogContent>
      </form>
    </Dialog>
  );
}
