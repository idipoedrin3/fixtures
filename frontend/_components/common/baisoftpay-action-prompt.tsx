"use client";

import Image from "next/image";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  contentClassName?: string;
};

export function BaisoftPayActionPrompt({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  contentClassName = "max-w-md",
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={contentClassName}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="flex gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            className="flex-1 bg-white text-foreground hover:bg-muted"
            onClick={() => {
              onOpenChange(false);
              onConfirm();
            }}
          >
            <Image
              src="/logo/baisoft-logo.png"
              alt=""
              aria-hidden
              width={20}
              height={20}
              className="mr-2 size-5 object-contain"
            />
            {confirmLabel}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={() => onOpenChange(false)}
          >
            Not Now
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
