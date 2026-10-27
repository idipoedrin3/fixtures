"use client";

import {Icon} from "@iconify/react";

import {Avatar, AvatarFallback} from "@/components/ui/avatar";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {cn} from "@/lib/utils";

export interface InstitutionSelectorOption {
  base_uuid: string;
  reference_code?: string | null;
  name?: string;
  institution_name?: string;
}

interface InstitutionSelectorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  institutions: InstitutionSelectorOption[];
  title: string;
  description: string;
  onSelect: (institution: InstitutionSelectorOption) => void | Promise<void>;
  selectedInstitutionUuid?: string;
  loadingInstitutionUuid?: string | null;
  alternativeActionLabel?: string;
  onAlternativeAction?: () => void;
}

export function InstitutionSelectorDialog({
  open,
  onOpenChange,
  institutions,
  title,
  description,
  onSelect,
  selectedInstitutionUuid,
  loadingInstitutionUuid,
  alternativeActionLabel,
  onAlternativeAction,
}: InstitutionSelectorDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-[500px] gap-5 rounded-[18px] p-4">
        <DialogHeader className="space-y-1 text-left">
          <DialogTitle className="text-xl font-semibold text-foreground">{title}</DialogTitle>
          <DialogDescription className="text-base leading-[22px] text-[#747479]">
            {description}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div
            className={cn(
              "max-h-[min(24rem,55vh)] overflow-y-auto rounded-lg border",
              "divide-y divide-border overscroll-contain",
            )}
          >
            {institutions.map((institution) => {
              const institutionName =
                institution.institution_name ?? institution.name ?? "Institution";
              const isCurrent = selectedInstitutionUuid === institution.base_uuid;
              const isLoading = loadingInstitutionUuid === institution.base_uuid;

              return (
                <Button
                  key={institution.base_uuid}
                  type="button"
                  variant="ghost"
                  disabled={isCurrent || !!loadingInstitutionUuid}
                  onClick={() => void onSelect(institution)}
                  className={cn(
                    "h-auto min-h-[68px] w-full justify-start rounded-none px-4 py-3",
                    "bg-white text-gray-800 hover:bg-[#F0F6FA]",
                    "first:rounded-t-lg last:rounded-b-lg",
                    isCurrent && "bg-primary/5 opacity-100",
                  )}
                >
                  <Avatar className="size-10 shrink-0">
                    <AvatarFallback className="bg-primary-100 text-sm font-semibold text-primary-700">
                      {institutionName.charAt(0).toUpperCase() || "I"}
                    </AvatarFallback>
                  </Avatar>

                  <div className="min-w-0 flex-1 text-left leading-[18px]">
                    <div className="truncate text-base font-medium">{institutionName}</div>
                    <div className="truncate text-sm text-gray-500">
                      {institution.reference_code}
                    </div>
                  </div>

                  {isLoading && (
                    <Icon
                      icon="mdi:loading"
                      className="ml-auto size-5 animate-spin text-primary"
                    />
                  )}

                  {isCurrent && (
                    <span className="ml-auto text-xs font-medium text-primary">Current</span>
                  )}
                </Button>
              );
            })}
          </div>

          {alternativeActionLabel && onAlternativeAction && (
            <button
              type="button"
              onClick={onAlternativeAction}
              className="block w-full text-center text-primary hover:underline"
            >
              {alternativeActionLabel}
            </button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
