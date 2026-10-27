"use client";

import {useState} from "react";
import {toast} from "sonner";
import {LENDERS_API} from "#/_api/loans.helpers";
import type {ILender, ILenderFormData} from "#/_types/loans.types";
import {showErrorToast} from "#/_lib/utils";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Textarea} from "@/components/ui/textarea";

export function LenderFormDialog({
  lender,
  onClose,
  onSuccess,
}: {
  lender?: ILender;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState(lender?.name ?? "");
  const [referenceCode, setReferenceCode] = useState(lender?.reference_code ?? "");
  const [description, setDescription] = useState(lender?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [nameError, setNameError] = useState("");

  const submit = async () => {
    if (saving) return;
    if (!name.trim()) {
      setNameError("Lender name is required");
      return;
    }
    setSaving(true);
    try {
      const payload: ILenderFormData = {
        name: name.trim(),
        description: description.trim(),
        ...(referenceCode.trim() ? {reference_code: referenceCode.trim()} : {}),
      };
      if (lender) await LENDERS_API.update(lender.base_uuid, payload);
      else await LENDERS_API.create(payload);
      toast.success(lender ? "Lender update submitted" : "Lender created");
      onSuccess();
    } catch (error) {
      showErrorToast({error, defaultMessage: "Unable to save lender"});
    } finally {
      setSaving(false);
    }
  };

  return (
    <SlideOverPanel
      open
      onClose={() => {
        if (!saving) onClose();
      }}
      title={lender ? "Edit Lender" : "Create Lender"}
      onSubmit={submit}
      submitLabel={lender ? "Update Lender" : "Create Lender"}
      isSubmitting={saving}
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="lender-reference-code" showOptional>
            Lender Code
          </Label>
          <Input
            id="lender-reference-code"
            value={referenceCode}
            maxLength={100}
            disabled={saving}
            onChange={(event) => setReferenceCode(event.target.value)}
            placeholder="Auto-generated if left blank"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="lender-name" required>
            Name
          </Label>
          <Input
            id="lender-name"
            value={name}
            maxLength={255}
            disabled={saving}
            onChange={(event) => {
              setName(event.target.value);
              setNameError("");
            }}
            aria-invalid={!!nameError}
            placeholder="Enter lender name"
          />
          {nameError && (
            <p role="alert" className="text-sm text-destructive">
              {nameError}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="lender-description" showOptional>
            Description
          </Label>
          <Textarea
            id="lender-description"
            value={description}
            disabled={saving}
            onChange={(event) => setDescription(event.target.value)}
            rows={4}
          />
        </div>
      </div>
    </SlideOverPanel>
  );
}
