"use client";

import {useRef, useState, type MouseEvent, type PointerEvent, type ReactNode} from "react";
import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import DraggableFloatingContainer from "@/platform/v1/components/common/hoverable/draggable-floating-container";

interface SettingsLauncherProps {
  storageKey: string;
  label: string;
  icon?: ReactNode;
  stackIndex?: number;
  children: (state: {open: boolean; onClose: () => void}) => ReactNode;
}

export function SettingsLauncher({
  storageKey,
  label,
  icon = <Icon icon="hugeicons:settings-02" className="size-6" />,
  stackIndex = 0,
  children,
}: SettingsLauncherProps) {
  const [open, setOpen] = useState(false);
  const pointerStartRef = useRef<{x: number; y: number} | null>(null);
  const suppressClickRef = useRef(false);

  const handlePointerDown = (event: PointerEvent<HTMLElement>) => {
    pointerStartRef.current = {x: event.clientX, y: event.clientY};
    suppressClickRef.current = false;
  };

  const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
    if (!pointerStartRef.current) return;

    const deltaX = event.clientX - pointerStartRef.current.x;
    const deltaY = event.clientY - pointerStartRef.current.y;
    suppressClickRef.current = deltaX * deltaX + deltaY * deltaY > 36;
  };

  const handlePointerUp = () => {
    if (suppressClickRef.current) {
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
  };

  const handleClick = (event: MouseEvent<HTMLElement>) => {
    if (suppressClickRef.current) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    setOpen(true);
  };

  return (
    <>
      <DraggableFloatingContainer
        storageKey={storageKey}
        stackIndex={stackIndex}
        boundsMargin={24}
        snapToRightEdge
      >
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              type="button"
              aria-label={label}
              className="flex h-14 w-14 items-center justify-center rounded-full bg-primary text-white shadow-md transition hover:bg-primary/90"
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onClick={handleClick}
            >
              {icon}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>{label}</p>
          </TooltipContent>
        </Tooltip>
      </DraggableFloatingContainer>

      {children({open, onClose: () => setOpen(false)})}
    </>
  );
}
