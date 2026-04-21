import * as XLSX from 'xlsx';

const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fmtDate = (d) => d ? `${String(d.day).padStart(2,'0')} ${MONTHS_SHORT[d.month - 1]} ${d.year}` : '';

function buildMetaRows(meta, data) {
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const freqLabels = { monthly: 'Monthly', quarterly: 'Quarterly', annual: 'Annual', fiscal_year: 'Fiscal Year' };
  const freqLabel = meta.frequency || freqLabels[meta.aggregation] || meta.aggregation || '';
  const rows = [];

  // Per-indicator unit lookup: pulled from the "(unit)" descriptor row that
  // both Dashboard and ChartPanel prepend to the wide-format export.
  const unitByName = {};
  const unitRow = (data || []).find((r) => r && String(r.TIME_PERIOD) === '(unit)');
  if (unitRow) {
    Object.entries(unitRow).forEach(([k, v]) => {
      if (!['TIME_PERIOD', 'LOCATION', 'SOURCE', 'FREQUENCY'].includes(k) && v) unitByName[k] = v;
    });
  }

  rows.push(['GENERAL INFORMATION', '']);
  rows.push(['Category',       meta.category]);
  rows.push(['Location',       meta.location]);
  if (meta.source) rows.push(['Source', meta.source]);
  rows.push(['Frequency',      freqLabel]);
  rows.push(['Period covered', `${fmtDate(meta.startDate)} – ${fmtDate(meta.endDate)}`]);
  if (meta.transform) rows.push(['Transformation', meta.transform]);
  rows.push(['Downloaded at',  now]);
  rows.push(['', '']);

  // ── Per-indicator detail ──────────────────────────────────────────────────
  rows.push(['INDICATOR DETAILS', '']);
  rows.push(['Indicator', 'Description', 'Definition', 'Unit', 'Source', 'Frequency']);
  (meta.indicators || []).forEach((ind) => {
    const name = ind.INDICATOR_NAME ?? '';
    rows.push([
      name,
      ind.DESCRIPTION ?? '',
      ind.DEFINITION  ?? '',
      ind.UNIT        ?? unitByName[name] ?? meta.unit      ?? '',
      ind.SOURCE      ?? meta.source      ?? '',
      ind.FREQUENCY   ?? freqLabel,
    ]);
  });

  return rows;
}

// ── Wide format conversion ────────────────────────────────────────────────────
// Converts long-format rows {TIME_PERIOD, LOCATION_NAME, INDICATOR_NAME, VALUE, UNIT, ...}
// to wide format: TIME_PERIOD, LOCATION, then one column per indicator.
// A units descriptor row is prepended so readers know each indicator's unit.
export function toWideFormat(data, meta = {}) {
  const freqLabels  = { monthly: 'Monthly', quarterly: 'Quarterly', annual: 'Annual', fiscal_year: 'Fiscal Year' };
  const periodOrder = [...new Set(data.map((r) => String(r.TIME_PERIOD)))];
  const indicators  = [...new Set(data.map((r) => r.INDICATOR_NAME).filter(Boolean))];

  // Derive context from data rows (all DB-sourced), fall back to meta params
  const location  = data[0]?.LOCATION_NAME ?? meta.location ?? '';
  const source    = data[0]?.SOURCE        ?? '';
  const frequency = data[0]?.FREQUENCY     ?? freqLabels[meta.aggregation] ?? meta.aggregation ?? '';

  // Per-indicator unit from raw rows
  const unitByIndicator = {};
  data.forEach((r) => {
    if (r.INDICATOR_NAME && r.UNIT) unitByIndicator[r.INDICATOR_NAME] = r.UNIT;
  });

  const lookup = {};
  data.forEach((r) => {
    const tp = String(r.TIME_PERIOD);
    if (!lookup[tp]) lookup[tp] = {};
    lookup[tp][r.INDICATOR_NAME] = r.VALUE;
  });

  // Descriptor rows for per-indicator metadata
  const unitRow   = { TIME_PERIOD: '(unit)',      LOCATION: '', SOURCE: '', FREQUENCY: '' };
  indicators.forEach((name) => { unitRow[name]   = unitByIndicator[name] ?? ''; });

  const dataRows = periodOrder.map((tp) => {
    const row = { TIME_PERIOD: tp, LOCATION: location, SOURCE: source, FREQUENCY: frequency };
    indicators.forEach((name) => { row[name] = lookup[tp]?.[name] ?? ''; });
    return row;
  });

  return [unitRow, ...dataRows];
}

// ── Excel ──────────────────────────────────────────────────────────────────────
export function downloadExcel(data, meta, filename) {
  const wb = XLSX.utils.book_new();

  // Sheet 1: DATA
  const ws_data = XLSX.utils.json_to_sheet(data);
  XLSX.utils.book_append_sheet(wb, ws_data, 'Data');

  // Sheet 2: METADATA
  const metaRows = buildMetaRows(meta, data);
  const ws_meta  = XLSX.utils.aoa_to_sheet(metaRows);

  // Simple column widths
  ws_meta['!cols'] = [{ wch: 22 }, { wch: 60 }, { wch: 80 }];
  XLSX.utils.book_append_sheet(wb, ws_meta, 'Metadata');

  XLSX.writeFile(wb, filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`);
}

// ── CSV helpers ───────────────────────────────────────────────────────────────

function csvCell(value) {
  if (value === null || value === undefined) return '';
  const s = String(value);
  return s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')
    ? '"' + s.replace(/"/g, '""') + '"'
    : s;
}

function aoa_to_csv(rows) {
  return rows.map((r) => r.map(csvCell).join(',')).join('\r\n');
}

// ── CSV: two files (data + metadata) ─────────────────────────────────────────
export function downloadCSV(data, meta, filename) {
  const base = filename.replace(/\.csv$/i, '');

  // ── File 1: data ──────────────────────────────────────────────────────────
  const dataRows = data.length
    ? [Object.keys(data[0]), ...data.map((r) => Object.values(r).map((v) => v ?? ''))]
    : [[]];
  const dataBlob = new Blob([aoa_to_csv(dataRows)], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(dataBlob, `${base}_data.csv`);

  // ── File 2: metadata ──────────────────────────────────────────────────────
  const metaBlob = new Blob([aoa_to_csv(buildMetaRows(meta, data))], { type: 'text/csv;charset=utf-8;' });
  setTimeout(() => triggerDownload(metaBlob, `${base}_metadata.csv`), 300);
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href    = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
