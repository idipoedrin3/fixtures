"use client";

import {Icon} from "@iconify/react";
import React, {useEffect, useState} from "react";
import WorkflowGraph from "./workflow-graph";
import DraggableFloatingContainer from "@/platform/v1/components/common/hoverable/draggable-floating-container";

interface FloatingWidgetProps {
  position?: "bottom-right" | "bottom-left";
  hideQuickAccess?: boolean;
  isOnline?: boolean;
  animateOnScroll?: boolean;
}

export const FloatingWidget: React.FC<FloatingWidgetProps> = ({
  position = "bottom-right",
  hideQuickAccess = false,
  animateOnScroll = true,
  isOnline = true,
}) => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let id: number;
    const main = document.querySelector("main");
    function monitor() {
      window.clearTimeout(id);
      id = window.setTimeout(() => {
        setShow(!!main && main.scrollTop > 100);
      });
    }
    main?.addEventListener("scroll", monitor);
    return () => main?.removeEventListener("scroll", monitor);
  });

  return (
    <>
      {/* Quick Access Button */}
      {((!hideQuickAccess && show) || !animateOnScroll) && (
        <DraggableFloatingContainer
          storageKey="quick-actions-widget"
          stackIndex={1}
          boundsMargin={24}
          snapToRightEdge
        >
          <div>
            <WorkflowGraph tooltip>
              <span
                className="cursor-pointer flex items-center justify-center w-14 h-14 rounded-full
              !bg-gradient-to-r !from-[rgba(164,35,245,1)] !to-[rgba(248,74,26,1)]
              text-white shadow-lg hover:brightness-110 transition animate-in duration-75"
              >
                <Icon icon="hugeicons:flash" width="24" height="24" />
              </span>
            </WorkflowGraph>
          </div>
        </DraggableFloatingContainer>
      )}
    </>
  );
};
