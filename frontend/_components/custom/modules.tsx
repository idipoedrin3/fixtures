"use client";

import {useState} from "react";
import {Blocks} from "lucide-react";
// Using Blocks icon for the dropdown trigger

import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function Modules() {
  const [isHovered, setIsHovered] = useState(false);
  const router = useRouter();

  // Main modules data with icons matching the reference image
  const modules = [
    {
      id: "hr",
      name: "HR",
      link: "/hrms/dashboard",
      icon: (
        <svg
          fill="none"
          height="24"
          viewBox="0 0 24 24"
          width="24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="10" cy="8" fill="none" r="4" stroke="currentColor" strokeWidth="1.5" />
          <path
            d="M6 19C6 16.2 7.8 14 10 14C12.2 14 14 16.2 14 19"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <path
            d="M14 13C14.8 12.5 15.9 12 17 12C19.2 12 21 13.8 21 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <circle cx="17" cy="7" fill="none" r="2" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      ),
    },
    {
      id: "accounting",
      name: "Accounting",
      link: "/accounting/dashboard",
      icon: (
        <svg
          fill="none"
          height="24"
          viewBox="0 0 24 24"
          width="24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect
            fill="none"
            height="8"
            stroke="currentColor"
            strokeWidth="1.5"
            width="4"
            x="6"
            y="12"
          />
          <rect
            fill="none"
            height="12"
            stroke="currentColor"
            strokeWidth="1.5"
            width="4"
            x="14"
            y="8"
          />
          <path d="M16 4L18 3" stroke="currentColor" strokeWidth="1.5" />
          <path d="M18 3L20 4" stroke="currentColor" strokeWidth="1.5" />
          <path d="M17 3H19" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      ),
    },
    {
      id: "crm",
      name: "CRM",
      link: "/crm/dashboard",
      icon: (
        <svg
          fill="none"
          height="24"
          viewBox="0 0 24 24"
          width="24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="10" cy="8" fill="none" r="4" stroke="currentColor" strokeWidth="1.5" />
          <path
            d="M6 19C6 16.2 7.8 14 10 14C12.2 14 14 16.2 14 19"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <path
            d="M17 11C17 9.3 18.3 8 20 8C21.7 8 23 9.3 23 11C23 12.7 21.7 14 20 14C19.4 14 18.9 13.8 18.4 13.5L16 16V18H18L19.2 16.8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
        </svg>
      ),
    },
  ];

  const handleModuleClick = (link: string) => {
    router.push(link);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="bg-gray-100 rounded-full flex items-center justify-center relative hover:bg-gray-200 w-8 h-8"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <Blocks className="h-5 w-5 text-gray-600" />

          <span
            className={`text-gray-100 px-2 py-1 rounded-sm z-10 bg-gray-600 text-xs font-medium absolute -top-6 left-1/2 transform -translate-x-1/2 pointer-events-none whitespace-nowrap ${
              isHovered ? "opacity-100" : "opacity-0"
            }`}
          >
            Modules
          </span>

          <span className="sr-only">Modules</span>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="p-0 border-0 shadow-lg" sideOffset={5}>
        {/* This is the card that exactly matches your reference image */}
        <div className="bg-white p-4 rounded-3xl shadow-md w-64">
          <div className="flex justify-between items-center">
            {modules.map((module) => (
              <div
                role="module-click-handler"
                key={module.id}
                className="flex flex-col items-center cursor-pointer"
                onClick={() => handleModuleClick(module.link)}
              >
                <div className="rounded-full border border-gray-200 p-2 w-12 h-12 flex items-center justify-center mb-2">
                  <div className="scale-75">{module.icon}</div>
                </div>
                <h3 className="text-sm font-bold text-gray-900">{module.name}</h3>
              </div>
            ))}
          </div>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
