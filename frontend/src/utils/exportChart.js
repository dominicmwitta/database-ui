function getSvg(containerEl) {
  return containerEl?.querySelector('svg') ?? null;
}

function serializeSvg(svg) {
  const clone = svg.cloneNode(true);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('width', '100%');
  bg.setAttribute('height', '100%');
  bg.setAttribute('fill', '#ffffff');
  clone.insertBefore(bg, clone.firstChild);
  return new XMLSerializer().serializeToString(clone);
}

function svgToCanvas(svg, scale = 2) {
  return new Promise((resolve, reject) => {
    const svgStr = serializeSvg(svg);
    const w = svg.clientWidth  || svg.getBoundingClientRect().width  || 800;
    const h = svg.clientHeight || svg.getBoundingClientRect().height || 400;

    const canvas = document.createElement('canvas');
    canvas.width  = w * scale;
    canvas.height = h * scale;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(scale, scale);

    const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const img  = new Image();
    img.onload  = () => { ctx.drawImage(img, 0, 0, w, h); URL.revokeObjectURL(url); resolve({ canvas, w, h }); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('SVG render failed')); };
    img.src = url;
  });
}

function triggerDownload(url, filename) {
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function exportSVG(containerEl, filename) {
  const svg = getSvg(containerEl);
  if (!svg) return;
  const blob = new Blob([serializeSvg(svg)], { type: 'image/svg+xml' });
  triggerDownload(URL.createObjectURL(blob), `${filename}.svg`);
}

export async function exportPNG(containerEl, filename) {
  const svg = getSvg(containerEl);
  if (!svg) return;
  const { canvas } = await svgToCanvas(svg, 2);
  canvas.toBlob((b) => triggerDownload(URL.createObjectURL(b), `${filename}.png`), 'image/png');
}

export async function exportJPEG(containerEl, filename) {
  const svg = getSvg(containerEl);
  if (!svg) return;
  const { canvas } = await svgToCanvas(svg, 2);
  canvas.toBlob((b) => triggerDownload(URL.createObjectURL(b), `${filename}.jpg`), 'image/jpeg', 0.92);
}

export async function exportPDF(containerEl, filename) {
  const svg = getSvg(containerEl);
  if (!svg) return;
  const { jsPDF } = await import('jspdf');
  const { canvas, w, h } = await svgToCanvas(svg, 2);
  const imgData = canvas.toDataURL('image/png');

  // A4 landscape or fit to content — use chart aspect ratio
  const margin   = 15;
  const pageW    = w  + margin * 2;
  const pageH    = h  + margin * 2;
  const pdf = new jsPDF({ orientation: pageW > pageH ? 'landscape' : 'portrait', unit: 'pt', format: [pageW, pageH] });
  pdf.addImage(imgData, 'PNG', margin, margin, w, h);
  pdf.save(`${filename}.pdf`);
}
