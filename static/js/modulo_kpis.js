    // =========================================================================
    // CONTROLADOR DE LA SUITE ANALÍTICA DE 20 KPIS (5 PESTAÑAS HOMOLOGADAS)
    // =========================================================================
    if (typeof Chart !== 'undefined') {
      Chart.defaults.devicePixelRatio = Math.max(window.devicePixelRatio || 1, 2);
      Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
      Chart.defaults.color = '#475569';
      if (typeof ChartDataLabels !== 'undefined') {
        try {
          Chart.register(ChartDataLabels);
        } catch (e) {
          console.warn('ChartDataLabels ya registrado o error:', e);
        }
      }
    }

    let modoLicenciaSuite = 'FULL'; // 'LIGHT' o 'FULL'
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

    function pillDatalabelConfig(bgColor = 'rgba(15, 23, 42, 0.88)', textColor = '#ffffff', formatter = null) {
      return {
        display: (ctx) => {
          const ds = ctx.dataset;
          if (ds && ds.data && ds.data.length > 10) {
            return (ctx.dataIndex % 2 === 0 || ctx.dataIndex === ds.data.length - 1);
          }
          return true;
        },
        backgroundColor: bgColor,
        borderRadius: 5,
        color: textColor,
        font: { weight: '800', size: 10 },
        padding: { top: 2, bottom: 2, left: 6, right: 6 },
        formatter: formatter || ((val) => (val !== null && val !== undefined) ? formatCO_Miles(val) : '')
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

    function exportarGraficoPngHd(canvasId, filename = 'grafico_kpi') {
      const canvas = document.getElementById(canvasId);
      if (!canvas) {
        mostrarToast('Gráfico no disponible para exportar', true);
        return;
      }
      try {
        const link = document.createElement('a');
        link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.png`;
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

    function cambiarSubpestanaKpis(num) {
      subpestanaKpiActiva = num;
      for (let i = 1; i <= 5; i++) {
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

      // En LIGHT, ocultar KPI 01 padrón o banner
      const kpi01Banner = document.getElementById('kpi01-banner');
      if (kpi01Banner) kpi01Banner.classList.toggle('hidden', esLight);
    }

    function cambiarModoLicenciaSuite(nuevoModo, recargar = true) {
      modoLicenciaSuite = (nuevoModo === 'LIGHT') ? 'LIGHT' : 'FULL';
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

    async function cargarSuite20Kpis() {
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
        params.append('licencia', modoLicenciaSuite);

        const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
        const headers = tok ? { 'Authorization': `Bearer ${tok}` } : {};

        const res = await fetch(`/api/kpis/suite-20?${params.toString()}`, { headers });
        if (!res.ok) {
          console.warn('No se pudo cargar la suite de 20 KPIs, status:', res.status);
          return;
        }

        const data = await res.json();
        datosSuite20Actuales = data;
        unidadSuite = data.unidad === 'horas' ? 'h' : 'km';

        // La licencia efectiva la decide el servidor según la configuración del cliente
        if (data.licencia && data.licencia !== modoLicenciaSuite) {
          cambiarModoLicenciaSuite(data.licencia, false);
        }

        renderizarTodaLaSuite20(data);

      } catch (err) {
        console.error('Error al cargar la Suite de 20 KPIs:', err);
      }
    }

    function renderizarTodaLaSuite20(data) {
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
            if (data.kpi_18) renderChartKpi18(data.kpi_18);
            if (data.kpi_19) renderChartKpi19(data.kpi_19);
          }
          break;
        case 5:
          if (modoLicenciaSuite === 'FULL') {
            if (data.kpi_20) renderKpi20(data.kpi_20);
          }
          break;
      }
    }

    // ==========================================
    // RENDERERS SUB-PESTAÑA 1 (KPI 01 AL 04)
    // ==========================================

    // KPI 01: Cumplimiento de Inspección vs Parque
    function renderizarKpi01(d) {
      if (!d) return;
      const pct = Math.min(100, Math.max(0, d.porcentaje_cumplimiento || 0));
      const elPct = document.getElementById('kpi01_cumplimiento_pct');
      const elAudPad = document.getElementById('kpi01_auditados_padron');
      const elBar = document.getElementById('kpi01_barra_progreso');
      const elBtnTxt = document.getElementById('btnKpi01Texto');

      if (elPct) elPct.textContent = `${formatCO_Decimal(pct, 1)}%`;
      if (elAudPad) elAudPad.textContent = `${formatCO_Miles(d.vehiculos_inspeccionados)} / ${formatCO_Miles(d.total_padron_activo)}`;
      if (elBar) elBar.style.width = `${pct}%`;
      const numPend = (d.placas_pendientes || []).length;
      if (elBtnTxt) elBtnTxt.textContent = `Placas Pendientes (${numPend})`;

      // Llenar tabla del modal
      const tbody = document.getElementById('tbodyModalPlacasPendientes');
      if (tbody) {
        if (!d.placas_pendientes || d.placas_pendientes.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" class="p-6 text-center text-slate-400">¡Excelente! El 100% de los vehículos del padrón han sido inspeccionados.</td></tr>';
        } else {
          tbody.innerHTML = (d.placas_pendientes || []).slice(0, 25).map(p => `
            <tr class="hover:bg-slate-50">
              <td class="p-2.5 font-black text-slate-900 font-mono">${p.placa || '-'}</td>
              <td class="p-2.5 text-slate-600">${p.cliente || '-'} ${p.subcliente ? `/ ${p.subcliente}` : ''}</td>
              <td class="p-2.5 text-slate-600">${p.tipologia || '-'}</td>
              <td class="p-2.5 text-center"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">${p.estado_padron || 'Activo'}</span></td>
            </tr>
          `).join('');
        }
      }
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

      const gradientBar = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
      gradientBar.addColorStop(0, '#3b82f6');
      gradientBar.addColorStop(1, '#1d4ed8');

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
              borderColor: '#10b981',
              backgroundColor: '#10b981',
              borderWidth: 2.8,
              tension: 0.35,
              pointBackgroundColor: '#10b981',
              pointBorderColor: '#ffffff',
              pointBorderWidth: 2,
              pointRadius: 4,
              yAxisID: 'y1',
              datalabels: pillDatalabelConfig('rgba(6, 95, 70, 0.9)', '#ffffff')
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
      const meta = ds.meta_porcentaje || 70.0;
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
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.12)',
                borderWidth: 2.8,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: '#10b981',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                datalabels: pillDatalabelConfig('rgba(6, 95, 70, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)}%`)
              },
              {
                label: `Meta (${meta}%)`,
                data: lineaMeta,
                borderColor: '#ef4444',
                borderWidth: 2,
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
                max: 100,
                ticks: { callback: (v) => `${v}%` },
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
        instanciasChartsSuite['kpi03_ciclos'] = new Chart(ctxCiclos, {
          type: 'bar',
          data: {
            labels: ds.labels || [],
            datasets: [
              { label: 'Original', data: c.original || [], backgroundColor: '#3b82f6', borderRadius: 4 },
              { label: 'R1', data: c.r1 || [], backgroundColor: '#10b981', borderRadius: 4 },
              { label: 'R2', data: c.r2 || [], backgroundColor: '#f59e0b', borderRadius: 4 },
              { label: 'R3+', data: c.r3_mas || [], backgroundColor: '#8b5cf6', borderRadius: 4 }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 20, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } },
              datalabels: { display: false }
            },
            scales: {
              x: { stacked: true, ticks: { font: { weight: 'bold', size: 10 } } },
              y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(226, 232, 240, 0.6)' } }
            }
          }
        });
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
              label: 'Vehículos',
              data: dsTip.valores || [],
              backgroundColor: '#6366f1',
              borderRadius: 6
            }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { right: 20 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              datalabels: pillDatalabelConfig('rgba(79, 70, 229, 0.9)', '#ffffff')
            },
            scales: {
              x: { beginAtZero: true, ticks: { callback: (v) => formatCO_Miles(v) } }
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
              backgroundColor: '#0ea5e9',
              borderRadius: 6
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 24 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              datalabels: pillDatalabelConfig('rgba(14, 165, 233, 0.9)', '#ffffff')
            },
            scales: {
              y: { beginAtZero: true, ticks: { callback: (v) => formatCO_Miles(v) } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // Columna C: Dimensión y Diseño (Donut)
      const ctxDim = document.getElementById('canvasKpi04_dimension');
      if (ctxDim && dsDim) {
        instanciasChartsSuite['kpi04_dim'] = new Chart(ctxDim, {
          type: 'doughnut',
          data: {
            labels: dsDim.labels || [],
            datasets: [{
              data: dsDim.valores || [],
              backgroundColor: ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b']
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '62%',
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10, weight: 'bold' } } },
              datalabels: {
                display: 'auto',
                color: '#fff',
                font: { weight: 'bold', size: 10 },
                formatter: (val, ctx) => {
                  const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? ((val / total) * 100).toFixed(0) : 0;
                  return `${pct}%`;
                }
              }
            }
          }
        });
      }
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
            <td class="p-2.5 font-bold text-slate-900">${a.placa || ''}</td>
            <td class="p-2.5 text-center font-mono font-bold text-indigo-600">Pos ${a.posicion || ''}</td>
            <td class="p-2.5 font-mono text-slate-400 line-through">${a.serial_anterior || ''}</td>
            <td class="p-2.5 font-mono font-bold text-rose-600">${a.serial_actual || ''}</td>
            <td class="p-2.5 text-right font-mono font-bold">${a.prof_actual_min || 0} mm</td>
            <td class="p-2.5 text-slate-400 text-xs">${a.fecha_anterior || ''}</td>
            <td class="p-2.5 text-slate-700 font-semibold text-xs">${a.fecha_actual || ''}</td>
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
              <td class="p-2.5 font-bold text-slate-800">${r.dimension || '-'}</td>
              <td class="p-2.5 text-center font-mono">${r.direccional || 0}</td>
              <td class="p-2.5 text-center font-mono">${r.traccion || 0}</td>
              <td class="p-2.5 text-center font-mono">${r.arrastre || 0}</td>
              <td class="p-2.5 text-right font-black font-mono text-rose-700 bg-rose-50/50">${r.total || 0}</td>
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
              backgroundColor: '#ef4444',
              borderRadius: 6
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
                <td class="p-2 text-left font-bold text-slate-900 sticky left-0 bg-white border-r border-slate-200">${r.placa || '-'}</td>
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
              { label: '% Alineación OK', data: h.pct_ok || [], backgroundColor: '#0ea5e9', borderRadius: 4 },
              { label: '% Desalineadas', data: h.pct_alerta || [], backgroundColor: '#dc2626', borderRadius: 4 }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } },
              datalabels: { display: false }
            },
            scales: {
              x: { stacked: true },
              y: { stacked: true, min: 0, max: 100, ticks: { callback: (v) => `${v}%` } }
            }
          }
        });
      }

      // Tabla Detallada por Placa
      const tbody = document.getElementById('tbodyKpi06_perdidaPlaca');
      if (tbody) {
        if (!d.tabla_perdidas || d.tabla_perdidas.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-400">Sin vehículos desalineados</td></tr>';
        } else {
          tbody.innerHTML = d.tabla_perdidas.map(r => `
            <tr class="hover:bg-slate-50">
              <td class="p-2.5 font-bold font-mono text-slate-900">${r.placa || '-'}</td>
              <td class="p-2.5 text-center font-mono text-slate-700">${formatCO_Decimal(r.pos1_mm, 1)}</td>
              <td class="p-2.5 text-center font-mono text-slate-700">${formatCO_Decimal(r.pos2_mm, 1)}</td>
              <td class="p-2.5 text-center font-mono font-black text-rose-600">${formatCO_Decimal(r.total_mm, 1)} mm</td>
              <td class="p-2.5 text-right font-mono font-bold text-slate-900">${modoLicenciaSuite === 'FULL' ? formatCO_Moneda(r.perdida_pesos) : 'Modo LIGHT'}</td>
              <td class="p-2.5 text-center"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800">${r.accion || 'Alinear Dirección'}</span></td>
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
              <td class="p-2.5 font-bold font-mono text-slate-900">${r.placa || '-'}</td>
              <td class="p-2.5 text-center font-medium text-indigo-700 font-mono">${r.esquema || 'P3 ↔ P9 / P4 ↔ P10'}</td>
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
              backgroundColor: '#f43f5e',
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
      }

      // Tarjetas de Cruce con Bodega 2
      const cont = document.getElementById('contenedorKpi08_crucesB2');
      if (cont) {
        if (!d.cruces_bodega2 || d.cruces_bodega2.length === 0) {
          cont.innerHTML = '<div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-center text-xs">Sin pachas con desbalance &gt; 3 mm</div>';
        } else {
          cont.innerHTML = d.cruces_bodega2.map(c => `
            <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
              <div>
                <span class="font-mono font-black text-slate-900">${c.placa || '-'}</span>
                <span class="text-slate-500 ml-1.5">${c.pacha || 'P3-P4'} (&Delta; ${formatCO_Decimal(c.diferencia_mm, 1)} mm)</span>
              </div>
              <div class="text-right">
                <span class="text-[10px] text-indigo-600 font-bold block">Bodega 2: ${c.llanta_b2_sugerida || 'Stock disponible'}</span>
                <span class="text-[10px] text-slate-500 font-mono">${c.milimetraje_b2 || 0} mm</span>
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
        instanciasChartsSuite['kpi09_psi'] = new Chart(ctx, {
          type: 'doughnut',
          data: {
            // Rangos según la presión objetivo de cada eje y las tolerancias asignadas al cliente
            labels: ['Baja severa (< -15 %)', 'Baja (fuera de tolerancia)', 'Correcta (en tolerancia)', 'Alta (fuera de tolerancia)'],
            datasets: [{
              data: [dist.baja_severa || 0, dist.baja_moderada || 0, dist.correcta || 0, dist.sobrepresion || 0],
              backgroundColor: ['#dc2626', '#f59e0b', '#10b981', '#6366f1']
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10, weight: 'bold' } } },
              datalabels: {
                color: '#fff',
                font: { weight: 'bold', size: 10 },
                formatter: (val, ctx) => {
                  const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                  return total > 0 ? `${((val / total) * 100).toFixed(0)}%` : '';
                }
              }
            }
          }
        });
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

      instanciasChartsSuite['kpi10_pareto'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: d.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Frecuencia Novedades',
              data: d.frecuencias || [],
              backgroundColor: '#a855f7',
              borderRadius: 4,
              yAxisID: 'y',
              datalabels: pillDatalabelConfig('rgba(168, 85, 247, 0.9)', '#ffffff')
            },
            {
              type: 'line',
              label: '% Acumulado (Pareto)',
              data: d.acumulado_pct || [],
              borderColor: '#f59e0b',
              backgroundColor: '#f59e0b',
              borderWidth: 2.5,
              pointRadius: 4,
              yAxisID: 'y1',
              datalabels: { display: false }
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 24, right: 12, bottom: 8, left: 8 } },
          animation: animacionCascadaStandard,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 10, font: { weight: 'bold', size: 10 } } }
          },
          scales: {
            y: { beginAtZero: true, position: 'left', title: { display: true, text: 'Cantidad' } },
            y1: { beginAtZero: true, max: 100, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => `${v}%` } },
            x: { ticks: { font: { weight: 'bold', size: 10 } } }
          }
        }
      });
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
            backgroundColor: '#f43f5e',
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
            borderColor: '#f97316',
            backgroundColor: '#f97316',
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

    // KPI 13: Km Rodados Reales vs. Proyección Final al Límite de Retiro
    function renderChartKpi13(ds) {
      destruirChartSuite('kpi13_comparativo');
      const ctx = document.getElementById('canvasKpi13_comparativo');
      if (!ctx || !ds) return;

      const gradientReales = ctx.getContext('2d').createLinearGradient(0, 0, 0, 260);
      gradientReales.addColorStop(0, '#2563eb');
      gradientReales.addColorStop(1, '#1d4ed8');

      const gradientProy = ctx.getContext('2d').createLinearGradient(0, 0, 0, 260);
      gradientProy.addColorStop(0, 'rgba(96, 165, 250, 0.7)');
      gradientProy.addColorStop(1, 'rgba(59, 130, 246, 0.4)');

      instanciasChartsSuite['kpi13_comparativo'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              label: unidadSuite === 'h' ? 'Horas reales' : 'Km Reales Rodados',
              data: ds.km_reales || [],
              backgroundColor: gradientReales,
              borderColor: '#1e40af',
              borderWidth: 1.5,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(30, 64, 175, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} ${uMed()}`)
            },
            {
              label: 'Proyección Final al Retiro',
              data: ds.proyeccion_final || [],
              backgroundColor: gradientProy,
              borderColor: '#2563eb',
              borderWidth: 1.5,
              borderDash: [4, 4],
              borderRadius: 6,
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
            x: { ticks: { font: { weight: 'bold', size: 11 } } }
          }
        }
      });
    }

    // KPI 14: Tríada Multidimensional Sincronizada (Proyección, Km/mm, CPK)
    function renderChartKpi14(ds) {
      destruirChartSuite('kpi14_proy');
      destruirChartSuite('kpi14_kmmm');
      destruirChartSuite('kpi14_cpk');
      if (!ds) return;

      const sel = document.getElementById('selAgrupacionKpi14');
      if (sel && ds.agrupacion_actual && sel.value !== ds.agrupacion_actual) {
        sel.value = ds.agrupacion_actual;
      }

      const labels = ds.labels || [];

      // 1. Proyección Km Final (Índigo)
      const ctxProy = document.getElementById('canvasKpi14_proy');
      if (ctxProy) {
        const gradProy = ctxProy.getContext('2d').createLinearGradient(0, 0, 0, 240);
        gradProy.addColorStop(0, '#6366f1');
        gradProy.addColorStop(1, '#4338ca');

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
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Proyección: ${formatCO_Miles(c.raw)} ${uMed()}` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => formatCO_Miles(v), font: { size: 9 } } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // 2. Rendimiento Km/mm (Esmeralda)
      const ctxKmmm = document.getElementById('canvasKpi14_kmmm');
      if (ctxKmmm) {
        const gradKmmm = ctxKmmm.getContext('2d').createLinearGradient(0, 0, 0, 240);
        gradKmmm.addColorStop(0, '#10b981');
        gradKmmm.addColorStop(1, '#047857');

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
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Rendimiento: ${formatCO_Decimal(c.raw, 1)} ${uMed()}/mm` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => formatCO_Decimal(v, 1), font: { size: 9 } } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }

      // 3. Costo por Kilómetro CPK (Púrpura)
      const ctxCpk = document.getElementById('canvasKpi14_cpk');
      if (ctxCpk) {
        const gradCpk = ctxCpk.getContext('2d').createLinearGradient(0, 0, 0, 240);
        gradCpk.addColorStop(0, '#a855f7');
        gradCpk.addColorStop(1, '#7e22ce');

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
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `CPK: $ ${formatCO_Decimal(c.raw, 2)} COP/${uMed()}` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => `$${formatCO_Decimal(v, 1)}`, font: { size: 9 } } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }
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
      if (tv) tv.innerHTML = (k.por_vida || []).map(v => `<tr><td class="p-2 font-bold">${v.vida}</td><td class="p-2 text-right">${v.llantas}</td>
        <td class="p-2 text-right font-mono">${fmt(v.cpk_operativo)}</td><td class="p-2 text-right font-mono">${fmt(v.cpk_proyectado)}</td></tr>`).join('')
        || '<tr><td colspan="4" class="p-2 text-slate-400 italic">Sin datos</td></tr>';
      const ta = document.getElementById('tbodyCpkAdmin');
      if (ta) ta.innerHTML = (k.administrativo || []).slice().reverse().map(m => `<tr><td class="p-2 font-bold">${m.mes}</td>
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

      const gradProm = ctx.getContext('2d').createLinearGradient(0, 0, 0, 260);
      gradProm.addColorStop(0, 'rgba(37, 99, 235, 0.85)');
      gradProm.addColorStop(1, 'rgba(29, 78, 216, 0.7)');

      instanciasChartsSuite['kpi15_potencial'] = new Chart(ctx, {
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Proyección Promedio',
              data: ds.promedio || [],
              backgroundColor: gradProm,
              borderColor: '#1d4ed8',
              borderWidth: 1.5,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(30, 64, 175, 0.85)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: 'Máximo Alcanzado',
              data: ds.maximo || [],
              borderColor: '#0284c7',
              backgroundColor: '#0284c7',
              borderWidth: 2.5,
              pointRadius: 4,
              tension: 0.25,
              datalabels: pillDatalabelConfig('rgba(2, 132, 199, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: 'Mínimo / Peor Desempeño',
              data: ds.minimo || [],
              borderColor: '#f59e0b',
              backgroundColor: '#f59e0b',
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
          layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } },
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
            x: { ticks: { font: { weight: 'bold', size: 11 } } }
          }
        }
      });
    }

    // KPI 16: Curva de Proyección por Rango de Desgaste (Madurez del Caucho)
    function renderChartKpi16(ds) {
      destruirChartSuite('kpi16_rangos');
      const ctx = document.getElementById('canvasKpi16_rangos');
      if (!ctx || !ds) return;

      instanciasChartsSuite['kpi16_rangos'] = new Chart(ctx, {
        data: {
          labels: ds.labels || [],
          datasets: [
            {
              type: 'bar',
              label: 'Llantas en Banda',
              data: ds.conteo_llantas || [],
              backgroundColor: 'rgba(129, 140, 248, 0.65)',
              borderColor: '#6366f1',
              borderWidth: 1.5,
              borderRadius: 6,
              yAxisID: 'y',
              datalabels: pillDatalabelConfig('rgba(79, 70, 229, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
            },
            {
              type: 'line',
              label: `Proyección Promedio (${uMed()})`,
              data: ds.proyeccion_promedio || [],
              borderColor: '#4f46e5',
              backgroundColor: 'rgba(79, 70, 229, 0.12)',
              fill: true,
              borderWidth: 2.8,
              pointRadius: 4,
              tension: 0.35,
              yAxisID: 'y1',
              datalabels: pillDatalabelConfig('rgba(67, 56, 202, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} ${uMed()}`)
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

      destruirChartSuite('kpi17_lineas');
      const ctx = document.getElementById('canvasKpi17_lineas');
      if (!ctx || !d.grafico_12m) return;

      const g = d.grafico_12m;
      const gradBar = ctx.getContext('2d').createLinearGradient(0, 0, 0, 240);
      gradBar.addColorStop(0, '#f43f5e');
      gradBar.addColorStop(1, '#be123c');

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
              borderColor: '#6366f1',
              backgroundColor: 'rgba(99, 102, 241, 0.1)',
              fill: true,
              borderWidth: 2.8,
              pointRadius: 4,
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
    }

    // KPI 18: Participación FVU por Marca, Ciclo y Causal de Daño (+ Alerta Garantía)
    function renderChartKpi18(d) {
      destruirChartSuite('kpi18_marca');
      destruirChartSuite('kpi18_ciclo');
      destruirChartSuite('kpi18_causal');
      if (!d) return;

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
        const gradM = ctxMarca.getContext('2d').createLinearGradient(0, 0, 0, 220);
        gradM.addColorStop(0, '#f43f5e');
        gradM.addColorStop(1, '#e11d48');

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
        const coloresCiclos = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'];
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

      // C. Causales de Daño (Doughnut interactiva)
      const ctxCausal = document.getElementById('canvasKpi18_causal');
      if (ctxCausal && d.por_causal) {
        const paletaCausales = ['#ef4444', '#f97316', '#f59e0b', '#8b5cf6', '#06b6d4', '#64748b', '#10b981', '#ec4899'];
        instanciasChartsSuite['kpi18_causal'] = new Chart(ctxCausal, {
          type: 'doughnut',
          data: {
            labels: d.por_causal.labels || [],
            datasets: [{
              data: d.por_causal.valores || [],
              backgroundColor: paletaCausales.slice(0, (d.por_causal.labels || []).length),
              borderWidth: 2,
              borderColor: '#ffffff'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: animacionCascadaStandard,
            plugins: {
              legend: { position: 'bottom', labels: { boxWidth: 10, font: { weight: 'bold', size: 9 } } },
              tooltip: {
                callbacks: {
                  label: (c) => {
                    const idx = c.dataIndex;
                    const pct = d.por_causal.porcentajes?.[idx] || 0;
                    return ` ${c.label}: ${formatCO_Miles(c.raw)} llantas (${pct}%)`;
                  }
                }
              },
              datalabels: {
                color: '#ffffff',
                font: { weight: '800', size: 9 },
                formatter: (val, ctx) => {
                  const idx = ctx.dataIndex;
                  const pct = d.por_causal.porcentajes?.[idx] || 0;
                  return pct >= 8 ? `${pct}%` : '';
                }
              }
            }
          }
        });
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
                borderColor: '#ef4444',
                backgroundColor: '#ef4444',
                borderWidth: 2.2,
                pointRadius: 4,
                tension: 0.25,
                datalabels: pillDatalabelConfig('rgba(239, 68, 68, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} mm`)
              },
              {
                label: 'Prof. Promedio (mm)',
                data: gl.promedio || [],
                borderColor: '#3b82f6',
                backgroundColor: '#3b82f6',
                borderWidth: 2.5,
                pointRadius: 4,
                tension: 0.25,
                datalabels: pillDatalabelConfig('rgba(59, 130, 246, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} mm`)
              },
              {
                label: 'Prof. Mínima (mm)',
                data: gl.minimo || [],
                borderColor: '#64748b',
                backgroundColor: '#64748b',
                borderWidth: 2,
                pointRadius: 4,
                tension: 0.25,
                datalabels: pillDatalabelConfig('rgba(100, 116, 139, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} mm`)
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
              backgroundColor: 'rgba(239, 68, 68, 0.6)',
              borderColor: '#dc2626',
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
                backgroundColor: '#ef4444',
                borderRadius: 6,
                datalabels: pillDatalabelConfig('rgba(239, 68, 68, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
              },
              {
                label: 'Stock Disponible (B1+B2+B3x0.9+B4)',
                data: gc.stock_disponible || [],
                backgroundColor: '#10b981',
                borderRadius: 6,
                datalabels: pillDatalabelConfig('rgba(16, 185, 129, 0.9)', '#ffffff', (v) => formatCO_Miles(v))
              },
              {
                label: 'Compra Neta Sugerida',
                data: gc.compra_neta || [],
                backgroundColor: '#6366f1',
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
      }

      // 2. Gran Tabla Maestra MRP de 12 Columnas
      if (tbody) {
        if (!d.matriz_mrp || d.matriz_mrp.length === 0) {
          tbody.innerHTML = '<tr><td colspan="12" class="p-6 text-center text-slate-400">No hay datos de inventario o necesidades para los filtros seleccionados.</td></tr>';
        } else {
          tbody.innerHTML = d.matriz_mrp.map(m => {
            const tieneCompra = (m.compra_neta_sugerida || 0) > 0;
            return `
              <tr class="hover:bg-slate-50 transition-colors">
                <!-- Demanda -->
                <td class="p-2.5 font-black text-slate-900 font-mono">${m.dimension || '-'}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.demanda_flota)}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.reposicion_bajas_fvu)}</td>
                <td class="p-2.5 text-center text-slate-500 font-mono">+${formatCO_Miles(m.margen_seguridad)}</td>
                <td class="p-2.5 text-center font-black bg-rose-50 text-rose-700 font-mono">${formatCO_Miles(m.necesidad_bruta)}</td>
                <!-- Bodegas -->
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b1)}</td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b2)}</td>
                <td class="p-2.5 text-center text-slate-600 font-mono">${formatCO_Miles(m.stock_b3_util)} <span class="text-[9px] text-slate-400">(${m.stock_b3})</span></td>
                <td class="p-2.5 text-center font-bold text-slate-700 font-mono">${formatCO_Miles(m.stock_b4)}</td>
                <td class="p-2.5 text-center font-black bg-emerald-50 text-emerald-700 font-mono">${formatCO_Miles(m.stock_disponible)}</td>
                <!-- Compra -->
                <td class="p-2.5 text-center font-black ${tieneCompra ? 'bg-amber-100 text-amber-900 border border-amber-300 rounded-lg' : 'text-slate-400'} font-mono">${formatCO_Miles(m.compra_neta_sugerida)}</td>
                <td class="p-2.5 text-right font-black text-indigo-700 font-mono">${formatCO_Moneda(m.presupuesto_estimado_cop)}</td>
              </tr>
            `;
          }).join('');
        }
      }
    }

