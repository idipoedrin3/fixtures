"use client";

import {useEffect, useState} from "react";
import {createPortal} from "react-dom";
import {LENDERS_API} from "#/_api/loans.helpers";
import type {ILender} from "#/_types/loans.types";
import Approvals from "#/_components/common/approvals/approvals";
import {RecordSwitcher} from "#/_components/common/record-switcher";
import {ResponsiveActions} from "#/_components/common/responsive-actions";
import {PERMISSION_CODES} from "#/_constants/enums";
import {Button} from "@/components/ui/button";

export function LenderDetailView({
  uuid,
  onEdit,
  onDelete,
  onRefresh,
  onClose,
  headerContainer,
}: {
  uuid: string;
  onEdit: (lender: ILender) => void;
  onDelete: (lender: ILender) => void;
  onRefresh: () => void;
  onClose: () => void;
  headerContainer: HTMLElement | null;
}) {
  const [lender, setLender] = useState<ILender | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [version, setVersion] = useState(0);
  const [panel, setPanel] = useState<HTMLDivElement | null>(null);
  const [toggle, setToggle] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    LENDERS_API.detail(uuid)
      .then((record) => { if (active) setLender(record); })
      .catch(() => { if (active) setError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [uuid, version]);

  if (loading) return <div className="p-5" role="status">Loading lender...</div>;
  if (error || !lender) return (
    <div className="space-y-3 p-5" role="alert">
      <p>Unable to load this lender.</p>
      <Button variant="outline" onClick={() => setVersion((value) => value + 1)}>Retry</Button>
    </div>
  );

  return (
    <div ref={setPanel} className="relative min-h-0 flex-1 overflow-y-auto">
      {headerContainer && createPortal(
      <div className="flex items-start justify-between gap-4 lg:pr-9">
        <div className="min-w-0">
        <RecordSwitcher<ILender>
          portalContainer={panel}
          currentId={lender.base_uuid}
          currentLabel={lender.name}
          currentDescription={lender.reference_code ?? undefined}
          basePath="/loan-mgt"
          getRecordPath={(record) => `/loan-mgt?tab=lenders&dialog=lender-details&lender=${record.base_uuid}`}
          fetchFirstPage={LENDERS_API.list}
          fetchFromUrl={LENDERS_API.fromUrl}
          idKey="base_uuid"
          labelKey="name"
          descriptionKey="reference_code"
          label="Lenders"
          className="max-w-full"
        />
        </div>
        <div className="-mt-1 ml-auto flex shrink-0 items-center gap-2">
          <div ref={setToggle} />
          <ResponsiveActions
            actions={[
              {
                key: "edit",
                label: "Edit",
                icon: "hugeicons:edit-01",
                visible: lender.allow_changes,
                permissionCode: PERMISSION_CODES.CAN_EDIT_LENDERS,
                onSelect: () => onEdit(lender),
              },
              {
                key: "delete",
                label: "Delete",
                icon: "hugeicons:delete-02",
                visible: lender.allow_changes && lender.approval_status === "active",
                permissionCode: PERMISSION_CODES.CAN_DELETE_LENDERS,
                onSelect: () => onDelete(lender),
              },
            ]}
          />
        </div>
      </div>,
      headerContainer,
      )}
      <Approvals
        entity="lender"
        data={lender}
        toggleContainer={toggle}
        onRefresh={() => { setVersion((value) => value + 1); onRefresh(); }}
        onActionComplete={(action) => { if (action === "reject") onClose(); }}
      >
        <div className="space-y-6 p-5">
          <div>
            <p className="mt-2 whitespace-pre-wrap text-muted-foreground">
              {lender.description || "No description provided."}
            </p>
          </div>
          <dl className="grid gap-5 sm:grid-cols-2">
            {[
              ["Approval", lender.approval_status.replaceAll("_", " ")],
              ["Availability", lender.is_active ? "Active" : "Inactive"],
              ["Created", new Date(lender.created_at).toLocaleString()],
              ["Last updated", new Date(lender.updated_at).toLocaleString()],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="mt-1 font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Approvals>
    </div>
  );
}
