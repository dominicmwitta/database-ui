import { useState, useRef, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { ChevronDown } from 'lucide-react';
import { CHART_COLORS } from '../theme';
import { exportSVG, exportPNG, exportJPEG, exportPDF } from '../utils/exportChart';
import { TRANSFORMS, DEFAULT_LAMBDA, applyTransform } from '../utils/transforms';
import { downloadExcel, downloadCSV } from '../utils/download';

const CHART_TYPES = ['Line', 'Bar', 'Area'];
const DEFAULT_H   = 280;
const MIN_H       = 140;
const MIN_W       = 320;
const MONTHS      = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const EXPORT_FORMATS = [
  { label: 'PNG',  fn: exportPNG  },
  { label: 'JPEG', fn: exportJPEG },
  { label: 'SVG',  fn: exportSVG  },
  { label: 'PDF',  fn: exportPDF  },
];

const TRANSFORM_GROUPS = TRANSFORMS.reduce((acc, t) => {
  (acc[t.group] ??= []).push(t);
  return acc;
}, {});

function parseYearMonth(period) {
  const parts = String(period).split(/[-T]/);
  if (parts.length >= 2) return { year: parts[0], monthIdx: parseInt(parts[1], 10) - 1 };
  return null;
}

function formatPeriod(period, frequency) {
  if (frequency === 'monthly') {
    const p = parseYearMonth(period);
    if (p && p.monthIdx >= 0 && p.monthIdx < 12) return `${MONTHS[p.monthIdx]}-${p.year}`;
  }
  if (frequency === 'fiscal_year') {
    // "FY2022/2023" → "FY 2022/23" to fit on the axis without overlap
    const m = String(period).match(/^FY(\d{4})\/(\d{4})$/);
    if (m) return `FY ${m[1]}/${m[2].slice(2)}`;
  }
  return String(period);
}

function buildTicks(periods, frequency, axisWidthPx) {
  if (!periods.length) return periods;
  const n = periods.length;
  if (n === 1) return periods;
  const labelPx  = frequency === 'monthly'     ? 68
                 : frequency === 'fiscal_year' ? 78
                 : 50;
  const maxTicks = Math.max(2, Math.floor((axisWidthPx ?? 400) / labelPx));
  const step     = Math.max(1, Math.ceil(n / maxTicks));
  const ticks    = periods.filter((_, i) => i % step === 0);
  const lastPeriod = periods[n - 1];
  if (ticks[ticks.length - 1] === lastPeriod) return ticks;
  const lastTickIdx = periods.indexOf(ticks[ticks.length - 1]);
  const gapToEnd    = n - 1 - lastTickIdx;
  if (gapToEnd < step * 0.5) {
    if (ticks.length >= 2) {
      const prevTickIdx = periods.indexOf(ticks[ticks.length - 2]);
      ticks[ticks.length - 1] = periods[Math.round((prevTickIdx + (n - 1)) / 2)];
    } else { ticks.pop(); }
  }
  ticks.push(lastPeriod);
  return ticks;
}

function Grip({ dir, active, theme }) {
  return (
    <div style={{ display: 'flex', flexDirection: dir === 'e' ? 'column' : 'row', gap: 3, alignItems: 'center', justifyContent: 'center' }}>
      {[0,1,2,3,4].map((i) => (
        <div key={i} style={{ width: 3, height: 3, borderRadius: '50%', background: active ? theme.accent : theme.border, transition: 'background 0.15s' }} />
      ))}
    </div>
  );
}

function Dropdown({ label, children, theme }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen((o) => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 4, padding: '4px 9px', fontSize: 11,
        cursor: 'pointer', background: theme.surface, color: theme.muted,
        border: `1px solid ${theme.border}`, borderRadius: 4, fontFamily: 'inherit',
      }}>
        {label} <ChevronDown size={11} />
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', right: 0, zIndex: 200,
          background: theme.surface, border: `1px solid ${theme.border}`,
          borderRadius: 4, boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
          minWidth: 210, overflow: 'hidden',
        }}>
          {children(setOpen)}
        </div>
      )}
    </div>
  );
}

// Checkbox-based transform picker. Each checked transform is plotted as a separate series.
function TransformCheckboxDropdown({ selected, onChange, theme }) {
  const nonNone = selected.filter((id) => id !== 'none');
  const label =
    nonNone.length === 0 ? 'Transform' :
    nonNone.length === 1 ? (TRANSFORMS.find((t) => t.id === nonNone[0])?.label ?? 'Transform') :
    `${nonNone.length} transforms`;

  const toggle = (id) => {
    if (selected.includes(id)) {
      const next = selected.filter((x) => x !== id);
      // always keep at least one selected
      onChange(next.length ? next : ['none']);
    } else {
      // adding a non-none: drop the 'none' placeholder if it was the only thing
      const base = selected.filter((x) => x !== 'none');
      onChange([...base, id]);
    }
  };

  const toggleNone = () => {
    if (selected.includes('none')) {
      const next = selected.filter((x) => x !== 'none');
      onChange(next.length ? next : ['none']);
    } else {
      onChange([...selected, 'none']);
    }
  };

  return (
    <Dropdown label={label} theme={theme}>
      {() => (
        <div style={{ padding: '4px 0', maxHeight: 340, overflowY: 'auto' }}>
          {Object.entries(TRANSFORM_GROUPS).map(([group, items]) => (
            <div key={group}>
              <div style={{ padding: '5px 12px 3px', fontSize: 10, fontWeight: 700, color: theme.muted, textTransform: 'uppercase', letterSpacing: '0.06em', borderTop: `1px solid ${theme.border}` }}>
                {group}
              </div>
              {items.map((t) => {
                const checked = t.id === 'none' ? selected.includes('none') : selected.includes(t.id);
                const onChg   = t.id === 'none' ? toggleNone : () => toggle(t.id);
                return (
                  <label key={t.id} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 14px', cursor: 'pointer', fontSize: 12, color: theme.text,
                    background: checked ? `${theme.accent}11` : 'none',
                  }}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={onChg}
                      style={{ accentColor: theme.accent, cursor: 'pointer' }}
                    />
                    {t.label}
                  </label>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </Dropdown>
  );
}

function ExportDropdown({ onExport, theme }) {
  return (
    <Dropdown label="Export" theme={theme}>
      {(setOpen) => (
        <>
          <div style={{ padding: '5px 12px 3px', fontSize: 10, fontWeight: 700, color: theme.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Chart image
          </div>
          {EXPORT_FORMATS.map(({ label }) => (
            <button key={label} onClick={() => { onExport(label); setOpen(false); }}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '7px 14px', fontSize: 12, cursor: 'pointer', background: 'none', border: 'none', color: theme.text, fontFamily: 'inherit' }}
              onMouseEnter={(e) => e.currentTarget.style.background = `${theme.accent}18`}
              onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
            >{label}</button>
          ))}
          <div style={{ padding: '5px 12px 3px', fontSize: 10, fontWeight: 700, color: theme.muted, textTransform: 'uppercase', letterSpacing: '0.06em', borderTop: `1px solid ${theme.border}`, marginTop: 2 }}>
            Data
          </div>
          {['Excel', 'CSV'].map((label) => (
            <button key={label} onClick={() => { onExport(`data:${label}`); setOpen(false); }}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '7px 14px', fontSize: 12, cursor: 'pointer', background: 'none', border: 'none', color: theme.text, fontFamily: 'inherit' }}
              onMouseEnter={(e) => e.currentTarget.style.background = `${theme.accent}18`}
              onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
            >{label}</button>
          ))}
        </>
      )}
    </Dropdown>
  );
}

export default function ChartPanel({ title, data, theme, frequency, defaultFlex, indicators, unit }) {
  const [chartType,      setChartType]      = useState('Line');
  // Array of selected transform IDs — each is applied independently and plotted as its own series
  const [selected,       setSelected]       = useState(['none']);
  const [lambda,         setLambda]         = useState(null);
  const [size,           setSize]           = useState({ w: null, h: DEFAULT_H });
  const [dragging,       setDragging]       = useState(null);
  const [containerWidth, setContainerWidth] = useState(480);
  const [metaOpen,       setMetaOpen]       = useState(true);
  const panelRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const effectiveLambda   = lambda ?? DEFAULT_LAMBDA[frequency] ?? 1600;
  const hasHP             = selected.some((id) => TRANSFORMS.find((t) => t.id === id)?.hasLambda);
  // When multiple transforms are selected, suffix each series key with the transform label
  const multiTransform    = selected.length > 1 || (selected.length === 1 && selected[0] !== 'none');
  const needsSuffix       = selected.length > 1;

  function startDrag(axis) {
    return (e) => {
      e.preventDefault();
      const startX = e.clientX, startY = e.clientY;
      const startW = size.w ?? (panelRef.current ? panelRef.current.offsetWidth : 480);
      const startH = size.h;
      setDragging(axis);
      const onMove = (ev) => {
        setSize({
          w: axis === 'y' ? size.w : Math.max(MIN_W, startW + ev.clientX - startX),
          h: axis === 'x' ? startH : Math.max(MIN_H, startH + ev.clientY - startY),
        });
      };
      const onUp = () => {
        setDragging(null);
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    };
  }

  // handleExport is defined after chartData is computed (see below)

  const isResized  = size.w !== null || size.h !== DEFAULT_H;
  const panelStyle = {
    background: theme.surface, border: `1px solid ${theme.border}`,
    borderRadius: 6, padding: '16px 18px 8px',
    position: 'relative', userSelect: dragging ? 'none' : 'auto',
    ...(size.w !== null
      ? { width: size.w, flex: `0 0 ${size.w}px` }
      : defaultFlex ? { flex: '1 1 100%' } : { flex: '1 1 480px' }
    ),
  };

  if (!data || !data.length) {
    return <div style={{ ...panelStyle, padding: 24, textAlign: 'center', color: theme.muted, fontSize: 13 }}>No data to display</div>;
  }

  // ── Build chart data: each selected transform produces its own set of series ──
  const seriesNames = [...new Set(data.map((r) => r.INDICATOR_NAME))].filter(Boolean);
  const periodSet   = [...new Set(data.map((r) => String(r.TIME_PERIOD)))].sort();

  // Pre-compute raw values per indicator
  const rawByName = {};
  seriesNames.forEach((name) => {
    const byPeriod = {};
    data.forEach((r) => { if (r.INDICATOR_NAME === name) byPeriod[String(r.TIME_PERIOD)] = r.VALUE; });
    rawByName[name] = periodSet.map((p) => byPeriod[p] ?? null);
  });

  // For each (transform, indicator) pair, compute a series key and transformed values
  const allSeriesKeys = [];
  const transformedByKey = {};

  selected.forEach((transformId) => {
    const tDef = TRANSFORMS.find((t) => t.id === transformId);
    seriesNames.forEach((name) => {
      const key = needsSuffix
        ? `${name} — ${tDef?.label ?? transformId}`
        : name;
      const tvs = applyTransform(rawByName[name], transformId, { lambda: effectiveLambda, frequency });
      transformedByKey[key] = Object.fromEntries(periodSet.map((p, i) => [p, tvs[i]]));
      allSeriesKeys.push(key);
    });
  });

  const chartData = periodSet.map((period) => {
    const row = { period };
    allSeriesKeys.forEach((key) => { row[key] = transformedByKey[key][period]; });
    return row;
  });

  // Defined here so it can reference chartData and allSeriesKeys
  function handleExport(format) {
    const safe = title.replace(/[^\w\s-]/g, '').trim();

    if (format === 'data:Excel' || format === 'data:CSV') {
      const location = data[0]?.LOCATION_NAME ?? '';
      const transformLabel = selected
        .filter((id) => id !== 'none')
        .map((id) => TRANSFORMS.find((t) => t.id === id)?.label ?? id)
        .join(', ') || 'None (raw)';

      const freqLabels = { monthly: 'Monthly', quarterly: 'Quarterly', annual: 'Annual', fiscal_year: 'Fiscal Year' };
      const source     = data[0]?.SOURCE    ?? '';
      const freqLabel  = data[0]?.FREQUENCY ?? freqLabels[frequency] ?? frequency;

      // Unit descriptor row so readers know each column's unit
      const unitRow = { TIME_PERIOD: '(unit)', LOCATION: '', SOURCE: '', FREQUENCY: '' };
      allSeriesKeys.forEach((key) => { unitRow[key] = unit ?? ''; });

      // Wide format: TIME_PERIOD, LOCATION, SOURCE, FREQUENCY + one column per series
      const dataRows = chartData.map((row) => {
        const out = {
          TIME_PERIOD: row.period,
          LOCATION:    location,
          SOURCE:      source,
          FREQUENCY:   freqLabel,
        };
        allSeriesKeys.forEach((key) => { out[key] = row[key] ?? ''; });
        return out;
      });
      const exportRows = [unitRow, ...dataRows];

      const meta = {
        category:    title,
        location,
        aggregation: frequency,
        source,
        frequency:   data[0]?.FREQUENCY ?? '',
        unit:        unit ?? '',
        startDate:   null,
        endDate:     null,
        indicators:  indicators ?? [],
        transform:   transformLabel,
      };

      if (format === 'data:Excel') downloadExcel(exportRows, meta, `${safe}_data`);
      else                          downloadCSV(exportRows,   meta, `${safe}_data`);
      return;
    }

    const el  = chartRef.current;
    const fmt = EXPORT_FORMATS.find((f) => f.label === format);
    if (fmt) fmt.fn(el, safe);
  }

  const xAxisWidthPx = Math.max(100, containerWidth - 100);
  const ticks        = buildTicks(periodSet, frequency, xAxisWidthPx);

  const ChartComponent  = chartType === 'Bar' ? BarChart  : chartType === 'Area' ? AreaChart  : LineChart;
  const SeriesComponent = chartType === 'Bar' ? Bar       : chartType === 'Area' ? Area       : Line;
  const extraProps =
    chartType === 'Area' ? { fillOpacity: 0.2, type: 'monotone' } :
    chartType === 'Line' ? { type: 'monotone', dot: false, strokeWidth: 2 } :
    {};

  return (
    <div ref={panelRef} style={panelStyle}>

      {/* ── Header: chart type + transform picker + export ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', marginBottom: 6, gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {isResized && (
            <button onClick={() => setSize({ w: null, h: DEFAULT_H })} title="Reset size"
              style={{ background: 'none', border: `1px solid ${theme.border}`, borderRadius: 4, padding: '3px 7px', cursor: 'pointer', fontSize: 10, color: theme.muted, fontFamily: 'inherit' }}>
              Reset
            </button>
          )}
          <div style={{ display: 'flex', border: `1px solid ${theme.border}`, borderRadius: 4, overflow: 'hidden' }}>
            {CHART_TYPES.map((t) => (
              <button key={t} onClick={() => setChartType(t)} style={{
                padding: '4px 10px', fontSize: 11, border: 'none', cursor: 'pointer',
                background: chartType === t ? theme.buttonBg : theme.surface,
                color:      chartType === t ? theme.buttonText : theme.muted,
                fontFamily: 'inherit',
              }}>{t}</button>
            ))}
          </div>
          <TransformCheckboxDropdown selected={selected} onChange={setSelected} theme={theme} />
          <ExportDropdown onExport={handleExport} theme={theme} />
        </div>
      </div>

      {/* ── Lambda input (shown when any HP filter transform is selected) ── */}
      {hasHP && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontSize: 11, color: theme.muted }}>
          <span>λ (smoothing):</span>
          <input type="number" min={1} value={lambda ?? effectiveLambda}
            onChange={(e) => setLambda(Number(e.target.value) || 1)}
            style={{ width: 90, padding: '2px 6px', fontSize: 11, border: `1px solid ${theme.border}`, borderRadius: 4, background: theme.bg, color: theme.text, fontFamily: 'inherit' }}
          />
          <button onClick={() => setLambda(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, color: theme.muted, padding: 0, fontFamily: 'inherit' }}
            title="Reset to default">reset</button>
          <span style={{ color: theme.muted, fontSize: 10 }}>(default {DEFAULT_LAMBDA[frequency] ?? 1600})</span>
        </div>
      )}

      {/* ── Active transform badge (single non-raw transform, no HP) ── */}
      {!needsSuffix && selected[0] !== 'none' && !hasHP && (
        <div style={{ marginBottom: 6, fontSize: 10, color: theme.accent, fontWeight: 600 }}>
          {TRANSFORMS.find((t) => t.id === selected[0])?.label}
        </div>
      )}

      {/* ── Chart ── */}
      <div ref={chartRef}>
        <ResponsiveContainer width="100%" height={size.h}>
          <ChartComponent data={chartData} margin={{ top: 4, right: 40, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
            <XAxis dataKey="period" ticks={ticks} tickFormatter={(v) => formatPeriod(v, frequency)}
              tick={{ fontSize: 10, fill: theme.muted, textAnchor: 'middle' }} tickLine={{ stroke: theme.muted, strokeWidth: 1 }} tickSize={5} interval={0} />
            <YAxis tick={{ fontSize: 10, fill: theme.muted }} tickLine={{ stroke: theme.muted, strokeWidth: 1 }} tickSize={5} axisLine={false} width={60} />
            <Tooltip
              contentStyle={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 4, fontSize: 11 }}
              labelStyle={{ color: theme.text, fontWeight: 600 }}
              labelFormatter={(v) => formatPeriod(v, frequency)}
            />
            {allSeriesKeys.length > 1 && (
              <Legend
                verticalAlign="top"
                iconType="plainline"
                wrapperStyle={{ fontSize: 11, color: theme.muted, paddingBottom: 8 }}
              />
            )}
            {allSeriesKeys.map((key, i) => (
              <SeriesComponent key={key} dataKey={key}
                stroke={CHART_COLORS[i % CHART_COLORS.length]}
                fill={CHART_COLORS[i % CHART_COLORS.length]}
                {...extraProps}
              />
            ))}
          </ChartComponent>
        </ResponsiveContainer>
      </div>

      {/* ── Bottom handle ── */}
      <div onMouseDown={startDrag('y')} title="Drag to resize height"
        style={{ marginTop: 6, height: 12, cursor: 'ns-resize', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Grip dir="s" active={dragging === 'y' || dragging === 'xy'} theme={theme} />
      </div>

      {/* ── Indicator metadata ── */}
      {indicators && indicators.length > 0 && (
        <div style={{ marginTop: 10, borderTop: `1px solid ${theme.border}`, paddingTop: 8 }}>
          <button onClick={() => setMetaOpen((o) => !o)}
            style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'none', border: 'none', cursor: 'pointer', padding: '0 0 6px', width: '100%', textAlign: 'left', color: theme.muted, fontFamily: 'inherit' }}>
            <svg width="10" height="10" viewBox="0 0 10 10" style={{ flexShrink: 0, transform: metaOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>
              <path d="M3 1 L8 5 L3 9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Indicator Details</span>
          </button>
          {metaOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {indicators.map((ind) => (
                <div key={ind.INDICATOR_NAME} style={{ fontSize: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8, marginBottom: 3 }}>
                    <span style={{ fontWeight: 600, color: theme.text, lineHeight: 1.3 }}>{ind.DESCRIPTION || ind.INDICATOR_NAME}</span>
                    {unit && (
                      <span style={{ fontSize: 10, whiteSpace: 'nowrap', flexShrink: 0, background: `${theme.accent}18`, color: theme.accent, borderRadius: 3, padding: '1px 6px', fontWeight: 600 }}>
                        {unit}
                      </span>
                    )}
                  </div>
                  {ind.DEFINITION
                    ? <p style={{ margin: 0, fontSize: 11, color: theme.muted, lineHeight: 1.55 }}>{ind.DEFINITION}</p>
                    : <p style={{ margin: 0, fontSize: 11, color: theme.muted, fontStyle: 'italic' }}>No definition available.</p>
                  }
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Right handle ── */}
      <div onMouseDown={startDrag('x')} title="Drag to resize width"
        style={{ position: 'absolute', top: '50%', right: 4, transform: 'translateY(-50%)', width: 14, height: 52, cursor: 'ew-resize', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
        <Grip dir="e" active={dragging === 'x' || dragging === 'xy'} theme={theme} />
      </div>

      {/* ── Corner handle ── */}
      <div onMouseDown={startDrag('xy')} title="Drag to resize"
        style={{ position: 'absolute', bottom: 0, right: 0, width: 16, height: 16, cursor: 'se-resize', display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end', padding: 3 }}>
        <svg width="8" height="8" viewBox="0 0 8 8">
          <path d="M8 0 L8 8 L0 8" fill="none" stroke={dragging === 'xy' ? theme.accent : theme.border} strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}
