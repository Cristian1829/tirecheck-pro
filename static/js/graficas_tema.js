// ============================================================================
// Tema de las gráficas (rediseño, fase 4), pensado para el jefe de llantas y el gerente de flota.
// Reglas: azul = cuánto (datos); gris = contexto (meses anteriores, totales, metas);
// verde, ámbar y rojo SOLO cuando hay un juicio (bien / vigilar / actuar).
// Cada gráfica puede llevar encima una frase con la conclusión (taLectura).
// Solo cambia colores y textos: los datos y las consultas al servidor son los mismos.
// ============================================================================
const TA_G = {
  azul: '#1d4ed8', azulClaro: '#b9cbf5', marino: '#0b1830',
  gris: '#94a3b8', grisClaro: '#dbe2ea',
  ok: '#15803d', okClaro: '#bfe3cb', al: '#d97706', cr: '#c0262d',
  texto: '#334155', rejilla: '#edf0f5'
};

function taHexRgb(h) { const n = parseInt(String(h).slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function taRgba(h, a) { const [r, g, b] = taHexRgb(h); return `rgba(${r},${g},${b},${a})`; }
function taMezclar(h, otro, t) {
  const a = taHexRgb(h), b = taHexRgb(otro);
  return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, '0')).join('');
}
// Texto oscuro sobre colores claros y blanco sobre oscuros
function taTextoSobre(color) {
  if (typeof color !== 'string' || color[0] !== '#') return '#ffffff';
  const [r, g, b] = taHexRgb(color);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.6 ? '#0f172a' : '#ffffff';
}
// Último elemento (el mes actual) en color fuerte; los anteriores en gris
function taUltimoEn(n, fuerte = TA_G.azul, suave = TA_G.grisClaro) {
  return Array.from({ length: n }, (_, i) => (i === n - 1 ? fuerte : suave));
}
// El mejor valor resaltado (el mayor, o el menor si «menor es mejor») y el resto en tono claro
function taMejorEn(valores, menorEsMejor = false, fuerte = TA_G.azul, suave = TA_G.azulClaro) {
  const v = (valores || []).map(Number);
  const validos = v.filter(x => Number.isFinite(x) && x > 0);
  if (!validos.length) return v.map(() => suave);
  const mejor = menorEsMejor ? Math.min(...validos) : Math.max(...validos);
  return v.map(x => (x === mejor ? fuerte : suave));
}
// Escala de un solo color para categorías con orden (Original, R1, R2, R3+): más oscuro = más reencauches
function taEscalaAzul(n) {
  return Array.from({ length: n }, (_, i) => taMezclar(TA_G.azul, '#ffffff', 0.72 - (0.72 * i) / Math.max(n - 1, 1)));
}
// Índice del mayor valor (para la frase de conclusión)
function taIndiceMayor(valores, menorEsMejor = false) {
  let idx = -1;
  (valores || []).forEach((x, i) => {
    const n = Number(x);
    if (!Number.isFinite(n) || (menorEsMejor && n <= 0)) return;
    if (idx < 0 || (menorEsMejor ? n < Number(valores[idx]) : n > Number(valores[idx]))) idx = i;
  });
  return idx;
}
// Último valor con dato y el anterior con dato
function taUltimos(valores) {
  const idx = [];
  (valores || []).forEach((v, i) => { if (v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v))) idx.push(i); });
  const u = idx[idx.length - 1], p = idx[idx.length - 2];
  return { i: u, valor: u === undefined ? null : Number(valores[u]), iPrevio: p, previo: p === undefined ? null : Number(valores[p]) };
}
const taSuma = (arr) => (arr || []).reduce((s, v) => s + (Number(v) || 0), 0);
const taFmtN = (v) => Math.round(Number(v) || 0).toLocaleString('es-CO');
const taFmtD = (v, d = 1) => Number(v || 0).toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });
const taPct = (parte, total) => (total > 0 ? Math.round((parte / total) * 100) : 0);

// Valor escrito sobre la barra (texto gris oscuro, sin globo de color)
function taEtiquetaDatos(formatter, opciones = {}) {
  return {
    display: (ctx) => {
      const val = ctx.dataset?.data?.[ctx.dataIndex];
      if (val === null || val === undefined || val === '') return false;
      const num = typeof val === 'number' ? val : parseFloat(val);
      if (!Number.isFinite(num) || (opciones.ocultarCero && num === 0)) return false;
      const n = ctx.dataset?.data?.length || 0;
      if (n > 10) return ctx.dataIndex % 2 === 0 || ctx.dataIndex === n - 1;
      return true;
    },
    anchor: 'end',
    align: (ctx) => (ctx.chart?.options?.indexAxis === 'y' ? 'end' : 'top'),
    offset: 2,
    clamp: true,
    clip: false,
    color: TA_G.texto,
    font: { weight: '600', size: 11 },
    formatter: formatter || ((v) => taFmtN(v))
  };
}

// Frase de conclusión encima de la gráfica, con el icono y el color de su estado
const TA_ICONO_LECTURA = { ok: 'fa-circle-check', al: 'fa-triangle-exclamation', cr: 'fa-circle-exclamation', in: 'fa-circle-info' };
function taLectura(canvasId, estado, texto) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !canvas.parentElement) return;
  const caja = canvas.parentElement;
  let p = document.querySelector(`.ta-lectura[data-para="${canvasId}"]`);
  if (!texto) { if (p) p.remove(); return; }
  if (!p) {
    p = document.createElement('p');
    p.dataset.para = canvasId;
    const padre = caja.parentElement;
    const estilo = window.getComputedStyle(padre);
    const enFila = estilo.display.includes('grid') || (estilo.display.includes('flex') && !estilo.flexDirection.startsWith('column'));
    if (enFila) {
      // En una fila (grid o flex) la frase no puede ser otra columna: la frase y la gráfica van juntas en un contenedor,
      // que hereda el ancho de columna (col-span) que tenía la gráfica
      const envoltura = document.createElement('div');
      envoltura.className = 'ta-lectura-envoltura';
      [...caja.classList].filter(c => /(^|:)col-span-/.test(c)).forEach(c => { caja.classList.remove(c); envoltura.classList.add(c); });
      padre.insertBefore(envoltura, caja);
      envoltura.append(p, caja);
    } else {
      padre.insertBefore(p, caja);
    }
  }
  const e = TA_ICONO_LECTURA[estado] ? estado : 'in';
  p.className = `ta-lectura ${e}`;
  p.innerHTML = `<i class="fa-solid ${TA_ICONO_LECTURA[e]}" aria-hidden="true"></i><span></span>`;
  p.querySelector('span').textContent = texto;
  // La conclusión también queda en la descripción accesible de la gráfica
  const base = canvas.dataset.titulo || canvas.getAttribute('aria-label') || '';
  canvas.setAttribute('aria-label', `${base.split('. Conclusión:')[0]}. Conclusión: ${texto}`);
}

// ---------------------------------------------------------------- Donas
// Colores para categorías sin orden (marcas, medidas): la mayor en azul fuerte y las demás en azules
// cada vez más claros; «Otros/Otras» siempre en gris.
function taColoresCategorias(labels) {
  const n = (labels || []).length;
  const azules = Array.from({ length: n }, (_, i) => taMezclar(TA_G.azul, '#ffffff', Math.min(0.78, (0.78 * i) / Math.max(n - 1, 1))));
  return (labels || []).map((l, i) => (/^otr[oa]s?\b/i.test(String(l || '').trim()) ? TA_G.grisClaro : azules[i]));
}

// Dona con la paleta del rediseño: porcentaje escrito en cada porción (si es de 5 % o más),
// total en el centro, leyenda abajo y en el detalle «n llantas (p %)».
function taDona(labels, data, colores, opciones = {}) {
  const total = taSuma(data);
  return {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colores, borderColor: '#ffffff', borderWidth: 2, hoverOffset: 4 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      layout: { padding: 4 },
      animation: { duration: 600 },
      plugins: {
        centerText: { text: opciones.centro ?? taFmtN(total), subtext: opciones.subtexto || 'Llantas', color: '#101c2e', fontSize: 22 },
        legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle', padding: 10, font: { size: 12, weight: '500' }, color: '#334155' } },
        datalabels: {
          display: (ctx) => total > 0 && (Number(ctx.dataset.data[ctx.dataIndex]) || 0) / total >= 0.05,
          color: (ctx) => taTextoSobre(ctx.dataset.backgroundColor[ctx.dataIndex]),
          font: { weight: '600', size: 11 },
          formatter: (v) => `${taPct(v, total)} %`
        },
        tooltip: { callbacks: { label: (c) => ` ${c.label}: ${taFmtN(c.raw)} ${opciones.unidad || 'llantas'} (${taPct(c.raw, total)} %)` } }
      }
    }
  };
}
