"use client";

import {PERMISSION_CODES} from "#/_constants/enums";
import {hasPermission} from "#/_api/helpers";
import {FEATURE_CODES} from "#/_constants/features.enum";

type PermissionCode = FEATURE_CODES | PERMISSION_CODES | string;

interface ProtectedComponentProps {
  permissionCode: PermissionCode | PermissionCode[];
  children: React.ReactNode;
}

export default function ProtectedComponent({permissionCode, children}: ProtectedComponentProps) {
  const codes = Array.isArray(permissionCode) ? permissionCode : [permissionCode];

  const isAllowed = codes.length > 0 && codes.every((perm) => hasPermission(perm || ""));

  if (!isAllowed) return null;

  return <>{children}</>;
}
