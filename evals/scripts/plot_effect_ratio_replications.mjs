#!/usr/bin/env node
/** Generate the effect-ratio comparison figure without a Python environment. */

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const input = resolve(root, "benchmark/effect_ratio_comparisons.csv");
const output = resolve(root, "../aeris-genai4health/figures/effect_calibration.svg");

function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === '"' && text[i + 1] === '"' && quoted) { field += '"'; i += 1; }
    else if (char === '"') quoted = !quoted;
    else if (char === "," && !quoted) { row.push(field); field = ""; }
    else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[i + 1] === "\n") i += 1;
      row.push(field); if (row.length > 1) rows.push(row); row = []; field = "";
    } else field += char;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const [header, ...body] = rows;
  return body.map(values => Object.fromEntries(header.map((key, i) => [key, values[i] || ""])));
}

const rows = parseCsv(readFileSync(input, "utf8")).filter(
  row => row.included_primary_meta === "true",
);
const noEvidenceStudies = new Set([
  "Brazil cancer mortality",
  "Northern Italy COVID-19",
  "OECD COVID-19",
]);
const width = 720, height = 470, left = 82, top = 38, plotW = 570, plotH = 360;
const xLow = 0.94, xHigh = 1.9, yLow = 0.6, yHigh = 1.9;
const xLogLow = Math.log2(xLow), xLogRange = Math.log2(xHigh) - xLogLow;
const yLogLow = Math.log2(yLow), yLogRange = Math.log2(yHigh) - yLogLow;
const x = value => left + ((Math.log2(value) - xLogLow) / xLogRange) * plotW;
const y = value => top + plotH - ((Math.log2(value) - yLogLow) / yLogRange) * plotH;
const esc = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const xTicks = [0.95, 1.0, 1.05, 1.1, 1.25, 1.5, 1.75];
const yTicks = [0.6, 0.75, 0.95, 1.0, 1.05, 1.1, 1.25, 1.5, 1.75];
const error = (value, lowKey, highKey, horizontal) => {
  const lo = Number(value[lowKey]), hi = Number(value[highKey]);
  if (!lo || !hi) return "";
  const a = horizontal ? x(lo) : y(lo), b = horizontal ? x(hi) : y(hi);
  const fixed = horizontal ? y(Number(value.aeris_ratio)) : x(Number(value.published_ratio));
  return horizontal
    ? `<line x1="${a}" y1="${fixed}" x2="${b}" y2="${fixed}" class="error"/><line x1="${a}" y1="${fixed - 3}" x2="${a}" y2="${fixed + 3}" class="error"/><line x1="${b}" y1="${fixed - 3}" x2="${b}" y2="${fixed + 3}" class="error"/>`
    : `<line x1="${fixed}" y1="${a}" x2="${fixed}" y2="${b}" class="error"/><line x1="${fixed - 3}" y1="${a}" x2="${fixed + 3}" y2="${a}" class="error"/><line x1="${fixed - 3}" y1="${b}" x2="${fixed + 3}" y2="${b}" class="error"/>`;
};
let svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
<style>
  text { font-family: Arial, Helvetica, sans-serif; fill: #1c1c1c; }
  .axis { stroke: #333; stroke-width: 1; } .grid { stroke: #d8d8d8; stroke-width: 1; }
  .tick { font-size: 11px; fill: #444; } .legend { font-size: 12px; fill: #333; }
  .error { stroke: #5f6368; stroke-width: 1; }
</style><rect width="100%" height="100%" fill="white"/>`;
for (const tick of xTicks) {
  const px = x(tick);
  svg += `<line x1="${px}" y1="${top}" x2="${px}" y2="${top + plotH}" class="grid"/><text x="${px}" y="${top + plotH + 19}" text-anchor="middle" class="tick">${tick}</text>`;
}
for (const tick of yTicks) {
  const py = y(tick);
  svg += `<line x1="${left}" y1="${py}" x2="${left + plotW}" y2="${py}" class="grid"/><text x="${left - 8}" y="${py + 4}" text-anchor="end" class="tick">${tick}</text>`;
}
svg += `<line x1="${left}" y1="${top + plotH}" x2="${left + plotW}" y2="${top + plotH}" class="axis"/><line x1="${left}" y1="${top}" x2="${left}" y2="${top + plotH}" class="axis"/>`;
svg += `<line x1="${x(xLow)}" y1="${y(xLow)}" x2="${x(xHigh)}" y2="${y(xHigh)}" stroke="#666" stroke-width="1.2" stroke-dasharray="5 4"/>`;
rows.forEach(row => {
  const px = x(Number(row.published_ratio)), py = y(Number(row.aeris_ratio));
  const noEvidence = noEvidenceStudies.has(row.study);
  const fill = noEvidence ? "#9aa0a6" : "#1a73e8";
  const stroke = noEvidence ? "#5f6368" : "#174ea6";
  svg += error(row, "published_ci_low", "published_ci_high", true);
  svg += error(row, "aeris_ci_low", "aeris_ci_high", false);
  svg += `<circle cx="${px}" cy="${py}" r="6" fill="${fill}" stroke="${stroke}" stroke-width="1.2"/>`;
});
svg += `<text x="${left + plotW / 2}" y="${height - 14}" text-anchor="middle" font-size="13">Published OR or RR (log2 scale)</text>`;
svg += `<text x="18" y="${top + plotH / 2}" text-anchor="middle" font-size="13" transform="rotate(-90 18 ${top + plotH / 2})">AERIS OR or RR (log2 scale)</text>`;
svg += `<circle cx="${left + 4}" cy="18" r="5" fill="#1a73e8" stroke="#174ea6"/><text x="${left + 16}" y="22" class="legend">Published positive association</text>`;
svg += `<circle cx="${left + 258}" cy="18" r="5" fill="#9aa0a6" stroke="#5f6368"/><text x="${left + 270}" y="22" class="legend">Published null or no evidence</text>`;
svg += `</svg>`;
writeFileSync(output, svg);
