"use client";

import type React from "react";
import type {PERMISSION_CODES} from "#/_constants/enums";

import {useState, useEffect, useMemo} from "react";

import PermissionDenied from "#/_components/custom/permission-denied";
import {hasPermission, isFeatureCode} from "#/_api/helpers";
import {FEATURE_CODES} from "#/_constants/features.enum";
import NotFoundComponent from "#/_components/custom/not-found-component";

interface ProtectedPageProps {
  permissionCode: PERMISSION_CODES | FEATURE_CODES | (PERMISSION_CODES | FEATURE_CODES)[]; // Support single or multiple codes
  children: React.ReactNode;
}

export default function ProtectedPage({permissionCode, children}: ProtectedPageProps) {
  const [loading, setLoading] = useState(true);
  const [isAllowed, setIsAllowed] = useState<boolean>();

  // Convert single permission code to array for consistent handling
  const requiredPermissionCodes = useMemo(
    () => (Array.isArray(permissionCode) ? permissionCode : [permissionCode]),
    [permissionCode],
  );

  useEffect(() => {
    const checkPermissions = () => {
      // Check if user has ALL required permissions
      const allowed = requiredPermissionCodes.every((code) => hasPermission(code));

      setIsAllowed(allowed);

      setLoading(false);
    };

    checkPermissions();
  }, [requiredPermissionCodes]);

  const missingRequiredFeature = requiredPermissionCodes.some(
    (code) => isFeatureCode(code) && !hasPermission(code),
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!isAllowed && missingRequiredFeature) {
    return <NotFoundComponent />;
  }

  if (!isAllowed) {
    return <PermissionDenied />;
  }

  return <>{children}</>;
}
