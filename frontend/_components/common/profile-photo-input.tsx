"use client";

import {Icon} from "@iconify/react";
import {useEffect, useId, useRef, useState} from "react";

import {Avatar, AvatarFallback, AvatarImage} from "@/components/ui/avatar";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {cn} from "@/lib/utils";

type ProfilePhotoInputProps = {
  file: File | null;
  onFileChange: (file: File | null) => void;
  onRemoveExisting?: () => void;
  id?: string;
  label?: string;
  description?: string;
  accept?: string;
  maxSizeMB?: number;
  existingImageUrl?: string | null;
  optional?: boolean;
  disabled?: boolean;
  className?: string;
  previewClassName?: string;
};

export function ProfilePhotoInput({
  file,
  onFileChange,
  onRemoveExisting,
  id,
  label = "Profile Photo",
  description,
  accept = "image/*",
  maxSizeMB = 2,
  existingImageUrl,
  optional = true,
  disabled = false,
  className,
  previewClassName,
}: ProfilePhotoInputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const inputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(existingImageUrl ?? null);
  const [error, setError] = useState<string | null>(null);
  const helperText = description ?? `Upload A Photo (PNG, JPG, Maximum File Size ${maxSizeMB} MB)`;

  useEffect(() => {
    if (!file) {
      setPreviewUrl(existingImageUrl ?? null);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [existingImageUrl, file]);

  return (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={inputId} showOptional={optional}>
        {label}
      </Label>

      <div className="flex flex-wrap items-center gap-4">
        <Avatar className={cn("size-16 border", previewClassName)}>
          <AvatarImage src={previewUrl ?? undefined} alt={`${label} preview`} />
          <AvatarFallback>
            <Icon icon="hugeicons:user-circle" className="size-7 text-muted-foreground" />
          </AvatarFallback>
        </Avatar>

        <div
          className={cn(
            "flex h-12 min-w-64 flex-1 cursor-pointer items-center overflow-hidden rounded-xl border border-input bg-background px-3",
            disabled && "pointer-events-none cursor-not-allowed opacity-50",
          )}
        >
          <label htmlFor={inputId} className="flex min-w-0 flex-1 cursor-pointer items-center">
            <span className="inline-flex shrink-0 items-center gap-2 rounded-full bg-primary/10 px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/20">
              <Icon icon="hugeicons:upload-01" className="size-4" />
              Choose File
            </span>
            <span className="min-w-0 flex-1 truncate px-4 text-sm text-foreground">
              {file?.name ?? "No File Chosen"}
            </span>
          </label>

          {(file || (existingImageUrl && onRemoveExisting)) && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => {
                setError(null);
                if (file) {
                  onFileChange(null);
                } else {
                  onRemoveExisting?.();
                }
              }}
              className="flex size-7 shrink-0 items-center justify-center rounded-full text-destructive transition-colors hover:bg-destructive/10 disabled:pointer-events-none disabled:opacity-50"
              aria-label={file ? "Clear selected photo" : "Remove existing photo"}
              title={file ? "Clear Selected Photo" : "Remove Existing Photo"}
            >
              <Icon icon="hugeicons:cancel-01" className="size-4" />
            </button>
          )}
        </div>

        <Input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={accept}
          disabled={disabled}
          onChange={(event) => {
            const selectedFile = event.target.files?.[0] ?? null;

            if (selectedFile && selectedFile.size > maxSizeMB * 1024 * 1024) {
              setError(`File Size Must Not Exceed ${maxSizeMB} MB`);
              event.target.value = "";
              onFileChange(null);
              return;
            }

            setError(null);
            onFileChange(selectedFile);
          }}
          className="sr-only"
        />
      </div>

      {helperText && <p className="text-sm text-muted-foreground">{helperText}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
