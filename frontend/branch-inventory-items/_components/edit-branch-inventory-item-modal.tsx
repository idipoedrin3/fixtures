"use client";

import GenericModal from "../../../_components/common/modals/custom-modal";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import SwitchSetting from "#/_components/common/inputs/switch-setting";
import type {IBranchInventoryItem} from "#/_types/api.types";
import {formatCurrency} from "#/_lib/utils";
import {useEffect, useRef, useState} from "react";

type RawUOM = NonNullable<IBranchInventoryItem["branch_inventory_item_units_of_measure"]>[number];
export type UOMEntry = RawUOM & {selling_price_num: number};

export interface BranchInventoryItemEditData {
  units: UOMEntry[];
  can_be_returned: boolean;
}

interface EditSellingPriceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (data: BranchInventoryItemEditData) => void | Promise<void>;
  initialUnits?: UOMEntry[];
  initialCanBeReturned?: boolean;
  isLoading?: boolean;
}

const PAGE_SIZE = 10;

function UOMRows({
  formData,
  setFormData,
}: {
  formData: {units: UOMEntry[]};
  setFormData: (data: {units: UOMEntry[]}) => void;
}) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const total = formData?.units?.length ?? 0;
  const visibleUnits = (formData?.units ?? []).slice(0, visibleCount);
  const hasMore = visibleCount < total;

  useEffect(() => {
    // reset when units list changes (modal reopened with different item)
    setVisibleCount(PAGE_SIZE);
  }, [total]);

  useEffect(() => {
    if (!hasMore) return;
    const sentinel = sentinelRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisibleCount((prev) => Math.min(prev + PAGE_SIZE, total));
        }
      },
      {root, threshold: 0.1},
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, total]);

  return (
    <div className="flex flex-col" style={{maxHeight: "52vh"}}>
      {/* Sticky headers */}
      <div
        className="flex-shrink-0 px-1 pb-2"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "10px",
          borderBottom: "1px solid hsl(var(--border))",
        }}
      >
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Unit of measure
        </span>
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Current price
        </span>
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          New price
        </span>
      </div>

      {/* Scrollable rows */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-2 pt-8 pr-1 pb-5">
        {(formData?.units ?? []).length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No units configured.</p>
        )}

        {visibleUnits.map((entry, index) => (
          <div
            key={entry.base_uuid}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: "10px",
              alignItems: "center",
            }}
          >
            {/* UOM — read-only */}
            <div className="flex h-9 items-center rounded-xl border bg-muted/40 px-3 text-sm">
              <span className="font-medium">{entry.unit_of_measure.unit_name}</span>
              <span className="ml-1.5 text-xs text-muted-foreground">
                ({entry.unit_of_measure.unit_abbreviation})
              </span>
            </div>

            {/* Current price — read-only */}
            <div className="flex h-9 items-center rounded-xl border bg-muted/40 px-3 text-sm text-muted-foreground">
              {formatCurrency(entry.selling_price)}
            </div>

            {/* New price — editable */}
            <FormattedNumberInput
              value={entry.selling_price_num}
              onValueChange={(value) =>
                setFormData({
                  units: (formData?.units ?? []).map((u, i) =>
                    i === index ? {...u, selling_price_num: value} : u,
                  ),
                })
              }
              placeholder="0.00"
              className="h-9 rounded-xl text-sm"
            />
          </div>
        ))}

        {hasMore && <div ref={sentinelRef} className="h-4" />}
        {hasMore && (
          <p className="pb-2 text-center text-xs text-muted-foreground">Loading more...</p>
        )}
      </div>
    </div>
  );
}

export default function EditSellingPriceModal({
  isOpen,
  onClose,
  onConfirm,
  initialUnits = [],
  initialCanBeReturned = false,
  isLoading = false,
}: EditSellingPriceModalProps) {
  return (
    <GenericModal<BranchInventoryItemEditData>
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Edit Branch Inventory Item"
      description="Update return availability and selling prices for this branch."
      confirmText="Save changes"
      isLoading={isLoading}
      initialData={{
        units: initialUnits,
        can_be_returned: initialCanBeReturned,
      }}
    >
      {({formData, setFormData, setField}) => (
        <div className="space-y-5">
          <div className="rounded-xl border p-4">
            <SwitchSetting
              id="branch-item-can-be-returned"
              label="Allow item returns"
              description="Allow this item to be returned when sold from this branch."
              checked={formData.can_be_returned}
              onCheckedChange={(checked) =>
                setField("can_be_returned", checked)
              }
            />
          </div>

          <UOMRows
            formData={formData}
            setFormData={setFormData}
          />
        </div>
      )}
    </GenericModal>
  );
}
