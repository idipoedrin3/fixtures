"use client";

import {useState} from "react";
import {useSelector} from "react-redux";
import {useSearchParams} from "next/navigation";
import {Icon} from "@iconify/react";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {LOANS_API} from "#/_api/loans.helpers";
import {PERMISSION_CODES} from "#/_constants/enums";
import ProtectedComponent from "#/_components/custom/protected-component";
import {LoanCreateDialog} from "./loan-create-dialog";
import {LoanDetailDialog} from "./loan-detail-dialog";
import {LoanEditDialog} from "./loan-edit-dialog";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {EmptyState} from "#/_components/common/nodata";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {Skeleton} from "@/components/ui/skeleton";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {Badge} from "#/_components/custom/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {formatCurrency, formatDate} from "#/_lib/utils";

export function LoansTable() {
  const institution = useSelector(selectSelectedInstitution);
  const params = useSearchParams();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [error, setError] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const detailId = params.get("dialog") === "loan-details" ? params.get("loan") : null;
  const closeDetails = () => router.replace("/loan-mgt?tab=loans");
  const openDetails = (id: string) =>
    router.replace(`/loan-mgt?tab=loans&dialog=loan-details&loan=${id}`);

  if (!institution) return <p>Select an institution to view loans.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Input
          aria-label="Search loans"
          placeholder="Search loans..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="max-w-sm rounded-xl"
        />
        <div className="ml-auto shrink-0">
          <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_CREATE_LOANS}>
            <Button onClick={() => setCreating(true)}>
              <Icon icon="hugeicons:add-01" className="mr-2 size-4" />
              Create Loan
            </Button>
          </ProtectedComponent>
        </div>
      </div>
      <PaginatedTableWrapper
        fetchFirstPage={async () => {
          const data = await LOANS_API.list({search});
          setError(false);
          return data;
        }}
        fetchFromUrl={async (query) => {
          const data = await LOANS_API.fromUrl(query);
          setError(false);
          return data;
        }}
        deps={[institution.id, search, refreshVersion]}
        onError={() => setError(true)}
      >
        {({data, loading, refresh}) =>
          error ? (
            <div role="alert" className="space-y-2">
              <p>Unable to load loans.</p>
              <Button variant="outline" onClick={() => void refresh()}>
                Retry
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {[
                      "Reference",
                      "Direction",
                      "Principal",
                      "Annual interest",
                      "Disbursement",
                      "Maturity",
                      "Status",
                    ].map((label) => (
                      <TableHead key={label}>{label}</TableHead>
                    ))}
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    Array.from({length: 5}).map((_, rowIndex) => (
                      <TableRow key={`loan-skeleton-${rowIndex}`}>
                        {Array.from({length: 8}).map((__, cellIndex) => (
                          <TableCell key={cellIndex}>
                            <Skeleton
                              className={
                                cellIndex === 7 ? "ml-auto h-8 w-8 rounded-full" : "h-4 w-3/4"
                              }
                            />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  ) : !data?.results.length ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={8}>
                        <EmptyState />
                      </TableCell>
                    </TableRow>
                  ) : (
                    data.results.map((loan) => (
                      <TableRow key={loan.base_uuid}>
                        <TableCell>
                          <button
                            type="button"
                            className="text-left font-medium text-primary hover:underline"
                            onClick={() => openDetails(loan.base_uuid)}
                          >
                            {loan.reference_code || "View Loan"}
                          </button>
                        </TableCell>
                        <TableCell>{loan.direction === "outflow" ? "Lent" : "Borrowed"}</TableCell>
                        <TableCell className="tabular-nums">
                          {formatCurrency(loan.principal)}
                        </TableCell>
                        <TableCell>{formatCurrency(loan.annual_interest_rate)}%</TableCell>
                        <TableCell>{formatDate(loan.disbursement_date)}</TableCell>
                        <TableCell>{formatDate(loan.maturity_date)}</TableCell>
                        <TableCell>
                          <Badge status={loan.status} />
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`Actions for loan ${loan.reference_code ?? loan.base_uuid}`}
                              >
                                <Icon icon="hugeicons:more-vertical-circle-01" className="size-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onSelect={() => openDetails(loan.base_uuid)}>
                                <Icon icon="hugeicons:view" className="mr-2 size-4" />
                                Details
                              </DropdownMenuItem>
                              <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_EDIT_LOANS}>
                                <DropdownMenuItem
                                  disabled={!loan.allow_changes}
                                  onSelect={() => setEditId(loan.base_uuid)}
                                >
                                  <Icon icon="hugeicons:edit-01" className="mr-2 size-4" />
                                  Edit
                                </DropdownMenuItem>
                              </ProtectedComponent>
                              <DropdownMenuItem disabled className="text-destructive">
                                <Icon icon="hugeicons:delete-02" className="mr-2 size-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )
        }
      </PaginatedTableWrapper>
      {detailId && !editId && (
        <LoanDetailDialog
          key={`detail-${detailId}`}
          uuid={detailId}
          onClose={closeDetails}
          onRefresh={() => setRefreshVersion((value) => value + 1)}
          onEdit={() => {
            setEditId(detailId);
            closeDetails();
          }}
        />
      )}
      {creating && (
        <LoanCreateDialog
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            setRefreshVersion((value) => value + 1);
          }}
        />
      )}
      {editId && (
        <LoanEditDialog
          key={`edit-${editId}`}
          uuid={editId}
          onClose={() => setEditId(null)}
          onSaved={() => {
            openDetails(editId);
            setEditId(null);
            setRefreshVersion((value) => value + 1);
          }}
        />
      )}
    </div>
  );
}
