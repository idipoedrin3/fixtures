"use client";

import {useSearchParams, useRouter} from "next/navigation";
import {useState, useEffect} from "react";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {TabsContent} from "@/components/ui/tabs";
import PageLayout from "#/_components/common/layouts/page-layout";
import InvoicesPage from "./_components/invoice-page";
import RecurringInvoicesPage from "./_components/recurring_invoices_page";

export default function InvoicesMainPage() {
  const params = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState("list");

  useEffect(() => {
    const urlTab = params.get("tab");
    if (urlTab === "recurring") {
      setTab("recurring");
    } else {
      setTab("list");
    }
  }, [params]);

  const handleTabChange = (value: string) => {
    setTab(value);
    router.push(`/invoices?tab=${value}`);
  };

  return (
    <PageLayout title="Invoices">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold">Invoices</h1>
        </div>
      </div>

      <Tabs onValueChange={handleTabChange} value={tab} className="flex-grow">
        <TabsList className="!bg-background !pl-0 !pb-4 gap-x-6 w-full justify-start rounded-none">
          <TabsTrigger
            value="list"
            className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
          >
            <span>List / History</span>
            <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
          </TabsTrigger>

          <TabsTrigger
            value="recurring"
            className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
          >
            <span>Recurring Invoices</span>
            <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="mt-2">
          <InvoicesPage />
        </TabsContent>

        <TabsContent value="recurring" className="mt-2">
          <RecurringInvoicesPage />
        </TabsContent>
      </Tabs>
    </PageLayout>
  );
}
