import {Icon} from "@iconify/react";

interface DescriptionSectionProps {
  description?: string | null;
  title?: string;
}

export function DescriptionSection({description, title = "Notes"}: DescriptionSectionProps) {
  const content = description?.trim();

  if (!content) return null;

  return (
    <section className="mt-3 overflow-hidden rounded-xl border bg-muted/20">
      <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-3">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon icon="hugeicons:note-01" className="size-4" />
        </div>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>

      <div className="px-4 py-4">
        <p className="whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">
          {content}
        </p>
      </div>
    </section>
  );
}
