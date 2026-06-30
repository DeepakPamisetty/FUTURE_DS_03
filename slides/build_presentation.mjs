import fs from "node:fs/promises";
import path from "node:path";

const artifactToolPath = process.env.ARTIFACT_TOOL_PATH ?? "@oai/artifact-tool";
const { Presentation, PresentationFile } = await import(artifactToolPath);

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const OUT = path.join(ROOT, "slides", "ga_funnel_business_presentation.pptx");
const QA = "/private/tmp/codex-presentations/FUTURE_DS_03/ga-funnel/tmp/qa";

const COLORS = {
  ink: "#111111",
  muted: "#5F6368",
  panel: "#F2F3F5",
  line: "#D8DCE2",
  accent: "#E85D35",
  green: "#1B7F5A",
  gold: "#C7831E",
  white: "#FFFFFF",
};

async function readJson(file) {
  return JSON.parse(await fs.readFile(path.join(ROOT, file), "utf8"));
}

async function readCsv(file) {
  const text = await fs.readFile(path.join(ROOT, file), "utf8");
  const lines = text.trim().split(/\r?\n/);
  const headers = lines.shift().split(",");
  return lines.map((line) => {
    const values = line.split(",");
    const row = {};
    headers.forEach((header, index) => {
      const raw = values[index] ?? "";
      const numeric = Number(raw);
      row[header] = Number.isFinite(numeric) && raw.trim() !== "" ? numeric : raw;
    });
    return row;
  });
}

function pct(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function int(value) {
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function money(value) {
  return `$${Number(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: style.fontSize ?? 22,
    color: style.color ?? COLORS.ink,
    bold: style.bold ?? false,
    alignment: style.alignment ?? "left",
  };
  return shape;
}

function addRect(slide, position, fill = COLORS.panel, line = COLORS.line) {
  return slide.shapes.add({
    geometry: "rect",
    position,
    fill,
    line: { style: "solid", fill: line, width: 1 },
  });
}

function addHeader(slide, title, eyebrow = "GA CUSTOMER REVENUE FUNNEL") {
  addText(slide, eyebrow, { left: 42, top: 34, width: 520, height: 28 }, { fontSize: 14, bold: true, color: COLORS.accent });
  addText(slide, title, { left: 42, top: 72, width: 880, height: 58 }, { fontSize: 38, bold: true });
  slide.shapes.add({
    geometry: "line",
    position: { left: 42, top: 144, width: 1196, height: 0 },
    line: { style: "solid", fill: COLORS.line, width: 1 },
  });
}

function addKpi(slide, label, value, note, left, top, width = 276) {
  addRect(slide, { left, top, width, height: 130 }, COLORS.panel);
  addText(slide, label, { left: left + 18, top: top + 16, width: width - 36, height: 26 }, { fontSize: 17, bold: true, color: COLORS.muted });
  addText(slide, value, { left: left + 18, top: top + 48, width: width - 36, height: 48 }, { fontSize: 36, bold: true });
  addText(slide, note, { left: left + 18, top: top + 96, width: width - 36, height: 24 }, { fontSize: 16, color: COLORS.muted });
}

async function writeBlob(file, blob) {
  await fs.writeFile(file, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(QA, { recursive: true });

  const summary = await readJson("data/processed/summary.json");
  const recommendations = await readJson("data/processed/recommendations.json");
  const funnel = await readCsv("data/processed/funnel_metrics.csv");
  const channel = await readCsv("data/processed/channel_metrics.csv");
  const monthly = await readCsv("data/processed/monthly_metrics.csv");

  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  {
    const slide = deck.slides.add();
    slide.background.fill = COLORS.white;
    addText(slide, "Marketing Funnel Analysis", { left: 42, top: 58, width: 900, height: 72 }, { fontSize: 58, bold: true });
    addText(slide, "Google Analytics Customer Revenue Prediction", { left: 42, top: 146, width: 790, height: 42 }, { fontSize: 28, color: COLORS.muted });
    addText(slide, "Visitors -> Leads -> Customers", { left: 42, top: 224, width: 660, height: 38 }, { fontSize: 30, bold: true, color: COLORS.accent });
    addRect(slide, { left: 910, top: 54, width: 328, height: 550 }, COLORS.panel);
    addText(slide, "Executive dashboard", { left: 938, top: 92, width: 270, height: 38 }, { fontSize: 27, bold: true });
    addText(slide, `Data note: ${summary.data_source_note}`, { left: 938, top: 150, width: 250, height: 126 }, { fontSize: 18, color: COLORS.muted });
    addKpi(slide, "Visitors", int(summary.visitors), "sessions analyzed", 42, 360, 260);
    addKpi(slide, "Leads", int(summary.leads), `${pct(summary.traffic_to_lead_rate)} traffic-to-lead`, 324, 360, 260);
    addKpi(slide, "Customers", int(summary.customers), `${pct(summary.lead_to_customer_rate)} lead-to-customer`, 606, 360, 260);
    addText(slide, "Main takeaway", { left: 938, top: 326, width: 250, height: 30 }, { fontSize: 24, bold: true });
    addText(slide, `The largest drop-off is ${summary.largest_dropoff_stage.toLowerCase()}, so the highest-value optimization is converting engaged leads into buyers.`, { left: 938, top: 370, width: 250, height: 146 }, { fontSize: 20, color: COLORS.ink });
  }

  {
    const slide = deck.slides.add();
    slide.background.fill = COLORS.white;
    addHeader(slide, "Funnel conversion shows the bottleneck");
    const maxCount = Math.max(...funnel.map((d) => Number(d.count)));
    const widths = funnel.map((d) => 370 + (Number(d.count) / maxCount) * 520);
    funnel.forEach((stage, index) => {
      const width = widths[index];
      const left = 190 + (900 - width) / 2;
      const top = 210 + index * 116;
      const fill = index === 0 ? COLORS.ink : index === 1 ? COLORS.accent : COLORS.green;
      addRect(slide, { left, top, width, height: 78 }, fill, fill);
      addText(slide, stage.stage, { left: left + 24, top: top + 12, width: width - 150, height: 30 }, { fontSize: 27, bold: true, color: COLORS.white });
      addText(slide, `${pct(stage.stage_conversion)} stage conversion`, { left: left + 24, top: top + 48, width: width - 150, height: 22 }, { fontSize: 17, color: COLORS.white });
      addText(slide, int(stage.count), { left: left + width - 126, top: top + 19, width: 100, height: 38 }, { fontSize: 32, bold: true, color: COLORS.white, alignment: "right" });
    });
    addText(slide, `Drop-off from leads to customers is ${(100 - summary.lead_to_customer_rate * 100).toFixed(1)}%, making follow-up and remarketing the priority.`, { left: 190, top: 590, width: 900, height: 42 }, { fontSize: 25, bold: true });
  }

  {
    const slide = deck.slides.add();
    slide.background.fill = COLORS.white;
    addHeader(slide, "Not all traffic channels produce the same quality");
    const top = channel.slice(0, 6);
    slide.charts.add("bar", {
      position: { left: 70, top: 190, width: 560, height: 360 },
      categories: top.map((d) => d.channel),
      series: [{ name: "Visitor-to-customer (%)", values: top.map((d) => Number(d.visitor_to_customer_rate) * 100), fill: COLORS.accent }],
      hasLegend: false,
      dataLabels: { showValue: true, position: "outEnd" },
      yAxis: { majorGridlines: { style: "solid", fill: COLORS.line, width: 1 } },
    });
    slide.charts.add("bar", {
      position: { left: 700, top: 190, width: 500, height: 360 },
      categories: top.map((d) => d.channel),
      series: [{ name: "Traffic-to-lead (%)", values: top.map((d) => Number(d.traffic_to_lead_rate) * 100), fill: COLORS.green }],
      hasLegend: false,
      dataLabels: { showValue: true, position: "outEnd" },
      yAxis: { majorGridlines: { style: "solid", fill: COLORS.line, width: 1 } },
    });
    addText(slide, "Quality conversion (%)", { left: 70, top: 560, width: 300, height: 30 }, { fontSize: 22, bold: true });
    addText(slide, "Lead capture (%)", { left: 700, top: 560, width: 300, height: 30 }, { fontSize: 22, bold: true });
  }

  {
    const slide = deck.slides.add();
    slide.background.fill = COLORS.white;
    addHeader(slide, "Monthly trend provides the operating rhythm");
    const recent = monthly.slice(-12);
    slide.charts.add("line", {
      position: { left: 70, top: 188, width: 770, height: 390 },
      categories: recent.map((d) => d.month),
      series: [
        { name: "Leads", values: recent.map((d) => Number(d.leads)), fill: COLORS.accent },
        { name: "Customers", values: recent.map((d) => Number(d.customers)), fill: COLORS.green },
      ],
      hasLegend: true,
      yAxis: { majorGridlines: { style: "solid", fill: COLORS.line, width: 1 } },
    });
    addRect(slide, { left: 900, top: 190, width: 300, height: 290 }, COLORS.panel);
    addText(slide, "Operating cadence", { left: 926, top: 224, width: 240, height: 32 }, { fontSize: 25, bold: true });
    addText(slide, "Review weekly movement by channel and campaign. Treat traffic volume as a secondary metric; lead quality and customer conversion should steer budget decisions.", { left: 926, top: 280, width: 240, height: 150 }, { fontSize: 20, color: COLORS.ink });
  }

  {
    const slide = deck.slides.add();
    slide.background.fill = COLORS.white;
    addHeader(slide, "Recommended conversion improvement plan");
    recommendations.slice(0, 5).forEach((rec, index) => {
      const top = 188 + index * 86;
      addText(slide, `0${index + 1}`, { left: 72, top, width: 70, height: 42 }, { fontSize: 32, bold: true, color: COLORS.accent });
      addText(slide, rec, { left: 160, top: top + 2, width: 950, height: 62 }, { fontSize: 23, color: COLORS.ink });
      slide.shapes.add({
        geometry: "line",
        position: { left: 160, top: top + 70, width: 950, height: 0 },
        line: { style: "solid", fill: COLORS.line, width: 1 },
      });
    });
  }

  for (const [index, slide] of deck.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(QA, `${stem}.png`), await deck.export({ slide, format: "png", scale: 1 }));
    await fs.writeFile(path.join(QA, `${stem}.layout.json`), await (await slide.export({ format: "layout" })).text());
  }
  await writeBlob(path.join(QA, "deck-montage.webp"), await deck.export({ format: "webp", montage: true, scale: 1 }));
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(OUT);
  console.log(OUT);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
