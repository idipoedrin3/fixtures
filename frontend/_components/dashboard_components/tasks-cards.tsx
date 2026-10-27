"use client";

import {Icon} from "@iconify/react";
import {useState, useEffect} from "react";

import {cn} from "@/lib/utils";
import {APPROVAL_TASKS_API} from "#/_api/approvals.helpers";
import Link from "@/platform/v1/components/link";
import ProtectedComponent from "../custom/protected-component";
import { PERMISSION_CODES } from "#/_constants/enums";

export interface Task {
  id: number;
  title: string;
  time: string;
  status: string;
  module: string;
}

interface TasksCardsProps {
  className?: string;
}

export function TasksCards({className}: TasksCardsProps) {
  const [metrics, setMetrics] = useState<{
    incoming: {count: number};
    open: {count: number};
    critical: {count: number};
    expired: {count: number};
    outgoing: {count: number};
  }>();

  useEffect(() => {
    (async () => {
      const data = await APPROVAL_TASKS_API.fetchDashboard();

      setMetrics(data);
    })();
  }, []);

  return (
    <div className={cn("flex flex-col lg:flex-row gap-4 cursor-pointer", className)}>
      {/* Critical Tasks Card */}
     <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_VIEW_CRITICAL_TASKS}>
      <Link
        href={`/tasks/?type=critical`}
        className="flex-1 bg-red-100 rounded-2xl py-3 px-4 flex justify-between items-center"
      >
        <div className="flex items-center">
          <span className="text-xl font-bold text-red-500 mr-2">
            {metrics?.critical?.count ?? 0}
          </span>
          <span className="text-red-500 text-sm">Critical Tasks</span>
        </div>
        <Icon icon="hugeicons:arrow-right-02" className="text-red-500 h-4 w-4" />
      </Link>
      </ProtectedComponent>

      {/* Other cards */}
     <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_VIEW_EXPIRED_TASKS}>
      <Link
        href={`/tasks/?type=expired`}
        className="flex-1 bg-blue-100 rounded-2xl py-3 px-4 flex justify-between items-center"
      >
        <div className="flex items-center">
          <span className="text-xl font-bold text-blue-500 mr-2">
            {metrics?.expired?.count ?? 0}
          </span>
          <span className="text-blue-500 text-sm">Expired Tasks</span>
        </div>
        <Icon icon="hugeicons:arrow-right-02" className="text-blue-500 h-4 w-4" />
      </Link>
    </ProtectedComponent>

     <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_VIEW_OPEN_TASKS}>
      <Link
        href={`/tasks/?type=open`}
        className="flex-1 bg-purple-100 rounded-2xl py-3 px-4 flex justify-between items-center"
      >
        <div className="flex items-center">
          <span className="text-xl font-bold text-purple-500 mr-2">
            {metrics?.open?.count ?? 0}
          </span>
          <span className="text-purple-500 text-sm">Open tasks</span>
        </div>
        <Icon icon="hugeicons:arrow-right-02" className="text-purple-500 h-4 w-4" />
      </Link>
    </ProtectedComponent>
     <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_VIEW_WAITING_TASKS}>
  
      <Link
        href={`/tasks/?type=incoming`}
        className="flex-1 bg-green-100 rounded-2xl py-3 px-4 flex justify-between items-center"
      >
        <div className="flex items-center">
          <span className="text-xl font-bold text-green-500 mr-2">
            {metrics?.incoming?.count ?? 0}
          </span>
          <span className="text-green-500 text-sm">Waiting Tasks</span>
        </div>
        <Icon icon="hugeicons:arrow-right-02" className="text-green-500 h-4 w-4" />
      </Link>
    </ProtectedComponent>
    </div>
  );
}
