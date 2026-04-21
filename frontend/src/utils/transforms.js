/**
 * All transformations operate on an ordered array of numbers (nulls allowed).
 * They return a same-length array with nulls where output is undefined.
 */

// ── Helpers ───────────────────────────────────────────────────────────────────

function lag(arr, k) {
  return arr.map((_, i) => (i >= k ? arr[i - k] : null));
}

function validMean(arr) {
  const v = arr.filter((x) => x != null && isFinite(x));
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0;
}

// ── HP Filter (Hodrick-Prescott) ───────────────────────────────────────────────
// Solves (I + λ D₂'D₂) τ = y via Cholesky on the banded symmetric matrix.

function hpFilter(y, lambda) {
  const n = y.length;
  if (n < 4) return { trend: [...y], cycle: y.map(() => 0) };

  // Build pentadiagonal bands: d (main), e (off-1), f (off-2)
  const d = new Float64Array(n);
  const e = new Float64Array(n);   // A[i+1, i]
  const f = new Float64Array(n);   // A[i+2, i]

  for (let i = 0; i < n; i++) {
    d[i] = 1 + lambda * (i === 0 || i === n - 1 ? 1 : i === 1 || i === n - 2 ? 5 : 6);
  }
  for (let i = 0; i < n - 1; i++) {
    e[i] = lambda * (i === 0 || i === n - 2 ? -2 : -4);
  }
  for (let i = 0; i < n - 2; i++) {
    f[i] = lambda;
  }

  // Cholesky: A = L Lᵀ  (L lower banded, bandwidth 2)
  const l0 = new Float64Array(n);
  const l1 = new Float64Array(n);
  const l2 = new Float64Array(n);

  for (let j = 0; j < n; j++) {
    let s = d[j];
    if (j >= 1) s -= l1[j - 1] ** 2;
    if (j >= 2) s -= l2[j - 2] ** 2;
    l0[j] = Math.sqrt(Math.max(s, 1e-14));

    if (j < n - 1) {
      let s1 = e[j];
      if (j >= 1) s1 -= l2[j - 1] * l1[j - 1];
      l1[j] = s1 / l0[j];
    }
    if (j < n - 2) l2[j] = f[j] / l0[j];
  }

  // Forward sub: L z = y
  const z = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let s = y[i] ?? 0;
    if (i >= 1) s -= l1[i - 1] * z[i - 1];
    if (i >= 2) s -= l2[i - 2] * z[i - 2];
    z[i] = s / l0[i];
  }

  // Back sub: Lᵀ x = z
  const x = new Float64Array(n);
  for (let i = n - 1; i >= 0; i--) {
    let s = z[i];
    if (i < n - 1) s -= l1[i] * x[i + 1];
    if (i < n - 2) s -= l2[i] * x[i + 2];
    x[i] = s / l0[i];
  }

  const trend = Array.from(x);
  const cycle = y.map((v, i) => (v != null ? v - trend[i] : null));
  return { trend, cycle };
}

// ── Seasonal Adjustment (additive, simple X-11 style) ─────────────────────────
// 1. Centre MA to estimate trend  2. S+I = y - trend  3. Average by season
// 4. Normalise seasonal factors   5. SA = y - seasonal factor

function seasonalAdjust(values, seasonLength) {
  const n = values.length;
  if (n < seasonLength * 2) return values.slice();

  // Step 1: centred MA of length seasonLength
  const half = Math.floor(seasonLength / 2);
  const trend = values.map((_, i) => {
    const from = i - half;
    const to   = i + half;
    if (from < 0 || to >= n) return null;
    const slice = values.slice(from, to + 1).filter((x) => x != null);
    return slice.length ? validMean(slice) : null;
  });

  // Step 2: irregular + seasonal
  const si = values.map((v, i) => (v != null && trend[i] != null ? v - trend[i] : null));

  // Step 3: seasonal means per season position
  const seasonMeans = new Array(seasonLength).fill(0);
  const counts      = new Array(seasonLength).fill(0);
  si.forEach((v, i) => {
    if (v != null) { seasonMeans[i % seasonLength] += v; counts[i % seasonLength]++; }
  });
  for (let s = 0; s < seasonLength; s++) {
    seasonMeans[s] = counts[s] ? seasonMeans[s] / counts[s] : 0;
  }

  // Step 4: normalise so seasonal factors sum to 0
  const mean = validMean(seasonMeans);
  const sf   = seasonMeans.map((v) => v - mean);

  // Step 5: remove seasonal from original
  return values.map((v, i) => (v != null ? v - sf[i % seasonLength] : null));
}

// ── Moving average ────────────────────────────────────────────────────────────

function movingAverage(values, window) {
  return values.map((_, i) => {
    if (i < window - 1) return null;
    const slice = values.slice(i - window + 1, i + 1).filter((x) => x != null);
    return slice.length === window ? validMean(slice) : null;
  });
}

// ── Main transform dispatcher ─────────────────────────────────────────────────

/**
 * @param {number[]} values  - ordered values for ONE series (nulls allowed)
 * @param {string}   id      - transform key
 * @param {object}   opts    - { lambda, frequency }
 * @returns {number[]}       - transformed values, same length
 */
export function applyTransform(values, id, opts = {}) {
  const { lambda = 1600, frequency = 'monthly' } = opts;
  const lagYoY = frequency === 'monthly' ? 12 : frequency === 'quarterly' ? 4 : 1;
  const seasonL = frequency === 'monthly' ? 12 : frequency === 'quarterly' ? 4 : 1;

  switch (id) {
    case 'none':
      return values.slice();

    case 'diff':
      return values.map((v, i) =>
        i === 0 || v == null || values[i - 1] == null ? null : v - values[i - 1]);

    case 'pct':
      return values.map((v, i) => {
        const prev = values[i - 1];
        return i === 0 || v == null || prev == null || prev === 0 ? null : (v - prev) / Math.abs(prev) * 100;
      });

    case 'yoy':
      return values.map((v, i) => {
        const prev = i >= lagYoY ? values[i - lagYoY] : null;
        return v == null || prev == null || prev === 0 ? null : (v - prev) / Math.abs(prev) * 100;
      });

    case 'log':
      return values.map((v) => (v != null && v > 0 ? Math.log(v) : null));

    case 'logdiff':
      return values.map((v, i) => {
        const prev = values[i - 1];
        return i === 0 || v == null || prev == null || v <= 0 || prev <= 0
          ? null : Math.log(v) - Math.log(prev);
      });

    case 'hp_trend': {
      const clean = values.map((v) => (v != null && isFinite(v) ? v : 0));
      return hpFilter(clean, lambda).trend.map((v, i) => (values[i] != null ? v : null));
    }

    case 'hp_cycle': {
      const clean = values.map((v) => (v != null && isFinite(v) ? v : 0));
      return hpFilter(clean, lambda).cycle.map((v, i) => (values[i] != null ? v : null));
    }

    case 'seasonal':
      return seasonalAdjust(values, seasonL);

    case 'ma3':
      return movingAverage(values, 3);

    case 'ma12':
      return movingAverage(values, 12);

    case 'index100': {
      const first = values.find((v) => v != null && isFinite(v) && v !== 0);
      return values.map((v) => (v != null && first ? (v / first) * 100 : null));
    }

    case 'zscore': {
      const valid = values.filter((v) => v != null && isFinite(v));
      if (!valid.length) return values.slice();
      const mean = validMean(valid);
      const std  = Math.sqrt(validMean(valid.map((v) => (v - mean) ** 2)));
      return values.map((v) => (v != null && std > 0 ? (v - mean) / std : null));
    }

    default:
      return values.slice();
  }
}

// ── Transform catalogue ───────────────────────────────────────────────────────

export const TRANSFORMS = [
  { id: 'none',      label: 'None (raw)',                group: 'Basic' },
  { id: 'diff',      label: 'First Difference',          group: 'Basic' },
  { id: 'pct',       label: '% Change (period)',         group: 'Basic' },
  { id: 'yoy',       label: 'Year-on-Year % Change',     group: 'Basic' },
  { id: 'log',       label: 'Log',                       group: 'Basic' },
  { id: 'logdiff',   label: 'Log Difference',            group: 'Basic' },
  { id: 'index100',  label: 'Index (base = 100)',        group: 'Basic' },
  { id: 'zscore',    label: 'Z-score (standardise)',     group: 'Basic' },
  { id: 'ma3',       label: '3-period Moving Average',  group: 'Smoothing' },
  { id: 'ma12',      label: '12-period Moving Average', group: 'Smoothing' },
  { id: 'seasonal',  label: 'Seasonal Adjustment',      group: 'Filtering' },
  { id: 'hp_trend',  label: 'HP Filter — Trend',        group: 'Filtering', hasLambda: true },
  { id: 'hp_cycle',  label: 'HP Filter — Cycle',        group: 'Filtering', hasLambda: true },
];

export const DEFAULT_LAMBDA = {
  monthly:   14400,
  quarterly: 1600,
  annual:    100,
};
