import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { LogOut, Play, RotateCcw, Settings, Download, FileSpreadsheet, Search, X, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { BRAND, THEMES } from '../theme';
import {
  fetchCategories, fetchIndicators, fetchLocations, fetchUnits, fetchData, logout,
} from '../api/client';
import ChartPanel from './ChartPanel';
import { downloadExcel, downloadCSV, toWideFormat } from '../utils/download';

const AGGREGATIONS = ['monthly', 'quarterly', 'annual', 'fiscal_year'];
const AGG_LABELS   = { monthly: 'Monthly', quarterly: 'Quarterly', annual: 'Calendar Year', fiscal_year: 'Fiscal Year' };
const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DOW          = ['Su','Mo','Tu','We','Th','Fr','Sa'];

// Converts a date object {year, month, day} to a sortable integer for comparisons
const dateOrd = (d) => d.year * 10000 + d.month * 100 + d.day;

// Indicator name prefixes (matched via startsWith) that appear in the right-hand
// Key Indicators panel, listed in the desired display order.
// National Accounts shows quarterly YoY growth rates; all others show latest monthly levels.
const CATEGORY_HIGHLIGHTS = {
  'Prices and Interest Rates':    ['INFLATION RATE', 'CORE INFLATION', 'UNPROCESSED FOOD INFLATION', 'ENERGY FUEL AND UTILITIES INFLATION', 'OVERALL LENDING RATE'],
  'External Sector':              ['CURRENT ACCOUNT', 'EXPORTS GOODS AND SERVICES', 'IMPORTS GOODS SERVICES'],
  'Financial Sector Indicators':  ['CREDIT TO PRIVATE SECTOR, PERCENT OF GDP', 'CREDIT TO THE PRIVATE SECTOR, ANNUAL PERCENTAGE CHANGE'],
  'Government Finance Statistics':['FISCAL DEFICIT', 'TOTAL DEBT STOCK', 'DOMESTIC DEBT STOCK', 'PUBLIC EXTERNAL DEBT STOCK'],
  'National Accounts':            ['REAL GDP', 'AGRICULTURE', 'MINING AND QUARRYING', 'CONSTRUCTION', 'FINANCE'],
  'Payment Statistics':           ['PAYMENT']
};


// Formats a number with thousand separators; abbreviates large values to M/B.
// `decimals` controls the small-value precision (defaults to 2).
function fmtNum(v, decimals = 2) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  if (isNaN(n)) return '—';
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (a >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (a >= 1e4) return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

// Formats a TIME_PERIOD string.
// quarterly=true  → "2025Q3"  (used for National Accounts)
// quarterly=false → "Mar 2025" (used for all other categories)
function fmtPeriod(p, quarterly = false) {
  if (!p) return '';
  const s = String(p);
  if (quarterly) {
    const qm = s.match(/^(\d{4})Q(\d)$/);
    if (qm) return s;
    const parts = s.split(/[-T]/);
    if (parts.length >= 2) {
      const m = parseInt(parts[1], 10);
      return `${parts[0]}Q${Math.ceil(m / 3)}`;
    }
  }
  const parts = s.split(/[-T]/);
  if (parts.length >= 2) {
    const m = parseInt(parts[1], 10) - 1;
    return `${MONTHS_SHORT[m] ?? parts[1]} ${parts[0]}`;
  }
  return s;
}

function KeyIndicatorsPanel({ items, loading, activeCategory, theme }) {
  if (!loading && !items.length) return null;

  return (
    <div style={{ width: 230, flexShrink: 0, position: 'sticky', top: 76 }}>
      {/* Header */}
      <div style={{
        background: theme.heroBg, borderRadius: '6px 6px 0 0',
        padding: '13px 16px 12px',
      }}>
        <div style={{ fontSize: 10, color: theme.heroAccent, textTransform: 'uppercase', letterSpacing: '0.14em', fontWeight: 700 }}>
          Key Indicators
        </div>
        <div style={{ fontSize: 14, color: theme.heroText, fontWeight: 600, marginTop: 3 }}>
          {activeCategory}
        </div>
      </div>

      {/* Cards */}
      <div style={{
        background: theme.surface, border: `1px solid ${theme.border}`,
        borderTop: 'none', borderRadius: '0 0 6px 6px', overflow: 'hidden',
      }}>
        {loading && !items.length ? (
          <div style={{ padding: '24px', textAlign: 'center', color: theme.muted, fontSize: 12 }}>Loading…</div>
        ) : (
          items.map((item, i) => {
            const isPct    = (item.unit || '').toLowerCase().includes('percent') || (item.unit || '').includes('%');
            const delta    = item.prevValue !== null ? Number(item.value) - Number(item.prevValue) : null;
            const up       = delta !== null ? delta > 0 : null;
            const neutral  = delta === null || Math.abs(delta) < 0.0001;
            const barColor = neutral ? theme.border : up ? '#16a34a' : '#dc2626';
            const txtColor = neutral ? theme.muted  : up ? '#16a34a' : '#dc2626';
            // Prices and Interest Rates: inflation metrics → 1 decimal; interest/lending rates → 2 decimals.
            const isInterestRate = /interest|lending|deposit|repo|treasury/i.test(item.name);
            const decimals = (activeCategory === 'Prices and Interest Rates' && !isInterestRate) ? 1 : 2;

            return (
              <div key={item.name} style={{
                padding: '14px 16px 13px 20px',
                borderBottom: i < items.length - 1 ? `1px solid ${theme.border}` : 'none',
                position: 'relative',
              }}>
                {/* Left accent bar */}
                <div style={{
                  position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
                  background: barColor,
                }} />

                {/* Name */}
                <div style={{ fontSize: 13, color: theme.text, lineHeight: 1.4, marginBottom: 6, textTransform: 'capitalize', fontWeight: 500 }}>
                  {item.name}
                </div>

                {/* Value + unit */}
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 28, fontWeight: 700, color: theme.text, lineHeight: 1, letterSpacing: '-0.5px' }}>
                    {fmtNum(item.value, decimals)}
                  </span>
                  {item.unit && (
                    <span style={{ fontSize: 11, color: theme.muted, fontWeight: 500, lineHeight: 1.3 }}>{item.unit.replace(/percent/gi, '%')}</span>
                  )}
                </div>

                {/* YoY growth rate (National Accounts only) */}
                {item.yoyPct != null && (
                  <div style={{ fontSize: 11, fontWeight: 600, marginTop: 3, color: item.yoyPct >= 0 ? '#16a34a' : '#dc2626' }}>
                    {item.yoyPct >= 0 ? '▲' : '▼'} {Math.abs(item.yoyPct).toFixed(1)}% year-on-year
                  </div>
                )}

                {/* Period + trend */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
                  <span style={{ fontSize: 11, color: theme.muted }}>{fmtPeriod(item.period, activeCategory === 'National Accounts')}</span>
                  {!neutral && delta !== null && (
                    <span style={{ fontSize: 11, fontWeight: 700, color: txtColor, display: 'flex', alignItems: 'center', gap: 2 }}>
                      {up ? '▲' : '▼'} {fmtNum(Math.abs(delta), decimals)}
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function Label({ children, theme }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 600, color: theme.muted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
      {children}
    </div>
  );
}

function Select({ value, onChange, options, theme, placeholder }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      style={{
        width: '100%', padding: '7px 10px', fontSize: 12,
        background: theme.surface, color: theme.text,
        border: `1px solid ${theme.border}`, borderRadius: 4,
        outline: 'none', fontFamily: 'inherit', cursor: 'pointer',
      }}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
      ))}
    </select>
  );
}

function MultiCheckList({ options, selected, onChange, theme }) {
  const [query, setQuery] = useState('');

  const filtered = query.trim()
    ? options.filter((o) => (o.label ?? o).toLowerCase().includes(query.toLowerCase()))
    : options;

  const toggle = (val) =>
    onChange(selected.includes(val) ? selected.filter((v) => v !== val) : [...selected, val]);

  const allFiltered = filtered.length > 0 && filtered.every((o) => selected.includes(o.value ?? o));
  const toggleFiltered = () => {
    const vals = filtered.map((o) => o.value ?? o);
    if (allFiltered) onChange(selected.filter((v) => !vals.includes(v)));
    else onChange([...new Set([...selected, ...vals])]);
  };

  return (
    <div style={{ border: `1px solid ${theme.border}`, borderRadius: 4, overflow: 'hidden' }}>
      {/* Search input */}
      <div style={{ position: 'relative', borderBottom: `1px solid ${theme.border}` }}>
        <Search size={12} style={{ position: 'absolute', left: 8, top: 8, color: theme.muted, pointerEvents: 'none' }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search indicators…"
          style={{
            width: '100%', padding: '7px 28px 7px 26px', fontSize: 12,
            background: theme.surface, color: theme.text,
            border: 'none', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
          }}
        />
        {query && (
          <button onClick={() => setQuery('')}
            style={{ position: 'absolute', right: 6, top: 6, background: 'none', border: 'none', cursor: 'pointer', color: theme.muted, padding: 2 }}>
            <X size={11} />
          </button>
        )}
      </div>

      {/* Select all (within filtered set) */}
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px',
        borderBottom: `1px solid ${theme.border}`, cursor: 'pointer', fontSize: 11, color: theme.muted,
        background: theme.bg }}>
        <input type="checkbox" checked={allFiltered} onChange={toggleFiltered} />
        {query ? `Select all (${filtered.length} matches)` : `Select all (${options.length})`}
      </label>

      {/* List */}
      <div style={{ maxHeight: 180, overflowY: 'auto' }}>
        {filtered.length === 0 && (
          <div style={{ padding: '10px', fontSize: 11, color: theme.muted, textAlign: 'center' }}>
            No matches
          </div>
        )}
        {filtered.map((o) => {
          const val = o.value ?? o;
          const lbl = o.label ?? o;
          const tip = o.title ?? val;
          const checked = selected.includes(val);
          return (
            <label key={val} title={tip} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
              cursor: 'pointer', fontSize: 12, color: theme.text,
              background: checked ? `${theme.accent}18` : 'transparent',
            }}>
              <input type="checkbox" checked={checked} onChange={() => toggle(val)} />
              <span style={{ whiteSpace: 'normal', lineHeight: 1.35 }}>{lbl}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

// value / min / max shape: { year, month, day }
// Three-level navigation: day → month → year
function DatePicker({ value, onChange, min, max, theme }) {
  const [open,       setOpen]      = useState(false);
  const [popupPos,   setPopupPos]  = useState({});
  const [mode,       setMode]      = useState('day');   // 'day' | 'month' | 'year'
  const [view,       setView]      = useState({ year: value.year, month: value.month });
  const triggerRef = useRef(null);
  const popupRef   = useRef(null);

  useEffect(() => {
    const close = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        popupRef.current   && !popupRef.current.contains(e.target)
      ) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const toggle = () => {
    setView({ year: value.year, month: value.month });
    setMode('day');
    setOpen((o) => {
      if (!o && triggerRef.current) {
        const rect        = triggerRef.current.getBoundingClientRect();
        const popupH      = 280;
        const spaceBelow  = window.innerHeight - rect.bottom;
        if (spaceBelow < popupH) {
          setPopupPos({ bottom: window.innerHeight - rect.top + 4, left: rect.left });
        } else {
          setPopupPos({ top: rect.bottom + 4, left: rect.left });
        }
      }
      return !o;
    });
  };

  // ── Day-view helpers ──────────────────────────────────────────────────────
  const prevMonth = () => setView((v) =>
    v.month === 1 ? { year: v.year - 1, month: 12 } : { ...v, month: v.month - 1 }
  );
  const nextMonth = () => setView((v) =>
    v.month === 12 ? { year: v.year + 1, month: 1 } : { ...v, month: v.month + 1 }
  );
  const isDayDisabled = (day) => {
    const ord = view.year * 10000 + view.month * 100 + day;
    if (min && ord < dateOrd(min)) return true;
    if (max && ord > dateOrd(max)) return true;
    return false;
  };
  const daysInMonth = new Date(view.year, view.month, 0).getDate();
  const firstDow    = new Date(view.year, view.month - 1, 1).getDay();
  const dayCells    = [...Array(firstDow).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];

  // ── Year-view helpers ─────────────────────────────────────────────────────
  const YR_PAGE = 12;
  const yearPageStart = Math.floor(view.year / YR_PAGE) * YR_PAGE;

  // ── Shared styles ─────────────────────────────────────────────────────────
  const navBtn = (onClick, icon) => (
    <button onClick={onClick} style={{
      background: 'none', border: `1px solid ${theme.border}`, borderRadius: 4,
      width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center',
      cursor: 'pointer', color: theme.muted, padding: 0, flexShrink: 0,
    }}>{icon}</button>
  );

  const drillBtn = (label, onClick) => (
    <button
      onClick={onClick}
      onMouseEnter={(e) => { e.currentTarget.style.background = `${theme.accent}18`; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
      style={{
        background: 'transparent', border: 'none', borderRadius: 4,
        fontSize: 12, fontWeight: 600, color: theme.text,
        cursor: 'pointer', padding: '3px 8px', fontFamily: 'inherit',
      }}
    >{label}</button>
  );

  const gridCell = (label, selected, disabled, onClick) => (
    <button
      key={label}
      disabled={disabled}
      onClick={onClick}
      style={{
        padding: '7px 0', fontSize: 11, textAlign: 'center',
        borderRadius: 4, border: 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        background: selected ? theme.accent : 'transparent',
        color: disabled ? theme.muted : selected ? '#fff' : theme.text,
        fontFamily: 'inherit', fontWeight: selected ? 600 : 400,
        opacity: disabled ? 0.3 : 1,
      }}
    >{label}</button>
  );

  const popup = open && createPortal(
    <div ref={popupRef} style={{
      position: 'fixed', ...popupPos, zIndex: 9999,
      background: theme.surface, border: `1px solid ${theme.border}`,
      borderRadius: 6, boxShadow: '0 8px 24px rgba(0,0,0,0.22)',
      padding: '10px 8px 8px', width: 214, userSelect: 'none',
      fontFamily: '"IBM Plex Sans", system-ui, sans-serif',
    }}>

          {/* ══ DAY VIEW ══ */}
          {mode === 'day' && (<>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              {navBtn(prevMonth, <ChevronLeft size={13} />)}
              {drillBtn(`${MONTHS_SHORT[view.month - 1]} ${view.year}`, () => setMode('month'))}
              {navBtn(nextMonth, <ChevronRight size={13} />)}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', marginBottom: 2 }}>
              {DOW.map((d) => (
                <div key={d} style={{ textAlign: 'center', fontSize: 10, fontWeight: 600, color: theme.muted, padding: '2px 0' }}>{d}</div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1 }}>
              {dayCells.map((day, i) => {
                if (!day) return <div key={i} />;
                const disabled = isDayDisabled(day);
                const selected = view.year === value.year && view.month === value.month && day === value.day;
                return gridCell(day, selected, disabled, () => {
                  if (!disabled) { onChange({ year: view.year, month: view.month, day }); setOpen(false); }
                });
              })}
            </div>
          </>)}

          {/* ══ MONTH VIEW ══ */}
          {mode === 'month' && (<>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              {navBtn(() => setView((v) => ({ ...v, year: v.year - 1 })), <ChevronLeft size={13} />)}
              {drillBtn(String(view.year), () => setMode('year'))}
              {navBtn(() => setView((v) => ({ ...v, year: v.year + 1 })), <ChevronRight size={13} />)}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
              {MONTHS_SHORT.map((m, i) => {
                const month    = i + 1;
                const selected = view.year === value.year && month === value.month;
                return gridCell(m, selected, false, () => {
                  setView((v) => ({ ...v, month }));
                  setMode('day');
                });
              })}
            </div>
          </>)}

          {/* ══ YEAR VIEW ══ */}
          {mode === 'year' && (<>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              {navBtn(() => setView((v) => ({ ...v, year: v.year - YR_PAGE })), <ChevronLeft size={13} />)}
              <span style={{ fontSize: 12, fontWeight: 600, color: theme.text }}>
                {yearPageStart} – {yearPageStart + YR_PAGE - 1}
              </span>
              {navBtn(() => setView((v) => ({ ...v, year: v.year + YR_PAGE })), <ChevronRight size={13} />)}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
              {Array.from({ length: YR_PAGE }, (_, i) => yearPageStart + i).map((yr) =>
                gridCell(yr, yr === value.year, false, () => {
                  setView((v) => ({ ...v, year: yr }));
                  setMode('month');
                })
              )}
            </div>
          </>)}

    </div>,
    document.body
  );

  return (
    <div ref={triggerRef}>
      {/* ── Trigger ── */}
      <button onClick={toggle} style={{
        width: '100%', padding: '7px 10px', fontSize: 12,
        background: theme.surface, color: theme.text,
        border: `1px solid ${open ? theme.accent : theme.border}`, borderRadius: 4,
        textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        transition: 'border-color 0.15s',
      }}>
        <span>{String(value.day).padStart(2, '0')} {MONTHS_SHORT[value.month - 1]} {value.year}</span>
        <ChevronDown size={12} style={{ color: theme.muted, flexShrink: 0, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
      </button>
      {popup}
    </div>
  );
}

export default function Dashboard({ onLogout }) {
  const [themeKey, setThemeKey]       = useState('institutional');
  const theme = THEMES[themeKey];

  const [categories, setCategories]   = useState([]);
  const [activeCategory, setActive]   = useState('');
  const [indicators, setIndicators]   = useState([]);
  const [locations, setLocations]     = useState([]);
  const [units, setUnits]             = useState([]);

  // Query params
  const [selectedInds, setSelectedInds] = useState([]);
  const [location, setLocation]         = useState('');
  const _today = new Date();
  const [startDate, setStartDate]       = useState({ year: 2015, month: 1, day: 1 });
  const [endDate,   setEndDate]         = useState({ year: _today.getFullYear(), month: _today.getMonth() + 1, day: _today.getDate() });
  const [aggregation, setAggregation]   = useState('monthly');
  const [unitFilter, setUnitFilter]     = useState('');

  const handleStartChange = (d) => {
    setStartDate(d);
    if (dateOrd(d) > dateOrd(endDate)) setEndDate(d);
  };
  const handleEndChange = (d) => {
    setEndDate(d);
    if (dateOrd(d) < dateOrd(startDate)) setStartDate(d);
  };

  // Results
  const [chartData, setChartData]     = useState([]);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState('');
  const [visualized, setVisualized]   = useState(false);

  // Key indicators panel
  const [highlights,  setHighlights]  = useState([]);
  const [hlLoading,   setHlLoading]   = useState(false);

  // Load categories once
  useEffect(() => {
    fetchCategories()
      .then((r) => {
        setCategories(r.categories);
        if (r.categories.length) setActive(r.categories[0].id);
      })
      .catch(() => {});
  }, []);

  // Load indicators + locations + units when category changes
  useEffect(() => {
    if (!activeCategory) return;
    setSelectedInds([]);
    setVisualized(false);
    setChartData([]);
    setError('');

    // National Accounts has no monthly data — bump to quarterly if needed
    if (activeCategory === 'National Accounts' && aggregation === 'monthly') {
      setAggregation('quarterly');
    }

    Promise.allSettled([
      fetchIndicators(activeCategory),
      fetchLocations(),
      fetchUnits(activeCategory),
    ]).then(([indsR, locsR, unsR]) => {
      if (indsR.status === 'fulfilled') setIndicators(indsR.value);
      else setIndicators([]);
      if (locsR.status === 'fulfilled') {
        const locs_list = locsR.value.locations || [];
        setLocations(locs_list);
        if (!location && locs_list.length)
          setLocation(locs_list.includes('Tanzania') ? 'Tanzania' : locs_list[0]);
      }
      setUnits(unsR.status === 'fulfilled' ? unsR.value.units || [] : []);
    });
  }, [activeCategory]);

  // Populates the right-hand Key Indicators panel.
  // National Accounts: fetches 3 years of quarterly data, displays levels in TZS Trillion
  //   plus a YoY % growth rate computed against the same quarter of the prior year.
  // All other categories: fetches 2 years of monthly data, displays latest level and
  //   the change vs the immediately preceding period.
  useEffect(() => {
    if (!activeCategory || !indicators.length) return;

    // Match indicators in the order defined by CATEGORY_HIGHLIGHTS.
    // Normalize ampersands/underscores so "Exports of Goods & Services" and
    // "exports_of_goods_and_services" both match pattern "EXPORTS OF GOODS AND SERVICES".
    const norm = (s) => (s || '').toUpperCase().replace(/&/g, 'AND').replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
    const patterns = CATEGORY_HIGHLIGHTS[activeCategory] || [];
    const used = new Set();
    const matched = patterns
      .map(p => {
        const pn = norm(p);
        // Prefer a prefix match; fall back to substring match (takes the first
        // candidate whose name OR description contains the phrase).
        const byPrefix = indicators.find(ind =>
          !used.has(ind.INDICATOR_NAME) &&
          (norm(ind.INDICATOR_NAME).startsWith(pn) || norm(ind.DESCRIPTION).startsWith(pn))
        );
        const hit = byPrefix || indicators.find(ind =>
          !used.has(ind.INDICATOR_NAME) &&
          (norm(ind.INDICATOR_NAME).includes(pn) || norm(ind.DESCRIPTION).includes(pn))
        );
        if (hit) used.add(hit.INDICATOR_NAME);
        return hit;
      })
      .filter(Boolean);

    if (!matched.length) return;

    setHlLoading(true);
    const now    = new Date();
    const isGDP  = activeCategory === 'National Accounts';
    // Need 3 years for National Accounts so same-quarter-last-year data is available
    const start  = new Date(now.getFullYear() - (isGDP ? 3 : 2), now.getMonth(), 1);

    fetchData({
      category:        activeCategory,
      start_year:      start.getFullYear(),
      start_month:     start.getMonth() + 1,
      start_day:       1,
      end_year:        now.getFullYear(),
      end_month:       now.getMonth() + 1,
      end_day:         now.getDate(),
      indicator_names: matched.map(i => i.INDICATOR_NAME),
      aggregation:     isGDP ? 'quarterly' : 'monthly',
      location:        location || 'Tanzania',
    })
      .then(res => {
        const rows = res.data || [];

        // Group rows by indicator name for easy lookup
        const byInd = {};
        rows.forEach(r => {
          if (!byInd[r.INDICATOR_NAME]) byInd[r.INDICATOR_NAME] = [];
          byInd[r.INDICATOR_NAME].push(r);
        });

        const items = matched.map(ind => {
          const sorted = (byInd[ind.INDICATOR_NAME] || [])
            .sort((a, b) => String(b.TIME_PERIOD).localeCompare(String(a.TIME_PERIOD)));
          if (!sorted.length) return null;
          const latest  = sorted[0];
          const rawUnit = latest.UNIT || '';

          // National Accounts values come in TZS Million — convert to TZS Trillion
          const isMillion = rawUnit.trim().toUpperCase() === 'TZS MILLION';
          const scale = (isMillion && isGDP) ? 1_000_000 : 1;
          const unit  = (isMillion && isGDP) ? 'TZS Trillion' : rawUnit;

          let prevValue = null;
          let yoyPct    = null;

          if (isGDP) {
            // For National Accounts: compare against the same quarter in the prior year
            const m = String(latest.TIME_PERIOD).match(/^(\d{4})Q(\d)$/);
            if (m) {
              const prevYearTp  = `${parseInt(m[1]) - 1}Q${m[2]}`;
              const prevYearRow = sorted.find(r => String(r.TIME_PERIOD) === prevYearTp);
              prevValue = prevYearRow?.VALUE != null ? prevYearRow.VALUE / scale : null;
              // YoY % growth rate shown as a secondary line in the card
              if (prevYearRow?.VALUE) yoyPct = (latest.VALUE - prevYearRow.VALUE) / Math.abs(prevYearRow.VALUE) * 100;
            }
          } else {
            // All other categories: compare against the immediately preceding period
            const prev = sorted[1] ?? null;
            prevValue  = prev?.VALUE != null ? prev.VALUE / scale : null;
          }

          return {
            name:      ind.DESCRIPTION || ind.INDICATOR_NAME,
            value:     latest.VALUE != null ? latest.VALUE / scale : null,
            unit,
            period:    latest.TIME_PERIOD,
            prevValue, // drives the bottom-right delta arrow
            yoyPct,    // non-null only for National Accounts
          };
        }).filter(Boolean);

        setHighlights(items);
      })
      .catch(() => {})
      .finally(() => setHlLoading(false));
  }, [activeCategory, indicators, location]);

  const handleVisualize = useCallback(async () => {
    setError('');
    setLoading(true);
    try {
      const res = await fetchData({
        category: activeCategory,
        start_year:  startDate.year,
        start_month: startDate.month,
        start_day:   startDate.day,
        end_year:    endDate.year,
        end_month:   endDate.month,
        end_day:     endDate.day,
        location,
        indicator_names: selectedInds.length ? selectedInds : undefined,
        unit_names: unitFilter ? [unitFilter] : undefined,
        aggregation,
      });
      setChartData(res.data || []);
      setVisualized(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [activeCategory, startDate, endDate, location, selectedInds, unitFilter, aggregation]);

  const handleLogout = async () => {
    await logout();
    onLogout();
  };

  // Group chart data by unit for multi-panel layout; attach indicator metadata
  const panels = (() => {
    if (!chartData.length) return [];
    const byUnit = {};
    chartData.forEach((r) => {
      const u = r.UNIT || 'Value';
      if (!byUnit[u]) byUnit[u] = [];
      byUnit[u].push(r);
    });
    return Object.entries(byUnit).map(([unit, data]) => {
      // Indicator names that appear in this panel
      const panelIndNames = new Set(data.map((r) => r.INDICATOR_NAME).filter(Boolean));
      // Match against full indicator metadata (which has DESCRIPTION, DEFINITION)
      const panelInds = indicators.filter((i) => panelIndNames.has(i.INDICATOR_NAME));
      const meta = {
        category:    activeCategory,
        location,
        aggregation,
        startDate,
        endDate,
        unit,
        indicators:  panelInds,
      };
      return { unit, data, meta };
    });
  })();

  const activeLabel = categories.find((c) => c.id === activeCategory)?.label || '';

  return (
    <div style={{ minHeight: '100vh', background: theme.bg, fontFamily: '"IBM Plex Sans", system-ui, sans-serif', color: theme.text }}>

      {/* ── Header ── */}
      <div style={{ background: theme.heroBg, color: theme.heroText, padding: '0 24px', position: 'sticky', top: 0, zIndex: 50, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56 }}>
          <div>
            <div style={{ fontFamily: 'Georgia, serif', fontSize: 16, fontWeight: 600 }}>Statistics</div>
            <div style={{ fontSize: 10, opacity: 0.65, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Bank of Tanzania</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Theme switcher */}
            <div style={{ display: 'flex', gap: 6 }}>
              {Object.keys(THEMES).map((k) => (
                <button key={k} onClick={() => setThemeKey(k)}
                  style={{
                    padding: '3px 10px', fontSize: 10, borderRadius: 4, border: `1px solid ${theme.heroAccent}`,
                    background: themeKey === k ? theme.heroAccent : 'transparent',
                    color: themeKey === k ? theme.heroBg : theme.heroAccent,
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>{THEMES[k].name}</button>
              ))}
            </div>
            <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'rgba(255,255,255,0.12)', border: 'none', borderRadius: 4, padding: '6px 12px', color: theme.heroText, cursor: 'pointer', fontSize: 12, fontFamily: 'inherit' }}>
              <LogOut size={13} /> Sign out
            </button>
          </div>
        </div>
      </div>

      {/* ── Category Tabs ── */}
      <div style={{ background: theme.surface, borderBottom: `1px solid ${theme.border}`, overflowX: 'auto' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', padding: '0 24px' }}>
          {categories.map((cat) => {
            const active = cat.id === activeCategory;
            return (
              <button key={cat.id} onClick={() => setActive(cat.id)}
                style={{
                  padding: '14px 18px', fontSize: 12, fontWeight: active ? 600 : 400,
                  color: active ? theme.tabActive : theme.muted,
                  borderBottom: active ? `3px solid ${theme.tabActiveBorder}` : '3px solid transparent',
                  background: 'none', border: 'none', borderRadius: 0,
                  cursor: 'pointer', whiteSpace: 'nowrap', fontFamily: 'inherit',
                  transition: 'color 0.15s',
                }}>
                {cat.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '20px 24px', display: 'flex', gap: 18, alignItems: 'flex-start' }}>

        {/* Payment Statistics has no data uploaded yet — show empty state and skip
            the query builder / key indicators panel. */}
        {activeCategory === 'Payment Statistics' ? (
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ background: theme.surface, border: `1px dashed ${theme.border}`, borderRadius: 6, padding: 64, textAlign: 'center', color: theme.muted }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📭</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: theme.text, marginBottom: 6 }}>{activeLabel}</div>
              <div style={{ fontSize: 12 }}>No data has been uploaded for this category yet.</div>
            </div>
          </div>
        ) : (
        <>
        {/* ── Left Sidebar ── */}
        <div style={{ width: 260, flexShrink: 0, background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 6, padding: 16, position: 'sticky', top: 76 }}>

          <div style={{ fontSize: 12, fontWeight: 600, color: theme.text, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Settings size={13} /> Query Builder
          </div>

          {/* Indicators */}
          <div style={{ marginBottom: 14 }}>
            <Label theme={theme}>Indicators ({selectedInds.length} selected)</Label>
            {indicators.length === 0
              ? <div style={{ fontSize: 11, color: theme.muted }}>Loading…</div>
              : <MultiCheckList
                  options={indicators.map((i) => ({ value: i.INDICATOR_NAME, label: i.DESCRIPTION || i.INDICATOR_NAME, title: i.INDICATOR_NAME }))}
                  selected={selectedInds}
                  onChange={setSelectedInds}
                  theme={theme}
                />
            }
          </div>

          {/* Location */}
          <div style={{ marginBottom: 12 }}>
            <Label theme={theme}>Location</Label>
            <Select value={location} onChange={setLocation} options={locations} theme={theme} />
          </div>

          {/* Aggregation */}
          <div style={{ marginBottom: 12 }}>
            <Label theme={theme}>Frequency</Label>
            <Select value={aggregation} onChange={setAggregation} theme={theme}
              options={AGGREGATIONS
                .filter((a) => !(activeCategory === 'National Accounts' && a === 'monthly'))
                .map((a) => ({ value: a, label: AGG_LABELS[a] }))} />
          </div>

          {/* Period range */}
          <div style={{ marginBottom: 12 }}>
            <Label theme={theme}>Period</Label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ fontSize: 10, color: theme.muted, marginBottom: 3 }}>From</div>
                <DatePicker value={startDate} onChange={handleStartChange} max={endDate} theme={theme} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: theme.muted, marginBottom: 3 }}>To</div>
                <DatePicker value={endDate} onChange={handleEndChange} min={startDate} theme={theme} />
              </div>
            </div>
          </div>

          {/* Unit filter */}
          {units.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <Label theme={theme}>Unit filter</Label>
              <Select value={unitFilter} onChange={setUnitFilter} theme={theme}
                placeholder="All units"
                options={units.map((u) => ({ value: u, label: u }))} />
            </div>
          )}

          {/* Actions */}
          <button onClick={handleVisualize} disabled={loading}
            style={{
              width: '100%', padding: '10px', background: loading ? theme.border : theme.buttonBg,
              color: loading ? theme.muted : theme.buttonText, border: 'none', borderRadius: 4,
              fontSize: 12, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              letterSpacing: '0.04em', textTransform: 'uppercase', fontFamily: 'inherit',
            }}>
            <Play size={13} /> {loading ? 'Loading…' : 'Load & Visualize'}
          </button>

          {visualized && (
            <button onClick={() => { setVisualized(false); setChartData([]); setSelectedInds([]); }}
              style={{ width: '100%', marginTop: 8, padding: '7px', background: 'none', border: `1px solid ${theme.border}`, borderRadius: 4, fontSize: 11, color: theme.muted, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, fontFamily: 'inherit' }}>
              <RotateCcw size={11} /> Reset
            </button>
          )}
        </div>

        {/* ── Main Area ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {error && (
            <div style={{ background: '#fff5f5', border: '1px solid #fca5a5', borderRadius: 6, padding: '10px 14px', fontSize: 12, color: '#dc2626', marginBottom: 14 }}>
              {error}
            </div>
          )}

          {!visualized && (
            <div style={{ background: theme.surface, border: `1px dashed ${theme.border}`, borderRadius: 6, padding: 48, textAlign: 'center', color: theme.muted }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📊</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: theme.text, marginBottom: 6 }}>{activeLabel}</div>
              <div style={{ fontSize: 12 }}>Select indicators and click <strong>Load &amp; Visualize</strong> to see charts.</div>
            </div>
          )}

          {visualized && panels.length === 0 && !loading && (
            <div style={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 6, padding: 32, textAlign: 'center', color: theme.muted, fontSize: 13 }}>
              No data returned for the selected filters.
            </div>
          )}

          {visualized && panels.length > 0 && (
            <>
              {/* ── Download bar (single file, all panels combined) ── */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8, marginBottom: 12 }}>
                <span style={{ fontSize: 11, color: theme.muted, marginRight: 4 }}>Download all data:</span>
                <button
                  onClick={() => {
                    const allData = panels.flatMap((p) => p.data);
                    const allInds = indicators.filter((i) =>
                      new Set(allData.map((r) => r.INDICATOR_NAME)).has(i.INDICATOR_NAME)
                    );
                    const allUnits  = [...new Set(allData.map((r) => r.UNIT).filter(Boolean))].join(', ');
                    const allSource = [...new Set(allData.map((r) => r.SOURCE).filter(Boolean))].join('; ');
                    const allFreq   = allData[0]?.FREQUENCY ?? '';
                    const meta = { category: activeCategory, location, aggregation, startDate, endDate, unit: allUnits, source: allSource, frequency: allFreq, indicators: allInds };
                    downloadCSV(toWideFormat(allData, meta), meta, activeLabel);
                  }}
                  style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', fontSize: 12, background: 'none', border: `1px solid ${theme.border}`, borderRadius: 4, cursor: 'pointer', color: theme.text, fontFamily: 'inherit' }}>
                  <Download size={13} /> CSV
                </button>
                <button
                  onClick={() => {
                    const allData = panels.flatMap((p) => p.data);
                    const allInds = indicators.filter((i) =>
                      new Set(allData.map((r) => r.INDICATOR_NAME)).has(i.INDICATOR_NAME)
                    );
                    const allUnits  = [...new Set(allData.map((r) => r.UNIT).filter(Boolean))].join(', ');
                    const allSource = [...new Set(allData.map((r) => r.SOURCE).filter(Boolean))].join('; ');
                    const allFreq   = allData[0]?.FREQUENCY ?? '';
                    const meta = { category: activeCategory, location, aggregation, startDate, endDate, unit: allUnits, source: allSource, frequency: allFreq, indicators: allInds };
                    downloadExcel(toWideFormat(allData, meta), meta, activeLabel);
                  }}
                  style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', fontSize: 12, background: 'none', border: `1px solid ${theme.border}`, borderRadius: 4, cursor: 'pointer', color: theme.text, fontFamily: 'inherit' }}>
                  <FileSpreadsheet size={13} /> Excel
                </button>
              </div>

              {/* ── Chart panels ── */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: panels.length > 1 ? 'repeat(2, minmax(0, 1fr))' : '1fr',
                gap: 16,
                alignItems: 'flex-start',
              }}>
                {panels.map(({ unit, data, meta }) => (
                  <ChartPanel key={unit} title={`${activeLabel} — ${unit}`} data={data} theme={theme} frequency={aggregation} defaultFlex={panels.length === 1} indicators={meta.indicators} unit={unit} />
                ))}
              </div>
            </>
          )}
        </div>

        {/* ── Right: Key Indicators Panel ── */}
        <KeyIndicatorsPanel
          items={highlights}
          loading={hlLoading}
          activeCategory={activeCategory}
          theme={theme}
        />
        </>
        )}

      </div>

      {/* ── Footer ── */}
      <div style={{ background: theme.heroBg, color: theme.heroText, padding: '12px 24px', marginTop: 32, fontSize: 10, textAlign: 'center', opacity: 0.75, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
        Bank of Tanzania · Statistics · {new Date().getFullYear()}
      </div>
    </div>
  );
}
