    // =========================================================================
    // CONTROLADOR DE LA SUITE ANALÍTICA DE 20 KPIS (5 PESTAÑAS HOMOLOGADAS)
    // =========================================================================
    // Plugin Centro Métrico para Gráficos Doughnut (Inspirado en Tremor / shadcn / Apple Health)
    const doughnutCenterTextPlugin = {
      id: 'doughnutCenterText',
      beforeDraw(chart) {
        const { ctx, chartArea } = chart;
        if (!chartArea || chart.config.type !== 'doughnut') return;
        const cfg = chart.config.options?.plugins?.centerText;
        if (!cfg || cfg.display === false || (!cfg.text && cfg.text !== 0)) return;

        ctx.save();
        const centerX = (chartArea.left + chartArea.right) / 2;
        const centerY = (chartArea.top + chartArea.bottom) / 2;

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const mainSize = cfg.fontSize || 22;
        ctx.font = `bold ${mainSize}px 'Inter', system-ui, sans-serif`;
        ctx.fillStyle = cfg.color || '#0f172a';
        const offsetY = cfg.subtext ? -8 : 0;
        ctx.fillText(String(cfg.text), centerX, centerY + offsetY);

        if (cfg.subtext) {
          const subSize = cfg.subFontSize || 9.5;
          ctx.font = `700 ${subSize}px 'Inter', system-ui, sans-serif`;
          ctx.fillStyle = cfg.subColor || '#64748b';
          ctx.fillText(String(cfg.subtext).toUpperCase(), centerX, centerY + 13);
        }
        ctx.restore();
      }
    };

    if (typeof Chart !== 'undefined') {
      Chart.defaults.devicePixelRatio = Math.max(window.devicePixelRatio || 1, 2);
      Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
      Chart.defaults.color = '#475569';

      // Estilo de cuadrícula minimalista y moderno (Tremor / shadcn)
      if (Chart.defaults.scale && Chart.defaults.scale.grid) {
        Chart.defaults.scale.grid.color = 'rgba(226, 232, 240, 0.55)';
        Chart.defaults.scale.grid.tickColor = 'transparent';
      }
      if (Chart.defaults.scale && Chart.defaults.scale.border) {
        Chart.defaults.scale.border.display = false;
      }

      // Estilo de leyendas ejecutivas
      if (Chart.defaults.plugins && Chart.defaults.plugins.legend) {
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
        Chart.defaults.plugins.legend.labels.boxWidth = 8;
        Chart.defaults.plugins.legend.labels.boxHeight = 8;
        Chart.defaults.plugins.legend.labels.padding = 12;
      }

      // Estilo de tooltips oscuros HD
      if (Chart.defaults.plugins && Chart.defaults.plugins.tooltip) {
        Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.94)';
        Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
        Chart.defaults.plugins.tooltip.bodyColor = '#f1f5f9';
        Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.12)';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.boxPadding = 4;
        Chart.defaults.plugins.tooltip.usePointStyle = true;
      }

      try {
        Chart.register(doughnutCenterTextPlugin);
      } catch (e) {}

      if (typeof ChartDataLabels !== 'undefined') {
        try {
          Chart.register(ChartDataLabels);
        } catch (e) {
          console.warn('ChartDataLabels ya registrado o error:', e);
        }
      }
    }

    let modoLicenciaSuite = 'FULL'; // 'LIGHT' o 'FULL'
    // true solo si el usuario pidió ver la vista LIGHT con el conmutador. Antes se enviaba la licencia mostrada:
    // tras consultar un cliente LIGHT, los siguientes clientes FULL también salían en LIGHT
    let vistaPreviaLight = false;
    const PESTANAS_SOLO_FULL = [3, 4, 5];
    let unidadSuite = 'km'; // 'km' u 'h' (vehículos medidos por horas de motor)
    const uMed = () => unidadSuite;
    let datosSuite20Actuales = null;
    let subpestanaKpiActiva = 1;
    let agrupacionKpi14Actual = 'marca';
    const instanciasChartsSuite = {};

    function formatCO_Miles(num) {
      if (num === null || num === undefined || isNaN(num)) return '0';
      return Math.round(num).toLocaleString('es-CO');
    }

    function formatCO_Moneda(num) {
      if (num === null || num === undefined || isNaN(num)) return '$ 0';
      return '$ ' + Math.round(num).toLocaleString('es-CO');
    }

    function formatCO_Decimal(num, dec = 1) {
      if (num === null || num === undefined || isNaN(num)) return '0,0';
      return Number(num).toLocaleString('es-CO', { minimumFractionDigits: dec, maximumFractionDigits: dec });
    }

    const animacionCascadaStandard = {
      duration: 850,
      easing: 'easeOutQuart',
      delay: (ctx) => (ctx.type === 'data' && ctx.mode === 'default') ? ctx.dataIndex * 35 : 0
    };

    // Rediseño: el valor va escrito en gris oscuro sobre la barra (sin globo de color); los colores que
    // reciben las llamadas se ignoran a propósito para no tener que tocar cada gráfica.
    function pillDatalabelConfig(bgColor = 'rgba(15, 23, 42, 0.88)', textColor = '#ffffff', formatter = null) {
      if (typeof taEtiquetaDatos === 'function') return taEtiquetaDatos(formatter || ((val) => (val !== null && val !== undefined) ? formatCO_Miles(val) : ''));
      return {
        display: (ctx) => {
          const val = ctx.dataset?.data?.[ctx.dataIndex];
          if (val === null || val === undefined || val === '') return false;
          const num = typeof val === 'number' ? val : parseFloat(val);
          if (isNaN(num)) return false;
          const ds = ctx.dataset;
          if (ds && ds.data && ds.data.length > 10) {
            return (ctx.dataIndex % 2 === 0 || ctx.dataIndex === ds.data.length - 1);
          }
          return true;
        },
        anchor: 'end',
        align: 'top',
        offset: 2,
        clamp: true,
        clip: false,
        backgroundColor: bgColor,
        borderRadius: 5,
        color: textColor,
        font: { weight: '800', size: 10 },
        padding: { top: 2, bottom: 2, left: 6, right: 6 },
        formatter: formatter || ((val) => (val !== null && val !== undefined) ? formatCO_Miles(val) : '')
      };
    }

    // Eje con nombres largos (marcas, causas, tipologías): se acortan con "…"; el nombre completo queda en el tooltip
    function ticksEtiquetaCorta(maxLetras = 14, rotacionMax = 45) {
      return {
        autoSkip: false,
        maxRotation: rotacionMax,
        font: { weight: 'bold', size: 10 },
        callback: function (valor) {
          const texto = String(this.getLabelForValue(valor) ?? '');
          return texto.length > maxLetras ? texto.slice(0, maxLetras - 1) + '…' : texto;
        }
      };
    }

    function destruirChartSuite(chartId) {
      if (instanciasChartsSuite[chartId]) {
        try {
          instanciasChartsSuite[chartId].destroy();
        } catch (e) {}
        delete instanciasChartsSuite[chartId];
      }
    }

    // Aviso sobre cada gráfica que no tiene información para dibujar (sin datos, o todos vacíos o en cero)
    const MSG_SIN_DATOS = 'No hay información suficiente para generar esta gráfica con los filtros seleccionados.';

    function graficoTieneDatos(chart) {
      if (!chart || !(chart.data.datasets || []).length) return false;
      const porPuntos = ['bubble', 'scatter'].includes(chart.config.type);
      if (!porPuntos && !(chart.data.labels || []).length) return false;
      return chart.data.datasets.some(ds => (ds.data || []).some(v => {
        const n = (v !== null && typeof v === 'object') ? (v.y ?? v.r ?? v.x) : v;
        return typeof n === 'number' && isFinite(n) && n !== 0;
      }));
    }

    function marcarGraficasSinDatos(num) {
      document.querySelectorAll(`#subvista-kpi-${num} canvas`).forEach(cv => {
        const caja = cv.parentElement;
        if (!caja) return;
        let aviso = caja.querySelector(':scope > .aviso-sin-datos');
        const sinDatos = !graficoTieneDatos(Chart.getChart(cv));
        if (sinDatos && !aviso) {
          if (getComputedStyle(caja).position === 'static') caja.classList.add('relative');
          aviso = document.createElement('div');
          aviso.className = 'aviso-sin-datos absolute inset-0 flex items-center justify-center text-center px-6 text-xs font-semibold text-slate-400 bg-white/90 rounded-xl';
          aviso.innerHTML = `<span><i class="fa-solid fa-chart-simple mr-1.5"></i>${MSG_SIN_DATOS}</span>`;
          caja.appendChild(aviso);
        }
        if (aviso) aviso.classList.toggle('hidden', !sinDatos);
      });
    }

    function exportarGraficoPngHd(canvasId, filename = 'grafico_kpi') {
      const canvas = document.getElementById(canvasId);
      if (!canvas) {
        mostrarToast('Gráfico no disponible para exportar', true);
        return;
      }
      try {
        const link = document.createElement('a');
        link.download = `${filename}_${fechaLocalISO()}.png`;
        link.href = canvas.toDataURL('image/png', 1.0);
        link.click();
        mostrarToast('📷 Gráfico HD exportado correctamente');
      } catch (e) {
        console.error('Error exportando PNG:', e);
        mostrarToast('No se pudo exportar la imagen', true);
      }
    }

    function exportarMrpExcel() {
      const cli = document.getElementById('filtroKpiCliente')?.value || '';
      const sub = document.getElementById('filtroKpiSubcliente')?.value || '';
      const op = document.getElementById('filtroKpiOperacion')?.value || '';
      const params = new URLSearchParams();
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);

      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (tok) params.append('token', tok);

      window.location.href = `/api/kpis/exportar-mrp-excel?${params.toString()}`;
    }

    // PDF de la suite: recorre las pestañas de la licencia, captura sus gráficos y el servidor arma el informe
    async function exportarKpisPdf() {
      if (!datosSuite20Actuales) {
        mostrarToast('Espere a que carguen los indicadores', true);
        return;
      }
      const btn = document.getElementById('btnExportarKpisPdf');
      if (btn) btn.disabled = true;
      const pestanaOriginal = subpestanaKpiActiva;
      const pestanas = modoLicenciaSuite === 'FULL' ? [1, 2, 3, 4, 5, 6] : [1, 2, 6];
      // Temporizador y no requestAnimationFrame: este se congela si la pestaña del navegador queda en segundo plano
      const esperarCuadro = () => new Promise(r => setTimeout(r, 80));
      const graficos = {};
      // Gráficos de barras con muchas etiquetas que en pantalla van a un tercio del ancho: se capturan anchos
      // para que las etiquetas no se monten unas sobre otras en el PDF
      const capturaAncha = new Set(['canvasKpi13_comparativo', 'canvasKpi14_proy', 'canvasKpi14_kmmm', 'canvasKpi14_cpk',
                                    'canvasKpi15_potencial']);
      mostrarToast('Generando PDF de indicadores...');
      // El PDF sale completo: los KPI que el usuario desmarcó se muestran mientras se capturan sus gráficos
      exportandoPdfKpis = true;
      aplicarVisibilidadKpis();
      try {
        for (const num of pestanas) {
          cambiarSubpestanaKpis(num);
          await esperarCuadro();
          for (const cv of document.querySelectorAll(`#subvista-kpi-${num} canvas`)) {
            const chart = Chart.getChart(cv);
            // Sin datos no se captura: el PDF pone su aviso de "sin datos" en lugar de una gráfica vacía
            if (!chart || !cv.width || !cv.height || !graficoTieneDatos(chart)) continue;
            // Sin animación para capturar el estado final; fondo blanco porque el canvas es transparente
            chart.stop();
            chart.options.animation = false;
            // Chart.js no deja el gráfico más ancho que su contenedor: se agranda el contenedor y luego se restaura
            const caja = capturaAncha.has(cv.id) ? cv.parentElement : null;
            const estiloCaja = caja ? caja.getAttribute('style') : null;
            if (caja) {
              caja.style.width = '1100px';
              caja.style.height = '380px';
              // Si el gráfico sigue animando, Chart.js aplaza el cambio de tamaño: se reintenta unas veces
              for (let intento = 0; intento < 4 && cv.clientWidth < 1000; intento++) {
                if (intento) await esperarCuadro();
                chart.stop();
                chart.resize();
                chart.update('none');
              }
            }
            chart.update('none');
            const lienzo = document.createElement('canvas');
            lienzo.width = cv.width;
            lienzo.height = cv.height;
            const ctx = lienzo.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, lienzo.width, lienzo.height);
            ctx.drawImage(cv, 0, 0);
            graficos[cv.id] = lienzo.toDataURL('image/png');
            if (caja) {
              if (estiloCaja === null) caja.removeAttribute('style');
              else caja.setAttribute('style', estiloCaja);
              chart.resize();
            }
          }
        }
      } finally {
        exportandoPdfKpis = false;
        aplicarVisibilidadKpis();
        cambiarSubpestanaKpis(pestanaOriginal);
      }

      const val = id => {
        const v = document.getElementById(id)?.value || '';
        return v === 'TODOS' ? '' : v;
      };
      const cuerpo = {
        cliente: val('filtroKpiCliente'), subcliente: val('filtroKpiSubcliente'), tipo_operacion: val('filtroKpiOperacion'),
        tipologia: val('filtroKpiTipologia'), marca: val('filtroKpiMarca'), dimension: val('filtroKpiDimension'),
        eje_temporal: val('filtroKpiEjeTemporal') || 'mes', base: val('filtroKpiBase') || 'ultima',
        unidad: val('filtroKpiUnidad') || 'km', agrupar_kpi14: agrupacionKpi14Actual, licencia: modoLicenciaSuite, graficos
      };
      try {
        const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
        const res = await fetch('/api/kpis/exportar-pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(tok ? { 'Authorization': `Bearer ${tok}` } : {}) },
          body: JSON.stringify(cuerpo)
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Error ${res.status}`);
        }
        const blob = await res.blob();
        const nombre = (res.headers.get('Content-Disposition') || '').match(/filename=([^;]+)/)?.[1] || 'TireAnalyze_KPIs.pdf';
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = nombre;
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 5000);
        mostrarToast('📄 PDF de indicadores generado');
      } catch (e) {
        console.error('Error exportando PDF de KPIs:', e);
        mostrarToast(`No se pudo generar el PDF: ${e.message}`, true);
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    // =========================================================================
    // ELEGIR QUÉ KPI VE EL USUARIO
    // El servidor guarda, por usuario, los KPI desmarcados: un indicador nuevo aparece marcado sin hacer nada.
    // =========================================================================
    let catalogoKpisVisibles = null;   // secciones con sus KPI (la misma lista del PDF de KPIs)
    let kpisOcultosUsuario = new Set();
    let exportandoPdfKpis = false;     // mientras se arma el PDF se muestran todos para capturar sus gráficos
    let temporizadorGuardarKpis = null;
    let promesaPreferenciasKpis = null;

    function cabecerasSeleccionKpis() {
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      return tok ? { 'Authorization': `Bearer ${tok}` } : {};
    }

    // Se pide una sola vez por página (cada carga de la suite la llama); si falla, el siguiente intento la vuelve a pedir
    function cargarPreferenciasKpis() {
      if (catalogoKpisVisibles) return Promise.resolve();
      promesaPreferenciasKpis = promesaPreferenciasKpis || (async () => {
        try {
          const res = await fetch('/api/kpis/visibles', { headers: cabecerasSeleccionKpis() });
          if (!res.ok) return;
          const data = await res.json();
          catalogoKpisVisibles = data.secciones || [];
          kpisOcultosUsuario = new Set(data.ocultos || []);
          aplicarVisibilidadKpis();
        } catch (e) {
          console.warn('No se pudo cargar la selección de KPI:', e);
        } finally {
          promesaPreferenciasKpis = null;
        }
      })();
      return promesaPreferenciasKpis;
    }

    function aplicarVisibilidadKpis() {
      const ocultos = exportandoPdfKpis ? new Set() : kpisOcultosUsuario;
      const tarjetas = [...document.querySelectorAll('#vista-kpis [data-kpi]')];
      tarjetas.forEach(el => el.classList.toggle('kpi-oculto-usuario', ocultos.has(el.dataset.kpi)));

      // Filas de dos tarjetas: si queda una sola ocupa todo el ancho; si no queda ninguna, la fila no deja hueco
      new Set(tarjetas.map(el => el.parentElement)).forEach(fila => {
        if (!fila || !fila.classList.contains('grid')) return;
        const enFila = [...fila.children].filter(h => h.dataset.kpi);
        const visibles = enFila.filter(h => !h.classList.contains('kpi-oculto-usuario'));
        enFila.forEach(h => h.classList.toggle('kpi-ancho-completo', visibles.length === 1));
        fila.classList.toggle('kpi-oculto-usuario', visibles.length === 0);
      });

      // Pestaña sin ningún KPI marcado: aviso con acceso directo para elegir
      for (let n = 1; n <= 6; n++) {
        const sub = document.getElementById(`subvista-kpi-${n}`);
        if (!sub) continue;
        const propias = [...sub.querySelectorAll('[data-kpi]')];
        const todasOcultas = propias.length > 0 && propias.every(t => t.classList.contains('kpi-oculto-usuario'));
        let aviso = sub.querySelector(':scope > .kpi-pestana-vacia');
        if (todasOcultas && !aviso) {
          aviso = document.createElement('div');
          aviso.className = 'kpi-pestana-vacia p-6 rounded-3xl bg-white border border-dashed border-slate-300 text-center space-y-3';
          aviso.innerHTML = '<p class="text-sm font-bold text-slate-700">Desmarcó todos los KPI de esta pestaña.</p>'
            + '<button type="button" onclick="abrirModalElegirKpis()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl">'
            + '<i class="fa-solid fa-sliders mr-1"></i>Elegir KPI</button>';
          sub.appendChild(aviso);
        }
        if (aviso) aviso.classList.toggle('hidden', !todasOcultas);
      }

      const badge = document.getElementById('badgeKpisOcultos');
      if (badge) {
        const n = kpisOcultosUsuario.size;
        badge.textContent = `${n} oculto${n === 1 ? '' : 's'}`;
        badge.classList.toggle('hidden', n === 0);
      }
    }

    function renderizarListaElegirKpis() {
      const cont = document.getElementById('listaElegirKpis');
      if (!cont) return;
      if (!catalogoKpisVisibles) {
        cont.innerHTML = '<p class="text-xs text-slate-500">No se pudo cargar la lista de KPI. Intente de nuevo.</p>';
        return;
      }
      const bloqueaFull = modoLicenciaSuite === 'LIGHT';
      cont.innerHTML = catalogoKpisVisibles.map(sec => {
        const bloqueada = sec.solo_full && bloqueaFull;
        const dis = bloqueada ? 'disabled' : '';
        return `<section class="border border-slate-200 rounded-2xl p-3 ${bloqueada ? 'opacity-50' : ''}">
          <label class="flex items-center gap-2 text-xs font-black text-slate-900 ${bloqueada ? '' : 'cursor-pointer'}">
            <input type="checkbox" class="w-4 h-4 shrink-0 accent-indigo-600" data-seccion-kpi="${sec.numero}" ${dis}
                   onchange="marcarSeccionKpis(${sec.numero}, this.checked)">
            <span>${escapeHtml(sec.titulo)}${bloqueada ? ' <span class="text-[10px] font-bold text-amber-700">· Solo licencia FULL / PRO</span>' : ''}</span>
          </label>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-1 mt-2">
            ${sec.kpis.map(k => `<label class="flex items-start gap-2 p-1.5 rounded-lg ${bloqueada ? '' : 'hover:bg-slate-50 cursor-pointer'} text-xs text-slate-700">
                <input type="checkbox" class="mt-0.5 w-4 h-4 shrink-0 accent-indigo-600" data-clave-kpi="${escapeHtml(k.clave)}" ${dis}
                       onchange="marcarKpi(this.dataset.claveKpi, this.checked)">
                <span>${escapeHtml(k.titulo)}</span></label>`).join('')}
          </div></section>`;
      }).join('');
      actualizarCasillasElegirKpis();
    }

    // Estado de las casillas sin redibujar la lista (no se pierde el foco ni el desplazamiento)
    function actualizarCasillasElegirKpis() {
      const cont = document.getElementById('listaElegirKpis');
      if (!cont || !catalogoKpisVisibles) return;
      cont.querySelectorAll('[data-clave-kpi]').forEach(cb => { cb.checked = !kpisOcultosUsuario.has(cb.dataset.claveKpi); });
      catalogoKpisVisibles.forEach(sec => {
        const cb = cont.querySelector(`[data-seccion-kpi="${sec.numero}"]`);
        if (!cb) return;
        const marcados = sec.kpis.filter(k => !kpisOcultosUsuario.has(k.clave)).length;
        cb.checked = marcados === sec.kpis.length;
        cb.indeterminate = marcados > 0 && marcados < sec.kpis.length;
      });
      const total = catalogoKpisVisibles.reduce((a, s) => a + s.kpis.length, 0);
      const lbl = document.getElementById('lblResumenElegirKpis');
      if (lbl) lbl.textContent = `${total - kpisOcultosUsuario.size} de ${total} KPI marcados`;
    }

    function marcarKpi(clave, visible) {
      if (visible) kpisOcultosUsuario.delete(clave);
      else kpisOcultosUsuario.add(clave);
      cambioSeleccionKpis();
    }

    function marcarSeccionKpis(numero, visible) {
      const sec = (catalogoKpisVisibles || []).find(s => s.numero === numero);
      if (!sec) return;
      sec.kpis.forEach(k => visible ? kpisOcultosUsuario.delete(k.clave) : kpisOcultosUsuario.add(k.clave));
      cambioSeleccionKpis();
    }

    function mostrarTodosLosKpis() {
      kpisOcultosUsuario.clear();
      cambioSeleccionKpis();
    }

    // Cada cambio se ve al instante y se guarda medio segundo después (varios clics seguidos = un solo guardado)
    function cambioSeleccionKpis() {
      aplicarVisibilidadKpis();
      actualizarCasillasElegirKpis();
      clearTimeout(temporizadorGuardarKpis);
      temporizadorGuardarKpis = setTimeout(guardarSeleccionKpis, 500);
    }

    async function guardarSeleccionKpis() {
      temporizadorGuardarKpis = null;
      try {
        const res = await fetch('/api/kpis/visibles', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...cabecerasSeleccionKpis() },
          body: JSON.stringify({ ocultos: [...kpisOcultosUsuario] })
        });
        if (!res.ok) throw new Error(`Error ${res.status}`);
      } catch (e) {
        console.error('No se pudo guardar la selección de KPI:', e);
        mostrarToast('No se pudo guardar la selección de KPI', true);
      }
    }

    async function abrirModalElegirKpis() {
      if (!catalogoKpisVisibles) await cargarPreferenciasKpis();
      renderizarListaElegirKpis();
      const m = document.getElementById('modalElegirKpis');
      if (m) { m.classList.remove('hidden'); m.classList.add('flex'); }
    }

    function cerrarModalElegirKpis() {
      const m = document.getElementById('modalElegirKpis');
      if (m) { m.classList.add('hidden'); m.classList.remove('flex'); }
      // Si quedó un guardado pendiente, se hace ya
      if (temporizadorGuardarKpis) {
        clearTimeout(temporizadorGuardarKpis);
        guardarSeleccionKpis();
      }
    }

    function cambiarSubpestanaKpis(num) {
      // Con licencia LIGHT no se puede entrar a las pestañas exclusivas de FULL / PRO
      if (modoLicenciaSuite === 'LIGHT' && PESTANAS_SOLO_FULL.includes(num)) {
        mostrarToast('🔒 Esta pestaña es exclusiva de la licencia FULL / PRO', true);
        return;
      }
      subpestanaKpiActiva = num;
      for (let i = 1; i <= 6; i++) {
        const sub = document.getElementById(`subvista-kpi-${i}`);
        const btn = document.getElementById(`btnSubtabKpi${i}`);
        if (sub) {
          if (i === num) sub.classList.remove('hidden');
          else sub.classList.add('hidden');
        }
        if (btn) {
          const iconBox = btn.querySelector('.subtab-icon-box');
          const title = btn.querySelector('.text-left span:first-child');
          const subTitle = btn.querySelector('.subtab-kpi-sub');
          if (i === num) {
            btn.className = 'subtab-kpi-btn px-4 py-2.5 rounded-xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white border border-indigo-500/30 shadow-md shadow-indigo-950/20 flex items-center space-x-2.5 shrink-0 transition-all scale-[1.02] cursor-pointer';
            if (iconBox) iconBox.className = 'subtab-icon-box w-7 h-7 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs shrink-0 transition-colors';
            if (title) title.className = 'block font-bold text-xs tracking-tight text-white';
            if (subTitle) subTitle.className = 'subtab-kpi-sub block text-[9.5px] font-mono text-indigo-300 opacity-90';
          } else {
            btn.className = 'subtab-kpi-btn px-4 py-2.5 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-white/80 flex items-center space-x-2.5 shrink-0 transition-all cursor-pointer';
            if (iconBox) iconBox.className = 'subtab-icon-box w-7 h-7 rounded-lg bg-slate-200/60 text-slate-500 flex items-center justify-center text-xs shrink-0 transition-colors';
            if (title) title.className = 'block font-bold text-xs tracking-tight text-slate-700';
            if (subTitle) subTitle.className = 'subtab-kpi-sub block text-[9.5px] font-mono text-slate-400';
          }
        }
      }

      sincronizarAvisosLicenciaSubpestanas();

      if (datosSuite20Actuales) {
        renderizarSubpestanaActiva(num, datosSuite20Actuales);
      }
    }

    function sincronizarAvisosLicenciaSubpestanas() {
      const esLight = (modoLicenciaSuite === 'LIGHT');
      const av3 = document.getElementById('bloqueAvisoLicenciaKpi3');
      const av4 = document.getElementById('bloqueAvisoLicenciaKpi4');
      const av5 = document.getElementById('bloqueAvisoLicenciaKpi5');
      if (av3) av3.classList.toggle('hidden', !esLight);
      if (av4) av4.classList.toggle('hidden', !esLight);
      if (av5) av5.classList.toggle('hidden', !esLight);
      // En LIGHT esas pestañas no se recalculan: se oculta su contenido para no dejar a la vista
      // las gráficas del cliente anterior (pasaba al ir de un cliente FULL a uno LIGHT)
      PESTANAS_SOLO_FULL.forEach(n => {
        const sub = document.getElementById(`subvista-kpi-${n}`);
        if (sub) {
          // El aviso de «pestaña sin KPI marcados» lo maneja aplicarVisibilidadKpis
          [...sub.children].forEach(hijo => {
            if (hijo.id !== `bloqueAvisoLicenciaKpi${n}` && !hijo.classList.contains('kpi-pestana-vacia')) {
              hijo.classList.toggle('hidden', esLight);
            }
          });
        }
        // Botón de la pestaña bloqueado en LIGHT
        const btn = document.getElementById(`btnSubtabKpi${n}`);
        if (btn) {
          btn.classList.toggle('opacity-40', esLight);
          btn.classList.toggle('cursor-not-allowed', esLight);
          btn.title = esLight ? 'Exclusivo licencia FULL / PRO' : '';
        }
      });

      // En LIGHT, ocultar KPI 01 padrón o banner
      const kpi01Banner = document.getElementById('kpi01-banner');
      if (kpi01Banner) kpi01Banner.classList.toggle('hidden', esLight);
    }

    function cambiarModoLicenciaSuite(nuevoModo, recargar = true) {
      modoLicenciaSuite = (nuevoModo === 'LIGHT') ? 'LIGHT' : 'FULL';
      // recargar = true: lo pidió el usuario con el conmutador; false: lo impuso el servidor
      if (recargar) vistaPreviaLight = (modoLicenciaSuite === 'LIGHT');
      if (modoLicenciaSuite === 'LIGHT' && PESTANAS_SOLO_FULL.includes(subpestanaKpiActiva)) {
        cambiarSubpestanaKpis(1);
      }
      const badge = document.getElementById('badgeLicenciaActiva');
      const btnLight = document.getElementById('btnModoLight');
      const btnPro = document.getElementById('btnModoPro');

      if (modoLicenciaSuite === 'LIGHT') {
        if (badge) {
          badge.textContent = 'LICENCIA LIGHT (OPERATIVA)';
          badge.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-800 border border-amber-400/40';
        }
        if (btnLight) btnLight.className = 'px-2.5 py-1 rounded-lg font-extrabold bg-amber-500 text-slate-950 shadow transition-all';
        if (btnPro) btnPro.className = 'px-2.5 py-1 rounded-lg font-bold text-slate-600 hover:text-slate-900 transition-all';
      } else {
        if (badge) {
          badge.textContent = 'LICENCIA FULL / PRO';
          badge.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-sky-500/20 text-sky-700 border border-sky-400/40';
        }
        if (btnPro) btnPro.className = 'px-2.5 py-1 rounded-lg font-extrabold bg-blue-600 text-white shadow transition-all';
        if (btnLight) btnLight.className = 'px-2.5 py-1 rounded-lg font-bold text-slate-600 hover:text-slate-900 transition-all';
      }

      sincronizarAvisosLicenciaSubpestanas();
      if (recargar) cargarSuite20Kpis();
    }

    function cambiarAgrupacionKpi14(nuevaAgrup) {
      agrupacionKpi14Actual = nuevaAgrup || 'marca';
      cargarSuite20Kpis();
    }

    function abrirModalPlacasPendientesKpi01() {
      const m = document.getElementById('modalPlacasPendientesKpi01');
      if (m) {
        m.classList.remove('hidden');
        m.classList.add('flex');
      }
    }

    function cerrarModalPlacasPendientesKpi01() {
      const m = document.getElementById('modalPlacasPendientesKpi01');
      if (m) {
        m.classList.add('hidden');
        m.classList.remove('flex');
      }
    }

    // Cada carga lleva un número: si el usuario cambia de filtro antes de que llegue la respuesta,
    // la respuesta vieja se descarta (antes podía pintar los datos de todos los clientes encima del filtrado)
    let consultaSuiteVigente = 0;

    async function cargarSuite20Kpis() {
      const consulta = ++consultaSuiteVigente;
      // La selección de KPI del usuario se pide en paralelo: así los desmarcados no se ven mientras carga la suite
      cargarPreferenciasKpis();
      try {
        const cliVal = document.getElementById('filtroKpiCliente')?.value || '';
        const sedeVal = document.getElementById('filtroKpiSubcliente')?.value || '';
        const opVal = document.getElementById('filtroKpiOperacion')?.value || '';
        const tipVal = document.getElementById('filtroKpiTipologia')?.value || '';
        const marVal = document.getElementById('filtroKpiMarca')?.value || '';
        const dimVal = document.getElementById('filtroKpiDimension')?.value || '';
        const ejeVal = document.getElementById('filtroKpiEjeTemporal')?.value || 'mes';

        const params = new URLSearchParams();
        if (cliVal && cliVal !== 'TODOS') params.append('cliente', cliVal);
        if (sedeVal && sedeVal !== 'TODOS') params.append('subcliente', sedeVal);
        if (opVal && opVal !== 'TODOS') params.append('tipo_operacion', opVal);
        if (tipVal && tipVal !== 'TODOS') params.append('tipologia', tipVal);
        if (marVal && marVal !== 'TODOS') params.append('marca', marVal);
        if (dimVal && dimVal !== 'TODOS') params.append('dimension', dimVal);
        params.append('eje_temporal', ejeVal);
        params.append('base', document.getElementById('filtroKpiBase')?.value || 'ultima');
        params.append('unidad', document.getElementById('filtroKpiUnidad')?.value || 'km');
        params.append('agrupar_kpi14', agrupacionKpi14Actual);
        // Sin licencia el servidor aplica la del cliente (o FULL para el administrador)
        if (vistaPreviaLight) params.append('licencia', 'LIGHT');

        const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
        const headers = tok ? { 'Authorization': `Bearer ${tok}` } : {};

        const res = await fetch(`/api/kpis/suite-20?${params.toString()}`, { headers });
        if (!res.ok) {
          let motivo = '';
          try { motivo = (await res.json()).detail || ''; } catch (e) { /* respuesta sin JSON */ }
          if (consulta !== consultaSuiteVigente) return;
          mostrarErrorSuiteKpis(res.status === 401 ? 'La sesión expiró. Vuelva a ingresar.'
            : `No se pudieron calcular los KPI (error ${res.status})${typeof motivo === 'string' && motivo ? ': ' + motivo : ''}.`);
          return;
        }

        const data = await res.json();
        if (consulta !== consultaSuiteVigente) return;
        mostrarErrorSuiteKpis(null);
        datosSuite20Actuales = data;
        unidadSuite = data.unidad === 'horas' ? 'h' : 'km';

        // La licencia efectiva la decide el servidor según la configuración del cliente
        if (data.licencia && data.licencia !== modoLicenciaSuite) {
          cambiarModoLicenciaSuite(data.licencia, false);
        }
        // El administrador ve todo; se le indica cuando el cliente en realidad tiene LIGHT
        // (se fija en cada respuesta: el aviso no debe quedar pegado al pasar a otro cliente)
        const badge = document.getElementById('badgeLicenciaActiva');
        if (badge) {
          badge.textContent = data.licencia === 'LIGHT' ? 'LICENCIA LIGHT (OPERATIVA)'
            : (data.vista_administrador && data.licencia_cliente === 'LIGHT')
              ? 'VISTA ADMINISTRADOR · CLIENTE CON LICENCIA LIGHT' : 'LICENCIA FULL / PRO';
        }

        renderizarTodaLaSuite20(data);
        aplicarVisibilidadKpis();

      } catch (err) {
        console.error('Error al cargar la Suite de 20 KPIs:', err);
        if (consulta === consultaSuiteVigente) {
          mostrarErrorSuiteKpis('No se pudieron cargar los KPI. Revise la conexión e intente de nuevo.');
        }
      }
    }

    // Con error se ocultan las cifras del filtro anterior y se ofrece reintentar (auditoría H-16);
    // con null se quita el aviso y vuelven a verse las subvistas.
    function mostrarErrorSuiteKpis(mensaje) {
      const caja = document.getElementById('kpiErrorCarga');
      const txt = document.getElementById('kpiErrorCargaTexto');
      if (mensaje) {
        Object.keys(instanciasChartsSuite).forEach(destruirChartSuite);
        datosSuite20Actuales = null;
      }
      document.querySelectorAll('[id^="subvista-kpi-"]').forEach(el => {
        el.style.visibility = mensaje ? 'hidden' : '';
      });
      if (txt) txt.textContent = mensaje || '';
      if (caja) caja.classList.toggle('hidden', !mensaje);
    }

    // Aviso de datos excluidos: cada indicador se calcula solo con las llantas que tienen el dato
    function renderizarCalidadDatosKpi(q) {
      const el = document.getElementById('kpiCalidadDatos');
      if (!el) return;
      if (!q || !q.llantas) { el.classList.add('hidden'); return; }
      const partes = [];
      if (q.sin_psi) partes.push(`${q.sin_psi} sin presión (fuera de los indicadores de presión)`);
      if (q.sin_prof_inicial) partes.push(`${q.sin_prof_inicial} sin profundidad inicial (fuera de desgaste y proyecciones)`);
      if (q.sin_precio) partes.push(`${q.sin_precio} sin precio (fuera de CPK y pérdidas en pesos)`);
      if (q.sin_numero_interno) partes.push(`${q.sin_numero_interno} sin número interno (fuera de la trazabilidad por llanta)`);
      if (q.sin_marca) partes.push(`${q.sin_marca} sin marca (salen como "Sin marca")`);
      if (q.marca_es_banda) partes.push(`${q.marca_es_banda} con una marca de banda de reencauche en el campo marca (${(q.marcas_banda_usadas || []).join(', ')}): corrija la marca de la llanta`);
      if (q.sin_sede) partes.push(`${q.sin_sede} sin sede`);
      if (q.fechas_invalidas) partes.push(`${q.fechas_invalidas} inspecciones con fecha inválida excluidas`);
      el.classList.toggle('hidden', partes.length === 0);
      el.textContent = partes.length ? `⚠️ De ${q.llantas} llantas analizadas: ${partes.join('; ')}.` : '';
    }

    function renderizarTodaLaSuite20(data) {
      // Datos nuevos (otro filtro): ninguna gráfica del filtro anterior queda dibujada en otra pestaña
      Object.keys(instanciasChartsSuite).forEach(destruirChartSuite);
      renderizarCalidadDatosKpi(data.calidad_datos);
      if (!data) return;
      sincronizarAvisosLicenciaSubpestanas();
      if (data.ahorro_roi || data.resumen_ahorro_roi) {
        renderizarBannerAhorroRoi(data.ahorro_roi || data.resumen_ahorro_roi);
      }
      renderizarSubpestanaActiva(subpestanaKpiActiva, data);
    }

    function renderizarSubpestanaActiva(num, data) {
      if (!data) return;
      switch (num) {
        case 1:
          if (data.kpi_01) renderizarKpi01(data.kpi_01);
          if (data.kpi_02) renderChartKpi02(data.kpi_02);
          if (data.kpi_03) renderChartKpi03(data.kpi_03);
          if (data.kpi_04) renderChartKpi04(data.kpi_04);
          break;
        case 2:
          if (data.kpi_05) renderKpi05(data.kpi_05);
          if (data.kpi_06) renderKpi06(data.kpi_06);
          if (data.kpi_07) renderKpi07(data.kpi_07);
          if (data.kpi_08) renderKpi08(data.kpi_08);
          if (data.kpi_09) renderKpi09(data.kpi_09);
          if (data.kpi_10) renderChartKpi10(data.kpi_10);
          if (data.kpi_11) renderChartKpi11(data.kpi_11);
          break;
        case 3:
          if (modoLicenciaSuite === 'FULL') {
            if (data.kpi_12) renderKpi12(data.kpi_12);
            if (data.kpi_13) renderChartKpi13(data.kpi_13);
            if (data.kpi_14) renderChartKpi14(data.kpi_14);
            if (data.kpi_cpk) renderKpiCpk(data.kpi_cpk);
            if (data.kpi_15) renderChartKpi15(data.kpi_15);
            if (data.kpi_16) renderChartKpi16(data.kpi_16);
          }
          break;
        case 4:
          if (modoLicenciaSuite === 'FULL') {
            if (data.kpi_17) renderKpi17(data.kpi_17);
            if (data.kpi_18) { renderChartKpi18(data.kpi_18); renderCarcasasKpi18(data.kpi_18.carcasas); }
            if (data.kpi_19) renderChartKpi19(data.kpi_19);
          }
          break;
        case 5:
          if (modoLicenciaSuite === 'FULL') {
            if (data.kpi_20) renderKpi20(data.kpi_20);
          }
          break;
        case 6:
          if (data.kpi_tendencias) renderTendencias(data.kpi_tendencias);
          break;
      }
      marcarGraficasSinDatos(num);
    }

    // ==========================================
    // RENDERERS SUB-PESTAÑA 1 (KPI 01 AL 04)
    // ==========================================

    // KPI 01: Cumplimiento de Inspección vs Parque, por mes, por año o en todo el historial
    let datosKpi01 = null;

    function renderizarKpi01(d) {
      if (!d) return;
      datosKpi01 = d;
      const sel = document.getElementById('kpi01_periodo');
      if (sel) {
        const previo = sel.value;
        const meses = [...(d.por_mes || [])].reverse();
        const anios = [...(d.por_anio || [])].reverse();
        sel.innerHTML =
          (meses.length ? `<optgroup label="Por mes">${meses.map(m => `<option value="mes:${escapeHtml(m.clave)}">${escapeHtml(m.etiqueta)}${m.clave === d.periodo_actual ? ' (mes actual)' : ''}</option>`).join('')}</optgroup>` : '')
          + (anios.length ? `<optgroup label="Por año">${anios.map(a => `<option value="anio:${escapeHtml(a.clave)}">Año ${escapeHtml(a.clave)}</option>`).join('')}</optgroup>` : '')
          + '<option value="historial">Todo el historial</option>';
        const opciones = [...sel.options].map(o => o.value);
        sel.value = opciones.includes(previo) ? previo : (d.periodo_actual && opciones.includes(`mes:${d.periodo_actual}`) ? `mes:${d.periodo_actual}` : 'historial');
      }
      renderChartKpi01Meses(d);
      aplicarPeriodoKpi01();
    }

    function periodoSeleccionadoKpi01() {
      const d = datosKpi01;
      const valor = document.getElementById('kpi01_periodo')?.value || 'historial';
      if (!d || valor === 'historial') {
        return d ? {
          etiqueta: 'todo el historial', inspeccionados: d.vehiculos_inspeccionados, total: d.total_padron_activo,
          pct: d.porcentaje_cumplimiento, pendientes: d.placas_pendientes || []
        } : null;
      }
      const [tipo, clave] = valor.split(':');
      const lista = tipo === 'anio' ? (d.por_anio || []) : (d.por_mes || []);
      const p = lista.find(x => x.clave === clave);
      if (!p) return null;
      // Los pendientes del periodo llegan como placas: se completan con los datos del parque
      // y la última inspección es la anterior al periodo (no una posterior, p. ej. de noviembre al mirar octubre)
      const previas = p.ultima_previa || {};
      const pendientes = (p.pendientes || []).map(placa => ({ placa, ...((d.parque || {})[placa] || {}), ultima_inspeccion: previas[placa] || '' }));
      return { etiqueta: tipo === 'anio' ? `el año ${clave}` : p.etiqueta, inspeccionados: p.inspeccionados, total: p.total, pct: p.pct, pendientes };
    }

    function aplicarPeriodoKpi01() {
      const d = datosKpi01;
      const per = periodoSeleccionadoKpi01();
      if (!d || !per) return;
      const sinPadron = per.pct === null || per.pct === undefined;
      const pct = sinPadron ? 0 : Math.min(100, Math.max(0, per.pct));
      const elPct = document.getElementById('kpi01_cumplimiento_pct');
      const elAudPad = document.getElementById('kpi01_auditados_padron');
      const elBar = document.getElementById('kpi01_barra_progreso');
      const elBtnTxt = document.getElementById('btnKpi01Texto');
      const elTexto = document.getElementById('kpi01_texto_periodo');
      const elSub = document.getElementById('kpi01_modal_subtitulo');

      if (elTexto) elTexto.textContent = `Inspeccionados en ${per.etiqueta} / Flota`;
      if (elSub) elSub.textContent = `Unidades activas sin inspección en ${per.etiqueta}`;
      if (elPct) {
        elPct.textContent = sinPadron ? 'Sin padrón' : `${formatCO_Decimal(pct, 1)}%`;
        // Sin padrón cargado el parque son los vehículos ya inspeccionados: se avisa
        elPct.title = d.parque_cargado ? 'Contra el parque automotor cargado por el administrador'
          : d.fuente_padron === 'vehiculos_inspeccionados'
            ? 'Sin padrón cargado: el parque son los vehículos ya inspeccionados alguna vez (puede faltar alguno)'
            : (sinPadron ? 'No hay padrón ni vehículos inspeccionados para medir el cumplimiento' : 'Contra el padrón de vehículos del cliente');
      }
      if (elAudPad) elAudPad.textContent = `${formatCO_Miles(per.inspeccionados)} / ${formatCO_Miles(per.total)}`;
      if (elBar) elBar.style.width = `${pct}%`;
      if (elBtnTxt) elBtnTxt.textContent = `Placas Pendientes (${per.pendientes.length})`;
      pendientesKpi01 = per.pendientes;
      const btnExp = document.getElementById('btnExportarPendientesKpi01');
      if (btnExp) btnExp.classList.toggle('hidden', !pendientesKpi01.length);

      // Tabla del modal (con parque cargado salen todos los que faltan)
      const tbody = document.getElementById('tbodyModalPlacasPendientes');
      if (tbody) {
        if (!per.pendientes.length) {
          tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400">¡Excelente! Todos los vehículos de la flota tienen inspección en ${escapeHtml(per.etiqueta)}.</td></tr>`;
        } else {
          const lista = d.parque_cargado ? per.pendientes : per.pendientes.slice(0, 25);
          tbody.innerHTML = lista.map(p => `
            <tr class="hover:bg-slate-50">
              <td class="p-2.5 font-black text-slate-900 font-mono whitespace-nowrap">${escapeHtml(p.placa || '-')}</td>
              <td class="p-2.5 text-slate-600">${escapeHtml(p.subcliente || '-')}</td>
              <td class="p-2.5 text-slate-600">${escapeHtml(p.tipologia || '-')}</td>
              <td class="p-2.5 text-slate-600">${escapeHtml([p.fabricante, p.linea].filter(Boolean).join(' ') || '-')}</td>
              <td class="p-2.5 text-center whitespace-nowrap">${p.ultima_inspeccion ? fmtFecha(p.ultima_inspeccion) : 'Nunca'}</td>
            </tr>
          `).join('');
        }
      }
    }

    // Últimos 12 meses seguidos (los meses sin inspecciones salen en cero, no se saltan)
    function mesesSeguidosKpi01(d) {
      const nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
      const porClave = Object.fromEntries((d.por_mes || []).map(m => [m.clave, m]));
      const ultimo = d.periodo_actual || ((d.por_mes || []).slice(-1)[0] || {}).clave;
      if (!ultimo) return [];
      let [anio, mes] = ultimo.split('-').map(Number);
      const lista = [];
      for (let i = 0; i < 12; i++) {
        const clave = `${anio}-${String(mes).padStart(2, '0')}`;
        lista.unshift(porClave[clave] || {
          clave, etiqueta: `${nombres[mes - 1]} ${String(anio).slice(-2)}`, inspeccionados: 0,
          total: d.total_padron_activo, pct: d.total_padron_activo ? 0 : null
        });
        mes -= 1;
        if (mes === 0) { mes = 12; anio -= 1; }
      }
      return lista;
    }

    // Vehículos inspeccionados cada mes frente al total de la flota (fondo claro para que se lea bien)
    function renderChartKpi01Meses(d) {
      destruirChartSuite('kpi01_meses');
      const ctx = document.getElementById('canvasKpi01_meses');
      const meses = mesesSeguidosKpi01(d);
      const anio = (d.por_anio || []).slice(-1)[0];
      const elAnio = document.getElementById('kpi01_texto_anio');
      if (elAnio) elAnio.textContent = anio ? `Año ${anio.clave}: ${formatCO_Miles(anio.inspeccionados)} de ${formatCO_Miles(anio.total)} vehículos${anio.pct != null ? ` (${formatCO_Decimal(anio.pct, 1)}%)` : ''}` : '';
      if (!ctx || typeof Chart === 'undefined' || !meses.length) return;
      const angosto = window.innerWidth < 640;
      const totalMax = Math.max(1, ...meses.map(m => m.total || 0), ...meses.map(m => m.inspeccionados || 0));
      // Rediseño: el mes actual en azul y los anteriores en gris; la cobertura se lee en la etiqueta y en la frase
      // (si el mes en curso aún no tiene inspecciones, se resalta el último mes con inspecciones)
      let iRes = meses.length - 1;
      while (iRes > 0 && !meses[iRes].inspeccionados) iRes--;
      const colorMes = (m, i) => (i === iRes ? TA_G.azul : TA_G.grisClaro);
      instanciasChartsSuite['kpi01_meses'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: meses.map(m => m.etiqueta),
          datasets: [
            {
              type: 'bar', label: 'Vehículos inspeccionados', data: meses.map(m => m.inspeccionados),
              backgroundColor: meses.map(colorMes), borderRadius: 4, maxBarThickness: 46, order: 2,
              datalabels: {
                anchor: 'end', align: 'end', offset: 2, clamp: true,
                color: c => (c.dataset.data[c.dataIndex] ? '#0f172a' : '#94a3b8'),
                font: { size: angosto ? 9 : 11, weight: 'bold' },
                formatter: (v, c) => {
                  const m = meses[c.dataIndex];
                  if (!v) return '0';  // mes sin inspecciones: un cero discreto
                  return (angosto || m.pct == null) ? formatCO_Miles(v) : `${formatCO_Miles(v)} · ${formatCO_Decimal(m.pct, 0)}%`;
                }
              }
            },
            {
              type: 'line', label: 'Total flota', data: meses.map(m => m.total), borderColor: TA_G.gris, backgroundColor: TA_G.gris,
              borderWidth: 1.5, borderDash: [6, 5], pointRadius: 0, tension: 0, order: 1,
              datalabels: { display: false }
            }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          layout: { padding: { top: 24, right: 12, bottom: 6, left: 6 } },
          plugins: {
            legend: {
              labels: {
                color: '#0f172a', font: { size: 11, weight: 'bold' }, usePointStyle: true, boxWidth: 10,
                // La barra cambia de color según la cobertura: en la leyenda se muestra en verde
                generateLabels: chart => Chart.defaults.plugins.legend.labels.generateLabels(chart).map(l =>
                  l.datasetIndex === 0 ? { ...l, fillStyle: TA_G.azul, strokeStyle: TA_G.azul } : l)
              }
            },
            tooltip: {
              callbacks: {
                label: c => c.dataset.type === 'line' ? `Total flota: ${formatCO_Miles(c.raw)}`
                  : `Inspeccionados: ${formatCO_Miles(c.raw)} de ${formatCO_Miles(meses[c.dataIndex].total)}${meses[c.dataIndex].pct != null ? ` (${formatCO_Decimal(meses[c.dataIndex].pct, 1)}%)` : ''}`
              }
            }
          },
          scales: {
            x: { ticks: { color: '#334155', font: { size: angosto ? 9 : 11, weight: 'bold' }, maxRotation: angosto ? 60 : 0, autoSkip: false }, grid: { display: false } },
            y: {
              beginAtZero: true, suggestedMax: Math.ceil(totalMax * 1.18),
              ticks: { color: '#334155', font: { size: 11 }, precision: 0 }, grid: { color: '#e2e8f0' },
              title: { display: !angosto, text: 'Vehículos', color: '#475569', font: { size: 11, weight: 'bold' } }
            }
          }
        }
      });
      // El mes en curso puede ir en cero: la frase usa el último mes con inspecciones
      const mUlt = [...meses].reverse().find(m => m.total && m.inspeccionados) || [...meses].reverse().find(m => m.total);
      if (mUlt) {
        const faltan = Math.max(0, (mUlt.total || 0) - (mUlt.inspeccionados || 0));
        const p = mUlt.pct != null ? mUlt.pct : taPct(mUlt.inspeccionados, mUlt.total);
        taLectura('canvasKpi01_meses', p >= 95 ? 'ok' : p >= 70 ? 'al' : 'cr',
          `${mUlt.etiqueta}: ${formatCO_Miles(mUlt.inspeccionados)} de ${formatCO_Miles(mUlt.total)} vehículos (${formatCO_Decimal(p, 0)} %).${faltan ? ` Faltan ${formatCO_Miles(faltan)} por inspeccionar.` : ' Toda la flota inspeccionada.'}`);
      }
    }

    let pendientesKpi01 = [];

    // Faltantes del KPI 01 a Excel (CSV con separador ';' para Excel en español)
    function exportarPendientesKpi01() {
      if (!pendientesKpi01.length) return;
      const celda = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const filas = [['Placa / N° interno', 'Sede', 'Tipología', 'Fabricante', 'Línea', 'Última inspección']]
        .concat(pendientesKpi01.map(p => [p.placa, p.subcliente, p.tipologia, p.fabricante, p.linea, p.ultima_inspeccion || 'Nunca']));
      const csv = '\ufeff' + filas.map(f => f.map(celda).join(';')).join('\r\n');
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `Vehiculos_pendientes_${fechaLocalISO()}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    // KPI 02: Volumen Auditado Mes a Mes (Mixto Doble Eje)
    function renderChartKpi02(ds) {
      destruirChartSuite('kpi02');
      const ctx = document.getElementById('canvasKpi02_volumen');
      if (!ctx || !ds) return;

      const badgeRazon = document.getElementById('kpi02_badge_razon');
      if (badgeRazon && ds.promedio_llantas_por_vehiculo !== undefined) {
        badgeRazon.textContent = `Promedio: ${formatCO_Decimal(ds.promedio_llantas_por_vehiculo, 1)} llantas/vehículo`;
      }

      const gradientBar = taUltimoEn((ds.llantas || []).length, TA_G.azul);

      instanciasChartsSuite['kpi02'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Llantas Rodando',
              data: ds.llantas || [],
              backgroundColor: gradientBar,
              borderRadius: 6,
              borderSkipped: false,
              yAxisID: 'y',
              datalabels: pillDatalabelConfig('rgba(30, 64, 175, 0.9)', '#ffffff')
            },
            {
              type: 'line',
              label: 'Vehículos Auditados',
              data: ds.vehiculos || [],
              borderColor: TA_G.gris,
              backgroundColor: TA_G.gris,
              borderWidth: 2,
              tension: 0.35,
              pointBackgroundColor: TA_G.gris,
              pointBorderColor: '#ffffff',
              pointBorderWidth: 2,
              pointRadius: 3,
              yAxisID: 'y1',
              datalabels: { display: false }
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              cornerRadius: 10,
              padding: 12,
              callbacks: {
                afterBody: (items) => {
                  const idx = items[0].dataIndex;
                  const ll = ds.llantas?.[idx] || 0;
                  const vh = ds.vehiculos?.[idx] || 1;
                  const rz = vh > 0 ? (ll / vh).toFixed(1) : '0';
                  return `Razón: ${rz} llantas/vehículo`;
                }
              }
            }
          },
          scales: {
            y: {
              type: 'linear',
              position: 'left',
              title: { display: true, text: 'Total Llantas', font: { weight: 'bold', size: 10 } },
              grace: '15%',
              grid: { color: 'rgba(226, 232, 240, 0.6)' },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            y1: {
              type: 'linear',
              position: 'right',
              title: { display: true, text: 'Vehículos', font: { weight: 'bold', size: 10 } },
              grace: '15%',
              grid: { drawOnChartArea: false },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            x: { ticks: { font: { weight: 'bold', size: 11 } } }
          }
        }
      });
      const u2 = taUltimos(ds.llantas);
      if (u2.valor !== null) {
        const dif = u2.previo !== null ? u2.valor - u2.previo : null;
        taLectura('canvasKpi02_volumen', 'in', `${(ds.labels || [])[u2.i] || 'Último mes'}: ${formatCO_Miles(u2.valor)} llantas inspeccionadas${dif === null ? '' : dif === 0 ? ', igual que el mes anterior' : `, ${formatCO_Miles(Math.abs(dif))} ${dif > 0 ? 'más' : 'menos'} que el mes anterior`}.`);
      }
    }

    // KPI 03: % Reencauche (Meta 70%) y Unidades por Ciclo
    function renderChartKpi03(ds) {
      destruirChartSuite('kpi03_pct');
      destruirChartSuite('kpi03_ciclos');
      const ctxPct = document.getElementById('canvasKpi03_pct');
      const ctxCiclos = document.getElementById('canvasKpi03_ciclos');
      if (!ds) return;

      // Badge meta
      const badge = document.getElementById('kpi03_badge_meta');
      const meta = ds.meta_porcentaje ?? 70.0;
      const sub3 = document.getElementById('kpi03_subtitulo');
      if (sub3) sub3.textContent = `Alineación a la meta del cliente (${formatCO_Decimal(meta, 0)}%) y ciclo de vida (Original, R1, R2, R3+)`;
      const ultimoPct = (ds.porcentajes && ds.porcentajes.length > 0) ? ds.porcentajes[ds.porcentajes.length - 1] : 0;
      if (badge) {
        if (ultimoPct >= meta) {
          badge.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300';
          badge.textContent = `🟢 Meta Cumplida (${formatCO_Decimal(ultimoPct, 1)}%)`;
        } else if (ultimoPct >= meta - 15) {
          badge.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300';
          badge.textContent = `🟡 Alerta Meta (${formatCO_Decimal(ultimoPct, 1)}%)`;
        } else {
          badge.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300';
          badge.textContent = `🔴 Crítico (${formatCO_Decimal(ultimoPct, 1)}%)`;
        }
      }

      // Subpanel A: Línea % Reencauche con umbral 70%
      if (ctxPct) {
        const lineaMeta = (ds.labels || []).map(() => meta);
        instanciasChartsSuite['kpi03_pct'] = new Chart(ctxPct, {
          type: 'line',
          data: {
            labels: ds.labels || [],
            datasets: [
              {
                label: '% Reencauche',
                data: ds.porcentajes || [],
                borderColor: TA_G.azul,
                backgroundColor: taRgba(TA_G.azul, 0.08),
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: TA_G.azul,
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                datalabels: pillDatalabelConfig('rgba(6, 95, 70, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)}%`)
              },
              {
                label: `Meta del cliente (${meta}%)`,
                data: lineaMeta,
                borderColor: TA_G.marino,
                borderWidth: 1.5,
                borderDash: [5, 5],
                pointRadius: 0,
                fill: false,
                datalabels: { display: false }
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 12, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } }
            },
            scales: {
              y: {
                min: 0,
                // Margen sobre el 100 % para que la etiqueta de un mes en 100 % no quede pegada al borde
                max: 112,
                ticks: { stepSize: 20, callback: (v) => (v <= 100 ? `${v}%` : '') },
                grid: { color: 'rgba(226, 232, 240, 0.6)' }
              },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // Subpanel B: Barras Apiladas por Ciclo
      if (ctxCiclos && ds.ciclos) {
        const c = ds.ciclos;
        const escCiclos = taEscalaAzul(4);
        instanciasChartsSuite['kpi03_ciclos'] = new Chart(ctxCiclos, {
          type: 'bar',
          data: {
            labels: ds.labels || [],
            datasets: [
              { label: 'Original', data: c.original || [], backgroundColor: escCiclos[0], borderRadius: 2 },
              { label: 'R1', data: c.r1 || [], backgroundColor: escCiclos[1], borderRadius: 2 },
              { label: 'R2', data: c.r2 || [], backgroundColor: escCiclos[2], borderRadius: 2 },
              { label: 'R3+', data: c.r3_mas || [], backgroundColor: escCiclos[3], borderRadius: 2 }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 20, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } },
              datalabels: {
                display: (ctx) => {
                  const v = ctx.dataset.data[ctx.dataIndex];
                  return (v && v > 0);
                },
                color: (ctx) => taTextoSobre(ctx.dataset.backgroundColor),
                font: { weight: '600', size: 10 },
                formatter: (val) => formatCO_Miles(val)
              }
            },
            scales: {
              x: { stacked: true, ticks: { font: { weight: 'bold', size: 10 } } },
              y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(226, 232, 240, 0.6)' } }
            }
          }
        });
      }

      // Conclusiones
      const u3 = taUltimos(ds.porcentajes);
      if (u3.valor !== null) {
        const falta = meta - u3.valor;
        taLectura('canvasKpi03_pct', u3.valor >= meta ? 'ok' : u3.valor >= meta - 15 ? 'al' : 'cr',
          u3.valor >= meta ? `${formatCO_Decimal(u3.valor, 1)} % reencauchadas: la meta de ${formatCO_Decimal(meta, 0)} % se cumple.`
            : `${formatCO_Decimal(u3.valor, 1)} % reencauchadas; la meta es ${formatCO_Decimal(meta, 0)} %. Faltan ${formatCO_Decimal(falta, 1)} puntos.`);
      }
      if (ds.ciclos) {
        const c = ds.ciclos;
        const i = taUltimos(c.original).i;
        if (i !== undefined) {
          const reen = (Number(c.r1?.[i]) || 0) + (Number(c.r2?.[i]) || 0) + (Number(c.r3_mas?.[i]) || 0);
          const tot = reen + (Number(c.original?.[i]) || 0);
          taLectura('canvasKpi03_ciclos', 'in', `${(ds.labels || [])[i] || 'Último mes'}: ${formatCO_Miles(reen)} de ${formatCO_Miles(tot)} llantas van en reencauche (R1 o más).`);
        }
      }
    }

    // KPI 04: Composición de Flota (Tipología, Marca, Dimensión)
    function renderChartKpi04(ds) {
      destruirChartSuite('kpi04_tip');
      destruirChartSuite('kpi04_mar');
      destruirChartSuite('kpi04_dim');
      if (!ds) return;

      const dsTip = ds.tipologias || ds.tipologia;
      const dsMar = ds.marcas || ds.marca;
      const dsDim = ds.dimensiones || ds.dimension;

      // Columna A: Tipología Vehicular (Barras Horizontales)
      const ctxTip = document.getElementById('canvasKpi04_tipologia');
      if (ctxTip && dsTip) {
        instanciasChartsSuite['kpi04_tip'] = new Chart(ctxTip, {
          type: 'bar',
          data: {
            labels: dsTip.labels || [],
            datasets: [{
              label: 'Llantas',
              data: dsTip.valores || [],
              backgroundColor: taMejorEn(dsTip.valores),
              borderRadius: 4
            }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { right: 48 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              datalabels: pillDatalabelConfig('rgba(79, 70, 229, 0.9)', '#ffffff')
            },
            scales: {
              x: { beginAtZero: true, ticks: { callback: (v) => formatCO_Miles(v) } },
              y: { ticks: ticksEtiquetaCorta(22, 0) }
            }
          }
        });
      }

      // Columna B: Marcas de Llanta (Barras Verticales)
      const ctxMar = document.getElementById('canvasKpi04_marca');
      if (ctxMar && dsMar) {
        instanciasChartsSuite['kpi04_mar'] = new Chart(ctxMar, {
          type: 'bar',
          data: {
            labels: dsMar.labels || [],
            datasets: [{
              label: 'Llantas',
              data: dsMar.valores || [],
              backgroundColor: taMejorEn(dsMar.valores),
              borderRadius: 4
            }]
          },
          options: {
            // Rediseño: barras horizontales para leer el nombre completo de cada marca
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { right: 48 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              datalabels: pillDatalabelConfig('rgba(14, 165, 233, 0.9)', '#ffffff')
            },
            scales: {
              x: { beginAtZero: true, ticks: { callback: (v) => formatCO_Miles(v) } },
              y: { ticks: ticksEtiquetaCorta(18, 0) }
            }
          }
        });
      }

      // Columna C: Dimensión (dona, con la paleta del rediseño: la medida principal en azul fuerte)
      const ctxDim = document.getElementById('canvasKpi04_dimension');
      if (ctxDim && dsDim) {
        instanciasChartsSuite['kpi04_dim'] = new Chart(ctxDim, taDona(dsDim.labels || [], dsDim.valores || [], taColoresCategorias(dsDim.labels || []),
          { centro: `${(dsDim.labels || []).length}`, subtexto: 'Medidas' }));
      }

      // Conclusiones
      const lecturaTop = (canvasId, d, plantilla) => {
        if (!d || !(d.valores || []).length) return;
        const i = taIndiceMayor(d.valores);
        if (i < 0) return;
        const empatados = d.valores.filter(v => Number(v) === Number(d.valores[i])).length;
        const p = taPct(d.valores[i], taSuma(d.valores));
        taLectura(canvasId, 'in', empatados > 1
          ? `Empate en primer lugar: ${empatados} con ${formatCO_Miles(d.valores[i])} llantas cada una (${p} %).`
          : plantilla(d.labels[i], d.valores[i], p));
      };
      lecturaTop('canvasKpi04_tipologia', dsTip, (l, v, p) => `${l} lleva más llantas: ${formatCO_Miles(v)} (${p} %).`);
      lecturaTop('canvasKpi04_marca', dsMar, (l, v, p) => `${l} es la marca con más llantas: ${formatCO_Miles(v)} (${p} %).`);
      lecturaTop('canvasKpi04_dimension', dsDim, (l, v, p) => `${p} % de las llantas son ${l}.`);
    }

    // ==========================================
    // INTELIGENCIA DE AHORRO FINANCIERO & ROI (BANNER & MODAL CAMBIAZOS)
    // ==========================================
    let ultimasAlertasCambiazo = [];

    function renderizarBannerAhorroRoi(ahorroData) {
      if (!ahorroData) return;
      ultimasAlertasCambiazo = ahorroData.alertas_cambiazo_serial || [];

      const totalFmt = formatCO_Moneda(ahorroData.ahorro_potencial_total_cop || 0) + ' COP';
      const cascosFmt = formatCO_Moneda(ahorroData.ahorro_salvamento_cascos_cop || 0) + ' COP';
      const alinFmt = formatCO_Moneda(ahorroData.ahorro_alineacion_oportuna_cop || 0) + ' COP';
      const combFmt = formatCO_Moneda(ahorroData.ahorro_combustible_anual_psi_cop || 0) + ' COP';
      const cantCambiazos = ahorroData.total_alertas_cambiazo !== undefined ? ahorroData.total_alertas_cambiazo : (ultimasAlertasCambiazo.length || 0);
      const cascosCant = ahorroData.cascos_en_ventana_salvamento || 0;

      // Banner en Vista KPIs
      const elTot = document.getElementById('banner_kpi_ahorro_total');
      if (elTot) elTot.textContent = totalFmt;
      const elCas = document.getElementById('banner_kpi_ahorro_cascos');
      if (elCas) elCas.textContent = cascosFmt;
      const elAlin = document.getElementById('banner_kpi_ahorro_alineacion');
      if (elAlin) elAlin.textContent = alinFmt;
      const elComb = document.getElementById('banner_kpi_ahorro_combustible');
      if (elComb) elComb.textContent = combFmt;
      const elNumC = document.getElementById('banner_kpi_cambiazos_num');
      if (elNumC) elNumC.textContent = cantCambiazos + (cantCambiazos === 1 ? ' Caso' : ' Casos');
      const elBdgC = document.getElementById('badge_cambiazos_total');
      if (elBdgC) elBdgC.textContent = cantCambiazos + (cantCambiazos === 1 ? ' Caso' : ' Casos');
      const elBdgS = document.getElementById('badge_cascos_salvamento');
      if (elBdgS) elBdgS.textContent = cascosCant + (cascosCant === 1 ? ' Casco' : ' Cascos');

      // Banner en Vista Diagnóstico
      const elDiagTot = document.getElementById('diag_ahorro_total_cop');
      if (elDiagTot) elDiagTot.textContent = totalFmt;
      const elDiagBdg = document.getElementById('diag_badge_cambiazos');
      if (elDiagBdg) elDiagBdg.textContent = cantCambiazos + (cantCambiazos === 1 ? ' Cambiazo' : ' Cambiazos');
    }

    function abrirModalAlertasCambiazo() {
      const modal = document.getElementById('modalAlertasCambiazo');
      const tbody = document.getElementById('tbodyAlertasCambiazo');
      const lblTotal = document.getElementById('lblTotalCambiazosModal');
      if (!modal || !tbody) return;

      if (!ultimasAlertasCambiazo || ultimasAlertasCambiazo.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="p-8 text-center text-slate-400 font-bold"><i class="fa-solid fa-circle-check text-emerald-500 mr-2 text-base"></i>No se detectaron discrepancias ni sustituciones no autorizadas de serial en la flota</td></tr>';
        if (lblTotal) lblTotal.textContent = 'Total: 0 discrepancias detectadas';
      } else {
        tbody.innerHTML = ultimasAlertasCambiazo.map(a => `
          <tr class="hover:bg-rose-50/50 transition-colors">
            <td class="p-2.5 font-bold text-slate-900">${escapeHtml(a.placa || '')}</td>
            <td class="p-2.5 text-center font-mono font-bold text-indigo-600">Pos ${escapeHtml(a.posicion || '')}</td>
            <td class="p-2.5 font-mono text-slate-400 line-through">${escapeHtml(a.serial_anterior || '')}</td>
            <td class="p-2.5 font-mono font-bold text-rose-600">${escapeHtml(a.serial_actual || '')}</td>
            <td class="p-2.5 text-right font-mono font-bold">${escapeHtml(a.prof_actual_min || 0)} mm</td>
            <td class="p-2.5 text-slate-400 text-xs">${escapeHtml(a.fecha_anterior || '')}</td>
            <td class="p-2.5 text-slate-700 font-semibold text-xs">${escapeHtml(a.fecha_actual || '')}</td>
            <td class="p-2.5 text-center"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">Sustitución sin Kardex</span></td>
          </tr>
        `).join('');
        if (lblTotal) lblTotal.textContent = `Total: ${ultimasAlertasCambiazo.length} discrepancias detectadas`;
      }

      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    function cerrarModalAlertasCambiazo() {
      const modal = document.getElementById('modalAlertasCambiazo');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
    }

    // ==========================================
    // RENDERERS SUB-PESTAÑA 2 (KPI 05 AL 11)
    // ==========================================

    // KPI 05: Cuadro de Cambios + Heatmap Placa vs Posición + Regla Direccional
    function renderKpi05(d) {
      if (!d) return;

      // Nivel 1: Tabla Cruzada Dimensión vs Eje
      const tbodyCruz = document.getElementById('tbodyKpi05_cruzada');
      if (tbodyCruz) {
        if (!d.tabla_cruzada || d.tabla_cruzada.length === 0) {
          tbodyCruz.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-slate-400">Sin retiros requeridos</td></tr>';
        } else {
          tbodyCruz.innerHTML = d.tabla_cruzada.map(r => `
            <tr class="hover:bg-slate-50">
              <td class="p-2.5 font-bold text-slate-800">${escapeHtml(r.dimension || '-')}</td>
              <td class="p-2.5 text-center font-mono">${escapeHtml(r.direccional || 0)}</td>
              <td class="p-2.5 text-center font-mono">${escapeHtml(r.traccion || 0)}</td>
              <td class="p-2.5 text-center font-mono">${escapeHtml(r.arrastre || 0)}</td>
              <td class="p-2.5 text-right font-black font-mono text-rose-700 bg-rose-50/50">${escapeHtml(r.total || 0)}</td>
            </tr>
          `).join('');
        }
      }

      // Nivel 1: Gráfico Barras Retiros Mensuales
      destruirChartSuite('kpi05_ret');
      const ctxRet = document.getElementById('canvasKpi05_retiros');
      if (ctxRet && d.retiros_mensuales) {
        const rm = d.retiros_mensuales;
        instanciasChartsSuite['kpi05_ret'] = new Chart(ctxRet, {
          type: 'bar',
          data: {
            labels: rm.labels || [],
            datasets: [{
              label: 'Retiros Mensuales',
              data: rm.valores || [],
              backgroundColor: taUltimoEn((rm.valores || []).length, TA_G.cr),
              borderRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 22 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              datalabels: pillDatalabelConfig('rgba(239, 68, 68, 0.9)', '#ffffff')
            },
            scales: {
              y: { beginAtZero: true, ticks: { callback: (v) => formatCO_Miles(v) } }
            }
          }
        });
        const u5 = taUltimos(rm.valores);
        if (u5.valor !== null) {
          const dif = u5.previo !== null ? u5.valor - u5.previo : null;
          taLectura('canvasKpi05_retiros', u5.valor > 0 ? 'cr' : 'ok', u5.valor > 0
            ? `${formatCO_Miles(u5.valor)} llantas llegaron al límite en ${(rm.labels || [])[u5.i] || 'el último mes'}${dif ? `: ${formatCO_Miles(Math.abs(dif))} ${dif > 0 ? 'más' : 'menos'} que el mes anterior` : ''}.`
            : 'Ninguna llanta llegó al límite de retiro en el último mes.');
        }
      }

      // Nivel 2: Heatmap Placa vs Posición 1..12
      const tbodyHeat = document.getElementById('tbodyKpi05_heatmap');
      if (tbodyHeat) {
        if (!d.matriz_posiciones || d.matriz_posiciones.length === 0) {
          tbodyHeat.innerHTML = '<tr><td colspan="13" class="p-4 text-center text-slate-400">Sin registros de posiciones</td></tr>';
        } else {
          tbodyHeat.innerHTML = d.matriz_posiciones.map(r => {
            const celdas = [1,2,3,4,5,6,7,8,9,10,11,12].map(pos => {
              const info = r.posiciones ? r.posiciones[String(pos)] : null;
              if (!info || info.prof === null || info.prof === undefined) {
                return '<td class="p-2 bg-slate-50 text-slate-300">-</td>';
              }
              const prof = info.prof;
              const lim = info.limite || 3.0;
              let bg = 'bg-emerald-50 text-emerald-800 border-emerald-100';
              if (prof <= lim) {
                bg = 'bg-rose-500 text-white font-black shadow-xs';
              } else if (prof <= lim + 2.0) {
                bg = 'bg-amber-400 text-slate-900 font-bold';
              }
              const title = `Pos ${pos}: ${prof}mm (Límite: ${lim}mm)${info.alerta_par_direccional ? ' ⚠️ Par Direccional' : ''}`;
              return `<td class="p-2 ${bg} border border-white" title="${title}">${prof}</td>`;
            }).join('');

            return `
              <tr class="hover:bg-slate-100 transition-colors">
                <td class="p-2 text-left font-bold text-slate-900 sticky left-0 bg-white border-r border-slate-200">${escapeHtml(r.placa || '-')}</td>
                ${celdas}
              </tr>
            `;
          }).join('');
        }
      }
    }

    // KPI 06: Seguimiento de Alineación y Pérdida
    function renderKpi06(d) {
      if (!d) return;

      destruirChartSuite('kpi06_alin');
      const ctx = document.getElementById('canvasKpi06_alineacion');
      if (ctx && d.historico) {
        const h = d.historico;
        instanciasChartsSuite['kpi06_alin'] = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: h.labels || [],
            datasets: [
              { label: '% Alineación OK', data: h.pct_ok || [], backgroundColor: TA_G.okClaro, borderRadius: 0 },
              { label: '% Desalineadas', data: h.pct_alerta || [], backgroundColor: TA_G.cr, borderRadius: 0 }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 20 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } },
              datalabels: {
                // Solo el porcentaje desalineado (lo que hay que atender), encima de su barra
                display: (ctx) => {
                  const v = ctx.dataset.data[ctx.dataIndex];
                  return ctx.datasetIndex === 1 && v !== null && v !== undefined;
                },
                anchor: 'end', align: 'top', offset: 2, clamp: true,
                color: TA_G.texto,
                font: { weight: '600', size: 10 },
                formatter: (val) => `${formatCO_Decimal(val, 0)}%`
              }
            },
            scales: {
              x: { stacked: true },
              y: { stacked: true, min: 0, max: 100, ticks: { callback: (v) => `${v}%` } }
            }
          }
        });
        const u6 = taUltimos(h.pct_alerta);
        if (u6.valor !== null) {
          const serie6 = (h.pct_alerta || []).filter(v => v !== null && v !== undefined).map(Number);
          const minimo = Math.min(...serie6);
          const esMenorUnico = u6.valor === minimo && serie6.filter(v => v === minimo).length === 1 && serie6.length > 1;
          taLectura('canvasKpi06_alineacion', u6.valor <= 10 ? 'ok' : u6.valor <= 20 ? 'al' : 'cr',
            `${formatCO_Decimal(u6.valor, Number.isInteger(Number(u6.valor)) ? 0 : 1)} % del eje direccional con desgaste de desalineación en ${(h.labels || [])[u6.i] || 'el último mes'}${esMenorUnico ? ', el menor del periodo' : ''}.`);
        }
      }

      // Tabla Detallada por Placa
      const tbody = document.getElementById('tbodyKpi06_perdidaPlaca');
      if (tbody) {
        if (!d.tabla_perdidas || d.tabla_perdidas.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-400">Sin vehículos desalineados</td></tr>';
        } else {
          tbody.innerHTML = d.tabla_perdidas.map(r => `
            <tr class="hover:bg-slate-50">
              <td class="p-2.5 font-bold font-mono text-slate-900">${escapeHtml(r.placa || '-')}</td>
              <td class="p-2.5 text-center font-mono text-slate-700">${formatCO_Decimal(r.pos1_mm, 1)}</td>
              <td class="p-2.5 text-center font-mono text-slate-700">${formatCO_Decimal(r.pos2_mm, 1)}</td>
              <td class="p-2.5 text-center font-mono font-black text-rose-600">${formatCO_Decimal(r.total_mm, 1)} mm</td>
              <td class="p-2.5 text-right font-mono font-bold text-slate-900">${modoLicenciaSuite === 'FULL' ? formatCO_Moneda(r.perdida_pesos) : 'Modo LIGHT'}</td>
              <td class="p-2.5 text-center"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800">${escapeHtml(r.accion || 'Alinear Dirección')}</span></td>
            </tr>
          `).join('');
        }
      }
    }

    // KPI 07: Plan de Rotaciones Tándem y Tráiler
    function renderKpi07(d) {
      if (!d) return;
      const tbody = document.getElementById('tbodyKpi07_rotaciones');
      if (tbody) {
        if (!d.rotaciones_sugeridas || d.rotaciones_sugeridas.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-400">Desgaste equilibrado: no se requieren rotaciones en este corte</td></tr>';
        } else {
          tbody.innerHTML = d.rotaciones_sugeridas.map(r => `
            <tr class="hover:bg-slate-50">
              <td class="p-2.5 font-bold font-mono text-slate-900">${escapeHtml(r.placa || '-')}</td>
              <td class="p-2.5 text-center font-medium text-indigo-700 font-mono">${escapeHtml(r.esquema || 'P3 ↔ P9 / P4 ↔ P10')}</td>
              <td class="p-2.5 text-center font-mono font-black text-amber-600">&Delta; ${formatCO_Decimal(r.delta_ejes_mm, 1)} mm</td>
              <td class="p-2.5 text-center">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${r.estado === 'Reincidente' ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'}">
                  ${r.estado || 'Solucionada'}
                </span>
              </td>
            </tr>
          `).join('');
        }
      }
    }

    // KPI 08: Duales Mal Apareados + Cruce con Bodega 2
    function renderKpi08(d) {
      if (!d) return;

      destruirChartSuite('kpi08_apar');
      const ctx = document.getElementById('canvasKpi08_apareo');
      if (ctx && d.frecuencia_mensual) {
        const fm = d.frecuencia_mensual;
        instanciasChartsSuite['kpi08_apar'] = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: fm.labels || [],
            datasets: [{
              label: 'Pachas Desapareadas',
              data: fm.valores || [],
              backgroundColor: taUltimoEn((fm.valores || []).length, TA_G.al),
              borderRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              datalabels: pillDatalabelConfig('rgba(244, 63, 94, 0.9)', '#ffffff')
            },
            scales: {
              y: { beginAtZero: true, ticks: { callback: (v) => formatCO_Miles(v) } }
            }
          }
        });
        const u8 = taUltimos(fm.valores);
        if (u8.valor !== null) {
          taLectura('canvasKpi08_apareo', u8.valor > 0 ? 'al' : 'ok', u8.valor > 0
            ? `${formatCO_Miles(u8.valor)} pares de duales por corregir en ${(fm.labels || [])[u8.i] || 'el último mes'}.`
            : 'Sin duales mal apareados en el último mes.');
        }
      }

      // Tarjetas de Cruce con Bodega 2
      const cont = document.getElementById('contenedorKpi08_crucesB2');
      if (cont) {
        if (!d.cruces_bodega2 || d.cruces_bodega2.length === 0) {
          cont.innerHTML = `<div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-center text-xs">Sin pachas con desbalance &ge; ${escapeHtml(formatCO_Decimal(Number(d.tolerancia_mm || 2.5), 1))} mm</div>`;
        } else {
          cont.innerHTML = d.cruces_bodega2.map(c => `
            <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
              <div>
                <span class="font-mono font-black text-slate-900">${escapeHtml(c.placa || '-')}</span>
                <span class="text-slate-500 ml-1.5">${escapeHtml(c.pacha || 'P3-P4')} (&Delta; ${formatCO_Decimal(c.diferencia_mm, 1)} mm)</span>
              </div>
              <div class="text-right">
                <span class="text-[10px] text-indigo-600 font-bold block">Bodega 2: ${escapeHtml(c.llanta_b2_sugerida || 'Stock disponible')}</span>
                <span class="text-[10px] text-slate-500 font-mono">${escapeHtml(c.milimetraje_b2 || 0)} mm</span>
              </div>
            </div>
          `).join('');
        }
      }
    }

    // KPI 09: Presiones PSI y Combustible
    function renderKpi09(d) {
      if (!d) return;

      destruirChartSuite('kpi09_psi');
      const ctx = document.getElementById('canvasKpi09_psi');
      if (ctx && d.distribucion) {
        const dist = d.distribucion;
        // Dona con el color de cada estado: verde correcta, ámbar baja, rojo baja severa y ámbar claro alta
        const valPsi = [dist.correcta || 0, dist.baja_moderada || 0, dist.baja_severa || 0, dist.sobrepresion || 0];
        const totPsi = taSuma(valPsi);
        instanciasChartsSuite['kpi09_psi'] = new Chart(ctx, taDona(
          // Rangos según la presión objetivo de cada eje y las tolerancias asignadas al cliente
          ['Correcta (en tolerancia)', 'Baja (fuera de tolerancia)', 'Baja severa (< -15 %)', 'Alta (fuera de tolerancia)'],
          valPsi, [TA_G.ok, TA_G.al, TA_G.cr, taMezclar(TA_G.al, '#ffffff', 0.45)],
          { centro: `${taPct(dist.correcta || 0, totPsi)}%`, subtexto: 'Presión OK' }));
        if (totPsi > 0) {
          const pOk = taPct(dist.correcta || 0, totPsi);
          const sev = dist.baja_severa || 0;
          taLectura('canvasKpi09_psi', pOk >= 90 && !sev ? 'ok' : sev ? 'cr' : 'al',
            `${pOk} % de las llantas con presión correcta${sev ? `; ${formatCO_Miles(sev)} en baja severa` : ''}.`);
        }
      }

      const elGalones = document.getElementById('kpi09_galones_diesel');
      if (elGalones) {
        // Estimado con parámetros de referencia; las llantas sin lectura de PSI no entran al cálculo
        const sinLectura = Number(d.llantas_sin_lectura_psi) || 0;
        elGalones.textContent = `${formatCO_Miles(d.galones_desperdiciados_mes || 0)} gal/mes (estimado)`;
        elGalones.title = sinLectura > 0 ? `${sinLectura} llanta(s) sin lectura de PSI no se incluyen` : '';
      }
    }

    // KPI 10: Pareto de Novedades y Taller
    function renderChartKpi10(d) {
      destruirChartSuite('kpi10_pareto');
      const ctx = document.getElementById('canvasKpi10_pareto');
      if (!ctx || !d) return;

      const elEfect = document.getElementById('kpi10_efectividad_badge');
      if (elEfect && d.efectividad_taller_pct !== undefined) {
        // null = no hay mes anterior con alertas para comparar
        elEfect.textContent = d.efectividad_taller_pct === null
          ? 'Efectividad: sin histórico'
          : `Efectividad: ${formatCO_Decimal(d.efectividad_taller_pct, 1)}%`;
      }

      // Rediseño: las novedades que suman hasta el 80 % en azul fuerte (atacarlas primero); el resto en azul claro
      const acum10 = (d.acumulado_pct || []).map(Number);
      const colores10 = (d.frecuencias || []).map((_, i) => (i === 0 || (acum10[i - 1] || 0) < 80) ? TA_G.azul : TA_G.azulClaro);
      instanciasChartsSuite['kpi10_pareto'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: d.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Frecuencia Novedades',
              data: d.frecuencias || [],
              backgroundColor: colores10,
              borderRadius: 4,
              yAxisID: 'y',
              datalabels: pillDatalabelConfig('rgba(168, 85, 247, 0.9)', '#ffffff')
            },
            {
              type: 'line',
              label: '% Acumulado (Pareto)',
              data: d.acumulado_pct || [],
              borderColor: TA_G.gris,
              backgroundColor: TA_G.gris,
              borderWidth: 2,
              pointRadius: 3,
              yAxisID: 'y1',
              datalabels: pillDatalabelConfig('rgba(217, 119, 6, 0.95)', '#ffffff', (v) => `${formatCO_Decimal(v, 0)}%`)
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 24, right: 12, bottom: 8, left: 28 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } }
          },
          scales: {
            y: { beginAtZero: true, position: 'left', title: { display: true, text: 'Cantidad' } },
            y1: { beginAtZero: true, max: 100, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => `${v}%` } },
            x: { ticks: ticksEtiquetaCorta(18) }
          }
        }
      });
      if ((d.frecuencias || []).length) {
        let k = acum10.findIndex(p => p >= 80);
        if (k < 0) k = acum10.length - 1;
        const pctK = acum10[k] || 0;
        taLectura('canvasKpi10_pareto', 'in', k === 0
          ? `«${(d.labels || [])[0]}» explica el ${formatCO_Decimal(pctK, 0)} % de las novedades: atacarla primero.`
          : `${k + 1} novedades explican el ${formatCO_Decimal(pctK, 0)} % de los casos: atacarlas primero.`);
      }
    }

    // KPI 11: Impacto Económico Interanual (mm vs $)
    function renderChartKpi11(d) {
      destruirChartSuite('kpi11_impacto');
      const ctx = document.getElementById('canvasKpi11_impacto');
      if (!d) return;

      const elMm = document.getElementById('kpi11_mm_perdidos');
      const elPesos = document.getElementById('kpi11_pesos_perdidos');
      if (elMm) elMm.textContent = `${formatCO_Decimal(d.total_mm_perdidos || 0, 1)} mm`;
      if (elPesos) {
        elPesos.textContent = (modoLicenciaSuite === 'FULL') ? formatCO_Moneda(d.impacto_economico_total || 0) : 'Modo LIGHT';
      }

      if (ctx) {
        const datasets = [
          {
            type: 'bar',
            label: 'Milímetros Perdidos',
            data: d.mm_mes || [],
            backgroundColor: TA_G.grisClaro,
            borderRadius: 6,
            yAxisID: 'y',
            datalabels: pillDatalabelConfig('rgba(244, 63, 94, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} mm`)
          }
        ];

        if (modoLicenciaSuite === 'FULL') {
          datasets.push({
            type: 'line',
            label: 'Pérdida Monetaria ($ COP)',
            data: d.pesos_mes || [],
            borderColor: TA_G.cr,
            backgroundColor: TA_G.cr,
            borderWidth: 2.8,
            tension: 0.35,
            pointRadius: 4,
            yAxisID: 'y1',
            datalabels: pillDatalabelConfig('rgba(249, 115, 22, 0.9)', '#ffffff', (v) => formatCO_Moneda(v))
          });
        }

        instanciasChartsSuite['kpi11_impacto'] = new Chart(ctx, {
          data: {
            labels: d.labels || [],
            datasets: datasets
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } }
            },
            scales: {
              y: { beginAtZero: true, title: { display: true, text: 'Milímetros Perdidos' }, ticks: { callback: (v) => `${formatCO_Decimal(v, 1)} mm` } },
              y1: {
                display: (modoLicenciaSuite === 'FULL'),
                beginAtZero: true,
                position: 'right',
                grid: { drawOnChartArea: false },
                title: { display: true, text: 'Pérdida Económica ($)' },
                ticks: { callback: (v) => formatCO_Moneda(v) }
              },
              x: { ticks: { font: { weight: 'bold', size: 11 } } }
            }
          }
        });
        const serie11 = modoLicenciaSuite === 'FULL' ? (d.pesos_mes || []) : (d.mm_mes || []);
        const u11 = taUltimos(serie11);
        const primero = serie11.find(v => v !== null && v !== undefined && Number(v) > 0);
        if (u11.valor !== null) {
          const baja = primero ? Math.round((1 - u11.valor / Number(primero)) * 100) : 0;
          const valorTxt = modoLicenciaSuite === 'FULL' ? formatCO_Moneda(u11.valor) : `${formatCO_Decimal(u11.valor, 1)} mm`;
          taLectura('canvasKpi11_impacto', baja > 0 ? 'ok' : u11.valor > 0 ? 'al' : 'ok',
            `${(d.labels || [])[u11.i] || 'Último mes'}: ${valorTxt} perdidos${baja > 0 ? `, ${baja} % menos que al inicio del periodo` : baja < 0 ? `, ${Math.abs(baja)} % más que al inicio del periodo` : ''}.`);
        }
      }
    }

    // ==========================================
    // RENDERERS SUB-PESTAÑA 3 (KPI 12 AL 16) [SOLO FULL]
    // ==========================================

    // KPI 12: Las 4 Tarjetas Maestras de Desempeño de Flota
    function renderKpi12(d) {
      if (!d) return;
      const elMmG = document.getElementById('kpi12_mm_gastados');
      const elProfAct = document.getElementById('kpi12_prof_actual');
      const elPctDesg = document.getElementById('kpi12_pct_desgaste');
      const elBarDesg = document.getElementById('kpi12_barra_desgaste');
      const elKmRec = document.getElementById('kpi12_km_recorridos');

      if (elMmG) elMmG.textContent = `${formatCO_Decimal(d.mm_gastados || 0, 1)} mm`;
      if (elProfAct) elProfAct.textContent = `${formatCO_Decimal(d.profundidad_actual || 0, 1)} mm`;

      const pct = Math.min(100, Math.max(0, d.pct_desgaste || 0));
      if (elPctDesg) elPctDesg.textContent = `${formatCO_Decimal(pct, 1)}%`;
      if (elBarDesg) {
        elBarDesg.style.width = `${pct}%`;
        if (pct < 60) {
          elBarDesg.className = 'h-full bg-emerald-500 rounded-full transition-all duration-500';
        } else if (pct < 85) {
          elBarDesg.className = 'h-full bg-amber-500 rounded-full transition-all duration-500';
        } else {
          elBarDesg.className = 'h-full bg-rose-500 rounded-full transition-all duration-500';
        }
      }
      if (elKmRec) elKmRec.textContent = `${formatCO_Miles(d.km_recorridos || 0)} ${uMed()}`;
    }

    // KPI 13 y 14 con originales y reencauches por separado: una reencauchada arranca con otra banda y otro precio,
    // así que se compara original con original y reencauche con reencauche. Originales en azul, reencauches en verde.
    const VIDA_COLORES = {
      original: { fuerte: TA_G.azul, suave: TA_G.azulClaro, nombre: 'Originales' },
      reencauche: { fuerte: TA_G.ok, suave: TA_G.okClaro, nombre: 'Reencauches' }
    };
    // Rótulos que se ocultan solos si chocan con otro (el valor sigue visible al pasar el cursor)
    function etiquetaSinChoque(fmt) {
      const e = pillDatalabelConfig(undefined, undefined, fmt);
      const base = e.display;
      e.display = (c) => ((typeof base === 'function' ? base(c) : base) ? 'auto' : false);
      return e;
    }
    function tieneDatosVida(serie) { return (serie || []).some(v => v !== null && v !== undefined && Number(v) > 0); }
    function leyendaVida(colores) {
      // La leyenda toma un color fijo por serie (las barras usan un tono fuerte para la mejor y suave para las demás)
      return {
        position: 'top',
        labels: {
          boxWidth: 12, font: { weight: 'bold', size: 11 },
          generateLabels: (chart) => chart.data.datasets.map((d, i) => ({
            text: d.label, fillStyle: colores[i], strokeStyle: colores[i], lineWidth: 0,
            hidden: !chart.isDatasetVisible(i), datasetIndex: i
          }))
        }
      };
    }
    // «Originales: A con X. Reencauches: B con Y.»
    function fraseVida(pv, campo, menorEsMejor, texto, vidas = ['original', 'reencauche']) {
      const partes = [];
      vidas.forEach(vida => {
        const serie = (pv[vida] || {})[campo] || [];
        const i = taIndiceMayor(serie, menorEsMejor);
        if (i < 0 || !(Number(serie[i]) > 0)) return;
        // Si varias empatan en el primer lugar se nombran todas
        const iguales = pv.labels.filter((_, j) => serie[j] !== null && serie[j] !== undefined && Number(serie[j]) === Number(serie[i]));
        const nombres = iguales.length > 1 ? `${iguales.slice(0, -1).join(', ')} y ${iguales[iguales.length - 1]}` : pv.labels[i];
        partes.push(`${VIDA_COLORES[vida].nombre}: ${nombres} (${texto(serie[i])})`);
      });
      return partes.join(' · ');
    }

    function renderChartKpi13Vida(pv) {
      const ctx = document.getElementById('canvasKpi13_comparativo');
      if (!ctx) return;
      const fmt = (v) => `${formatCO_Miles(v)} ${uMed()}`;
      const recorrido = unidadSuite === 'h' ? 'horas reales' : 'km recorridos';
      const series = [
        { vida: 'original', campo: 'km_reales', label: `Originales · ${recorrido}`, color: TA_G.azul },
        { vida: 'original', campo: 'proyeccion_final', label: 'Originales · proyección al retiro', color: TA_G.azulClaro }
      ];
      if (tieneDatosVida((pv.reencauche || {}).proyeccion_final)) series.push(
        { vida: 'reencauche', campo: 'km_reales', label: `Reencauches · ${recorrido}`, color: TA_G.ok },
        { vida: 'reencauche', campo: 'proyeccion_final', label: 'Reencauches · proyección al retiro', color: TA_G.okClaro });
      // Con originales y reencauches (o muchas marcas) solo se rotula la proyección; lo recorrido se ve al pasar el cursor
      const muchos = series.length > 2 || (pv.labels || []).length > 4;
      instanciasChartsSuite['kpi13_comparativo'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: pv.labels || [],
          datasets: series.map(se => {
            const etiqueta = etiquetaSinChoque(fmt);
            if (muchos && se.campo === 'km_reales') etiqueta.display = false;
            return { label: se.label, data: (pv[se.vida] || {})[se.campo] || [], backgroundColor: se.color, borderWidth: 0, borderRadius: 4, datalabels: etiqueta };
          })
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: leyendaVida(series.map(se => se.color)),
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)', cornerRadius: 10, padding: 12,
              callbacks: {
                label: (c) => (c.raw === null || c.raw === undefined) ? `${c.dataset.label}: sin llantas` : `${c.dataset.label}: ${fmt(c.raw)}`,
                afterBody: (items) => {
                  const idx = items[0].dataIndex;
                  return ['original', 'reencauche'].map(vida => {
                    const r = (pv[vida] || {}).km_reales?.[idx], p = (pv[vida] || {}).proyeccion_final?.[idx];
                    const n = (pv.llantas || {})[vida]?.[idx] || 0;
                    return p ? `${VIDA_COLORES[vida].nombre} (${n} llantas): les quedan ${fmt(Math.max(0, p - (r || 0)))}` : null;
                  }).filter(Boolean);
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true, grace: '15%',
              title: { display: true, text: unidadSuite === 'h' ? 'Horas' : 'Kilómetros', font: { weight: 'bold', size: 10 } },
              grid: { color: 'rgba(226, 232, 240, 0.6)' },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            x: { ticks: ticksEtiquetaCorta(14) }
          }
        }
      });
      const frase = fraseVida(pv, 'proyeccion_final', false, fmt);
      if (frase) taLectura('canvasKpi13_comparativo', 'in', `Mayor proyección al retiro. ${frase}.`);
    }

    function renderChartKpi14Vida(pv, soloOriginales = false) {
      // Con «marca» los reencauches no se muestran: su marca es la de la carcasa y se comparan por banda en la tabla
      const hayReenc = !soloOriginales && ['proyeccion_km', 'km_mm', 'cpk'].some(c => tieneDatosVida((pv.reencauche || {})[c]));
      const vidas = hayReenc ? ['original', 'reencauche'] : ['original'];
      const graficas = [
        { clave: 'kpi14_proy', canvas: 'canvasKpi14_proy', campo: 'proyeccion_km', menor: false,
          fmt: (v) => `${formatCO_Miles(v)} ${uMed()}`, eje: (v) => formatCO_Miles(v),
          frase: (f) => `Mayor proyección. ${f}.` },
        { clave: 'kpi14_kmmm', canvas: 'canvasKpi14_kmmm', campo: 'km_mm', menor: false,
          fmt: (v) => `${formatCO_Decimal(v, 1)} ${uMed()}/mm`, eje: (v) => formatCO_Decimal(v, 1),
          frase: (f) => `Mejor rendimiento. ${f}.` },
        { clave: 'kpi14_cpk', canvas: 'canvasKpi14_cpk', campo: 'cpk', menor: true,
          fmt: (v) => `$ ${formatCO_Decimal(v, 2)}`, eje: (v) => `$${formatCO_Decimal(v, 1)}`,
          frase: (f) => `Más barata por ${uMed()}. ${f}.` }
      ];
      graficas.forEach(g => {
        const ctx = document.getElementById(g.canvas);
        if (!ctx) return;
        instanciasChartsSuite[g.clave] = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: pv.labels || [],
            datasets: vidas.map(vida => {
              const serie = (pv[vida] || {})[g.campo] || [];
              const col = VIDA_COLORES[vida];
              return { label: col.nombre, data: serie, backgroundColor: taMejorEn(serie, g.menor, col.fuerte, col.suave), borderRadius: 6,
                       datalabels: etiquetaSinChoque(g.fmt) };
            })
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 24 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: leyendaVida(vidas.map(v => VIDA_COLORES[v].fuerte)),
              tooltip: { callbacks: { label: (c) => {
                const n = (pv.llantas || {})[vidas[c.datasetIndex]]?.[c.dataIndex] || 0;
                return (c.raw === null || c.raw === undefined) ? `${c.dataset.label}: sin datos` : `${c.dataset.label} (${n} llantas): ${g.fmt(c.raw)}`;
              } } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: g.eje, font: { size: 9 } } },
              x: { ticks: ticksEtiquetaCorta(14) }
            }
          }
        });
        const f = fraseVida(pv, g.campo, g.menor, g.fmt, vidas);
        if (f) taLectura(g.canvas, 'in', g.frase(f));
      });
    }

    // KPI 13: Km Rodados Reales vs. Proyección Final al Límite de Retiro
    function renderChartKpi13(ds) {
      destruirChartSuite('kpi13_comparativo');
      const ctx = document.getElementById('canvasKpi13_comparativo');
      if (!ctx || !ds) return;
      destruirChartSuite('kpi13_reencauche');
      if (ds.por_referencia) { renderKpi13Referencia(ds.por_referencia); return; }
      if (ds.por_vida && (ds.por_vida.labels || []).length) { renderChartKpi13Vida(ds.por_vida); return; }

      // Rediseño: lo recorrido en azul fuerte y la proyección en azul claro
      const gradientReales = TA_G.azul;
      const gradientProy = TA_G.azulClaro;

      instanciasChartsSuite['kpi13_comparativo'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              label: unidadSuite === 'h' ? 'Horas reales' : 'Km Reales Rodados',
              data: ds.km_reales || [],
              backgroundColor: gradientReales,
              borderWidth: 0,
              borderRadius: 4,
              datalabels: pillDatalabelConfig('rgba(30, 64, 175, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} ${uMed()}`)
            },
            {
              label: 'Proyección Final al Retiro',
              data: ds.proyeccion_final || [],
              backgroundColor: gradientProy,
              borderWidth: 0,
              borderRadius: 4,
              datalabels: pillDatalabelConfig('rgba(37, 99, 235, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} ${uMed()}`)
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              cornerRadius: 10,
              padding: 12,
              callbacks: {
                label: (c) => `${c.dataset.label}: ${formatCO_Miles(c.raw)} ${uMed()}`,
                afterBody: (items) => {
                  const idx = items[0].dataIndex;
                  const r = ds.km_reales?.[idx] || 0;
                  const p = ds.proyeccion_final?.[idx] || 0;
                  const dif = Math.max(0, p - r);
                  return `Vida Remanente Est.: ${formatCO_Miles(dif)} ${uMed()}`;
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grace: '15%',
              title: { display: true, text: 'Kilómetros', font: { weight: 'bold', size: 10 } },
              grid: { color: 'rgba(226, 232, 240, 0.6)' },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            x: { ticks: ticksEtiquetaCorta(14) }
          }
        }
      });
      const i13 = taIndiceMayor(ds.proyeccion_final);
      if (i13 >= 0) {
        const i13b = taIndiceMayor(ds.proyeccion_final, true);
        const dif = (Number(ds.proyeccion_final[i13]) || 0) - (Number(ds.proyeccion_final[i13b]) || 0);
        taLectura('canvasKpi13_comparativo', 'in', `${ds.labels[i13]} proyecta ${formatCO_Miles(ds.proyeccion_final[i13])} ${uMed()} al retiro${i13b >= 0 && i13b !== i13 ? `, ${formatCO_Miles(dif)} más que ${ds.labels[i13b]}` : ''}.`);
      }
    }

    // ===== Rendimiento por referencia: originales (marca · diseño · medida · eje) y reencauches (banda · medida · eje).
    // Son dos universos que no se mezclan: en un reencauche se evalúa la banda, no la carcasa sobre la que va montada.
    const MAX_REF_GRAFICA = 10;
    const nombreRefOrig = (f) => [`${f.marca}${f.diseno ? ' ' + f.diseno : ''}`, `${f.dimension} · ${f.eje}`];
    const nombreRefReenc = (f) => [f.banda, `${f.dimension} · ${f.eje}`];
    const textoRef = (partes) => partes.join(' · ');

    function graficaReferencia(canvasId, clave, altoId, vacioId, notaId, filas, nombre, fuerte, suave) {
      destruirChartSuite(clave);
      const vacio = document.getElementById(vacioId), alto = document.getElementById(altoId), nota = document.getElementById(notaId);
      const conProy = (filas || []).filter(f => Number(f.proyeccion) > 0);
      if (vacio) vacio.classList.toggle('hidden', conProy.length > 0);
      if (alto) alto.classList.toggle('hidden', conProy.length === 0);
      if (!conProy.length) { taLectura(canvasId, null, ''); if (nota) nota.classList.add('hidden'); return null; }
      const top = conProy.slice(0, MAX_REF_GRAFICA);
      if (nota) {
        nota.classList.toggle('hidden', conProy.length <= MAX_REF_GRAFICA);
        nota.textContent = `Se muestran las ${MAX_REF_GRAFICA} referencias con más llantas; las ${conProy.length - MAX_REF_GRAFICA} restantes están en la tabla de KPI 14.`;
      }
      if (alto) alto.style.height = `${Math.max(160, 52 * top.length + 50)}px`;
      const u = uMed();
      const rodado = top.map(f => Math.min(Number(f.km_reales) || 0, Number(f.proyeccion)));
      const falta = top.map((f, i) => Math.max(0, Number(f.proyeccion) - rodado[i]));
      const ctx = document.getElementById(canvasId);
      if (!ctx) return top;
      // En pantallas angostas la etiqueta se acorta: «295/80 · Trac» en lugar de «295/80R22.5 · Tracción»
      const angosto = (ctx.parentElement?.clientWidth || 999) < 520;
      const corto = { 'Direccional': 'Dir', 'Tracción': 'Trac', 'Libre / Arrastre': 'Libre', 'Repuesto': 'Rep' };
      const etiquetaEje = (l) => angosto ? [l[0].length > 13 ? l[0].slice(0, 12) + '…' : l[0], l[1].replace(/R\d+(\.\d+)?/i, '').replace(/· (.+)$/, (m, e) => '· ' + (corto[e] || e))] : l;
      const etiquetaFin = pillDatalabelConfig(undefined, undefined, (v, c) => `${formatCO_Miles(top[c.dataIndex].proyeccion)} ${u}`);
      instanciasChartsSuite[clave] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: top.map(f => etiquetaEje(nombre(f))),
          datasets: [
            { label: 'Rodado', data: rodado, backgroundColor: fuerte, borderRadius: 4, barThickness: 20, datalabels: { display: false } },
            { label: 'Falta hasta el retiro', data: falta, backgroundColor: suave, borderRadius: 4, barThickness: 20, datalabels: etiquetaFin }
          ]
        },
        options: {
          indexAxis: 'y', responsive: true, maintainAspectRatio: false,
          layout: { padding: { top: 4, right: 78, bottom: 4, left: 4 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)', cornerRadius: 10, padding: 12,
              callbacks: {
                title: (items) => textoRef(nombre(top[items[0].dataIndex])),
                label: () => null,
                afterBody: (items) => {
                  const f = top[items[0].dataIndex];
                  const lineas = [`Llantas: ${f.llantas}`, `Rodado prom.: ${formatCO_Miles(f.km_reales)} ${u}`, `Proyección: ${formatCO_Miles(f.proyeccion)} ${u}`,
                                  `Km por mm: ${f.km_mm != null ? formatCO_Decimal(f.km_mm, 1) : '—'}`, `Costo por ${u}: ${f.cpk > 0 ? '$ ' + formatCO_Decimal(f.cpk, 2) : 'sin precio'}`];
                  if (f.carcasas && f.carcasas.length) lineas.push(`Carcasas: ${f.carcasas.join(', ')}`);
                  return lineas;
                }
              }
            }
          },
          scales: {
            x: { stacked: true, beginAtZero: true, grace: '8%', ticks: { callback: (v) => formatCO_Miles(v), font: { size: 9 } } },
            y: { stacked: true, ticks: { font: { size: 10, weight: 'bold' } } }
          }
        }
      });
      return top;
    }

    function renderKpi13Referencia(pr) {
      const u = uMed();
      const orig = graficaReferencia('canvasKpi13_comparativo', 'kpi13_comparativo', 'altoKpi13Orig', 'vacioKpi13Orig', 'notaKpi13Orig',
                                     pr.originales, nombreRefOrig, TA_G.azul, TA_G.azulClaro);
      const reenc = graficaReferencia('canvasKpi13_reencauche', 'kpi13_reencauche', 'altoKpi13Reenc', 'vacioKpi13Reenc', 'notaKpi13Reenc',
                                      pr.reencauches, nombreRefReenc, TA_G.ok, TA_G.okClaro);
      const mejor = (filas) => (filas || []).filter(f => Number(f.proyeccion) > 0).sort((a, b) => b.proyeccion - a.proyeccion)[0];
      const mo = mejor(pr.originales);
      if (orig && mo) taLectura('canvasKpi13_comparativo', 'in', `Mayor proyección: ${textoRef(nombreRefOrig(mo))}, ${formatCO_Miles(mo.proyeccion)} ${u} (lleva ${formatCO_Miles(mo.km_reales)}).`);
      if (reenc) {
        // La misma banda en varias medidas: se cuenta cuánto proyecta en cada una (BDM 295 proyecta 50.000, en 315 proyecta 30.000)
        const mr = mejor(pr.reencauches.filter(f => !f.sin_banda)) || mejor(pr.reencauches);
        const otras = pr.reencauches.filter(f => f.banda === mr.banda && f !== mr && Number(f.proyeccion) > 0);
        let t = `Mayor proyección: ${mr.banda} en ${mr.dimension} (${mr.eje.toLowerCase()}), ${formatCO_Miles(mr.proyeccion)} ${u}`;
        if (otras.length) t += `; la misma banda en ${otras.slice(0, 2).map(f => `${f.dimension} (${f.eje.toLowerCase()}) proyecta ${formatCO_Miles(f.proyeccion)}`).join(' y en ')}`;
        taLectura('canvasKpi13_reencauche', 'in', t + '.');
      }
    }

    function renderTablasReferenciaKpi14(pr) {
      const u = uMed();
      const num = (v, d = 0) => (v === null || v === undefined) ? '—' : (d ? formatCO_Decimal(v, d) : formatCO_Miles(v));
      const cpk = (v) => v > 0 ? `$ ${formatCO_Decimal(v, 2)}` : '<span class="text-slate-400">Sin precio</span>';
      const vacia = (n, txt) => `<tr><td colspan="${n}" class="p-4 text-center text-slate-400">${txt}</td></tr>`;
      const nota = (id, texto, ok) => {
        const e = document.getElementById(id);
        if (!e) return;
        e.classList.toggle('hidden', !texto);
        e.className = `${texto ? '' : 'hidden '}text-[12px] px-3 py-2 rounded-xl border ${ok ? 'bg-emerald-50 border-emerald-100 text-emerald-900' : 'bg-blue-50 border-blue-100 text-slate-700'}`;
        e.textContent = texto || '';
      };
      const orig = (pr && pr.originales) || [];
      const reenc = (pr && pr.reencauches) || [];
      const mejorCpk = (filas) => Math.min(...filas.map(f => Number(f.cpk)).filter(v => v > 0));
      const mcO = mejorCpk(orig), mcR = mejorCpk(reenc);

      const tO = document.getElementById('tbodyRefOrigKpi14');
      if (tO) tO.innerHTML = orig.length ? orig.map(f => `
        <tr>
          <td class="font-bold">${escapeHtml(f.marca)}${f.diseno ? ` <span class="text-slate-500 font-semibold">${escapeHtml(f.diseno)}</span>` : ''}</td>
          <td>${escapeHtml(f.dimension)}</td><td>${escapeHtml(f.eje)}</td>
          <td class="text-right">${num(f.llantas)}</td>
          <td class="text-right">${num(f.km_reales)} ${u}</td>
          <td class="text-right">${num(f.proyeccion)} ${u}</td>
          <td class="text-right">${num(f.km_mm, 1)}</td>
          <td class="text-right${Number(f.cpk) === mcO ? ' font-bold' : ''}">${cpk(f.cpk)}</td>
        </tr>`).join('') : vacia(8, 'No hay llantas originales con desgaste suficiente para proyectar.');

      const frente = (f) => {
        const ref = Number(f.cpk_original_misma_medida);
        if (!(ref > 0) || !(f.cpk > 0)) return '<span class="text-slate-400">Sin dato</span>';
        const p = Math.round((Number(f.cpk) / ref - 1) * 100);
        if (p === 0) return '<span class="ta-pastilla ok">Igual que la original</span>';
        return p < 0 ? `<span class="ta-pastilla ok">${Math.abs(p)} % más barata</span>` : `<span class="ta-pastilla cr">${p} % más cara</span>`;
      };
      const tR = document.getElementById('tbodyRefReencKpi14');
      if (tR) tR.innerHTML = reenc.length ? reenc.map(f => `
        <tr>
          <td class="font-bold">${escapeHtml(f.banda)}${f.sin_banda ? ' <span class="text-[10px] text-amber-700">· falta registrar la banda</span>' : ''}</td>
          <td>${escapeHtml(f.dimension)}</td><td>${escapeHtml(f.eje)}</td>
          <td class="text-right" title="${escapeHtml(f.carcasas && f.carcasas.length ? 'Carcasas: ' + f.carcasas.join(', ') : '')}">${num(f.llantas)}</td>
          <td class="text-right">${num(f.km_reales)} ${u}</td>
          <td class="text-right">${num(f.proyeccion)} ${u}</td>
          <td class="text-right">${num(f.km_mm, 1)}</td>
          <td class="text-right${Number(f.cpk) === mcR ? ' font-bold' : ''}">${cpk(f.cpk)}</td>
          <td>${frente(f)}</td>
        </tr>`).join('') : vacia(9, 'No hay reencauches con desgaste suficiente para proyectar.');

      // Conclusiones: la referencia más barata por km de cada universo
      const barata = (filas) => filas.filter(f => f.cpk > 0).sort((a, b) => a.cpk - b.cpk)[0];
      const bo = barata(orig), br = barata(reenc.filter(f => !f.sin_banda));
      nota('notaRefOrigKpi14', bo ? `Más barata por ${u}: ${textoRef(nombreRefOrig(bo))}, $ ${formatCO_Decimal(bo.cpk, 2)}.` : '', false);
      let tr = '';
      if (br) {
        tr = `Banda más barata por ${u}: ${textoRef(nombreRefReenc(br))}, $ ${formatCO_Decimal(br.cpk, 2)}`;
        const ref = Number(br.cpk_original_misma_medida);
        if (ref > 0) {
          const p = Math.round((1 - br.cpk / ref) * 100);
          tr += p > 0 ? `, ${p} % menos que una original de la misma medida y eje` : (p < 0 ? `, ${Math.abs(p)} % más que una original de la misma medida y eje` : '');
        }
        tr += '.';
      }
      if (pr && pr.reencauches_sin_banda > 0) tr += ` ${pr.reencauches_sin_banda} reencauche(s) sin banda registrada.`;
      nota('notaRefReencKpi14', tr.trim(), !!(br && Number(br.cpk_original_misma_medida) > br.cpk));
    }

    // Reencauches por banda: gráfica de costo por km (con la original de referencia en gris) y tabla con todas las medidas
    function renderBandasKpi14(pb) {
      const filas = (pb && pb.filas) || [];
      const orig = pb && pb.original;
      const vacio = document.getElementById('vacioBandasKpi14');
      const contenido = document.getElementById('contenidoBandasKpi14');
      const tbody = document.getElementById('tbodyBandasKpi14');
      if (!tbody) return;  // la sección por banda fue reemplazada por las tablas por referencia
      const hay = filas.length > 0;
      if (vacio) vacio.classList.toggle('hidden', hay);
      if (contenido) contenido.classList.toggle('hidden', !hay);
      if (!hay) { tbody.innerHTML = ''; taLectura('canvasKpi14_bandas', null, ''); return; }

      const u = uMed();
      const th = (id, t) => { const e = document.getElementById(id); if (e) e.textContent = t; };
      th('thBandaRecorrido', unidadSuite === 'h' ? 'Horas prom.' : 'Recorrido prom.');
      th('thBandaKmmm', `${unidadSuite === 'h' ? 'Horas' : 'Km'} por mm`);
      th('thBandaCpk', `Costo por ${u}`);
      const num = (v, d = 0) => (v === null || v === undefined) ? '—' : (d ? formatCO_Decimal(v, d) : formatCO_Miles(v));
      const cpkOrig = orig && orig.cpk > 0 ? Number(orig.cpk) : null;
      const mejorCpk = Math.min(...filas.map(f => Number(f.cpk)).filter(v => v > 0));
      const mejorKmmm = Math.max(...filas.map(f => Number(f.km_mm)).filter(v => v > 0));
      // Diferencia de costo por km frente a la original: verde si es más barata, rojo si es más cara
      const frente = (f) => {
        if (!cpkOrig || !(f.cpk > 0)) return '<span class="text-slate-400">Sin dato</span>';
        const p = Math.round((Number(f.cpk) / cpkOrig - 1) * 100);
        if (p === 0) return '<span class="ta-pastilla ok">Igual que la original</span>';
        return p < 0 ? `<span class="ta-pastilla ok">${Math.abs(p)} % más barata</span>` : `<span class="ta-pastilla cr">${p} % más cara</span>`;
      };
      const filaHtml = (f, esOrig) => `
        <tr${esOrig ? ' class="bg-slate-50"' : ''}>
          <td class="font-bold">${esOrig ? '<span class="text-slate-500">Llanta original (referencia)</span>' : escapeHtml(f.banda)}${f.sin_banda ? ' <span class="text-[10px] text-amber-700">· falta registrar la banda</span>' : ''}</td>
          <td class="text-right">${num(f.llantas)}</td>
          <td class="text-right${!esOrig && Number(f.cpk) === mejorCpk ? ' font-bold' : ''}">${f.cpk > 0 ? `$ ${num(f.cpk, 2)}` : '—'}</td>
          <td>${esOrig ? '<span class="text-slate-400">—</span>' : frente(f)}</td>
          <td class="text-right${!esOrig && Number(f.km_mm) === mejorKmmm ? ' font-bold' : ''}">${num(f.km_mm, 1)}</td>
          <td class="text-right">${num(f.proyeccion)} ${u}</td>
          <td class="text-right">${num(f.km_reales)} ${u}</td>
        </tr>`;
      tbody.innerHTML = filas.map(f => filaHtml(f, false)).join('') + (orig ? filaHtml(orig, true) : '');

      // Gráfica: barras horizontales; la mejor banda en verde fuerte, las demás en verde claro y la original en gris
      const ctx = document.getElementById('canvasKpi14_bandas');
      const conCpk = filas.filter(f => f.cpk > 0);
      const etiquetas = conCpk.map(f => f.banda).concat(cpkOrig ? ['Original'] : []);
      const valores = conCpk.map(f => Number(f.cpk)).concat(cpkOrig ? [cpkOrig] : []);
      const colores = conCpk.map(f => Number(f.cpk) === mejorCpk ? TA_G.ok : TA_G.okClaro).concat(cpkOrig ? [TA_G.gris] : []);
      const alto = document.getElementById('altoGraficaBandasKpi14');
      if (alto) alto.style.height = `${Math.max(180, 46 * etiquetas.length + 40)}px`;
      if (ctx && etiquetas.length) {
        instanciasChartsSuite['kpi14_bandas'] = new Chart(ctx, {
          type: 'bar',
          data: { labels: etiquetas, datasets: [{ label: `Costo por ${u}`, data: valores, backgroundColor: colores, borderRadius: 6, barThickness: 22,
                   datalabels: pillDatalabelConfig(undefined, undefined, (v) => `$ ${formatCO_Decimal(v, 2)}`) }] },
          options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            layout: { padding: { top: 4, right: 64, bottom: 4, left: 4 } },
            animation: animacionCascadaStandard,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `Costo por ${u}: $ ${formatCO_Decimal(c.raw, 2)}` } } },
            scales: {
              x: { beginAtZero: true, grace: '10%', ticks: { callback: (v) => `$${formatCO_Decimal(v, 0)}`, font: { size: 9 } } },
              y: { ticks: { font: { size: 11, weight: 'bold' } } }
            }
          }
        });
      }

      // Conclusión en palabras sencillas
      const mejor = conCpk[0];
      let texto = '';
      if (mejor) {
        texto = `${mejor.banda} es la banda más barata por ${u}: $ ${formatCO_Decimal(mejor.cpk, 2)}`;
        if (cpkOrig) {
          const p = Math.round((1 - Number(mejor.cpk) / cpkOrig) * 100);
          texto += p > 0 ? `, ${p} % menos que una llanta original` : (p < 0 ? `, pero cuesta ${Math.abs(p)} % más que una llanta original` : ', igual que una llanta original');
        }
        texto += '.';
        const peor = conCpk[conCpk.length - 1];
        if (peor && peor !== mejor) {
          const dif = Math.round((Number(peor.cpk) / Number(mejor.cpk) - 1) * 100);
          texto += ` ${peor.banda} cuesta ${dif} % más que ${mejor.banda}.`;
        }
      }
      if (pb.reencauches_sin_banda > 0) texto += ` ${pb.reencauches_sin_banda} reencauche(s) sin banda registrada.`;
      taLectura('canvasKpi14_bandas', mejor && cpkOrig && Number(mejor.cpk) < cpkOrig ? 'ok' : 'in', texto.trim());
    }

    // KPI 14: Tríada Multidimensional Sincronizada (Proyección, Km/mm, CPK)
    function renderChartKpi14(ds) {
      destruirChartSuite('kpi14_proy');
      destruirChartSuite('kpi14_kmmm');
      destruirChartSuite('kpi14_cpk');
      destruirChartSuite('kpi14_bandas');
      if (!ds) return;

      const sel = document.getElementById('selAgrupacionKpi14');
      if (sel && ds.agrupacion_actual && sel.value !== ds.agrupacion_actual) {
        sel.value = ds.agrupacion_actual;
      }

      if (ds.por_referencia) renderTablasReferenciaKpi14(ds.por_referencia); else renderBandasKpi14(ds.por_banda);
      const soloOriginales = (ds.agrupacion_actual || 'marca') === 'marca';
      const notaMarca = document.getElementById('notaMarcaKpi14');
      if (notaMarca) notaMarca.classList.toggle('hidden', !soloOriginales);
      if (ds.por_vida && (ds.por_vida.labels || []).length) { renderChartKpi14Vida(ds.por_vida, soloOriginales); return; }
      const labels = ds.labels || [];

      // 1. Proyección Km Final (Índigo)
      const ctxProy = document.getElementById('canvasKpi14_proy');
      if (ctxProy) {
        const gradProy = taMejorEn(ds.proyeccion_km);

        instanciasChartsSuite['kpi14_proy'] = new Chart(ctxProy, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: unidadSuite === 'h' ? 'Proy. horas final' : 'Proy. Km Final',
              data: ds.proyeccion_km || [],
              backgroundColor: gradProy,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(67, 56, 202, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} ${uMed()}`)
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 24 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Proyección: ${formatCO_Miles(c.raw)} ${uMed()}` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => formatCO_Miles(v), font: { size: 9 } } },
              x: { ticks: ticksEtiquetaCorta(14) }
            }
          }
        });
      }

      // 2. Rendimiento Km/mm (Esmeralda)
      const ctxKmmm = document.getElementById('canvasKpi14_kmmm');
      if (ctxKmmm) {
        const gradKmmm = taMejorEn(ds.km_mm);

        instanciasChartsSuite['kpi14_kmmm'] = new Chart(ctxKmmm, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: `Rendimiento ${uMed()}/mm`,
              data: ds.km_mm || [],
              backgroundColor: gradKmmm,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(4, 120, 87, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} ${uMed()}/mm`)
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 24 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Rendimiento: ${formatCO_Decimal(c.raw, 1)} ${uMed()}/mm` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => formatCO_Decimal(v, 1), font: { size: 9 } } },
              x: { ticks: ticksEtiquetaCorta(14) }
            }
          }
        });
      }

      // 3. Costo por Kilómetro CPK (Púrpura)
      const ctxCpk = document.getElementById('canvasKpi14_cpk');
      if (ctxCpk) {
        const gradCpk = taMejorEn(ds.cpk, true);

        instanciasChartsSuite['kpi14_cpk'] = new Chart(ctxCpk, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: `CPK proyectado ($/${uMed()})`,
              data: ds.cpk || [],
              backgroundColor: gradCpk,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(126, 34, 206, 0.9)', '#ffffff', (v) => `$ ${formatCO_Decimal(v, 2)}`)
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 24 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `CPK: $ ${formatCO_Decimal(c.raw, 2)} COP/${uMed()}` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => `$${formatCO_Decimal(v, 1)}`, font: { size: 9 } } },
              x: { ticks: ticksEtiquetaCorta(14) }
            }
          }
        });
      }

      // Conclusiones: el mejor de cada indicador
      const iP = taIndiceMayor(ds.proyeccion_km);
      if (iP >= 0) taLectura('canvasKpi14_proy', 'in', `Mayor proyección: ${labels[iP]} con ${formatCO_Miles(ds.proyeccion_km[iP])} ${uMed()} (mayor es mejor).`);
      const iK = taIndiceMayor(ds.km_mm);
      if (iK >= 0) taLectura('canvasKpi14_kmmm', 'in', `Mejor rendimiento: ${labels[iK]} con ${formatCO_Decimal(ds.km_mm[iK], 1)} ${uMed()} por milímetro.`);
      const iC = taIndiceMayor(ds.cpk, true);
      const iCmax = taIndiceMayor(ds.cpk);
      if (iC >= 0) {
        const extra = iCmax >= 0 && iCmax !== iC && Number(ds.cpk[iC]) > 0
          ? ` ${labels[iCmax]} cuesta ${Math.round((Number(ds.cpk[iCmax]) / Number(ds.cpk[iC]) - 1) * 100)} % más.` : '';
        taLectura('canvasKpi14_cpk', 'in', `Más barata por ${uMed()}: ${labels[iC]}, $ ${formatCO_Decimal(ds.cpk[iC], 1)} (menor es mejor).${extra}`);
      }
    }

    // Tendencias mensuales (gerencia)
    function renderTendencias(t) {
      const meses = (t && t.meses) || [];
      const pct = v => (v === null || v === undefined) ? '-' : `${formatCO_Decimal(v, 1)}%`;
      const tb = document.getElementById('tbodyTendencias');
      if (tb) tb.innerHTML = meses.slice().reverse().map(m => `<tr>
          <td class="p-2 font-bold">${_mesLegible(m.mes)}</td><td class="p-2 text-right">${escapeHtml(m.vehiculos_inspeccionados)}${m.pct_cumplimiento_parque == null ? '' : `<span class="block text-[10px] text-indigo-600 font-bold whitespace-nowrap">${pct(m.pct_cumplimiento_parque)} del parque</span>`}</td>
          <td class="p-2 text-right">${pct(m.pct_presion_correcta)}</td><td class="p-2 text-right">${pct(m.pct_en_retiro)}</td>
          <td class="p-2 text-right">${m.prof_minima_promedio == null ? '-' : formatCO_Decimal(m.prof_minima_promedio, 1) + ' mm'}</td>
          <td class="p-2 text-right">${pct(m.pct_alerta_alineacion)}</td>
          <td class="p-2 text-right">${m.cpk_operativo == null ? '-' : '$ ' + formatCO_Decimal(m.cpk_operativo, 1) + ' /' + uMed()}</td></tr>`).join('')
        || '<tr><td colspan="7" class="p-2 text-slate-400 italic">Sin inspecciones en el periodo</td></tr>';
      destruirChartSuite('tendencias');
      const ctx = document.getElementById('canvasTendencias');
      if (!ctx || !meses.length) return;
      const serie = (k, label, color) => ({ label, data: meses.map(m => m[k]), borderColor: color, backgroundColor: color, tension: 0.25, spanGaps: true });
      const series = [
        serie('pct_presion_correcta', 'Presión correcta (%)', TA_G.ok),
        serie('pct_en_retiro', 'En límite de retiro (%)', TA_G.cr),
        serie('pct_alerta_alineacion', 'Alerta de alineación (%)', TA_G.al)];
      if (meses.some(m => m.pct_cumplimiento_parque != null)) {
        series.unshift({ ...serie('pct_cumplimiento_parque', 'Parque inspeccionado (%)', TA_G.azul), borderWidth: 3 });
      }
      instanciasChartsSuite['tendencias'] = new Chart(ctx, {
        type: 'line',
        data: { labels: meses.map(m => _mesLegible(m.mes)), datasets: series },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } },
            // Rediseño: solo el valor del último mes, del color de su serie (antes un globo en cada punto)
            datalabels: {
              display: (ctx) => {
                const v = ctx.dataset.data[ctx.dataIndex];
                return (v !== null && v !== undefined && v !== '') && ctx.dataIndex === taUltimos(ctx.dataset.data).i;
              },
              anchor: 'end',
              align: 'right',
              offset: 4,
              clamp: true,
              color: (ctx) => ctx.dataset.borderColor || TA_G.texto,
              font: { weight: '700', size: 11 },
              formatter: (v) => `${formatCO_Decimal(v, 0)}%`
            }
          },
          layout: { padding: { top: 22, right: 40, bottom: 6, left: 6 } },
          scales: { y: { min: 0, max: 100, ticks: { callback: v => `${v}%` } } }
        }
      });
      const ult = meses[meses.length - 1] || {};
      const partes = [];
      if (ult.pct_cumplimiento_parque != null) partes.push(`parque inspeccionado ${formatCO_Decimal(ult.pct_cumplimiento_parque, 0)} %`);
      if (ult.pct_presion_correcta != null) partes.push(`presión correcta ${formatCO_Decimal(ult.pct_presion_correcta, 0)} %`);
      if (ult.pct_en_retiro != null) partes.push(`en retiro ${formatCO_Decimal(ult.pct_en_retiro, 1)} %`);
      if (ult.pct_alerta_alineacion != null) partes.push(`alerta de alineación ${formatCO_Decimal(ult.pct_alerta_alineacion, 1)} %`);
      if (partes.length) taLectura('canvasTendencias', 'in', `${_mesLegible(ult.mes)}: ${partes.join('; ')}.`);
    }

    function _mesLegible(m) {
      const nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
      const [a, mm] = String(m || '').split('-');
      // 'Sep 26', igual que las demás gráficas mensuales (antes 'Sep 2026')
      return mm ? `${nombres[parseInt(mm, 10) - 1]} ${String(a).slice(-2)}` : m;
    }

    // KPI CPK: los 4 costos por kilómetro (sin dato = sin precio o sin km suficientes)
    function renderKpiCpk(k) {
      const fmt = v => (v === null || v === undefined) ? 'Sin dato' : `$ ${Number(v).toLocaleString('es-CO', { maximumFractionDigits: 1 })} /${uMed()}`;
      const f = k.flota || {};
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set('kpiCpkOperativo', fmt(f.cpk_operativo));
      set('kpiCpkProyectado', fmt(f.cpk_proyectado));
      set('kpiCpkTotal', fmt(f.cpk_total));
      const adm = (k.administrativo || []).filter(m => m.km_flota > 0);
      set('kpiCpkAdmin', adm.length ? fmt(adm[adm.length - 1].cpk_administrativo) : 'Sin dato');
      set('kpiCpkNota', `${f.llantas_con_cpk || 0} vidas de llanta con CPK; ${f.llantas_sin_precio || 0} sin precio (registre la lista de precios del cliente en Catálogos).`);
      const tv = document.getElementById('tbodyCpkPorVida');
      if (tv) tv.innerHTML = (k.por_vida || []).map(v => `<tr><td class="p-2 font-bold">${escapeHtml(v.vida)}</td><td class="p-2 text-right">${escapeHtml(v.llantas)}</td>
        <td class="p-2 text-right font-mono">${fmt(v.cpk_operativo)}</td><td class="p-2 text-right font-mono">${fmt(v.cpk_proyectado)}</td></tr>`).join('')
        || '<tr><td colspan="4" class="p-2 text-slate-400 italic">Sin datos</td></tr>';
      const ta = document.getElementById('tbodyCpkAdmin');
      if (ta) ta.innerHTML = (k.administrativo || []).slice().reverse().map(m => `<tr><td class="p-2 font-bold">${escapeHtml(m.mes)}</td>
        <td class="p-2 text-right font-mono">${m.inversion ? formatCO_Moneda(m.inversion) : '-'}</td>
        <td class="p-2 text-right font-mono">${m.km_flota ? Number(m.km_flota).toLocaleString('es-CO') : '-'}</td>
        <td class="p-2 text-right font-mono">${fmt(m.cpk_administrativo)}</td></tr>`).join('')
        || '<tr><td colspan="4" class="p-2 text-slate-400 italic">Sin instalaciones registradas en Bodegas</td></tr>';
    }

    // KPI 15: Potencial de Llanta: Proyección vs Máx y Mín (Filtro Madurez >= 1.5mm)
    function renderChartKpi15(ds) {
      destruirChartSuite('kpi15_potencial');
      const ctx = document.getElementById('canvasKpi15_potencial');
      if (!ctx || !ds) return;

      const badgeBrecha = document.getElementById('kpi15_brecha_badge');
      if (badgeBrecha && ds.brecha_promedio_total !== undefined) {
        const br = ds.brecha_promedio_total;
        badgeBrecha.textContent = `Brecha: ${formatCO_Decimal(br, 1)}%`;
        if (br < 15) {
          badgeBrecha.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300';
        } else if (br < 30) {
          badgeBrecha.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300';
        } else {
          badgeBrecha.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300';
        }
      }

      // Rediseño: promedio en azul claro; mejor llanta en azul y peor llanta en gris
      const gradProm = TA_G.azulClaro;

      instanciasChartsSuite['kpi15_potencial'] = new Chart(ctx, {
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Proyección Promedio',
              data: ds.promedio || [],
              backgroundColor: gradProm,
              borderWidth: 0,
              borderRadius: 4,
              datalabels: pillDatalabelConfig('rgba(30, 64, 175, 0.85)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: 'Máximo Alcanzado',
              data: ds.maximo || [],
              borderColor: TA_G.azul,
              backgroundColor: TA_G.azul,
              borderWidth: 2.5,
              pointRadius: 4,
              tension: 0.25,
              datalabels: pillDatalabelConfig('rgba(2, 132, 199, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: 'Mínimo / Peor Desempeño',
              data: ds.minimo || [],
              borderColor: TA_G.gris,
              backgroundColor: TA_G.gris,
              borderWidth: 2.5,
              pointRadius: 4,
              tension: 0.25,
              datalabels: pillDatalabelConfig('rgba(217, 119, 6, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 24 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              cornerRadius: 10,
              padding: 12,
              callbacks: {
                label: (c) => `${c.dataset.label}: ${formatCO_Miles(c.raw)} ${uMed()}`
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grace: '15%',
              title: { display: true, text: 'Kilómetros', font: { weight: 'bold', size: 10 } },
              grid: { color: 'rgba(226, 232, 240, 0.6)' },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            x: { ticks: ticksEtiquetaCorta(14) }
          }
        }
      });
      const i15 = taIndiceMayor(ds.promedio);
      if (i15 >= 0) {
        taLectura('canvasKpi15_potencial', 'in', `${ds.labels[i15]}: entre ${formatCO_Miles(ds.minimo?.[i15])} y ${formatCO_Miles(ds.maximo?.[i15])} ${uMed()}; ${formatCO_Miles(ds.promedio[i15])} en promedio.`);
      }
    }

    // KPI 16: Curva de Proyección por Rango de Desgaste (Madurez del Caucho)
    function renderChartKpi16(ds) {
      destruirChartSuite('kpi16_rangos');
      const ctx = document.getElementById('canvasKpi16_rangos');
      if (!ctx || !ds) return;
      // Rediseño: las dos bandas de mayor desgaste en ámbar y rojo (las que piden acción); el resto en azul claro
      const nB = (ds.conteo_llantas || []).length;
      const coloresBandas = (ds.conteo_llantas || []).map((_, i) => (nB >= 3 && i === nB - 1) ? TA_G.cr : (nB >= 3 && i === nB - 2) ? TA_G.al : TA_G.azulClaro);

      instanciasChartsSuite['kpi16_rangos'] = new Chart(ctx, {
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Llantas en Banda',
              data: ds.conteo_llantas || [],
              backgroundColor: coloresBandas,
              borderWidth: 0,
              borderRadius: 4,
              yAxisID: 'y',
              datalabels: pillDatalabelConfig('rgba(79, 70, 229, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: `Proyección Promedio (${uMed()})`,
              data: ds.proyeccion_promedio || [],
              borderColor: TA_G.gris,
              backgroundColor: 'transparent',
              fill: false,
              borderWidth: 2,
              pointRadius: 3,
              tension: 0.35,
              yAxisID: 'y1',
              datalabels: { display: false }
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              cornerRadius: 10,
              padding: 12
            }
          },
          scales: {
            y: {
              type: 'linear',
              position: 'left',
              beginAtZero: true,
              grace: '15%',
              title: { display: true, text: 'Cantidad de Llantas', font: { weight: 'bold', size: 10 } },
              grid: { color: 'rgba(226, 232, 240, 0.6)' },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            y1: {
              type: 'linear',
              position: 'right',
              beginAtZero: true,
              grace: '15%',
              title: { display: true, text: `Proyección (${uMed()})`, font: { weight: 'bold', size: 10 } },
              grid: { drawOnChartArea: false },
              ticks: { callback: (v) => `${formatCO_Miles(v)} ${uMed()}` }
            },
            x: { ticks: { font: { weight: 'bold', size: 10 } } }
          }
        }
      });
      if (nB >= 3) {
        const cerca = (Number(ds.conteo_llantas[nB - 2]) || 0) + (Number(ds.conteo_llantas[nB - 1]) || 0);
        taLectura('canvasKpi16_rangos', cerca > 0 ? 'al' : 'ok', cerca > 0
          ? `${formatCO_Miles(cerca)} llantas están en las dos bandas de mayor desgaste (${ds.labels[nB - 2]} y ${ds.labels[nB - 1]}).`
          : 'Ninguna llanta en las bandas de mayor desgaste.');
      }
    }

    // ==========================================
    // RENDERERS SUB-PESTAÑA 4 (KPI 17 AL 19) [SOLO FULL]
    // ==========================================

    // KPI 17: Indicadores Globales FVU
    function renderKpi17(d) {
      if (!d) return;
      const elCant = document.getElementById('kpi17_cantidad_fvu');
      const elIr = document.getElementById('kpi17_ir_fvu');
      const elPctReen = document.getElementById('kpi17_pct_reenc_fvu');

      if (elCant) elCant.textContent = `${formatCO_Miles(d.cantidad_fvu || 0)} llantas`;
      if (elIr) elIr.textContent = formatCO_Decimal(d.indice_reencauchabilidad_ir || 0, 2);
      if (elPctReen) elPctReen.textContent = `${formatCO_Decimal(d.pct_reencauche_fvu || 0, 1)}%`;
      const elNota = document.getElementById('kpi17_nota_sin_fecha');
      if (elNota) {
        const sinFecha = d.bajas_sin_fecha || 0;
        elNota.classList.toggle('hidden', !sinFecha);
        elNota.textContent = sinFecha
          ? `⚠️ ${formatCO_Miles(sinFecha)} de ${formatCO_Miles(d.cantidad_fvu)} bajas no tienen fecha de baja registrada: cuentan en el total pero no aparecen en la gráfica mensual.`
          : '';
      }

      destruirChartSuite('kpi17_lineas');
      const ctx = document.getElementById('canvasKpi17_lineas');
      if (!ctx || !d.grafico_12m) return;

      const g = d.grafico_12m;
      // Rediseño: las bajas en gris (contexto) y el índice de reencauchabilidad en azul (lo que se sigue)
      const gradBar = TA_G.grisClaro;

      instanciasChartsSuite['kpi17_lineas'] = new Chart(ctx, {
        data: {
          labels: g.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Bajas FVU (Llantas)',
              data: g.cantidad || [],
              backgroundColor: gradBar,
              borderRadius: 6,
              yAxisID: 'y',
              datalabels: pillDatalabelConfig('rgba(190, 18, 60, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: 'Índice Reencauchabilidad (I.R.)',
              data: g.ir || [],
              borderColor: TA_G.azul,
              backgroundColor: taRgba(TA_G.azul, 0.07),
              fill: true,
              borderWidth: 2.5,
              pointRadius: 3,
              tension: 0.35,
              yAxisID: 'y1',
              datalabels: pillDatalabelConfig('rgba(79, 70, 229, 0.9)', '#ffffff', (v) => formatCO_Decimal(v, 2))
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              cornerRadius: 10,
              padding: 12
            }
          },
          scales: {
            y: {
              type: 'linear',
              position: 'left',
              beginAtZero: true,
              grace: '15%',
              title: { display: true, text: 'Llantas FVU', font: { weight: 'bold', size: 10 } },
              grid: { color: 'rgba(226, 232, 240, 0.6)' },
              ticks: { callback: (v) => formatCO_Miles(v) }
            },
            y1: {
              type: 'linear',
              position: 'right',
              beginAtZero: true,
              grace: '15%',
              title: { display: true, text: 'I.R. FVU', font: { weight: 'bold', size: 10 } },
              grid: { drawOnChartArea: false },
              ticks: { callback: (v) => formatCO_Decimal(v, 1) }
            },
            x: { ticks: { font: { weight: 'bold', size: 11 } } }
          }
        }
      });
      const bajas12 = taSuma(g.cantidad);
      taLectura('canvasKpi17_lineas', 'in', bajas12 > 0
        ? `${formatCO_Miles(bajas12)} llantas dadas de baja en el periodo; índice de reencauchabilidad global: ${formatCO_Decimal(d.indice_reencauchabilidad_ir || 0, 2)}.`
        : 'Sin bajas registradas en el periodo.');
    }

    // KPI 18: Participación FVU por Marca, Ciclo y Causal de Daño (+ Alerta Garantía)
    // Módulo C: resistencia de carcasas por marca y medida (gráfica de ciclo alcanzado y tabla)
    function renderCarcasasKpi18(filas) {
      destruirChartSuite('kpi18_carcasas');
      filas = filas || [];
      const vacio = document.getElementById('vacioCarcasasKpi18'), cont = document.getElementById('contenidoCarcasasKpi18');
      if (vacio) vacio.classList.toggle('hidden', filas.length > 0);
      if (cont) cont.classList.toggle('hidden', filas.length === 0);
      const tbody = document.getElementById('tbodyCarcasasKpi18');
      if (!filas.length) { if (tbody) tbody.innerHTML = ''; taLectura('canvasKpi18_carcasas', null, ''); return; }
      const u = uMed();
      const dec = (v, d = 1) => (v === null || v === undefined) ? '—' : formatCO_Decimal(v, d);
      const maxAlBaja = Math.max(...filas.map(f => Number(f.reencauches_al_baja)).filter(v => Number.isFinite(v)));
      const minCpk = Math.min(...filas.map(f => Number(f.cpk_total_vida)).filter(v => v > 0));
      if (tbody) tbody.innerHTML = filas.map(f => `
        <tr>
          <td class="font-bold">${escapeHtml(f.marca)}</td>
          <td>${escapeHtml(f.dimension)}</td>
          <td class="text-right">${formatCO_Miles(f.carcasas)}</td>
          <td class="text-right">${dec(f.reencauches_por_carcasa)}</td>
          <td class="text-right${Number(f.reencauches_al_baja) === maxAlBaja ? ' font-bold' : ''}">${f.reencauches_al_baja === null ? '<span class="text-slate-400">Sin bajas</span>' : dec(f.reencauches_al_baja)}</td>
          <td class="text-right">${formatCO_Miles(f.bajas)}</td>
          <td>${f.causa_principal ? `${escapeHtml(f.causa_principal)} <span class="text-slate-400">(${dec(f.causa_pct, 0)} %)</span>` : '<span class="text-slate-400">—</span>'}</td>
          <td class="text-right${Number(f.cpk_total_vida) === minCpk ? ' font-bold' : ''}">${f.cpk_total_vida > 0 ? `$ ${dec(f.cpk_total_vida, 2)}` : '<span class="text-slate-400">Sin dato</span>'}</td>
          <td class="text-right">${f.km_vida_promedio ? `${formatCO_Miles(f.km_vida_promedio)} ${u}` : '—'}</td>
        </tr>`).join('');

      // Gráfica: barras horizontales apiladas con el ciclo alcanzado (más oscuro = más reencauches)
      const top = filas.slice(0, 10);
      const alto = document.getElementById('altoCarcasasKpi18');
      if (alto) alto.style.height = `${Math.max(160, 40 * top.length + 60)}px`;
      const ctx = document.getElementById('canvasKpi18_carcasas');
      const ciclos = ['Original', 'R1', 'R2', 'R3+'];
      const colores = taEscalaAzul(4);
      if (ctx) {
        instanciasChartsSuite['kpi18_carcasas'] = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: top.map(f => `${f.marca} · ${f.dimension}`),
            datasets: ciclos.map((cn, i) => ({
              label: cn, data: top.map(f => (f.ciclos || {})[cn] || 0), backgroundColor: colores[i], borderRadius: 3, barThickness: 20,
              datalabels: { display: (c) => (c.dataset.data[c.dataIndex] || 0) > 0, color: taTextoSobre(colores[i]), font: { weight: 'bold', size: 10 } }
            }))
          },
          options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
              tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw} carcasa(s)`,
                                      afterBody: (items) => { const f = top[items[0].dataIndex]; return [`Reencauches por carcasa: ${dec(f.reencauches_por_carcasa)}`, `Al darse de baja: ${f.reencauches_al_baja === null ? 'sin bajas' : dec(f.reencauches_al_baja)}`]; } } }
            },
            scales: { x: { stacked: true, beginAtZero: true, ticks: { precision: 0, font: { size: 9 } } }, y: { stacked: true, ticks: { font: { size: 10, weight: 'bold' } } } }
          }
        });
      }

      // Conclusión: la carcasa que más reencauches aguanta (con bajas, que es cuando la vida terminó) y su causa de baja
      const conBajas = filas.filter(f => f.reencauches_al_baja !== null);
      let t;
      if (conBajas.length) {
        const m = conBajas.slice().sort((a, b) => b.reencauches_al_baja - a.reencauches_al_baja || b.carcasas - a.carcasas)[0];
        t = `${m.marca} ${m.dimension} es la carcasa que más aguanta: ${dec(m.reencauches_al_baja)} reencauches en promedio al darse de baja`;
        if (m.causa_principal) t += `. Causa principal de baja: ${m.causa_principal} (${dec(m.causa_pct, 0)} %)`;
        t += '.';
      } else {
        const m = filas[0];
        t = `Aún no hay carcasas dadas de baja. Por ahora ${m.marca} ${m.dimension} lleva más reencauches: ${dec(m.reencauches_por_carcasa)} por carcasa.`;
      }
      taLectura('canvasKpi18_carcasas', 'in', t);
    }

    function renderChartKpi18(d) {
      destruirChartSuite('kpi18_marca');
      destruirChartSuite('kpi18_ciclo');
      destruirChartSuite('kpi18_causal');
      if (!d) return;

      // Bajas con profundidad actual mayor que la inicial: dato imposible, no se cuentan como garantía
      const notaInc = document.getElementById('kpi18_nota_inconsistente');
      if (notaInc) {
        const nInc = d.bajas_profundidad_inconsistente || 0;
        notaInc.classList.toggle('hidden', !nInc);
        notaInc.textContent = nInc
          ? `⚠️ ${formatCO_Miles(nInc)} bajas tienen la profundidad actual mayor que la inicial (dato imposible): no se cuentan como garantía. Corrija su profundidad en Bodegas.`
          : '';
      }

      // Badge garantía
      const badgeGarantia = document.getElementById('kpi18_badge_garantia');
      const numGar = (d.alertas_garantia || []).length;
      if (badgeGarantia) {
        badgeGarantia.textContent = `${numGar} en Garantía (<30%)`;
        if (numGar > 0) {
          badgeGarantia.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300 animate-pulse';
        } else {
          badgeGarantia.className = 'text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200';
        }
      }

      // A. Bajas por Marca (Barras)
      const ctxMarca = document.getElementById('canvasKpi18_marca');
      if (ctxMarca && d.por_marca) {
        const gradM = taMejorEn(d.por_marca.valores);

        instanciasChartsSuite['kpi18_marca'] = new Chart(ctxMarca, {
          type: 'bar',
          data: {
            labels: d.por_marca.labels || [],
            datasets: [{
              label: 'Bajas FVU',
              data: d.por_marca.valores || [],
              backgroundColor: gradM,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(225, 29, 72, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 24, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Llantas dadas de baja: ${formatCO_Miles(c.raw)}` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { font: { size: 9 } } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // B. Por Ciclo de Vida (Barras Agrupadas)
      const ctxCiclo = document.getElementById('canvasKpi18_ciclo');
      if (ctxCiclo && d.por_ciclo) {
        // Rediseño: un solo azul que se oscurece de Original a R3+
        const coloresCiclos = taEscalaAzul(Math.max(2, (d.por_ciclo.labels || []).length));
        instanciasChartsSuite['kpi18_ciclo'] = new Chart(ctxCiclo, {
          type: 'bar',
          data: {
            labels: d.por_ciclo.labels || [],
            datasets: [{
              label: 'Ciclo de Fallo',
              data: d.por_ciclo.valores || [],
              backgroundColor: coloresCiclos,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(15, 23, 42, 0.85)', '#ffffff', (v) => formatCO_Miles(v))
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 24, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Llantas: ${formatCO_Miles(c.raw)}` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { font: { size: 9 } } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // C. Causales de Daño (dona: desgaste normal en gris y daños evitables en tonos de rojo)
      const ctxCausal = document.getElementById('canvasKpi18_causal');
      if (ctxCausal && d.por_causal) {
        const esNormal = (l) => /desgaste\s*normal|fin\s*de\s*vida|normal/i.test(String(l || ''));
        const labCausal = d.por_causal.labels || [];
        let kRojo = 0;
        const coloresCausal = labCausal.map(l => (esNormal(l) ? TA_G.gris : taMezclar(TA_G.cr, '#ffffff', Math.min(0.6, 0.18 * kRojo++))));
        instanciasChartsSuite['kpi18_causal'] = new Chart(ctxCausal, taDona(labCausal, d.por_causal.valores || [], coloresCausal, { subtexto: 'Bajas' }));
        const totCausal = taSuma(d.por_causal.valores);
        const evitables = taSuma((d.por_causal.valores || []).filter((_, i) => !esNormal(labCausal[i])));
        if (totCausal > 0) {
          taLectura('canvasKpi18_causal', evitables > 0 ? 'cr' : 'ok', evitables > 0
            ? `${formatCO_Miles(evitables)} de ${formatCO_Miles(totCausal)} bajas (${taPct(evitables, totCausal)} %) fueron por daños evitables.`
            : 'Todas las bajas fueron por desgaste normal.');
        }
      }

      // Conclusiones de marca y ciclo
      taLectura('canvasKpi18_marca', null, '');
      taLectura('canvasKpi18_ciclo', null, '');
      if (d.por_marca) {
        const iM = taIndiceMayor(d.por_marca.valores);
        if (iM >= 0 && taSuma(d.por_marca.valores) > 0) taLectura('canvasKpi18_marca', 'in', `${d.por_marca.labels[iM]} tiene más bajas: ${formatCO_Miles(d.por_marca.valores[iM])} de ${formatCO_Miles(taSuma(d.por_marca.valores))}.`);
      }
      if (d.por_ciclo) {
        const iCi = taIndiceMayor(d.por_ciclo.valores);
        if (iCi >= 0 && taSuma(d.por_ciclo.valores) > 0) taLectura('canvasKpi18_ciclo', 'in', `${formatCO_Miles(d.por_ciclo.valores[iCi])} de ${formatCO_Miles(taSuma(d.por_ciclo.valores))} bajas fueron en vida ${d.por_ciclo.labels[iCi]}.`);
      }
    }

    // KPI 19: Profundidad de Retiro (Líneas) y Dispersión por mm (Burbujas)
    function renderChartKpi19(d) {
      destruirChartSuite('kpi19_lineas');
      destruirChartSuite('kpi19_burbujas');
      if (!d) return;

      // 1. Gráfico de 3 Líneas (Máx, Prom, Mín)
      const ctxLineas = document.getElementById('canvasKpi19_lineas');
      if (ctxLineas && d.grafico_lineas) {
        const gl = d.grafico_lineas;
        instanciasChartsSuite['kpi19_lineas'] = new Chart(ctxLineas, {
          type: 'line',
          data: {
            labels: gl.labels || [],
            datasets: [
              {
                label: 'Prof. Máxima (mm)',
                data: gl.maximo || [],
                borderColor: taMezclar(TA_G.azul, '#ffffff', 0.6),
                backgroundColor: taRgba(TA_G.azul, 0.10),
                borderWidth: 1,
                pointRadius: 0,
                tension: 0.25,
                fill: '+2',
                datalabels: { display: false }
              },
              {
                label: 'Prof. Promedio (mm)',
                data: gl.promedio || [],
                borderColor: TA_G.azul,
                backgroundColor: TA_G.azul,
                borderWidth: 2.5,
                pointRadius: 4,
                tension: 0.25,
                datalabels: pillDatalabelConfig('rgba(59, 130, 246, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} mm`)
              },
              {
                label: 'Prof. Mínima (mm)',
                data: gl.minimo || [],
                borderColor: taMezclar(TA_G.azul, '#ffffff', 0.6),
                backgroundColor: taMezclar(TA_G.azul, '#ffffff', 0.6),
                borderWidth: 1,
                pointRadius: 0,
                tension: 0.25,
                datalabels: { display: false }
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 10 } } },
              tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${formatCO_Decimal(c.raw, 1)} mm` } }
            },
            scales: {
              y: { beginAtZero: true, title: { display: true, text: 'Milímetros' }, ticks: { callback: (v) => `${formatCO_Decimal(v, 1)} mm` } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // 2. Gráfico de Burbujas (Dispersión mm vs Dinero Perdido)
      const ctxBurbujas = document.getElementById('canvasKpi19_burbujas');
      if (ctxBurbujas && d.burbujas_dispersion) {
        instanciasChartsSuite['kpi19_burbujas'] = new Chart(ctxBurbujas, {
          type: 'bubble',
          data: {
            datasets: [{
              label: 'Dispersión Retiro FVU',
              data: d.burbujas_dispersion || [],
              backgroundColor: taRgba(TA_G.al, 0.5),
              borderColor: TA_G.al,
              borderWidth: 1.5,
              datalabels: {
                display: true,
                formatter: (val) => val.cantidad > 0 ? `${val.x}mm (${val.cantidad})` : '',
                font: { weight: 'bold', size: 9 },
                color: '#1e293b',
                align: 'top'
              }
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 24, right: 16, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: (c) => {
                    const raw = c.raw;
                    return `Profundidad: ${raw.x} mm | Llantas: ${raw.cantidad} | Scrap: ${formatCO_Moneda(raw.y)}`;
                  }
                }
              }
            },
            scales: {
              x: {
                title: { display: true, text: 'Milímetros al Salir a FVU (mm)', font: { weight: 'bold', size: 10 } },
                min: 0,
                max: 20,
                ticks: { stepSize: 2 }
              },
              y: {
                title: { display: true, text: 'Dinero Scrap Perdido ($ COP)', font: { weight: 'bold', size: 10 } },
                beginAtZero: true,
                ticks: { callback: (v) => formatCO_Moneda(v) }
              }
            }
          }
        });
      }

      if (d.grafico_lineas) {
        const u19 = taUltimos(d.grafico_lineas.promedio);
        if (u19.valor !== null) {
          taLectura('canvasKpi19_lineas', 'al', `Las llantas se retiran con ${formatCO_Decimal(u19.valor, 1)} mm en promedio (${(d.grafico_lineas.labels || [])[u19.i] || 'último mes'}): caucho pagado que no se usó.`);
        }
      }
      const burb = d.burbujas_dispersion || [];
      if (burb.length) {
        const llantas = taSuma(burb.map(b => b.cantidad));
        const plata = taSuma(burb.map(b => b.y));
        taLectura('canvasKpi19_burbujas', 'al', `${formatCO_Miles(llantas)} llantas retiradas con caucho útil: ${formatCO_Moneda(plata)} en desecho.`);
      }
    }

    // ==========================================
    // RENDERERS SUB-PESTAÑA 5 (KPI 20) [SOLO FULL]
    // ==========================================

    // KPI 20: Matriz de Evaluación de Necesidades vs Las 7 Bodegas (MRP)
    function renderKpi20(d) {
      destruirChartSuite('kpi20_mrp');
      const ctx = document.getElementById('canvasKpi20_mrp');
      const tbody = document.getElementById('tbodyKpi20_mrp');
      if (!d) return;

      // 1. Gráfico Superior de Barras Comparativas por Dimensión
      if (ctx && d.grafico_comparativo) {
        const gc = d.grafico_comparativo;
        instanciasChartsSuite['kpi20_mrp'] = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: gc.labels || [],
            datasets: [
              {
                label: 'Necesidad Bruta Total',
                data: gc.necesidad_bruta || [],
                backgroundColor: TA_G.grisClaro,
                borderRadius: 6,
                datalabels: pillDatalabelConfig('rgba(239, 68, 68, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
              },
              {
                label: 'Stock Disponible (B1+B2+B3x0.9+B4)',
                data: gc.stock_disponible || [],
                backgroundColor: TA_G.azulClaro,
                borderRadius: 6,
                datalabels: pillDatalabelConfig('rgba(16, 185, 129, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
              },
              {
                label: 'Compra Neta Sugerida',
                data: gc.compra_neta || [],
                backgroundColor: TA_G.azul,
                borderRadius: 6,
                datalabels: pillDatalabelConfig('rgba(99, 102, 241, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold', size: 11 } } },
              tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.94)',
                cornerRadius: 10,
                padding: 12
              }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', title: { display: true, text: 'Cantidad de Llantas' } },
              x: { ticks: { font: { weight: 'bold', size: 11 } } }
            }
          }
        });
        const compra = taSuma(gc.compra_neta);
        const retornoKpi20 = (d.matriz_mrp || []).reduce((a, m) => a + (Number(m.retorno_reencauche_proyectado) || 0), 0);
        const detalle = (gc.labels || []).map((l, i) => [l, Number(gc.compra_neta?.[i]) || 0]).filter(x => x[1] > 0)
          .sort((a, b) => b[1] - a[1]).slice(0, 3).map(([l, n]) => `${formatCO_Miles(n)} de ${l}`);
        taLectura('canvasKpi20_mrp', compra > 0 ? 'al' : 'ok', compra > 0
          ? `Comprar ${formatCO_Miles(compra)} llantas: ${detalle.join(', ')}.${retornoKpi20 > 0 ? ` El reencauche de las llantas que se retiran cubre otras ${formatCO_Miles(retornoKpi20)}.` : ''}`
          : (retornoKpi20 > 0 ? `No hay compra sugerida: la bodega y el reencauche de las llantas que se retiran (${formatCO_Miles(retornoKpi20)}) cubren la necesidad.` : 'La bodega cubre la necesidad: no hay compra sugerida.'));
      }

      // 2. Gran Tabla Maestra MRP de 12 Columnas
      if (tbody) {
        if (!d.matriz_mrp || d.matriz_mrp.length === 0) {
          tbody.innerHTML = '<tr><td colspan="14" class="p-6 text-center text-slate-400">No hay datos de inventario o necesidades para los filtros seleccionados.</td></tr>';
        } else {
          tbody.innerHTML = d.matriz_mrp.map(m => {
            const tieneCompra = (m.compra_neta_sugerida || 0) > 0;
            return `
              <tr class="hover:bg-slate-50 transition-colors">
                <!-- Demanda -->
                <td class="p-2.5 font-black text-slate-900 font-mono">${escapeHtml(m.dimension || '-')}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.demanda_flota)}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.reposicion_bajas_fvu)}</td>
                <td class="p-2.5 text-center text-slate-500 font-mono">+${formatCO_Miles(m.margen_seguridad)}</td>
                <td class="p-2.5 text-center font-black bg-rose-50 text-rose-700 font-mono">${formatCO_Miles(m.necesidad_bruta)}</td>
                <!-- Bodegas -->
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b1)}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b2)}</td>
                <td class="p-2.5 text-center text-slate-600 font-mono">${formatCO_Miles(m.stock_b3_util)} <span class="text-[9px] text-slate-400">(${escapeHtml(m.stock_b3)})</span></td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b4)}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b5)}</td>
                <td class="p-2.5 text-center font-black bg-emerald-50 text-emerald-700 font-mono">${formatCO_Miles(m.stock_disponible)}</td>
                <td class="p-2.5 text-center font-bold text-emerald-700 font-mono" title="Desecho estimado: ${escapeHtml(m.desecho_proyectado || 0)}">${formatCO_Miles(m.retorno_reencauche_proyectado || 0)}</td>
                <!-- Compra -->
                <td class="p-2.5 text-center font-black ${tieneCompra ? 'bg-amber-100 text-amber-900 border border-amber-300 rounded-lg' : 'text-slate-400'} font-mono">${formatCO_Miles(m.compra_neta_sugerida)}</td>
                <td class="p-2.5 text-right font-black text-indigo-700 font-mono" title="${m.precio_ref_nueva ? `Precio de referencia: nueva ${formatCO_Moneda(m.precio_ref_nueva)}${m.precio_ref_reencauche ? ` · reencauche ${formatCO_Moneda(m.precio_ref_reencauche)}` : ''}` : 'Sin precios registrados para esta medida'}">${(m.presupuesto_estimado_cop === null || m.presupuesto_estimado_cop === undefined) ? (tieneCompra ? '<span class="text-slate-400 font-semibold">Sin precio</span>' : formatCO_Moneda(0)) : formatCO_Moneda(m.presupuesto_estimado_cop)}</td>
              </tr>
            `;
          }).join('');
        }
      }
    }

