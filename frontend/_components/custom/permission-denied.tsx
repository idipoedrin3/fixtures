"use client";

import {Button} from "@/components/ui/button";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";

export default function PermissionDenied() {
  const router = useRouter();

  return (
    <div className="flex flex-col items-center justify-center h-screen text-center px-4">
      <h1 className="text-3xl font-bold text-red-600 mb-4">Access Denied</h1>
      <p className="text-gray-700 mb-6">
        You do not have permission to view this page.
        <br />
        Please contact the administrator for access.
      </p>

      <div className="flex gap-3">
        <Button className="px-4 py-2" variant="outline" onClick={() => router.back()}>
          Go Back
        </Button>

        <Button className="px-4 py-2" onClick={() => window.location.reload()}>
          Refresh
        </Button>
      </div>
    </div>
  );
}
