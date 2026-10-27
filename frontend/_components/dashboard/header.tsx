"use client";

import {Icon} from "@iconify/react";
import {useEffect, useState} from "react";
import {useSelector} from "react-redux";
import {useDispatch} from "react-redux";
import Image from "next/image";

import FeatureSearchDialog from "../feature-search/feature-match-score";

import NotificationsDropdown from "./notifications-dropdown";

import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {Avatar, AvatarFallback} from "@/components/ui/avatar";
import {LogoutDialog} from "#/_components/dashboard/logout-dialog";
import {selectRefreshToken, selectSelectedInstitution, selectUser} from "@/store/auth/selectors";
import {InstitutionBranchSelector} from "#/_components/dashboard/institution-branch-selector";
import {CustomLink as Link} from "@/platform/v1/components/link";
import {selectSidebarOpened} from "@/store/miscellaneous/selectors";
import {toggleSideBar} from "@/store/miscellaneous/actions";
import {useMobile} from "#/_hooks/use-mobile";
import {Separator} from "@/components/ui/separator";
import {
  InstitutionSelectorDialog,
  InstitutionSelectorOption,
} from "#/_components/auth/institution-selector-dialog";
import {AUTH_API, USERS_API} from "#/_api/api.helpers";
import {
  setAccessToken,
  setRefreshToken,
  setSelectedBranches,
  setSelectedInstitution,
  setUserAction,
} from "@/store/auth/actions";
import {useToast} from "#/_hooks/use-toast";
import {persistor} from "@/store";

export function DashboardHeader() {
  const [showLogoutDialog, setShowLogoutDialog] = useState(false);
  const [showInstitutionDialog, setShowInstitutionDialog] = useState(false);
  const [institutions, setInstitutions] = useState<InstitutionSelectorOption[]>([]);
  const [switchingInstitutionUuid, setSwitchingInstitutionUuid] = useState<string | null>(null);
  const currentUser = useSelector(selectUser);
  const selectedInstitution = useSelector(selectSelectedInstitution);
  const refreshToken = useSelector(selectRefreshToken);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [userInitials, setUserInitials] = useState("U");
  const [searchDialogOpen, setSearchDialogOpen] = useState<boolean>(false);
  const collapsed = useSelector(selectSidebarOpened);
  const isMobile = useMobile();
  const {toast} = useToast();

  const dispatch = useDispatch();

  const toggleNavBar = () => {
    dispatch(toggleSideBar());
  };

  useEffect(() => {
    USERS_API.fetchUserAttachedInstitutions()
      .then(setInstitutions)
      .catch(() => setInstitutions([]));
  }, []);

  const handleInstitutionSwitch = async (institution: InstitutionSelectorOption) => {
    if (!refreshToken || institution.base_uuid === selectedInstitution?.base_uuid) return;

    setSwitchingInstitutionUuid(institution.base_uuid);

    try {
      const response = await AUTH_API.switchInstitution(institution.base_uuid, refreshToken);
      const nextInstitution = response.institutions_attached[0];

      dispatch(setAccessToken(response.tokens.access));
      dispatch(setRefreshToken(response.tokens.refresh));
      dispatch(setUserAction(response.user));
      dispatch(setSelectedInstitution(nextInstitution));
      dispatch(setSelectedBranches(nextInstitution.branches ?? []));

      setShowInstitutionDialog(false);
      await persistor.flush();
      window.location.assign("/dashboard");
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Unable to switch institution",
        description: error instanceof Error ? error.message : "Please try again.",
      });
    } finally {
      setSwitchingInstitutionUuid(null);
    }
  };

  useEffect(() => {
    if (!selectedInstitution || !currentUser) {
      return;
    }
    let role = "";

    if (selectedInstitution.institution_owner_id === currentUser.id) {
      role = "Super User";
    } else if (Array.isArray(currentUser.roles) && currentUser.roles.length > 0) {
      const matchingRole = currentUser.roles.find((r: {name: string}) => !!r.name);

      if (matchingRole) {
        // Format role to "Title Case"
        role = matchingRole.name.charAt(0).toUpperCase() + matchingRole.name.slice(1).toLowerCase();
      }
    }
    if (role.trim()) {
      setUserRole(role);
    }

    const nameParts = currentUser.fullname.split(" ");

    if (nameParts.length > 1) {
      setUserInitials(`${nameParts[0][0]}${nameParts[1][0]}`.toUpperCase());
    } else if (nameParts.length === 1) {
      setUserInitials(nameParts[0][0].toUpperCase());
    }
  }, [currentUser, selectedInstitution]);

  return (
    <>
      <header className="bg-white  border-0 px-4 flex items-center w-full !h-16 !min-h-16">
        <div className="flex items-center justify-between relative w-full">
          {!isMobile ? (
            <Icon
              onClick={toggleNavBar}
              icon={!collapsed ? "hugeicons:menu-05" : "hugeicons:menu-05"}
              className="w-6 h-6 !text-[#848496] cursor-pointer"
            />
          ) : (
            <Icon
              icon={"hugeicons:menu-05"}
              className="w-6 h-6 !text-[#848496] cursor-pointer"
              onClick={toggleNavBar}
            />
          )}

          <div className="flex-1" />

          <div className="hidden flex-1 lg:flex justify-center">
            <InstitutionBranchSelector />
          </div>

          <div className="flex-1 flex items-center justify-end space-x-4">
            <div className="relative inline-block">
              <Button
                variant="ghost"
                size="sm"
                className="p-2"
                onClick={() => setSearchDialogOpen(!searchDialogOpen)}
              >
                <Icon icon="hugeicons:search-01" width={24} height={24} className="!w-6 !h-6" />
              </Button>
              <FeatureSearchDialog open={searchDialogOpen} onOpenChange={setSearchDialogOpen} />
            </div>

            <Link href={"/admin"}>
              <Button variant="ghost" size="sm" className="p-2">
                <Icon icon="hugeicons:shield-01" width={24} height={24} className="!w-6 !h-6" />
              </Button>
            </Link>

            <NotificationsDropdown />

            <Separator className="h-[25px]" orientation="vertical" />

            <DropdownMenu>
              <DropdownMenuTrigger asChild className="rounded-full hover:bg-gray-100 !py-6">
                <Button variant="ghost" className="flex items-center gap-0.5 !py-4 !px-1">
                  <Avatar className="w-8 h-8">
                    <AvatarFallback className="bg-primary-100 text-primary-700 !relative">
                      <Image fill alt="Profile" src={"/images/profile-placeholder.jpg"} />
                    </AvatarFallback>
                  </Avatar>
                  <Icon icon="hugeicons:arrow-down-01" className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                {institutions.length > 1 && (
                  <DropdownMenuItem onSelect={() => setShowInstitutionDialog(true)}>
                    <Icon icon="hugeicons:arrow-left-right" className="mr-2 size-4" />
                    Switch Institution
                  </DropdownMenuItem>
                )}

                <DropdownMenuItem asChild>
                  <Link href="/user-setting">
                    <Icon icon="hugeicons:settings-01" className="w-4 h-4 mr-2" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => setShowLogoutDialog(true)}
                  className="text-red-600"
                >
                  <Icon icon="hugeicons:logout-03" className="w-4 h-4 mr-2" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <LogoutDialog open={showLogoutDialog} onOpenChange={setShowLogoutDialog} />

      <InstitutionSelectorDialog
        open={showInstitutionDialog}
        onOpenChange={setShowInstitutionDialog}
        institutions={institutions}
        title="Switch Institution"
        description="Choose the institution you want to work in. Your current session will securely move to the selected institution."
        selectedInstitutionUuid={selectedInstitution?.base_uuid}
        loadingInstitutionUuid={switchingInstitutionUuid}
        onSelect={handleInstitutionSwitch}
      />
    </>
  );
}
