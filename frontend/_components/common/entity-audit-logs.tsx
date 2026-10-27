"use client";

import {Icon} from "@iconify/react";
import {useState} from "react";
import {EmptyState} from "#/_components/common/nodata";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {Input} from "@/components/ui/input";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {AUDIT_LOGS_API, IInstitutionAuditLog} from "#/_api/services/system.service";
import {Avatar, AvatarFallback, AvatarImage} from "@/components/ui/avatar";
import {formatDateTime} from "#/_lib/utils";

const ACTION_COLORS: Record<string, string> = {
  CREATE: "text-green-600",
  UPDATE: "text-amber-600",
  DELETE: "text-red-600",
  ACCESS: "text-green-600",
  LOGIN: "text-blue-600",
  LOGOUT: "text-gray-500",
};

function parseUser(raw: string | null) {
  if (!raw) return {name: "—", email: ""};
  const parts = raw.split("-");
  const emailIdx = parts.findIndex((p) => p.includes("@"));
  if (emailIdx === -1) return {name: raw, email: ""};
  const email = parts[emailIdx].trim();
  const name = (parts[emailIdx - 1] ?? "").trim() || email;
  return {name, email};
}

interface EntityAuditLogsProps {
  objectId: number;
  contentType: string;
  showSearch?: boolean;
}

export default function EntityAuditLogs({
  objectId,
  contentType,
  showSearch = true,
}: EntityAuditLogsProps) {
  const [search, setSearch] = useState("");

  return (
    <div className="space-y-4">
      {showSearch && (
        <div className="relative w-full md:max-w-md">
          <Icon
            icon="hugeicons:search-01"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground h-4 w-4"
          />
          <Input
            placeholder="Search user, action, or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 rounded-xl"
          />
        </div>
      )}

      <PaginatedTableWrapper<IInstitutionAuditLog>
        query={{search, object_id: objectId, content_type: contentType}}
        deps={[search, objectId, contentType]}
        fetchFirstPage={AUDIT_LOGS_API.fetchFirstPage}
        fetchFromUrl={AUDIT_LOGS_API.fetchFromUrl}
      >
        {({data, loading}) => {
          const logs = data?.results ?? [];

          return (
            <div className="overflow-x-auto w-full">
              <Table className="min-w-[800px]">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">No</TableHead>
                    <TableHead>Staff</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    Array.from({length: 6}).map((_, i) => (
                      <TableRow key={i} className="border-none">
                        <TableCell colSpan={5}>
                          <div className="h-4 bg-muted animate-pulse rounded" />
                        </TableCell>
                      </TableRow>
                    ))
                  ) : logs.length === 0 ? (
                    <TableRow className="border-none">
                      <TableCell colSpan={5}>
                        <EmptyState />
                      </TableCell>
                    </TableRow>
                  ) : (
                    logs.map((log, i) => {
                      const {name, email} = parseUser(log.user);

                      return (
                        <TableRow key={log.id}>
                          <TableCell className="text-sm text-muted-foreground">{i + 1}</TableCell>

                          <TableCell className="whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Avatar className="size-7">
                                <AvatarImage
                                  src="/images/profile-placeholder.jpg"
                                  alt={name || "Automated"}
                                />
                                <AvatarFallback delayMs={600}>
                                  {name
                                    ?.split(" ")
                                    .reduce((z, x) => z + (x[0] ?? ""), "")
                                    .toUpperCase()}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex flex-col min-w-0">
                                <span className="font-medium truncate">{name}</span>
                                {email && (
                                  <span className="text-xs text-muted-foreground truncate">
                                    {email}
                                  </span>
                                )}
                              </div>
                            </div>
                          </TableCell>

                          <TableCell>
                            <span
                              className={`font-medium ${ACTION_COLORS[log.action] ?? "text-gray-600"}`}
                            >
                              {log.action?.toLowerCase()}
                            </span>
                          </TableCell>

                          <TableCell className="max-w-sm truncate" title={log.description}>
                            {log.description || "—"}
                          </TableCell>

                          <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                            {formatDateTime(log.timestamp)}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          );
        }}
      </PaginatedTableWrapper>
    </div>
  );
}
