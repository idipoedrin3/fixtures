"use client";

import type React from "react";
import {useCallback, useEffect, useRef, useState} from "react";

import ProtectedPage from "#/_components/custom/protected-page";
import {ConfirmationDialog} from "#/_components/common/dialogs/confirmation-dialog";
import {PERMISSION_CODES} from "#/_constants/enums";
import {useDocumentTitle} from "#/_hooks/use-document-title";
import {FEATURE_CODES} from "#/_constants/features.enum";
import {registerLeavePageGuard} from "@/platform/v1/navigation/leave-page-guard";

type LeaveGuard = {
  enabled: boolean;
  onLeave: () => void | Promise<unknown>;
  requireConfirmation?: boolean;
  message?: string;
};

type Props = {
  children: React.ReactNode;
  title?: string;
  className?: string;
  contentClassName?: string;
  permissions?: PERMISSION_CODES | FEATURE_CODES | (PERMISSION_CODES | FEATURE_CODES)[];
  leaveGuard?: LeaveGuard;
};

export function PageLayout({
  permissions,
  children,
  title,
  className,
  contentClassName,
  leaveGuard,
}: Props) {
  useDocumentTitle(title ?? "");
  const leaveGuardRef = useRef(leaveGuard);
  const leaveActionPromiseRef = useRef<Promise<unknown> | null>(null);
  const pendingProceedRef = useRef<(() => void) | null>(null);
  const [isLeaveConfirmationOpen, setIsLeaveConfirmationOpen] = useState(false);

  useEffect(() => {
    leaveGuardRef.current = leaveGuard;
  }, [leaveGuard]);

  const runLeaveAction = useCallback((): Promise<unknown> | null => {
    const currentGuard = leaveGuardRef.current;
    if (!currentGuard?.enabled) return null;
    if (leaveActionPromiseRef.current) return leaveActionPromiseRef.current;

    let leaveActionResult: void | Promise<unknown>;
    try {
      leaveActionResult = currentGuard.onLeave();
    } catch {
      return null;
    }

    const leaveActionPromise = Promise.resolve(leaveActionResult).catch(() => undefined);
    leaveActionPromiseRef.current = leaveActionPromise;
    void leaveActionPromise.finally(() => {
      if (leaveActionPromiseRef.current === leaveActionPromise) {
        leaveActionPromiseRef.current = null;
      }
    });
    return leaveActionPromise;
  }, []);

  const requestLeave = useCallback(
    (proceed: () => void) => {
      const currentGuard = leaveGuardRef.current;
      if (!currentGuard?.enabled) return false;

      if (currentGuard.requireConfirmation === false) {
        const leaveAction = runLeaveAction();
        if (leaveAction) {
          void leaveAction.finally(proceed);
        } else {
          proceed();
        }
        return true;
      }

      pendingProceedRef.current = proceed;
      setIsLeaveConfirmationOpen(true);
      return true;
    },
    [runLeaveAction],
  );

  const confirmLeave = useCallback(() => {
    const proceed = pendingProceedRef.current;
    pendingProceedRef.current = null;
    setIsLeaveConfirmationOpen(false);
    if (!proceed) return;

    const leaveAction = runLeaveAction();
    if (leaveAction) {
      void leaveAction.finally(proceed);
    } else {
      proceed();
    }
  }, [runLeaveAction]);

  const cancelLeave = useCallback(() => {
    pendingProceedRef.current = null;
    setIsLeaveConfirmationOpen(false);
  }, []);

  const discardChangesAndLeave = useCallback(() => {
    const proceed = pendingProceedRef.current;
    pendingProceedRef.current = null;
    setIsLeaveConfirmationOpen(false);
    proceed?.();
  }, []);

  useEffect(() => registerLeavePageGuard(requestLeave), [requestLeave]);

  useEffect(() => {
    if (!leaveGuard?.enabled) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (leaveGuardRef.current?.requireConfirmation === false) return;

      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [leaveGuard?.enabled, runLeaveAction]);

  return (
    <>
      <ProtectedPage permissionCode={permissions || []}>
        <div className={`rounded-t-lg bg-white border-0 mb-10 p-5 ${className}`}>
          <div
            className={`flex min-h-[83vh] h-full w-full flex-col ${
              contentClassName ?? "gap-y-6 pb-16"
            }`}
          >
            {children}
          </div>
        </div>
      </ProtectedPage>

      <ConfirmationDialog
        isOpen={isLeaveConfirmationOpen}
        onClose={cancelLeave}
        onConfirm={confirmLeave}
        contentClassName="max-w-md"
        footerClassName="grid grid-cols-3 gap-2 sm:space-x-0 [&>*]:mt-0 [&>*]:w-full [&>*:first-child]:order-3 [&>*:last-child]:order-[-1]"
        title="Save draft before leaving?"
        description={
          leaveGuard?.message ??
          "You have unsaved customer information. Save it as a draft before leaving this page?"
        }
        confirmText="Save draft"
        cancelText="Cancel"
        secondaryActionText="Discard"
        onSecondaryAction={discardChangesAndLeave}
      />
    </>
  );
}

export default PageLayout;
