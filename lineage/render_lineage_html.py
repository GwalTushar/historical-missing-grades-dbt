"""
Render extracted dbt column lineage as an enhanced interactive HTML report.

Input:
- target/lineage_output.json

Output:
- target/lineage_report.html
"""

from __future__ import annotations

import html
import json
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINEAGE_PATH = PROJECT_ROOT / "target" / "lineage_output.json"
HTML_OUTPUT = PROJECT_ROOT / "target" / "lineage_report.html"


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


# ── HTML template (no f-string – uses ##PLACEHOLDER## substitution) ───────────
_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ShopStream · Column Lineage Explorer</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:       #f7f8fb;
      --surface:  #ffffff;
      --surface2: #f2f4f8;
      --border:   #dde3ee;
      --ink:      #1d2330;
      --muted:    #5e6a7d;
      --accent:   #ff694b;
      --accent-soft: #fff0ec;
      --bronze:   #b55e1f;
      --silver:   #3d6fd6;
      --intermed: #6f55c9;
      --gold:     #bb8b18;
      --direct:   #198754;
      --derived:  #b07c00;
      --agg:      #d64545;
      --cast:     #2f7fd9;
      --font: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
      --mono: "Cascadia Code", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    }
    body {
      font-family: var(--font);
      background: var(--bg);
      color: var(--ink);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* ── Top bar ── */
    .topbar {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 10px 18px;
      min-height: 56px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      box-shadow: 0 2px 8px rgba(25, 33, 50, 0.04);
    }
    .logo {
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
      display: flex;
      align-items: center;
      gap: 7px;
      white-space: nowrap;
    }
    .logo-icon { color: var(--accent); }
    .stat-pills { display: flex; gap: 6px; flex: 1; }
    .pill {
      padding: 2px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--muted);
    }
    .tabs { display: flex; gap: 2px; }
    .tab {
      padding: 5px 13px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      color: var(--muted);
      border: 1px solid transparent;
      background: none;
    }
    .tab:hover { color: var(--ink); background: #f7f9fd; }
    .tab.active {
      color: var(--accent);
      background: var(--accent-soft);
      border-color: #ffd2c7;
      font-weight: 700;
    }
    .search-wrap { position: relative; }
    .search-icon {
      position: absolute; left: 8px; top: 50%;
      transform: translateY(-50%);
      color: var(--muted); pointer-events: none;
    }
    #global-search {
      padding: 5px 10px 5px 28px;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--ink);
      font-size: 12px;
      width: 190px;
    }
    #global-search::placeholder { color: var(--muted); }
    #global-search:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(255, 105, 75, 0.18);
    }

    /* ── App body ── */
    .app-body { flex: 1; display: flex; overflow: hidden; }

    /* ── Graph tab ── */
    #tab-graph { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .lane-header {
      display: flex;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      background: var(--surface);
    }
    .lane-head {
      flex: 1;
      padding: 7px 15px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .07em;
      border-right: 1px solid var(--border);
    }
    .lane-head:last-child { border-right: none; }
    .lane-head.bronze  { color: var(--bronze); }
    .lane-head.silver  { color: var(--silver); }
    .lane-head.intermed { color: var(--intermed); }
    .lane-head.gold    { color: var(--gold); }
    .graph-scroll {
      flex: 1;
      overflow: auto;
      position: relative;
      background:
        radial-gradient(circle at 20% 10%, rgba(255, 105, 75, 0.08), transparent 34%),
        radial-gradient(circle at 80% 0%, rgba(61, 111, 214, 0.08), transparent 28%),
        #fbfcff;
    }
    .graph-canvas {
      display: flex;
      min-height: 100%;
      min-width: 1060px;
      position: relative;
    }
    .svg-overlay {
      position: absolute;
      top: 0; left: 0;
      pointer-events: none;
      overflow: visible;
    }
    .lane {
      flex: 1;
      padding: 18px 12px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      border-right: 1px solid var(--border);
    }
    .lane:nth-child(2) { background: rgba(181, 94, 31, 0.04); }
    .lane:nth-child(3) { background: rgba(61, 111, 214, 0.035); }
    .lane:nth-child(4) { background: rgba(111, 85, 201, 0.03); }
    .lane:nth-child(5) { background: rgba(187, 139, 24, 0.03); }
    .lane:last-child { border-right: none; }

    /* ── Node cards ── */
    .node-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      transition: box-shadow .15s, transform .15s;
      box-shadow: 0 3px 10px rgba(16, 24, 40, 0.05);
    }
    .node-card:hover { transform: translateY(-1px); }
    .node-card.hl { box-shadow: 0 0 0 2px rgba(255, 105, 75, 0.45), 0 10px 24px rgba(255, 105, 75, 0.18); }
    .node-header {
      padding: 8px 12px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 7px;
      border-bottom: 1px solid var(--border);
    }
    .nd { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .node-header.bronze  { color: var(--bronze);  background: rgba(181, 94, 31, 0.1); }
    .node-header.bronze  .nd { background: var(--bronze); }
    .node-header.silver  { color: var(--silver);  background: rgba(61, 111, 214, 0.1); }
    .node-header.silver  .nd { background: var(--silver); }
    .node-header.intermed { color: var(--intermed); background: rgba(111, 85, 201, 0.1); }
    .node-header.intermed .nd { background: var(--intermed); }
    .node-header.gold    { color: var(--gold);    background: rgba(187, 139, 24, 0.1); }
    .node-header.gold    .nd { background: var(--gold); }

    .col-list { padding: 4px 0; }
    .col-row {
      padding: 5px 12px;
      font-size: 12px;
      font-family: var(--mono);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      transition: background .1s;
      color: var(--muted);
    }
    .col-row:hover { background: var(--surface2); color: var(--ink); }
    .col-row.active {
      background: var(--accent-soft);
      color: #cc4a30;
      border-left: 3px solid var(--accent);
      padding-left: 9px;
    }
    .col-row.faded { opacity: .2; }
    .col-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: .5; flex-shrink: 0; }

    /* ── Legend ── */
    .legend {
      display: flex;
      gap: 16px;
      align-items: center;
      padding: 7px 18px;
      background: var(--surface);
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }
    .legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--muted); }
    .legend-line { width: 22px; height: 2px; border-radius: 2px; }
    .legend-hint { margin-left: auto; font-size: 11px; color: var(--muted); font-style: italic; }

    /* ── Table tab ── */
    #tab-table { flex: 1; display: none; flex-direction: column; overflow: hidden; }
    .tbl-toolbar {
      padding: 9px 18px;
      display: flex;
      gap: 8px;
      align-items: center;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      flex-shrink: 0;
    }
    .tbl-label { font-size: 12px; color: var(--muted); }
    .filter-sel {
      padding: 4px 9px;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--ink);
      font-size: 12px;
    }
    .filter-sel:focus { outline: none; border-color: var(--accent); }
    .row-count { margin-left: auto; font-size: 11px; color: var(--muted); }
    .tbl-wrap { flex: 1; overflow: auto; }
    .data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .data-table th {
      position: sticky; top: 0;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 8px 13px;
      text-align: left;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--muted);
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }
    .data-table th:hover { color: var(--ink); }
    .sort-ic { margin-left: 3px; opacity: .4; }
    .data-table th.sorted .sort-ic { opacity: 1; color: var(--accent); }
    .data-table td {
      padding: 7px 13px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
      font-family: var(--mono);
      color: var(--muted);
    }
    .data-table tr:hover td { background: #f8faff; }
    .data-table td.hi { color: var(--ink); }
    .badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 700;
      font-family: var(--font);
      text-transform: uppercase;
    }
    .badge.direct    { background: rgba(25,135,84,.12);   color: var(--direct); }
    .badge.derived   { background: rgba(176,124,0,.12);   color: var(--derived); }
    .badge.aggregate { background: rgba(214,69,69,.12);   color: var(--agg); }
    .badge.cast      { background: rgba(47,127,217,.12);  color: var(--cast); }

    /* ── Detail panel ── */
    #detail-panel {
      width: 300px;
      min-width: 300px;
      background: var(--surface);
      border-left: 1px solid var(--border);
      display: none;
      flex-direction: column;
      overflow: hidden;
    }
    #detail-panel.open { display: flex; }
    .panel-hdr {
      padding: 11px 14px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
      font-weight: 600;
    }
    .panel-close { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 18px; line-height: 1; }
    .panel-close:hover { color: var(--ink); }
    .panel-body { flex: 1; overflow: auto; padding: 14px; }
    .panel-sec { margin-bottom: 18px; }
    .panel-lbl {
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .07em; color: var(--muted); margin-bottom: 7px;
    }
    .panel-mono {
      font-family: var(--mono); font-size: 12px;
      background: var(--surface2); border: 1px solid var(--border);
      border-radius: 6px; padding: 7px 10px; color: var(--ink); word-break: break-all;
    }
    .edge-item {
      padding: 8px 10px; background: var(--surface2);
      border: 1px solid var(--border); border-radius: 6px; margin-bottom: 7px;
    }
    .edge-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 6px; }
    .edge-name { font-family: var(--mono); font-size: 11px; color: var(--muted); line-height: 1.4; }
    .edge-name b { color: var(--ink); }
    .edge-expr {
      font-family: var(--mono); font-size: 11px; color: var(--ink);
      margin-top: 5px; background: #f7f9fd;
      border-radius: 4px; padding: 3px 6px;
    }
    .chain-node {
      display: inline-block; margin: 2px 3px;
      font-family: var(--mono); font-size: 11px;
      background: var(--surface2); border: 1px solid var(--border);
      border-radius: 4px; padding: 2px 6px; color: var(--ink);
    }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #adb8ca; }

    @media (max-width: 1120px) {
      .topbar {
        flex-wrap: wrap;
        align-items: center;
      }
      .stat-pills {
        order: 3;
        width: 100%;
        flex-wrap: wrap;
      }
      .search-wrap {
        margin-left: auto;
      }
      #global-search {
        width: 160px;
      }
    }

    @media (max-width: 780px) {
      .app-body {
        flex-direction: column;
      }
      #detail-panel {
        width: 100%;
        min-width: 100%;
        border-left: 0;
        border-top: 1px solid var(--border);
        max-height: 45vh;
      }
    }
  </style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <div class="logo">
    <svg class="logo-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round">
      <polygon points="12 2 2 7 12 12 22 7"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
    </svg>
    dbt Explorer &middot; ShopStream
  </div>
  <div class="stat-pills">
    <span class="pill">##PROJECT##</span>
    <span class="pill">##N_MODELS## models</span>
    <span class="pill">##N_SOURCES## sources</span>
    <span class="pill">##N_EDGES## column edges</span>
  </div>
  <div class="tabs">
    <button class="tab active" id="btn-graph" onclick="showTab('graph')">&#9432; Graph</button>
    <button class="tab"        id="btn-table" onclick="showTab('table')">&#8801; Table</button>
  </div>
  <div class="search-wrap">
    <svg class="search-icon" width="12" height="12" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2.5">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <input id="global-search" type="search" placeholder="Search columns&hellip;" autocomplete="off">
  </div>
</div>

<!-- APP BODY -->
<div class="app-body">

  <!-- GRAPH TAB -->
  <div id="tab-graph">
    <div class="lane-header">
      <div class="lane-head bronze">&#9679; Bronze &middot; Raw</div>
      <div class="lane-head silver">&#9679; Silver &middot; Staging</div>
      <div class="lane-head intermed">&#9679; Silver &middot; Intermediate</div>
      <div class="lane-head gold">&#9679; Gold</div>
    </div>
    <div class="graph-scroll" id="graph-scroll">
      <div class="graph-canvas" id="graph-canvas">
        <svg class="svg-overlay" id="svg-overlay"></svg>
        <div class="lane" id="lane-bronze"></div>
        <div class="lane" id="lane-silver"></div>
        <div class="lane" id="lane-intermed"></div>
        <div class="lane" id="lane-gold"></div>
      </div>
    </div>
    <div class="legend">
      <div class="legend-item"><div class="legend-line" style="background:var(--direct)"></div>Direct</div>
      <div class="legend-item"><div class="legend-line" style="background:var(--derived)"></div>Derived</div>
      <div class="legend-item"><div class="legend-line" style="background:var(--agg)"></div>Aggregate</div>
      <div class="legend-item"><div class="legend-line" style="background:var(--cast)"></div>Cast</div>
      <span class="legend-hint">Click a column to trace its full lineage path</span>
    </div>
  </div>

  <!-- TABLE TAB -->
  <div id="tab-table">
    <div class="tbl-toolbar">
      <span class="tbl-label">Filter:</span>
      <select id="filter-model" class="filter-sel">
        <option value="">All Models</option>
        ##MODEL_OPTIONS##
      </select>
      <select id="filter-type" class="filter-sel">
        <option value="">All Types</option>
        <option>DIRECT</option><option>DERIVED</option><option>AGGREGATE</option><option>CAST</option>
      </select>
      <span class="row-count" id="row-count"></span>
    </div>
    <div class="tbl-wrap">
      <table class="data-table" id="data-table">
        <thead><tr>
          <th data-col="source_table">Source Table<span class="sort-ic">&#8645;</span></th>
          <th data-col="source_column">Source Column<span class="sort-ic">&#8645;</span></th>
          <th data-col="target_table">Target Table<span class="sort-ic">&#8645;</span></th>
          <th data-col="target_column">Target Column<span class="sort-ic">&#8645;</span></th>
          <th data-col="transformation">Type<span class="sort-ic">&#8645;</span></th>
          <th data-col="expression">Expression<span class="sort-ic">&#8645;</span></th>
        </tr></thead>
        <tbody id="tbl-body"></tbody>
      </table>
    </div>
  </div>

  <!-- DETAIL PANEL -->
  <div id="detail-panel">
    <div class="panel-hdr">
      <span id="panel-title">Details</span>
      <button class="panel-close" onclick="closePanel()" title="Close">&times;</button>
    </div>
    <div class="panel-body" id="panel-body"></div>
  </div>

</div><!-- /app-body -->

<script>
// ── data ──────────────────────────────────────────────────────────────────────
const COL = ##COL_JSON##;

// ── helpers ───────────────────────────────────────────────────────────────────
const shortName = r => String(r).split('.').pop();
const hesc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function badge(t) {
  const cls = t.toLowerCase();
  return `<span class="badge ${cls}">${t}</span>`;
}

// ── lane classification ───────────────────────────────────────────────────────
function laneOf(rel) {
  if (rel.startsWith('lh_bronze') || shortName(rel).startsWith('raw_')) return 'bronze';
  if (rel.startsWith('wh_gold'))   return 'gold';
  const n = shortName(rel);
  if (n.startsWith('int_'))        return 'intermed';
  return 'silver';
}

// ── build graph data structures ───────────────────────────────────────────────
const tableMap   = {};   // rel -> Set<col>
const edgeList   = [];
const edgesOut   = {};   // "rel.col" -> [edge]
const edgesIn    = {};   // "rel.col" -> [edge]

for (const e of COL) {
  const sr = e.source_table, sc = e.source_column;
  const tr = e.target_table, tc = e.target_column;
  if (!tableMap[sr]) tableMap[sr] = new Set();
  if (!tableMap[tr]) tableMap[tr] = new Set();
  tableMap[sr].add(sc);
  tableMap[tr].add(tc);
  const type = (e.transformation || e.lineage_type || 'DIRECT').toUpperCase();
  const edge = { sr, sc, tr, tc, type, expr: e.expression || '' };
  edgeList.push(edge);
  const sk = sr + '\x00' + sc, tk = tr + '\x00' + tc;
  (edgesOut[sk] = edgesOut[sk] || []).push(edge);
  (edgesIn[tk]  = edgesIn[tk]  || []).push(edge);
}

// ── build DOM cards ───────────────────────────────────────────────────────────
const LANE_IDS = { bronze:'lane-bronze', silver:'lane-silver', intermed:'lane-intermed', gold:'lane-gold' };
const byLane   = { bronze:[], silver:[], intermed:[], gold:[] };

for (const rel of Object.keys(tableMap)) byLane[laneOf(rel)].push(rel);
Object.values(byLane).forEach(a => a.sort());

for (const [lane, rels] of Object.entries(byLane)) {
  const container = document.getElementById(LANE_IDS[lane]);
  for (const rel of rels) {
    const sn   = shortName(rel);
    const cols = [...tableMap[rel]].sort();
    const rows = cols.map(col => {
      const k = rel + '\x00' + col;
      const linked = (edgesOut[k] || []).length + (edgesIn[k] || []).length > 0;
      return `<div class="col-row" data-key="${hesc(k)}" onclick="selectCol(this)">`
           + `<span>${hesc(col)}</span>`
           + (linked ? `<span class="col-dot"></span>` : '')
           + `</div>`;
    }).join('');
    container.insertAdjacentHTML('beforeend',
      `<div class="node-card" data-rel="${hesc(rel)}">`
      + `<div class="node-header ${lane}"><span class="nd"></span>${hesc(sn)}</div>`
      + `<div class="col-list">${rows}</div>`
      + `</div>`
    );
  }
}

// ── SVG edge drawing ──────────────────────────────────────────────────────────
const COLORS = { DIRECT:'#3fb950', DERIVED:'#e3b341', AGGREGATE:'#f85149', CAST:'#79c0ff' };
const svgEl  = document.getElementById('svg-overlay');
const scroll = document.getElementById('graph-scroll');
const canvas = document.getElementById('graph-canvas');
let paths    = [];   // {el, sk, tk, type}

function colRowEl(rel, col) {
  return canvas.querySelector(`.col-row[data-key="${CSS.escape(rel + '\x00' + col)}"]`);
}

function midOf(el) {
  const cr = canvas.getBoundingClientRect();
  const r  = el.getBoundingClientRect();
  return {
    cx:    r.left - cr.left + scroll.scrollLeft + r.width  / 2,
    cy:    r.top  - cr.top  + scroll.scrollTop  + r.height / 2,
    right: r.right - cr.left + scroll.scrollLeft,
    left:  r.left  - cr.left + scroll.scrollLeft,
  };
}

function drawEdges() {
  svgEl.setAttribute('width',  canvas.scrollWidth);
  svgEl.setAttribute('height', canvas.scrollHeight);
  svgEl.innerHTML = '';
  paths = [];

  for (const e of edgeList) {
    const srcEl = colRowEl(e.sr, e.sc);
    const tgtEl = colRowEl(e.tr, e.tc);
    if (!srcEl || !tgtEl) continue;

    const s = midOf(srcEl), t = midOf(tgtEl);
    const color = COLORS[e.type] || '#8b949e';
    const x1 = s.right, y1 = s.cy, x2 = t.left, y2 = t.cy;
    const cx = (x1 + x2) / 2;

    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`);
    p.setAttribute('fill',           'none');
    p.setAttribute('stroke',         color);
    p.setAttribute('stroke-width',   '1.5');
    p.setAttribute('stroke-opacity', '0.3');
    p.setAttribute('stroke-linecap', 'round');
    svgEl.appendChild(p);

    const sk = e.sr + '\x00' + e.sc, tk = e.tr + '\x00' + e.tc;
    paths.push({ el: p, sk, tk, type: e.type });
  }
}

// ── selection ─────────────────────────────────────────────────────────────────
let selected = null;

function clearSel() {
  canvas.querySelectorAll('.col-row').forEach(r => r.classList.remove('active','faded'));
  canvas.querySelectorAll('.node-card').forEach(c => c.classList.remove('hl'));
  paths.forEach(p => {
    p.el.setAttribute('stroke-opacity', '0.3');
    p.el.setAttribute('stroke-width',   '1.5');
  });
  selected = null;
}

function selectCol(el) {
  const key = el.dataset.key;
  if (selected === key) { clearSel(); closePanel(); return; }
  selected = key;

  // transitive walk
  const connected = new Set([key]);
  function up(k)   { (edgesIn[k]  || []).forEach(e => { const s=e.sr+'\x00'+e.sc; if (!connected.has(s)) { connected.add(s); up(s);   } }); }
  function down(k) { (edgesOut[k] || []).forEach(e => { const t=e.tr+'\x00'+e.tc; if (!connected.has(t)) { connected.add(t); down(t); } }); }
  up(key); down(key);

  const connectedTables = new Set([...connected].map(k => k.split('\x00')[0]));

  canvas.querySelectorAll('.col-row').forEach(r => {
    const k = r.dataset.key;
    r.classList.toggle('active', k === key);
    r.classList.toggle('faded',  !connected.has(k));
  });
  canvas.querySelectorAll('.node-card').forEach(c => c.classList.toggle('hl', connectedTables.has(c.dataset.rel)));

  paths.forEach(p => {
    const on = connected.has(p.sk) && connected.has(p.tk);
    p.el.setAttribute('stroke-opacity', on ? '1'   : '0.05');
    p.el.setAttribute('stroke-width',   on ? '2.5' : '1');
  });

  openPanel(key, connected);
}

// ── detail panel ──────────────────────────────────────────────────────────────
function openPanel(key, connected) {
  const parts = key.split('\x00');
  const col   = parts.pop();
  const rel   = parts.join('\x00');

  document.getElementById('panel-title').textContent = col;
  document.getElementById('detail-panel').classList.add('open');

  const up   = edgesIn[key]  || [];
  const down = edgesOut[key] || [];

  let h = `<div class="panel-sec">
    <div class="panel-lbl">Table</div>
    <div class="panel-mono">${hesc(shortName(rel))}</div>
  </div>`;

  if (up.length) {
    h += `<div class="panel-sec"><div class="panel-lbl">Upstream (${up.length})</div>`;
    for (const e of up) {
      h += `<div class="edge-item">
        <div class="edge-row">
          <span class="edge-name">${hesc(shortName(e.sr))}.<b>${hesc(e.sc)}</b></span>
          ${badge(e.type)}
        </div>
        ${e.expr ? `<div class="edge-expr">${hesc(e.expr)}</div>` : ''}
      </div>`;
    }
    h += '</div>';
  }

  if (down.length) {
    h += `<div class="panel-sec"><div class="panel-lbl">Downstream (${down.length})</div>`;
    for (const e of down) {
      h += `<div class="edge-item">
        <div class="edge-row">
          <span class="edge-name">${hesc(shortName(e.tr))}.<b>${hesc(e.tc)}</b></span>
          ${badge(e.type)}
        </div>
        ${e.expr ? `<div class="edge-expr">${hesc(e.expr)}</div>` : ''}
      </div>`;
    }
    h += '</div>';
  }

  // chain nodes sorted by lane
  const laneOrder = { bronze:0, silver:1, intermed:2, gold:3 };
  const sorted = [...connected].sort((a,b) => {
    const ra = a.split('\x00')[0], rb = b.split('\x00')[0];
    const la = laneOrder[laneOf(ra)] ?? 99, lb = laneOrder[laneOf(rb)] ?? 99;
    return la !== lb ? la - lb : a.localeCompare(b);
  });
  const chips = sorted.map(k => {
    const p = k.split('\x00'); const c = p.pop(); const r = p.join('\x00');
    return `<span class="chain-node">${hesc(shortName(r))}.<b>${hesc(c)}</b></span>`;
  }).join(' ');

  h += `<div class="panel-sec">
    <div class="panel-lbl">Full chain (${connected.size} nodes)</div>
    <div style="line-height:2">${chips}</div>
  </div>`;

  document.getElementById('panel-body').innerHTML = h;
}

function closePanel() {
  document.getElementById('detail-panel').classList.remove('open');
  clearSel();
}

// ── tab switching ─────────────────────────────────────────────────────────────
function showTab(tab) {
  document.getElementById('tab-graph').style.display = tab === 'graph' ? 'flex' : 'none';
  document.getElementById('tab-table').style.display = tab === 'table' ? 'flex' : 'none';
  document.getElementById('btn-graph').classList.toggle('active', tab === 'graph');
  document.getElementById('btn-table').classList.toggle('active', tab === 'table');
  if (tab === 'table') renderTable();
}
showTab('graph');

// ── table view ────────────────────────────────────────────────────────────────
let sortCol = 'source_table', sortDir = 1;

function renderTable() {
  const model = document.getElementById('filter-model').value;
  const type  = document.getElementById('filter-type').value;
  const q     = document.getElementById('global-search').value.toLowerCase();

  let rows = COL.filter(e => {
    if (model && e.model_name !== model) return false;
    const t = (e.transformation || e.lineage_type || '').toUpperCase();
    if (type && t !== type) return false;
    if (q) {
      const hay = [e.source_table, e.source_column, e.target_table, e.target_column, e.expression || '']
                    .join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  rows.sort((a, b) => {
    const av = (a[sortCol] || '').toLowerCase();
    const bv = (b[sortCol] || '').toLowerCase();
    return av < bv ? -sortDir : av > bv ? sortDir : 0;
  });

  document.getElementById('row-count').textContent = `${rows.length} rows`;
  document.getElementById('tbl-body').innerHTML = rows.map(e => {
    const t = (e.transformation || e.lineage_type || 'DIRECT').toUpperCase();
    return `<tr>
      <td class="hi">${hesc(shortName(e.source_table))}</td>
      <td class="hi">${hesc(e.source_column)}</td>
      <td class="hi">${hesc(shortName(e.target_table))}</td>
      <td class="hi">${hesc(e.target_column)}</td>
      <td>${badge(t)}</td>
      <td>${hesc(e.expression || '')}</td>
    </tr>`;
  }).join('');

  document.querySelectorAll('.data-table th[data-col]').forEach(th => {
    const on = th.dataset.col === sortCol;
    th.classList.toggle('sorted', on);
    th.querySelector('.sort-ic').innerHTML = on ? (sortDir > 0 ? '&#8593;' : '&#8595;') : '&#8645;';
  });
}

document.querySelectorAll('.data-table th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    if (sortCol === th.dataset.col) sortDir *= -1;
    else { sortCol = th.dataset.col; sortDir = 1; }
    renderTable();
  });
});

document.getElementById('filter-model').addEventListener('change', renderTable);
document.getElementById('filter-type').addEventListener('change',  renderTable);

// ── global search ─────────────────────────────────────────────────────────────
document.getElementById('global-search').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  canvas.querySelectorAll('.col-row').forEach(r => {
    r.style.display = !q || r.dataset.key.toLowerCase().includes(q) ? '' : 'none';
  });
  if (document.getElementById('tab-table').style.display !== 'none') renderTable();
  drawEdges();
});

// ── init ──────────────────────────────────────────────────────────────────────
requestAnimationFrame(drawEdges);
scroll.addEventListener('scroll', drawEdges);
window.addEventListener('resize', () => { drawEdges(); });
</script>
</body>
</html>
"""


def _model_options(column_lineage: list[dict]) -> str:
    models = sorted({e["model_name"] for e in column_lineage})
    return "\n".join(f'<option value="{esc(m)}">{esc(m)}</option>' for m in models)


def render_html(data: dict) -> str:
    metadata       = data["metadata"]
    column_lineage = data["column_lineage"]

    col_json = json.dumps(column_lineage, ensure_ascii=False)

    return (
        _TEMPLATE
        .replace("##PROJECT##",      esc(metadata.get("dbt_project", "shopstream_dbt_demo")))
        .replace("##N_MODELS##",     esc(metadata.get("total_models", "?")))
        .replace("##N_SOURCES##",    esc(metadata.get("total_sources", "?")))
        .replace("##N_EDGES##",      str(len(column_lineage)))
        .replace("##MODEL_OPTIONS##", _model_options(column_lineage))
        .replace("##COL_JSON##",     col_json)
    )




def main() -> None:
    data = json.loads(LINEAGE_PATH.read_text(encoding="utf-8"))
    HTML_OUTPUT.write_text(render_html(data), encoding="utf-8")
    print(f"Wrote lineage HTML report: {HTML_OUTPUT}")


if __name__ == "__main__":
    main()
