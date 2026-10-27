import {jsPDF} from "jspdf";

export interface ReceiptSection {
  type: "text" | "row" | "table" | "divider";
  text?: string;
  align?: "center" | "left";
  bold?: boolean;
  size?: number;
  label?: string;
  value?: string | null;
  columns?: {header: string; width: number; align?: "left" | "right"}[]; 
  rows?: string[][];
}

export interface ReceiptConfig {
  header: {businessName?: string; lines?: string[]}; 
  sections: ReceiptSection[];
  footerLines?: string[];
  pageWidth?: number; 
}

export const generateReceiptPDF = (config: ReceiptConfig): string => {
  const pageWidth = config.pageWidth ?? 88;
  const margin = 5;
  const contentWidth = pageWidth - margin * 2;

  // ── Height pre-pass ─────────────────────────────────
  const probe = new jsPDF({unit: "mm", format: [pageWidth, 1000]});
  probe.setFont("courier", "normal");
  probe.setFontSize(7);
  const countLines = (text: string, maxW: number) =>
    probe.splitTextToSize(text, maxW).length;

  let est = 14; 
  for (const l of config.header.lines ?? []) est += countLines(l, contentWidth) * 4;
  for (const s of config.sections) {
    if (s.type === "divider") est += 4;
    else if (s.type === "text") est += countLines(s.text ?? "", contentWidth) * ((s.size ?? 7) * 0.55);
    else if (s.type === "row") est += countLines(s.value ?? "", contentWidth * 0.55) * 4;
    else if (s.type === "table") {
      est += 8; // header rows
      for (const row of s.rows ?? []) est += Math.max(...row.map((c, i) => countLines(c, contentWidth * (s.columns?.[i]?.width ?? 0.25)))) * 4;
    }
  }
  est += (config.footerLines?.length ?? 0) * 4 + 10;
  const height = Math.max(50, est);

  // ── Render ──────────────────────────────────────────
  const doc = new jsPDF({
    unit: "mm",
    format: [pageWidth, height],
    orientation: height >= pageWidth ? "portrait" : "landscape",
    });
  const center = pageWidth / 2;
  let y = 8;

  const dashedLine = () => {
    doc.setLineDashPattern([1, 1], 0);
    doc.setDrawColor("#000000");
    doc.line(margin, y, pageWidth - margin, y);
    doc.setLineDashPattern([], 0);
    y += 4;
  };

  const centerText = (text: string, size = 7, bold = false) => {
    doc.setFont("courier", bold ? "bold" : "normal");
    doc.setFontSize(size);
    for (const l of doc.splitTextToSize(text, contentWidth) as string[]) {
      doc.text(l, center, y, {align: "center"});
      y += size * 0.55;
    }
  };

  // Header
  if (config.header.businessName) centerText(config.header.businessName.toUpperCase(), 9, true);
  for (const l of config.header.lines ?? []) centerText(l);
  y += 1;
  dashedLine();

  // Sections
  for (const s of config.sections) {
    if (s.type === "divider") {
      y += 1;
      dashedLine();
    } else if (s.type === "text") {
      if (s.align === "left") {
        doc.setFont("courier", s.bold ? "bold" : "normal");
        doc.setFontSize(s.size ?? 7);
        for (const l of doc.splitTextToSize(s.text ?? "", contentWidth) as string[]) {
          doc.text(l, margin, y);
          y += (s.size ?? 7) * 0.55;
        }
      } else {
        centerText(s.text ?? "", s.size ?? 7, s.bold ?? false);
      }
    } else if (s.type === "row") {
      doc.setFontSize(s.size ?? 7);
      doc.setFont("courier", "normal");
      doc.text(s.label ?? "", margin, y);
      doc.setFont("courier", s.bold ? "bold" : "normal");
      const valueLines: string[] = doc.splitTextToSize(s.value ?? "", contentWidth * 0.55);
      doc.text(valueLines[0] ?? "", pageWidth - margin, y, {align: "right"});
      y += (s.size ?? 7) * 0.6;
      for (const extra of valueLines.slice(1)) {
        doc.text(extra, pageWidth - margin, y, {align: "right"});
        y += (s.size ?? 7) * 0.6;
      }
    } else if (s.type === "table" && s.columns) {
      // column x anchors from cumulative widths
      const anchors: {x: number; align: "left" | "right"}[] = [];
      let acc = 0;
      for (const col of s.columns) {
        const alignRight = col.align === "right";
        anchors.push({
          x: alignRight ? margin + (acc + col.width) * contentWidth : margin + acc * contentWidth,
          align: alignRight ? "right" : "left",
        });
        acc += col.width;
      }
      doc.setFont("courier", "bold");
      doc.setFontSize(7);
      s.columns.forEach((col, i) =>
        doc.text(col.header, anchors[i].x, y, {align: anchors[i].align}),
      );
      y += 4;
      doc.setFont("courier", "normal");
      for (const row of s.rows ?? []) {
        let extraLines: string[] = [];
        row.forEach((cell, i) => {
          const cellLines: string[] = doc.splitTextToSize(cell, contentWidth * s.columns![i].width);
          doc.text(cellLines[0] ?? "", anchors[i].x, y, {align: anchors[i].align});
          if (i === 0) extraLines = cellLines.slice(1); // only wrap first (name) column
        });
        y += 4;
        for (const extra of extraLines) {
          doc.text(extra, anchors[0].x, y, {align: anchors[0].align});
          y += 4;
        }
      }
    }
  }

  // Footer
  y += 1;
  dashedLine();
  for (const l of config.footerLines ?? []) centerText(l);

  doc.autoPrint();
  return doc.output("bloburl").toString();
};