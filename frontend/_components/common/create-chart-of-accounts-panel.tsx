"use client";

import type {IAccount} from "#/_types/api.types";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
import {AccountCreateForm} from "#/(dashboard)/accounts/_components/account-create-form";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (id: string, name: string, account?: IAccount) => void;
  title?: string;
  portalContainer?: HTMLElement | null;
}

export function CreateAccountPanel({
  open,
  onClose,
  onCreated,
  title = "New Account",
  portalContainer,
}: Props) {
  return (
    <SlideOverPanel
      open={open}
      onClose={onClose}
      title={title}
      description="Create a new GL account."
      width="md"
      allowRezize
      portalContainer={portalContainer}
      hideFooter
    >
      <AccountCreateForm
        layout="panel"
        showHeader={false}
        fullWidthAction
        onCancel={onClose}
        onCreated={async (account) => {
          onCreated(account.base_uuid ?? String(account.id), account.account_name, account);
        }}
      />
    </SlideOverPanel>
  );
}
