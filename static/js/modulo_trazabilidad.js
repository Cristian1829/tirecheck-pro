    // ==========================================
    // VISTA 4: TRAZABILIDAD & KPIS DE LLANTAS
    // ==========================================
    let kpisFiltrosPoblados = false;
    let paginaActualKpis = 1;
    const ITEMS_POR_PAGINA_KPIS = 25;

    async function cargarKpis() {
      const tbody = document.getElementById('tbodyKpis');
      if (tbody && (!cacheKpis || cacheKpis.length === 0)) {
        tbody.innerHTML = `
          <tr>
            <td colspan="20" class="p-8 text-center text-slate-500 font-bold text-xs">
              <i class="fa-solid fa-circle-notch fa-spin text-indigo-600 mr-2 text-sm"></i>
              Cargando métricas de trazabilidad y KPIs...
            </td>
          </tr>
        `;
      }

      const qNum = (document.getElementById('filtroKpiNumero')?.value || '').trim();
      const cli = document.getElementById('filtroKpiCliente')?.value || '';
      const sub = document.getElementById('filtroKpiSubcliente')?.value || '';
      const op = document.getElementById('filtroKpiOperacion')?.value || '';
      const marca = document.getElementById('filtroKpiMarca')?.value || '';
      // Tipología y dimensión también filtran la tabla (antes solo las gráficas)
      const tip = document.getElementById('filtroKpiTipologia')?.value || '';
      const dim = document.getElementById('filtroKpiDimension')?.value || '';

      const params = new URLSearchParams();
      if (qNum) params.append('numero_interno', qNum);
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);
      if (tip && tip !== 'TODOS') params.append('tipologia', tip);
      if (marca && marca !== 'TODOS') params.append('marca', marca);
      if (dim && dim !== 'TODOS') params.append('dimension', dim);

      const token = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      try {
        const res = await fetch(`/api/kpis-llantas?${params.toString()}`, { headers });
        if (res.ok) {
          cacheKpis = await res.json();
          poblarSelectoresFiltroKpis(cacheKpis);
          renderizarTablaKpis();
        } else if (res.status === 401) {
          if (tbody) {
            tbody.innerHTML = `<tr><td colspan="20" class="p-8 text-center text-amber-600 font-bold"><i class="fa-solid fa-lock mr-2"></i>Sesión no válida o expirada. Por favor inicia sesión nuevamente.</td></tr>`;
          }
        } else {
          if (tbody) {
            tbody.innerHTML = `<tr><td colspan="20" class="p-8 text-center text-rose-500 font-bold"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Error al consultar métricas (${res.status}). <button onclick="cargarKpis()" class="ml-2 px-3 py-1 bg-slate-900 text-white text-xs rounded-lg shadow">Reintentar</button></td></tr>`;
          }
        }
      } catch (e) {
        console.error('Error en cargarKpis:', e);
        if (tbody) {
          tbody.innerHTML = `<tr><td colspan="20" class="p-8 text-center text-rose-500 font-bold"><i class="fa-solid fa-wifi mr-2"></i>Error al procesar métricas de KPIs. <button onclick="cargarKpis()" class="ml-2 px-3 py-1 bg-slate-900 text-white text-xs rounded-lg shadow">Reintentar</button></td></tr>`;
        }
        mostrarToast('Error al cargar métricas de KPIs: ' + (e.message || ''), true);
      }
    }

    function poblarSelectoresFiltroKpis(data) {
      const selCli = document.getElementById('filtroKpiCliente');
      const selSub = document.getElementById('filtroKpiSubcliente');
      const selOp = document.getElementById('filtroKpiOperacion');
      const selMar = document.getElementById('filtroKpiMarca');

      const valCliActual = selCli ? (selCli.value || 'TODOS') : 'TODOS';
      const valSubActual = selSub ? (selSub.value || 'TODOS') : 'TODOS';
      const valOpActual = selOp ? (selOp.value || 'TODOS') : 'TODOS';
      const valMarActual = selMar ? (selMar.value || 'TODOS') : 'TODOS';

      // Detectar clientes asignados del usuario si es inspector
      let clisAsignados = [];
      if (usuarioActual && !esUsuarioAdmin()) {
        if (Array.isArray(usuarioActual.clientes_asignados) && usuarioActual.clientes_asignados.length > 0) {
          clisAsignados = usuarioActual.clientes_asignados.map(c => String(c).trim()).filter(Boolean);
        } else if (usuarioActual.cliente_asignado) {
          clisAsignados = usuarioActual.cliente_asignado.split(',').map(s => s.trim()).filter(Boolean);
        }
      }

      // Clientes disponibles
      let clientes = [];
      if (data && data.length > 0) {
        clientes = Array.from(new Set(data.map(d => d.cliente).filter(Boolean))).sort();
      }
      if (clisAsignados.length > 0) {
        clisAsignados.forEach(c => {
          if (!clientes.some(x => x.toLowerCase() === c.toLowerCase())) clientes.push(c);
        });
        clientes.sort();
      }

      if (selCli) {
        if (clisAsignados.length === 1) {
          const unico = clisAsignados[0];
          selCli.innerHTML = `<option value="${unico}" selected>${unico} (Fijo)</option>`;
          selCli.disabled = true;
          selCli.classList.add('bg-slate-100', 'cursor-not-allowed');
        } else {
          selCli.disabled = false;
          selCli.classList.remove('bg-slate-100', 'cursor-not-allowed');
          const lblTodos = clisAsignados.length > 1 ? 'Mis flotas' : 'Todos';
          selCli.innerHTML = `<option value="TODOS">${lblTodos}</option>` +
            clientes.map(c => `<option value="${c}">${c}</option>`).join('');
          if (valCliActual && clientes.includes(valCliActual)) {
            selCli.value = valCliActual;
          } else {
            selCli.value = 'TODOS';
          }
        }
      }

      // Subclientes / Sedes disponibles (filtrados por cliente si está seleccionado)
      const cliFiltro = selCli ? selCli.value : 'TODOS';
      const dataSedes = (cliFiltro && cliFiltro !== 'TODOS')
        ? (data || []).filter(d => String(d.cliente || '').toUpperCase() === cliFiltro.toUpperCase())
        : (data || []);
      const subclientes = Array.from(new Set(dataSedes.map(d => d.subcliente).filter(Boolean))).sort();
      if (selSub) {
        selSub.innerHTML = '<option value="TODOS">Todas</option>' +
          subclientes.map(s => `<option value="${s}">${s}</option>`).join('');
        if (valSubActual && subclientes.includes(valSubActual)) selSub.value = valSubActual;
        else selSub.value = 'TODOS';
      }

      // Operaciones
      const operaciones = Array.from(new Set((data || []).map(d => d.tipo_operacion).filter(Boolean))).sort();
      if (selOp) {
        selOp.innerHTML = '<option value="TODOS">Todas</option>' +
          operaciones.map(o => `<option value="${o}">${o}</option>`).join('');
        if (valOpActual && operaciones.includes(valOpActual)) selOp.value = valOpActual;
        else selOp.value = 'TODOS';
      }

      // Marcas
      const marcas = Array.from(new Set((data || []).map(d => d.marca).filter(Boolean))).sort();
      if (selMar) {
        selMar.innerHTML = '<option value="TODOS">Todas</option>' +
          marcas.map(m => `<option value="${m}">${m}</option>`).join('');
        if (valMarActual && marcas.includes(valMarActual)) selMar.value = valMarActual;
        else selMar.value = 'TODOS';
      }

      kpisFiltrosPoblados = true;
    }

    function renderizarTablaKpis() {
      const tbody = document.getElementById('tbodyKpis');
      const contenedorPaginacion = document.getElementById('contenedorPaginacionKpis');
      const data = cacheKpis;

      const elTotal = document.getElementById('cardKpiTotal');
      const elKm = document.getElementById('cardKpiKmProm');
      const elCpk = document.getElementById('cardKpiCpkProm');
      const elProy = document.getElementById('cardKpiProyProm');

      if (!data || data.length === 0) {
        if (elTotal) elTotal.textContent = '0';
        if (elKm) elKm.textContent = '0.0';
        if (elCpk) elCpk.textContent = '$0.0000';
        if (elProy) elProy.textContent = '0 km';
        if (tbody) tbody.innerHTML = `<tr><td colspan="20" class="p-8 text-center text-slate-400">No hay datos de rendimiento coincidentes con los filtros.</td></tr>`;
        if (contenedorPaginacion) contenedorPaginacion.classList.add('hidden');
        return;
      }

      // Cálculo de promedios para tarjetas sobre el TOTAL de datos
      const km_mms = data.map(d => d.km_por_mm).filter(v => v > 0);
      const cpks = data.map(d => d.cpk).filter(v => v > 0);
      const proys = data.map(d => d.proyeccion_total_km).filter(v => v > 0);

      // Flota: Σkm / Σmm y Σcosto / Σkm (antes promedio de cada llanta: una llanta con pocos km lo inflaba)
      const sum = (arr, f) => arr.reduce((a, d) => a + (Number(f(d)) || 0), 0);
      const conRend = data.filter(d => d.km_por_mm > 0), conCpk = data.filter(d => d.cpk > 0);
      const prom_km_mm = sum(conRend, d => d.desgaste_mm) > 0 ? sum(conRend, d => d.km_rodados) / sum(conRend, d => d.desgaste_mm) : 0;
      const prom_cpk = sum(conCpk, d => d.km_rodados) > 0 ? sum(conCpk, d => d.precio) / sum(conCpk, d => d.km_rodados) : 0;
      const prom_proy = proys.length ? (proys.reduce((a, b) => a + b, 0) / proys.length) : 0;

      if (elTotal) elTotal.textContent = data.length.toLocaleString();
      if (elKm) elKm.textContent = prom_km_mm.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
      if (elCpk) elCpk.textContent = `$ ${fmtDec(prom_cpk, 1)}`;
      if (elProy) elProy.textContent = `${Math.round(prom_proy).toLocaleString()} km`;

      // Paginación estricta de 25 registros por página
      const totalRegistros = data.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_KPIS) || 1;
      if (paginaActualKpis > totalPaginas) paginaActualKpis = totalPaginas;
      if (paginaActualKpis < 1) paginaActualKpis = 1;

      const inicio = (paginaActualKpis - 1) * ITEMS_POR_PAGINA_KPIS;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_KPIS, totalRegistros);
      const paginaItems = data.slice(inicio, fin);

      tbody.innerHTML = paginaItems.map(d => `
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="p-2.5 font-black text-slate-900">${d.numero_interno || '-'}</td>
          <td class="p-2.5 font-bold text-blue-700">${d.placa || '-'}</td>
          <td class="p-2.5 text-center font-bold">${d.posicion}</td>
          <td class="p-2.5">${d.marca} ${d.diseno}</td>
          <td class="p-2.5">${d.dimension || '-'}</td>
          <td class="p-2.5">${d.vida || '-'}</td>
          <td class="p-2.5">${d.banda_reen || '-'}</td>
          <td class="p-2.5 text-center font-mono">${d.prof_inicial} mm</td>
          <td class="p-2.5 text-center font-mono font-bold">${d.prof_actual_min} mm</td>
          <td class="p-2.5 text-center font-mono text-slate-500">${d.limite_retiro_mm || 3.0} mm</td>
          <td class="p-2.5 text-center">${d.requiere_cambio === 'Sí' || d.requiere_cambio === 'S' || d.requiere_cambio === 'SÍ' ? '<span class="bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded-full text-[10px]">Sí</span>' : '<span class="text-slate-400">NO</span>'}</td>
          <td class="p-2.5 text-center font-mono font-bold text-rose-600">${d.desgaste_mm} mm</td>
          <td class="p-2.5 text-center font-mono">${fmtDec((d.porcentaje_desgaste || 0), 1)}%</td>
          <td class="p-2.5 text-right font-mono">${(d.km_rodados || 0).toLocaleString()}</td>
          <td class="p-2.5 text-right font-mono font-bold text-blue-600">${(d.km_por_mm || 0).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})}</td>
          <td class="p-2.5 text-right font-mono">$${(d.precio || 0).toLocaleString()}</td>
          <td class="p-2.5 text-right font-mono font-bold text-emerald-600">$ ${fmtDec(d.cpk || 0, 1)}</td>
          <td class="p-2.5 text-right font-mono">${Math.round(d.proyeccion_total_km || 0).toLocaleString()}</td>
          <td class="p-2.5 text-right font-mono">$ ${fmtDec(d.cpk_proyectado || 0, 1)}</td>
          <td class="p-2.5 text-right font-mono font-black text-purple-700">${Math.round(d.km_restantes || 0).toLocaleString()} km</td>
        </tr>
      `).join('');

      actualizarBarraPaginacionKpis(totalRegistros, inicio, fin);
    }

    function cambiarPaginaKpis(nuevaPagina) {
      const totalRegistros = cacheKpis ? cacheKpis.length : 0;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_KPIS) || 1;
      if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
      paginaActualKpis = nuevaPagina;
      renderizarTablaKpis();
      const contTabla = document.querySelector('#vista-kpis .overflow-x-auto');
      if (contTabla) contTabla.scrollTop = 0;
    }

    function actualizarBarraPaginacionKpis(totalRegistros, inicio, fin) {
      const contenedor = document.getElementById('contenedorPaginacionKpis');
      const lblInicio = document.getElementById('pagInicioKpis');
      const lblFin = document.getElementById('pagFinKpis');
      const lblTotal = document.getElementById('pagTotalKpis');
      const controles = document.getElementById('controlesPaginacionKpis');

      if (!contenedor || !controles) return;
      if (totalRegistros === 0) {
        contenedor.classList.add('hidden');
        return;
      }

      contenedor.classList.remove('hidden');
      if (lblInicio) lblInicio.textContent = (inicio + 1).toLocaleString();
      if (lblFin) lblFin.textContent = fin.toLocaleString();
      if (lblTotal) lblTotal.textContent = totalRegistros.toLocaleString();

      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_KPIS) || 1;

      let html = '';

      // Botón Primero
      const deshabilitarPrimero = paginaActualKpis <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaKpis(1)" ${deshabilitarPrimero ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarPrimero ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Primera página">
          <i class="fa-solid fa-angles-left text-[11px]"></i>
        </button>
      `;

      // Botón Anterior
      const deshabilitarAnt = paginaActualKpis <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaKpis(${paginaActualKpis - 1})" ${deshabilitarAnt ? 'disabled' : ''}
          class="inline-flex items-center space-x-1 px-2.5 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all ${
            deshabilitarAnt ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Página anterior">
          <i class="fa-solid fa-chevron-left text-[11px]"></i>
          <span class="hidden sm:inline">Ant</span>
        </button>
      `;

      // Botones numéricos de página
      const paginas = [];
      if (totalPaginas <= 7) {
        for (let i = 1; i <= totalPaginas; i++) paginas.push(i);
      } else {
        paginas.push(1);
        let start = Math.max(2, paginaActualKpis - 1);
        let end = Math.min(totalPaginas - 1, paginaActualKpis + 1);

        if (paginaActualKpis <= 3) {
          end = 4;
        } else if (paginaActualKpis >= totalPaginas - 2) {
          start = totalPaginas - 3;
        }

        if (start > 2) paginas.push('...');
        for (let i = start; i <= end; i++) paginas.push(i);
        if (end < totalPaginas - 1) paginas.push('...');
        paginas.push(totalPaginas);
      }

      paginas.forEach(p => {
        if (p === '...') {
          html += `<span class="w-6 h-8 flex items-center justify-center text-slate-400 font-bold text-xs select-none">...</span>`;
        } else if (p === paginaActualKpis) {
          html += `
            <button type="button" class="w-8 h-8 rounded-xl bg-blue-600 text-white font-black text-xs shadow-sm flex items-center justify-center cursor-default">
              ${p}
            </button>
          `;
        } else {
          html += `
            <button type="button" onclick="cambiarPaginaKpis(${p})" class="w-8 h-8 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900 font-bold text-xs shadow-xs transition-all flex items-center justify-center cursor-pointer active:scale-95">
              ${p}
            </button>
          `;
        }
      });

      // Botón Siguiente
      const deshabilitarSig = paginaActualKpis >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaKpis(${paginaActualKpis + 1})" ${deshabilitarSig ? 'disabled' : ''}
          class="inline-flex items-center space-x-1 px-2.5 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all ${
            deshabilitarSig ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Página siguiente">
          <span class="hidden sm:inline">Sig</span>
          <i class="fa-solid fa-chevron-right text-[11px]"></i>
        </button>
      `;

      // Botón Último
      const deshabilitarUltimo = paginaActualKpis >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaKpis(${totalPaginas})" ${deshabilitarUltimo ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarUltimo ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Última página">
          <i class="fa-solid fa-angles-right text-[11px]"></i>
        </button>
      `;

      controles.innerHTML = html;
    }

    function alCambiarFiltroKpiCliente() {
      const selCli = document.getElementById('filtroKpiCliente');
      const selSub = document.getElementById('filtroKpiSubcliente');
      const cliFiltro = selCli ? selCli.value : 'TODOS';
      if (selSub && cacheKpis && cacheKpis.length > 0) {
        const dataSedes = (cliFiltro && cliFiltro !== 'TODOS')
          ? cacheKpis.filter(d => String(d.cliente || '').toUpperCase() === cliFiltro.toUpperCase())
          : cacheKpis;
        const subclientes = Array.from(new Set(dataSedes.map(d => d.subcliente).filter(Boolean))).sort();
        selSub.innerHTML = '<option value="TODOS">Todas</option>' +
          subclientes.map(s => `<option value="${s}">${s}</option>`).join('');
        selSub.value = 'TODOS';
      }
      cargarSuite20Kpis();
      cargarKpis();
    }

    function limpiarFiltrosKpis() {
      const elNum = document.getElementById('filtroKpiNumero');
      if (elNum) elNum.value = '';
      const selCli = document.getElementById('filtroKpiCliente');
      if (selCli && !selCli.disabled) {
        selCli.value = 'TODOS';
      }
      const selSub = document.getElementById('filtroKpiSubcliente');
      if (selSub) selSub.value = 'TODOS';
      const selOp = document.getElementById('filtroKpiOperacion');
      if (selOp) selOp.value = 'TODOS';
      const selTip = document.getElementById('filtroKpiTipologia');
      if (selTip) selTip.value = 'TODOS';
      const selMar = document.getElementById('filtroKpiMarca');
      if (selMar) selMar.value = 'TODOS';
      const selDim = document.getElementById('filtroKpiDimension');
      if (selDim) selDim.value = 'TODOS';
      const selEje = document.getElementById('filtroKpiEjeTemporal');
      if (selEje) selEje.value = 'mes';

      cargarSuite20Kpis();
      cargarKpis();
    }

    function exportarKpisExcel() {
      const qNum = (document.getElementById('filtroKpiNumero')?.value || '').trim();
      const cli = document.getElementById('filtroKpiCliente')?.value || '';
      const sub = document.getElementById('filtroKpiSubcliente')?.value || '';
      const op = document.getElementById('filtroKpiOperacion')?.value || '';
      const marca = document.getElementById('filtroKpiMarca')?.value || '';
      // Tipología y dimensión también filtran la tabla (antes solo las gráficas)
      const tip = document.getElementById('filtroKpiTipologia')?.value || '';
      const dim = document.getElementById('filtroKpiDimension')?.value || '';

      const params = new URLSearchParams();
      if (qNum) params.append('numero_interno', qNum);
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);
      if (tip && tip !== 'TODOS') params.append('tipologia', tip);
      if (marca && marca !== 'TODOS') params.append('marca', marca);
      if (dim && dim !== 'TODOS') params.append('dimension', dim);

      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (tok) params.append('token', tok);

      window.location.href = `/api/kpis-llantas/exportar-excel?${params.toString()}`;
    }

    // =========================================================================
    // VISTA: COMPOSICIÓN & CARACTERIZACIÓN DE FLOTA (v3.5 ENTERPRISE) - SCRIPTS
    // =========================================================================
    let cacheComposicionLlantas = [];
    let chartsComposicion = { vida: null, marca: null, dimension: null, diseno: null };

    function normalizarTextoComp(val, fallback = 'SIN ESPECIFICAR') {
      return String(val || '').trim().toUpperCase() || fallback;
    }

    function esLlantaReencauchadaComp(vidaStr) {
      const v = String(vidaStr || '').trim().toLowerCase();
      return /^r\d+$/.test(v) || /^\d+r$/.test(v) || ['reenc', 'renov'].some(token => v.includes(token));
    }

    async function cargarComposicionFlotaWeb(forzarRecarga = false) {
      if (!forzarRecarga && cacheComposicionLlantas && cacheComposicionLlantas.length > 0) {
        renderizarComposicionFlotaWeb();
        return;
      }

      const tbody = document.getElementById('tbody_composicion_flota');
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="8" class="p-10 text-center"><div class="flex flex-col items-center justify-center space-y-3"><div class="w-8 h-8 rounded-full border-3 border-cyan-500 border-t-transparent animate-spin"></div><p class="text-xs font-bold text-slate-600">Consultando composición de flota en tiempo real...</p></div></td></tr>`;
      }

      const token = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      try {
        const res = await fetch('/api/kpis-llantas', { headers });
        if (res.ok) {
          const raw = await res.json();
          cacheComposicionLlantas = (Array.isArray(raw) ? raw : []).map(item => ({
            ...item,
            // Dato vacío = "SIN ..." (antes GENÉRICA / ESTÁNDAR / FLOTA GENERAL: parecían marcas, medidas y clientes reales)
            marca: normalizarTextoComp(item.marca, 'SIN MARCA'),
            diseno: normalizarTextoComp(item.diseno, 'SIN DISEÑO'),
            dimension: normalizarTextoComp(item.dimension, 'SIN MEDIDA'),
            cliente: normalizarTextoComp(item.cliente, 'SIN CLIENTE'),
            subcliente: normalizarTextoComp(item.subcliente, 'SIN SEDE'),
            vida: normalizarTextoComp(item.vida, 'ORIGINAL'),
            tipo_eje: String(item.tipo_eje || 'libre').trim().toLowerCase()
          }));

          poblarFiltrosComposicionCascada();
          renderizarComposicionFlotaWeb();
        } else if (res.status === 401) {
          if (tbody) {
            tbody.innerHTML = `<tr><td colspan="8" class="p-10 text-center"><div class="flex flex-col items-center justify-center space-y-2 max-w-sm mx-auto"><div class="w-10 h-10 rounded-2xl bg-amber-50 flex items-center justify-center text-amber-600 text-lg shadow-2xs"><i class="fa-solid fa-lock"></i></div><p class="text-xs font-bold text-amber-800">Sesión no válida o expirada</p><p class="text-[11px] text-slate-500">Por favor, inicie sesión nuevamente para acceder a los datos de composición.</p></div></td></tr>`;
          }
        } else {
          if (tbody) {
            tbody.innerHTML = `<tr><td colspan="8" class="p-10 text-center"><div class="flex flex-col items-center justify-center space-y-3 max-w-sm mx-auto"><div class="w-10 h-10 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-600 text-lg shadow-2xs"><i class="fa-solid fa-triangle-exclamation"></i></div><p class="text-xs font-bold text-rose-700">Error al consultar composición (${res.status})</p><button type="button" onclick="cargarComposicionFlotaWeb(true)" class="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-sm transition-all cursor-pointer">Reintentar</button></div></td></tr>`;
          }
        }
      } catch (e) {
        console.error('Error al cargarComposicionFlotaWeb:', e);
        if (tbody) {
          tbody.innerHTML = `<tr><td colspan="8" class="p-10 text-center"><div class="flex flex-col items-center justify-center space-y-3 max-w-sm mx-auto"><div class="w-10 h-10 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-600 text-lg shadow-2xs"><i class="fa-solid fa-wifi"></i></div><p class="text-xs font-bold text-rose-700">Error de red al consultar composición de flota</p><button type="button" onclick="cargarComposicionFlotaWeb(true)" class="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-sm transition-all cursor-pointer">Reintentar</button></div></td></tr>`;
        }
      }
    }

    function poblarFiltrosComposicionCascada() {
      const selCli = document.getElementById('filtro_comp_cliente');
      if (!selCli) return;

      const valorCliPrevio = selCli.value || 'TODOS';
      const clientesUnicos = Array.from(new Set(cacheComposicionLlantas.map(x => x.cliente).filter(Boolean))).sort();

      let htmlCli = '<option value="TODOS">Todos</option>';
      clientesUnicos.forEach(c => {
        htmlCli += `<option value="${c}">${c}</option>`;
      });
      selCli.innerHTML = htmlCli;

      if (clientesUnicos.includes(valorCliPrevio)) {
        selCli.value = valorCliPrevio;
      } else {
        selCli.value = 'TODOS';
      }

      poblarFiltrosSecundariosComposicion();
    }

    function poblarFiltrosSecundariosComposicion() {
      const cli = document.getElementById('filtro_comp_cliente')?.value || 'TODOS';
      const conjunto = (cli && cli !== 'TODOS')
        ? cacheComposicionLlantas.filter(x => x.cliente === cli)
        : cacheComposicionLlantas;

      const selSub = document.getElementById('filtro_comp_subcliente');
      const selMarca = document.getElementById('filtro_comp_marca');
      const selDim = document.getElementById('filtro_comp_dimension');
      const selDis = document.getElementById('filtro_comp_diseno');

      const rellenarSelect = (el, lista, etiquetaTodos) => {
        if (!el) return;
        const prev = el.value || 'TODOS';
        let h = `<option value="TODOS">${etiquetaTodos}</option>`;
        lista.forEach(val => {
          h += `<option value="${val}">${val}</option>`;
        });
        el.innerHTML = h;
        if (lista.includes(prev)) el.value = prev;
        else el.value = 'TODOS';
      };

      const subs = Array.from(new Set(conjunto.map(x => x.subcliente).filter(Boolean))).sort();
      const marcas = Array.from(new Set(conjunto.map(x => x.marca).filter(Boolean))).sort();
      const dims = Array.from(new Set(conjunto.map(x => x.dimension).filter(Boolean))).sort();
      const disenos = Array.from(new Set(conjunto.map(x => x.diseno).filter(Boolean))).sort();

      rellenarSelect(selSub, subs, 'Todas');
      rellenarSelect(selMarca, marcas, 'Todas');
      rellenarSelect(selDim, dims, 'Todas');
      rellenarSelect(selDis, disenos, 'Todos');
    }

    function alCambiarClienteComposicion() {
      poblarFiltrosSecundariosComposicion();
      renderizarComposicionFlotaWeb();
    }

    function seleccionarEjeRapidoComposicion(tipoEje) {
      const selEje = document.getElementById('filtro_comp_tipo_eje');
      if (selEje) selEje.value = tipoEje;
      sincronizarBotonesEjeComposicion(tipoEje);
      renderizarComposicionFlotaWeb();
    }

    function alCambiarTipoEjeSelectComposicion() {
      const selEje = document.getElementById('filtro_comp_tipo_eje');
      const tipo = selEje ? selEje.value : 'TODOS';
      sincronizarBotonesEjeComposicion(tipo);
      renderizarComposicionFlotaWeb();
    }

    function sincronizarBotonesEjeComposicion(tipoActivo) {
      const botones = ['TODOS', 'direccional', 'traccion', 'libre'];
      botones.forEach(b => {
        const btn = document.getElementById(`btn_eje_comp_${b}`);
        if (!btn) return;
        if (b === tipoActivo) {
          btn.className = 'px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all bg-white text-slate-900 shadow-sm border border-slate-200/80 cursor-pointer';
        } else {
          btn.className = 'px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 cursor-pointer';
        }
      });
    }

    function limpiarFiltrosComposicion() {
      const selCli = document.getElementById('filtro_comp_cliente');
      const selSub = document.getElementById('filtro_comp_subcliente');
      const selEje = document.getElementById('filtro_comp_tipo_eje');
      const selVida = document.getElementById('filtro_comp_vida');
      const selMar = document.getElementById('filtro_comp_marca');
      const selDim = document.getElementById('filtro_comp_dimension');
      const selDis = document.getElementById('filtro_comp_diseno');

      if (selCli) selCli.value = 'TODOS';
      if (selSub) selSub.value = 'TODOS';
      if (selEje) selEje.value = 'TODOS';
      if (selVida) selVida.value = 'TODAS';
      if (selMar) selMar.value = 'TODOS';
      if (selDim) selDim.value = 'TODOS';
      if (selDis) selDis.value = 'TODOS';

      sincronizarBotonesEjeComposicion('TODOS');
      poblarFiltrosSecundariosComposicion();
      renderizarComposicionFlotaWeb();
    }

    function renderizarComposicionFlotaWeb() {
      const cli = document.getElementById('filtro_comp_cliente')?.value || 'TODOS';
      const sub = document.getElementById('filtro_comp_subcliente')?.value || 'TODOS';
      const eje = document.getElementById('filtro_comp_tipo_eje')?.value || 'TODOS';
      const vida = document.getElementById('filtro_comp_vida')?.value || 'TODAS';
      const marca = document.getElementById('filtro_comp_marca')?.value || 'TODOS';
      const dim = document.getElementById('filtro_comp_dimension')?.value || 'TODOS';
      const dis = document.getElementById('filtro_comp_diseno')?.value || 'TODOS';

      // 1. Filtrado Reactivo en Memoria con Reglas de Negocio
      const dataFiltrada = cacheComposicionLlantas.filter(llanta => {
        if (cli !== 'TODOS' && llanta.cliente !== cli) return false;
        if (sub !== 'TODOS' && llanta.subcliente !== sub) return false;

        // Regla Especial de Ejes y Repuesto (Sección 7 del Manual):
        // Si se filtra por un eje operativo ('direccional', 'traccion', 'libre'),
        // las llantas de repuesto ('repuesto') NO se suman; solo se incluyen en 'TODOS'.
        if (eje !== 'TODOS') {
          if (llanta.tipo_eje === 'repuesto' || llanta.tipo_eje !== eje) return false;
        }

        if (vida !== 'TODAS') {
          const esReenc = esLlantaReencauchadaComp(llanta.vida);
          if (vida === 'ORIGINAL' && esReenc) return false;
          if (vida === 'REENCAUCHE' && !esReenc) return false;
        }

        if (marca !== 'TODOS' && llanta.marca !== marca) return false;
        if (dim !== 'TODOS' && llanta.dimension !== dim) return false;
        if (dis !== 'TODOS' && llanta.diseno !== dis) return false;
        return true;
      });

      const totalLlantas = dataFiltrada.length;
      const placasSet = new Set(dataFiltrada.map(x => x.placa).filter(Boolean));
      const totalVehiculos = placasSet.size;

      // 2. Agregaciones y Mapas
      let cntReenc = 0;
      let cntOrig = 0;
      const mapaMarcas = {};
      const mapaDimensiones = {};
      const mapaDisenos = {};
      const mapaCombinaciones = {};

      dataFiltrada.forEach(llanta => {
        const esReenc = esLlantaReencauchadaComp(llanta.vida);
        if (esReenc) cntReenc++; else cntOrig++;

        mapaMarcas[llanta.marca] = (mapaMarcas[llanta.marca] || 0) + 1;
        mapaDimensiones[llanta.dimension] = (mapaDimensiones[llanta.dimension] || 0) + 1;
        mapaDisenos[llanta.diseno] = (mapaDisenos[llanta.diseno] || 0) + 1;

        const keyComb = `${llanta.marca}|||${llanta.diseno}|||${llanta.dimension}`;
        if (!mapaCombinaciones[keyComb]) {
          mapaCombinaciones[keyComb] = {
            marca: llanta.marca,
            diseno: llanta.diseno,
            dimension: llanta.dimension,
            orig: 0,
            reenc: 0,
            total: 0,
            sumaProf: 0,
            cantProf: 0
          };
        }
        const c = mapaCombinaciones[keyComb];
        if (esReenc) c.reenc++; else c.orig++;
        c.total++;
        const pMin = parseFloat(llanta.prof_actual_min || 0);
        if (pMin > 0) {
          c.sumaProf += pMin;
          c.cantProf++;
        }
      });

      // 3. Actualización de las 6 Tarjetas Resumen de KPIs (Scorecards) con Protección Div/0
      const elTotLlantas = document.getElementById('comp_kpi_total_llantas');
      const elTotVeh = document.getElementById('comp_kpi_total_vehiculos');
      const elPctReenc = document.getElementById('comp_kpi_pct_reenc');
      const elCntReenc = document.getElementById('comp_kpi_cnt_reenc');
      const elPctOrig = document.getElementById('comp_kpi_pct_orig');
      const elCntOrig = document.getElementById('comp_kpi_cnt_orig');
      const elTopMarca = document.getElementById('comp_kpi_top_marca');
      const elSubMarca = document.getElementById('comp_kpi_sub_marca');
      const elTopDim = document.getElementById('comp_kpi_top_dim');
      const elSubDim = document.getElementById('comp_kpi_sub_dim');
      const elTopDis = document.getElementById('comp_kpi_top_diseno');
      const elSubDis = document.getElementById('comp_kpi_sub_diseno');

      if (elTotLlantas) elTotLlantas.textContent = totalLlantas;
      if (elTotVeh) elTotVeh.textContent = `${totalVehiculos} vehículo(s) activo(s)`;

      if (totalLlantas === 0) {
        if (elPctReenc) elPctReenc.textContent = '0.0%';
        if (elCntReenc) elCntReenc.textContent = '0 llanta(s) reencauchada(s)';
        if (elPctOrig) elPctOrig.textContent = '0.0%';
        if (elCntOrig) elCntOrig.textContent = '0 llanta(s) originales';
        if (elTopMarca) elTopMarca.textContent = '—';
        if (elSubMarca) elSubMarca.textContent = '0 llantas (0.0%)';
        if (elTopDim) elTopDim.textContent = '—';
        if (elSubDim) elSubDim.textContent = '0 llantas (0.0%)';
        if (elTopDis) elTopDis.textContent = '—';
        if (elSubDis) elSubDis.textContent = '0 llantas montadas (0.0%)';
      } else {
        const pctR = fmtDec(((cntReenc / totalLlantas) * 100), 1);
        const pctO = fmtDec(((cntOrig / totalLlantas) * 100), 1);
        if (elPctReenc) elPctReenc.textContent = `${pctR}%`;
        if (elCntReenc) elCntReenc.textContent = `${cntReenc} llanta(s) reencauchada(s)`;
        if (elPctOrig) elPctOrig.textContent = `${pctO}%`;
        if (elCntOrig) elCntOrig.textContent = `${cntOrig} llanta(s) originales`;

        // La marca, medida y diseño "principal" son el valor real más frecuente: los "SIN ..." solo si no hay otro
        const principalPrimero = mapa => {
          const arr = Object.entries(mapa).sort((a, b) => b[1] - a[1]);
          return [...arr.filter(([k]) => !k.startsWith('SIN ')), ...arr.filter(([k]) => k.startsWith('SIN '))];
        };
        const arrM = principalPrimero(mapaMarcas);
        const arrDm = principalPrimero(mapaDimensiones);
        const arrDs = principalPrimero(mapaDisenos);

        if (arrM.length > 0) {
          const [mNom, mCant] = arrM[0];
          const mPct = fmtDec(((mCant / totalLlantas) * 100), 1);
          if (elTopMarca) elTopMarca.textContent = mNom;
          if (elSubMarca) elSubMarca.textContent = `${mCant} llantas (${mPct}%)`;
        }
        if (arrDm.length > 0) {
          const [dNom, dCant] = arrDm[0];
          const dPct = fmtDec(((dCant / totalLlantas) * 100), 1);
          if (elTopDim) elTopDim.textContent = dNom;
          if (elSubDim) elSubDim.textContent = `${dCant} llantas (${dPct}%)`;
        }
        if (arrDs.length > 0) {
          const [sNom, sCant] = arrDs[0];
          const sPct = fmtDec(((sCant / totalLlantas) * 100), 1);
          if (elTopDis) elTopDis.textContent = sNom;
          if (elSubDis) elSubDis.textContent = `${sCant} llantas montadas (${sPct}%)`;
        }
      }

      // 4. Panel de Auditoría: "Las 4 Reglas de Oro de Negocio" (Sección 8 del Manual)
      // Regla de Oro 1: Cero Reencauches en Dirección
      const llantasDireccionales = dataFiltrada.filter(x => x.tipo_eje === 'direccional');
      const totalDir = llantasDireccionales.length;
      const reencEnDir = llantasDireccionales.filter(x => esLlantaReencauchadaComp(x.vida)).length;
      const pctReencDir = totalDir > 0 ? fmtDec(((reencEnDir / totalDir) * 100), 1) : '0,0';

      const cardR1 = document.getElementById('card_regla_oro_1');
      const badgeR1 = document.getElementById('badge_regla_oro_1');
      const titR1 = document.getElementById('txt_regla_oro_1_titulo');
      const descR1 = document.getElementById('txt_regla_oro_1_desc');

      if (reencEnDir > 0) {
        if (cardR1) cardR1.className = 'p-3 rounded-2xl border transition-all duration-300 bg-rose-50 border-rose-300 shadow-sm';
        if (badgeR1) {
          badgeR1.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-rose-600 text-white animate-pulse';
          badgeR1.textContent = 'INCUMPLIDA';
        }
        if (titR1) {
          titR1.className = 'text-xs font-black text-rose-900';
          titR1.textContent = '🚨 REGLA DE ORO 1 INCUMPLIDA';
        }
        if (descR1) {
          descR1.className = 'text-[11px] text-rose-800 mt-0.5 leading-snug font-medium';
          descR1.textContent = `Se detectaron ${reencEnDir} llanta(s) reencauchada(s) en Eje Direccional (${pctReencDir}%). El estándar exige estrictamente 0,0%.`;
        }
      } else {
        if (cardR1) cardR1.className = 'p-3 rounded-2xl border transition-all duration-300 bg-emerald-50 border-emerald-300 shadow-sm';
        if (badgeR1) {
          badgeR1.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-600 text-white';
          badgeR1.textContent = 'CUMPLIDA (0.0%)';
        }
        if (titR1) {
          titR1.className = 'text-xs font-black text-emerald-900';
          titR1.textContent = '✅ Regla de Oro 1 Cumplida';
        }
        if (descR1) {
          descR1.className = 'text-[11px] text-emerald-800 mt-0.5 leading-snug';
          descR1.textContent = '0.0% Reencauches en Dirección. Cumplimiento estricto de seguridad vial.';
        }
      }

      // Regla de Oro 2: Adopción Renovado Remolques y Tracción
      const llantasLibres = dataFiltrada.filter(x => x.tipo_eje === 'libre');
      const reencLibres = llantasLibres.filter(x => esLlantaReencauchadaComp(x.vida)).length;
      const pctLibres = llantasLibres.length > 0 ? fmtDec(((reencLibres / llantasLibres.length) * 100), 1) : '0,0';

      const llantasTrac = dataFiltrada.filter(x => x.tipo_eje === 'traccion');
      const reencTrac = llantasTrac.filter(x => esLlantaReencauchadaComp(x.vida)).length;
      const pctTrac = llantasTrac.length > 0 ? fmtDec(((reencTrac / llantasTrac.length) * 100), 1) : '0,0';

      const badgeR2 = document.getElementById('badge_regla_oro_2');
      const descR2 = document.getElementById('txt_regla_oro_2_desc');
      if (badgeR2 && descR2) {
        badgeR2.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-blue-100 text-blue-800';
        badgeR2.textContent = `Rem ${pctLibres}% | Trac ${pctTrac}%`;
        descR2.textContent = `Madurez: Remolque ${pctLibres}% (Meta >70%), Tracción ${pctTrac}% (Meta 50%-65%).`;
      }

      // Regla de Oro 3: Índice de Dispersión Dimensional
      const arrDimsTotal = Object.entries(mapaDimensiones).sort((a, b) => b[1] - a[1]);
      const cardR3 = document.getElementById('card_regla_oro_3');
      const badgeR3 = document.getElementById('badge_regla_oro_3');
      const titR3 = document.getElementById('txt_regla_oro_3_titulo');
      const descR3 = document.getElementById('txt_regla_oro_3_desc');

      if (arrDimsTotal.length > 0 && totalLlantas > 0) {
        const topDimPct = (arrDimsTotal[0][1] / totalLlantas) * 100;
        const totalDimsDistintas = arrDimsTotal.length;
        if (topDimPct < 70 && totalDimsDistintas > 4) {
          if (cardR3) cardR3.className = 'p-3 rounded-2xl border transition-all duration-300 bg-amber-50 border-amber-300 shadow-sm';
          if (badgeR3) {
            badgeR3.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-amber-500 text-white';
            badgeR3.textContent = 'ALTA DISPERSIÓN';
          }
          if (titR3) titR3.textContent = '⚠️ Dispersión Dimensional';
          if (descR3) descR3.textContent = `Medida líder concentra ${fmtDec(topDimPct, 1)}% con ${totalDimsDistintas} medidas activas. Se sugiere racionalizar.`;
        } else {
          if (cardR3) cardR3.className = 'p-3 rounded-2xl border transition-all duration-300 bg-emerald-50 border-emerald-200';
          if (badgeR3) {
            badgeR3.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800';
            badgeR3.textContent = 'ESTANDARIZADA';
          }
          if (titR3) titR3.textContent = '✅ Estandarización Óptima';
          if (descR3) descR3.textContent = `Medida principal concentra ${fmtDec(topDimPct, 1)}% en ${totalDimsDistintas} dimensión(es).`;
        }
      }

      // 5. Renderizado de Gráficos Chart.js HD (Sección 5 del Manual)
      renderizarGraficosComposicion({
        cntOrig,
        cntReenc,
        mapaMarcas,
        mapaDimensiones,
        mapaDisenos,
        totalLlantas
      });

      // 6. Renderizado de la Matriz de Inventario [Marca × Diseño × Medida]
      renderizarMatrizComposicion(mapaCombinaciones, totalLlantas);
    }

    function renderizarGraficosComposicion({ cntOrig, cntReenc, mapaMarcas, mapaDimensiones, mapaDisenos, totalLlantas }) {
      if (typeof Chart === 'undefined') return;

      const tooltipStyleHD = {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        padding: 10,
        boxPadding: 4,
        cornerRadius: 8,
        displayColors: true
      };

      // Gráfico 1: Condición / Vida de Llanta por Eje (Doughnut cutout: '62%')
      const cvVida = document.getElementById('chartCompVidaEje');
      if (cvVida) {
        if (chartsComposicion.vida) chartsComposicion.vida.destroy();
        const ctxVida = cvVida.getContext('2d');
        const totVida = cntOrig + cntReenc;

        if (totVida === 0) {
          chartsComposicion.vida = new Chart(ctxVida, {
            type: 'doughnut',
            data: {
              labels: ['Sin llantas registradas'],
              datasets: [{
                data: [1],
                backgroundColor: ['#f1f5f9'],
                borderWidth: 1,
                borderColor: '#e2e8f0'
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: '62%',
              plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, padding: 8, font: { size: 10, weight: '600' } } },
                tooltip: { enabled: false }
              }
            }
          });
        } else {
          const pOrig = fmtDec(((cntOrig / totVida) * 100), 1);
          const pReenc = fmtDec(((cntReenc / totVida) * 100), 1);

          chartsComposicion.vida = new Chart(ctxVida, {
            type: 'doughnut',
            data: {
              labels: [`Original (${pOrig}%)`, `Reencauche (${pReenc}%)`],
              datasets: [{
                data: [cntOrig, cntReenc],
                backgroundColor: ['#3b82f6', '#10b981'],
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 4
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: '62%',
              plugins: {
                legend: {
                  position: 'bottom',
                  labels: { boxWidth: 12, padding: 12, font: { size: 11, weight: 'bold' } }
                },
                tooltip: {
                  ...tooltipStyleHD,
                  callbacks: {
                    label: (ctx) => ` ${ctx.label}: ${ctx.raw} llantas`
                  }
                }
              }
            }
          });
        }
      }

      // Gráfico 2: Participación por Marca — Top 7 (Doughnut cutout: '58%')
      const cvMarcas = document.getElementById('chartCompMarcas');
      if (cvMarcas) {
        if (chartsComposicion.marca) chartsComposicion.marca.destroy();
        const ctxMarcas = cvMarcas.getContext('2d');

        if (totalLlantas === 0) {
          chartsComposicion.marca = new Chart(ctxMarcas, {
            type: 'doughnut',
            data: {
              labels: ['Sin datos'],
              datasets: [{ data: [1], backgroundColor: ['#f1f5f9'], borderWidth: 1, borderColor: '#e2e8f0' }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: '58%',
              plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, padding: 8, font: { size: 10, weight: '600' } } },
                tooltip: { enabled: false }
              }
            }
          });
        } else {
          const arrM = Object.entries(mapaMarcas).sort((a, b) => b[1] - a[1]);
          const top7M = arrM.slice(0, 7);
          const otrosM = arrM.slice(7).reduce((acc, curr) => acc + curr[1], 0);
          if (otrosM > 0) top7M.push(['OTROS', otrosM]);

          const paletaMarcas = ['#2563eb', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b', '#94a3b8'];
          const labelsM = top7M.map(([m, cnt]) => {
            const p = fmtDec(((cnt / totalLlantas) * 100), 1);
            return `${m} (${p}%)`;
          });
          const dataM = top7M.map(([, cnt]) => cnt);

          chartsComposicion.marca = new Chart(ctxMarcas, {
            type: 'doughnut',
            data: {
              labels: labelsM,
              datasets: [{
                data: dataM,
                backgroundColor: paletaMarcas.slice(0, top7M.length),
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 4
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: '58%',
              plugins: {
                legend: {
                  position: 'bottom',
                  labels: { boxWidth: 10, padding: 8, font: { size: 10, weight: '600' } }
                },
                tooltip: {
                  ...tooltipStyleHD,
                  callbacks: {
                    label: (ctx) => ` ${ctx.label}: ${ctx.raw} llantas`
                  }
                }
              }
            }
          });
        }
      }

      // Gráfico 3: Distribución por Dimensión — Top 6 (Pie 360°)
      const cvDim = document.getElementById('chartCompDimensiones');
      if (cvDim) {
        if (chartsComposicion.dimension) chartsComposicion.dimension.destroy();
        const ctxDim = cvDim.getContext('2d');

        if (totalLlantas === 0) {
          chartsComposicion.dimension = new Chart(ctxDim, {
            type: 'pie',
            data: {
              labels: ['Sin datos'],
              datasets: [{ data: [1], backgroundColor: ['#f1f5f9'], borderWidth: 1, borderColor: '#e2e8f0' }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, padding: 8, font: { size: 10, weight: '600' } } },
                tooltip: { enabled: false }
              }
            }
          });
        } else {
          const arrD = Object.entries(mapaDimensiones).sort((a, b) => b[1] - a[1]);
          const top6D = arrD.slice(0, 6);
          const otrosD = arrD.slice(6).reduce((acc, curr) => acc + curr[1], 0);
          if (otrosD > 0) top6D.push(['OTRAS', otrosD]);

          const paletaDim = ['#7c3aed', '#0891b2', '#d97706', '#059669', '#1d4ed8', '#c026d3', '#94a3b8'];
          const labelsD = top6D.map(([d, cnt]) => {
            const p = fmtDec(((cnt / totalLlantas) * 100), 1);
            return `${d} (${p}%)`;
          });
          const dataD = top6D.map(([, cnt]) => cnt);

          chartsComposicion.dimension = new Chart(ctxDim, {
            type: 'pie',
            data: {
              labels: labelsD,
              datasets: [{
                data: dataD,
                backgroundColor: paletaDim.slice(0, top6D.length),
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 4
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: 'bottom',
                  labels: { boxWidth: 10, padding: 8, font: { size: 10, weight: '600' } }
                },
                tooltip: {
                  ...tooltipStyleHD,
                  callbacks: {
                    label: (ctx) => ` ${ctx.label}: ${ctx.raw} llantas`
                  }
                }
              }
            }
          });
        }
      }

      // Gráfico 4: Top Diseños de Rodamiento — Top 6 (Bar Vertical)
      const cvDis = document.getElementById('chartCompDisenos');
      if (cvDis) {
        if (chartsComposicion.diseno) chartsComposicion.diseno.destroy();
        const ctxDis = cvDis.getContext('2d');

        if (totalLlantas === 0) {
          chartsComposicion.diseno = new Chart(ctxDis, {
            type: 'bar',
            data: {
              labels: ['Sin datos'],
              datasets: [{ label: 'Llantas Montadas', data: [0], backgroundColor: '#f1f5f9' }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              scales: { y: { beginAtZero: true, max: 10 } },
              plugins: { legend: { display: false }, tooltip: { enabled: false } }
            }
          });
        } else {
          const arrDs = Object.entries(mapaDisenos).sort((a, b) => b[1] - a[1]);
          const top6Ds = arrDs.slice(0, 6);
          const labelsDs = top6Ds.map(([ds]) => ds);
          const dataDs = top6Ds.map(([, cnt]) => cnt);

          chartsComposicion.diseno = new Chart(ctxDis, {
            type: 'bar',
            data: {
              labels: labelsDs,
              datasets: [{
                label: 'Llantas Montadas',
                data: dataDs,
                backgroundColor: '#f59e0b',
                borderRadius: 6,
                borderSkipped: false
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false },
                tooltip: {
                  ...tooltipStyleHD,
                  callbacks: {
                    label: (ctx) => {
                      const cnt = ctx.raw;
                      const p = fmtDec(((cnt / totalLlantas) * 100), 1);
                      return ` ${cnt} llantas (${p}%)`;
                    }
                  }
                }
              },
              scales: {
                x: {
                  grid: { display: false },
                  ticks: { font: { size: 10, weight: '600' } }
                },
                y: {
                  beginAtZero: true,
                  ticks: { precision: 0 }
                }
              }
            }
          });
        }
      }
    }

    function renderizarMatrizComposicion(mapaCombinaciones, totalLlantasFlota) {
      const tbody = document.getElementById('tbody_composicion_flota');
      const badgeComb = document.getElementById('badge_comp_combinaciones');
      if (!tbody) return;

      const combinaciones = Object.values(mapaCombinaciones).sort((a, b) => b.total - a.total);
      if (badgeComb) {
        badgeComb.textContent = `${combinaciones.length} combinaciones activas`;
      }

      if (combinaciones.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="8" class="p-10 text-center">
              <div class="flex flex-col items-center justify-center max-w-sm mx-auto space-y-3">
                <div class="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400 text-xl shadow-inner">
                  <i class="fa-solid fa-filter-circle-xmark"></i>
                </div>
                <p class="text-sm font-bold text-slate-800">No hay neumáticos con los filtros seleccionados</p>
                <p class="text-xs text-slate-500">Prueba ajustando los criterios de búsqueda o limpiando los filtros para ver toda la flota activa.</p>
                <button type="button" onclick="limpiarFiltrosComposicion()" class="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm active:scale-95 cursor-pointer flex items-center gap-1.5">
                  <i class="fa-solid fa-rotate-left text-[11px]"></i>
                  <span>Restablecer Filtros</span>
                </button>
              </div>
            </td>
          </tr>
        `;
        return;
      }

      let html = '';
      combinaciones.forEach(c => {
        const pctFlota = totalLlantasFlota > 0 ? fmtDec(((c.total / totalLlantasFlota) * 100), 1) : '0,0';
        let profPromText = '—';
        let semaforoProf = 'text-slate-600 bg-slate-100 border border-slate-200';
        let semaforoDot = 'bg-slate-400';

        if (c.cantProf > 0) {
          const prom = (c.sumaProf / c.cantProf);
          profPromText = `${fmtDec(prom, 1)} mm`;
          if (prom >= 9.0) {
            semaforoProf = 'text-emerald-700 bg-emerald-50 border border-emerald-200/80';
            semaforoDot = 'bg-emerald-500';
          } else if (prom >= 5.0) {
            semaforoProf = 'text-amber-700 bg-amber-50 border border-amber-200/80';
            semaforoDot = 'bg-amber-500';
          } else {
            semaforoProf = 'text-rose-700 bg-rose-50 border border-rose-200/80 font-bold';
            semaforoDot = 'bg-rose-500 animate-pulse';
          }
        }

        html += `
          <tr class="hover:bg-cyan-50/40 transition-colors duration-150 border-b border-slate-100 last:border-b-0">
            <td class="p-3 font-bold text-slate-900">${c.marca}</td>
            <td class="p-3 text-slate-800 font-semibold">${c.diseno}</td>
            <td class="p-3 font-mono text-slate-600 text-[11px]">${c.dimension}</td>
            <td class="p-3 text-center text-blue-600 font-bold">${c.orig}</td>
            <td class="p-3 text-center text-emerald-600 font-bold">${c.reenc}</td>
            <td class="p-3 text-center text-slate-900 font-black">${c.total}</td>
            <td class="p-3 text-center text-indigo-600 font-extrabold">${pctFlota}%</td>
            <td class="p-3 text-center">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-xs font-black ${semaforoProf}">
                <span class="w-1.5 h-1.5 rounded-full ${semaforoDot}"></span>
                <span>${profPromText}</span>
              </span>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    }

    function exportarComposicionExcel() {
      const tbody = document.getElementById('tbody_composicion_flota');
      if (!tbody) return;

      const rows = Array.from(tbody.querySelectorAll('tr'));
      if (rows.length === 0 || rows[0].innerText.includes('No se encontraron') || rows[0].innerText.includes('Cargando')) {
        mostrarToast('No hay datos disponibles en la matriz para exportar', true);
        return;
      }

      let csv = '\uFEFF';
      csv += 'Marca;Diseño;Dimensión;Original;Reencauche;Total Llantas;% Part. Flota;Prof. Promedio\r\n';

      rows.forEach(tr => {
        const cols = Array.from(tr.querySelectorAll('td')).map(td => {
          let text = td.innerText.replace(/(\r\n|\n|\r)/gm, '').trim();
          return `"${text.replace(/"/g, '""')}"`;
        });
        if (cols.length === 8) {
          csv += cols.join(';') + '\r\n';
        }
      });

      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const now = new Date();
      const fechaStr = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}`;
      link.setAttribute('href', url);
      link.setAttribute('download', `Composicion_Flota_TireAnalyze_${fechaStr}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      mostrarToast('✅ Matriz de Composición de Flota exportada exitosamente');
    }

