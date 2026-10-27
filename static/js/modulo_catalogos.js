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
      if ((subtab === 'clientes' || subtab === 'marcas_cliente' || subtab === 'precios_cliente' || subtab === 'directorio_clientes') && !puedeVerClientes) {
        subtab = 'operaciones';
      }
      const tabs = ['directorio_clientes', 'operaciones', 'tipologias', 'modelos', 'clientes', 'marcas_cliente', 'precios_cliente', 'usuarios'];
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
      } else if (subtab === 'precios_cliente' && puedeVerClientes) {
        cargarPreciosClienteCat();
      } else if (subtab === 'marcas_cliente' && puedeVerClientes) {
        cargarMarcasClienteCat();
        cargarMaximosReencaucheCat();
        cargarStockSeguridadCat();
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
      document.getElementById('nuevo_cliente_meta_reencauche').value = '70';
      document.getElementById('nuevo_cliente_aprob_reencauche').value = '85';
      document.getElementById('nuevo_cliente_stock_seguridad').value = '4';
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
      document.getElementById('nuevo_cliente_meta_reencauche').value = cli.meta_reencauche_pct ?? 70;
      document.getElementById('nuevo_cliente_aprob_reencauche').value = cli.porcentaje_aprobacion_reencauche ?? 85;
      document.getElementById('nuevo_cliente_stock_seguridad').value = cli.stock_seguridad_default ?? 4;
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
        meta_reencauche_pct: parseFloat(document.getElementById('nuevo_cliente_meta_reencauche').value),
        porcentaje_aprobacion_reencauche: parseFloat(document.getElementById('nuevo_cliente_aprob_reencauche').value),
        stock_seguridad_default: parseInt(document.getElementById('nuevo_cliente_stock_seguridad').value, 10),
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
                  <div class="flex items-center space-x-1.5">
                    ${t.permite_reencauche_direccion ? `<span class="text-[10px] font-black bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-full" title="Esta tipología permite llantas reencauchadas en eje direccional">Reencauche Dir.</span>` : ''}
                    <span class="text-xs font-bold bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">${t.cant_llantas} llantas</span>
                  </div>
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
    let catalogoModelosFiltrados = null;

    async function cargarModelosCat() {
      const res = await fetch('/api/modelos-llanta');
      if (res.ok) {
        catalogoModelosCache = await res.json();
        poblarOpcionesFiltrosModelosCat();
        filtrarModelosCat();
      }
    }

    function poblarOpcionesFiltrosModelosCat() {
      const lista = catalogoModelosCache || [];
      const selMarca = document.getElementById('filtroMarcaModelosCat');
      const selDim = document.getElementById('filtroDimensionModelosCat');

      if (selMarca) {
        const valActual = selMarca.value || 'TODAS';
        const marcas = Array.from(new Set(lista.map(m => String(m.marca || '').trim().toUpperCase()).filter(Boolean))).sort();
        selMarca.innerHTML = '<option value="TODAS">Todas las marcas</option>' +
          marcas.map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('');
        if (marcas.includes(valActual)) {
          selMarca.value = valActual;
        } else {
          selMarca.value = 'TODAS';
        }
      }

      if (selDim) {
        const valActual = selDim.value || 'TODAS';
        const dims = Array.from(new Set(lista.map(m => String(m.dimension || '').trim().toUpperCase()).filter(Boolean))).sort();
        selDim.innerHTML = '<option value="TODAS">Todas las dimensiones</option>' +
          dims.map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
        if (dims.includes(valActual)) {
          selDim.value = valActual;
        } else {
          selDim.value = 'TODAS';
        }
      }
    }

    function limpiarBuscadorModelosCat() {
      const elB = document.getElementById('filtroBuscadorModelosCat');
      if (elB) elB.value = '';
      filtrarModelosCat();
    }

    function limpiarFiltrosModelosCat() {
      const elB = document.getElementById('filtroBuscadorModelosCat');
      if (elB) elB.value = '';
      const elT = document.getElementById('filtroTipoModelosCat');
      if (elT) elT.value = 'TODOS';
      const elM = document.getElementById('filtroMarcaModelosCat');
      if (elM) elM.value = 'TODAS';
      const elD = document.getElementById('filtroDimensionModelosCat');
      if (elD) elD.value = 'TODAS';
      filtrarModelosCat();
    }

    function filtrarModelosCat() {
      const q = (document.getElementById('filtroBuscadorModelosCat')?.value || '').trim().toLowerCase();
      const fTipo = (document.getElementById('filtroTipoModelosCat')?.value || 'TODOS').trim().toUpperCase();
      const fMarca = (document.getElementById('filtroMarcaModelosCat')?.value || 'TODAS').trim().toUpperCase();
      const fDim = (document.getElementById('filtroDimensionModelosCat')?.value || 'TODAS').trim().toUpperCase();

      const btnLimpiar = document.getElementById('btnLimpiarFiltrosModelosCat');
      const btnLimpiarBuscador = document.getElementById('btnLimpiarBuscadorModelosCat');
      const hayFiltros = Boolean(q) || fTipo !== 'TODOS' || fMarca !== 'TODAS' || fDim !== 'TODAS';

      if (btnLimpiar) {
        btnLimpiar.classList.toggle('hidden', !hayFiltros);
        btnLimpiar.classList.toggle('flex', hayFiltros);
      }
      if (btnLimpiarBuscador) {
        btnLimpiarBuscador.classList.toggle('hidden', !q);
      }

      const lista = catalogoModelosCache || [];
      catalogoModelosFiltrados = lista.filter(m => {
        if (fTipo !== 'TODOS') {
          const t = String(m.tipo_llanta || '').trim().toUpperCase();
          if (t !== fTipo) return false;
        }
        if (fMarca !== 'TODAS') {
          const ma = String(m.marca || '').trim().toUpperCase();
          if (ma !== fMarca) return false;
        }
        if (fDim !== 'TODAS') {
          const d = String(m.dimension || '').trim().toUpperCase();
          if (d !== fDim) return false;
        }
        if (q) {
          const texto = `${m.marca || ''} ${m.diseno || ''} ${m.dimension || ''} ${m.tipo_llanta || ''} ${m.descripcion || ''} ${m.prof_inicial || ''}`.toLowerCase();
          if (!texto.includes(q)) return false;
        }
        return true;
      });

      const badge = document.getElementById('badgeContadorModelosCat');
      if (badge) {
        if (hayFiltros) {
          badge.textContent = `${catalogoModelosFiltrados.length} de ${lista.length} modelos`;
          badge.classList.remove('hidden');
        } else if (lista.length > 0) {
          badge.textContent = `${lista.length} modelos`;
          badge.classList.remove('hidden');
        } else {
          badge.classList.add('hidden');
        }
      }

      paginaActualModelosCat = 1;
      renderizarTablaModelosCat();
    }

    function renderizarTablaModelosCat() {
      const tbody = document.getElementById('tbodyModelosCat');
      const contenedor = document.getElementById('contenedorPaginacionModelosCat');
      if (!tbody) return;

      const lista = catalogoModelosFiltrados !== null ? catalogoModelosFiltrados : (catalogoModelosCache || []);
      const totalOriginal = (catalogoModelosCache || []).length;
      const hayFiltros = catalogoModelosFiltrados !== null && catalogoModelosFiltrados.length !== totalOriginal;

      if (lista.length === 0) {
        const msg = hayFiltros
          ? 'No se encontraron modelos que coincidan con los filtros aplicados. <button type="button" onclick="limpiarFiltrosModelosCat()" class="ml-1 text-blue-600 hover:underline font-bold cursor-pointer">Limpiar filtros</button>'
          : 'No hay modelos de llanta registrados.';
        tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-slate-400 font-medium">${msg}</td></tr>`;
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
          <td class="p-2.5 font-bold">${escapeHtml(m.tipo_llanta || '')}</td>
          <td class="p-2.5 font-black text-slate-900">${escapeHtml(m.marca || '')}</td>
          <td class="p-2.5 font-bold text-slate-800">${escapeHtml(m.diseno || '')}</td>
          <td class="p-2.5 text-slate-700">${escapeHtml(m.dimension || '')}</td>
          <td class="p-2.5 text-center font-mono font-black text-blue-700">${m.prof_inicial} mm</td>
          <td class="p-2.5 text-slate-500">${escapeHtml(m.descripcion || '-')}</td>
          <td class="p-2.5 text-center">
            ${puedeEditar ? `
              <div class="flex items-center justify-center space-x-1">
                <button type="button" onclick="abrirModalEditarModelo(${m.id})" class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded-lg hover:bg-blue-50 font-bold transition-all cursor-pointer" title="Editar modelo y sincronizar prof. inicial en BD">
                  <i class="fa-solid fa-pen-to-square"></i>
                </button>
                <button type="button" onclick="eliminarModeloCat(${m.id}, '${encodeURIComponent((m.marca || '') + ' ' + (m.diseno || ''))}')" class="text-rose-600 hover:text-rose-800 text-xs px-2 py-1 rounded-lg hover:bg-rose-50 font-bold transition-all cursor-pointer" title="Eliminar modelo del catálogo">
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

      // Poblar datalists sugeridos
      const dlM = document.getElementById('dl_marcas_modelo_catalogo');
      if (dlM) dlM.innerHTML = obtenerListaMarcasDisponibles().map(m => `<option value="${escapeHtml(m)}">`).join('');
      const dlD = document.getElementById('dl_dimensiones_modelo_catalogo');
      if (dlD) dlD.innerHTML = obtenerListaDimensionesDisponibles().map(d => `<option value="${escapeHtml(d)}">`).join('');

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

      // Poblar datalists sugeridos
      const dlM = document.getElementById('dl_marcas_modelo_catalogo');
      if (dlM) dlM.innerHTML = obtenerListaMarcasDisponibles().map(x => `<option value="${escapeHtml(x)}">`).join('');
      const dlD = document.getElementById('dl_dimensiones_modelo_catalogo');
      if (dlD) dlD.innerHTML = obtenerListaDimensionesDisponibles().map(d => `<option value="${escapeHtml(d)}">`).join('');

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

    // ==========================================
    // HELPERS GLOBALES DE CATÁLOGOS
    // ==========================================
    function obtenerListaClientesDisponibles() {
      const set = new Set();
      (cacheDirectorioClientes || []).forEach(c => {
        if (c.cliente) set.add(c.cliente.trim().toUpperCase());
      });
      (catalogoLimitesCache || []).forEach(c => {
        if (c.cliente) set.add(c.cliente.trim().toUpperCase());
      });
      (marcasClienteCatCache || []).forEach(m => {
        if (m.cliente) set.add(m.cliente.trim().toUpperCase());
      });
      (preciosClienteCatCache || []).forEach(p => {
        if (p.cliente) set.add(p.cliente.trim().toUpperCase());
      });
      return Array.from(set).filter(Boolean).sort();
    }

    function obtenerListaMarcasDisponibles() {
      const set = new Set();
      const comunes = [
        'MICHELIN', 'GOODYEAR', 'BRIDGESTONE', 'CONTINENTAL', 'FIRESTONE',
        'PIRELLI', 'HANKOOK', 'DOUBLE COIN', 'AEOLUS', 'TRIANGLE',
        'SAILUN', 'KUMHO', 'YOKOHAMA', 'DUNLOP', 'BANDAG', 'MARANGONI', 'VIPAL'
      ];
      comunes.forEach(m => set.add(m));
      (catalogoModelosCache || []).forEach(m => {
        if (m.marca) set.add(m.marca.trim().toUpperCase());
      });
      (marcasClienteCatCache || []).forEach(m => {
        if (m.marca) set.add(m.marca.trim().toUpperCase());
      });
      (preciosClienteCatCache || []).forEach(p => {
        if (p.marca) set.add(p.marca.trim().toUpperCase());
      });
      return Array.from(set).filter(Boolean).sort();
    }

    function obtenerListaDimensionesDisponibles() {
      const set = new Set();
      const comunes = [
        '295/80R22.5', '11R22.5', '12R22.5', '315/80R22.5', '275/70R22.5',
        '385/65R22.5', '12.00R24', '12.00R20', '7.50R16', '215/75R17.5',
        '225/70R19.5', '11.00R20', '10.00R20', '255/70R22.5'
      ];
      comunes.forEach(d => set.add(d));
      (catalogoModelosCache || []).forEach(m => {
        if (m.dimension) set.add(m.dimension.trim().toUpperCase());
      });
      (preciosClienteCatCache || []).forEach(p => {
        if (p.dimension) set.add(p.dimension.trim().toUpperCase());
      });
      return Array.from(set).filter(Boolean).sort();
    }

    let paginaActualLimitesCat = 1;
    const ITEMS_POR_PAGINA_LIMITES = 25;
    let catalogoLimitesFiltrados = null;

    async function cargarClientesLimCat() {
      const res = await fetch('/api/configuraciones-clientes');
      if (res.ok) {
        catalogoLimitesCache = await res.json();
        poblarFiltrosLimitesCat();
        filtrarLimitesCat();
      }
    }

    function poblarFiltrosLimitesCat() {
      const selCli = document.getElementById('filtroClienteLimitesCat');
      if (!selCli) return;
      const valPrev = selCli.value || 'TODOS';
      const clis = Array.from(new Set((catalogoLimitesCache || []).map(c => c.cliente))).sort();
      selCli.innerHTML = '<option value="TODOS">Todos los clientes</option>' +
        clis.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
      if (clis.includes(valPrev)) selCli.value = valPrev;
    }

    function filtrarLimitesCat() {
      const q = (document.getElementById('filtroBuscadorLimitesCat')?.value || '').trim().toLowerCase();
      const fCli = (document.getElementById('filtroClienteLimitesCat')?.value || 'TODOS').trim().toUpperCase();
      const fEje = (document.getElementById('filtroEjeLimitesCat')?.value || 'TODOS').trim().toUpperCase();

      const btnL = document.getElementById('btnLimpiarFiltrosLimitesCat');
      const hay = Boolean(q) || fCli !== 'TODOS' || fEje !== 'TODOS';
      if (btnL) {
        btnL.classList.toggle('hidden', !hay);
        btnL.classList.toggle('flex', hay);
      }

      const lista = catalogoLimitesCache || [];
      catalogoLimitesFiltrados = lista.filter(c => {
        if (fCli !== 'TODOS' && String(c.cliente || '').trim().toUpperCase() !== fCli) return false;
        if (fEje !== 'TODOS' && String(c.eje || 'TODOS').trim().toUpperCase() !== fEje) return false;
        if (q) {
          const t = `${c.cliente || ''} ${c.subcliente || ''} ${c.eje || ''} ${c.observaciones || ''} ${c.limite_retiro_mm || ''}`.toLowerCase();
          if (!t.includes(q)) return false;
        }
        return true;
      });

      paginaActualLimitesCat = 1;
      renderizarTablaLimitesCat();
    }

    function limpiarFiltrosLimitesCat() {
      const b = document.getElementById('filtroBuscadorLimitesCat');
      if (b) b.value = '';
      const c = document.getElementById('filtroClienteLimitesCat');
      if (c) c.value = 'TODOS';
      const e = document.getElementById('filtroEjeLimitesCat');
      if (e) e.value = 'TODOS';
      filtrarLimitesCat();
    }

    function renderizarTablaLimitesCat() {
      const tbody = document.getElementById('tbodyClientesLimCat');
      const contenedor = document.getElementById('contenedorPaginacionLimitesCat');
      if (!tbody) return;

      const lista = catalogoLimitesFiltrados !== null ? catalogoLimitesFiltrados : (catalogoLimitesCache || []);
      if (lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-400 italic font-medium">No se encontraron límites configurados con los filtros aplicados.</td></tr>`;
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
            <td class="p-2.5 font-black text-slate-900">${escapeHtml(c.cliente)}</td>
            <td class="p-2.5 font-bold text-slate-700">${escapeHtml(c.subcliente || 'TODOS')}</td>
            <td class="p-2.5 text-center">${badgeEje}</td>
            <td class="p-2.5 text-center font-black text-rose-700 font-mono text-sm">${c.limite_retiro_mm} mm</td>
            <td class="p-2.5 text-slate-600">${escapeHtml(c.observaciones) || '-'}</td>
            <td class="p-2.5 text-center">
              <div class="flex items-center justify-center space-x-1">
                <button type="button" onclick="abrirModalEditarLimiteCliente(${c.id})" class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded-lg hover:bg-blue-50 font-bold transition-all cursor-pointer" title="Editar límite de retiro">
                  <i class="fa-solid fa-pen-to-square"></i>
                </button>
                <button type="button" onclick="eliminarLimiteCliente(${c.id})" class="text-rose-600 hover:text-rose-800 text-xs px-2 py-1 rounded-lg hover:bg-rose-50 font-bold transition-all cursor-pointer" title="Eliminar regla de límite">
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

    function alCambiarClienteModalLimite() {
      const cli = (document.getElementById('lim_cliente')?.value || '').trim().toUpperCase();
      const selSub = document.getElementById('lim_subcliente');
      const customSub = document.getElementById('lim_subcliente_custom');
      if (!selSub) return;

      if (customSub) {
        customSub.classList.add('hidden');
        customSub.value = '';
      }

      const clienteObj = (cacheDirectorioClientes || []).find(c => (c.cliente || '').toUpperCase() === cli);
      const subclientes = (clienteObj && clienteObj.subclientes) ? clienteObj.subclientes : [];

      let html = '<option value="TODOS">TODOS (Toda la flota)</option>';
      subclientes.forEach(s => {
        if (s && s.toUpperCase() !== 'TODOS') {
          html += `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`;
        }
      });
      html += '<option value="__OTRA__">+ Escribir otra sede...</option>';
      selSub.innerHTML = html;
    }

    function alCambiarSubclienteModalLimite() {
      const selSub = document.getElementById('lim_subcliente');
      const customSub = document.getElementById('lim_subcliente_custom');
      if (!selSub || !customSub) return;
      if (selSub.value === '__OTRA__') {
        customSub.classList.remove('hidden');
        customSub.focus();
      } else {
        customSub.classList.add('hidden');
        customSub.value = '';
      }
    }

    function abrirModalLimiteCliente() {
      limiteClienteEditandoId = null;
      const elTit = document.getElementById('tituloModalLimiteCliente');
      if (elTit) elTit.textContent = 'Límite de Retiro por Cliente y Eje';
      const elBtn = document.getElementById('btnGuardarLimiteTexto');
      if (elBtn) elBtn.textContent = 'Guardar Límite';

      // Poblar selector de clientes
      const selCli = document.getElementById('lim_cliente');
      if (selCli) {
        const clientes = obtenerListaClientesDisponibles();
        selCli.innerHTML = '<option value="">-- Seleccionar Cliente --</option>' +
          clientes.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
        selCli.value = '';
      }

      alCambiarClienteModalLimite();
      document.getElementById('lim_eje').value = 'TODOS';
      document.getElementById('lim_mm').value = '3.0';
      document.getElementById('lim_obs').value = '';
      document.getElementById('modalLimiteCliente').classList.remove('hidden');
      document.getElementById('modalLimiteCliente').classList.add('flex');
    }

    function abrirModalEditarLimiteCliente(id) {
      const c = (catalogoLimitesCache || []).find(x => x.id === id);
      if (!c) return;
      limiteClienteEditandoId = id;
      const elTit = document.getElementById('tituloModalLimiteCliente');
      if (elTit) elTit.textContent = `Editar Límite: ${c.cliente}`;
      const elBtn = document.getElementById('btnGuardarLimiteTexto');
      if (elBtn) elBtn.textContent = 'Guardar Cambios';

      // Poblar selector de clientes
      const selCli = document.getElementById('lim_cliente');
      if (selCli) {
        const clientes = obtenerListaClientesDisponibles();
        if (!clientes.includes(c.cliente)) clientes.push(c.cliente);
        selCli.innerHTML = '<option value="">-- Seleccionar Cliente --</option>' +
          clientes.sort().map(cli => `<option value="${escapeHtml(cli)}">${escapeHtml(cli)}</option>`).join('');
        selCli.value = c.cliente;
      }

      alCambiarClienteModalLimite();

      // Ajustar valor de sede
      const selSub = document.getElementById('lim_subcliente');
      const customSub = document.getElementById('lim_subcliente_custom');
      const subVal = c.subcliente || 'TODOS';
      if (selSub) {
        const opciones = Array.from(selSub.options).map(o => o.value);
        if (opciones.includes(subVal)) {
          selSub.value = subVal;
          if (customSub) customSub.classList.add('hidden');
        } else {
          selSub.value = '__OTRA__';
          if (customSub) {
            customSub.classList.remove('hidden');
            customSub.value = subVal;
          }
        }
      }

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
      const cli = (document.getElementById('lim_cliente')?.value || '').trim().toUpperCase();
      const selSub = document.getElementById('lim_subcliente')?.value || 'TODOS';
      const customSub = (document.getElementById('lim_subcliente_custom')?.value || '').trim().toUpperCase();
      const sub = (selSub === '__OTRA__' ? customSub : selSub) || 'TODOS';
      const eje = (document.getElementById('lim_eje')?.value || 'TODOS').trim().toUpperCase();
      const mm = parseFloat(document.getElementById('lim_mm')?.value);
      const obs = (document.getElementById('lim_obs')?.value || '').trim().toUpperCase();

      if (!cli) {
        alert('Por favor selecciona un cliente de la lista desplegable.');
        return;
      }
      if (isNaN(mm) || mm <= 0) {
        alert('Por favor ingresa un límite de retiro válido en mm.');
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

    // ==========================================
    // PRECIOS POR CLIENTE (TARIFARIO & EXCEL)
    // ==========================================
    let preciosClienteCatCache = [];
    let cacheFiltradosPreciosCat = [];
    let paginaActualPreciosCat = 1;
    const ITEMS_POR_PAGINA_PRECIOS = 20;
    let idPrecioEnEdicion = null;
    let archivoPreciosExcelSeleccionado = null;

    async function cargarPreciosClienteCat() {
      const tbody = document.getElementById('tbodyPreciosCliente');
      if (!tbody) return;
      const desde = document.getElementById('precio_desde');
      if (desde && !desde.value) desde.value = new Date().toISOString().slice(0, 10);

      try {
        const res = await fetch('/api/precios-cliente');
        const lista = res.ok ? await res.json() : [];
        preciosClienteCatCache = lista || [];

        // KPIs rápidos
        const total = preciosClienteCatCache.length;
        const clientesUnicos = Array.from(new Set(preciosClienteCatCache.map(p => p.cliente).filter(Boolean)));
        const nuevas = preciosClienteCatCache.filter(p => p.tipo === 'Original' && p.precio > 0);
        const promNueva = nuevas.length ? Math.round(nuevas.reduce((s, p) => s + Number(p.precio), 0) / nuevas.length) : 0;
        const reencauches = preciosClienteCatCache.filter(p => p.tipo === 'Reencauche' && p.precio > 0);
        const promReen = reencauches.length ? Math.round(reencauches.reduce((s, p) => s + Number(p.precio), 0) / reencauches.length) : 0;

        const elTot = document.getElementById('kpiPreciosTotal');
        if (elTot) elTot.textContent = `${total} tarifas`;
        const elCli = document.getElementById('kpiPreciosClientes');
        if (elCli) elCli.textContent = `${clientesUnicos.length} clientes`;
        const elPn = document.getElementById('kpiPreciosPromNueva');
        if (elPn) elPn.textContent = `$ ${promNueva.toLocaleString('es-CO')}`;
        const elPr = document.getElementById('kpiPreciosPromReen');
        if (elPr) elPr.textContent = `$ ${promReen.toLocaleString('es-CO')}`;

        // Poblar selector de cliente en el formulario
        const selCliForm = document.getElementById('precio_cli');
        if (selCliForm) {
          const valPrevio = selCliForm.value;
          const todosClientes = obtenerListaClientesDisponibles();
          selCliForm.innerHTML = '<option value="">-- Seleccionar Cliente --</option>' +
            todosClientes.map(c => `<option value="${c}">${c}</option>`).join('');
          if (valPrevio && todosClientes.includes(valPrevio)) {
            selCliForm.value = valPrevio;
          }
          alCambiarClienteFormPrecios();
        }

        // Poblar filtros de cliente y marca
        const selFiltroCli = document.getElementById('filtroClientePreciosCat');
        if (selFiltroCli) {
          const valPrev = selFiltroCli.value;
          const clientesFiltro = Array.from(new Set([...clientesUnicos, ...obtenerListaClientesDisponibles()])).sort();
          selFiltroCli.innerHTML = '<option value="TODOS">Todos los clientes</option>' +
            clientesFiltro.map(c => `<option value="${c}">${c}</option>`).join('');
          if (valPrev) selFiltroCli.value = valPrev;
        }

        const selFiltroMarca = document.getElementById('filtroMarcaPreciosCat');
        if (selFiltroMarca) {
          const valPrev = selFiltroMarca.value;
          const marcasFiltro = Array.from(new Set(preciosClienteCatCache.map(p => p.marca).filter(Boolean))).sort();
          selFiltroMarca.innerHTML = '<option value="TODAS">Todas las marcas</option>' +
            marcasFiltro.map(m => `<option value="${m}">${m}</option>`).join('');
          if (valPrev) selFiltroMarca.value = valPrev;
        }

        filtrarPreciosClienteCat();
      } catch (e) {
        console.error("Error al cargar precios:", e);
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="p-4 text-center text-rose-600">No se pudieron cargar los precios</td></tr>';
      }
    }

    function alCambiarClienteFormPrecios() {
      const cli = (document.getElementById('precio_cli')?.value || '').trim().toUpperCase();
      const selMarca = document.getElementById('precio_marca');
      if (!selMarca) return;

      const valPrevio = selMarca.value;
      const todasMarcas = obtenerListaMarcasDisponibles();

      const marcasAsociadas = (marcasClienteCatCache || [])
        .filter(m => m.cliente === cli)
        .map(m => m.marca);

      let opts = '<option value="">-- Marca --</option>';
      if (marcasAsociadas.length > 0) {
        opts += `<optgroup label="⭐ Marcas Habituales de ${cli}">`;
        marcasAsociadas.forEach(m => {
          opts += `<option value="${m}">${m}</option>`;
        });
        opts += `</optgroup>`;
        opts += `<optgroup label="Otras Marcas del Catálogo">`;
        todasMarcas.filter(m => !marcasAsociadas.includes(m)).forEach(m => {
          opts += `<option value="${m}">${m}</option>`;
        });
        opts += `</optgroup>`;
      } else {
        todasMarcas.forEach(m => {
          opts += `<option value="${m}">${m}</option>`;
        });
      }
      opts += '<option value="__OTRA__">+ Escribir otra marca...</option>';
      selMarca.innerHTML = opts;

      if (valPrevio && (todasMarcas.includes(valPrevio) || marcasAsociadas.includes(valPrevio))) {
        selMarca.value = valPrevio;
      }
      alCambiarMarcaFormPrecios();
    }

    function alCambiarMarcaFormPrecios() {
      const sel = document.getElementById('precio_marca');
      const custom = document.getElementById('precio_marca_custom');
      if (!sel) return;

      if (sel.value === '__OTRA__') {
        if (custom) {
          custom.classList.remove('hidden');
          custom.focus();
        }
      } else {
        if (custom) {
          custom.classList.add('hidden');
          custom.value = '';
        }
      }

      const marca = sel.value === '__OTRA__' ? (custom?.value || '').trim().toUpperCase() : sel.value.trim().toUpperCase();
      const dlDisenos = document.getElementById('dl_precio_disenos');
      const dlDims = document.getElementById('dl_precio_dimensiones');

      let disenosSugeridos = new Set();
      let dimsSugeridas = new Set(obtenerListaDimensionesDisponibles());

      if (typeof catalogoModelosCache !== 'undefined' && Array.isArray(catalogoModelosCache)) {
        catalogoModelosCache.forEach(m => {
          if (!marca || (m.marca && m.marca.toUpperCase() === marca)) {
            if (m.diseno) disenosSugeridos.add(m.diseno.toUpperCase());
            if (m.dimension) dimsSugeridas.add(m.dimension.toUpperCase());
          }
        });
      }

      if (dlDisenos) {
        dlDisenos.innerHTML = Array.from(disenosSugeridos).sort().map(d => `<option value="${d}">`).join('');
      }
      if (dlDims) {
        dlDims.innerHTML = Array.from(dimsSugeridas).sort().map(d => `<option value="${d}">`).join('');
      }
    }

    function alEscribirPrecioValor(val) {
      const preview = document.getElementById('previewPrecioCOP');
      if (!preview) return;
      const num = parseFloat(val) || 0;
      preview.textContent = `$ ${num.toLocaleString('es-CO')} COP`;
    }

    function filtrarPreciosClienteCat() {
      const txt = (document.getElementById('filtroBuscadorPreciosCat')?.value || '').trim().toLowerCase();
      const cli = (document.getElementById('filtroClientePreciosCat')?.value || 'TODOS').trim().toUpperCase();
      const mar = (document.getElementById('filtroMarcaPreciosCat')?.value || 'TODAS').trim().toUpperCase();
      const tip = (document.getElementById('filtroTipoPreciosCat')?.value || 'TODOS').trim();

      const btnLimpiar = document.getElementById('btnLimpiarFiltrosPreciosCat');
      if (btnLimpiar) {
        if (txt || cli !== 'TODOS' || mar !== 'TODAS' || tip !== 'TODOS') {
          btnLimpiar.classList.remove('hidden');
          btnLimpiar.classList.add('flex');
        } else {
          btnLimpiar.classList.add('hidden');
          btnLimpiar.classList.remove('flex');
        }
      }

      cacheFiltradosPreciosCat = (preciosClienteCatCache || []).filter(p => {
        if (cli !== 'TODOS' && p.cliente !== cli) return false;
        if (mar !== 'TODAS' && p.marca !== mar) return false;
        if (tip !== 'TODOS' && p.tipo !== tip) return false;
        if (txt) {
          const buscable = `${p.cliente} ${p.marca} ${p.diseno || ''} ${p.dimension} ${p.tipo}`.toLowerCase();
          if (!buscable.includes(txt)) return false;
        }
        return true;
      });

      paginaActualPreciosCat = 1;
      renderizarTablaPreciosCliente(cacheFiltradosPreciosCat);
    }

    function limpiarFiltrosPreciosCat() {
      const txt = document.getElementById('filtroBuscadorPreciosCat');
      if (txt) txt.value = '';
      const cli = document.getElementById('filtroClientePreciosCat');
      if (cli) cli.value = 'TODOS';
      const mar = document.getElementById('filtroMarcaPreciosCat');
      if (mar) mar.value = 'TODAS';
      const tip = document.getElementById('filtroTipoPreciosCat');
      if (tip) tip.value = 'TODOS';
      filtrarPreciosClienteCat();
    }

    function cambiarPaginaPrecios(p) {
      paginaActualPreciosCat = p;
      renderizarTablaPreciosCliente(cacheFiltradosPreciosCat);
    }

    function renderizarTablaPreciosCliente(lista) {
      const tbody = document.getElementById('tbodyPreciosCliente');
      const contenedor = document.getElementById('contenedorPaginacionPreciosCat');
      if (!tbody) return;

      lista = lista || [];

      if (lista.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="8" class="p-8 text-center text-slate-400">
              <i class="fa-solid fa-tags text-3xl mb-2 text-slate-300 block"></i>
              No se encontraron precios registrados con los filtros aplicados.
            </td>
          </tr>
        `;
        if (contenedor) contenedor.classList.add('hidden');
        return;
      }

      const totalRegistros = lista.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_PRECIOS) || 1;
      if (paginaActualPreciosCat > totalPaginas) paginaActualPreciosCat = totalPaginas;
      if (paginaActualPreciosCat < 1) paginaActualPreciosCat = 1;

      const inicio = (paginaActualPreciosCat - 1) * ITEMS_POR_PAGINA_PRECIOS;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_PRECIOS, totalRegistros);
      const paginaItems = lista.slice(inicio, fin);

      tbody.innerHTML = paginaItems.map(p => {
        const esNueva = p.tipo === 'Original';
        const badgeTipo = esNueva
          ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-50 text-emerald-700 border border-emerald-200">
              <i class="fa-solid fa-circle text-[6px] mr-1 text-emerald-500"></i> Llanta nueva
             </span>`
          : `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-50 text-amber-700 border border-amber-200">
              <i class="fa-solid fa-arrows-rotate text-[8px] mr-1 text-amber-500"></i> Reencauche
             </span>`;

        const disenoHtml = p.diseno && p.diseno.trim() && p.diseno !== 'TODOS'
          ? `<span class="font-semibold text-slate-700">${p.diseno}</span>`
          : `<span class="text-slate-400 italic font-mono text-[11px]">Todos</span>`;

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-3 font-bold text-slate-900">${p.cliente}</td>
            <td class="p-3">
              <span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-100">
                ${p.marca}
              </span>
            </td>
            <td class="p-3">${disenoHtml}</td>
            <td class="p-3 font-mono font-bold text-slate-700 text-xs">${p.dimension}</td>
            <td class="p-3 text-center">${badgeTipo}</td>
            <td class="p-3 text-right font-mono font-black text-slate-900 text-xs">
              $ ${Number(p.precio).toLocaleString('es-CO')}
            </td>
            <td class="p-3 text-center font-mono text-slate-500 text-[11px]">${p.vigente_desde || '-'}</td>
            <td class="p-3 text-center">
              <div class="inline-flex items-center space-x-1">
                <button type="button" onclick="editarPrecioClienteCat(${p.id})" class="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg font-bold text-xs transition-colors cursor-pointer" title="Modificar precio">
                  <i class="fa-solid fa-pen-to-square"></i>
                </button>
                <button type="button" onclick="eliminarPrecioClienteCat(${p.id})" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded-lg font-bold text-xs transition-colors cursor-pointer" title="Eliminar tarifa">
                  <i class="fa-solid fa-trash-can"></i>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      actualizarBarraPaginacionGenerica('PreciosCat', totalRegistros, inicio, fin, paginaActualPreciosCat, totalPaginas, 'cambiarPaginaPrecios');
    }

    function editarPrecioClienteCat(id) {
      const p = (preciosClienteCatCache || []).find(item => item.id === id);
      if (!p) return;

      idPrecioEnEdicion = id;

      const selCli = document.getElementById('precio_cli');
      if (selCli) {
        selCli.value = p.cliente;
        alCambiarClienteFormPrecios();
      }

      const selMarca = document.getElementById('precio_marca');
      const customMarca = document.getElementById('precio_marca_custom');
      if (selMarca) {
        const existe = Array.from(selMarca.options).some(o => o.value === p.marca);
        if (existe) {
          selMarca.value = p.marca;
          if (customMarca) customMarca.classList.add('hidden');
        } else {
          selMarca.value = '__OTRA__';
          if (customMarca) {
            customMarca.classList.remove('hidden');
            customMarca.value = p.marca;
          }
        }
        alCambiarMarcaFormPrecios();
      }

      const inpDiseno = document.getElementById('precio_diseno');
      if (inpDiseno) inpDiseno.value = p.diseno || '';

      const inpDim = document.getElementById('precio_dimension');
      if (inpDim) inpDim.value = p.dimension || '';

      const selTipo = document.getElementById('precio_tipo');
      if (selTipo) selTipo.value = p.tipo;

      const inpValor = document.getElementById('precio_valor');
      if (inpValor) {
        inpValor.value = p.precio;
        alEscribirPrecioValor(p.precio);
      }

      const inpDesde = document.getElementById('precio_desde');
      if (inpDesde) inpDesde.value = p.vigente_desde || '';

      const badge = document.getElementById('badgeModoPrecio');
      if (badge) {
        badge.classList.remove('bg-blue-600');
        badge.classList.add('bg-amber-500');
      }
      const tit = document.getElementById('tituloFormularioPrecio');
      if (tit) tit.textContent = 'Modificar Tarifa de Precio';
      const aviso = document.getElementById('avisoModoEdicionPrecio');
      if (aviso) aviso.classList.remove('hidden');
      const btnCancel = document.getElementById('btnCancelarEdicionPrecio');
      if (btnCancel) btnCancel.classList.remove('hidden');
      const btnTxt = document.getElementById('btnGuardarPrecioClienteTexto');
      if (btnTxt) btnTxt.textContent = 'Actualizar Tarifa';

      document.getElementById('cardFormularioPreciosCliente')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function cancelarEdicionPrecioCliente() {
      idPrecioEnEdicion = null;
      const f = document.getElementById('formPreciosClienteCat');
      if (f) f.reset();

      const customMarca = document.getElementById('precio_marca_custom');
      if (customMarca) {
        customMarca.classList.add('hidden');
        customMarca.value = '';
      }

      const badge = document.getElementById('badgeModoPrecio');
      if (badge) {
        badge.classList.add('bg-blue-600');
        badge.classList.remove('bg-amber-500');
      }
      const tit = document.getElementById('tituloFormularioPrecio');
      if (tit) tit.textContent = 'Registrar Nuevo Precio de Llanta';
      const aviso = document.getElementById('avisoModoEdicionPrecio');
      if (aviso) aviso.classList.add('hidden');
      const btnCancel = document.getElementById('btnCancelarEdicionPrecio');
      if (btnCancel) btnCancel.classList.add('hidden');
      const btnTxt = document.getElementById('btnGuardarPrecioClienteTexto');
      if (btnTxt) btnTxt.textContent = 'Guardar Precio';

      const preview = document.getElementById('previewPrecioCOP');
      if (preview) preview.textContent = '$ 0 COP';

      const desde = document.getElementById('precio_desde');
      if (desde) desde.value = new Date().toISOString().slice(0, 10);
    }

    async function guardarPrecioClienteCat(ev) {
      ev.preventDefault();
      const v = id => (document.getElementById(id)?.value || '').trim();

      const cli = v('precio_cli').toUpperCase();
      let marca = v('precio_marca').toUpperCase();
      if (marca === '__OTRA__') {
        marca = v('precio_marca_custom').toUpperCase();
      }

      const diseno = v('precio_diseno').toUpperCase();
      const dimension = v('precio_dimension').toUpperCase();
      const tipo = v('precio_tipo');
      const precio = parseFloat(v('precio_valor'));
      const vigente_desde = v('precio_desde');

      if (!cli) {
        mostrarToast('⚠️ Selecciona un cliente', true);
        return;
      }
      if (!marca) {
        mostrarToast('⚠️ Selecciona o escribe una marca', true);
        return;
      }
      if (!dimension) {
        mostrarToast('⚠️ Especifica la dimensión de la llanta', true);
        return;
      }
      if (!precio || precio <= 0) {
        mostrarToast('⚠️ Ingresa un precio válido en COP', true);
        return;
      }
      if (!vigente_desde) {
        mostrarToast('⚠️ Selecciona la fecha de vigencia', true);
        return;
      }

      const body = { cliente: cli, marca, diseno, dimension, tipo, precio, vigente_desde };

      try {
        const btnGuardar = document.getElementById('btnGuardarPrecioCliente');
        if (btnGuardar) btnGuardar.disabled = true;

        const res = await fetch('/api/precios-cliente', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          mostrarToast('❌ ' + (d.detail || 'No se pudo guardar el precio'), true);
          return;
        }

        mostrarToast(idPrecioEnEdicion ? '✅ Tarifa actualizada exitosamente' : '✅ Precio guardado exitosamente');
        cancelarEdicionPrecioCliente();
        await cargarPreciosClienteCat();
      } catch (e) {
        mostrarToast('❌ Error de conexión al guardar precio', true);
      } finally {
        const btnGuardar = document.getElementById('btnGuardarPrecioCliente');
        if (btnGuardar) btnGuardar.disabled = false;
      }
    }

    async function eliminarPrecioClienteCat(id) {
      if (!confirm('¿Eliminar esta tarifa de precio de la lista?')) return;
      try {
        const res = await fetch(`/api/precios-cliente/${id}`, { method: 'DELETE' });
        if (res.ok) {
          mostrarToast('Precio eliminado');
          cargarPreciosClienteCat();
        } else {
          mostrarToast('No se pudo eliminar el precio', true);
        }
      } catch (e) {
        mostrarToast('Error de conexión', true);
      }
    }

    // Funciones Excel Precios
    function descargarPlantillaPreciosExcel() {
      window.location.href = '/api/precios-cliente/plantilla-excel';
    }

    function exportarPreciosClienteExcel() {
      window.location.href = '/api/precios-cliente/exportar-excel';
    }

    function abrirModalImportarPreciosExcel() {
      archivoPreciosExcelSeleccionado = null;
      const lbl = document.getElementById('lblArchivoPreciosSeleccionado');
      if (lbl) lbl.textContent = 'Formatos permitidos: .xlsx, .xls';
      const fileInput = document.getElementById('filePreciosExcelInput');
      if (fileInput) fileInput.value = '';

      const btn = document.getElementById('btnSubirPreciosExcel') || document.getElementById('btnEjecutarImportarPreciosExcel');
      if (btn) btn.disabled = true;

      const modal = document.getElementById('modalImportarPreciosExcel');
      if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      }

      // Drag & Drop
      const dropZone = document.getElementById('dropZonePreciosExcel');
      if (dropZone && !dropZone._dndInit) {
        dropZone._dndInit = true;
        dropZone.addEventListener('click', () => {
          document.getElementById('filePreciosExcelInput')?.click();
        });
        dropZone.addEventListener('dragover', (e) => {
          e.preventDefault();
          dropZone.classList.add('border-emerald-500', 'bg-emerald-50/40');
        });
        dropZone.addEventListener('dragleave', () => {
          dropZone.classList.remove('border-emerald-500', 'bg-emerald-50/40');
        });
        dropZone.addEventListener('drop', (e) => {
          e.preventDefault();
          dropZone.classList.remove('border-emerald-500', 'bg-emerald-50/40');
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            archivoPreciosExcelSeleccionado = e.dataTransfer.files[0];
            const lbl = document.getElementById('lblArchivoPreciosSeleccionado');
            if (lbl) lbl.textContent = `Archivo: ${archivoPreciosExcelSeleccionado.name} (${(archivoPreciosExcelSeleccionado.size / 1024).toFixed(1)} KB)`;
            const btnImportar = document.getElementById('btnSubirPreciosExcel') || document.getElementById('btnEjecutarImportarPreciosExcel');
            if (btnImportar) btnImportar.disabled = false;
          }
        });
      }
    }

    function cerrarModalImportarPreciosExcel() {
      const modal = document.getElementById('modalImportarPreciosExcel');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
    }

    function alSeleccionarArchivoPreciosExcel(e) {
      if (e.target.files && e.target.files[0]) {
        archivoPreciosExcelSeleccionado = e.target.files[0];
        const lbl = document.getElementById('lblArchivoPreciosSeleccionado');
        if (lbl) lbl.textContent = `Archivo: ${archivoPreciosExcelSeleccionado.name} (${(archivoPreciosExcelSeleccionado.size / 1024).toFixed(1)} KB)`;
        const btnImportar = document.getElementById('btnSubirPreciosExcel') || document.getElementById('btnEjecutarImportarPreciosExcel');
        if (btnImportar) btnImportar.disabled = false;
      }
    }

    async function ejecutarImportarPreciosExcel() {
      if (!archivoPreciosExcelSeleccionado) {
        alert('Por favor selecciona o arrastra un archivo de Excel (.xlsx o .xls)');
        return;
      }

      const btn = document.getElementById('btnSubirPreciosExcel') || document.getElementById('btnEjecutarImportarPreciosExcel');
      const originalText = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Procesando...';
      }

      try {
        const formData = new FormData();
        formData.append('file', archivoPreciosExcelSeleccionado);

        const res = await fetch('/api/precios-cliente/importar-excel', {
          method: 'POST',
          body: formData
        });

        const data = await res.json();
        if (!res.ok) {
          alert('❌ ' + (data.detail || 'Error al procesar el archivo Excel'));
          return;
        }

        cerrarModalImportarPreciosExcel();
        let msg = `✅ Importación completada con éxito:\n• ${data.importados} tarifas registradas o actualizadas.`;
        if (data.errores && data.errores.length > 0) {
          msg += `\n\n⚠️ ${data.errores.length} fila(s) omitida(s) por inconsistencias:\n` + data.errores.slice(0, 8).join('\n');
          if (data.errores.length > 8) msg += `\n...y ${data.errores.length - 8} más.`;
        }
        alert(msg);
        mostrarToast(`✅ ${data.importados} precios importados`);
        cargarPreciosClienteCat();
      } catch (err) {
        alert('Error de conexión al subir el archivo');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      }
    }

    // ==========================================
    // STOCK DE SEGURIDAD DEL MRP
    // ==========================================
    async function cargarStockSeguridadCat() {
      const tbody = document.getElementById('tbodyStockSeguridad');
      if (!tbody) return;

      // Poblar selectores de clientes y dimensiones
      const selCli = document.getElementById('stockseg_cliente');
      if (selCli) {
        const valPrev = selCli.value;
        const clis = obtenerListaClientesDisponibles();
        selCli.innerHTML = '<option value="">-- Seleccionar Cliente --</option>' +
          clis.map(c => `<option value="${c}">${c}</option>`).join('');
        if (valPrev && clis.includes(valPrev)) selCli.value = valPrev;
      }

      const dlDims = document.getElementById('dl_stockseg_dimensiones');
      if (dlDims) {
        const dims = obtenerListaDimensionesDisponibles();
        dlDims.innerHTML = dims.map(d => `<option value="${d}">`).join('');
      }

      try {
        const res = await fetch('/api/stock-seguridad');
        const lista = res.ok ? await res.json() : [];
        const nombreEje = { DIRECCIONAL: 'Direccional', TRACCION: 'Tracción', LIBRE: 'Libre / remolque' };
        tbody.innerHTML = lista.length ? lista.map(r => {
          const q = s => String(s).replace(/'/g, "\\'");
          return `<tr><td class="p-2 font-bold">${r.cliente}</td><td class="p-2 font-mono">${r.dimension}</td><td class="p-2">${nombreEje[r.eje] || r.eje}</td>
            <td class="p-2 text-center font-bold">${r.cantidad}</td>
            <td class="p-2 text-center"><button type="button" onclick="eliminarStockSeguridadCat('${q(r.cliente)}', '${q(r.dimension)}', '${r.eje}')" class="text-rose-600 font-bold hover:underline cursor-pointer">Eliminar</button></td></tr>`;
        }).join('') : '<tr><td colspan="5" class="p-2 text-slate-400 italic">Sin reglas: se usa el stock de seguridad general de cada cliente</td></tr>';
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-2 text-rose-600">No se pudieron cargar las reglas</td></tr>';
      }
    }

    async function guardarStockSeguridadCat(ev) {
      ev.preventDefault();
      const body = {
        cliente: document.getElementById('stockseg_cliente').value.trim().toUpperCase(),
        dimension: document.getElementById('stockseg_dimension').value.trim().toUpperCase(),
        eje: document.getElementById('stockseg_eje').value,
        cantidad: parseInt(document.getElementById('stockseg_cantidad').value, 10)
      };
      const res = await fetch('/api/stock-seguridad', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        mostrarToast('❌ ' + (d.detail || 'No se pudo guardar la regla'), true);
        return;
      }
      mostrarToast('✅ Stock de seguridad guardado');
      document.getElementById('stockseg_dimension').value = '';
      document.getElementById('stockseg_cantidad').value = '';
      cargarStockSeguridadCat();
    }

    async function eliminarStockSeguridadCat(cliente, dimension, eje) {
      if (!confirm(`¿Eliminar el stock de seguridad de ${cliente} / ${dimension} / ${eje}?`)) return;
      await fetch(`/api/stock-seguridad?cliente=${encodeURIComponent(cliente)}&dimension=${encodeURIComponent(dimension)}&eje=${encodeURIComponent(eje)}`, { method: 'DELETE' });
      cargarStockSeguridadCat();
    }

    // ==========================================
    // MÁXIMO DE REENCAUCHES
    // ==========================================
    async function cargarMaximosReencaucheCat() {
      const tbody = document.getElementById('tbodyMaximosReencauche');
      if (!tbody) return;

      // Poblar selects de cliente y marca
      const selCli = document.getElementById('maxreen_cliente');
      if (selCli) {
        const valPrev = selCli.value;
        const clis = obtenerListaClientesDisponibles();
        selCli.innerHTML = '<option value="">-- Seleccionar Cliente --</option>' +
          clis.map(c => `<option value="${c}">${c}</option>`).join('');
        if (valPrev && clis.includes(valPrev)) selCli.value = valPrev;
      }

      const selMarca = document.getElementById('maxreen_marca');
      if (selMarca) {
        const valPrev = selMarca.value;
        const marcas = obtenerListaMarcasDisponibles();
        selMarca.innerHTML = '<option value="TODAS">TODAS LAS MARCAS</option>' +
          marcas.map(m => `<option value="${m}">${m}</option>`).join('');
        if (valPrev) selMarca.value = valPrev;
      }

      try {
        const res = await fetch('/api/configuracion-reencauche');
        const lista = res.ok ? await res.json() : [];
        tbody.innerHTML = lista.length ? lista.map(r => {
          const cli = String(r.cliente).replace(/'/g, "\\'"), mar = String(r.marca).replace(/'/g, "\\'");
          return `<tr><td class="p-2 font-bold">${r.cliente}</td><td class="p-2">${r.marca}</td>
            <td class="p-2 text-center font-mono font-bold">${r.max_reencauches}</td>
            <td class="p-2 text-center"><button type="button" onclick="eliminarMaximoReencaucheCat('${cli}', '${mar}')" class="text-rose-600 font-bold hover:underline cursor-pointer">Eliminar</button></td></tr>`;
        }).join('') : '<tr><td colspan="4" class="p-2 text-slate-400 italic">Sin reglas: no hay tope de reencauches</td></tr>';
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" class="p-2 text-rose-600">No se pudieron cargar las reglas</td></tr>';
      }
    }

    async function guardarMaximoReencaucheCat(ev) {
      ev.preventDefault();
      const body = {
        cliente: document.getElementById('maxreen_cliente').value.trim().toUpperCase(),
        marca: (document.getElementById('maxreen_marca').value.trim() || 'TODAS').toUpperCase(),
        max_reencauches: parseInt(document.getElementById('maxreen_valor').value, 10)
      };
      const res = await fetch('/api/configuracion-reencauche', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        mostrarToast('❌ ' + (d.detail || 'No se pudo guardar la regla'), true);
        return;
      }
      mostrarToast('✅ Regla de reencauches guardada');
      document.getElementById('maxreen_valor').value = '';
      cargarMaximosReencaucheCat();
    }

    async function eliminarMaximoReencaucheCat(cliente, marca) {
      if (!confirm(`¿Eliminar el máximo de reencauches de ${cliente} / ${marca}?`)) return;
      await fetch(`/api/configuracion-reencauche?cliente=${encodeURIComponent(cliente)}&marca=${encodeURIComponent(marca)}`, { method: 'DELETE' });
      cargarMaximosReencaucheCat();
    }

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
            <button type="button" onclick="eliminarMarcaClientePorId(${item.id}, '${item.cliente}', '${item.marca}')" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded-lg font-bold text-xs transition-colors cursor-pointer" title="Desvincular marca de este cliente">
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
      const selCli = document.getElementById('asoc_marca_cliente');
      const selMarca = document.getElementById('asoc_marca_nombre_select');
      const customMarca = document.getElementById('asoc_marca_nombre_custom');
      const hiddenMarca = document.getElementById('asoc_marca_nombre');

      // Poblar selector de clientes
      if (selCli) {
        const selFiltro = document.getElementById('filtroCatMarcaCliente');
        const pref = clientePref || (selFiltro && selFiltro.value ? selFiltro.value : '');
        const clis = obtenerListaClientesDisponibles();
        selCli.innerHTML = '<option value="">-- Seleccionar Cliente --</option>' +
          clis.map(c => `<option value="${c}">${c}</option>`).join('');
        if (pref && clis.includes(pref)) selCli.value = pref;
      }

      // Poblar selector de marcas
      if (selMarca) {
        const marcas = obtenerListaMarcasDisponibles();
        selMarca.innerHTML = '<option value="">-- Seleccionar Marca del Catálogo --</option>' +
          marcas.map(m => `<option value="${m}">${m}</option>`).join('') +
          '<option value="__OTRA__">+ Escribir otra marca...</option>';
        selMarca.value = '';
      }

      if (customMarca) {
        customMarca.value = '';
        customMarca.classList.add('hidden');
      }
      if (hiddenMarca) hiddenMarca.value = '';

      const modal = document.getElementById('modalAsociarMarcaCliente');
      if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      }
    }

    function alCambiarMarcaAsocModal() {
      const sel = document.getElementById('asoc_marca_nombre_select');
      const custom = document.getElementById('asoc_marca_nombre_custom');
      if (!sel) return;

      if (sel.value === '__OTRA__') {
        if (custom) {
          custom.classList.remove('hidden');
          custom.focus();
        }
      } else {
        if (custom) {
          custom.classList.add('hidden');
          custom.value = '';
        }
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
      const selMarca = document.getElementById('asoc_marca_nombre_select')?.value || '';
      const customMarca = (document.getElementById('asoc_marca_nombre_custom')?.value || '').trim();

      const marca = (selMarca === '__OTRA__' ? customMarca : selMarca).trim().toUpperCase();

      if (!cli) {
        alert('Por favor selecciona un Cliente');
        return;
      }
      if (!marca) {
        alert('Por favor selecciona o escribe la Marca a vincular');
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
          // Actualizar marcas de patio si corresponde
          const cliPatio = (document.getElementById('cliente')?.value || '').trim().toUpperCase();
          if (cliPatio === cli && typeof actualizarMarcasCliente === 'function') {
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
      cont.onchange = () => poblarSedesUsuarioModal(modo);
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

    // Sedes permitidas: checkboxes 'CLIENTE|SEDE' de los clientes marcados (ninguna = todas las sedes)
    async function poblarSedesUsuarioModal(modo, sedesSeleccionadas = null) {
      const pfx = modo === 'nuevo' ? 'usr_' : 'edit_usr_';
      const cont = document.getElementById(`${pfx}lista_sedes_check`);
      if (!cont) return;
      if (!cacheDirectorioClientes.length) {
        try { const r = await fetch('/api/clientes-directorio'); if (r.ok) cacheDirectorioClientes = await r.json(); } catch (e) {}
      }
      const marcadas = new Set(sedesSeleccionadas !== null
        ? String(sedesSeleccionadas || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
        : Array.from(cont.querySelectorAll('input:checked')).map(i => i.value));
      const clientes = Array.from(document.querySelectorAll(`.chk-cli-modal-${modo}:checked`)).map(c => c.value.trim().toUpperCase());
      const filas = [];
      clientes.forEach(cli => {
        const info = cacheDirectorioClientes.find(c => String(c.cliente || '').toUpperCase() === cli);
        (info && info.subclientes ? info.subclientes : []).forEach(sede => {
          const val = `${cli}|${String(sede).trim().toUpperCase()}`;
          filas.push(`<label class="flex items-center space-x-2 cursor-pointer"><input type="checkbox" value="${val}" class="rounded text-blue-600" ${marcadas.has(val) ? 'checked' : ''}><span>${cli} — ${sede}</span></label>`);
        });
      });
      cont.innerHTML = filas.length ? filas.join('') : '<p class="text-slate-400 italic text-[11px]">Marca un cliente para ver sus sedes.</p>';
    }

    function obtenerSedesSeleccionadasModal(modo) {
      const pfx = modo === 'nuevo' ? 'usr_' : 'edit_usr_';
      const chkTodas = document.getElementById(`${pfx}todas_flotas`);
      if (chkTodas && chkTodas.checked) return '';
      return Array.from(document.querySelectorAll(`#${pfx}lista_sedes_check input:checked`)).map(i => i.value).join(', ');
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
      if (document.getElementById(`${pfx}vista_bodegas`)?.checked) vistas.push('bodegas');
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
      document.getElementById('usr_vista_diagnostico').checked = false;
      document.getElementById('usr_vista_kpis').checked = false;
      document.getElementById('usr_vista_composicion').checked = false;
      document.getElementById('usr_vista_catalogos').checked = false;
      if (document.getElementById('usr_vista_bodegas')) document.getElementById('usr_vista_bodegas').checked = false;
      // Solo el administrador trabaja sin cliente asignado
      document.getElementById('usr_todas_flotas').checked = false;
      document.getElementById('usr_cliente_custom_nuevo').value = '';
      toggleClientesTodosModal('nuevo');
      alCambiarRolUsuarioModal('nuevo');
      poblarListaCheckboxesClientesModal('nuevo', []).then(() => poblarSedesUsuarioModal('nuevo', ''));

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
            sedes_asignadas: obtenerSedesSeleccionadasModal('nuevo'),
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
      if (document.getElementById('edit_usr_vista_bodegas')) document.getElementById('edit_usr_vista_bodegas').checked = vistas.includes('bodegas');

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
      poblarListaCheckboxesClientesModal('editar', clis).then(() => poblarSedesUsuarioModal('editar', u.sedes_asignadas || ''));

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
            sedes_asignadas: obtenerSedesSeleccionadasModal('editar'),
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


