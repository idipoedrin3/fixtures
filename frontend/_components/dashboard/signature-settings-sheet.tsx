"use client";

import {useEffect, useState} from "react";
import {useSelector} from "react-redux";
import {toast} from "sonner";
import {USERS_API} from "#/_api/api.helpers";
import {SignaturePad} from "#/_components/common/signature-pad";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
import {Label} from "@/components/ui/label";
import {selectSelectedInstitution} from "@/store/auth/selectors";

interface SignatureSettingsSheetProps {
  open: boolean;
  onClose: () => void;
}

export default function SignatureSettingsSheet({open, onClose}: SignatureSettingsSheetProps) {
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [signature, setSignature] = useState<string | null>(null);
  const [initialSignature, setInitialSignature] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    const fetchSignature = async () => {
      setIsLoading(true);
      setSignature(null);
      setInitialSignature(null);

      try {
        const settings = await USERS_API.fetchCurrentUserSettings();

        if (!cancelled) {
          setSignature(settings.signature_base64);
          setInitialSignature(settings.signature_base64);
        }
      } catch {
        if (!cancelled) {
          toast.error("Failed to load signature");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchSignature();

    return () => {
      cancelled = true;
    };
  }, [open, currentInstitution?.base_uuid]);

  const handleSave = async () => {
    if (!signature || signature === initialSignature) return;

    setIsSaving(true);

    try {
      const response = await USERS_API.updateCurrentUserSettings({
        signature_base64: signature,
      });

      setSignature(response.signature_base64);
      setInitialSignature(response.signature_base64);
      toast.success("Signature saved successfully");
      onClose();
    } catch (error: any) {
      const message =
        error?.response?.data?.signature_base64?.[0] ??
        error?.response?.data?.message ??
        "Failed to save signature";

      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <SlideOverPanel
      open={open}
      onClose={() => {
        if (!isSaving) onClose();
      }}
      title="Signature"
      description={`Add the signature used for your profile at ${
        currentInstitution?.institution_name ?? "the selected institution"
      }.`}
      onSubmit={handleSave}
      submitLabel="Save Signature"
      isSubmitting={isSaving}
      submitDisabled={isLoading || !signature || signature === initialSignature}
    >
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading signature...</p>
      ) : (
        <div className="space-y-2">
          <Label>Your signature</Label>
          <SignaturePad
            value={signature}
            onChange={setSignature}
            readOnly={Boolean(initialSignature)}
          />
          <p className="text-xs text-muted-foreground">
            {initialSignature
              ? "Your signature is locked. Contact an authorized user if it needs to be reset."
              : "Draw your signature above, then save it to your profile."}
          </p>
        </div>
      )}
    </SlideOverPanel>
  );
}
