"use client";

import {SettingsLauncher} from "#/_components/common/settings-launcher";
import {InvoiceSettingsPanel} from "./invoice-settings-panel";

export function InvoiceSettings() {
  return (
    <SettingsLauncher storageKey="invoice-settings-launcher" label="Invoices Settings">
      {({open, onClose}) => <InvoiceSettingsPanel open={open} onClose={onClose} />}
    </SettingsLauncher>
  );
}
