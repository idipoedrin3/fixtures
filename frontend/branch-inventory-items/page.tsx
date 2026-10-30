"use client";

import {useEffect, useState} from "react";
import {useSearchParams} from "next/navigation";
import InventoryItemsTable from "./_components/items.table";
import {Tabs, TabsList, TabsTrigger, TabsContent} from "@/components/ui/tabs";
import PageLayout from "#/_components/common/layouts/page-layout";
import {capitalizeEachWord} from "#/_api/helpers";

export default function Page() {
  const params = useSearchParams();
  const [tab, setTab] = useState("items");

  useEffect(() => {
    const t = params.get("tab");

    if (t && ["units", "items"].includes(t || "")) {
      setTab(t);
    }
  }, [params]);

  return (
    <PageLayout title="Branch Products & Services">
      <h1 className="text-3xl font-bold">Branch Products & Services</h1>
      <Tabs value={tab} onValueChange={setTab} className="flex-grow -mt-3">
        <TabsList className="!h-auto !bg-transparent !p-0 mb-5 gap-x-6">
          {["items", "services"].map((x) => (
            <TabsTrigger
              value={x}
              key={x}
              className="flex flex-col !px-0 !py-0 relative group data-[state=active]:!bg-transparent data-[state=active]:shadow-none"
            >
              <span>{x == "items" ? "Goods" : capitalizeEachWord(x)}</span>
              <div className="mt-2 w-full rounded-full border-b-4 border-transparent group-data-[state=active]:border-primary" />
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="items" className="data-[state=active]:min-h-[60vh] flex flex-col !mt-0">
          <InventoryItemsTable type="item" />
        </TabsContent>
        <TabsContent
          value="services"
          className="data-[state=active]:min-h-[60vh] flex flex-col !mt-0"
        >
          <InventoryItemsTable type="service" />
        </TabsContent>
      </Tabs>
    </PageLayout>
  );
}
