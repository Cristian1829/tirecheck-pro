    // ==========================================
    // VISTA 2: BASE DE INSPECCIONES (CRUD, FILTROS & EXCEL)
    // ==========================================
    let bdFiltrosPoblados = false;

    async function cargarBaseInspecciones() {
      const tbody = document.getElementById('tbodyInspecciones');
      if (tbody && (!cacheTodasInspecciones || cacheTodasInspecciones.length === 0)) {
        tbody.innerHTML = '<tr><td colspan="25" class="p-8 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2 text-blue-600"></i>Cargando base de inspecciones...</td></tr>';
      }
      try {
        const res = await fetch('/api/inspecciones');
        if (res.ok) {
          cacheTodasInspecciones = await res.json();
          const bTotal = document.getElementById('badgeTotalInspecciones');
          if (bTotal) bTotal.textContent = cacheTodasInspecciones.length;
          const lTotal = document.getElementById('lblTotalBD');
          if (lTotal) lTotal.textContent = cacheTodasInspecciones.length;
          poblarSelectoresFiltroBD(cacheTodasInspecciones);
          filtrarTablaBD();
        } else if (res.status === 401) {
          if (tbody) {
            tbody.innerHTML = '<tr><td colspan="25" class="p-8 text-center text-amber-600 font-bold"><i class="fa-solid fa-lock mr-2"></i>Sesión no iniciada o expirada. <button onclick="document.getElementById(\x27modalLogin\x27).classList.remove(\x27hidden\x27)" class="ml-2 px-3 py-1 bg-blue-600 text-white text-xs rounded-lg shadow">Iniciar Sesión</button></td></tr>';
          }
        } else {
          if (tbody) {
            tbody.innerHTML = `<tr><td colspan="25" class="p-8 text-center text-rose-500 font-bold"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Error al consultar el servidor (HTTP ${res.status}). <button onclick="cargarBaseInspecciones()" class="ml-2 px-3 py-1 bg-blue-600 text-white text-xs rounded-lg shadow">Reintentar</button></td></tr>`;
          }
        }
      } catch (e) {
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="25" class="p-8 text-center text-rose-500 font-bold"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Error de conexión o tiempo de espera agotado. <button onclick="cargarBaseInspecciones()" class="ml-2 px-3 py-1 bg-blue-600 text-white text-xs rounded-lg shadow">Reintentar</button></td></tr>';
        }
        mostrarToast('Error al cargar inspecciones desde el servidor', true);
      }
    }

    function poblarSelectoresFiltroBD(data) {
      if (!Array.isArray(data)) return;

      const selCli = document.getElementById('filtroBDCliente');
      const selOp = document.getElementById('filtroBDOperacion');
      const selTip = document.getElementById('filtroBDTipologia');
      const selMar = document.getElementById('filtroBDMarca');

      if (!selCli || !selOp || !selTip || !selMar) return;

      // Guardar selecciones actuales
      const valCli = selCli.value || 'TODOS';
      const valOp = selOp.value || 'TODOS';
      const valTip = selTip.value || 'TODOS';
      const valMar = selMar.value || 'TODOS';

      // Extraer valores únicos no vacíos
      const clientes = Array.from(new Set(data.map(r => (r.cliente || '').trim()).filter(Boolean))).sort();
      const operaciones = Array.from(new Set(data.map(r => (r.tipo_operacion || '').trim()).filter(Boolean))).sort();
      const tipologias = Array.from(new Set(data.map(r => (r.tipologia || '').trim()).filter(Boolean))).sort();
      const marcas = Array.from(new Set(data.map(r => (r.marca || '').trim()).filter(Boolean))).sort();

      selCli.innerHTML = '<option value="TODOS">Todos los Clientes</option>' + clientes.map(c => `<option value="${c}">${c}</option>`).join('');
      selOp.innerHTML = '<option value="TODOS">Todas las Operaciones</option>' + operaciones.map(o => `<option value="${o}">${o}</option>`).join('');
      selTip.innerHTML = '<option value="TODOS">Todas las Tipologías</option>' + tipologias.map(t => `<option value="${t}">${t}</option>`).join('');
      selMar.innerHTML = '<option value="TODOS">Todas las Marcas</option>' + marcas.map(m => `<option value="${m}">${m}</option>`).join('');

      // Restaurar si aún existen
      if (clientes.includes(valCli)) selCli.value = valCli;
      if (operaciones.includes(valOp)) selOp.value = valOp;
      if (tipologias.includes(valTip)) selTip.value = valTip;
      if (marcas.includes(valMar)) selMar.value = valMar;

      actualizarCombosSedesBD();
    }

    function actualizarCombosSedesBD() {
      const selCli = document.getElementById('filtroBDCliente');
      const selSede = document.getElementById('filtroBDSede');
      if (!selSede) return;

      const valCli = selCli ? (selCli.value || 'TODOS') : 'TODOS';
      const valSedeActual = selSede.value || 'TODOS';

      const sedes = Array.from(new Set(
        cacheTodasInspecciones
          .filter(r => (valCli === 'TODOS' || (r.cliente || '').toLowerCase() === valCli.toLowerCase()))
          .map(r => (r.subcliente || '').trim())
          .filter(Boolean)
      )).sort();

      selSede.innerHTML = '<option value="TODOS">Todas las Sedes</option>' +
        sedes.map(s => `<option value="${s}">${s}</option>`).join('');

      if (sedes.some(s => s.toLowerCase() === valSedeActual.toLowerCase())) {
        selSede.value = valSedeActual;
      } else {
        selSede.value = 'TODOS';
      }
    }

    function onCambioFiltroBDCliente() {
      actualizarCombosSedesBD();
      filtrarTablaBD();
    }

    let paginaActualBD = 1;
    const ITEMS_POR_PAGINA_BD = 25;
    let cacheFiltradasBD = [];

    function filtrarTablaBD() {
      paginaActualBD = 1;
      aplicarFiltrosYRenderizarBD();
    }

    function cambiarPaginaBD(nuevaPagina) {
      const totalPaginas = Math.ceil(cacheFiltradasBD.length / ITEMS_POR_PAGINA_BD) || 1;
      if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
      paginaActualBD = nuevaPagina;
      renderizarTablaBD();
      const contTabla = document.querySelector('#vista-basedatos .overflow-x-auto');
      if (contTabla) contTabla.scrollTop = 0;
    }

    function aplicarFiltrosYRenderizarBD() {
      const tbody = document.getElementById('tbodyInspecciones');
      if (!tbody) return;

      const q = (document.getElementById('filtroTextoBD')?.value || '').trim().toLowerCase();
      const fDesde = document.getElementById('filtroBDFechaDesde')?.value || '';
      const fHasta = document.getElementById('filtroBDFechaHasta')?.value || '';
      const cli = document.getElementById('filtroBDCliente')?.value || 'TODOS';
      const sede = document.getElementById('filtroBDSede')?.value || 'TODOS';
      const op = document.getElementById('filtroBDOperacion')?.value || 'TODOS';
      const tip = document.getElementById('filtroBDTipologia')?.value || 'TODOS';
      const marca = document.getElementById('filtroBDMarca')?.value || 'TODOS';
      const vida = document.getElementById('filtroBDVida')?.value || 'TODOS';
      const semaforo = document.getElementById('filtroBDSemaforo')?.value || 'TODOS';

      // Conteo de filtros activos
      let filtrosActivos = 0;
      if (q) filtrosActivos++;
      if (fDesde) filtrosActivos++;
      if (fHasta) filtrosActivos++;
      if (cli !== 'TODOS') filtrosActivos++;
      if (sede !== 'TODOS') filtrosActivos++;
      if (op !== 'TODOS') filtrosActivos++;
      if (tip !== 'TODOS') filtrosActivos++;
      if (marca !== 'TODOS') filtrosActivos++;
      if (vida !== 'TODOS') filtrosActivos++;
      if (semaforo !== 'TODOS') filtrosActivos++;

      const badgeFiltros = document.getElementById('badgeFiltrosActivosBD');
      if (badgeFiltros) {
        if (filtrosActivos > 0) {
          badgeFiltros.textContent = `${filtrosActivos} filtro${filtrosActivos > 1 ? 's' : ''} activo${filtrosActivos > 1 ? 's' : ''}`;
          badgeFiltros.classList.remove('hidden');
        } else {
          badgeFiltros.classList.add('hidden');
        }
      }

      cacheFiltradasBD = cacheTodasInspecciones.filter(r => {
        // 1. Filtro Texto Libre
        if (q) {
          const matchTexto = (r.placa || '').toLowerCase().includes(q) ||
                             (r.cliente || '').toLowerCase().includes(q) ||
                             (r.subcliente || '').toLowerCase().includes(q) ||
                             (r.numero_interno || '').toLowerCase().includes(q) ||
                             (r.marca || '').toLowerCase().includes(q) ||
                             (r.diseno || '').toLowerCase().includes(q) ||
                             (r.dimension || '').toLowerCase().includes(q) ||
                             (r.novedades || '').toLowerCase().includes(q) ||
                             (r.usuario_registro || '').toLowerCase().includes(q);
          if (!matchTexto) return false;
        }

        // 2. Rango de Fechas
        if (fDesde && r.fecha && r.fecha < fDesde) return false;
        if (fHasta && r.fecha && r.fecha > fHasta) return false;

        // 3. Cliente
        if (cli !== 'TODOS' && (r.cliente || '').toLowerCase() !== cli.toLowerCase()) return false;

        // 3.1 Sede (subcliente)
        if (sede !== 'TODOS' && (r.subcliente || '').toLowerCase() !== sede.toLowerCase()) return false;

        // 4. Operación
        if (op !== 'TODOS' && (r.tipo_operacion || '').toLowerCase() !== op.toLowerCase()) return false;

        // 5. Tipología
        if (tip !== 'TODOS' && (r.tipologia || '').toLowerCase() !== tip.toLowerCase()) return false;

        // 6. Marca
        if (marca !== 'TODOS' && (r.marca || '').toLowerCase() !== marca.toLowerCase()) return false;

        // 7. Condición / Vida
        if (vida !== 'TODOS') {
          const vNorm = (r.vida || '').toLowerCase();
          if (!vNorm.includes(vida.toLowerCase())) return false;
        }

        // 8. Semáforo / Desgaste & Presión
        if (semaforo !== 'TODOS') {
          const pExt = parseFloat(r.prof_ext) || 0;
          const pCent = parseFloat(r.prof_cent) || 0;
          const pInt = parseFloat(r.prof_int) || 0;
          const profValidas = [pExt, pCent, pInt].filter(p => p > 0);
          const minP = profValidas.length > 0 ? Math.min(...profValidas) : 0;
          const psiVal = parseFloat(r.psi) || 0;

          if (semaforo === 'CRITICO' && !(minP > 0 && minP <= 3.0)) return false;
          if (semaforo === 'ALERTA' && !(minP > 3.0 && minP <= 5.0)) return false;
          if (semaforo === 'OPTIMO' && !(minP > 5.0)) return false;
          if (semaforo === 'PSI_ANORMAL' && (psiVal >= 90 && psiVal <= 120)) return false;
        }

        return true;
      });

      document.getElementById('lblConteoBD').textContent = cacheFiltradasBD.length;
      document.getElementById('lblTotalBD').textContent = cacheTodasInspecciones.length;

      renderizarTablaBD();
    }

    function renderizarTablaBD() {
      const tbody = document.getElementById('tbodyInspecciones');
      const contenedorPaginacion = document.getElementById('contenedorPaginacionBD');
      if (!tbody) return;

      if (!cacheFiltradasBD || cacheFiltradasBD.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="25" class="p-12 text-center text-slate-400">
              <div class="flex flex-col items-center justify-center space-y-2">
                <i class="fa-solid fa-filter-circle-xmark text-3xl text-slate-300"></i>
                <span class="font-bold text-slate-600">No se encontraron inspecciones con los filtros seleccionados</span>
                <span class="text-xs text-slate-400">Intenta cambiar los términos de búsqueda o restablecer los filtros</span>
                <button type="button" onclick="limpiarFiltrosBD()" class="mt-2 px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 font-bold text-xs rounded-xl border border-blue-200 transition-all">
                  Restablecer Filtros
                </button>
              </div>
            </td>
          </tr>
        `;
        if (contenedorPaginacion) contenedorPaginacion.classList.add('hidden');
        return;
      }

      // Cálculo de Paginación de 25 resultados
      const totalRegistros = cacheFiltradasBD.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_BD) || 1;
      if (paginaActualBD > totalPaginas) paginaActualBD = totalPaginas;
      if (paginaActualBD < 1) paginaActualBD = 1;

      const inicio = (paginaActualBD - 1) * ITEMS_POR_PAGINA_BD;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_BD, totalRegistros);
      const paginaItems = cacheFiltradasBD.slice(inicio, fin);

      tbody.innerHTML = paginaItems.map(r => {
        const pExt = parseFloat(r.prof_ext) || 0;
        const pCent = parseFloat(r.prof_cent) || 0;
        const pInt = parseFloat(r.prof_int) || 0;
        const profValidas = [pExt, pCent, pInt].filter(p => p > 0);
        const minP = profValidas.length > 0 ? Math.min(...profValidas) : 0;
        
        let colorDesgaste = 'text-slate-700 font-medium';
        let badgeAlerta = '';
        if (minP > 0 && minP <= 3.0) {
          colorDesgaste = 'text-rose-600 font-black';
          badgeAlerta = '<span class="ml-1 px-1.5 py-0.5 rounded text-[9px] font-black bg-rose-100 text-rose-800">RETIRO</span>';
        } else if (minP > 3.0 && minP <= 5.0) {
          colorDesgaste = 'text-amber-600 font-bold';
        }

        const fotos = obtenerListaFotos(r.foto_novedad);
        const tieneFotos = fotos.length > 0;
        const htmlBotonFotos = tieneFotos ? `
          <button type="button" onclick="abrirGaleriaFotosPorId(${r.id})" class="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-blue-50 hover:bg-blue-100 active:scale-95 text-blue-700 font-bold text-xs border border-blue-200 transition-all shadow-xs cursor-pointer" title="Clic para ver ${fotos.length} foto(s) de evidencia de forma ordenada">
            <i class="fa-solid fa-camera text-blue-600 text-[11px]"></i>
            <span>Ver foto${fotos.length > 1 ? 's' : ''} (${fotos.length})</span>
          </button>
        ` : `<span class="text-slate-300 font-medium text-xs">Sin fotos</span>`;

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-2.5 text-center font-bold text-slate-400">${r.id}</td>
            <td class="p-2.5 text-center whitespace-nowrap">
              ${tieneFotos ? `
                <button type="button" onclick="abrirGaleriaFotosPorId(${r.id})" class="px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold rounded-lg mr-1 text-xs transition-colors cursor-pointer" title="Ver evidencias fotográficas">
                  <i class="fa-solid fa-camera"></i>
                </button>
              ` : ''}
              ${esAdminOJefatura() ? `
                <button type="button" onclick="abrirModalEditarInspeccion(${r.id})" class="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold rounded-lg mr-1 text-xs transition-colors cursor-pointer" title="Editar Fila">
                  <i class="fa-solid fa-pen-to-square"></i>
                </button>
                <button type="button" onclick="eliminarInspeccion(${r.id}, '${r.placa}', ${r.posicion})" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold rounded-lg text-xs transition-colors cursor-pointer" title="Eliminar Fila">
                  <i class="fa-solid fa-trash"></i>
                </button>
              ` : ''}
            </td>
            <td class="p-2.5 font-mono text-slate-600">${r.fecha || '-'}</td>
            <td class="p-2.5 font-bold text-slate-900">${r.cliente || '-'}</td>
            <td class="p-2.5 text-slate-500">${r.subcliente || '-'}</td>
            <td class="p-2.5">${r.tipo_operacion || '-'}</td>
            <td class="p-2.5 font-black text-blue-700 font-mono tracking-wide">${r.placa || '-'}</td>
            <td class="p-2.5 font-bold text-slate-800">${r.numero_interno || '-'}</td>
            <td class="p-2.5 text-center font-black">
              <span class="w-6 h-6 inline-flex items-center justify-center rounded-lg bg-slate-100 text-slate-800 font-mono text-xs">
                ${r.posicion}
              </span>
            </td>
            <td class="p-2.5 text-right font-mono">${(r.kilometraje || 0).toLocaleString()}</td>
            <td class="p-2.5">${r.tipologia || '-'}</td>
            <td class="p-2.5 font-bold text-slate-800">${r.marca || '-'}</td>
            <td class="p-2.5">${r.diseno || '-'}</td>
            <td class="p-2.5 font-mono text-[11px]">${r.dimension || '-'}</td>
            <td class="p-2.5">
              <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${
                (r.vida || '').toLowerCase().includes('reen') || (r.banda_reen && r.banda_reen !== '-') 
                  ? 'bg-purple-50 text-purple-700' 
                  : 'bg-blue-50 text-blue-700'
              }">
                ${(r.vida && r.vida !== '-') ? r.vida : (r.banda_reen && r.banda_reen !== '-' ? 'REENCAUCHE' : 'ORIGINAL')}
              </span>
            </td>
            <td class="p-2.5 text-slate-500">${r.banda_reen || '-'}</td>
            <td class="p-2.5 text-center font-mono ${colorDesgaste}">${r.prof_ext}</td>
            <td class="p-2.5 text-center font-mono ${colorDesgaste}">${r.prof_cent}</td>
            <td class="p-2.5 text-center font-mono ${colorDesgaste}">${r.prof_int}${badgeAlerta}</td>
            <td class="p-2.5 text-center font-mono font-bold ${
              (parseFloat(r.psi) < 90 || parseFloat(r.psi) > 120) ? 'text-amber-600 bg-amber-50/60 rounded' : 'text-slate-700'
            }">${r.psi}</td>
            <td class="p-2.5 max-w-xs truncate" title="${escapeHtml(r.novedades || '')}">
              ${escapeHtml(r.novedades) || '-'}
            </td>
            <td class="p-2.5 text-center whitespace-nowrap">
              ${htmlBotonFotos}
            </td>
            <td class="p-2.5 text-right font-mono text-slate-600">$${(r.precio || 0).toLocaleString()}</td>
            <td class="p-2.5 text-center font-mono text-slate-400">${r.prof_inicial || 0}</td>
            <td class="p-2.5 text-right font-mono text-slate-400">${(r.km_montaje || 0).toLocaleString()}</td>
          </tr>
        `;
      }).join('');

      actualizarBarraPaginacionBD(totalRegistros, totalPaginas, inicio, fin);
    }

    function actualizarBarraPaginacionBD(totalRegistros, totalPaginas, inicio, fin) {
      const contenedor = document.getElementById('contenedorPaginacionBD');
      const spanInicio = document.getElementById('pagInicioBD');
      const spanFin = document.getElementById('pagFinBD');
      const spanTotal = document.getElementById('pagTotalBD');
      const controles = document.getElementById('controlesPaginacionBD');

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
      const deshabilitarPrimero = paginaActualBD <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaBD(1)" ${deshabilitarPrimero ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarPrimero ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Primera página">
          <i class="fa-solid fa-angles-left text-[11px]"></i>
        </button>
      `;

      // Botón Anterior
      const deshabilitarAnt = paginaActualBD <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaBD(${paginaActualBD - 1})" ${deshabilitarAnt ? 'disabled' : ''}
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
        let start = Math.max(2, paginaActualBD - 1);
        let end = Math.min(totalPaginas - 1, paginaActualBD + 1);

        if (paginaActualBD <= 3) {
          end = 4;
        } else if (paginaActualBD >= totalPaginas - 2) {
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
        } else if (p === paginaActualBD) {
          html += `
            <button type="button" class="w-8 h-8 rounded-xl bg-blue-600 text-white font-black text-xs shadow-sm flex items-center justify-center cursor-default">
              ${p}
            </button>
          `;
        } else {
          html += `
            <button type="button" onclick="cambiarPaginaBD(${p})" class="w-8 h-8 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900 font-bold text-xs shadow-xs transition-all flex items-center justify-center cursor-pointer active:scale-95">
              ${p}
            </button>
          `;
        }
      });

      // Botón Siguiente
      const deshabilitarSig = paginaActualBD >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaBD(${paginaActualBD + 1})" ${deshabilitarSig ? 'disabled' : ''}
          class="inline-flex items-center space-x-1 px-2.5 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all ${
            deshabilitarSig ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Página siguiente">
          <span class="hidden sm:inline">Sig</span>
          <i class="fa-solid fa-chevron-right text-[11px]"></i>
        </button>
      `;

      // Botón Último
      const deshabilitarUltimo = paginaActualBD >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaBD(${totalPaginas})" ${deshabilitarUltimo ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarUltimo ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Última página">
          <i class="fa-solid fa-angles-right text-[11px]"></i>
        </button>
      `;

      controles.innerHTML = html;
    }

    function limpiarTextoFiltroBD() {
      const input = document.getElementById('filtroTextoBD');
      if (input) {
        input.value = '';
        filtrarTablaBD();
      }
    }

    function limpiarFiltrosBD() {
      const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
      setVal('filtroTextoBD', '');
      setVal('filtroBDFechaDesde', '');
      setVal('filtroBDFechaHasta', '');
      setVal('filtroBDCliente', 'TODOS');
      setVal('filtroBDSede', 'TODOS');
      setVal('filtroBDOperacion', 'TODOS');
      setVal('filtroBDTipologia', 'TODOS');
      setVal('filtroBDMarca', 'TODOS');
      setVal('filtroBDVida', 'TODOS');
      setVal('filtroBDSemaforo', 'TODOS');
      actualizarCombosSedesBD();
      filtrarTablaBD();
      mostrarToast('Filtros de búsqueda restablecidos.');
    }

    async function abrirModalEditarInspeccion(id) {
      try {
        const res = await fetch(`/api/inspecciones/${id}`);
        if (!res.ok) throw new Error('No se pudo obtener el registro');
        const d = await res.json();
        
        document.getElementById('edit_id').value = d.id;
        document.getElementById('lblEditSubtitulo').textContent = `ID: ${d.id} | Vehículo: ${d.placa} | Posición: ${d.posicion}`;
        document.getElementById('edit_fecha').value = d.fecha || '';
        document.getElementById('edit_cliente').value = d.cliente || '';
        document.getElementById('edit_subcliente').value = d.subcliente || '';
        document.getElementById('edit_tipo_operacion').value = d.tipo_operacion || '';
        document.getElementById('edit_placa').value = d.placa || '';
        document.getElementById('edit_posicion').value = d.posicion || 1;
        document.getElementById('edit_numero_interno').value = d.numero_interno || '';
        document.getElementById('edit_kilometraje').value = d.kilometraje || 0;
        document.getElementById('edit_tipologia').value = d.tipologia || '';
        document.getElementById('edit_marca').value = d.marca || '';
        document.getElementById('edit_diseno').value = d.diseno || '';
        document.getElementById('edit_dimension').value = d.dimension || '';
        const vEd = String(d.vida || 'Original').trim();
        const selEditVida = document.getElementById('edit_vida');
        if (selEditVida) {
          selEditVida.value = vEd.toLowerCase().includes('reen') ? 'Reencauche' : 'Original';
        }
        document.getElementById('edit_banda_reen').value = d.banda_reen || '';
        document.getElementById('edit_psi').value = d.psi || 100;
        document.getElementById('edit_prof_ext').value = d.prof_ext || 0;
        document.getElementById('edit_prof_cent').value = d.prof_cent || 0;
        document.getElementById('edit_prof_int').value = d.prof_int || 0;
        document.getElementById('edit_prof_inicial').value = d.prof_inicial || 0;
        document.getElementById('edit_precio').value = d.precio || 0;
        document.getElementById('edit_km_montaje').value = d.km_montaje || 0;
        document.getElementById('edit_novedades').value = d.novedades || '';
        fotosEdicionActuales = obtenerListaFotos(d.foto_novedad);
        actualizarUIFotosEdicion();

        document.getElementById('modalEditarInspeccion').classList.remove('hidden');
        document.getElementById('modalEditarInspeccion').classList.add('flex');
      } catch (e) {
        mostrarToast('Error al cargar datos para edición', true);
      }
    }

    function cerrarModalEditarInspeccion() {
      const m = document.getElementById('modalEditarInspeccion');
      m.classList.add('hidden');
      m.classList.remove('flex');
      fotosEdicionActuales = [];
    }

    async function guardarEdicionInspeccion(e) {
      e.preventDefault();
      const id = document.getElementById('edit_id').value;
      const subVal = (document.getElementById('edit_subcliente')?.value || '').trim();
      if (!subVal) {
        mostrarToast('⚠️ La Sede / Subcliente es un campo obligatorio', true);
        document.getElementById('edit_subcliente')?.focus();
        return;
      }
      const payload = {
        fecha: document.getElementById('edit_fecha').value,
        cliente: document.getElementById('edit_cliente').value,
        subcliente: document.getElementById('edit_subcliente').value,
        tipo_operacion: document.getElementById('edit_tipo_operacion').value,
        placa: document.getElementById('edit_placa').value.trim().toUpperCase(),
        posicion: parseInt(document.getElementById('edit_posicion').value) || 1,
        numero_interno: document.getElementById('edit_numero_interno').value.trim().toUpperCase(),
        tipo_licencia: (typeof clienteLicenciaCaptura !== 'undefined' && clienteLicenciaCaptura) ? clienteLicenciaCaptura : (typeof modoLicenciaGraficos !== 'undefined' ? modoLicenciaGraficos : 'LIGHT'),
        kilometraje: parseFloat(document.getElementById('edit_kilometraje').value) || 0,
        tipologia: document.getElementById('edit_tipologia').value,
        marca: document.getElementById('edit_marca').value,
        diseno: document.getElementById('edit_diseno').value,
        dimension: document.getElementById('edit_dimension').value,
        vida: (document.getElementById('edit_vida')?.value || 'Original').trim() || 'Original',
        banda_reen: document.getElementById('edit_banda_reen').value,
        psi: parseFloat(document.getElementById('edit_psi').value) || 100,
        prof_ext: parseFloat(document.getElementById('edit_prof_ext').value) || 0,
        prof_cent: parseFloat(document.getElementById('edit_prof_cent').value) || 0,
        prof_int: parseFloat(document.getElementById('edit_prof_int').value) || 0,
        prof_inicial: parseFloat(document.getElementById('edit_prof_inicial').value) || 0,
        precio: parseFloat(document.getElementById('edit_precio').value) || 0,
        km_montaje: parseFloat(document.getElementById('edit_km_montaje').value) || 0,
        novedades: document.getElementById('edit_novedades').value,
        foto_novedad: document.getElementById('edit_foto_novedad_base64')?.value || ''
      };


      try {
        const res = await fetch(`/api/inspecciones/${id}`, {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (res.ok) {
          cerrarModalEditarInspeccion();
          mostrarToast(`✅ Registro ID ${id} actualizado correctamente.`);
          cargarBaseInspecciones();
        } else {
          mostrarToast(d.detail || d.message || 'Error al actualizar', true);
        }
      } catch (err) {
        mostrarToast('Error de red al actualizar la inspección', true);
      }
    }

    async function eliminarInspeccion(id, placa, pos) {
      if (!confirm(`¿Eliminar la inspección ID ${id} (Vehículo ${placa}, Posición ${pos})?`)) return;
      try {
        const res = await fetch(`/api/inspecciones/${id}`, { method: 'DELETE' });
        if (res.ok) {
          mostrarToast(`🗑️ Registro ID ${id} eliminado.`);
          cargarBaseInspecciones();
        } else {
          mostrarToast('No se pudo eliminar el registro', true);
        }
      } catch (e) {
        mostrarToast('Error al intentar eliminar', true);
      }
    }

    // Funciones de Excel
    function abrirModalImportarExcel() {
      const m = document.getElementById('modalImportarExcel');
      m.classList.remove('hidden');
      m.classList.add('flex');
    }
    function cerrarModalImportarExcel() {
      const m = document.getElementById('modalImportarExcel');
      m.classList.add('hidden');
      m.classList.remove('flex');
    }
    function descargarPlantillaExcel() {
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      const q = tok ? `?token=${encodeURIComponent(tok)}` : '';
      window.location.href = `/api/inspecciones/plantilla-excel${q}`;
    }
    function exportarInspeccionesExcel() {
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      const q = tok ? `?token=${encodeURIComponent(tok)}` : '';
      window.location.href = `/api/inspecciones/exportar-excel${q}`;
    }

    // Zona Drag and Drop Excel
    const dropZone = document.getElementById('dropZoneExcel');
    const fileInput = document.getElementById('fileExcelInput');
    if (dropZone && fileInput) {
      dropZone.onclick = () => fileInput.click();
      dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('border-emerald-500', 'bg-emerald-50'); };
      dropZone.ondragleave = () => { dropZone.classList.remove('border-emerald-500', 'bg-emerald-50'); };
      dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-emerald-500', 'bg-emerald-50');
        if (e.dataTransfer.files.length) {
          fileInput.files = e.dataTransfer.files;
          alSeleccionarArchivoExcel({ target: fileInput });
        }
      };
    }

    function alSeleccionarArchivoExcel(e) {
      const f = e.target.files[0];
      const lbl = document.getElementById('lblArchivoSeleccionado');
      const btn = document.getElementById('btnSubirExcel');
      if (f) {
        lbl.textContent = `Archivo seleccionado: ${f.name} (${(f.size/1024).toFixed(1)} KB)`;
        btn.disabled = false;
      } else {
        lbl.textContent = 'Formatos permitidos: .xlsx, .xls';
        btn.disabled = true;
      }
    }

    async function ejecutarImportarExcel() {
      const f = fileInput.files[0];
      if (!f) return;
      const btn = document.getElementById('btnSubirExcel');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Procesando...';

      const formData = new FormData();
      formData.append('file', f);

      try {
        const res = await fetch('/api/inspecciones/importar-excel', {
          method: 'POST',
          body: formData
        });
        const d = await res.json();
        if (res.ok) {
          cerrarModalImportarExcel();
          mostrarToast(`🎉 ${d.message || 'Importación completada'}`);
          cargarBaseInspecciones();
        } else {
          mostrarToast(d.detail || 'Error al procesar el archivo Excel', true);
        }
      } catch (e) {
        mostrarToast('Error de red al subir el archivo', true);
      } finally {
        btn.disabled = false;
        btn.innerHTML = 'Subir e Importar';
      }
    }

