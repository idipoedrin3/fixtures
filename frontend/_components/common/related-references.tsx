"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";

export type RelatedReference = {
  id: string;
  reference: string;
  href?: string;
};

type RelatedReferencesProps = {
  items?: RelatedReference[];
};

export function RelatedReferences({items}: RelatedReferencesProps) {
  const router = useRouter();

  if (!items?.length) return null;

  const first = items[0];
  const remaining = items.slice(1);

  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        className={
          first.href
            ? "whitespace-nowrap text-sm font-medium text-primary hover:underline"
            : "whitespace-nowrap text-sm font-medium"
        }
        onClick={() => first.href && router.push(first.href)}
      >
        {first.reference}
      </button>

      {remaining.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="whitespace-nowrap text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
            >
              +{remaining.length} more
            </button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="start" className="min-w-44">
            {remaining.map((item) => (
              <DropdownMenuItem
                key={item.id}
                className={item.href ? "cursor-pointer" : ""}
                onSelect={() => item.href && router.push(item.href)}
              >
                {item.reference}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
