"use client";

import {useSearchParams} from "next/navigation";
import {useSelector} from "react-redux";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import PageLayout from "#/_components/common/layouts/page-layout";
import ProtectedPage from "#/_components/custom/protected-page";
import {PERMISSION_CODES} from "#/_constants/enums";
import {Tabs, TabsList, TabsTrigger, TabsContent} from "@/components/ui/tabs";
import {LoansTable} from "./_components/loans-table";
import {LendersTable} from "./_components/lenders-table";

export default function Page() {
  const params = useSearchParams();
  const router = useRouter();
  const institution = useSelector(selectSelectedInstitution);
  const tab = params.get("tab") === "lenders" ? "lenders" : "loans";

  return (
    <PageLayout title="Loan Management">
      <h1 className="text-3xl font-bold">Loan Management</h1>
      <Tabs value={tab} onValueChange={(value) => router.replace(`/loan-mgt?tab=${value}`)}>
        <TabsList className="!h-auto !bg-transparent !p-0 mb-5 gap-x-6">
          {["loans", "lenders"].map((value) => (
            <TabsTrigger
              key={value}
              value={value}
              className="flex flex-col !px-0 !py-0 group data-[state=active]:!bg-transparent data-[state=active]:shadow-none"
            >
              <span>{value === "loans" ? "Loans" : "Lenders"}</span>
              <div className="mt-2 w-full rounded-full border-b-4 border-transparent group-data-[state=active]:border-primary" />
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="loans" className="!mt-0">
          <ProtectedPage permissionCode={PERMISSION_CODES.CAN_VIEW_LOANS}>
            <LoansTable key={institution?.id ?? "none"} />
          </ProtectedPage>
        </TabsContent>
        <TabsContent value="lenders" className="!mt-0">
          <ProtectedPage permissionCode={PERMISSION_CODES.CAN_VIEW_LENDERS}>
            <LendersTable key={institution?.id ?? "none"} />
          </ProtectedPage>
        </TabsContent>
      </Tabs>
    </PageLayout>
  );
}
