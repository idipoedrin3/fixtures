"use client";

import {useEffect, useState} from "react";
import {useDispatch, useSelector} from "react-redux";
import {Icon} from "@iconify/react";

import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Link from "@/platform/v1/components/link";
import {selectRefreshToken, selectSelectedInstitution} from "@/store/auth/selectors";
import {
  setAccessToken,
  setAttachedInstitutions,
  setRefreshToken,
  setSelectedBranches,
  setSelectedInstitution,
  setUserAction,
} from "@/store/auth/actions";
import {persistor} from "@/store";
import {AUTH_API, USERS_API} from "#/_api/api.helpers";
import {InstitutionSelectorOption} from "#/_components/auth/institution-selector-dialog";
import {useToast} from "#/_hooks/use-toast";

export function InstitutionSwitcher({label}: {label?: string}) {
  const [institutions, setInstitutions] = useState<InstitutionSelectorOption[]>([]);
  const [switching, setSwitching] = useState(false);
  const selectedInstitution = useSelector(selectSelectedInstitution);
  const refreshToken = useSelector(selectRefreshToken);
  const dispatch = useDispatch();
  const {toast} = useToast();

  useEffect(() => {
    USERS_API.fetchUserAttachedInstitutions()
      .then(setInstitutions)
      .catch(() => setInstitutions([]));
  }, []);

  const switchInstitution = async (institution: InstitutionSelectorOption) => {
    if (!refreshToken || switching || institution.base_uuid === selectedInstitution?.base_uuid) {
      return;
    }

    setSwitching(true);
    try {
      const response = await AUTH_API.switchInstitution(institution.base_uuid, refreshToken);
      const nextInstitution = response.institutions_attached[0];

      dispatch(setAccessToken(response.tokens.access));
      dispatch(setRefreshToken(response.tokens.refresh));
      dispatch(setUserAction(response.user));
      dispatch(setAttachedInstitutions(response.institutions_attached));
      dispatch(setSelectedInstitution(nextInstitution));
      dispatch(setSelectedBranches(nextInstitution.branches ?? []));
      await persistor.flush();
      window.location.assign("/dashboard");
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Unable to switch institution",
        description: error instanceof Error ? error.message : "Please try again.",
      });
      setSwitching(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant={label ? "outline" : "ghost"}
          size={label ? "default" : "icon"}
          disabled={switching}
          aria-label="Switch or create an institution"
          className={label ? "gap-2" : "size-6 shrink-0"}
        >
          <Icon
            icon={switching ? "mdi:loading" : "hugeicons:arrow-left-right"}
            className={`size-4 ${switching ? "animate-spin" : ""}`}
          />
          {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="mobile-nav-drawer z-[110] w-72 max-w-[calc(100vw-2rem)]"
      >
        <DropdownMenuLabel>Institutions</DropdownMenuLabel>
        <div className="max-h-64 overflow-y-auto">
          <DropdownMenuItem disabled className="flex-col items-start gap-1">
            <span className="w-full truncate">
              {selectedInstitution?.institution_name || "Current institution"}
            </span>
            <span className="text-xs text-primary">Current</span>
          </DropdownMenuItem>
          {institutions
            .filter((institution) => institution.base_uuid !== selectedInstitution?.base_uuid)
            .map((institution) => (
              <DropdownMenuItem
                key={institution.base_uuid}
                disabled={switching}
                onSelect={() => void switchInstitution(institution)}
              >
                <div className="min-w-0">
                  <div className="truncate">
                    {institution.institution_name ?? institution.name ?? "Institution"}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {institution.reference_code}
                  </div>
                </div>
              </DropdownMenuItem>
            ))}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild disabled={switching}>
          <Link href="/create-organisation">
            <Icon icon="hugeicons:add-01" className="size-5" />
            New Institution
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
