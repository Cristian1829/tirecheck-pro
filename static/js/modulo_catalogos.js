    // ==========================================
    // VISTA 5: GESTIÓN DE CATÁLOGOS & CONFIGURACIÓN
    // ==========================================
    let cacheDirectorioClientes = [];

    function mostrarSubtabCat(subtab) {
      const esAdmin = esUsuarioAdmin();
      const puedeVerClientes = esAdminOJefatura();
      if (subtab === 'usuarios' && !esAdmin) {
        subtab = 'operaciones';
      }
      if ((subtab === 'clientes' || subtab === 'marcas_cliente' || subtab === 'directorio_clientes') && !puedeVerClientes) {
        subtab = 'operaciones';
      }
      const tabs = ['directorio_clientes', 'operaciones', 'tipologias', 'modelos', 'clientes', 'marcas_cliente', 'usuarios'];
      tabs.forEach(t => {
        const sec = document.getElementById(`cat-seccion-${t}`);
        if (sec) sec.classList.add('hidden');
        const btn = document.getElementById(`subtab-btn-${t}`);
        if (btn) btn.className = 'px-3 py-1.5 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200';
      });
      const secAct = document.getElementById(`cat-seccion-${subtab}`);
      if (secAct) secAct.classList.remove('hidden');
      const btnAct = document.getElementById(`subtab-btn-${subtab}`);
      if (btnAct) btnAct.className = 'px-3 py-1.5 rounded-xl bg-slate-900 text-white';

      // Cargar los datos de la subpestaña seleccionada
      if (subtab === 'directorio_clientes' && puedeVerClientes) {
        cargarDirectorioClientesCat();
      } else if (subtab === 'usuarios' && esAdmin) {
        cargarUsuariosCat();
      } else if (subtab === 'clientes' && puedeVerClientes) {
        cargarClientesLimCat();
      } else if (subtab === 'marcas_cliente' && puedeVerClientes) {
        cargarMarcasClienteCat();
      } else if (subtab === 'operaciones') {
        cargarOperacionesCat();
      } else if (subtab === 'tipologias') {
        cargarTipologiasCat();
      } else if (subtab === 'modelos') {
        cargarModelosCat();
      }
    }

    async function cargarGestionCatalogos() {
      if (esAdminOJefatura()) {
        cargarDirectorioClientesCat();
        cargarClientesLimCat();
        cargarMarcasClienteCat();
      }
      cargarOperacionesCat();
      cargarTipologiasCat();
      cargarModelosCat();
      if (esUsuarioAdmin()) {
        cargarUsuariosCat();
      }
    }

    async function cargarDirectorioClientesCat() {
      try {
        const res = await fetch('/api/clientes-directorio');
        if (res.ok) {
          cacheDirectorioClientes = await res.json();
          renderizarDirectorioClientes(cacheDirectorioClientes);
        } else {
          const tbody = document.getElementById('tbodyDirectorioClientesCat');
          if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="p-4 text-center text-rose-500 font-bold">Error al cargar clientes desde el servidor.</td></tr>`;
        }
      } catch (e) {
        console.error('Error cargando directorio de clientes:', e);
        const tbody = document.getElementById('tbodyDirectorioClientesCat');
        if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="p-4 text-center text-rose-500 font-bold">Error de conexión al cargar clientes.</td></tr>`;
      }
    }

    function renderizarDirectorioClientes(lista) {
      const tbody = document.getElementById('tbodyDirectorioClientesCat');
      if (!tbody) return;

      const totalClientes = lista ? lista.length : 0;
      let totalVehiculos = 0;
      let totalInspecciones = 0;
      (lista || []).forEach(c => {
        totalVehiculos += (c.vehiculos_count || 0);
        totalInspecciones += (c.inspecciones_count || 0);
      });

      if (document.getElementById('kpiTotalClientesCat')) {
        document.getElementById('kpiTotalClientesCat').textContent = totalClientes;
      }
      if (document.getElementById('kpiTotalVehiculosCat')) {
        document.getElementById('kpiTotalVehiculosCat').textContent = `${totalVehiculos} veh (${totalInspecciones} insp)`;
      }

      if (!lista || lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="p-6 text-center text-slate-400 italic font-medium">No se encontraron clientes registrados con el filtro aplicado</td></tr>`;
        return;
      }

      const puedeEditar = esAdminOJefatura();
      tbody.innerHTML = lista.map(c => {
        const licBadge = (c.tipo_licencia === 'PRO') 
          ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-100 text-amber-900 border border-amber-300">PRO (Bodegas & MRP)</span>'
          : '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-slate-100 text-slate-700 border border-slate-300">LIGHT</span>';

        const reqMes = (c.requiere_mes_siguiente !== false && c.requiere_mes_siguiente !== 0);
        const diasNum = c.dias_espera_inspeccion || 20;
        const freqBadge = reqMes
          ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-800 border border-indigo-200" title="Mes siguiente y mínimo ${diasNum} días transcurridos">📅 Mes sig. + ${diasNum}d</span>`
          : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200" title="Habilita exactamente a los ${diasNum} días de la última inspección">⚡ ${diasNum}d corridos</span>`;

        const subChips = (c.subclientes && c.subclientes.length > 0)
          ? c.subclientes.map(s => `<span class="inline-block px-1.5 py-0.5 text-[10px] font-bold rounded-md bg-slate-100 text-slate-700 mr-1 mb-0.5">${s}</span>`).join('')
          : '<span class="text-slate-400 italic text-[11px]">Principal</span>';

        const serialCliSeguro = String(c.cliente || '').replace(/'/g, "\\'");

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-3">
              <div class="font-black text-slate-900 flex items-center space-x-1.5">
                <i class="fa-solid fa-building text-slate-400 text-xs"></i>
                <span>${c.cliente}</span>
              </div>
              <div class="text-[10px] text-slate-400 mt-0.5">Actualizado: ${c.fecha_actualizacion ? c.fecha_actualizacion.slice(0, 10) : 'Al día'}</div>
            </td>
            <td class="p-3 text-center">${licBadge}</td>
            <td class="p-3 text-center font-mono font-black text-rose-700">${Number(c.limite_retiro_mm || 3.0).toFixed(1)} mm</td>
            <td class="p-3 text-center">${freqBadge}</td>
            <td class="p-3 max-w-[200px]">${subChips}</td>
            <td class="p-3 text-center">
              <span class="font-bold text-slate-800">${c.vehiculos_count || 0}</span>
              <span class="text-[10px] text-slate-400 block">${c.inspecciones_count || 0} insp</span>
            </td>
            <td class="p-3 text-center">
              <span class="font-black ${c.llantas_count > 0 ? 'text-blue-700' : 'text-slate-400'}">${c.llantas_count || 0}</span>
            </td>
            <td class="p-3 text-center">
              <span class="font-bold text-slate-700">${c.marcas_count || 0}</span>
            </td>
            <td class="p-3 text-slate-600 max-w-[180px] truncate" title="${escapeHtml(c.observaciones || '')}">${escapeHtml(c.observaciones) || '-'}</td>
            <td class="p-3 text-center">
              <div class="flex items-center justify-center space-x-1">
                ${puedeEditar ? `
                  <button type="button" onclick="abrirModalEditarCliente('${serialCliSeguro}')" class="p-1.5 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg font-bold text-xs transition-colors" title="Editar configuración del cliente">
                    <i class="fa-solid fa-pen-to-square"></i>
                  </button>
                  <button type="button" onclick="irAAsociarMarcaCliente('${serialCliSeguro}')" class="p-1.5 text-emerald-600 hover:text-emerald-800 hover:bg-emerald-50 rounded-lg font-bold text-xs transition-colors" title="Parametrizar marcas autorizadas">
                    <i class="fa-solid fa-tags"></i>
                  </button>
                  ${(c.inspecciones_count === 0 && c.llantas_count === 0) ? `
                    <button type="button" onclick="eliminarClienteDirectorio('${serialCliSeguro}')" class="p-1.5 text-rose-600 hover:text-rose-800 hover:bg-rose-50 rounded-lg font-bold text-xs transition-colors" title="Eliminar cliente sin historial">
                      <i class="fa-solid fa-trash"></i>
                    </button>
                  ` : `
                    <span class="p-1.5 text-slate-300 text-xs cursor-not-allowed" title="Cliente con historial operativo protegido">
                      <i class="fa-solid fa-lock"></i>
                    </span>
                  `}
                ` : '<span class="text-slate-400 text-xs italic">Ver</span>'}
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function filtrarDirectorioClientesCat(texto) {
      const q = String(texto || '').trim().toUpperCase();
      if (!q) {
        renderizarDirectorioClientes(cacheDirectorioClientes);
        return;
      }
      const filtrados = cacheDirectorioClientes.filter(c => {
        return c.cliente.includes(q) || 
               (c.subclientes_str && c.subclientes_str.toUpperCase().includes(q)) ||
               (c.observaciones && c.observaciones.toUpperCase().includes(q));
      });
      renderizarDirectorioClientes(filtrados);
    }

    function abrirModalNuevoCliente() {
      document.getElementById('tituloModalCliente').textContent = 'Agregar Nuevo Cliente / Flota';
      document.getElementById('btnGuardarClienteTexto').textContent = 'Guardar Cliente';
      document.getElementById('nuevo_cliente_nombre').value = '';
      document.getElementById('nuevo_cliente_nombre').readOnly = false;
      document.getElementById('nuevo_cliente_licencia').value = 'LIGHT';
      document.getElementById('nuevo_cliente_limite').value = '3.0';
      document.getElementById('nuevo_cliente_dias_inspeccion').value = '20';
      document.getElementById('nuevo_cliente_regla_frecuencia').value = 'mes_siguiente';
      document.getElementById('nuevo_cliente_subclientes').value = 'Principal';
      document.getElementById('nuevo_cliente_observaciones').value = '';

      document.getElementById('modalNuevoCliente').classList.remove('hidden');
      document.getElementById('modalNuevoCliente').classList.add('flex');
    }

    function abrirModalEditarCliente(clienteNom) {
      const clean = String(clienteNom || '').trim().toUpperCase();
      const cli = cacheDirectorioClientes.find(c => c.cliente === clean);
      if (!cli) return;

      document.getElementById('tituloModalCliente').textContent = `Editar Configuración: ${cli.cliente}`;
      document.getElementById('btnGuardarClienteTexto').textContent = 'Actualizar Cambios';
      document.getElementById('nuevo_cliente_nombre').value = cli.cliente;
      document.getElementById('nuevo_cliente_nombre').readOnly = true;
      document.getElementById('nuevo_cliente_licencia').value = cli.tipo_licencia || 'LIGHT';
      document.getElementById('nuevo_cliente_limite').value = cli.limite_retiro_mm || '3.0';
      document.getElementById('nuevo_cliente_dias_inspeccion').value = cli.dias_espera_inspeccion || 20;
      const esCorridos = (cli.requiere_mes_siguiente === false || cli.requiere_mes_siguiente === 0);
      document.getElementById('nuevo_cliente_regla_frecuencia').value = esCorridos ? 'dias_corridos' : 'mes_siguiente';
      document.getElementById('nuevo_cliente_subclientes').value = (cli.subclientes && cli.subclientes.length > 0) ? cli.subclientes.join(', ') : 'Principal';
      document.getElementById('nuevo_cliente_observaciones').value = cli.observaciones || '';

      document.getElementById('modalNuevoCliente').classList.remove('hidden');
      document.getElementById('modalNuevoCliente').classList.add('flex');
    }

    function cerrarModalNuevoCliente() {
      document.getElementById('modalNuevoCliente').classList.add('hidden');
      document.getElementById('modalNuevoCliente').classList.remove('flex');
    }

    async function guardarNuevoCliente(e) {
      e.preventDefault();
      const nom = document.getElementById('nuevo_cliente_nombre').value.trim().toUpperCase();
      if (!nom) {
        mostrarToast('⚠️ Ingrese el nombre del cliente o flota', true);
        return;
      }

      const payload = {
        cliente: nom,
        tipo_licencia: document.getElementById('nuevo_cliente_licencia').value,
        limite_retiro_mm: parseFloat(document.getElementById('nuevo_cliente_limite').value) || 3.0,
        dias_espera_inspeccion: parseInt(document.getElementById('nuevo_cliente_dias_inspeccion').value) || 20,
        requiere_mes_siguiente: document.getElementById('nuevo_cliente_regla_frecuencia').value === 'mes_siguiente',
        subclientes: document.getElementById('nuevo_cliente_subclientes').value.trim(),
        observaciones: document.getElementById('nuevo_cliente_observaciones').value.trim()
      };

      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
        const res = await fetch('/api/clientes-directorio', {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });
        const resp = await res.json();
        if (res.ok && (resp.ok || resp.status === 'ok')) {
          mostrarToast(`✅ Cliente '${nom}' guardado exitosamente`);
          cerrarModalNuevoCliente();
          await cargarDirectorioClientesCat();
          if (typeof cargarCatalogos === 'function') {
            await cargarCatalogos();
          }
        } else {
          mostrarToast('❌ Error: ' + (resp.detail || resp.mensaje || 'No se pudo guardar el cliente'), true);
        }
      } catch (err) {
        console.error('Error al guardar cliente:', err);
        mostrarToast('❌ Error de conexión al guardar cliente', true);
      }
    }

    async function eliminarClienteDirectorio(clienteNom) {
      if (!confirm(`¿Está seguro de eliminar el cliente '${clienteNom}'? Esta acción solo se permite si el cliente no tiene inspecciones ni llantas en bodega.`)) {
        return;
      }
      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch(`/api/clientes-directorio/${encodeURIComponent(clienteNom)}`, {
          method: 'DELETE',
          headers
        });
        const resp = await res.json();
        if (res.ok && (resp.ok || resp.status === 'ok')) {
          mostrarToast(`✅ Cliente '${clienteNom}' eliminado exitosamente`);
          await cargarDirectorioClientesCat();
          if (typeof cargarCatalogos === 'function') {
            await cargarCatalogos();
          }
        } else {
          mostrarToast('❌ ' + (resp.detail || resp.mensaje || 'No se pudo eliminar el cliente'), true);
        }
      } catch (err) {
        console.error('Error al eliminar cliente:', err);
        mostrarToast('❌ Error de comunicación con el servidor', true);
      }
    }

    function irAAsociarMarcaCliente(clienteNom) {
      mostrarSubtabCat('marcas_cliente');
      const filtro = document.getElementById('filtroCatMarcaCliente');
      if (filtro) {
        filtro.value = clienteNom;
        filtrarMarcasClienteCat();
      }
    }

    async function cargarOperacionesCat() {
      const res = await fetch('/api/operaciones');
      if (res.ok) {
        const ops = await res.json();
        const box = document.getElementById('listaOperacionesCat');
        const puedeEditar = esAdminOJefatura();
        box.innerHTML = ops.map(op => `
          <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
            <span class="font-bold text-slate-800">${op}</span>
            ${puedeEditar ? `
              <button type="button" onclick="eliminarOperacionCat('${op}')" class="text-rose-600 hover:text-rose-800 text-xs" title="Eliminar Operación"><i class="fa-solid fa-trash"></i></button>
            ` : ''}
          </div>
        `).join('');
      }
    }

    async function eliminarOperacionCat(nombre) {
      if (!confirm(`¿Eliminar la operación "${nombre}"?`)) return;
      const res = await fetch(`/api/operaciones?nombre=${encodeURIComponent(nombre)}`, { method: 'DELETE' });
      if (res.ok) {
        mostrarToast('Operación eliminada.');
        cargarOperacionesCat();
      }
    }

    let tipologiaEditando = null;
    let catalogoModelosCache = [];
    let modeloEditandoId = null;
    let catalogoLimitesCache = [];
    let limiteClienteEditandoId = null;

    async function cargarTipologiasCat() {
      const res = await fetch('/api/tipologias');
      if (res.ok) {
        const tips = await res.json();
        const box = document.getElementById('listaTipologiasCat');
        const puedeEditar = esAdminOJefatura();
        box.innerHTML = tips.map(t => {
          return `
            <div class="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2 hover:shadow-sm transition-all flex flex-col justify-between">
              <div class="space-y-1">
                <div class="flex items-center justify-between">
                  <span class="font-black text-slate-900 text-sm">${t.nombre}</span>
                  <span class="text-xs font-bold bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">${t.cant_llantas} llantas</span>
                </div>
                <p class="text-xs text-slate-500 min-h-[1.5rem]">${t.descripcion || 'Sin descripción'}</p>
              </div>
              ${puedeEditar ? `
                <div class="pt-2 border-t border-slate-200/70 flex items-center justify-end space-x-1.5">
                  <button type="button" onclick="abrirModalEditarTipologia('${encodeURIComponent(JSON.stringify(t))}')" class="px-2.5 py-1 text-xs font-bold text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg flex items-center space-x-1 transition-all" title="Editar Tipología">
                    <i class="fa-solid fa-pen-to-square"></i>
                    <span>Editar</span>
                  </button>
                  <button type="button" onclick="eliminarTipologiaCat('${encodeURIComponent(t.nombre)}')" class="px-2.5 py-1 text-xs font-bold text-rose-600 hover:text-rose-800 hover:bg-rose-50 rounded-lg flex items-center space-x-1 transition-all" title="Eliminar Tipología">
                    <i class="fa-solid fa-trash"></i>
                    <span>Eliminar</span>
                  </button>
                </div>
              ` : ''}
            </div>
          `;
        }).join('');
      }
    }

    async function eliminarTipologiaCat(nombreEncoded) {
      const nombre = decodeURIComponent(nombreEncoded);
      if (!confirm(`¿Estás seguro de eliminar la tipología "${nombre}"?\nEsta acción sólo se completará si no está en uso por ningún vehículo o inspección en la base de datos.`)) {
        return;
      }
      try {
        const res = await fetch(`/api/tipologias?nombre=${encodeURIComponent(nombre)}`, { method: 'DELETE' });
        if (res.ok) {
          mostrarToast(`✅ Tipología "${nombre}" eliminada correctamente.`);
          cargarTipologiasCat();
          cargarCatalogos();
        } else {
          const data = await res.json().catch(() => ({}));
          const msg = data.detail || `No se pudo eliminar la tipología "${nombre}".`;
          alert(`⚠️ ${msg}`);
        }
      } catch (err) {
        alert('Error de conexión al intentar eliminar la tipología.');
      }
    }

        function actualizarBarraPaginacionGenerica(sufijo, totalRegistros, inicio, fin, paginaActual, totalPaginas, fnCambioNombre) {
      const contenedor = document.getElementById(`contenedorPaginacion${sufijo}`);
      const lblInicio = document.getElementById(`pagInicio${sufijo}`);
      const lblFin = document.getElementById(`pagFin${sufijo}`);
      const lblTotal = document.getElementById(`pagTotal${sufijo}`);
      const controles = document.getElementById(`controlesPaginacion${sufijo}`);

      if (!contenedor || !controles) return;
      if (totalRegistros <= 25 && totalPaginas <= 1) {
        contenedor.classList.remove('hidden');
        if (lblInicio) lblInicio.textContent = (inicio + 1).toLocaleString();
        if (lblFin) lblFin.textContent = fin.toLocaleString();
        if (lblTotal) lblTotal.textContent = totalRegistros.toLocaleString();
        controles.innerHTML = '<span class="text-xs text-slate-400 font-bold px-2 py-1">Pág 1 de 1</span>';
        return;
      }

      contenedor.classList.remove('hidden');
      if (lblInicio) lblInicio.textContent = (inicio + 1).toLocaleString();
      if (lblFin) lblFin.textContent = fin.toLocaleString();
      if (lblTotal) lblTotal.textContent = totalRegistros.toLocaleString();

      let html = '';
      const deshabilitarPrimero = paginaActual <= 1;
      html += `
        <button type="button" onclick="${fnCambioNombre}(1)" ${deshabilitarPrimero ? 'disabled' : ''}
          class="w-7 h-7 rounded-lg border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarPrimero ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-2xs cursor-pointer'
          }" title="Primera página">
          <i class="fa-solid fa-angles-left text-[10px]"></i>
        </button>
      `;

      const deshabilitarAnt = paginaActual <= 1;
      html += `
        <button type="button" onclick="${fnCambioNombre}(${paginaActual - 1})" ${deshabilitarAnt ? 'disabled' : ''}
          class="w-7 h-7 rounded-lg border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarAnt ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-2xs cursor-pointer'
          }" title="Página anterior">
          <i class="fa-solid fa-chevron-left text-[10px]"></i>
        </button>
      `;

      for (let i = 1; i <= totalPaginas; i++) {
        if (i === paginaActual) {
          html += `<button type="button" class="w-7 h-7 rounded-lg bg-blue-600 text-white font-black text-xs shadow-2xs flex items-center justify-center cursor-default">${i}</button>`;
        } else {
          html += `<button type="button" onclick="${fnCambioNombre}(${i})" class="w-7 h-7 rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 font-bold text-xs shadow-2xs flex items-center justify-center cursor-pointer">${i}</button>`;
        }
      }

      const deshabilitarSig = paginaActual >= totalPaginas;
      html += `
        <button type="button" onclick="${fnCambioNombre}(${paginaActual + 1})" ${deshabilitarSig ? 'disabled' : ''}
          class="w-7 h-7 rounded-lg border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarSig ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-2xs cursor-pointer'
          }" title="Página siguiente">
          <i class="fa-solid fa-chevron-right text-[10px]"></i>
        </button>
      `;

      const deshabilitarUltimo = paginaActual >= totalPaginas;
      html += `
        <button type="button" onclick="${fnCambioNombre}(${totalPaginas})" ${deshabilitarUltimo ? 'disabled' : ''}
          class="w-7 h-7 rounded-lg border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarUltimo ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-2xs cursor-pointer'
          }" title="Última página">
          <i class="fa-solid fa-angles-right text-[10px]"></i>
        </button>
      `;

      controles.innerHTML = html;
    }

    let paginaActualModelosCat = 1;
    const ITEMS_POR_PAGINA_MODELOS = 25;

    async function cargarModelosCat() {
      const res = await fetch('/api/modelos-llanta');
      if (res.ok) {
        catalogoModelosCache = await res.json();
        paginaActualModelosCat = 1;
        renderizarTablaModelosCat();
      }
    }

    function renderizarTablaModelosCat() {
      const tbody = document.getElementById('tbodyModelosCat');
      const contenedor = document.getElementById('contenedorPaginacionModelosCat');
      if (!tbody) return;

      const lista = catalogoModelosCache || [];
      if (lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-slate-400 italic">No hay modelos de llanta registrados</td></tr>`;
        if (contenedor) contenedor.classList.add('hidden');
        return;
      }

      const totalRegistros = lista.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_MODELOS) || 1;
      if (paginaActualModelosCat > totalPaginas) paginaActualModelosCat = totalPaginas;
      if (paginaActualModelosCat < 1) paginaActualModelosCat = 1;

      const inicio = (paginaActualModelosCat - 1) * ITEMS_POR_PAGINA_MODELOS;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_MODELOS, totalRegistros);
      const paginaItems = lista.slice(inicio, fin);
      const puedeEditar = esAdminOJefatura();

      tbody.innerHTML = paginaItems.map(m => `
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="p-2.5 font-bold">${m.tipo_llanta}</td>
          <td class="p-2.5 font-black text-slate-900">${m.marca}</td>
          <td class="p-2.5 font-bold text-slate-800">${m.diseno}</td>
          <td class="p-2.5 text-slate-700">${m.dimension}</td>
          <td class="p-2.5 text-center font-mono font-black text-blue-700">${m.prof_inicial} mm</td>
          <td class="p-2.5 text-slate-500">${m.descripcion || '-'}</td>
          <td class="p-2.5 text-center">
            ${puedeEditar ? `
              <div class="flex items-center justify-center space-x-1">
                <button type="button" onclick="abrirModalEditarModelo(${m.id})" class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded-lg hover:bg-blue-50 font-bold transition-all" title="Editar modelo y sincronizar prof. inicial en BD">
                  <i class="fa-solid fa-pen-to-square"></i>
                </button>
                <button type="button" onclick="eliminarModeloCat(${m.id}, '${encodeURIComponent(m.marca + ' ' + m.diseno)}')" class="text-rose-600 hover:text-rose-800 text-xs px-2 py-1 rounded-lg hover:bg-rose-50 font-bold transition-all" title="Eliminar modelo del catálogo">
                  <i class="fa-solid fa-trash"></i>
                </button>
              </div>
            ` : '-'}
          </td>
        </tr>
      `).join('');

      actualizarBarraPaginacionGenerica('ModelosCat', totalRegistros, inicio, fin, paginaActualModelosCat, totalPaginas, 'cambiarPaginaModelosCat');
    }

    function cambiarPaginaModelosCat(p) {
      paginaActualModelosCat = p;
      renderizarTablaModelosCat();
    }

    function abrirModalNuevoModelo() {
      modeloEditandoId = null;
      const elTit = document.getElementById('tituloModalModelo');
      if (elTit) elTit.textContent = 'Nuevo Modelo de Llanta';
      const elNota = document.getElementById('notaSincronizarModelo');
      if (elNota) elNota.classList.add('hidden');
      const elBtn = document.getElementById('btnGuardarModeloTexto');
      if (elBtn) elBtn.textContent = 'Guardar';
      document.getElementById('mod_tipo').value = 'Nueva';
      document.getElementById('mod_marca').value = '';
      document.getElementById('mod_diseno').value = '';
      document.getElementById('mod_dimension').value = '295/80R22.5';
      document.getElementById('mod_prof').value = '';
      document.getElementById('mod_desc').value = '';
      document.getElementById('modalNuevoModelo').classList.remove('hidden');
      document.getElementById('modalNuevoModelo').classList.add('flex');
    }

    function abrirModalEditarModelo(id) {
      const m = catalogoModelosCache.find(x => x.id === id);
      if (!m) return;
      modeloEditandoId = id;
      const elTit = document.getElementById('tituloModalModelo');
      if (elTit) elTit.textContent = `Editar Modelo: ${m.marca} ${m.diseno}`;
      const elNota = document.getElementById('notaSincronizarModelo');
      if (elNota) elNota.classList.remove('hidden');
      const elBtn = document.getElementById('btnGuardarModeloTexto');
      if (elBtn) elBtn.textContent = 'Guardar Cambios';
      document.getElementById('mod_tipo').value = m.tipo_llanta;
      document.getElementById('mod_marca').value = m.marca;
      document.getElementById('mod_diseno').value = m.diseno;
      document.getElementById('mod_dimension').value = m.dimension;
      document.getElementById('mod_prof').value = m.prof_inicial;
      document.getElementById('mod_desc').value = m.descripcion || '';
      document.getElementById('modalNuevoModelo').classList.remove('hidden');
      document.getElementById('modalNuevoModelo').classList.add('flex');
    }

    function cerrarModalNuevoModelo() {
      document.getElementById('modalNuevoModelo').classList.add('hidden');
      document.getElementById('modalNuevoModelo').classList.remove('flex');
    }

    async function guardarNuevoModelo() {
      const p = parseFloat(document.getElementById('mod_prof').value);
      if (!p || p <= 0) {
        alert('Ingresa una profundidad inicial válida (mayor a 0)');
        return;
      }
      const item = {
        tipo_llanta: document.getElementById('mod_tipo').value,
        marca: document.getElementById('mod_marca').value.trim().toUpperCase(),
        diseno: document.getElementById('mod_diseno').value.trim().toUpperCase(),
        dimension: document.getElementById('mod_dimension').value.trim().toUpperCase(),
        prof_inicial: p,
        descripcion: document.getElementById('mod_desc').value.trim()
      };
      if (!item.marca || !item.diseno) {
        alert('Marca y Diseño son obligatorios');
        return;
      }

      if (modeloEditandoId) {
        const payload = {
          id: modeloEditandoId,
          ...item,
          actualizar_bd: true
        };
        try {
          const res = await fetch('/api/modelos-llanta', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
          });
          if (res.ok) {
            const data = await res.json();
            cerrarModalNuevoModelo();
            const msgSinc = data.filas_actualizadas > 0 
              ? ` Se actualizó la prof. inicial (${data.prof_inicial} mm) en ${data.filas_actualizadas} inspección(es) de la base de datos.` 
              : '';
            mostrarToast(`✅ Modelo "${item.marca} ${item.diseno}" actualizado.${msgSinc}`);
            cargarModelosCat();
            if (typeof cargarBaseInspecciones === 'function') cargarBaseInspecciones();
          } else {
            const err = await res.json().catch(() => ({}));
            alert(err.detail || 'Error al actualizar el modelo de llanta.');
          }
        } catch (e) {
          alert('Error de conexión al actualizar el modelo.');
        }
      } else {
        const res = await fetch('/api/modelos-llanta', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(item)
        });
        if (res.ok) {
          cerrarModalNuevoModelo();
          mostrarToast('✅ Modelo guardado en catálogo.');
          cargarModelosCat();
        } else {
          const err = await res.json().catch(() => ({}));
          alert(err.detail || 'Error al guardar el modelo de llanta.');
        }
      }
    }

    async function eliminarModeloCat(id, nombreEncoded) {
      const nombre = decodeURIComponent(nombreEncoded);
      if (!confirm(`¿Eliminar el modelo "${nombre}" del catálogo?`)) return;
      try {
        const res = await fetch(`/api/modelos-llanta/${id}`, { method: 'DELETE' });
        if (res.ok) {
          mostrarToast(`✅ Modelo "${nombre}" eliminado del catálogo.`);
          cargarModelosCat();
        } else {
          alert('Error al eliminar el modelo.');
        }
      } catch (e) {
        alert('Error de conexión al eliminar modelo.');
      }
    }

    let paginaActualLimitesCat = 1;
    const ITEMS_POR_PAGINA_LIMITES = 25;

    async function cargarClientesLimCat() {
      const res = await fetch('/api/configuraciones-clientes');
      if (res.ok) {
        catalogoLimitesCache = await res.json();
        paginaActualLimitesCat = 1;
        renderizarTablaLimitesCat();
      }
    }

    function renderizarTablaLimitesCat() {
      const tbody = document.getElementById('tbodyClientesLimCat');
      const contenedor = document.getElementById('contenedorPaginacionLimitesCat');
      if (!tbody) return;

      const lista = catalogoLimitesCache || [];
      if (lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-slate-400 italic font-medium">No hay límites configurados por cliente</td></tr>`;
        if (contenedor) contenedor.classList.add('hidden');
        return;
      }

      const totalRegistros = lista.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_LIMITES) || 1;
      if (paginaActualLimitesCat > totalPaginas) paginaActualLimitesCat = totalPaginas;
      if (paginaActualLimitesCat < 1) paginaActualLimitesCat = 1;

      const inicio = (paginaActualLimitesCat - 1) * ITEMS_POR_PAGINA_LIMITES;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_LIMITES, totalRegistros);
      const paginaItems = lista.slice(inicio, fin);

      tbody.innerHTML = paginaItems.map(c => {
        let badgeEje = '';
        const ejeUpper = (c.eje || 'TODOS').toUpperCase();
        if (ejeUpper === 'DIRECCIONAL') {
          badgeEje = '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-100 text-amber-800 border border-amber-200">DIRECCIONAL</span>';
        } else if (ejeUpper === 'TRACCIÓN' || ejeUpper === 'TRACCION') {
          badgeEje = '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">TRACCIÓN</span>';
        } else if (ejeUpper === 'LIBRE') {
          badgeEje = '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-blue-100 text-blue-800 border border-blue-200">LIBRE</span>';
        } else if (ejeUpper === 'REPUESTO') {
          badgeEje = '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-purple-100 text-purple-800 border border-purple-200">REPUESTO</span>';
        } else {
          badgeEje = '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-slate-100 text-slate-800 border border-slate-300">TODOS</span>';
        }

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-2.5 font-black text-slate-900">${c.cliente}</td>
            <td class="p-2.5 font-bold text-slate-700">${c.subcliente || 'TODOS'}</td>
            <td class="p-2.5 text-center">${badgeEje}</td>
            <td class="p-2.5 text-center font-black text-rose-700 font-mono text-sm">${c.limite_retiro_mm} mm</td>
            <td class="p-2.5 text-slate-600">${c.observaciones || '-'}</td>
            <td class="p-2.5 text-center">
              <div class="flex items-center justify-center space-x-1">
                <button type="button" onclick="abrirModalEditarLimiteCliente(${c.id})" class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded-lg hover:bg-blue-50 font-bold transition-all" title="Editar límite de retiro">
                  <i class="fa-solid fa-pen-to-square"></i>
                </button>
                <button type="button" onclick="eliminarLimiteCliente(${c.id})" class="text-rose-600 hover:text-rose-800 text-xs px-2 py-1 rounded-lg hover:bg-rose-50 font-bold transition-all" title="Eliminar regla de límite">
                  <i class="fa-solid fa-trash"></i>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      actualizarBarraPaginacionGenerica('LimitesCat', totalRegistros, inicio, fin, paginaActualLimitesCat, totalPaginas, 'cambiarPaginaLimitesCat');
    }

    function cambiarPaginaLimitesCat(p) {
      paginaActualLimitesCat = p;
      renderizarTablaLimitesCat();
    }

    function abrirModalLimiteCliente() {
      limiteClienteEditandoId = null;
      const elTit = document.getElementById('tituloModalLimiteCliente');
      if (elTit) elTit.textContent = 'Límite de Retiro por Cliente y Eje';
      const elBtn = document.getElementById('btnGuardarLimiteTexto');
      if (elBtn) elBtn.textContent = 'Guardar Límite';
      document.getElementById('lim_cliente').value = '';
      document.getElementById('lim_subcliente').value = 'TODOS';
      document.getElementById('lim_eje').value = 'TODOS';
      document.getElementById('lim_mm').value = '3.0';
      document.getElementById('lim_obs').value = '';
      document.getElementById('modalLimiteCliente').classList.remove('hidden');
      document.getElementById('modalLimiteCliente').classList.add('flex');
    }

    function abrirModalEditarLimiteCliente(id) {
      const c = catalogoLimitesCache.find(x => x.id === id);
      if (!c) return;
      limiteClienteEditandoId = id;
      const elTit = document.getElementById('tituloModalLimiteCliente');
      if (elTit) elTit.textContent = `Editar Límite: ${c.cliente}`;
      const elBtn = document.getElementById('btnGuardarLimiteTexto');
      if (elBtn) elBtn.textContent = 'Guardar Cambios';
      document.getElementById('lim_cliente').value = c.cliente;
      document.getElementById('lim_subcliente').value = c.subcliente || 'TODOS';
      document.getElementById('lim_eje').value = (c.eje || 'TODOS').toUpperCase();
      document.getElementById('lim_mm').value = c.limite_retiro_mm;
      document.getElementById('lim_obs').value = c.observaciones || '';
      document.getElementById('modalLimiteCliente').classList.remove('hidden');
      document.getElementById('modalLimiteCliente').classList.add('flex');
    }

    function cerrarModalLimiteCliente() {
      document.getElementById('modalLimiteCliente').classList.add('hidden');
      document.getElementById('modalLimiteCliente').classList.remove('flex');
    }

    async function guardarLimiteCliente() {
      const cli = document.getElementById('lim_cliente').value.trim().toUpperCase();
      const sub = (document.getElementById('lim_subcliente').value.trim() || 'TODOS').toUpperCase();
      const eje = document.getElementById('lim_eje').value.trim().toUpperCase();
      const mm = parseFloat(document.getElementById('lim_mm').value);
      const obs = document.getElementById('lim_obs').value.trim().toUpperCase();
      if (!cli || isNaN(mm)) {
        alert('Por favor completa el cliente y el límite en mm');
        return;
      }

      if (limiteClienteEditandoId) {
        const payload = {
          id: limiteClienteEditandoId,
          cliente: cli,
          subcliente: sub,
          eje: eje,
          limite_retiro_mm: mm,
          observaciones: obs
        };
        try {
          const res = await fetch('/api/configuraciones-clientes', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
          });
          if (res.ok) {
            cerrarModalLimiteCliente();
            mostrarToast(`✅ Límite actualizado para ${cli} (${sub} - ${eje}) a ${mm} mm.`);
            cargarClientesLimCat();
          } else {
            const err = await res.json().catch(() => ({}));
            alert(err.detail || 'Error al actualizar el límite de cliente');
          }
        } catch (e) {
          alert('Error de conexión al actualizar límite.');
        }
      } else {
        const res = await fetch('/api/configuraciones-clientes', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            cliente: cli,
            subcliente: sub,
            eje: eje,
            limite_retiro_mm: mm,
            observaciones: obs
          })
        });
        if (res.ok) {
          cerrarModalLimiteCliente();
          mostrarToast(`✅ Límite para ${cli} (${sub} - ${eje}) guardado en ${mm} mm.`);
          cargarClientesLimCat();
        } else {
          const err = await res.json().catch(() => ({}));
          alert(err.detail || 'Error al guardar el límite de cliente');
        }
      }
    }

    async function eliminarLimiteCliente(id) {
      if (!confirm('¿Deseas eliminar esta política de límite de retiro?')) return;
      const res = await fetch(`/api/configuraciones-clientes/${id}`, { method: 'DELETE' });
      if (res.ok) {
        mostrarToast('Límite eliminado.');
        cargarClientesLimCat();
      }
    }

    // ==========================================
    // GESTIÓN DE MARCAS POR CLIENTE (CATÁLOGOS)
    // ==========================================
    let marcasClienteCatCache = [];

    async function cargarMarcasClienteCat() {
      try {
        const res = await fetch('/api/configuracion-marcas-cliente');
        if (!res.ok) return;
        marcasClienteCatCache = await res.json();

        // Poblar selector de filtro por cliente
        const selFiltro = document.getElementById('filtroCatMarcaCliente');
        if (selFiltro) {
          const valPrevio = selFiltro.value;
          const clientesUnicos = Array.from(new Set(marcasClienteCatCache.map(m => m.cliente))).sort();
          selFiltro.innerHTML = `<option value="">TODOS LOS CLIENTES (${clientesUnicos.length})</option>` +
            clientesUnicos.map(c => `<option value="${c}">${c}</option>`).join('');
          if (valPrevio) selFiltro.value = valPrevio;
        }

        filtrarMarcasClienteCat();
      } catch (err) {
        console.error("Error al cargar marcas cliente en catálogos:", err);
      }
    }

    function filtrarMarcasClienteCat() {
      const cliSel = (document.getElementById('filtroCatMarcaCliente')?.value || '').trim().toUpperCase();
      let filtradas = marcasClienteCatCache;
      if (cliSel) {
        filtradas = marcasClienteCatCache.filter(m => m.cliente === cliSel);
      }
      renderizarTablaMarcasCliente(filtradas);
    }

    let paginaActualMarcasCat = 1;
    const ITEMS_POR_PAGINA_MARCAS = 25;
    let cacheFiltradasMarcasCat = [];

    function renderizarTablaMarcasCliente(lista) {
      const tbody = document.getElementById('tbodyMarcasClienteCat');
      const contador = document.getElementById('contadorMarcasClienteCat');
      const contenedor = document.getElementById('contenedorPaginacionMarcasCat');
      cacheFiltradasMarcasCat = lista || [];

      if (contador) contador.textContent = `Total: ${lista ? lista.length : 0} asociaciones (25 por página)`;
      if (!tbody) return;

      if (!lista || lista.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="4" class="p-6 text-center text-slate-400">
              <i class="fa-solid fa-tags text-2xl mb-2 text-slate-300 block"></i>
              No hay marcas parametrizadas para este cliente aún. Haz clic en "Asociar Marca a Cliente".
            </td>
          </tr>
        `;
        if (contenedor) contenedor.classList.add('hidden');
        return;
      }

      const totalRegistros = lista.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_MARCAS) || 1;
      if (paginaActualMarcasCat > totalPaginas) paginaActualMarcasCat = totalPaginas;
      if (paginaActualMarcasCat < 1) paginaActualMarcasCat = 1;

      const inicio = (paginaActualMarcasCat - 1) * ITEMS_POR_PAGINA_MARCAS;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_MARCAS, totalRegistros);
      const paginaItems = lista.slice(inicio, fin);

      tbody.innerHTML = paginaItems.map(item => `
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="p-2.5 font-bold text-slate-900">${item.cliente}</td>
          <td class="p-2.5">
            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-black bg-blue-50 text-blue-700 border border-blue-200">
              <i class="fa-solid fa-tag mr-1 text-[10px]"></i>
              ${item.marca}
            </span>
          </td>
          <td class="p-2.5 font-mono text-[11px] text-slate-500">${(item.fecha_actualizacion || '').replace('T', ' ').substring(0, 19)}</td>
          <td class="p-2.5 text-center">
            <button type="button" onclick="eliminarMarcaClientePorId(${item.id}, '${item.cliente}', '${item.marca}')" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded-lg font-bold text-xs transition-colors" title="Desvincular marca de este cliente">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </td>
        </tr>
      `).join('');

      actualizarBarraPaginacionGenerica('MarcasCat', totalRegistros, inicio, fin, paginaActualMarcasCat, totalPaginas, 'cambiarPaginaMarcasCat');
    }

    function cambiarPaginaMarcasCat(p) {
      paginaActualMarcasCat = p;
      renderizarTablaMarcasCliente(cacheFiltradasMarcasCat);
    }

    async function abrirModalAsociarMarcaCliente(clientePref = '') {
      const cliInput = document.getElementById('asoc_marca_cliente');
      const marcaInput = document.getElementById('asoc_marca_nombre');
      if (cliInput) {
        const selFiltro = document.getElementById('filtroCatMarcaCliente');
        cliInput.value = clientePref || (selFiltro && selFiltro.value ? selFiltro.value : '');
      }
      if (marcaInput) marcaInput.value = '';

      // Cargar todas las marcas del catálogo en datalist
      try {
        const res = await fetch('/api/valores-campo?campo=marca&todas=true');
        if (res.ok) {
          const marcas = await res.json();
          const dl = document.getElementById('dl_marcas_todas');
          if (dl) dl.innerHTML = marcas.map(m => `<option value="${m}">`).join('');
        }
      } catch (e) {}

      const modal = document.getElementById('modalAsociarMarcaCliente');
      if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      }
    }

    function cerrarModalAsociarMarcaCliente() {
      const modal = document.getElementById('modalAsociarMarcaCliente');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
    }

    async function guardarAsociacionMarcaCliente() {
      const cli = (document.getElementById('asoc_marca_cliente')?.value || '').trim().toUpperCase();
      const marca = (document.getElementById('asoc_marca_nombre')?.value || '').trim();
      if (!cli || !marca) {
        alert('Por favor ingresa tanto el Cliente como la Marca');
        return;
      }

      try {
        const res = await fetch('/api/configuracion-marcas-cliente', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ cliente: cli, marca: marca })
        });
        if (res.ok) {
          cerrarModalAsociarMarcaCliente();
          mostrarToast(`✅ Marca '${marca}' asociada a '${cli}'.`);
          await cargarMarcasClienteCat();
          // Si el patio tiene seleccionado a este cliente, refrescar marcas de patio
          const cliPatio = (document.getElementById('cliente')?.value || '').trim().toUpperCase();
          if (cliPatio === cli) {
            actualizarMarcasCliente(cli);
          }
        } else {
          const err = await res.json().catch(() => ({}));
          alert(err.detail || 'Error al asociar marca');
        }
      } catch (err) {
        alert('Error de conexión al asociar marca');
      }
    }

    async function eliminarMarcaClientePorId(id, cliente, marca) {
      if (!confirm(`¿Deseas desvincular la marca '${marca}' del cliente '${cliente}'?`)) return;
      try {
        const res = await fetch(`/api/configuracion-marcas-cliente/${id}`, { method: 'DELETE' });
        if (res.ok) {
          mostrarToast(`Marca '${marca}' desvinculada de '${cliente}'.`);
          await cargarMarcasClienteCat();
          const cliPatio = (document.getElementById('cliente')?.value || '').trim().toUpperCase();
          if (cliPatio === cliente) {
            actualizarMarcasCliente(cliente);
          }
        } else {
          const err = await res.json().catch(() => ({}));
          alert(err.detail || 'Error al eliminar asociación');
        }
      } catch (err) {
        alert('Error de conexión al desvincular marca');
      }
    }

    let usuariosCatCache = [];

    function renderizarBadgeRol(rol) {
      const r = String(rol || '').trim().toLowerCase();
      if (r === 'admin' || r === 'administrador') {
        return `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-purple-100 text-purple-800 border border-purple-200">ADMIN</span>`;
      } else if (r === 'jefatura' || r === 'jefe' || r === 'jefe_llantas') {
        return `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">JEFATURA LLANTAS</span>`;
      } else if (r === 'gerencia' || r === 'gerente') {
        return `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-indigo-100 text-indigo-800 border border-indigo-200">GERENCIA</span>`;
      } else {
        return `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-blue-100 text-blue-800 border border-blue-200">INSPECTOR</span>`;
      }
    }

    function renderizarBadgesVistas(vistasVal, rol) {
      const r = String(rol || '').trim().toLowerCase();
      if (r === 'admin' || r === 'administrador') {
        return `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-purple-100 text-purple-800 border border-purple-200">Acceso Total (Admin)</span>`;
      }
      let vistas = [];
      if (Array.isArray(vistasVal)) {
        vistas = vistasVal.map(s => String(s).trim().toLowerCase()).filter(Boolean);
      } else if (typeof vistasVal === 'string' && vistasVal.trim()) {
        vistas = vistasVal.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
      } else {
        if (r === 'jefatura' || r === 'jefe' || r === 'jefe_llantas') vistas = ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'];
        else if (r === 'gerencia' || r === 'gerente') vistas = ['basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas'];
        else vistas = ['patio', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'];
      }
      const badges = [];
      if (vistas.includes('patio')) badges.push('<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-50 text-blue-700 border border-blue-200">Patio</span>');
      if (vistas.includes('basedatos')) badges.push('<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Base Datos</span>');
      if (vistas.includes('diagnostico')) badges.push('<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-50 text-amber-700 border border-amber-200">Diag</span>');
      if (vistas.includes('kpis')) badges.push('<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-50 text-purple-700 border border-purple-200">KPIs</span>');
      if (vistas.includes('composicion')) badges.push('<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-50 text-cyan-700 border border-cyan-200">Composición Flota</span>');
      if (vistas.includes('bodegas')) badges.push('<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">Bodegas MRP</span>');
      if (vistas.includes('catalogos')) {
        const catText = (r === 'jefatura' || r === 'jefe' || r === 'jefe_llantas') ? 'Catálogos & Límites' : 'Catálogos (Lectura)';
        badges.push(`<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-50 text-slate-700 border border-slate-200">${catText}</span>`);
      }
      return badges.length > 0 ? `<div class="flex flex-wrap gap-1">${badges.join('')}</div>` : `<span class="text-slate-400 italic text-[10px]">Sin vistas</span>`;
    }

    function renderizarBadgesClientes(clienteAsignadoVal) {
      let clis = [];
      if (Array.isArray(clienteAsignadoVal)) {
        clis = clienteAsignadoVal.map(s => String(s).trim()).filter(Boolean);
      } else if (typeof clienteAsignadoVal === 'string' && clienteAsignadoVal.trim()) {
        clis = clienteAsignadoVal.split(',').map(s => s.trim()).filter(Boolean);
      }
      if (clis.length === 0) {
        return '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">Todas las Flotas</span>';
      }
      if (clis.length === 1) {
        return `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200 flex items-center space-x-1 inline-flex"><i class="fa-solid fa-lock text-[8px] mr-1"></i>${clis[0]} (Fijo)</span>`;
      }
      return `<div class="flex flex-wrap gap-1">${clis.map(c => `<span class="px-1.5 py-0.5 rounded text-[9px] font-medium bg-slate-100 text-slate-800 border border-slate-200">${c}</span>`).join('')}</div>`;
    }

    async function cargarUsuariosCat() {
      const tbody = document.getElementById('tbodyUsuariosCat');
      if (!tbody) return;

      if (!esUsuarioAdmin()) {
        console.warn("Intento de cargar usuarios sin perfil de administrador.");
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="p-6 text-center text-amber-600 font-bold text-xs">
              <i class="fa-solid fa-lock mr-1"></i>
              Acceso restringido: Solo los administradores pueden ver y gestionar usuarios.
            </td>
          </tr>
        `;
        return;
      }

      // Feedback visual de carga inmediato
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="p-6 text-center text-slate-500">
            <div class="inline-flex items-center justify-center space-x-2 text-xs font-bold text-slate-600">
              <i class="fa-solid fa-circle-notch fa-spin text-indigo-600 text-base"></i>
              <span>Cargando lista de usuarios del sistema...</span>
            </div>
          </td>
        </tr>
      `;

      try {
        const token = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch('/api/usuarios', { headers });

        if (res.ok) {
          usuariosCatCache = await res.json();
          if (!tbody) return;
          if (!usuariosCatCache || usuariosCatCache.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-slate-400 italic text-xs">No hay usuarios registrados. Usa el botón "+ Nuevo Usuario" para crear uno.</td></tr>`;
            return;
          }
          tbody.innerHTML = usuariosCatCache.map(u => `
            <tr class="hover:bg-slate-50 transition-colors">
              <td class="p-2.5 font-black text-slate-900">${u.username}</td>
              <td class="p-2.5 font-bold">${u.nombre_completo}</td>
              <td class="p-2.5 text-center font-bold uppercase text-[10px]">
                ${renderizarBadgeRol(u.rol)}
              </td>
              <td class="p-2.5">${renderizarBadgesVistas(u.vistas_permitidas, u.rol)}</td>
              <td class="p-2.5">${renderizarBadgesClientes(u.clientes_asignados || u.cliente_asignado)}</td>
              <td class="p-2.5 text-center">
                ${u.activo ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">Activo</span>' : '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-100 text-rose-800 border border-rose-200">Inactivo</span>'}
              </td>
              <td class="p-2.5 text-center">
                <div class="flex items-center justify-center space-x-1">
                  <button type="button" onclick="abrirModalEditarUsuario('${u.username}')" class="p-1.5 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg text-xs transition-colors" title="Editar Usuario">
                    <i class="fa-solid fa-user-pen"></i>
                  </button>
                  <button type="button" onclick="abrirModalResetPassword('${u.username}')" class="p-1.5 text-amber-600 hover:text-amber-800 hover:bg-amber-50 rounded-lg text-xs transition-colors" title="🔑 Restablecer Contraseña">
                    <i class="fa-solid fa-key"></i>
                  </button>
                  ${String(u.username).toLowerCase() !== 'admin' ? `
                    <button type="button" onclick="eliminarUsuarioCat('${u.username}')" class="p-1.5 text-rose-600 hover:text-rose-800 hover:bg-rose-50 rounded-lg text-xs transition-colors" title="Eliminar Usuario">
                      <i class="fa-solid fa-trash"></i>
                    </button>
                  ` : `
                    <span class="p-1.5 text-slate-300 text-xs" title="Superadmin Protegido"><i class="fa-solid fa-lock"></i></span>
                  `}
                </div>
              </td>
            </tr>
          `).join('');
          console.info(`Usuarios cargados con éxito (${usuariosCatCache.length} registros).`);
        } else {
          const errData = await res.json().catch(() => ({}));
          console.error("Error al obtener usuarios, status:", res.status, errData);
          if (tbody) {
            tbody.innerHTML = `
              <tr>
                <td colspan="7" class="p-6 text-center text-rose-600 font-bold text-xs space-y-2">
                  <div><i class="fa-solid fa-triangle-exclamation mr-1"></i> No se pudo cargar los usuarios (${res.status}): ${errData.detail || 'Sesión no válida o sin permisos'}</div>
                  <button type="button" onclick="cargarUsuariosCat()" class="mt-2 px-3 py-1 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-[11px] font-bold">
                    <i class="fa-solid fa-arrows-rotate mr-1"></i> Reintentar
                  </button>
                </td>
              </tr>
            `;
          }
        }
      } catch (e) {
        console.error("Error de conexión al cargar usuarios:", e);
        if (tbody) {
          tbody.innerHTML = `
            <tr>
              <td colspan="7" class="p-6 text-center text-rose-600 font-bold text-xs space-y-2">
                <div><i class="fa-solid fa-wifi mr-1"></i> Error de conexión con el servidor: ${e.message}</div>
                <button type="button" onclick="cargarUsuariosCat()" class="mt-2 px-3 py-1 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-[11px] font-bold">
                  <i class="fa-solid fa-arrows-rotate mr-1"></i> Reintentar
                </button>
              </td>
            </tr>
          `;
        }
      }
    }

    // Helpers de Control de Vistas y Asignación de Clientes en Modales
    function alCambiarRolUsuarioModal(modo) {
      const pfx = modo === 'nuevo' ? 'usr_' : 'edit_usr_';
      const rol = String(document.getElementById(`${pfx}rol`).value || '').trim().toLowerCase();
      const chkBD = document.getElementById(`${pfx}vista_basedatos`);
      const chkCat = document.getElementById(`${pfx}vista_catalogos`);
      const chkPatio = document.getElementById(`${pfx}vista_patio`);
      const chkDiag = document.getElementById(`${pfx}vista_diagnostico`);
      const chkKpis = document.getElementById(`${pfx}vista_kpis`);
      const chkComp = document.getElementById(`${pfx}vista_composicion`);
      const lblBD = document.getElementById(`lbl_${pfx}vista_basedatos`);
      const badgeBD = document.getElementById(`badge_${pfx}vista_basedatos`);

      if (rol === 'admin') {
        // Para admin: acceso total a las vistas
        if (chkPatio) chkPatio.checked = true;
        if (chkDiag) chkDiag.checked = true;
        if (chkKpis) chkKpis.checked = true;
        if (chkComp) chkComp.checked = true;
        if (chkBD) { chkBD.checked = true; chkBD.disabled = false; }
        if (chkCat) { chkCat.checked = true; chkCat.disabled = false; }
        if (lblBD) {
          lblBD.classList.remove('text-slate-400', 'bg-slate-100');
          lblBD.classList.add('text-slate-700', 'bg-white', 'cursor-pointer');
        }
        if (badgeBD) badgeBD.classList.add('hidden');
      } else if (rol === 'jefatura') {
        // Para Jefatura: acceso técnico completo por defecto (Patio, BD, Diag, KPIs, Composición, Catálogos)
        if (chkPatio) chkPatio.checked = true;
        if (chkDiag) chkDiag.checked = true;
        if (chkKpis) chkKpis.checked = true;
        if (chkComp) chkComp.checked = true;
        if (chkBD) { chkBD.checked = true; chkBD.disabled = false; }
        if (chkCat) { chkCat.checked = true; chkCat.disabled = false; }
        if (lblBD) {
          lblBD.classList.remove('text-slate-400', 'bg-slate-100');
          lblBD.classList.add('text-slate-700', 'bg-white', 'cursor-pointer');
        }
        if (badgeBD) badgeBD.classList.add('hidden');
      } else if (rol === 'gerencia') {
        // Para Gerencia: enfoque ejecutivo de auditoría y análisis (BD, Diag, KPIs, Composición)
        if (chkPatio) chkPatio.checked = false;
        if (chkDiag) chkDiag.checked = true;
        if (chkKpis) chkKpis.checked = true;
        if (chkComp) chkComp.checked = true;
        if (chkBD) { chkBD.checked = true; chkBD.disabled = false; }
        if (chkCat) { chkCat.checked = false; chkCat.disabled = false; }
        if (lblBD) {
          lblBD.classList.remove('text-slate-400', 'bg-slate-100');
          lblBD.classList.add('text-slate-700', 'bg-white', 'cursor-pointer');
        }
        if (badgeBD) badgeBD.classList.add('hidden');
      } else {
        // Para inspector: NUNCA tiene acceso a basedatos. SÍ puede consultar catalogos y composición
        if (chkBD) { chkBD.checked = false; chkBD.disabled = true; }
        if (lblBD) {
          lblBD.classList.remove('text-slate-700', 'bg-white', 'cursor-pointer');
          lblBD.classList.add('text-slate-400', 'bg-slate-100');
        }
        if (badgeBD) badgeBD.classList.remove('hidden');

        // Catálogos y Composición disponible para inspector
        if (chkCat) { chkCat.disabled = false; }
      }
    }

    function toggleClientesTodosModal(modo) {
      const pfx = modo === 'nuevo' ? 'usr_' : 'edit_usr_';
      const chk = document.getElementById(`${pfx}todas_flotas`);
      const cont = document.getElementById(modo === 'nuevo' ? 'usr_contenedor_clientes_nuevo' : 'edit_usr_contenedor_clientes');
      if (chk && cont) {
        if (chk.checked) {
          cont.classList.add('hidden');
        } else {
          cont.classList.remove('hidden');
        }
      }
    }

    async function poblarListaCheckboxesClientesModal(modo, clientesSeleccionados = []) {
      const contId = modo === 'nuevo' ? 'usr_lista_clientes_check_nuevo' : 'edit_usr_lista_clientes_check';
      const cont = document.getElementById(contId);
      if (!cont) return;

      let clientesDisponibles = [];
      try {
        const res = await fetch('/api/valores-campo?campo=cliente');
        if (res.ok) {
          clientesDisponibles = await res.json();
        }
      } catch(e) {}

      // Combinar con los ya seleccionados para no perder ningún valor histórico
      const setTotal = new Set();
      (clientesSeleccionados || []).forEach(c => { if (c && c.trim()) setTotal.add(c.trim().toUpperCase()); });
      (clientesDisponibles || []).forEach(c => { if (c && c.trim()) setTotal.add(c.trim().toUpperCase()); });

      const lista = Array.from(setTotal).sort((a, b) => a.localeCompare(b));
      if (lista.length === 0) {
        cont.innerHTML = '<p class="text-slate-400 italic text-[11px] p-2">No hay clientes registrados en el catálogo. Puedes escribir uno abajo.</p>';
        return;
      }

      const selSet = new Set((clientesSeleccionados || []).map(s => s.trim().toLowerCase()));
      cont.innerHTML = lista.map(c => {
        const isChecked = selSet.has(c.toLowerCase());
        return `
          <label class="flex items-center space-x-2 text-slate-800 text-xs cursor-pointer p-1 rounded-lg hover:bg-slate-50 transition-colors">
            <input type="checkbox" value="${c}" class="chk-cli-modal-${modo} rounded text-blue-600 focus:ring-blue-500" ${isChecked ? 'checked' : ''}>
            <span class="font-medium">${c}</span>
          </label>
        `;
      }).join('');
    }

    function agregarClienteCustomModal(modo) {
      const inpId = modo === 'nuevo' ? 'usr_cliente_custom_nuevo' : 'edit_usr_cliente_custom';
      const inp = document.getElementById(inpId);
      if (!inp) return;
      const val = inp.value.trim().toUpperCase();
      if (!val) return;

      const contId = modo === 'nuevo' ? 'usr_lista_clientes_check_nuevo' : 'edit_usr_lista_clientes_check';
      const cont = document.getElementById(contId);
      if (!cont) return;

      // Verificar si ya existe el checkbox
      const existentes = Array.from(cont.querySelectorAll(`.chk-cli-modal-${modo}`)).map(el => el.value.toLowerCase());
      if (existentes.includes(val.toLowerCase())) {
        const chk = Array.from(cont.querySelectorAll(`.chk-cli-modal-${modo}`)).find(el => el.value.toLowerCase() === val.toLowerCase());
        if (chk) chk.checked = true;
      } else {
        const lbl = document.createElement('label');
        lbl.className = 'flex items-center space-x-2 text-slate-800 text-xs cursor-pointer p-1 rounded-lg hover:bg-slate-50 transition-colors';
        lbl.innerHTML = `
          <input type="checkbox" value="${val}" class="chk-cli-modal-${modo} rounded text-blue-600 focus:ring-blue-500" checked>
          <span class="font-medium">${val}</span>
        `;
        cont.prepend(lbl);
      }
      inp.value = '';
    }

    function obtenerVistasSeleccionadasModal(modo) {
      const pfx = modo === 'nuevo' ? 'usr_' : 'edit_usr_';
      const rol = document.getElementById(`${pfx}rol`).value;
      if (rol === 'admin') {
        return 'patio,basedatos,diagnostico,kpis,composicion,bodegas,catalogos';
      }
      const vistas = [];
      if (document.getElementById(`${pfx}vista_patio`)?.checked) vistas.push('patio');
      if (document.getElementById(`${pfx}vista_basedatos`)?.checked && (rol === 'jefatura' || rol === 'gerencia')) vistas.push('basedatos');
      if (document.getElementById(`${pfx}vista_diagnostico`)?.checked) vistas.push('diagnostico');
      if (document.getElementById(`${pfx}vista_kpis`)?.checked) vistas.push('kpis');
      if (document.getElementById(`${pfx}vista_composicion`)?.checked) vistas.push('composicion');
      if (document.getElementById(`${pfx}vista_catalogos`)?.checked) vistas.push('catalogos');
      // Seguridad inquebrantable: NUNCA añadir basedatos para inspector
      if (vistas.length === 0) vistas.push(rol === 'gerencia' ? 'diagnostico' : 'patio');
      return vistas.join(',');
    }

    function obtenerClientesSeleccionadosModal(modo) {
      const pfx = modo === 'nuevo' ? 'usr_' : 'edit_usr_';
      const chkTodas = document.getElementById(`${pfx}todas_flotas`);
      if (chkTodas && chkTodas.checked) {
        return '';
      }
      const checkboxes = document.querySelectorAll(`.chk-cli-modal-${modo}:checked`);
      const seleccionados = Array.from(checkboxes).map(c => c.value.trim()).filter(Boolean);
      return seleccionados.join(', ');
    }

    function configurarClientesUsuarioEnInspeccion() {
      if (!usuarioActual) return;
      const selCli = document.getElementById('cliente');
      const badgeFijo = document.getElementById('badgeClienteAsignadoFijo');
      if (!selCli) return;

      let rawClis = [];
      if (Array.isArray(usuarioActual.clientes_asignados) && usuarioActual.clientes_asignados.length > 0) {
        rawClis = usuarioActual.clientes_asignados;
      } else if (usuarioActual.cliente_asignado && typeof usuarioActual.cliente_asignado === 'string') {
        rawClis = usuarioActual.cliente_asignado.split(',');
      }

      // Normalizar a mayúsculas limpias y deduplicar insensible a mayúsculas
      const mapClis = new Map();
      rawClis.forEach(c => {
        const clean = String(c || '').trim().toUpperCase();
        if (clean && !mapClis.has(clean)) {
          mapClis.set(clean, clean);
        }
      });
      const clis = Array.from(mapClis.values()).sort();

      if (!esUsuarioAdmin() && clis.length === 1) {
        // REGLA: Si es solo un cliente, en la inspección aparecerá predeterminado y fijo
        const cliUnico = clis[0];

        let existeOpcion = false;
        for (let i = 0; i < selCli.options.length; i++) {
          if (selCli.options[i].value.toUpperCase() === cliUnico) {
            existeOpcion = true;
            selCli.selectedIndex = i;
            break;
          }
        }
        if (!existeOpcion) {
          const opt = document.createElement('option');
          opt.value = cliUnico;
          opt.textContent = cliUnico;
          opt.selected = true;
          selCli.appendChild(opt);
        }
        selCli.value = cliUnico;
        selCli.disabled = true;
        selCli.classList.add('bg-slate-100', 'text-slate-700', 'cursor-not-allowed');
        selCli.classList.remove('bg-slate-50');

        if (badgeFijo) {
          badgeFijo.classList.remove('hidden');
          badgeFijo.innerHTML = `<i class="fa-solid fa-lock text-[9px] mr-1"></i><span>${cliUnico}</span>`;
        }

        alCambiarClienteMobile();
      } else if (!esUsuarioAdmin() && clis.length > 1) {
        // REGLA: Múltiples clientes asignados
        selCli.disabled = false;
        selCli.classList.remove('bg-slate-100', 'cursor-not-allowed');
        selCli.classList.add('bg-slate-50');

        if (badgeFijo) {
          badgeFijo.classList.remove('hidden');
          badgeFijo.innerHTML = `<i class="fa-solid fa-building-user text-[9px] mr-1"></i><span>${clis.length} Flotas</span>`;
        }

        const valorPrevio = selCli.value ? selCli.value.trim().toUpperCase() : '';
        let html = `<option value="" disabled ${!valorPrevio ? 'selected' : ''} class="text-slate-400 font-normal">Seleccionar cliente (${clis.length} asignados)</option>`;
        clis.forEach(c => {
          const isSel = (valorPrevio && valorPrevio === c);
          html += `<option value="${c}" ${isSel ? 'selected' : ''}>${c}</option>`;
        });
        selCli.innerHTML = html;
        if (valorPrevio && clis.includes(valorPrevio)) {
          selCli.value = valorPrevio;
        }
      } else {
        // Administrador o Todas las flotas
        selCli.disabled = false;
        selCli.classList.remove('bg-slate-100', 'cursor-not-allowed');
        selCli.classList.add('bg-slate-50');
        if (badgeFijo) badgeFijo.classList.add('hidden');
      }
    }

    function abrirModalNuevoUsuario() {
      document.getElementById('usr_username').value = '';
      document.getElementById('usr_nombre').value = '';
      document.getElementById('usr_pass').value = '';
      document.getElementById('usr_rol').value = 'inspector';
      document.getElementById('usr_vista_patio').checked = true;
      document.getElementById('usr_vista_diagnostico').checked = true;
      document.getElementById('usr_vista_kpis').checked = true;
      document.getElementById('usr_vista_composicion').checked = true;
      document.getElementById('usr_vista_catalogos').checked = true;
      document.getElementById('usr_todas_flotas').checked = true;
      document.getElementById('usr_cliente_custom_nuevo').value = '';
      toggleClientesTodosModal('nuevo');
      alCambiarRolUsuarioModal('nuevo');
      poblarListaCheckboxesClientesModal('nuevo', []);

      // Solo el admin puede asignar el rol admin
      const optAdminNuevo = document.querySelector('#usr_rol option[value="admin"]');
      if (optAdminNuevo) {
        optAdminNuevo.disabled = !esUsuarioAdmin();
      }

      const modal = document.getElementById('modalNuevoUsuario');
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    function cerrarModalNuevoUsuario() {
      const modal = document.getElementById('modalNuevoUsuario');
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }

    async function guardarNuevoUsuario() {
      const u = document.getElementById('usr_username').value.trim();
      const n = document.getElementById('usr_nombre').value.trim();
      const p = document.getElementById('usr_pass').value.trim();
      if (!u || !n || !p) {
        alert('Por favor completa todos los campos del usuario.');
        return;
      }
      if (p.length < 4) {
        alert('La contraseña debe tener al menos 4 caracteres.');
        return;
      }
      const rol = document.getElementById('usr_rol').value;
      if (rol === 'admin' && !esUsuarioAdmin()) {
        alert('Solo un administrador puede crear usuarios con rol Administrador.');
        return;
      }

      const vistas = obtenerVistasSeleccionadasModal('nuevo');
      const cliente = obtenerClientesSeleccionadosModal('nuevo');

      try {
        const res = await fetch('/api/usuarios', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            username: u,
            nombre_completo: n,
            password: p,
            rol: rol,
            cliente_asignado: cliente,
            vistas_permitidas: vistas
          })
        });
        if (res.ok) {
          cerrarModalNuevoUsuario();
          mostrarToast(`✅ Usuario "${u}" creado exitosamente.`);
          cargarUsuariosCat();
        } else {
          const d = await res.json();
          mostrarToast(d.detail || 'Error al crear usuario', true);
        }
      } catch (e) {
        mostrarToast('Error de conexión con el servidor', true);
      }
    }

    function abrirModalEditarUsuario(username) {
      const u = usuariosCatCache.find(x => x.username.toLowerCase() === username.toLowerCase());
      if (!u) return;
      document.getElementById('edit_usr_username').value = u.username;
      document.getElementById('edit_usr_nombre').value = u.nombre_completo;
      document.getElementById('edit_usr_rol').value = u.rol;
      document.getElementById('edit_usr_activo').value = u.activo ? '1' : '0';
      document.getElementById('edit_usr_cliente_custom').value = '';

      const errBox = document.getElementById('edit_usr_error');
      if (errBox) errBox.classList.add('hidden');

      const esSuperAdmin = u.username.toLowerCase() === 'admin';
      document.getElementById('edit_usr_rol').disabled = esSuperAdmin;
      document.getElementById('edit_usr_activo').disabled = esSuperAdmin;

      // Solo el admin puede asignar el rol admin
      const optAdminEdit = document.querySelector('#edit_usr_rol option[value="admin"]');
      if (optAdminEdit) {
        optAdminEdit.disabled = !esUsuarioAdmin();
      }

      alCambiarRolUsuarioModal('editar');

      // Vistas permitidas
      let vistas = [];
      if (Array.isArray(u.vistas_permitidas)) {
        vistas = u.vistas_permitidas.map(s => String(s).trim().toLowerCase());
      } else if (typeof u.vistas_permitidas === 'string' && u.vistas_permitidas.trim()) {
        vistas = u.vistas_permitidas.split(',').map(s => s.trim().toLowerCase());
      } else {
        vistas = ['patio', 'diagnostico', 'kpis', 'composicion', 'catalogos'];
      }
      document.getElementById('edit_usr_vista_patio').checked = vistas.includes('patio');
      if (document.getElementById('edit_usr_vista_basedatos')) {
        document.getElementById('edit_usr_vista_basedatos').checked = vistas.includes('basedatos') && u.rol !== 'inspector';
      }
      document.getElementById('edit_usr_vista_diagnostico').checked = vistas.includes('diagnostico');
      document.getElementById('edit_usr_vista_kpis').checked = vistas.includes('kpis');
      if (document.getElementById('edit_usr_vista_composicion')) {
        document.getElementById('edit_usr_vista_composicion').checked = vistas.includes('composicion');
      }
      document.getElementById('edit_usr_vista_catalogos').checked = vistas.includes('catalogos');

      // Clientes asignados
      let clis = [];
      if (Array.isArray(u.clientes_asignados) && u.clientes_asignados.length > 0) {
        clis = u.clientes_asignados;
      } else if (u.cliente_asignado) {
        clis = u.cliente_asignado.split(',').map(s => s.trim()).filter(Boolean);
      }

      if (clis.length === 0) {
        document.getElementById('edit_usr_todas_flotas').checked = true;
      } else {
        document.getElementById('edit_usr_todas_flotas').checked = false;
      }
      toggleClientesTodosModal('editar');
      poblarListaCheckboxesClientesModal('editar', clis);

      const modal = document.getElementById('modalEditarUsuario');
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    function cerrarModalEditarUsuario() {
      const modal = document.getElementById('modalEditarUsuario');
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }

    async function guardarEdicionUsuario() {
      const username = document.getElementById('edit_usr_username').value.trim();
      const nombre = document.getElementById('edit_usr_nombre').value.trim();
      const rol = document.getElementById('edit_usr_rol').value;
      const activo = document.getElementById('edit_usr_activo').value === '1';
      const vistas = obtenerVistasSeleccionadasModal('editar');
      const cliente = obtenerClientesSeleccionadosModal('editar');
      const errBox = document.getElementById('edit_usr_error');
      if (errBox) errBox.classList.add('hidden');

      if (!nombre) {
        if (errBox) {
          errBox.textContent = 'El nombre completo es obligatorio.';
          errBox.classList.remove('hidden');
        }
        return;
      }

      if (rol === 'admin' && !esUsuarioAdmin()) {
        if (errBox) {
          errBox.textContent = 'Solo un administrador puede asignar el rol Administrador.';
          errBox.classList.remove('hidden');
        }
        return;
      }

      try {
        const res = await fetch(`/api/usuarios/${username}`, {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            nombre_completo: nombre,
            rol: rol,
            cliente_asignado: cliente,
            vistas_permitidas: vistas,
            activo: activo
          })
        });
        const d = await res.json();
        if (res.ok) {
          if (usuarioActual && usuarioActual.username.toLowerCase() === username.toLowerCase()) {
            usuarioActual.nombre_completo = nombre;
            usuarioActual.rol = rol;
            usuarioActual.cliente_asignado = cliente;
            usuarioActual.clientes_asignados = cliente ? cliente.split(',').map(s => s.trim().toUpperCase()).filter(Boolean) : [];
            usuarioActual.vistas_permitidas = vistas;
            localStorage.setItem('tireanalyze_usuario_sesion', JSON.stringify(usuarioActual));
            localStorage.setItem('tirecheck_usuario_sesion', JSON.stringify(usuarioActual));
            actualizarUIUsuario();
            configurarClientesUsuarioEnInspeccion();
          }

          cerrarModalEditarUsuario();
          mostrarToast(`✅ Usuario "${username}" actualizado correctamente.`);
          cargarUsuariosCat();
          sincronizarUsuarioActualSesion();
        } else {
          if (errBox) {
            errBox.textContent = d.detail || 'Error al actualizar el usuario.';
            errBox.classList.remove('hidden');
          }
        }
      } catch (e) {
        if (errBox) {
          errBox.textContent = 'Error de conexión con el servidor.';
          errBox.classList.remove('hidden');
        }
      }
    }

    let targetResetUser = null;

    function abrirModalResetPassword(username) {
      targetResetUser = username;
      document.getElementById('reset_usr_label').textContent = username;
      document.getElementById('reset_nueva_password').value = '';
      document.getElementById('reset_confirmar_password').value = '';
      const errBox = document.getElementById('reset_password_error');
      if (errBox) errBox.classList.add('hidden');

      const modal = document.getElementById('modalResetPassword');
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    function cerrarModalResetPassword() {
      targetResetUser = null;
      const modal = document.getElementById('modalResetPassword');
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }

    function togglePasswordVisibility(inputId, iconId) {
      const inp = document.getElementById(inputId);
      const ico = document.getElementById(iconId);
      if (!inp || !ico) return;
      if (inp.type === 'password') {
        inp.type = 'text';
        ico.classList.remove('fa-eye');
        ico.classList.add('fa-eye-slash');
      } else {
        inp.type = 'password';
        ico.classList.remove('fa-eye-slash');
        ico.classList.add('fa-eye');
      }
    }

    async function ejecutarResetPassword() {
      if (!targetResetUser) return;
      const p1 = document.getElementById('reset_nueva_password').value.trim();
      const p2 = document.getElementById('reset_confirmar_password').value.trim();
      const errBox = document.getElementById('reset_password_error');
      if (errBox) errBox.classList.add('hidden');

      if (!p1 || p1.length < 4) {
        if (errBox) {
          errBox.textContent = 'La nueva contraseña debe tener al menos 4 caracteres.';
          errBox.classList.remove('hidden');
        }
        return;
      }

      if (p1 !== p2) {
        if (errBox) {
          errBox.textContent = 'Las contraseñas no coinciden. Por favor verifícalas.';
          errBox.classList.remove('hidden');
        }
        return;
      }

      try {
        const res = await fetch(`/api/usuarios/${targetResetUser}/reset-password`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ nueva_password: p1 })
        });
        const d = await res.json();
        if (res.ok) {
          cerrarModalResetPassword();
          mostrarToast(`🔑 Contraseña restablecida exitosamente para "${targetResetUser}".`);
        } else {
          if (errBox) {
            errBox.textContent = d.detail || 'Error al restablecer la contraseña.';
            errBox.classList.remove('hidden');
          }
        }
      } catch (e) {
        if (errBox) {
          errBox.textContent = 'Error de conexión con el servidor.';
          errBox.classList.remove('hidden');
        }
      }
    }

    async function eliminarUsuarioCat(username) {
      if (!confirm(`¿Eliminar al usuario "${username}"?`)) return;
      const res = await fetch(`/api/usuarios/${username}`, { method: 'DELETE' });
      if (res.ok) {
        mostrarToast(`Usuario ${username} eliminado.`);
        cargarUsuariosCat();
      } else {
        const d = await res.json();
        mostrarToast(d.detail || 'Error al eliminar usuario', true);
      }
    }


