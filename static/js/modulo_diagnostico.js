    // ==========================================
    // VISTA 3: PLANES DE ACCIÓN & DIAGNÓSTICO
    // ==========================================
    // ==========================================
    // VISTA 3: PLANES DE ACCIÓN & DIAGNÓSTICO (V3.5 ENTERPRISE)
    // ==========================================
    let paginaActualDiag = 1;
    const ITEMS_POR_PAGINA_DIAG = 25;
    let cacheFiltradasDiag = [];

    // Helper reactivo para compatibilidad total con IDs oficiales del manual y clásicos
    function getDiagEl(idNuevo, idClasico) {
      return document.getElementById(idNuevo) || (idClasico ? document.getElementById(idClasico) : null);
    }
    function getDiagVal(idNuevo, idClasico, defaultVal = '') {
      const el = getDiagEl(idNuevo, idClasico);
      return el ? (el.value || defaultVal) : defaultVal;
    }

    async function cargarDiagnostico() {
      const tbody = getDiagEl('tbody_diagnostico_web', 'tbodyDiagnostico');
      const tbodyMat = getDiagEl('tbody_semaforo_matriz_flota', 'tbodyMatrizSemaforos');
      if (tbody && (!cacheDiagnostico || cacheDiagnostico.length === 0)) {
        tbody.innerHTML = '<tr><td colspan="12" class="p-8 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2 text-blue-600"></i>Cargando diagnósticos de flota...</td></tr>';
      }
      if (tbodyMat && (!cacheMatrizSemaforos || !cacheMatrizSemaforos.filas)) {
        tbodyMat.innerHTML = '<tr><td colspan="16" class="p-8 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2 text-indigo-600"></i>Cargando matriz de semáforos por posición...</td></tr>';
      }
      try {
        const token = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        const fDesde = getDiagVal('filtro_diag_fecha_desde', 'filtroDiagFechaDesde');
        const fHasta = getDiagVal('filtro_diag_fecha_hasta', 'filtroDiagFechaHasta');
        const qParams = new URLSearchParams();
        if (fDesde) qParams.append('fecha_desde', fDesde);
        if (fHasta) qParams.append('fecha_hasta', fHasta);
        const qs = qParams.toString() ? `?${qParams.toString()}` : '';

        const [res, resMat] = await Promise.all([
          fetch(`/api/diagnostico${qs}`, { headers }),
          fetch(`/api/diagnostico/matriz-semaforos${qs}`, { headers })
        ]);
        if (res.ok) {
          cacheDiagnostico = await res.json();
        }
        if (resMat.ok) {
          cacheMatrizSemaforos = await resMat.json();
        }

        // Consultar indicadores de Ahorro ROI para el banner en diagnóstico
        try {
          const resGraf = await fetch(`/api/diagnostico/graficos${qs}`, { headers });
          if (resGraf.ok) {
            const dataGraf = await resGraf.json();
            if (dataGraf.ahorro_roi || dataGraf.resumen_ahorro_roi) {
              renderizarBannerAhorroRoi(dataGraf.ahorro_roi || dataGraf.resumen_ahorro_roi);
            }
          }
        } catch (_) {}
        if (res.ok) {
          actualizarCombosFiltroDiagnostico();
          filtrarTablaDiagnostico();
        } else if (res.status === 401) {
          if (tbody) tbody.innerHTML = '<tr><td colspan="12" class="p-8 text-center text-amber-600 font-bold"><i class="fa-solid fa-lock mr-2"></i>Sesión no iniciada o expirada. Inicia sesión para ver los diagnósticos.</td></tr>';
          if (tbodyMat) tbodyMat.innerHTML = '<tr><td colspan="16" class="p-8 text-center text-amber-600 font-bold"><i class="fa-solid fa-lock mr-2"></i>Sesión no iniciada o expirada.</td></tr>';
        } else {
          if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="p-8 text-center text-rose-500 font-bold"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Error al consultar diagnósticos (HTTP ${res.status}). <button onclick="cargarDiagnostico()" class="ml-2 px-3 py-1 bg-blue-600 text-white text-xs rounded-lg shadow">Reintentar</button></td></tr>`;
        }
      } catch (e) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="12" class="p-8 text-center text-rose-500 font-bold"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Error de conexión con el servidor. <button onclick="cargarDiagnostico()" class="ml-2 px-3 py-1 bg-blue-600 text-white text-xs rounded-lg shadow">Reintentar</button></td></tr>';
        if (typeof mostrarToast === 'function') mostrarToast('Error al cargar diagnóstico de flota', true);
      }
    }

    function onCambioRangoFechasDiagnostico() {
      cargarDiagnostico();
    }

    function actualizarCombosFiltroDiagnostico() {
      const selCli = getDiagEl('filtro_diag_cliente', 'filtroDiagCliente');
      const selOp = getDiagEl('filtro_diag_operacion', 'filtroDiagOperacion');

      const clientes = Array.from(new Set(cacheDiagnostico.map(r => r.Cliente ? String(r.Cliente).trim().toUpperCase() : '').filter(Boolean))).sort();
      const operaciones = Array.from(new Set(cacheDiagnostico.map(r => r.Operación).filter(Boolean))).sort();

      if (selCli) {
        const valCli = selCli.value || 'Todos';
        selCli.innerHTML = '<option value="Todos">Todos</option>' +
          clientes.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
        if (clientes.includes(valCli)) selCli.value = valCli;
      }

      actualizarCombosSedesDiagnostico();

      if (selOp) {
        const valOp = selOp.value || 'Todos';
        selOp.innerHTML = '<option value="Todos">Todas</option>' +
          operaciones.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join('');
        if (operaciones.includes(valOp)) selOp.value = valOp;
      }
    }

    function actualizarCombosSedesDiagnostico() {
      const selCli = getDiagEl('filtro_diag_cliente', 'filtroDiagCliente');
      const selSede = getDiagEl('filtro_diag_subcliente', 'filtroDiagSede');
      if (!selSede) return;

      const valCli = selCli ? (selCli.value || 'Todos') : 'Todos';
      const valCliNorm = valCli.trim().toUpperCase();
      const valSedeActual = selSede.value || 'Todos';

      const sedes = Array.from(new Set(
        cacheDiagnostico
          .filter(r => (valCliNorm === 'TODOS' || String(r.Cliente || '').trim().toUpperCase() === valCliNorm))
          .map(r => r.Subcliente)
          .filter(Boolean)
      )).sort();

      selSede.innerHTML = '<option value="Todos">Todas</option>' +
        sedes.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');

      if (sedes.some(s => s.trim().toUpperCase() === valSedeActual.trim().toUpperCase())) {
        selSede.value = valSedeActual;
      } else {
        selSede.value = 'Todos';
      }
    }

    function onCambioFiltrosDiagnostico() {
      filtrarTablaDiagnostico();
    }

    function onCambioFiltroDiagCliente() {
      actualizarCombosSedesDiagnostico();
      filtrarTablaDiagnostico();
    }

    function filtrarDiagnosticoPorCard(tipoAlerta) {
      const sel = getDiagEl('filtro_diag_accion', 'filtroDiagAlerta');
      if (sel) {
        sel.value = tipoAlerta;
        filtrarTablaDiagnostico();
      }
    }

    function cambiarPaginaDiag(nuevaPagina) {
      const totalPaginas = Math.ceil(cacheFiltradasDiag.length / ITEMS_POR_PAGINA_DIAG) || 1;
      if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
      paginaActualDiag = nuevaPagina;
      renderizarTablaDiagnostico();
      const contTabla = document.getElementById('contenedorTablaDiagnostico');
      if (contTabla) contTabla.scrollTop = 0;
    }

    function filtrarTablaDiagnostico() {
      const cli = getDiagVal('filtro_diag_cliente', 'filtroDiagCliente', 'Todos');
      const sede = getDiagVal('filtro_diag_subcliente', 'filtroDiagSede', 'Todos');
      const op = getDiagVal('filtro_diag_operacion', 'filtroDiagOperacion', 'Todos');
      const accion = getDiagVal('filtro_diag_accion', 'filtroDiagAlerta', 'Todos');
      const busqueda = getDiagVal('filtro_diag_busqueda', 'filtroDiagPlaca', '').trim().toLowerCase();

      // Actualizar botón de Consolidado Flota según el cliente y sede filtrados
      const btnCons = document.getElementById('btnConsolidadoDiag');
      const lblCons = document.getElementById('lblConsolidadoDiag');
      if (lblCons) {
        if (cli && cli !== 'Todos') {
          let texto = `Consolidado Flota (${cli}`;
          if (sede && sede !== 'Todos') {
            texto += ` - ${sede}`;
          }
          texto += `)`;
          lblCons.textContent = texto;
          if (btnCons) btnCons.title = `Generar Consolidado PDF para la flota de ${cli}${sede && sede !== 'Todos' ? ' · Sede ' + sede : ''}`;
        } else {
          lblCons.textContent = 'Consolidado Flota PDF';
          if (btnCons) btnCons.title = 'Selecciona un cliente en el filtro para generar su consolidado de flota';
        }
      }

      const cliNorm = String(cli || 'Todos').trim().toUpperCase();
      const sedeNorm = String(sede || 'Todos').trim().toUpperCase();
      const opNorm = String(op || 'Todos').trim().toUpperCase();

      // 1. Filtrar por ámbito de flota (Cliente, Sede, Operación y Placa/Búsqueda)
      const flotaFiltrada = (cacheDiagnostico || []).filter(r => {
        if (cliNorm !== 'TODOS' && String(r.Cliente || '').trim().toUpperCase() !== cliNorm) return false;
        if (sedeNorm !== 'TODOS' && String(r.Subcliente || '').trim().toUpperCase() !== sedeNorm) return false;
        if (opNorm !== 'TODOS' && String(r.Operación || '').trim().toUpperCase() !== opNorm) return false;
        if (busqueda && !String(r['Vehículo/Placa'] || '').toLowerCase().includes(busqueda)) return false;
        return true;
      });

      // 2. Conteo métrico de las 5 tarjetas KPI según el estándar de la Sección 4
      const kpiVehiculos = new Set(flotaFiltrada.map(r => r['Vehículo/Placa'])).size;
      const kpiRetiroYA = flotaFiltrada.reduce((acc, r) => acc + (Number(r.Cant_Cambios) || (r.Plan_Cambio_Llanta === 'SÍ' ? 1 : 0)), 0);
      const kpiProximas = flotaFiltrada.reduce((acc, r) => acc + (Number(r.Cant_Proximas) || 0), 0);
      const kpiAlineacionDual = flotaFiltrada.filter(r => 
        r.Plan_Alineacion === 'SÍ' || 
        r.Plan_Dual_Mal_Apareado === 'SÍ' || 
        r.Plan_Rotacion === 'SÍ' || 
        r.Badge_Rotacion === 'AUTO-AJUSTE'
      ).length;
      const kpiPresion = flotaFiltrada.reduce((acc, r) => acc + (Number(r.Cant_Presiones) || (r.Plan_Calibracion_PSI === 'SÍ' ? 1 : 0)), 0);

      // Actualizar valores en el DOM (oficiales y alias)
      const setCardTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
      setCardTxt('cardDiagTotal', kpiVehiculos);
      setCardTxt('diag_kpi_vehiculos', kpiVehiculos);
      setCardTxt('cardDiagCambio', kpiRetiroYA);
      setCardTxt('diag_kpi_retiro_ya', kpiRetiroYA);
      setCardTxt('cardDiagProximas', kpiProximas);
      setCardTxt('diag_kpi_proximas', kpiProximas);
      setCardTxt('cardDiagAlineacion', kpiAlineacionDual);
      setCardTxt('diag_kpi_alineacion_dual', kpiAlineacionDual);
      setCardTxt('cardDiagPresion', kpiPresion);
      setCardTxt('diag_kpi_presion', kpiPresion);

      // Resaltar tarjeta seleccionada según el filtro de acción
      const mapCards = {
        'Todos': 'cardBoxTotal',
        'Retiro Inmediato': 'cardBoxCambio',
        'Cambio': 'cardBoxCambio',
        'Próximas a Cambio': 'cardBoxProximas',
        'Proximas': 'cardBoxProximas',
        'Alineación': 'cardBoxAlineacion',
        'Alineacion': 'cardBoxAlineacion',
        'Dual': 'cardBoxAlineacion',
        'Rotaciones': 'cardBoxAlineacion',
        'Presión': 'cardBoxPresion',
        'Presion': 'cardBoxPresion'
      };
      ['cardBoxTotal', 'cardBoxCambio', 'cardBoxProximas', 'cardBoxAlineacion', 'cardBoxPresion'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-2');
      });
      const activeId = mapCards[accion];
      if (activeId && accion !== 'Todos') {
        const el = document.getElementById(activeId);
        if (el) el.classList.add('ring-2', 'ring-blue-500', 'ring-offset-2');
      }

      // 3. Filtrar por acción específica (8 opciones oficiales + alias clásicos)
      const filtradas = flotaFiltrada.filter(r => {
        const cCambios = Number(r.Cant_Cambios) || (r.Plan_Cambio_Llanta === 'SÍ' ? 1 : 0);
        const cProx = Number(r.Cant_Proximas) || 0;
        const esAlin = r.Plan_Alineacion === 'SÍ';
        const esDual = r.Plan_Dual_Mal_Apareado === 'SÍ';
        const esRot = r.Plan_Rotacion === 'SÍ' || r.Badge_Rotacion === 'AUTO-AJUSTE';
        const cPres = Number(r.Cant_Presiones) || (r.Plan_Calibracion_PSI === 'SÍ' ? 1 : 0);

        if (accion === 'Retiro Inmediato' || accion === 'Cambio') {
          return cCambios > 0;
        }
        if (accion === 'Próximas a Cambio' || accion === 'Proximas') {
          return cProx > 0;
        }
        if (accion === 'Estado OK' || accion === 'OK') {
          return cCambios === 0 && !esAlin && !esDual && !esRot && cPres === 0;
        }
        if (accion === 'Rotaciones') {
          return esRot;
        }
        if (accion === 'Alineación' || accion === 'Alineacion') {
          return esAlin;
        }
        if (accion === 'Dual') {
          return esDual;
        }
        if (accion === 'Presión' || accion === 'Presion') {
          return cPres > 0;
        }
        if (accion === 'Alerta') {
          return cCambios > 0 || cProx > 0 || esAlin || esDual || esRot || cPres > 0;
        }
        return true;
      });

      // Ordenar de la inspección más reciente a la más antigua (y secundariamente por placa)
      filtradas.sort((a, b) => {
        const fechaA = String(a.Fecha || '').trim();
        const fechaB = String(b.Fecha || '').trim();
        if (fechaA !== fechaB) {
          return fechaB.localeCompare(fechaA);
        }
        return String(a['Vehículo/Placa'] || '').localeCompare(String(b['Vehículo/Placa'] || ''));
      });

      // Sincronizar tooltip de exportación de diagnóstico a Excel
      const btnExp = document.getElementById('btnExportarDiagExcel');
      const hayFiltros = (cliNorm !== 'TODOS' || sedeNorm !== 'TODOS' || opNorm !== 'TODOS' || (accion && accion !== 'Todos') || Boolean(busqueda));
      if (btnExp) {
        btnExp.title = hayFiltros 
          ? `Exportar reporte Excel aplicando los filtros activos (${filtradas.length} vehículos)` 
          : `Exportar diagnóstico completo de flota en Excel (${kpiVehiculos} vehículos)`;
      }

      // Asignar a la caché de diagnóstico filtrado y renderizar página 1
      cacheFiltradasDiag = filtradas;
      paginaActualDiag = 1;
      renderizarTablaDiagnostico();

      // Actualizar automáticamente la Matriz de Semáforos por Posición
      renderizarMatrizSemaforos(cli, sede, op, busqueda);
    }

    // Mínima por eje (llanta más crítica de cada eje) y aviso si la tipología no está en el catálogo
    function resumenEjesDiagHtml(r) {
      const nombres = { 'DIRECCIONAL': 'Dir', 'TRACCIÓN': 'Trac', 'LIBRE': 'Libre', 'REPUESTO': 'Rep', 'SIN EJE': 'Sin eje' };
      const ejes = Array.isArray(r.Resumen_Ejes) ? r.Resumen_Ejes : [];
      const partes = ejes.map(e => {
        const min = (e.minima === null || e.minima === undefined) ? '—' : Number(e.minima).toFixed(1).replace('.', ',');
        const color = e.retiro > 0 ? 'text-rose-700 font-black' : (e.proximas > 0 ? 'text-amber-700 font-bold' : 'text-slate-600');
        return `<span class="${color}">${nombres[e.eje] || e.eje} ${min}</span>`;
      });
      let html = partes.length
        ? `<div class="text-[10px] text-slate-500 mb-1"><i class="fa-solid fa-ruler-vertical mr-1 text-slate-400"></i>Mín. por eje (mm): ${partes.join(' · ')}</div>`
        : '';
      if (r.Tipologia_Inferida) {
        html += `<div class="text-[10px] text-amber-700 mb-1"><i class="fa-solid fa-triangle-exclamation mr-1"></i>Tipología "${escapeHtml(r.Tipo || '')}" sin estructura en Catálogos: ejes deducidos</div>`;
      }
      return html;
    }

    function renderizarTablaDiagnostico() {
      const tbody = getDiagEl('tbody_diagnostico_web', 'tbodyDiagnostico');
      const contenedorPaginacion = document.getElementById('contenedorPaginacionDiag');
      if (!tbody) return;

      if (!cacheFiltradasDiag || cacheFiltradasDiag.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="p-8 text-center text-slate-400 font-medium">No hay vehículos que coincidan con los filtros seleccionados.</td></tr>`;
        if (contenedorPaginacion) contenedorPaginacion.classList.add('hidden');
        return;
      }

      // Cálculo de Paginación de 25 registros
      const totalRegistros = cacheFiltradasDiag.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_DIAG) || 1;
      if (paginaActualDiag > totalPaginas) paginaActualDiag = totalPaginas;
      if (paginaActualDiag < 1) paginaActualDiag = 1;

      const inicio = (paginaActualDiag - 1) * ITEMS_POR_PAGINA_DIAG;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_DIAG, totalRegistros);
      const paginaItems = cacheFiltradasDiag.slice(inicio, fin);

      // Rediseño: columnas y textos sencillos como el prototipo. Los datos son los mismos del cálculo del servidor;
      // cada alerta se resume en una palabra y el plan de acción se escribe en una sola línea.
      const variosClientes = new Set(cacheFiltradasDiag.map(x => x.Cliente)).size > 1;
      const sinAlerta = '<span class="ta-sin-alerta">Sin alerta</span>';
      const pastilla = (clase, texto, titulo) => `<span class="ta-pastilla ${clase}" title="${escapeHtml(titulo || '')}">${escapeHtml(texto)}</span>`;
      const numeros = (bloques, re) => {
        const vistos = new Set();
        bloques.forEach(b => { let m; const r2 = new RegExp(re.source, 'g'); while ((m = r2.exec(String(b.texto || '')))) vistos.add(Number(m[1])); });
        return [...vistos].sort((x, y) => x - y);
      };
      const lista = (arr) => arr.join(', ');
      // Los nombres llegan en MAYÚSCULAS: se muestran como en el prototipo (Sede Norte, Cabezote (6x4))
      const nombreBonito = (t) => String(t || '').toLowerCase().replace(/(^|[\s(/-])([a-záéíóúñ])/g, (m, a, b) => a + b.toUpperCase());

      tbody.innerHTML = paginaItems.map(r => {
        const cantCambios = Number(r.Cant_Cambios) || (r.Plan_Cambio_Llanta === 'SÍ' ? 1 : 0);
        const cantProx = Number(r.Cant_Proximas) || 0;
        const cantPsi = Number(r.Cant_Presiones) || 0;
        const esAlin = r.Plan_Alineacion === 'SÍ';
        const esDual = r.Plan_Dual_Mal_Apareado === 'SÍ';
        const bl = Array.isArray(r.Bloques_Recomendaciones) ? r.Bloques_Recomendaciones : [];
        const por = (...tipos) => bl.filter(b => tipos.includes(b.tipo));

        // Posiciones y pares que menciona el cálculo
        const posRetiro = numeros(por('RETIRO', 'PAR_DIRECCIONAL'), /Pos\s*(\d+)/);
        const posAlin = numeros(por('ALINEACION'), /Pos\s*(\d+)/);
        const pares = por('DUAL').map(b => (String(b.texto || '').match(/Dual\s*(\d+)\s*-\s*(\d+)/) || []).slice(1, 3).join('-')).filter(Boolean);
        const nDual = pares.length || (esDual ? 1 : 0);
        const posPend = Array.isArray(r.Posiciones_Pendientes) ? r.Posiciones_Pendientes : [];
        const cantPend = Number(r.Cant_Pendientes) || posPend.length;

        // Plan de acción: una frase corta por cada cosa por hacer
        const plan = [];
        if (cantCambios > 0) plan.push(posRetiro.length ? `Cambiar pos. ${lista(posRetiro)}` : `Cambiar ${cantCambios} llanta(s)`);
        if (esAlin) plan.push(posAlin.length ? `Alinear dirección (pos. ${lista(posAlin)})` : 'Alinear dirección');
        if (nDual > 0) plan.push(pares.length ? `Emparejar duales ${lista(pares)}` : 'Emparejar duales');
        if (cantPsi > 0) plan.push(`Calibrar ${cantPsi} llanta(s)`);
        // «Cruzar P1 ↔ P2» → «cruzar 1 ↔ 2»; «Invertir Pos 5 ↔ Pos 6» → «invertir 5 ↔ 6»
        const rotaciones = por('AUTO_AJUSTE', 'EQUIS_LARGA').map(b => String(b.texto || '')
          .replace(/^Auto-Ajuste[^:]*:\s*/i, '').replace(/\s*\(.*$/, '').replace(/\bPos\.?\s*(?=\d)/gi, '').replace(/\bP(?=\d)/g, '').trim())
          .filter(Boolean).map(t => t.charAt(0).toLowerCase() + t.slice(1));
        if (rotaciones.length) plan.push(`Rotar: ${rotaciones.join(', ')}`);
        const posIrreg = numeros(por('ROTACION_IRREGULAR', 'ROTACION_ESCALONADO'), /Pos\s*(\d+)/);
        if (posIrreg.length) plan.push(`Revisar desgaste irregular (pos. ${lista(posIrreg)})`);
        if (cantPend > 0) plan.push(posPend.length ? `Inspeccionar pos. ${lista(posPend)}` : `Inspeccionar ${cantPend} posición(es) pendiente(s)`);

        // Mínima por eje y aviso de tipología (información de apoyo, en gris debajo del plan)
        const apoyo = resumenEjesDiagHtml(r);
        // Marca de la fila: franja roja si hay llantas para retiro; además fondo rojo leve si el retiro es en la dirección
        const retiroDir = (Array.isArray(r.Resumen_Ejes) ? r.Resumen_Ejes : []).some(e => e.eje === 'DIRECCIONAL' && Number(e.retiro) > 0);
        const claseFila = retiroDir ? 'ta-fila-retiro ta-fila-urgente' : (cantCambios > 0 ? 'ta-fila-retiro' : '');
        const tituloFila = retiroDir ? 'Retiro en el eje de dirección: atender primero' : (cantCambios > 0 ? 'Tiene llantas para retiro' : '');

        return `
          <tr class="${claseFila}"${tituloFila ? ` title="${tituloFila}"` : ''}>
            <td class="placa">
              ${escapeHtml(r['Vehículo/Placa'])}
              ${r.Fecha ? `<span class="ta-fecha-fila">${fmtFecha(r.Fecha)}</span>` : ''}
            </td>
            <td class="s">
              ${escapeHtml(nombreBonito(r.Subcliente) || '—')}
              ${variosClientes ? `<span class="ta-fecha-fila">${escapeHtml(nombreBonito(r.Cliente))}</span>` : ''}
            </td>
            <td>
              ${escapeHtml(nombreBonito(r.Tipo) || '—')}
              <span class="ta-fecha-fila">${escapeHtml(r['Llantas Inspeccionadas'] || 0)} llantas · límite ${fmtDec(Number(r.Limite_Retiro_mm || 3), 1)} mm</span>
            </td>
            <td class="r">${cantCambios > 0 ? `<b class="ta-num-cr">${cantCambios}</b>` : '<span class="s">0</span>'}</td>
            <td class="r">${cantProx > 0 ? cantProx : '<span class="s">0</span>'}</td>
            <td>${esAlin ? pastilla('al', 'Revisar', r.Detalle_Alineacion) : sinAlerta}</td>
            <td>${nDual > 0 ? pastilla('al', `${nDual} par(es)`, r.Detalle_Dual) : sinAlerta}</td>
            <td>${cantPsi > 0 ? pastilla('al', `${cantPsi} llanta(s)`, r.Detalle_Calibracion_PSI) : sinAlerta}</td>
            <td class="wrap">
              ${plan.length ? escapeHtml(plan.join(' · ')) : '<span class="s">Sin acciones pendientes</span>'}
              ${apoyo ? `<div class="ta-apoyo">${apoyo}</div>` : ''}
            </td>
            <td class="c">
              <button type="button" onclick="abrirModalInformePdf('${r['Vehículo/Placa']}', '${escapeHtml(r.Fecha || '')}', '${escapeHtml(r.Cliente || '')}', '${escapeHtml(r.Tipo || '')}')" class="px-2.5 py-1 bg-white hover:bg-slate-50 text-slate-800 font-bold rounded-lg text-xs border border-slate-200 transition-all cursor-pointer" title="Generar informe técnico en PDF de ${escapeHtml(r['Vehículo/Placa'])}">
                <i class="fa-solid fa-file-pdf mr-1"></i>PDF
              </button>
            </td>
          </tr>
        `;
      }).join('');

      actualizarBarraPaginacionDiag(totalRegistros, totalPaginas, inicio, fin);
    }

    function actualizarBarraPaginacionDiag(totalRegistros, totalPaginas, inicio, fin) {
      const contenedor = document.getElementById('contenedorPaginacionDiag');
      const spanInicio = document.getElementById('pagInicioDiag');
      const spanFin = document.getElementById('pagFinDiag');
      const spanTotal = document.getElementById('pagTotalDiag');
      const controles = document.getElementById('controlesPaginacionDiag');

      if (!contenedor || !spanInicio || !spanFin || !spanTotal || !controles) return;

      if (totalRegistros === 0) {
        contenedor.classList.add('hidden');
        return;
      }
      contenedor.classList.remove('hidden');

      spanInicio.textContent = (inicio + 1).toLocaleString();
      spanFin.textContent = fin.toLocaleString();
      spanTotal.textContent = totalRegistros.toLocaleString();

      let html = '';

      // Botón Primero
      const deshabilitarPrimero = paginaActualDiag <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaDiag(1)" ${deshabilitarPrimero ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarPrimero ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Primera página">
          <i class="fa-solid fa-angles-left text-[11px]"></i>
        </button>
      `;

      // Botón Anterior
      const deshabilitarAnt = paginaActualDiag <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaDiag(${paginaActualDiag - 1})" ${deshabilitarAnt ? 'disabled' : ''}
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
        let start = Math.max(2, paginaActualDiag - 1);
        let end = Math.min(totalPaginas - 1, paginaActualDiag + 1);

        if (paginaActualDiag <= 3) {
          end = 4;
        } else if (paginaActualDiag >= totalPaginas - 2) {
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
        } else if (p === paginaActualDiag) {
          html += `
            <button type="button" class="w-8 h-8 rounded-xl bg-blue-600 text-white font-black text-xs shadow-sm flex items-center justify-center cursor-default">
              ${p}
            </button>
          `;
        } else {
          html += `
            <button type="button" onclick="cambiarPaginaDiag(${p})" class="w-8 h-8 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900 font-bold text-xs shadow-xs transition-all flex items-center justify-center cursor-pointer active:scale-95">
              ${p}
            </button>
          `;
        }
      });

      // Botón Siguiente
      const deshabilitarSig = paginaActualDiag >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaDiag(${paginaActualDiag + 1})" ${deshabilitarSig ? 'disabled' : ''}
          class="inline-flex items-center space-x-1 px-2.5 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all ${
            deshabilitarSig ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Página siguiente">
          <span class="hidden sm:inline">Sig</span>
          <i class="fa-solid fa-chevron-right text-[11px]"></i>
        </button>
      `;

      // Botón Último
      const deshabilitarUltimo = paginaActualDiag >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaDiag(${totalPaginas})" ${deshabilitarUltimo ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarUltimo ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Última página">
          <i class="fa-solid fa-angles-right text-[11px]"></i>
        </button>
      `;

      controles.innerHTML = html;
    }

    let paginaActualMatriz = 1;
    const ITEMS_POR_PAGINA_MATRIZ = 25;
    let cacheFiltradasMatriz = [];

    function renderizarMatrizSemaforos(cli, sede, op, placa) {
      const thead = getDiagEl('thead_semaforo_matriz_flota', 'theadMatrizSemaforos');
      const tbody = getDiagEl('tbody_semaforo_matriz_flota', 'tbodyMatrizSemaforos');
      const tfoot = getDiagEl('tfoot_semaforo_matriz_flota', 'tfootMatrizSemaforos');
      const contenedorPaginacion = document.getElementById('contenedorPaginacionMatriz');
      if (!tbody) return;

      // Obtener filas de matriz: sincronizadas desde cacheFiltradasDiag si tiene Llantas_Posiciones, o fallback a cacheMatrizSemaforos
      let filasFiltradas = [];
      const posiciones = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

      if (cacheFiltradasDiag && cacheFiltradasDiag.length > 0 && cacheFiltradasDiag[0].Llantas_Posiciones) {
        filasFiltradas = cacheFiltradasDiag.map(r => {
          const mapPos = {};
          if (Array.isArray(r.Llantas_Posiciones)) {
            r.Llantas_Posiciones.forEach(lp => {
              const semNorm = String(lp.semaforo || '').trim().toLowerCase();
              const col = semNorm === 'verde' ? 'verde' : semNorm === 'amarillo' ? 'amarillo' : semNorm === 'rojo' ? 'rojo' : 'gris';
              mapPos[lp.posicion] = {
                color: col,
                pb: lp.prof_min !== undefined ? lp.prof_min : 0.0,
                numero_interno: lp.numero_interno || '',
                psi: lp.psi,
                dimension: lp.dimension,
                eje: lp.posicion <= 2 ? 'Direccional' : 'Tracción/Arrastre',
                limite: r.Limite_Retiro_mm || 3.0
              };
            });
          } else if (typeof r.Llantas_Posiciones === 'object') {
            Object.assign(mapPos, r.Llantas_Posiciones);
          }
          return {
            placa: r['Vehículo/Placa'],
            cliente: r.Cliente,
            subcliente: r.Subcliente,
            tipologia: r.Tipo,
            limite: r.Limite_Retiro_mm || 3.0,
            posiciones: mapPos
          };
        });
      } else if (cacheMatrizSemaforos && cacheMatrizSemaforos.filas) {
        const cliNorm = String(cli || 'Todos').trim().toUpperCase();
        const sedeNorm = String(sede || 'Todos').trim().toUpperCase();
        const opNorm = String(op || 'Todos').trim().toUpperCase();
        const placaNorm = String(placa || '').trim().toLowerCase();

        filasFiltradas = cacheMatrizSemaforos.filas.filter(r => {
          if (cliNorm !== 'TODOS' && String(r.cliente || '').trim().toUpperCase() !== cliNorm) return false;
          if (sedeNorm !== 'TODOS' && String(r.subcliente || '').trim().toUpperCase() !== sedeNorm) return false;
          if (opNorm !== 'TODOS' && String(r.tipo_operacion || '').trim().toUpperCase() !== opNorm) return false;
          if (placaNorm && !String(r.placa || '').toLowerCase().includes(placaNorm)) return false;
          return true;
        });
      }

      cacheFiltradasMatriz = filasFiltradas;

      // Encabezado estándar de la matriz de semáforos
      if (thead) {
        thead.innerHTML = `
          <tr>
            <th class="p-2.5 text-left font-bold sticky left-0 z-30 bg-slate-900 min-w-[95px] shadow-sm">Placa</th>
            <th class="p-2.5 text-left font-bold min-w-[130px]">Cliente / Sede</th>
            <th class="p-2.5 text-left font-bold min-w-[110px]">Tipología</th>
            <th class="p-2.5 text-center font-bold min-w-[75px]">Límite</th>
            ${posiciones.map(p => `<th class="p-2 text-center font-black min-w-[55px] border-l border-slate-800" title="Posición ${p}">P${p}</th>`).join('')}
            <th class="p-2.5 text-center font-bold min-w-[95px] border-l border-slate-800">🔴/🟡/🟢</th>
          </tr>
        `;
      }

      if (filasFiltradas.length === 0) {
        tbody.innerHTML = `<tr><td colspan="17" class="p-8 text-center text-slate-400 font-medium">No se encontraron vehículos que coincidan con los filtros aplicados.</td></tr>`;
        if (tfoot) tfoot.innerHTML = '';
        if (contenedorPaginacion) contenedorPaginacion.classList.add('hidden');
        return;
      }

      // Cálculos globales sobre TODAS las filas filtradas
      const posTotales = {};
      posiciones.forEach(p => {
        posTotales[p] = { rojo: 0, amarillo: 0, verde: 0, gris: 0, total: 0 };
      });
      const globalTot = { rojo: 0, amarillo: 0, verde: 0, gris: 0 };

      filasFiltradas.forEach(r => {
        posiciones.forEach(p => {
          const cel = r.posiciones ? (r.posiciones[p] || r.posiciones[String(p)]) : null;
          if (cel) {
            const col = cel.color;
            if (col === 'rojo') { posTotales[p].rojo++; globalTot.rojo++; }
            else if (col === 'amarillo') { posTotales[p].amarillo++; globalTot.amarillo++; }
            else if (col === 'verde') { posTotales[p].verde++; globalTot.verde++; }
            else { posTotales[p].gris++; globalTot.gris++; }
            posTotales[p].total++;
          }
        });
      });

      // Paginación de 25 vehículos por página
      const totalRegistros = filasFiltradas.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_MATRIZ) || 1;
      if (paginaActualMatriz > totalPaginas) paginaActualMatriz = totalPaginas;
      if (paginaActualMatriz < 1) paginaActualMatriz = 1;

      const inicio = (paginaActualMatriz - 1) * ITEMS_POR_PAGINA_MATRIZ;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_MATRIZ, totalRegistros);
      const paginaItems = filasFiltradas.slice(inicio, fin);

      tbody.innerHTML = paginaItems.map(r => {
        let cRojo = 0, cAmar = 0, cVerde = 0;
        const celdasPos = posiciones.map(p => {
          const cel = r.posiciones ? (r.posiciones[p] || r.posiciones[String(p)]) : null;
          if (!cel) {
            return '<td class="p-1.5 text-center text-slate-300 font-mono border-l border-slate-100">-</td>';
          }
          const pb = cel.pb !== undefined ? cel.pb : (cel.p_min !== undefined ? cel.p_min : 0.0);
          const col = cel.color;
          if (col === 'rojo') cRojo++;
          else if (col === 'amarillo') cAmar++;
          else if (col === 'verde') cVerde++;

          let badgeClass = '';
          let dotColor = '';
          if (col === 'rojo') {
            badgeClass = 'bg-rose-100 text-rose-800 border-rose-300 font-black';
            dotColor = 'bg-rose-600 animate-pulse';
          } else if (col === 'amarillo') {
            badgeClass = 'bg-amber-100 text-amber-800 border-amber-300 font-bold';
            dotColor = 'bg-amber-500';
          } else if (col === 'verde') {
            badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-300 font-bold';
            dotColor = 'bg-emerald-500';
          } else {
            badgeClass = 'bg-slate-100 text-slate-500 border-slate-200 font-medium';
            dotColor = 'bg-slate-400';
          }

          const valTxt = pb > 0 ? fmtDec(pb, 1) : '0,0';
          const numInterno = cel.numero_interno || cel.serie || '';
          const lim = cel.limite !== undefined ? cel.limite : (r.limite || 3.0);
          const tooltip = `Pos P${p} (${cel.eje || 'Eje'}) | PB: ${valTxt} mm | Límite: ${lim} mm | ${cel.estado || ''} ${cel.accion ? '- ' + cel.accion : ''} ${cel.marca ? '| ' + cel.marca : ''} ${numInterno ? '| #' + numInterno : ''} ${cel.psi ? '| ' + cel.psi + ' PSI' : ''}`.trim();

          return `
            <td class="p-1 text-center border-l border-slate-100" title="${tooltip}">
              <div class="inline-flex flex-col items-center justify-center">
                <span class="inline-flex items-center justify-center space-x-1 px-1.5 py-0.5 rounded-md border text-[11px] font-mono ${badgeClass} cursor-help shadow-2xs">
                  <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
                  <span>${valTxt}</span>
                </span>
                ${numInterno ? `<span class="text-[9px] text-slate-400 font-mono truncate max-w-[50px] leading-tight" title="Serial/Interno: ${numInterno}">#${numInterno}</span>` : ''}
              </div>
            </td>
          `;
        }).join('');

        const subClienteTxt = r.subcliente ? `<br><span class="text-[10px] text-slate-400 font-normal">${escapeHtml(r.subcliente)}</span>` : '';
        const tipoTxt = r.tipologia ? `<span class="truncate block max-w-[110px]" title="${escapeHtml(r.tipologia)}">${escapeHtml(r.tipologia)}</span>` : '-';
        const limTxt = (r.limite ? fmtDec(Number(r.limite), 1) : '3,0') + ' mm';

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-2.5 font-black text-slate-900 sticky left-0 z-10 bg-white border-r border-slate-100 text-left shadow-2xs">${escapeHtml(r.placa)}</td>
            <td class="p-2.5 text-left font-bold text-slate-700">${escapeHtml(r.cliente || '-')}${subClienteTxt}</td>
            <td class="p-2.5 text-left text-slate-600 text-[11px]">${tipoTxt}</td>
            <td class="p-2 text-center font-mono font-bold text-slate-600">${limTxt}</td>
            ${celdasPos}
            <td class="p-2 text-center border-l border-slate-100 font-mono text-xs whitespace-nowrap">
              <span class="text-rose-700 font-black">${cRojo}</span> /
              <span class="text-amber-700 font-bold">${cAmar}</span> /
              <span class="text-emerald-700 font-bold">${cVerde}</span>
            </td>
          </tr>
        `;
      }).join('');

      if (tfoot) {
        tfoot.innerHTML = `
          <tr class="bg-slate-100 text-slate-800 border-t-2 border-slate-300">
            <td class="p-2.5 text-left font-black sticky left-0 z-10 bg-slate-100 shadow-2xs">TOTALES FLOTA</td>
            <td class="p-2.5 text-left text-[11px] text-slate-500 font-bold">${filasFiltradas.length} Vehículos</td>
            <td class="p-2.5 text-left text-[10px] text-slate-500 font-bold">🔴/🟡/🟢</td>
            <td class="p-2 text-center text-slate-400 font-mono">-</td>
            ${posiciones.map(p => {
              const t = posTotales[p];
              return `
                <td class="p-1.5 text-center border-l border-slate-200 font-mono text-[10px] whitespace-nowrap" title="Totales Pos P${p}: ${escapeHtml(t.rojo)} Retiro Urgente, ${escapeHtml(t.amarillo)} Próxima a Cambio, ${escapeHtml(t.verde)} Óptima">
                  <span class="text-rose-700 font-black">${escapeHtml(t.rojo)}</span>/<span class="text-amber-700 font-bold">${escapeHtml(t.amarillo)}</span>/<span class="text-emerald-700 font-bold">${escapeHtml(t.verde)}</span>
                </td>
              `;
            }).join('')}
            <td class="p-2 text-center border-l border-slate-200 font-mono font-black text-xs whitespace-nowrap">
              <span class="text-rose-700">${globalTot.rojo}</span> /
              <span class="text-amber-700">${globalTot.amarillo}</span> /
              <span class="text-emerald-700">${globalTot.verde}</span>
            </td>
          </tr>
        `;
      }

      actualizarBarraPaginacionMatriz(totalRegistros, inicio, fin);
    }

    function cambiarPaginaMatriz(nuevaPagina) {
      const totalRegistros = cacheFiltradasMatriz ? cacheFiltradasMatriz.length : 0;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_MATRIZ) || 1;
      if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
      paginaActualMatriz = nuevaPagina;
      
      const cli = getDiagVal('filtro_diag_cliente', 'filtroDiagCliente');
      const sede = getDiagVal('filtro_diag_subcliente', 'filtroDiagSede');
      const op = getDiagVal('filtro_diag_operacion', 'filtroDiagOperacion');
      const placa = getDiagVal('filtro_diag_busqueda', 'filtroDiagPlaca');
      renderizarMatrizSemaforos(cli, sede, op, placa);

      const contTabla = document.querySelector('#contenedorMatrizSemaforosFlota');
      if (contTabla) contTabla.scrollTop = 0;
    }

    function actualizarBarraPaginacionMatriz(totalRegistros, inicio, fin) {
      const contenedor = document.getElementById('contenedorPaginacionMatriz');
      const lblInicio = document.getElementById('pagInicioMatriz');
      const lblFin = document.getElementById('pagFinMatriz');
      const lblTotal = document.getElementById('pagTotalMatriz');
      const controles = document.getElementById('controlesPaginacionMatriz');

      if (!contenedor || !controles) return;
      if (totalRegistros === 0) {
        contenedor.classList.add('hidden');
        return;
      }

      contenedor.classList.remove('hidden');
      if (lblInicio) lblInicio.textContent = (inicio + 1).toLocaleString();
      if (lblFin) lblFin.textContent = fin.toLocaleString();
      if (lblTotal) lblTotal.textContent = totalRegistros.toLocaleString();

      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_MATRIZ) || 1;

      let html = '';

      // Botón Primero
      const deshabilitarPrimero = paginaActualMatriz <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaMatriz(1)" ${deshabilitarPrimero ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarPrimero ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Primera página">
          <i class="fa-solid fa-angles-left text-[11px]"></i>
        </button>
      `;

      // Botón Anterior
      const deshabilitarAnt = paginaActualMatriz <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaMatriz(${paginaActualMatriz - 1})" ${deshabilitarAnt ? 'disabled' : ''}
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
        let start = Math.max(2, paginaActualMatriz - 1);
        let end = Math.min(totalPaginas - 1, paginaActualMatriz + 1);

        if (paginaActualMatriz <= 3) {
          end = 4;
        } else if (paginaActualMatriz >= totalPaginas - 2) {
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
        } else if (p === paginaActualMatriz) {
          html += `
            <button type="button" class="w-8 h-8 rounded-xl bg-blue-600 text-white font-black text-xs shadow-sm flex items-center justify-center cursor-default">
              ${p}
            </button>
          `;
        } else {
          html += `
            <button type="button" onclick="cambiarPaginaMatriz(${p})" class="w-8 h-8 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900 font-bold text-xs shadow-xs transition-all flex items-center justify-center cursor-pointer active:scale-95">
              ${p}
            </button>
          `;
        }
      });

      // Botón Siguiente
      const deshabilitarSig = paginaActualMatriz >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaMatriz(${paginaActualMatriz + 1})" ${deshabilitarSig ? 'disabled' : ''}
          class="inline-flex items-center space-x-1 px-2.5 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all ${
            deshabilitarSig ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Página siguiente">
          <span class="hidden sm:inline">Sig</span>
          <i class="fa-solid fa-chevron-right text-[11px]"></i>
        </button>
      `;

      // Botón Último
      const deshabilitarUltimo = paginaActualMatriz >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaMatriz(${totalPaginas})" ${deshabilitarUltimo ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarUltimo ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Última página">
          <i class="fa-solid fa-angles-right text-[11px]"></i>
        </button>
      `;

      controles.innerHTML = html;
    }

    function limpiarFiltrosDiagnostico() {
      const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
      setVal('filtro_diag_cliente', 'Todos');
      setVal('filtroDiagCliente', 'Todos');
      actualizarCombosSedesDiagnostico();
      setVal('filtro_diag_subcliente', 'Todos');
      setVal('filtroDiagSede', 'Todos');
      setVal('filtro_diag_operacion', 'Todos');
      setVal('filtroDiagOperacion', 'Todos');
      setVal('filtro_diag_fecha_desde', '');
      setVal('filtroDiagFechaDesde', '');
      setVal('filtro_diag_fecha_hasta', '');
      setVal('filtroDiagFechaHasta', '');
      setVal('filtro_diag_accion', 'Todos');
      setVal('filtroDiagAlerta', 'Todos');
      setVal('filtro_diag_busqueda', '');
      setVal('filtroDiagPlaca', '');
      cargarDiagnostico();
      if (typeof mostrarToast === 'function') mostrarToast('Filtros de diagnóstico restablecidos.');
    }

    function exportarDiagnosticoExcel() {
      const cli = getDiagVal('filtro_diag_cliente', 'filtroDiagCliente', 'Todos');
      const sede = getDiagVal('filtro_diag_subcliente', 'filtroDiagSede', 'Todos');
      const op = getDiagVal('filtro_diag_operacion', 'filtroDiagOperacion', 'Todos');
      const accion = getDiagVal('filtro_diag_accion', 'filtroDiagAlerta', 'Todos');
      const busqueda = getDiagVal('filtro_diag_busqueda', 'filtroDiagPlaca', '').trim();
      const fDesde = getDiagVal('filtro_diag_fecha_desde', 'filtroDiagFechaDesde', '').trim();
      const fHasta = getDiagVal('filtro_diag_fecha_hasta', 'filtroDiagFechaHasta', '').trim();

      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));

      const params = new URLSearchParams();
      if (tok) params.append('token', tok);
      if (cli && cli !== 'Todos') params.append('cliente', cli);
      if (sede && sede !== 'Todos') params.append('subcliente', sede);
      if (op && op !== 'Todos') params.append('tipo_operacion', op);
      if (accion && accion !== 'Todos') params.append('alerta', accion);
      if (busqueda) params.append('placa', busqueda);
      if (fDesde) params.append('fecha_desde', fDesde);
      if (fHasta) params.append('fecha_hasta', fHasta);

      const btn = document.getElementById('btnExportarDiagExcel');
      const lbl = document.getElementById('lblExportarDiagExcel');
      const origText = lbl ? lbl.innerHTML : 'Exportar Diagnóstico';

      if (lbl) {
        lbl.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin mr-1"></i>Generando...`;
      }
      if (btn) btn.disabled = true;

      const descFiltro = (cli !== 'Todos' || sede !== 'Todos' || op !== 'Todos' || accion !== 'Todos' || busqueda || fDesde || fHasta)
        ? 'con los filtros seleccionados'
        : 'de toda la flota';

      if (typeof mostrarToast === 'function') {
        mostrarToast(`Generando archivo Excel ${descFiltro}...`, 'info');
      }

      window.location.href = `/api/diagnostico/exportar-excel?${params.toString()}`;

      setTimeout(() => {
        if (lbl) lbl.innerHTML = origText;
        if (btn) btn.disabled = false;
      }, 3000);
    }

