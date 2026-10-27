"use client";

import {useSearchParams} from "next/navigation";
import {ReactNode, useEffect, useState} from "react";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";

type ITab = {
  [key: string]: ReactNode;
};

type Props = {
  tabs: ITab;
  defaultTab: keyof Props["tabs"];
  onTabChange?: (tab: string) => void;
  contentClassName?: string;
};

export default function TabbedContent({
  tabs,
  defaultTab,
  onTabChange,
  contentClassName = "data-[state=active]:min-h-[60vh]",
}: Props) {
  const params = useSearchParams();

  const normalizeKey = (key: string) => key.toLowerCase().replaceAll(" ", "_");

  const tabKeys = Object.keys(tabs);
  const normalizedDefaultTab = normalizeKey(defaultTab.toString());

  const [activeTab, setActiveTab] = useState<string>(normalizedDefaultTab);

  useEffect(() => {
    const urlTab = params.get("tab");
    if (urlTab) {
      const normalizedUrlTab = normalizeKey(urlTab);
      const foundKey = tabKeys.find((key) => normalizeKey(key) === normalizedUrlTab);
      if (foundKey) {
        setActiveTab(normalizeKey(foundKey));
        return;
      }
    }
    setActiveTab(normalizedDefaultTab);
  }, [params]);

  useEffect(() => {
    onTabChange?.(activeTab);
  }, [activeTab, onTabChange]);

  const handleTabChange = (value: string) => {
    setActiveTab(value);
  };

  return (
    <Tabs value={activeTab} onValueChange={handleTabChange} className="relative flex-grow">
      <TabsList className="!bg-background !pl-0 !pb-4 mb-4 gap-x-6 rounded-none w-full justify-start">
        {tabKeys.map((originalKey) => {
          const normalizedKey = normalizeKey(originalKey);
          return (
            <TabsTrigger
              value={normalizedKey}
              key={normalizedKey}
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:text-primary"
            >
              <span>{originalKey}</span>
              <div className="mt-2 w-full rounded-full border-b-4 border-transparent group-data-[state=active]:border-primary" />
            </TabsTrigger>
          );
        })}
      </TabsList>

      {tabKeys.map((originalKey) => {
        const normalizedKey = normalizeKey(originalKey);
        return (
          <TabsContent
            key={normalizedKey}
            value={normalizedKey}
            className={`${contentClassName} flex flex-col !mt-0`}
          >
            {tabs[originalKey]}
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
