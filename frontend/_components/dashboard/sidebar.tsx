"use client";

import {useEffect, useState} from "react";
import {Icon} from "@iconify/react";
import {usePathname} from "next/navigation";
import {useSelector} from "react-redux";
import {useDispatch} from "react-redux";
import Image from "next/image";

import {InstitutionBranchSelector} from "./institution-branch-selector";
import {InstitutionSwitcher} from "./institution-switcher";
import {TruncatedText} from "../common/truncated-text";

import {cn} from "@/lib/utils";
import {Button} from "@/components/ui/button";
import {selectSidebarOpened} from "@/store/miscellaneous/selectors";
import {toggleSideBar} from "@/store/miscellaneous/actions";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {useMobile} from "#/_hooks/use-mobile";
import {NavItem} from "#/(dashboard)/nav-items";
import Link from "@/platform/v1/components/link";

type Props = {
  navigation: NavItem[];
};

function SidebarItem({
  item,
  children,
  onToggle,
  onOpenSidebar,
  onClose,
  isMobileView,
  href,
  className,
  variant,
  size,
  ...rest
}: {
  item: any;
  children: React.ReactNode;
  onToggle: (title: string) => void;
  onOpenSidebar: () => void;
  onClose: () => void;
  isMobileView: boolean;
  href?: any;
  className?: string;
  variant?: string;
  size?: string;
  [key: string]: any;
}) {
  return item.submenu?.length ? (
    <Button
      className={className}
      variant={variant as any}
      size={size as any}
      onClick={() => {
        onToggle(item.title);
        onOpenSidebar();
      }}
    >
      {children}
    </Button>
  ) : (
    <Link
      href={href}
      className={className}
      prefetch
      onClick={(e) => {
        e.stopPropagation();
        if (isMobileView) onClose();
      }}
    >
      {children}
    </Link>
  );
}

export function DashboardSidebar({navigation}: Props) {
  const isSideBarOpened = useSelector(selectSidebarOpened);
  const selectedInstitution = useSelector(selectSelectedInstitution);
  const isMobile = useMobile();
  const [institutionNameInitials, setInstitutionNameInitials] = useState("");
  const [expandedItems, setExpandedItems] = useState<{[key: string]: boolean}>({});
  const [hasManuallyExpanded, setHasManuallyExpanded] = useState(false);

  useEffect(() => {
    if (!selectedInstitution) {
      return;
    }
    let initials = selectedInstitution?.institution_name
      ?.split(" ")
      .map((chunk: string) => chunk.charAt(0).toUpperCase())
      .join("");
    // Typing chunk to string explicitly here becomes useful when this module is integrated to the host platform
    // so this is not a mistake, just trying to avoid a lint error when this is synced

    setInstitutionNameInitials(initials);
  }, [selectedInstitution]);

  const pathName = usePathname();
  const dispatch = useDispatch();

  useEffect(() => {
    if (isMobile) {
      closeSideBar();
    }
  }, [pathName]);

  // useEffect(()=>{
  //   console.log("\n\n Mobile view is : ", isMobile)
  //   if(!isMobile){
  //     openSideBar()
  //   }
  // }, [isMobile])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isSideBarOpened && isMobile) {
        const target = event.target as HTMLElement;

        if (!target.closest(".mobile-nav-drawer") && !target.closest(".mobile-menu-button")) {
          closeSideBar();
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isSideBarOpened, isMobile]);

  useEffect(() => {
    if (hasManuallyExpanded) return;

    const matchingGroups = navigation.filter((item) =>
      item.submenu?.some((sub) => pathName === sub.href),
    );

    if (matchingGroups.length === 1) {
      setExpandedItems({[matchingGroups[0].title]: true});
    }
  }, []);

  const onSidebarToggle = () => {
    dispatch(toggleSideBar());
  };

  const closeSideBar = () => {
    if (isSideBarOpened) {
      dispatch(toggleSideBar());
    }
  };

  const openSideBar = () => {
    if (!isSideBarOpened) {
      dispatch(toggleSideBar());
    }
  };

  const toggleExpand = (title: string) => {
    setHasManuallyExpanded(true);
    setExpandedItems((prev) => ({[title]: !prev[title]}));
  };

  const renderNavigationItem = (item: (typeof navigation)[0], isMobileView = false) => {
    const isActive = item.submenu ? expandedItems[item.title] === true : pathName === item.href;

    const baseClasses =
      "w-full !rounded-xl flex items-center px-4 !py-2 text-md font-normal transition-colors";
    const openCloseClasses = isSideBarOpened ? "justify-between" : "justify-center";

    const activeClasses = item.submenu
      ? "bg-primary/10 text-primary" // submenu active
      : "bg-primary/80 text-gray-100"; // no submenu active
    const inactiveClasses = "text-gray-600 hover:bg-primary/10 hover:text-primary";

    if (item.href === "#" && !item.submenu?.length) return null;

    return (
      <div key={item.title} className="w-full py-0.5">
        <SidebarItem
          item={item}
          href={item.href}
          variant="ghost"
          className={cn(baseClasses, openCloseClasses, isActive ? activeClasses : inactiveClasses)}
          onToggle={toggleExpand}
          onOpenSidebar={openSideBar}
          onClose={closeSideBar}
          isMobileView={isMobileView}
        >
          <div className="flex items-center space-x-2">
            {item.icon}
            {isSideBarOpened ? <span className="flex-grow line-clamp-1">{item.title}</span> : null}
          </div>
          {isSideBarOpened ? (
            item.submenu?.length ? (
              expandedItems[item.title] ? (
                <Icon icon="hugeicons:arrow-down-01" className="h-4 w-4" />
              ) : (
                <Icon icon="hugeicons:arrow-right-01" className="h-4 w-4" />
              )
            ) : null
          ) : null}
        </SidebarItem>
        {item.submenu?.length && expandedItems[item.title] ? (
          <div className="ml-6 pl-4 flex flex-col space-y-2 mt-2 border-l-2 border-gray-200">
            {isSideBarOpened &&
              item.submenu.map((sub: (typeof item.submenu)[0]) => (
                <SidebarItem
                  key={sub.href}
                  href={sub.href}
                  item={sub}
                  variant="ghost"
                  className={`w-full !rounded-md !text-left flex items-center px-2 !h-8 text-sm  ${
                    pathName === sub.href ? activeClasses : inactiveClasses
                  }`}
                  onToggle={toggleExpand}
                  onOpenSidebar={openSideBar}
                  onClose={closeSideBar}
                  isMobileView={isMobileView}
                >
                  <span className="!w-full truncate !text-left !bg-transparent">{sub.title}</span>
                </SidebarItem>
              ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <>
      {isMobile ? (
        <>
          {isSideBarOpened && (
            <div
              className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity duration-300"
              onClick={closeSideBar}
            />
          )}

          {/* Drawer */}
          <div
            className={`mobile-nav-drawer fixed left-0 top-0 h-full w-80 bg-white transform transition-transform duration-300 ease-in-out z-[100] ${
              isSideBarOpened ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            {/* Drawer Header */}
            <div className="p-4 border-b border-gray-100 min-h-16 h-20 max-h-20 flex items-center justify-between">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className=" text-white rounded-sm flex items-center justify-center">
                  <Image
                    alt="Institution Logo"
                    className="object-cover rounded-xl"
                    height={50}
                    width={50}
                    src={
                      selectedInstitution?.institution_logo
                        ? `${process.env.NEXT_PUBLIC_BASE_URL || ""}${selectedInstitution.institution_logo}`
                        : "/logo-accounting.png" // fallback when missing
                    }
                    onError={(e) => {
                      // fallback when broken
                      (e.currentTarget as HTMLImageElement).src = "/logo-accounting.png";
                    }}
                  />
                </div>
                <span className="min-w-0 font-bold text-gray-900">
                  <TruncatedText
                    text={selectedInstitution?.institution_name}
                    maxLength={18}
                    contentClassName="mobile-nav-drawer z-[110]"
                  />
                </span>
                <InstitutionSwitcher />
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onSidebarToggle()}
                className="p-2 hover:bg-gray-100"
              >
                <Icon icon="cancel-01" className="h-5 w-5" />
              </Button>
            </div>

            {/* Branch Selector */}
            <div className="p-4 border-b border-gray-100">
              <InstitutionBranchSelector />
            </div>

            {/* Navigation Items */}
            <div className="flex-1 overflow-y-auto p-2 pb-20">
              {navigation.map((item: NavItem) => renderNavigationItem(item, isMobile))}
            </div>
          </div>
        </>
      ) : (
        <div
          className={cn(
            "bg-white transition-all duration-300",
            !isSideBarOpened ? "!w-20 !min-w-20 !max-w-20" : "!w-60 !min-w-60 !max-w-60",
          )}
        >
          <div className="flex flex-col h-full">
            {/* Logo and Toggle */}

            <div className="flex items-center justify-between py-4 mx-4 max-h-16 min-h-16 border-b border-gray-200">
              {isSideBarOpened ? (
                <div className="flex items-center gap-2 min-w-0">
                  {" "}
                  {/* min-w-0 enables truncate in flex */}
                  <div className="flex items-center justify-center h-10 w-10 rounded-md overflow-hidden">
                    <Image
                      className="w-full h-full object-cover object-center"
                      width={48}
                      height={48}
                      alt={selectedInstitution?.institution_name || ""}
                      src={
                        selectedInstitution?.institution_logo
                          ? selectedInstitution.institution_logo.startsWith("http")
                            ? selectedInstitution.institution_logo
                            : (process.env.NEXT_PUBLIC_BASE_URL || "") +
                              selectedInstitution.institution_logo
                          : "/logo-accounting.png"
                      }
                    />
                  </div>
                  <h1 className="min-w-0 text-lg font-semibold text-gray-900">
                    <TruncatedText
                      text={selectedInstitution?.institution_name}
                      maxLength={13}
                      textClassName="whitespace-nowrap"
                    />
                  </h1>
                  <InstitutionSwitcher />
                </div>
              ) : (
                <div className="flex items-center justify-center h-10 w-10 rounded-md overflow-hidden">
                  <Image
                    className="w-full h-full object-cover object-center"
                    width={48}
                    height={48}
                    alt={selectedInstitution?.institution_name || ""}
                    src={
                      selectedInstitution?.institution_logo
                        ? selectedInstitution.institution_logo.startsWith("http")
                          ? selectedInstitution.institution_logo
                          : (process.env.NEXT_PUBLIC_BASE_URL || "") +
                            selectedInstitution.institution_logo
                        : "/logo-accounting.png"
                    }
                  />
                </div>
              )}
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-2 overflow-y-auto max-h-[90dvh]">
              {navigation.map((item: (typeof navigation)[0]) => renderNavigationItem(item, false))}
            </nav>
          </div>
        </div>
      )}
    </>
  );
}
