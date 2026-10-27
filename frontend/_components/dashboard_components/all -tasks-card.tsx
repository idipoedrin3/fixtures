"use client";

import {useEffect, useState} from "react";
import {Icon} from "@iconify/react";
import {ChevronDown, ChevronRight, Search} from "lucide-react";
import {formatDistanceToNow} from "date-fns";

import {Badge} from "../custom/badge";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {ApprovalTask} from "#/_types/approvals.types";
import {APPROVAL_TASKS_API} from "#/_api/approvals.helpers";
import {showErrorToast} from "#/_lib/utils";
import {generateTaskLink} from "#/_constants";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import ProtectedComponent from "../custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";

interface Task {
  id: number;
  title: string;
  time: string;
  status: string;
  module: string;
}

interface AllTasksCardProps {
  tasks: Task[];
}

export default function AllTasksCard() {
  const [search, setSearch] = useState("");
  const [tasks, setTasks] = useState<ApprovalTask[]>([]);
  const router = useRouter();

  useEffect(() => {
    (async () => {
      try {
        const res = await APPROVAL_TASKS_API.fetchAll({search});

        setTasks(res.results);
      } catch (error) {
        showErrorToast({error, defaultMessage: "Failed to load approval tasks."});
      }
    })();
  }, [search]);

  return (
    <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_VIEW_ALL_TASKS}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="border-[1px] border-[#D3D3E5] w-full h-full  bg-[#F0F0F6] rounded-2xl py-3 px-4 flex justify-between items-center hover:bg-[#e6e6ec] transition"
          >
            <div className="flex gap-2 items-center">
              <Icon icon="hugeicons:task-02" className="text-[#162032] h-4 w-4" />
              <span className="text-[#162032] text-sm font-medium">All Tasks</span>
              <span className="bg-[#767E9940] px-2 rounded-2xl text-[#162032] text-sm font-medium">
                {tasks.length}
              </span>
            </div>
            <ChevronDown className="text-[#162032] h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          align="start"
          side="bottom"
          className="h-fit p-2 rounded-xl"
          style={{width: "var(--radix-dropdown-menu-trigger-width)"}}
        >
          {/* SEARCH INPUT */}
          <div className="relative px-1 py-2">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-5 text-gray-300" />
            <Input
              type="text"
              placeholder="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 text-sm"
            />
          </div>

          {/* TASK LIST */}
          <div className="overflow-y-auto w-full max-h-[300px]">
            {tasks.length > 0 ? (
              tasks.map((task) => {
                const link = generateTaskLink(task);

                return (
                  <DropdownMenuItem
                    key={task.id}
                    onClick={() => link && router.push(link)}
                    className="w-full max-w-full px-4 py-2 gap-2 hover:bg-gray-50 flex justify-between items-center cursor-pointer"
                  >
                    <div className="flex flex-col gap-1 flex-grow">
                      <div className="line-clamp-1">
                        {task.comment || `Approval needed from ${task.level_name}`}
                      </div>
                      <div className="flex items-center gap-[6px] text-xs text-gray-500">
                        <span className="text-[#4D4D51] bg-[#ececff] rounded-[5px] text-xs px-2">
                          {task.level_name}
                        </span>
                        <span className="font-bold text-md">·</span>
                        <span>
                          {formatDistanceToNow(new Date(task.updated_at), {
                            addSuffix: true,
                          })}
                        </span>
                      </div>
                    </div>
                    <div className="">
                      <Badge status={task.status} />
                    </div>
                    <span>
                      <ChevronRight className="text-gray-500 !h-4 !w-4" />
                    </span>
                  </DropdownMenuItem>
                );
              })
            ) : (
              <div className="px-4 py-3 text-center text-sm text-gray-500">No tasks found</div>
            )}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </ProtectedComponent>
  );
}
