"use client";

import {useState} from "react";
import {useSelector} from "react-redux";
import {useSearchParams} from "next/navigation";
import {toast} from "sonner";
import {Icon} from "@iconify/react";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {LENDERS_API} from "#/_api/loans.helpers";
import type {ILender} from "#/_types/loans.types";
import {showErrorToast} from "#/_lib/utils";
import {PERMISSION_CODES} from "#/_constants/enums";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {DeleteConfirmationDialog} from "#/_components/common/dialogs/delete-confirmation-dialog";
import {EmptyState} from "#/_components/common/nodata";
import {FeatureReportExport} from "#/_components/common/feature-report-export";
import {TruncatedText} from "#/_components/common/truncated-text";
import {Badge} from "#/_components/custom/badge";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Skeleton} from "@/components/ui/skeleton";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {LenderFormDialog} from "./lender-form-dialog";
import {LenderDetailView} from "./lender-detail-view";

export function LendersTable() {
  const [headerContainer, setHeaderContainer] = useState<HTMLDivElement | null>(null);
  const institution = useSelector(selectSelectedInstitution);
  const params = useSearchParams();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<ILender | "new" | null>(null);
  const [deleting, setDeleting] = useState<ILender | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const detailId = params.get("dialog") === "lender-details" ? params.get("lender") : null;
  const closeDetails = () => router.replace("/loan-mgt?tab=lenders");
  const openDetails = (lender: ILender) =>
    router.replace(`/loan-mgt?tab=lenders&dialog=lender-details&lender=${lender.base_uuid}`);

  if (!institution) return <p>Select an institution to view lenders.</p>;

  return (
    <div className="space-y-4">
      <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          aria-label="Search lenders"
          placeholder="Search lenders..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="w-full rounded-xl sm:w-64 sm:shrink-0"
        />
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_CREATE_LENDERS}>
            <Button onClick={() => setForm("new")} className="rounded-xl whitespace-nowrap">
              <Icon icon="hugeicons:add-01" className="mr-2 size-4" />
              New Lender
            </Button>
          </ProtectedComponent>
          <FeatureReportExport feature="Lender" />
        </div>
      </div>
      <PaginatedTableWrapper
        fetchFirstPage={async () => {
          const data = await LENDERS_API.list({search});
          setError(false);
          return data;
        }}
        fetchFromUrl={async (query) => {
          const data = await LENDERS_API.fromUrl(query);
          setError(false);
          return data;
        }}
        deps={[institution.id, search]}
        onError={() => setError(true)}
      >
        {({data, loading, refresh}) => (
          <>
            {error ? (
              <div role="alert" className="space-y-2">
                <p>Unable to load lenders.</p>
                <Button variant="outline" onClick={() => void refresh()}>
                  Retry
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {["Lender Code", "Name", "Description", "Status"].map((label) => (
                        <TableHead key={label}>{label}</TableHead>
                      ))}
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      Array.from({length: 5}).map((_, rowIndex) => (
                        <TableRow key={`lender-skeleton-${rowIndex}`}>
                          {Array.from({length: 5}).map((__, cellIndex) => (
                            <TableCell key={cellIndex}>
                              <Skeleton
                                className={
                                  cellIndex === 4 ? "ml-auto h-8 w-8 rounded-full" : "h-4 w-3/4"
                                }
                              />
                            </TableCell>
                          ))}
                        </TableRow>
                      ))
                    ) : !data?.results.length ? (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={5}>
                          <EmptyState />
                        </TableCell>
                      </TableRow>
                    ) : (
                      data.results.map((lender) => (
                        <TableRow key={lender.base_uuid}>
                          <TableCell>{lender.reference_code || "—"}</TableCell>
                          <TableCell>
                            <button
                              className="text-left hover:underline"
                              onClick={() => openDetails(lender)}
                            >
                              {lender.name}
                            </button>
                          </TableCell>
                          <TableCell className="max-w-xs">
                            <TruncatedText
                              text={lender.description}
                              maxLength={48}
                              emptyFallback="—"
                              singleLine
                              className="max-w-xs"
                            />
                          </TableCell>
                          <TableCell>
                            <Badge status={lender.is_active ? "active" : "inactive"} />
                          </TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label={`Actions for ${lender.name}`}
                                >
                                  <Icon
                                    icon="hugeicons:more-vertical-circle-01"
                                    className="size-4"
                                  />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => openDetails(lender)}>
                                  <Icon icon="hugeicons:view" className="mr-2 size-4" />
                                  View Details
                                </DropdownMenuItem>
                                {lender.allow_changes && (
                                  <ProtectedComponent
                                    permissionCode={PERMISSION_CODES.CAN_EDIT_LENDERS}
                                  >
                                    <DropdownMenuItem onClick={() => setForm(lender)}>
                                      <Icon icon="hugeicons:edit-01" className="mr-2 size-4" />
                                      Edit
                                    </DropdownMenuItem>
                                  </ProtectedComponent>
                                )}
                                {lender.allow_changes && lender.approval_status === "active" && (
                                  <ProtectedComponent
                                    permissionCode={PERMISSION_CODES.CAN_DELETE_LENDERS}
                                  >
                                    <DropdownMenuItem
                                      className="text-destructive focus:text-destructive"
                                      onClick={() => setDeleting(lender)}
                                    >
                                      <Icon icon="hugeicons:delete-02" className="mr-2 size-4" />
                                      Delete
                                    </DropdownMenuItem>
                                  </ProtectedComponent>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            )}

            <Dialog
              open={!!detailId}
              onOpenChange={(open) => {
                if (!open) closeDetails();
              }}
            >
              <DialogContent
                className="flex h-[94vh] !w-[90vw] !max-w-[90vw] flex-col gap-0 overflow-hidden p-0"
                onPointerDownOutside={(event) => event.preventDefault()}
              >
                <DialogHeader className="px-5 pt-5 text-left">
                  <DialogTitle asChild>
                    <div ref={setHeaderContainer}>
                      <span className="sr-only">Lender Details</span>
                    </div>
                  </DialogTitle>
                  <DialogDescription className="sr-only">
                    View lender information and approval history.
                  </DialogDescription>
                </DialogHeader>
                {detailId && (
                  <LenderDetailView
                    key={detailId}
                    uuid={detailId}
                    headerContainer={headerContainer}
                    onClose={closeDetails}
                    onRefresh={() => void refresh()}
                    onEdit={(lender) => {
                      closeDetails();
                      setForm(lender);
                    }}
                    onDelete={(lender) => {
                      closeDetails();
                      setDeleting(lender);
                    }}
                  />
                )}
              </DialogContent>
            </Dialog>

            {form && (
              <LenderFormDialog
                key={form === "new" ? "new" : form.base_uuid}
                lender={form === "new" ? undefined : form}
                onClose={() => setForm(null)}
                onSuccess={() => {
                  setForm(null);
                  void refresh();
                }}
              />
            )}
            <DeleteConfirmationDialog
              isOpen={!!deleting}
              onClose={() => {
                if (!busy) setDeleting(null);
              }}
              title="Delete Lender"
              description={`Request deletion of "${deleting?.name ?? ""}"? Approval may be required. Lenders referenced by loans cannot be deleted.`}
              isDeleting={busy}
              permissions={PERMISSION_CODES.CAN_DELETE_LENDERS}
              onConfirm={async () => {
                if (!deleting || busy) return;
                setBusy(true);
                try {
                  const result = await LENDERS_API.remove(deleting.base_uuid);
                  toast.success(
                    result === "pending" ? "Deletion submitted for approval" : "Lender deleted",
                  );
                  setDeleting(null);
                  void refresh();
                } catch (error) {
                  showErrorToast({error, defaultMessage: "Unable to delete lender"});
                } finally {
                  setBusy(false);
                }
              }}
            />
          </>
        )}
      </PaginatedTableWrapper>
    </div>
  );
}
