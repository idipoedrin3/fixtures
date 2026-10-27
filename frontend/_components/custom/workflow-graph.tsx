"use client";

import {WORKFLOW_API} from "#/_api/services/user.service";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import {cn} from "@/lib/utils";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {TooltipArrow} from "@radix-ui/react-tooltip";
import React, {useEffect, useRef, useState} from "react";
import {useSelector} from "react-redux";
import {toast} from "sonner";
import QuickAccessChart from "./quick-access-chart";

async function fetchWorkflowGraphData(theme?: string) {
  try {
    const items = await WORKFLOW_API.fetchSectionItems();
    const data = toMermaidFlowchartWithSections(items);
    return data;
  } catch (error) {
    toast.error("Failed to load workflow data.");
    return "";
  }
}

type Section = {
  id: number;
  name: string;
};

type Relation = {
  id: number;
  code: string;
  name: string;
  section: Section;
};

type Item = {
  id: number;
  code: string;
  name: string;
  section: Section;
  parents?: Relation[];
  children?: Relation[];
};

export function toMermaidFlowchartWithSections(data: Item[], theme = "#0CA0F5"): string {
  const sections = new Map<number, {name: string; nodes: Set<string>}>();
  const nodeLabels = new Map<string, string>();
  const edges = new Set<string>();
  const styles: string[] = [];

  const nodeId = (code: string) => code.replace(/[^a-zA-Z0-9_]/g, "_");
  const sectionKey = (id: number) => `section_${id}`;

  // Helper to register a node under its section
  const registerNode = (code: string, name: string, section: Section) => {
    const id = nodeId(code);

    if (!nodeLabels.has(id)) {
      nodeLabels.set(id, `${id}[${name}]`);
      nodeLabels.set(
        id,
        `${id}("<img src='https://api.iconify.design/hugeicons/${"scroll"}.svg?color=${theme.replace("#", "%23")}' style='width:24px;height:24px;display:inline;margin-right:1rem;color:blue' />${name}<span class="node-data" data-node="${name}"></span>")`,
      );
      styles.push(`style ${nodeId(id)} fill:#f8f9fa,stroke:#b8c2cc`);
    }

    if (!sections.has(section.id)) {
      sections.set(section.id, {
        name: section.name,
        nodes: new Set(),
      });
    }

    sections.get(section.id)!.nodes.add(id);
    return id;
  };

  // Walk full graph
  for (const item of data) {
    const currentId = registerNode(item.code, item.name, item.section);

    // Parents → item
    for (const parent of item.parents ?? []) {
      const parentId = registerNode(parent.code, parent.name, parent.section);
      edges.add(`${parentId} --> ${currentId}`);
    }

    // Item → children
    for (const child of item.children ?? []) {
      const childId = registerNode(child.code, child.name, child.section);
      edges.add(`${currentId} --> ${childId}`);
    }
  }

  const lines: string[] = [];

  lines.push(`flowchart TB`);
  lines.push(``);

  // Render section subgraphs
  for (const [id, section] of sections) {
    lines.push(
      `subgraph SECTION_${sectionKey(id)}["<p style='background-color:#F7F7FB;border-radius:8px;padding:8px 12px;'><b>${section.name}</b></p>"]`,
    );
    styles.push(`style SECTION_${sectionKey(id)} fill:#fff,stroke:#999,stroke-dasharray: 5 5`);

    for (const node of section.nodes) {
      lines.push(`  ${nodeLabels.get(node)}`);
    }
    lines.push(`end`);
    lines.push(``);
  }

  return lines.join("\n") + Array.from(edges).join("\n") + `\n\n` + styles.join("\n");
}

type Props = {
  title?: string;
  children?: React.ReactNode;
  tooltip?: boolean;
};

export default function WorkflowGraph({title = "Quick Access", tooltip = false, children}: Props) {
  const selectedInstitution = useSelector(selectSelectedInstitution);

  const [open, setOpen] = useState(false);
  const pointerStartRef = useRef<{x: number; y: number} | null>(null);
  const suppressClickRef = useRef(false);

  const handlePointerDown = (event: React.PointerEvent<HTMLElement>) => {
    pointerStartRef.current = {x: event.clientX, y: event.clientY};
    suppressClickRef.current = false;
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLElement>) => {
    if (!pointerStartRef.current) return;

    const deltaX = event.clientX - pointerStartRef.current.x;
    const deltaY = event.clientY - pointerStartRef.current.y;
    suppressClickRef.current = deltaX * deltaX + deltaY * deltaY > 36;
  };

  const handlePointerUp = () => {
    if (suppressClickRef.current) {
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
  };

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    if (suppressClickRef.current) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    setOpen(true);
  };

  const [code, setCode] = useState(`flowchart LR\n  A[Loading data...]`);

  useEffect(() => {
    if (!open) return;
    fetchWorkflowGraphData(selectedInstitution?.theme_color ?? undefined)
      .then((data) => setCode(data))
      .catch(() => setCode(`flowchart LR\n  A[Not Found.]`));
  }, [open]);

  function nodeClickListener(event: MessageEvent<any>) {
    const {type, payload} = event.data || {};
    if (type === "NODE_CLICK") {
      console.log(type, payload);
    }
  }

  useEffect(() => {
    window.addEventListener("message", nodeClickListener);

    return () => window.removeEventListener("message", nodeClickListener);
  });

  return (
    <>
      {tooltip ? (
        <Tooltip delayDuration={0}>
          <TooltipTrigger
            asChild
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onClick={handleClick}
          >
            {children}
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Quick Access</p>
            <TooltipArrow />
          </TooltipContent>
        </Tooltip>
      ) : null}
      <Dialog open={open} onOpenChange={setOpen}>
        {!tooltip ? <DialogTrigger asChild>{children}</DialogTrigger> : null}
        <DialogContent className="max-w-[80vw] h-[80vh] p-0 flex flex-col overflow-hidden">
          <DialogHeader className="px-6 pt-4">
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className={cn("relative flex-1 overflow-hidden select-none")}>
            <QuickAccessChart code={code} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
