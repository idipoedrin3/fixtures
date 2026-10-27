"use client";

import {SettingsLauncher} from "#/_components/common/settings-launcher";
import {SignatureIcon} from "lucide-react";
import SignatureSettingsSheet from "./signature-settings-sheet";

export function DashboardSignatureSettingsLauncher() {
  return (
    <SettingsLauncher
      storageKey="dashboard-signature-settings-launcher"
      label="Signature Settings"
      icon={<SignatureIcon className="size-6" />}
      stackIndex={2}
    >
      {({open, onClose}) => <SignatureSettingsSheet open={open} onClose={onClose} />}
    </SettingsLauncher>
  );
}
