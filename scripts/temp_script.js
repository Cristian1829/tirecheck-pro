
    // Variables globales de estado
    let listaPosicionesActual = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    let posicionesInspeccionadasPlaca = new Set();
    let posicionesConNovedadPlaca = new Map();
    let fotosNovedadActuales = [];
    let galeriaFotosActivas = [];
    let galeriaFotoIndexActual = 0;
    let ruedaSinRepuestoMarcada = false;
    let usuarioActual = null;
    let esquemaTipologiaCache = null;
    let sincronizandoCola = false;
    let datosInspeccionAnterior = null;
    let cacheTodasInspecciones = [];
    let cacheDiagnostico = [];
    let cacheKpis = [];

    // ==========================================
    // NAVEGACIÓN ENTRE PESTAÑAS (SPA)
    // ==========================================
    function navegarTab(tabId) {
      const tabs = ['patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos', 'remoto'];
      tabs.forEach(t => {
        const elVista = document.getElementById(`vista-${t}`);
        const elBtn = document.getElementById(`nav-btn-${t}`);
        if (elVista) elVista.classList.add('hidden');
        if (elBtn) elBtn.classList.remove('active');
      });

      const vistaActiva = document.getElementById(`vista-${tabId}`);
      const btnActivo = document.getElementById(`nav-btn-${tabId}`);
      if (vistaActiva) vistaActiva.classList.remove('hidden');
      if (btnActivo) btnActivo.classList.add('active');

      const stickyBar = document.getElementById('stickyBottomActionBarMobile');
      if (stickyBar) {
        if (tabId === 'patio') stickyBar.classList.remove('hidden');
        else stickyBar.classList.add('hidden');
      }

      // Carga perezosa de datos según la pestaña activa
      if (tabId === 'basedatos') cargarBaseInspecciones();
      else if (tabId === 'diagnostico') cargarDiagnostico();
      else if (tabId === 'kpis') cargarKpis();
      else if (tabId === 'catalogos') cargarGestionCatalogos();
      else if (tabId === 'remoto') cargarInfoServidor();
    }

    // ==========================================
    // AUTENTICACIÓN Y SESIÓN
    // ==========================================
    function verificarSesionUsuario() {
      const data = localStorage.getItem('tirecheck_usuario_sesion');
      if (data) {
        try {
          usuarioActual = JSON.parse(data);
          actualizarUIUsuario();
          document.getElementById('modalLogin').classList.add('hidden');
          return true;
        } catch(e) {
          localStorage.removeItem('tirecheck_usuario_sesion');
        }
      }
      document.getElementById('modalLogin').classList.remove('hidden');
      return false;
    }

    async function ejecutarLogin() {
      const u = document.getElementById('login_username').value.trim();
      const p = document.getElementById('login_password').value.trim();
      const errBox = document.getElementById('login_error');
      errBox.classList.add('hidden');

      if (!u || !p) {
        errBox.textContent = 'Por favor ingresa usuario y contraseña.';
        errBox.classList.remove('hidden');
        return;
      }

      try {
        const res = await fetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username: u, password: p})
        });
        const d = await res.json();
        if (res.ok) {
          usuarioActual = d.usuario;
          localStorage.setItem('tirecheck_usuario_sesion', JSON.stringify(usuarioActual));
          document.getElementById('modalLogin').classList.add('hidden');
          actualizarUIUsuario();
          cargarCatalogos();
          validarVida();
          mostrarToast(`¡Bienvenido, ${usuarioActual.nombre_completo}!`);
        } else {
          errBox.textContent = d.detail || 'Usuario o contraseña incorrectos.';
          errBox.classList.remove('hidden');
        }
      } catch (e) {
        errBox.textContent = 'Error de conexión con el servidor.';
        errBox.classList.remove('hidden');
      }
    }

    function cerrarSesionUsuario() {
      if (confirm('¿Deseas cerrar tu sesión actual?')) {
        localStorage.removeItem('tirecheck_usuario_sesion');
        usuarioActual = null;
        document.getElementById('modalLogin').classList.remove('hidden');
      }
    }

    function actualizarUIUsuario() {
      if (!usuarioActual) return;
      const lbl = document.getElementById('lblUsuarioActivo');
      if (lbl) {
        const rolBadge = usuarioActual.rol ? `[${usuarioActual.rol.toUpperCase()}]` : '';
        lbl.textContent = `${usuarioActual.nombre_completo} ${rolBadge}`;
      }
      if (usuarioActual.rol !== 'admin' && usuarioActual.cliente_asignado) {
        const inpCli = document.getElementById('cliente');
        if (inpCli) {
          inpCli.value = usuarioActual.cliente_asignado;
          inpCli.readOnly = true;
          document.getElementById('badgeClienteGuardado').textContent = 'Asignado a Flota';
        }
      }
    }

    // ==========================================
    // NOTIFICACIONES TOAST FLOTANTES CON BOTÓN [X]
    // ==========================================
    let toastTimeoutId = null;

    function cerrarToast() {
      const toast = document.getElementById('toast');
      if (toast) {
        toast.classList.add('hidden');
      }
      if (toastTimeoutId) {
        clearTimeout(toastTimeoutId);
        toastTimeoutId = null;
      }
    }

    function mostrarToast(mensaje, esError = false) {
      const toast = document.getElementById('toast');
      if (!toast) return;

      if (toastTimeoutId) {
        clearTimeout(toastTimeoutId);
        toastTimeoutId = null;
      }

      const esCandado = mensaje.includes('CANDADO') || mensaje.includes('límite') || mensaje.includes('⛔') || esError;
      const icono = esCandado 
        ? '<i class="fa-solid fa-shield-halved text-rose-300 text-base mt-0.5"></i>' 
        : '<i class="fa-solid fa-circle-check text-emerald-300 text-base mt-0.5"></i>';

      toast.className = `fixed bottom-20 lg:bottom-6 right-4 sm:right-6 z-50 transform transition-all duration-300 p-3.5 sm:p-4 rounded-2xl text-xs sm:text-sm font-bold shadow-2xl max-w-md border backdrop-blur-md flex items-start space-x-3 ${
        esError || esCandado
          ? 'bg-rose-950/95 text-rose-100 border-rose-600 shadow-rose-950/50' 
          : 'bg-slate-900/95 text-emerald-300 border-slate-700 shadow-slate-950/50'
      }`;

      toast.innerHTML = `
        <div class="flex-shrink-0">
          ${icono}
        </div>
        <div class="flex-1 text-left leading-snug">
          ${mensaje}
        </div>
        <button type="button" onclick="cerrarToast()" class="ml-2 -mr-1 -mt-1 w-6 h-6 rounded-full hover:bg-white/20 active:scale-95 text-white/80 hover:text-white flex items-center justify-center text-xs transition-all flex-shrink-0" title="Cerrar notificación (X)">
          <i class="fa-solid fa-xmark text-sm"></i>
        </button>
      `;

      toast.classList.remove('hidden');

      // Si es un candado o error, NO se auto-cierra: el usuario debe darle clic a la X para cerrarlo
      if (!esCandado && !esError) {
        toastTimeoutId = setTimeout(() => {
          cerrarToast();
        }, 4500);
      }
    }

    // ==========================================
    // VISTA 2: BASE DE INSPECCIONES (CRUD, FILTROS & EXCEL)
    // ==========================================
    let bdFiltrosPoblados = false;

    async function cargarBaseInspecciones() {
      try {
        const res = await fetch('/api/inspecciones');
        if (res.ok) {
          cacheTodasInspecciones = await res.json();
          document.getElementById('badgeTotalInspecciones').textContent = cacheTodasInspecciones.length;
          document.getElementById('lblTotalBD').textContent = cacheTodasInspecciones.length;
          poblarSelectoresFiltroBD(cacheTodasInspecciones);
          filtrarTablaBD();
        }
      } catch (e) {
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
    }

    function filtrarTablaBD() {
      const tbody = document.getElementById('tbodyInspecciones');
      if (!tbody) return;

      const q = (document.getElementById('filtroTextoBD')?.value || '').trim().toLowerCase();
      const fDesde = document.getElementById('filtroBDFechaDesde')?.value || '';
      const fHasta = document.getElementById('filtroBDFechaHasta')?.value || '';
      const cli = document.getElementById('filtroBDCliente')?.value || 'TODOS';
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

      const filtradas = cacheTodasInspecciones.filter(r => {
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

      document.getElementById('lblConteoBD').textContent = filtradas.length;
      document.getElementById('lblTotalBD').textContent = cacheTodasInspecciones.length;

      if (filtradas.length === 0) {
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
        return;
      }

      tbody.innerHTML = filtradas.map(r => {
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
                (r.vida || '').toLowerCase().includes('orig') ? 'bg-blue-50 text-blue-700' : 'bg-purple-50 text-purple-700'
              }">
                ${r.vida || '-'}
              </span>
            </td>
            <td class="p-2.5 text-slate-500">${r.banda_reen || '-'}</td>
            <td class="p-2.5 text-center font-mono ${colorDesgaste}">${r.prof_ext}</td>
            <td class="p-2.5 text-center font-mono ${colorDesgaste}">${r.prof_cent}</td>
            <td class="p-2.5 text-center font-mono ${colorDesgaste}">${r.prof_int}${badgeAlerta}</td>
            <td class="p-2.5 text-center font-mono font-bold ${
              (parseFloat(r.psi) < 90 || parseFloat(r.psi) > 120) ? 'text-amber-600 bg-amber-50/60 rounded' : 'text-slate-700'
            }">${r.psi}</td>
            <td class="p-2.5 max-w-xs truncate" title="${r.novedades || ''}">
              ${r.novedades || '-'}
            </td>
            <td class="p-2.5 text-center whitespace-nowrap">
              ${htmlBotonFotos}
            </td>
            <td class="p-2.5 text-right font-mono text-slate-600">$${(r.precio || 0).toLocaleString()}</td>
            <td class="p-2.5 text-center font-mono text-slate-400">${r.prof_inicial || 0}</td>
            <td class="p-2.5 text-right font-mono text-slate-400">${(r.km_montaje || 0).toLocaleString()}</td>
            <td class="p-2.5 text-center whitespace-nowrap">
              ${tieneFotos ? `
                <button type="button" onclick="abrirGaleriaFotosPorId(${r.id})" class="px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold rounded-lg mr-1 text-xs transition-colors" title="Ver evidencias fotográficas">
                  <i class="fa-solid fa-camera"></i>
                </button>
              ` : ''}
              <button type="button" onclick="abrirModalEditarInspeccion(${r.id})" class="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold rounded-lg mr-1 text-xs transition-colors" title="Editar Fila">
                <i class="fa-solid fa-pen-to-square"></i>
              </button>
              <button type="button" onclick="eliminarInspeccion(${r.id}, '${r.placa}', ${r.posicion})" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold rounded-lg text-xs transition-colors" title="Eliminar Fila">
                <i class="fa-solid fa-trash"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
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
      setVal('filtroBDOperacion', 'TODOS');
      setVal('filtroBDTipologia', 'TODOS');
      setVal('filtroBDMarca', 'TODOS');
      setVal('filtroBDVida', 'TODOS');
      setVal('filtroBDSemaforo', 'TODOS');
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
        document.getElementById('edit_vida').value = d.vida || 'Original';
        document.getElementById('edit_banda_reen').value = d.banda_reen || '';
        document.getElementById('edit_psi').value = d.psi || 100;
        document.getElementById('edit_prof_ext').value = d.prof_ext || 0;
        document.getElementById('edit_prof_cent').value = d.prof_cent || 0;
        document.getElementById('edit_prof_int').value = d.prof_int || 0;
        document.getElementById('edit_prof_inicial').value = d.prof_inicial || 0;
        document.getElementById('edit_precio').value = d.precio || 0;
        document.getElementById('edit_km_montaje').value = d.km_montaje || 0;
        document.getElementById('edit_novedades').value = d.novedades || '';

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
    }

    async function guardarEdicionInspeccion(e) {
      e.preventDefault();
      const id = document.getElementById('edit_id').value;
      const payload = {
        fecha: document.getElementById('edit_fecha').value,
        cliente: document.getElementById('edit_cliente').value,
        subcliente: document.getElementById('edit_subcliente').value,
        tipo_operacion: document.getElementById('edit_tipo_operacion').value,
        placa: document.getElementById('edit_placa').value.trim().toUpperCase(),
        posicion: parseInt(document.getElementById('edit_posicion').value) || 1,
        numero_interno: document.getElementById('edit_numero_interno').value.trim().toUpperCase(),
        kilometraje: parseFloat(document.getElementById('edit_kilometraje').value) || 0,
        tipologia: document.getElementById('edit_tipologia').value,
        marca: document.getElementById('edit_marca').value,
        diseno: document.getElementById('edit_diseno').value,
        dimension: document.getElementById('edit_dimension').value,
        vida: document.getElementById('edit_vida').value,
        banda_reen: document.getElementById('edit_banda_reen').value,
        psi: parseFloat(document.getElementById('edit_psi').value) || 100,
        prof_ext: parseFloat(document.getElementById('edit_prof_ext').value) || 0,
        prof_cent: parseFloat(document.getElementById('edit_prof_cent').value) || 0,
        prof_int: parseFloat(document.getElementById('edit_prof_int').value) || 0,
        prof_inicial: parseFloat(document.getElementById('edit_prof_inicial').value) || 0,
        precio: parseFloat(document.getElementById('edit_precio').value) || 0,
        km_montaje: parseFloat(document.getElementById('edit_km_montaje').value) || 0,
        novedades: document.getElementById('edit_novedades').value
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
      window.location.href = '/api/inspecciones/plantilla-excel';
    }
    function exportarInspeccionesExcel() {
      window.location.href = '/api/inspecciones/exportar-excel';
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

    // ==========================================
    // VISTA 3: PLANES DE ACCIÓN & DIAGNÓSTICO
    // ==========================================
    async function cargarDiagnostico() {
      try {
        const res = await fetch('/api/diagnostico');
        if (res.ok) {
          cacheDiagnostico = await res.json();
          actualizarCombosFiltroDiagnostico();
          filtrarTablaDiagnostico();
        }
      } catch (e) {
        mostrarToast('Error al cargar diagnóstico de flota', true);
      }
    }

    function actualizarCombosFiltroDiagnostico() {
      const selCli = document.getElementById('filtroDiagCliente');
      const selOp = document.getElementById('filtroDiagOperacion');

      const clientes = Array.from(new Set(cacheDiagnostico.map(r => r.Cliente).filter(Boolean))).sort();
      const operaciones = Array.from(new Set(cacheDiagnostico.map(r => r.Operación).filter(Boolean))).sort();

      if (selCli) {
        const valCli = selCli.value || 'Todos';
        selCli.innerHTML = '<option value="Todos">Todos los Clientes</option>' +
          clientes.map(c => `<option value="${c}">${c}</option>`).join('');
        if (clientes.includes(valCli)) selCli.value = valCli;
      }

      if (selOp) {
        const valOp = selOp.value || 'Todos';
        selOp.innerHTML = '<option value="Todos">Todas las Operaciones</option>' +
          operaciones.map(o => `<option value="${o}">${o}</option>`).join('');
        if (operaciones.includes(valOp)) selOp.value = valOp;
      }
    }

    function filtrarTablaDiagnostico() {
      const tbody = document.getElementById('tbodyDiagnostico');
      const cli = document.getElementById('filtroDiagCliente')?.value || 'Todos';
      const op = document.getElementById('filtroDiagOperacion')?.value || 'Todos';
      const alerta = document.getElementById('filtroDiagAlerta')?.value || 'Todos';
      const placa = (document.getElementById('filtroDiagPlaca')?.value || '').trim().toLowerCase();

      let tot = 0, cambio = 0, alin = 0, dual = 0, ok = 0;

      const filtradas = cacheDiagnostico.filter(r => {
        // Conteo métrico
        tot++;
        if (r.Plan_Cambio_Llanta === 'SÍ') cambio++;
        if (r.Plan_Alineacion === 'SÍ') alin++;
        if (r.Plan_Dual_Mal_Apareado === 'SÍ') dual++;
        if (r.Plan_Cambio_Llanta !== 'SÍ' && r.Plan_Alineacion !== 'SÍ' && r.Plan_Dual_Mal_Apareado !== 'SÍ') ok++;

        // Filtros
        if (cli !== 'Todos' && r.Cliente !== cli) return false;
        if (op !== 'Todos' && r.Operación !== op) return false;
        if (placa && !(r['Vehículo/Placa'] || '').toLowerCase().includes(placa)) return false;

        if (alerta === 'Cambio' && r.Plan_Cambio_Llanta !== 'SÍ') return false;
        if (alerta === 'Alineacion' && r.Plan_Alineacion !== 'SÍ') return false;
        if (alerta === 'Dual' && r.Plan_Dual_Mal_Apareado !== 'SÍ') return false;
        if (alerta === 'Alerta' && r.Plan_Cambio_Llanta !== 'SÍ' && r.Plan_Alineacion !== 'SÍ' && r.Plan_Dual_Mal_Apareado !== 'SÍ') return false;
        if (alerta === 'OK' && (r.Plan_Cambio_Llanta === 'SÍ' || r.Plan_Alineacion === 'SÍ' || r.Plan_Dual_Mal_Apareado === 'SÍ')) return false;

        return true;
      });

      // Actualizar tarjetas
      document.getElementById('cardDiagTotal').textContent = tot;
      document.getElementById('cardDiagCambio').textContent = cambio;
      document.getElementById('cardDiagAlineacion').textContent = alin;
      document.getElementById('cardDiagDual').textContent = dual;
      document.getElementById('cardDiagOK').textContent = ok;

      if (filtradas.length === 0) {
        tbody.innerHTML = `<tr><td colspan="15" class="p-8 text-center text-slate-400">No hay vehículos que coincidan con los filtros seleccionados.</td></tr>`;
        return;
      }

      tbody.innerHTML = filtradas.map(r => {
        const bgRow = r.Plan_Cambio_Llanta === 'SÍ' ? 'bg-rose-50/60' : (r.Plan_Alineacion === 'SÍ' || r.Plan_Dual_Mal_Apareado === 'SÍ') ? 'bg-amber-50/50' : '';
        return `
          <tr class="${bgRow} hover:bg-slate-100 transition-colors">
            <td class="p-2.5 font-black text-slate-900">${r['Vehículo/Placa']}</td>
            <td class="p-2.5 font-bold">${r.Cliente || '-'}</td>
            <td class="p-2.5">${r.Subcliente || '-'}</td>
            <td class="p-2.5">${r.Operación || '-'}</td>
            <td class="p-2.5">${r.Tipo || '-'}</td>
            <td class="p-2.5 text-right font-mono">${(r.Km || 0).toLocaleString()}</td>
            <td class="p-2.5 text-center font-bold">${r['Llantas Inspeccionadas']}</td>
            <td class="p-2.5 text-center font-bold text-slate-600">${r.Limite_Retiro_mm || 3.0} mm</td>
            <td class="p-2.5 text-center">${r.Plan_Cambio_Llanta === 'SÍ' ? '<span class="bg-rose-100 text-rose-800 font-black px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' : '<span class="text-slate-400">NO</span>'}</td>
            <td class="p-2.5 text-center">${r.Plan_Alineacion === 'SÍ' ? '<span class="bg-red-100 text-red-800 font-bold px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' : '<span class="text-slate-400">NO</span>'}</td>
            <td class="p-2.5 text-center">${r.Plan_Dual_Mal_Apareado === 'SÍ' ? '<span class="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' : '<span class="text-slate-400">NO</span>'}</td>
            <td class="p-2.5 max-w-xs truncate font-medium text-rose-700" title="${r.Detalle_Cambio || ''}">${r.Detalle_Cambio || 'OK'}</td>
            <td class="p-2.5 max-w-xs truncate font-medium text-red-700" title="${r.Detalle_Alineacion || ''}">${r.Detalle_Alineacion || 'OK'}</td>
            <td class="p-2.5 max-w-xs truncate font-medium text-amber-700" title="${r.Detalle_Dual || ''}">${r.Detalle_Dual || 'OK'}</td>
            <td class="p-2.5 text-center">
              <button type="button" onclick="abrirModalInformePdf('${r['Vehículo/Placa']}')" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg text-xs" title="Ver Plan de Mantenimiento">
                <i class="fa-solid fa-file-pdf"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    function limpiarFiltrosDiagnostico() {
      const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
      setVal('filtroDiagCliente', 'Todos');
      setVal('filtroDiagOperacion', 'Todos');
      setVal('filtroDiagAlerta', 'Todos');
      setVal('filtroDiagPlaca', '');
      filtrarTablaDiagnostico();
      mostrarToast('Filtros de diagnóstico restablecidos.');
    }

    function exportarDiagnosticoExcel() {
      window.location.href = '/api/diagnostico/exportar-excel';
    }

    // ==========================================
    // VISTA 4: TRAZABILIDAD & KPIS DE LLANTAS
    // ==========================================
    let kpisFiltrosPoblados = false;

    async function cargarKpis() {
      const qNum = (document.getElementById('filtroKpiNumero').value || '').trim();
      const cli = document.getElementById('filtroKpiCliente').value || '';
      const sub = document.getElementById('filtroKpiSubcliente').value || '';
      const op = document.getElementById('filtroKpiOperacion').value || '';
      const marca = document.getElementById('filtroKpiMarca').value || '';

      const params = new URLSearchParams();
      if (qNum) params.append('numero_interno', qNum);
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);
      if (marca && marca !== 'TODOS') params.append('marca', marca);

      try {
        const res = await fetch(`/api/kpis-llantas?${params.toString()}`);
        if (res.ok) {
          cacheKpis = await res.json();
          if (!kpisFiltrosPoblados) {
            poblarSelectoresFiltroKpis(cacheKpis);
          }
          renderizarTablaKpis();
        }
      } catch (e) {
        mostrarToast('Error al cargar métricas de KPIs', true);
      }
    }

    function poblarSelectoresFiltroKpis(data) {
      if (!data || data.length === 0) return;
      const clientes = Array.from(new Set(data.map(d => d.cliente).filter(Boolean))).sort();
      const subclientes = Array.from(new Set(data.map(d => d.subcliente).filter(Boolean))).sort();
      const operaciones = Array.from(new Set(data.map(d => d.tipo_operacion).filter(Boolean))).sort();
      const marcas = Array.from(new Set(data.map(d => d.marca).filter(Boolean))).sort();

      const selCli = document.getElementById('filtroKpiCliente');
      const selSub = document.getElementById('filtroKpiSubcliente');
      const selOp = document.getElementById('filtroKpiOperacion');
      const selMar = document.getElementById('filtroKpiMarca');

      if (selCli) selCli.innerHTML = '<option value="TODOS">Todos los Clientes</option>' + clientes.map(c => `<option value="${c}">${c}</option>`).join('');
      if (selSub) selSub.innerHTML = '<option value="TODOS">Todas las Sedes</option>' + subclientes.map(s => `<option value="${s}">${s}</option>`).join('');
      if (selOp) selOp.innerHTML = '<option value="TODOS">Todas las Operaciones</option>' + operaciones.map(o => `<option value="${o}">${o}</option>`).join('');
      if (selMar) selMar.innerHTML = '<option value="TODOS">Todas las Marcas</option>' + marcas.map(m => `<option value="${m}">${m}</option>`).join('');

      kpisFiltrosPoblados = true;
    }

    function renderizarTablaKpis() {
      const tbody = document.getElementById('tbodyKpis');
      const data = cacheKpis;

      if (!data || data.length === 0) {
        document.getElementById('cardKpiTotal').textContent = '0';
        document.getElementById('cardKpiKmProm').textContent = '0.0';
        document.getElementById('cardKpiCpkProm').textContent = '$0.0000';
        document.getElementById('cardKpiProyProm').textContent = '0 km';
        tbody.innerHTML = `<tr><td colspan="20" class="p-8 text-center text-slate-400">No hay datos de rendimiento coincidentes con los filtros.</td></tr>`;
        return;
      }

      // Cálculo de promedios para tarjetas
      const km_mms = data.map(d => d.km_por_mm).filter(v => v > 0);
      const cpks = data.map(d => d.cpk).filter(v => v > 0);
      const proys = data.map(d => d.proyeccion_total_km).filter(v => v > 0);

      const prom_km_mm = km_mms.length ? (km_mms.reduce((a, b) => a + b, 0) / km_mms.length) : 0;
      const prom_cpk = cpks.length ? (cpks.reduce((a, b) => a + b, 0) / cpks.length) : 0;
      const prom_proy = proys.length ? (proys.reduce((a, b) => a + b, 0) / proys.length) : 0;

      document.getElementById('cardKpiTotal').textContent = data.length;
      document.getElementById('cardKpiKmProm').textContent = prom_km_mm.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
      document.getElementById('cardKpiCpkProm').textContent = `$${prom_cpk.toFixed(4)}`;
      document.getElementById('cardKpiProyProm').textContent = `${Math.round(prom_proy).toLocaleString()} km`;

      tbody.innerHTML = data.map(d => `
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
          <td class="p-2.5 text-center">${d.requiere_cambio === 'SÍ' ? '<span class="bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' : '<span class="text-slate-400">NO</span>'}</td>
          <td class="p-2.5 text-center font-mono font-bold text-rose-600">${d.desgaste_mm} mm</td>
          <td class="p-2.5 text-center font-mono">${(d.porcentaje_desgaste || 0).toFixed(1)}%</td>
          <td class="p-2.5 text-right font-mono">${(d.km_rodados || 0).toLocaleString()}</td>
          <td class="p-2.5 text-right font-mono font-bold text-blue-600">${(d.km_por_mm || 0).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})}</td>
          <td class="p-2.5 text-right font-mono">$${(d.precio || 0).toLocaleString()}</td>
          <td class="p-2.5 text-right font-mono font-bold text-emerald-600">$${(d.cpk || 0).toFixed(4)}</td>
          <td class="p-2.5 text-right font-mono">${Math.round(d.proyeccion_total_km || 0).toLocaleString()}</td>
          <td class="p-2.5 text-right font-mono">$${(d.cpk_proyectado || 0).toFixed(4)}</td>
          <td class="p-2.5 text-right font-mono font-black text-purple-700">${Math.round(d.km_restantes || 0).toLocaleString()} km</td>
        </tr>
      `).join('');
    }

    function limpiarFiltrosKpis() {
      document.getElementById('filtroKpiNumero').value = '';
      document.getElementById('filtroKpiCliente').value = 'TODOS';
      document.getElementById('filtroKpiSubcliente').value = 'TODOS';
      document.getElementById('filtroKpiOperacion').value = 'TODOS';
      document.getElementById('filtroKpiMarca').value = 'TODOS';
      cargarKpis();
    }

    function exportarKpisExcel() {
      const qNum = (document.getElementById('filtroKpiNumero').value || '').trim();
      const cli = document.getElementById('filtroKpiCliente').value || '';
      const sub = document.getElementById('filtroKpiSubcliente').value || '';
      const op = document.getElementById('filtroKpiOperacion').value || '';
      const marca = document.getElementById('filtroKpiMarca').value || '';

      const params = new URLSearchParams();
      if (qNum) params.append('numero_interno', qNum);
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);
      if (marca && marca !== 'TODOS') params.append('marca', marca);

      window.location.href = `/api/kpis-llantas/exportar-excel?${params.toString()}`;
    }

    // ==========================================
    // VISTA 5: GESTIÓN DE CATÁLOGOS & CONFIGURACIÓN
    // ==========================================
    function mostrarSubtabCat(subtab) {
      const tabs = ['operaciones', 'tipologias', 'modelos', 'clientes', 'usuarios'];
      tabs.forEach(t => {
        document.getElementById(`cat-seccion-${t}`).classList.add('hidden');
        const btn = document.getElementById(`subtab-btn-${t}`);
        btn.className = 'px-3 py-1.5 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200';
      });
      document.getElementById(`cat-seccion-${subtab}`).classList.remove('hidden');
      document.getElementById(`subtab-btn-${subtab}`).className = 'px-3 py-1.5 rounded-xl bg-slate-900 text-white';
    }

    async function cargarGestionCatalogos() {
      cargarOperacionesCat();
      cargarTipologiasCat();
      cargarModelosCat();
      cargarClientesLimCat();
      cargarUsuariosCat();
    }

    async function cargarOperacionesCat() {
      const res = await fetch('/api/operaciones');
      if (res.ok) {
        const ops = await res.json();
        const box = document.getElementById('listaOperacionesCat');
        box.innerHTML = ops.map(op => `
          <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
            <span class="font-bold text-slate-800">${op}</span>
            <button type="button" onclick="eliminarOperacionCat('${op}')" class="text-rose-600 hover:text-rose-800 text-xs"><i class="fa-solid fa-trash"></i></button>
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

    async function cargarTipologiasCat() {
      const res = await fetch('/api/tipologias');
      if (res.ok) {
        const tips = await res.json();
        const box = document.getElementById('listaTipologiasCat');
        box.innerHTML = tips.map(t => `
          <div class="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1">
            <div class="flex items-center justify-between">
              <span class="font-black text-slate-900 text-sm">${t.nombre}</span>
              <span class="text-xs font-bold bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">${t.cant_llantas} llantas</span>
            </div>
            <p class="text-xs text-slate-500">${t.descripcion || 'Sin descripción'}</p>
          </div>
        `).join('');
      }
    }

    async function cargarModelosCat() {
      const res = await fetch('/api/modelos-llanta');
      if (res.ok) {
        const mods = await res.json();
        const tbody = document.getElementById('tbodyModelosCat');
        tbody.innerHTML = mods.map(m => `
          <tr class="hover:bg-slate-50">
            <td class="p-2.5 font-bold">${m.tipo_llanta}</td>
            <td class="p-2.5 font-black text-slate-900">${m.marca}</td>
            <td class="p-2.5">${m.diseno}</td>
            <td class="p-2.5">${m.dimension}</td>
            <td class="p-2.5 text-center font-mono font-bold text-blue-700">${m.prof_inicial} mm</td>
            <td class="p-2.5 text-slate-500">${m.descripcion || '-'}</td>
          </tr>
        `).join('');
      }
    }

    function abrirModalNuevoModelo() {
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
        alert('Ingresa una profundidad inicial válida');
        return;
      }
      const item = {
        tipo_llanta: document.getElementById('mod_tipo').value,
        marca: document.getElementById('mod_marca').value.trim(),
        diseno: document.getElementById('mod_diseno').value.trim(),
        dimension: document.getElementById('mod_dimension').value.trim(),
        prof_inicial: p,
        descripcion: document.getElementById('mod_desc').value.trim()
      };
      const res = await fetch('/api/modelos-llanta', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item)
      });
      if (res.ok) {
        cerrarModalNuevoModelo();
        mostrarToast('✅ Modelo guardado en catálogo.');
        cargarModelosCat();
      }
    }

    async function cargarClientesLimCat() {
      const res = await fetch('/api/configuraciones-clientes');
      if (res.ok) {
        const clis = await res.json();
        const tbody = document.getElementById('tbodyClientesLimCat');
        tbody.innerHTML = clis.map(c => `
          <tr class="hover:bg-slate-50">
            <td class="p-2.5 font-black text-slate-900">${c.cliente}</td>
            <td class="p-2.5 text-center font-black text-rose-700 font-mono">${c.limite_retiro_mm} mm</td>
            <td class="p-2.5 text-slate-600">${c.observaciones || '-'}</td>
            <td class="p-2.5 text-slate-400 font-mono">${c.fecha_actualizacion || '-'}</td>
          </tr>
        `).join('');
      }
    }

    function abrirModalLimiteCliente() {
      document.getElementById('modalLimiteCliente').classList.remove('hidden');
      document.getElementById('modalLimiteCliente').classList.add('flex');
    }
    function cerrarModalLimiteCliente() {
      document.getElementById('modalLimiteCliente').classList.add('hidden');
      document.getElementById('modalLimiteCliente').classList.remove('flex');
    }
    async function guardarLimiteCliente() {
      const cli = document.getElementById('lim_cliente').value.trim();
      const mm = parseFloat(document.getElementById('lim_mm').value);
      if (!cli || !mm) {
        alert('Por favor completa el cliente y el límite en mm');
        return;
      }
      const res = await fetch('/api/configuraciones-clientes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          cliente: cli,
          limite_retiro_mm: mm,
          observaciones: document.getElementById('lim_obs').value.trim()
        })
      });
      if (res.ok) {
        cerrarModalLimiteCliente();
        mostrarToast(`✅ Límite para ${cli} guardado en ${mm} mm.`);
        cargarClientesLimCat();
      }
    }

    async function cargarUsuariosCat() {
      const res = await fetch('/api/usuarios');
      if (res.ok) {
        const usrs = await res.json();
        const tbody = document.getElementById('tbodyUsuariosCat');
        tbody.innerHTML = usrs.map(u => `
          <tr class="hover:bg-slate-50">
            <td class="p-2.5 font-black text-slate-900">${u.username}</td>
            <td class="p-2.5 font-bold">${u.nombre_completo}</td>
            <td class="p-2.5 text-center font-bold uppercase text-[10px]"><span class="px-2 py-0.5 rounded-full ${u.rol === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'}">${u.rol}</span></td>
            <td class="p-2.5">${u.cliente_asignado || 'Todas las Flotas'}</td>
            <td class="p-2.5 text-center">${u.activo ? '<span class="text-emerald-600 font-bold">Activo</span>' : '<span class="text-rose-600 font-bold">Inactivo</span>'}</td>
            <td class="p-2.5 text-center">
              ${u.username !== 'admin' ? `<button type="button" onclick="eliminarUsuarioCat('${u.username}')" class="text-rose-600 hover:text-rose-800 font-bold text-xs"><i class="fa-solid fa-trash"></i></button>` : '-'}
            </td>
          </tr>
        `).join('');
      }
    }

    function abrirModalNuevoUsuario() {
      document.getElementById('modalNuevoUsuario').classList.remove('hidden');
      document.getElementById('modalNuevoUsuario').classList.add('flex');
    }
    function cerrarModalNuevoUsuario() {
      document.getElementById('modalNuevoUsuario').classList.add('hidden');
      document.getElementById('modalNuevoUsuario').classList.remove('flex');
    }
    async function guardarNuevoUsuario() {
      const u = document.getElementById('usr_username').value.trim();
      const n = document.getElementById('usr_nombre').value.trim();
      const p = document.getElementById('usr_pass').value.trim();
      if (!u || !n || !p) {
        alert('Por favor completa todos los campos del usuario');
        return;
      }
      const res = await fetch('/api/usuarios', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          username: u,
          nombre_completo: n,
          password: p,
          rol: document.getElementById('usr_rol').value,
          cliente_asignado: document.getElementById('usr_cliente').value.trim()
        })
      });
      if (res.ok) {
        cerrarModalNuevoUsuario();
        mostrarToast(`✅ Usuario ${u} creado exitosamente.`);
        cargarUsuariosCat();
      } else {
        const d = await res.json();
        mostrarToast(d.detail || 'Error al crear usuario', true);
      }
    }

    async function eliminarUsuarioCat(username) {
      if (!confirm(`¿Eliminar al usuario "${username}"?`)) return;
      const res = await fetch(`/api/usuarios/${username}`, { method: 'DELETE' });
      if (res.ok) {
        mostrarToast(`Usuario ${username} eliminado.`);
        cargarUsuariosCat();
      }
    }

    // ==========================================
    // VISTA 6: CONECTAR CELULAR / REMOTO (QR & NGROK)
    // ==========================================
    async function cargarInfoServidor() {
      try {
        const res = await fetch('/api/servidor/info');
        if (res.ok) {
          const d = await res.json();
          document.getElementById('lblUrlLocal').textContent = d.url_local;
          document.getElementById('imgCodigoQR').src = `/qr?t=${Date.now()}`;
          actualizarEstadoNgrokUI(d.ngrok_activo, d.ngrok_url);
        }
      } catch (e) {}
    }

    function actualizarEstadoNgrokUI(activo, url) {
      const badge = document.getElementById('badgeNgrokEstado');
      const box = document.getElementById('boxUrlNgrok');
      const txt = document.getElementById('txtUrlNgrok');
      const btn = document.getElementById('btnToggleNgrok');

      if (activo && url) {
        badge.className = 'text-xs font-black px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300';
        badge.textContent = 'En Línea por Internet';
        box.classList.remove('hidden');
        txt.value = url;
        btn.innerHTML = '<i class="fa-solid fa-power-off mr-1"></i> Desactivar Enlace Público';
        btn.className = 'w-full py-3 bg-rose-600 hover:bg-rose-700 text-white font-black text-xs rounded-xl shadow transition-all';
      } else {
        badge.className = 'text-xs font-black px-2.5 py-1 rounded-full bg-slate-200 text-slate-700';
        badge.textContent = 'Desconectado';
        box.classList.add('hidden');
        txt.value = '';
        btn.innerHTML = '<i class="fa-solid fa-bolt mr-1"></i> Activar Enlace Público de Internet (ngrok)';
        btn.className = 'w-full py-3 bg-purple-600 hover:bg-purple-700 text-white font-black text-xs rounded-xl shadow transition-all';
      }
    }

    async function alternarNgrokWeb() {
      const btn = document.getElementById('btnToggleNgrok');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Comunicando con túnel...';

      try {
        const res = await fetch('/api/ngrok/toggle', { method: 'POST' });
        const d = await res.json();
        if (res.ok) {
          actualizarEstadoNgrokUI(d.activo, d.url);
          document.getElementById('imgCodigoQR').src = `/qr?t=${Date.now()}`;
          mostrarToast(d.message);
        } else {
          mostrarToast(d.detail || 'Error al alternar ngrok', true);
        }
      } catch (e) {
        mostrarToast('Error de conexión al activar el túnel', true);
      } finally {
        btn.disabled = false;
      }
    }

    function copiarEnlaceServidor() {
      const url = document.getElementById('lblUrlLocal').textContent;
      navigator.clipboard.writeText(url).then(() => {
        mostrarToast(`📋 Enlace copiado al portapapeles: ${url}`);
      });
    }

    function copiarUrlNgrok() {
      const url = document.getElementById('txtUrlNgrok').value;
      navigator.clipboard.writeText(url).then(() => {
        mostrarToast(`📋 Enlace HTTPS público copiado: ${url}`);
      });
    }

    // ==========================================
    // FUNCIONES DEL MOTOR DE PATIO Y CAPTURA
    // ==========================================
    async function cargarCatalogos(seleccionarOp = null, seleccionarTip = null) {
      await Promise.all([
        poblarDatalist('dl_clientes', '/api/valores-campo?campo=cliente'),
        poblarDatalist('dl_marcas', '/api/valores-campo?campo=marca'),
        poblarDatalist('dl_dimensiones', '/api/valores-campo?campo=dimension')
      ]);

      const resOps = await fetch('/api/operaciones');
      if (resOps.ok) {
        const ops = await resOps.json();
        const selOp = document.getElementById('tipo_operacion');
        selOp.innerHTML = ops.map(op => `<option value="${op}">${op}</option>`).join('');
        if (seleccionarOp) selOp.value = seleccionarOp;
      }

      const resTips = await fetch('/api/tipologias');
      if (resTips.ok) {
        const tips = await resTips.json();
        const selTip = document.getElementById('tipologia');
        selTip.innerHTML = tips.map(t => `<option value="${t.nombre}">${t.nombre}</option>`).join('');
        if (seleccionarTip) selTip.value = seleccionarTip;
        cambioTipologia();
      }
    }

    async function poblarDatalist(elementId, endpoint) {
      try {
        const res = await fetch(endpoint);
        if (res.ok) {
          const items = await res.json();
          const dl = document.getElementById(elementId);
          if (dl) dl.innerHTML = items.map(i => `<option value="${i}">`).join('');
        }
      } catch(e) {}
    }

    async function alCambiarClienteMobile() {
      const cli = document.getElementById('cliente').value.trim();
      if (cli) {
        await Promise.all([
          poblarDatalist('dl_subclientes', `/api/valores-campo?campo=subcliente&cliente=${encodeURIComponent(cli)}`),
          actualizarLimiteCliente()
        ]);
      }
    }

    async function actualizarLimiteCliente() {
      const cli = document.getElementById('cliente').value.trim();
      const res = await fetch(`/api/limite-cliente?cliente=${encodeURIComponent(cli)}`);
      if (res.ok) {
        const d = await res.json();
        const mm = d.limite_retiro_mm || 3.0;
        document.getElementById('lblMmRetiroCliente').textContent = mm.toFixed(1);
        document.getElementById('lblMmAlerta').textContent = mm.toFixed(1);
      }
    }

    function evaluarSugerenciaCambio() {
      const pExt = parseFloat(document.getElementById('prof_ext').value) || 0;
      const pCent = parseFloat(document.getElementById('prof_cent').value) || 0;
      const pInt = parseFloat(document.getElementById('prof_int').value) || 0;
      const mmLimite = parseFloat(document.getElementById('lblMmRetiroCliente').textContent) || 3.0;

      const profs = [pExt, pCent, pInt].filter(p => p > 0);
      const minProf = profs.length ? Math.min(...profs) : 0;
      const boxAlerta = document.getElementById('alertaRetiroInmediato');

      if (minProf > 0 && minProf <= mmLimite) {
        boxAlerta.classList.remove('hidden');
      } else {
        boxAlerta.classList.add('hidden');
      }
    }

    async function cambioTipologia() {
      const tip = document.getElementById('tipologia').value;
      try {
        const res = await fetch(`/api/esquema?tipologia=${encodeURIComponent(tip)}`);
        if (res.ok) {
          const d = await res.json();
          esquemaTipologiaCache = d.esquema;
          listaPosicionesActual = d.posiciones;
          const posActual = parseInt(document.getElementById('posicion').value) || 1;
          renderizarChasisEjes(d.esquema, d.posiciones);
          renderizarBotonesPosicion(d.posiciones, d.esquema);
          renderizarCarruselLlantasMobile();

          // Si la posición actual no existe en la nueva tipología, cambiar a la primera
          if (!listaPosicionesActual.includes(posActual)) {
            seleccionarPosicion(listaPosicionesActual[0] || 1);
          } else {
            seleccionarPosicion(posActual);
          }
        }
      } catch (e) {}
    }

    function toggleConvenciones() {
      document.getElementById('boxConvenciones').classList.toggle('hidden');
    }

    /**
     * Devuelve posiciones y coordenadas para las distribuciones
     * sencillas y duales del diseño aprobado.
     * No renumera, no modifica el esquema y no descarta posiciones.
     */
    function distribuirEjeReferencia(eje) {
      if (!Array.isArray(eje.posiciones)) {
        throw new Error(`El eje ${eje.eje} no contiene posiciones válidas.`);
      }

      const posiciones = eje.posiciones;
      const izquierda = posiciones.filter(p => p.lado === 'izq');
      const derecha = posiciones.filter(p => p.lado === 'der');

      // Una rueda por lado: conserva el rol original (ej. Sencillas: DIR, SEN)
      if (izquierda.length === 1 && derecha.length === 1) {
        return [
          { posicion: izquierda[0], x: 112, y: 12 },
          { posicion: derecha[0], x: 408, y: 12 }
        ];
      }

      // Dos ruedas por lado: duales exterior e interior
      if (izquierda.length === 2 && derecha.length === 2) {
        function obtenerUnica(lado, rol) {
          const coincidencias = lado.filter(p => String(p.rol).toUpperCase().includes(rol));
          if (coincidencias.length === 1) return coincidencias[0];
          return (rol === 'EXT') ? lado[0] : lado[1];
        }

        return [
          { posicion: obtenerUnica(izquierda, 'EXT'), x: 96, y: 12 },
          { posicion: obtenerUnica(izquierda, 'INT'), x: 150, y: 12 },
          { posicion: obtenerUnica(derecha, 'INT'), x: 370, y: 12 },
          { posicion: obtenerUnica(derecha, 'EXT'), x: 424, y: 12 }
        ];
      }

      // Soporte para configuraciones asimétricas sin descartar posiciones
      const resultado = [];
      izquierda.forEach((p, idx) => {
        const x = (izquierda.length === 1) ? 112 : (96 + idx * 54);
        resultado.push({ posicion: p, x, y: 12 });
      });
      derecha.forEach((p, idx) => {
        const x = (derecha.length === 1) ? 408 : (370 + idx * 54);
        resultado.push({ posicion: p, x, y: 12 });
      });
      return resultado;
    }

    // ==============================================================
    // NORMALIZACIÓN DE ETIQUETAS Y ROLES (CHASIS ACCESIBLE)
    // ==============================================================
    function normalizarRolRueda(rol) {
      if (!rol) return '';
      const r = String(rol).trim().toUpperCase();
      if (r.includes('DIR')) return 'DIR';
      if (r.includes('EXT')) return 'EXT';
      if (r.includes('INT')) return 'INT';
      if (r.includes('REP')) return 'REP';
      if (r.includes('SEN') || r.includes('LIB')) return 'SEN';
      return r;
    }

    function normalizarEtiquetaTipo(tipo) {
      if (!tipo) return 'Rodante';
      const t = String(tipo).trim().toLowerCase();
      if (t === 'traccion' || t === 'tracción') return 'Tracción';
      if (t === 'direccional') return 'Direccional';
      if (t === 'libre') return 'Libre';
      if (t === 'repuesto') return 'Repuesto';
      if (t === 'sencilla') return 'Sencilla';
      return tipo.charAt(0).toUpperCase() + tipo.slice(1);
    }

    function obtenerTextoRolLargo(rol) {
      const r = normalizarRolRueda(rol);
      if (r === 'EXT') return 'Exterior (EXT)';
      if (r === 'INT') return 'Interior (INT)';
      if (r === 'DIR') return 'Direccional (DIR)';
      if (r === 'REP') return 'Repuesto (REP)';
      if (r === 'SEN') return 'Sencilla (SEN)';
      return rol || 'Estándar';
    }

    /**
     * Genera el SVG completo de la fila de un eje según la imagen aprobada.
     * viewBox: 0 0 560 158.
     * Neumáticos SIEMPRE en grafito. Insignia superior (check o !) y medallón numérico exterior con color del estado.
     * Selección: contorno azul 2.5px y fondo azul muy tenue #EFF6FF visible en cualquier estado.
     */
    function generarSvgFilaEje(eje, posActual) {
      const items = distribuirEjeReferencia(eje);
      const ejeId = eje.eje;

      let svg = `
        <svg viewBox="0 0 560 158" width="100%" height="auto" class="max-w-[560px] overflow-visible select-none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <!-- 1. Gradiente Base Grafito (Llanta Pendiente) -->
            <linearGradient id="gradRubber_eje_${ejeId}" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#1E293B"/>
              <stop offset="15%" stop-color="#334155"/>
              <stop offset="50%" stop-color="#1E293B"/>
              <stop offset="85%" stop-color="#334155"/>
              <stop offset="100%" stop-color="#0F172A"/>
            </linearGradient>

            <!-- 1b. Gradiente Sutil Esmeralda Técnico (Llanta Registrada OK) -->
            <linearGradient id="gradRubber_ok_eje_${ejeId}" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#0A2A1E"/>
              <stop offset="15%" stop-color="#144633"/>
              <stop offset="50%" stop-color="#0C3324"/>
              <stop offset="85%" stop-color="#144633"/>
              <stop offset="100%" stop-color="#071E15"/>
            </linearGradient>

            <!-- 1c. Gradiente Sutil Ámbar Técnico (Llanta Con Novedad) -->
            <linearGradient id="gradRubber_warn_eje_${ejeId}" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#332008"/>
              <stop offset="15%" stop-color="#4E310C"/>
              <stop offset="50%" stop-color="#3B2509"/>
              <stop offset="85%" stop-color="#4E310C"/>
              <stop offset="100%" stop-color="#211404"/>
            </linearGradient>

            <!-- 2. Gradiente Cilíndrico Metálico del Tubo de Eje -->
            <linearGradient id="gradAxleTube_eje_${ejeId}" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#94A3B8"/>
              <stop offset="25%" stop-color="#E2E8F0"/>
              <stop offset="55%" stop-color="#CBD5E1"/>
              <stop offset="85%" stop-color="#94A3B8"/>
              <stop offset="100%" stop-color="#64748B"/>
            </linearGradient>

            <!-- 3. Gradiente del Cubo Central de Acople -->
            <linearGradient id="gradAcopleCenter_eje_${ejeId}" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#F1F5F9"/>
              <stop offset="50%" stop-color="#CBD5E1"/>
              <stop offset="100%" stop-color="#94A3B8"/>
            </linearGradient>
          </defs>

          <!-- 1. EJE METÁLICO DETALLADO DETRÁS DE LOS NEUMÁTICOS -->
          <g id="eje_metalico_${ejeId}">
            <line x1="120" y1="58.5" x2="440" y2="58.5" stroke="#CBD5E1" stroke-width="2" opacity="0.6"/>
            <rect x="120" y="52.5" width="320" height="6.5" rx="1.5" fill="url(#gradAxleTube_eje_${ejeId})" stroke="#94A3B8" stroke-width="0.75"/>
            <rect x="162" y="50" width="3.5" height="11.5" rx="1" fill="#E2E8F0" stroke="#64748B" stroke-width="0.75"/>
            <rect x="394" y="50" width="3.5" height="11.5" rx="1" fill="#E2E8F0" stroke="#64748B" stroke-width="0.75"/>
            <rect x="267" y="47.5" width="26" height="16.5" rx="3.5" fill="url(#gradAcopleCenter_eje_${ejeId})" stroke="#64748B" stroke-width="1.2"/>
            <circle cx="280" cy="55.75" r="7.5" fill="#E2E8F0" stroke="#475569" stroke-width="1.2"/>
            <circle cx="280" cy="55.75" r="2.5" fill="#334155"/>
            <circle cx="270" cy="50.5" r="1.2" fill="#475569"/>
            <circle cx="290" cy="50.5" r="1.2" fill="#475569"/>
            <circle cx="270" cy="61" r="1.2" fill="#475569"/>
            <circle cx="290" cy="61" r="1.2" fill="#475569"/>
          </g>
      `;

      // 2. NEUMÁTICOS ILUSTRADOS Y CÍRCULOS DE NÚMERO
      items.forEach(item => {
        const p = item.posicion;
        const x = item.x;
        const y = item.y; // 12
        const esSeleccionada = (p.pos === posActual);
        const tieneNovedad = posicionesConNovedadPlaca.has(p.pos);
        const esInspeccionada = posicionesInspeccionadasPlaca.has(p.pos);
        const textoNovedad = tieneNovedad ? (posicionesConNovedadPlaca.get(p.pos) || 'Novedad registrada') : '';

        // Caucho con cambio de color sutil y profesional al ser inspeccionada
        let fillCaucho = `url(#gradRubber_eje_${ejeId})`;
        let strokeCaucho = '#0F172A';
        let strokeWidthCaucho = '1.25';
        let colorSurcos = '#0F172A';

        if (tieneNovedad) {
          fillCaucho = `url(#gradRubber_warn_eje_${ejeId})`;
          strokeCaucho = '#92400E';
          colorSurcos = '#451A03';
        } else if (esInspeccionada) {
          fillCaucho = `url(#gradRubber_ok_eje_${ejeId})`;
          strokeCaucho = '#065F46';
          colorSurcos = '#022C22';
        }
        let ariaTitle = `Llanta posición ${p.pos}, rol ${normalizarRolRueda(p.rol)}`;

        if (tieneNovedad) {
          ariaTitle += ` - Con Novedad: ${textoNovedad}`;
        } else if (esInspeccionada) {
          ariaTitle += ' - Registrada';
        }

        svg += `
          <g id="neumatico_node_${p.pos}" class="tire-interactive-node" onclick="seleccionarPosicion(${p.pos})" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();seleccionarPosicion(${p.pos});}" role="button" tabindex="0" aria-label="${ariaTitle}">
            <title>${ariaTitle}</title>
            
            <!-- A. Anillo y Fondo de Selección Activa (Contorno azul 2.5px más fondo azul muy tenue #EFF6FF) -->
            ${esSeleccionada ? `
              <rect x="${x - 5}" y="${y - 5}" width="50" height="102" rx="12" fill="#EFF6FF" stroke="#2563EB" stroke-width="2.5" class="tire-selection-ring"/>
            ` : ''}

            <!-- B. Sombra suave bajo el neumático -->
            <ellipse cx="${x + 20}" cy="${y + 93}" rx="17" ry="3.5" fill="#000000" opacity="0.18"/>

            <!-- C. Silueta Principal del Neumático (SIEMPRE GRAFITO) -->
            <rect x="${x}" y="${y}" width="40" height="92" rx="8" fill="${fillCaucho}" stroke="${strokeCaucho}" stroke-width="${strokeWidthCaucho}" class="tire-rubber-body"/>

            <!-- D. Surcos Longitudinales Continuos -->
            <line x1="${x + 13}" y1="${y + 5}" x2="${x + 13}" y2="${y + 87}" stroke="${colorSurcos}" stroke-width="2" stroke-linecap="round"/>
            <line x1="${x + 27}" y1="${y + 5}" x2="${x + 27}" y2="${y + 87}" stroke="${colorSurcos}" stroke-width="2" stroke-linecap="round"/>
        `;

        // E. Ranuras transversales en hombros
        for (let cutY = y + 10; cutY <= y + 82; cutY += 9) {
          svg += `
            <line x1="${x + 2}" y1="${cutY}" x2="${x + 10}" y2="${cutY}" stroke="${colorSurcos}" stroke-width="1.2" opacity="0.85"/>
            <line x1="${x + 30}" y1="${cutY}" x2="${x + 38}" y2="${cutY}" stroke="${colorSurcos}" stroke-width="1.2" opacity="0.85"/>
          `;
        }

        // Tacos centrales discretos
        for (let tY = y + 14; tY <= y + 78; tY += 14) {
          svg += `
            <line x1="${x + 16}" y1="${tY}" x2="${x + 24}" y2="${tY}" stroke="${colorSurcos}" stroke-width="1.2" opacity="0.6"/>
          `;
        }

        // Insignias superiores de estado: Check verde (Registrada) o '!' Ámbar (Con Novedad)
        if (tieneNovedad) {
          svg += `
            <!-- Insignia: '!' Ámbar para Con Novedad -->
            <g id="badge_warn_${p.pos}">
              <circle cx="${x + 32}" cy="${y + 8.5}" r="7.5" fill="#F59E0B" stroke="#FFFFFF" stroke-width="1.6"/>
              <line x1="${x + 32}" y1="${y + 4.8}" x2="${x + 32}" y2="${y + 9}" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
              <circle cx="${x + 32}" cy="${y + 11.8}" r="1" fill="#FFFFFF"/>
            </g>
          `;
        } else if (esInspeccionada) {
          svg += `
            <!-- Insignia: Check Verde para Registrada -->
            <g id="badge_ok_${p.pos}">
              <circle cx="${x + 32}" cy="${y + 8.5}" r="7" fill="#10B981" stroke="#FFFFFF" stroke-width="1.6"/>
              <path d="M ${x + 29.5} ${y + 8.5} L ${x + 31.5} ${y + 10.5} L ${x + 34.5} ${y + 6.8}" fill="none" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            </g>
          `;
        }

        // Medallón Numérico Exterior en y = 125 con el color del estado
        const cxNum = x + 20;
        const cyNum = 125;
        let fillCirculo = '#F8FAFC';
        let strokeCirculo = '#CBD5E1';
        let strokeWidthNum = '1.2';
        let fillTexto = '#1E293B';

        if (tieneNovedad) {
          fillCirculo = '#FFFBEB';
          strokeCirculo = '#F59E0B';
          strokeWidthNum = '2';
          fillTexto = '#B45309';
        } else if (esInspeccionada) {
          fillCirculo = '#ECFDF5';
          strokeCirculo = '#10B981';
          strokeWidthNum = '2';
          fillTexto = '#047857';
        }

        // Selección resalta con anillo exterior azul de 2.5px visible en cualquier estado
        let ringSeleccionNum = '';
        if (esSeleccionada) {
          ringSeleccionNum = `
            <circle cx="${cxNum}" cy="${cyNum}" r="15" fill="none" stroke="#2563EB" stroke-width="2.5" opacity="0.95"/>
          `;
        }

        svg += `
            <!-- Medallón Numérico Exterior -->
            ${ringSeleccionNum}
            <circle cx="${cxNum}" cy="${cyNum}" r="12" fill="${fillCirculo}" stroke="${strokeCirculo}" stroke-width="${strokeWidthNum}"/>
            <text x="${cxNum}" y="${cyNum + 0.5}" font-size="11.5" font-weight="800" fill="${fillTexto}" font-family="system-ui, -apple-system, sans-serif" text-anchor="middle" dominant-baseline="central">
              ${p.pos}
            </text>

            <!-- G. Etiqueta de Rol (DIR, EXT, INT...) en mayúsculas, 10.5px, sans-serif -->
            <text x="${cxNum}" y="148" font-size="10.5" font-weight="700" fill="#64748B" font-family="system-ui, -apple-system, sans-serif" text-anchor="middle" letter-spacing="0.5">
              ${normalizarRolRueda(p.rol)}
            </text>

          </g>
        `;
      });

      svg += `</svg>`;
      return svg;
    }

    /**
     * Genera la caja miniatura de la rueda de repuesto para la sección independiente.
     * Soporta estados: Seleccionada, Con Novedad (!), Registrada (✓) y Pendiente.
     */
    function generarCajaRepuestoHtml(pos, rol, posActual) {
      const esSeleccionada = (pos === posActual);
      const tieneNovedad = posicionesConNovedadPlaca.has(pos);
      const esInspeccionada = posicionesInspeccionadasPlaca.has(pos);
      const textoNovedad = tieneNovedad ? (posicionesConNovedadPlaca.get(pos) || 'Novedad registrada') : '';

      let borderCardClass = 'bg-[#F8FAFC] border-slate-200 hover:bg-slate-100';
      if (esSeleccionada) {
        borderCardClass = 'bg-blue-50/90 border-blue-400 ring-2 ring-blue-500 shadow-sm';
      } else if (tieneNovedad) {
        borderCardClass = 'bg-amber-50/80 border-amber-400 ring-1 ring-amber-300 shadow-sm';
      } else if (esInspeccionada) {
        borderCardClass = 'bg-emerald-50/80 border-emerald-400 ring-1 ring-emerald-300 shadow-sm';
      }

      const div = document.createElement('div');
      div.className = `tire-repuesto-card p-2.5 rounded-2xl border transition-all cursor-pointer flex flex-col items-center ${borderCardClass} ${ruedaSinRepuestoMarcada ? 'opacity-30 line-through' : ''}`;
      div.onclick = () => seleccionarPosicion(pos);
      div.setAttribute('tabindex', '0');
      div.setAttribute('role', 'button');
      div.setAttribute('aria-label', `Llanta de repuesto posición ${pos}${tieneNovedad ? ' - Con Novedad: ' + textoNovedad : esInspeccionada ? ' - Registrada' : ''}`);
      div.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          seleccionarPosicion(pos);
        }
      };

      // Caucho con cambio de color sutil para repuesto
      div.innerHTML = `
        <svg viewBox="0 0 40 92" width="28" height="64" class="overflow-visible select-none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="gradRubberRep_${pos}" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#1E293B"/>
              <stop offset="20%" stop-color="#334155"/>
              <stop offset="50%" stop-color="#1E293B"/>
              <stop offset="80%" stop-color="#334155"/>
              <stop offset="100%" stop-color="#0F172A"/>
            </linearGradient>
            <linearGradient id="gradRubberRep_ok_${pos}" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#0A2A1E"/>
              <stop offset="20%" stop-color="#144633"/>
              <stop offset="50%" stop-color="#0C3324"/>
              <stop offset="80%" stop-color="#144633"/>
              <stop offset="100%" stop-color="#071E15"/>
            </linearGradient>
            <linearGradient id="gradRubberRep_warn_${pos}" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#332008"/>
              <stop offset="20%" stop-color="#4E310C"/>
              <stop offset="50%" stop-color="#3B2509"/>
              <stop offset="80%" stop-color="#4E310C"/>
              <stop offset="100%" stop-color="#211404"/>
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="40" height="92" rx="8" fill="${tieneNovedad ? `url(#gradRubberRep_warn_${pos})` : esInspeccionada ? `url(#gradRubberRep_ok_${pos})` : `url(#gradRubberRep_${pos})`}" stroke="${tieneNovedad ? '#92400E' : esInspeccionada ? '#065F46' : '#0F172A'}" stroke-width="1.25"/>
          <line x1="13" y1="5" x2="13" y2="87" stroke="${tieneNovedad ? '#451A03' : esInspeccionada ? '#022C22' : '#0F172A'}" stroke-width="2"/>
          <line x1="27" y1="5" x2="27" y2="87" stroke="${tieneNovedad ? '#451A03' : esInspeccionada ? '#022C22' : '#0F172A'}" stroke-width="2"/>
          <!-- Tacos -->
          <line x1="2" y1="20" x2="10" y2="20" stroke="#0F172A" stroke-width="1.2"/>
          <line x1="30" y1="20" x2="38" y2="20" stroke="#0F172A" stroke-width="1.2"/>
          <line x1="2" y1="46" x2="10" y2="46" stroke="#0F172A" stroke-width="1.2"/>
          <line x1="30" y1="46" x2="38" y2="46" stroke="#0F172A" stroke-width="1.2"/>
          <line x1="2" y1="72" x2="10" y2="72" stroke="#0F172A" stroke-width="1.2"/>
          <line x1="30" y1="72" x2="38" y2="72" stroke="#0F172A" stroke-width="1.2"/>
          
          ${tieneNovedad ? `
            <circle cx="32" cy="8.5" r="7.5" fill="#F59E0B" stroke="#FFFFFF" stroke-width="1.5"/>
            <line x1="32" y1="5" x2="32" y2="9" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
            <circle cx="32" cy="11.5" r="0.9" fill="#FFFFFF"/>
          ` : esInspeccionada ? `
            <circle cx="32" cy="8.5" r="7" fill="#10B981" stroke="#FFFFFF" stroke-width="1.5"/>
            <path d="M 29.5 8.5 L 31.5 10.5 L 34.5 6.8" fill="none" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          ` : ''}
        </svg>

        <span class="mt-1.5 font-sans text-xs font-black flex items-center space-x-1 ${
          tieneNovedad ? 'text-amber-700' : esInspeccionada ? 'text-emerald-700' : 'text-slate-800'
        }">
          <span>${pos}</span>
          ${tieneNovedad ? '<span class="text-[10px]">!</span>' : esInspeccionada ? '<span class="text-[10px]">✓</span>' : ''}
        </span>
        <span class="text-[10px] font-bold text-slate-500 uppercase">REP</span>
      `;

      return div;
    }

    /**
     * Actualiza el panel resumen con la posición seleccionada (Subido a columna derecha).
     * Muestra la insignia de estado 'Registrada' una sola vez.
     */
    function renderizarResumenPosicion(posActual) {
      const panel = document.getElementById('panelResumenPosicion');
      if (!panel) return;

      const esq = esquemaTipologiaCache || [];
      let posData = null;
      let ejeData = null;

      for (const e of esq) {
        for (const p of (e.posiciones || [])) {
          if (p.pos === posActual) {
            posData = p;
            ejeData = e;
            break;
          }
        }
        if (posData) break;
      }

      if (!posData || !ejeData) {
        panel.innerHTML = `
          <div class="flex items-center space-x-2 text-slate-500 font-bold text-xs">
            <span>Posición ${posActual} activa</span>
          </div>
        `;
        return;
      }

      const esRep = (ejeData.eje === 99 || (ejeData.tipo || '').toLowerCase() === 'repuesto');
      const tipoNormalizado = normalizarEtiquetaTipo(ejeData.tipo);
      const nombreEje = esRep ? 'Soporte de Repuesto' : `Eje ${ejeData.eje} · ${tipoNormalizado}`;
      const ladoTexto = posData.lado === 'izq' ? 'Lado Izquierdo' : posData.lado === 'der' ? 'Lado Derecho' : 'Soporte Central';
      const rolTexto = obtenerTextoRolLargo(posData.rol);
      
      const tieneNovedad = posicionesConNovedadPlaca.has(posActual);
      const estaInsp = posicionesInspeccionadasPlaca.has(posActual);
      const textoNovedad = tieneNovedad ? (posicionesConNovedadPlaca.get(posActual) || 'Novedad registrada') : '';

      let badgeEstadoHtml = '';
      if (tieneNovedad) {
        badgeEstadoHtml = `
          <span class="px-2.5 py-1 rounded-full text-xs font-black bg-amber-100 text-amber-900 border border-amber-300 flex items-center space-x-1.5 shadow-xs">
            <span class="w-3.5 h-3.5 rounded-full bg-amber-500 text-white flex items-center justify-center text-[10px]">!</span>
            <span>Con Novedad</span>
          </span>
        `;
      } else if (estaInsp) {
        badgeEstadoHtml = `
          <span class="px-2.5 py-1 rounded-full text-xs font-black bg-emerald-50 text-emerald-800 border border-emerald-300 flex items-center space-x-1.5 shadow-xs">
            <i class="fa-solid fa-check text-emerald-600 text-xs"></i>
            <span>Registrada</span>
          </span>
        `;
      } else {
        badgeEstadoHtml = `
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200 flex items-center space-x-1">
            <i class="fa-solid fa-clock text-slate-400 text-[10px]"></i>
            <span>Pendiente</span>
          </span>
        `;
      }

      panel.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <span class="w-9 h-9 rounded-xl bg-blue-600 text-white font-black flex items-center justify-center text-base font-mono shadow-md shadow-blue-500/20">
              ${posActual}
            </span>
            <div>
              <div class="font-extrabold text-slate-900 text-xs sm:text-sm">
                ${nombreEje} · ${ladoTexto}
              </div>
              <div class="text-xs text-slate-500 font-medium">
                Posición: <b class="text-slate-800">${rolTexto}</b>
              </div>
            </div>
          </div>

          <div>
            ${badgeEstadoHtml}
          </div>
        </div>

        ${tieneNovedad ? `
          <div class="mt-2.5 text-xs text-amber-900 font-bold bg-amber-50 px-2.5 py-1.5 rounded-xl border border-amber-200 flex items-center space-x-2">
            <i class="fa-solid fa-triangle-exclamation text-amber-600 text-xs"></i>
            <span>Novedad: ${textoNovedad}</span>
          </div>
        ` : ''}
      `;
    }

    /**
     * Renderiza el componente completo de Chasis Vectorial por Ejes.
     */
    function renderizarChasisEjes(esquema, posiciones) {
      const contenedor = document.getElementById('contenedorChasisEjes');
      if (!contenedor) return;
      contenedor.innerHTML = '';
      const posActual = parseInt(document.getElementById('posicion').value) || 1;

      if (!esquema || esquema.length === 0) {
        contenedor.innerHTML = '<div class="text-center text-xs text-slate-400 py-6">Selecciona una tipología</div>';
        return;
      }

      // 1. Título de Configuración y Contador de Progreso
      const selTip = document.getElementById('tipologia');
      const tipNombre = selTip ? (selTip.options[selTip.selectedIndex]?.text || selTip.value) : 'Vehículo';
      
      const lblTitulo = document.getElementById('lblTituloConfiguracion');
      if (lblTitulo) lblTitulo.textContent = tipNombre;

      const totalPos = (posiciones && posiciones.length > 0) ? posiciones.length : (listaPosicionesActual.length || 1);
      const inspCount = Array.from(posicionesInspeccionadasPlaca).filter(p => (posiciones || listaPosicionesActual).includes(p)).length;

      const badgeContador = document.getElementById('badgeContadorProgreso');
      if (badgeContador) badgeContador.textContent = `${inspCount} de ${totalPos}`;

      const barraProgreso = document.getElementById('barraProgresoChasis');
      if (barraProgreso) {
        const pct = totalPos > 0 ? (inspCount / totalPos) * 100 : 0;
        barraProgreso.style.width = `${pct}%`;
      }

      // 2. Separar Ejes Rodantes del Eje de Repuesto (eje 99 o tipo repuesto)
      const ejesRodantes = esquema.filter(e => e.eje !== 99 && (e.tipo || '').toLowerCase() !== 'repuesto');
      const ejeRepuesto = esquema.find(e => e.eje === 99 || (e.tipo || '').toLowerCase() === 'repuesto');

      // 3. Renderizar Filas de Ejes Rodantes con separador horizontal claro
      ejesRodantes.forEach((eje, idx) => {
        const filaDiv = document.createElement('div');
        filaDiv.className = `space-y-1.5 pb-3 ${idx < ejesRodantes.length - 1 ? 'border-b border-slate-100' : ''}`;

        // Encabezado de la Fila con tildes normalizadas (Tracción, Direccional, Libre)
        const headerFila = document.createElement('div');
        headerFila.className = 'flex items-center space-x-2 text-xs text-slate-500 pl-1';
        const labelTipo = normalizarEtiquetaTipo(eje.tipo);

        headerFila.innerHTML = `
          <span class="w-2 h-2 rounded-full bg-slate-400"></span>
          <span class="font-black text-slate-800">Eje ${eje.eje}</span>
          <span class="text-slate-300">•</span>
          <span class="font-bold text-slate-600">${labelTipo}</span>
        `;
        filaDiv.appendChild(headerFila);

        // SVG del Eje
        const svgBox = document.createElement('div');
        svgBox.className = 'w-full flex justify-center';
        svgBox.innerHTML = generarSvgFilaEje(eje, posActual);
        filaDiv.appendChild(svgBox);

        contenedor.appendChild(filaDiv);
      });

      // 4. Renderizar Sección de Repuesto Independiente al pie
      const secRepuesto = document.getElementById('seccionRepuestoChasis');
      const cajaRepuesto = document.getElementById('contenedorCajaRepuestoChasis');
      const btnSinRep = document.getElementById('btnSinRepuesto');

      if (cajaRepuesto) cajaRepuesto.innerHTML = '';

      if (ejeRepuesto && ejeRepuesto.posiciones && ejeRepuesto.posiciones.length > 0) {
        if (secRepuesto) secRepuesto.classList.remove('hidden');
        if (btnSinRep) btnSinRep.parentElement.classList.remove('hidden');
        ejeRepuesto.posiciones.forEach(p => {
          if (cajaRepuesto) cajaRepuesto.appendChild(generarCajaRepuestoHtml(p.pos, p.rol || 'REP', posActual));
        });
      } else {
        if (secRepuesto) secRepuesto.classList.add('hidden');
        if (btnSinRep) btnSinRep.parentElement.classList.add('hidden');
      }

      // 5. Renderizar Resumen Exterior de la Posición Activa
      renderizarResumenPosicion(posActual);
    }

    /**
     * Renderiza el selector alternativo accesible en HTML.
     */
    function renderizarBotonesPosicion(posiciones, esquema) {
      const grid = document.getElementById('gridBotonesPosicion');
      if (!grid) return;
      grid.innerHTML = '';
      const posActual = parseInt(document.getElementById('posicion').value) || 1;
      const esq = esquema || esquemaTipologiaCache;

      if (esq && esq.length > 0) {
        esq.forEach(eje => {
          const cardEje = document.createElement('div');
          cardEje.className = 'bg-slate-50 border border-slate-200 rounded-xl p-2 space-y-1.5';

          let titulo = eje.nombre || `Eje ${eje.eje}`;
          if (eje.eje === 99 || (eje.tipo || '').toLowerCase() === 'repuesto') titulo = 'Soporte de Repuesto';

          cardEje.innerHTML = `
            <div class="flex items-center justify-between text-[11px] font-bold text-slate-700">
              <span>${titulo}</span>
              <span class="text-[10px] text-slate-400 font-mono">${(eje.posiciones || []).length} llanta(s)</span>
            </div>
            <div class="flex flex-wrap gap-1.5"></div>
          `;

          const boxBtns = cardEje.querySelector('.flex.flex-wrap');
          (eje.posiciones || []).forEach(p => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.id = `btn_pos_${p.pos}`;
            const tieneNovedad = posicionesConNovedadPlaca.has(p.pos);
            const estaInspeccionada = posicionesInspeccionadasPlaca.has(p.pos);
            const esRepuestoDesactivado = (eje.tipo === 'repuesto' || eje.eje === 99) && ruedaSinRepuestoMarcada;

            let estadoClase = 'bg-white text-slate-800 hover:bg-slate-100';
            let iconoBadge = '';
            if (p.pos === posActual) {
              estadoClase = 'active';
              if (tieneNovedad) iconoBadge = '<i class="fa-solid fa-triangle-exclamation text-[9px] text-amber-300"></i>';
              else if (estaInspeccionada) iconoBadge = '<i class="fa-solid fa-check text-[9px] text-emerald-300"></i>';
            } else if (tieneNovedad) {
              estadoClase = 'with-warning';
              iconoBadge = '<i class="fa-solid fa-triangle-exclamation text-[9px] text-amber-600"></i>';
            } else if (estaInspeccionada) {
              estadoClase = 'inspected';
              iconoBadge = '<i class="fa-solid fa-check text-[9px] text-emerald-600"></i>';
            }

            btn.className = `pos-btn px-2.5 py-1.5 text-xs font-black rounded-lg border border-slate-200 transition-all flex items-center space-x-1 ${estadoClase} ${
              esRepuestoDesactivado ? 'opacity-40 line-through' : ''
            }`;
            
            btn.innerHTML = `
              <span>${p.pos}</span>
              <span class="text-[9px] opacity-60">(${p.rol || ''})</span>
              ${iconoBadge}
            `;
            btn.onclick = () => seleccionarPosicion(p.pos);
            boxBtns.appendChild(btn);
          });

          grid.appendChild(cardEje);
        });
      } else {
        const boxPlano = document.createElement('div');
        boxPlano.className = 'grid grid-cols-4 gap-1.5';
        (posiciones || []).forEach(p => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.id = `btn_pos_${p}`;
          const tieneNovedad = posicionesConNovedadPlaca.has(p);
          const estaInspeccionada = posicionesInspeccionadasPlaca.has(p);
          let estadoClase = 'bg-slate-50 text-slate-800 hover:bg-slate-100';
          let iconoBadge = '';
          if (p === posActual) {
            estadoClase = 'active';
            if (tieneNovedad) iconoBadge = '<i class="fa-solid fa-triangle-exclamation text-[9px] text-amber-300 ml-0.5"></i>';
            else if (estaInspeccionada) iconoBadge = '<i class="fa-solid fa-check text-[9px] text-emerald-300 ml-0.5"></i>';
          } else if (tieneNovedad) {
            estadoClase = 'with-warning';
            iconoBadge = '<i class="fa-solid fa-triangle-exclamation text-[9px] text-amber-600 ml-0.5"></i>';
          } else if (estaInspeccionada) {
            estadoClase = 'inspected';
            iconoBadge = '<i class="fa-solid fa-check text-[9px] text-emerald-600 ml-0.5"></i>';
          }
          btn.className = `pos-btn py-2 text-xs font-black rounded-xl border border-slate-200 transition-all ${estadoClase}`;
          btn.innerHTML = `${p} ${iconoBadge}`;
          btn.onclick = () => seleccionarPosicion(p);
          boxPlano.appendChild(btn);
        });
        grid.appendChild(boxPlano);
      }
    }

    // ==========================================
    // NAVEGACIÓN SUAVE & FOCO EN PANTALLA UNIFICADA
    // ==========================================
    function irAMedicionesPosicion() {
      const modMed = document.getElementById('moduloMediciones');
      if (modMed) {
        modMed.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const pExt = document.getElementById('prof_ext');
        if (pExt) setTimeout(() => pExt.focus(), 350);
      }
    }

    function cambiarModoPatioMobile(modo) {
      if (modo === 'form' || modo === 'mediciones') {
        irAMedicionesPosicion();
      } else if (modo === 'chasis') {
        const modChasis = document.getElementById('moduloChasis');
        if (modChasis) modChasis.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    function renderizarCarruselLlantasMobile() {
      const contenedor = document.getElementById('carruselLlantasMobile');
      if (!contenedor) return;
      contenedor.innerHTML = '';
      const posActual = parseInt(document.getElementById('posicion').value) || 1;

      if (!listaPosicionesActual || listaPosicionesActual.length === 0) return;

      listaPosicionesActual.forEach(p => {
        const esSeleccionada = (p === posActual);
        const tieneNovedad = posicionesConNovedadPlaca.has(p);
        const estaInspeccionada = posicionesInspeccionadasPlaca.has(p);

        // Obtener rol
        let rol = '';
        if (esquemaTipologiaCache) {
          for (const eje of esquemaTipologiaCache) {
            const match = (eje.posiciones || []).find(item => item.pos === p);
            if (match) { rol = match.rol || ''; break; }
          }
        }

        let clasePill = 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50';
        let textoSubPill = rol || 'Pos';

        if (esSeleccionada) {
          clasePill = 'active bg-blue-600 text-white border-blue-600 shadow-md ring-2 ring-blue-300';
          if (tieneNovedad) textoSubPill = '⚠️ ' + (rol || 'Nov');
          else if (estaInspeccionada) textoSubPill = '✓ ' + (rol || 'OK');
        } else if (tieneNovedad) {
          clasePill = 'bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100 ring-1 ring-amber-300';
          textoSubPill = '⚠️ ' + (rol || 'Nov');
        } else if (estaInspeccionada) {
          clasePill = 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100 ring-1 ring-emerald-300';
          textoSubPill = '✓ ' + (rol || 'OK');
        }

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.id = `carrusel_pill_${p}`;
        btn.className = `carrusel-tire-pill rounded-xl border flex flex-col items-center justify-center text-xs font-black select-none ${clasePill}`;

        btn.innerHTML = `
          <span class="leading-none text-sm font-mono">${p}</span>
          <span class="text-[9px] font-bold opacity-80 leading-none mt-0.5">${textoSubPill}</span>
        `;
        btn.onclick = () => seleccionarPosicion(p);
        contenedor.appendChild(btn);
      });

      actualizarBarraPosicionMobile(posActual);
    }

    function actualizarBarraPosicionMobile(posActual) {
      // 1. Número en pill superior y en botón sticky inferior
      const lblPill = document.getElementById('lblPosPill');
      const lblSticky = document.getElementById('lblPosStickyBtn');
      if (lblPill) lblPill.textContent = posActual;
      if (lblSticky) lblSticky.textContent = posActual;

      // 2. Estado inspeccionada / con novedad / pendiente
      const badgeEstado = document.getElementById('badgeEstadoPosPill');
      const tieneNovedad = posicionesConNovedadPlaca.has(posActual);
      const estaInsp = posicionesInspeccionadasPlaca.has(posActual);
      if (badgeEstado) {
        if (tieneNovedad) {
          badgeEstado.className = 'text-[10px] font-black px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 flex items-center space-x-1';
          badgeEstado.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-amber-600 text-[9px] mr-1"></i>Con Novedad';
        } else if (estaInsp) {
          badgeEstado.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center space-x-1';
          badgeEstado.innerHTML = '<i class="fa-solid fa-check text-[8px] mr-1"></i>Registrada';
        } else {
          badgeEstado.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200';
          badgeEstado.innerHTML = '<i class="fa-solid fa-hourglass-half text-[8px] mr-1"></i>Pendiente';
        }
      }

      // 3. Detalle de eje, lado y rol
      const lblDetalle = document.getElementById('lblDetallePosPill');
      if (lblDetalle && esquemaTipologiaCache) {
        let matchPos = null;
        let matchEje = null;
        for (const eje of esquemaTipologiaCache) {
          const item = (eje.posiciones || []).find(x => x.pos === posActual);
          if (item) {
            matchPos = item;
            matchEje = eje;
            break;
          }
        }
        if (matchPos && matchEje) {
          const nombreEje = (matchEje.eje === 99 || (matchEje.tipo || '').toLowerCase() === 'repuesto') ? 'Repuesto' : `Eje ${matchEje.eje} (${matchEje.tipo || 'Rodante'})`;
          const lado = matchPos.lado === 'izq' ? 'Lado Izq (Conductor)' : matchPos.lado === 'der' ? 'Lado Der (Acompañante)' : 'Repuesto';
          const rol = matchPos.rol ? ` · ${matchPos.rol}` : '';
          lblDetalle.textContent = `${nombreEje} · ${lado}${rol}`;
        }
      }

      // 4. Progreso total en insignias
      const total = listaPosicionesActual ? listaPosicionesActual.length : 10;
      const count = posicionesInspeccionadasPlaca ? posicionesInspeccionadasPlaca.size : 0;
      const txtProgreso = `${count} / ${total}`;
      const lblProg = document.getElementById('lblTotalLlantasProgreso');
      const badgeChasisMob = document.getElementById('badgeProgresoChasisMobile');
      if (lblProg) lblProg.textContent = txtProgreso;
      if (badgeChasisMob) badgeChasisMob.textContent = txtProgreso;

      const bannerCompleto = document.getElementById('bannerInspeccionCompletaPatio');
      if (bannerCompleto) {
        if (count >= total && total > 0) {
          bannerCompleto.classList.remove('hidden');
          bannerCompleto.classList.add('flex');
        } else {
          bannerCompleto.classList.add('hidden');
          bannerCompleto.classList.remove('flex');
        }
      }

      // 5. Actualizar estilos del carrusel y hacer auto-scroll al seleccionado
      if (listaPosicionesActual && listaPosicionesActual.length > 0) {
        listaPosicionesActual.forEach(p => {
          const pill = document.getElementById(`carrusel_pill_${p}`);
          if (!pill) return;
          const esSel = (p === posActual);
          const esInsp = posicionesInspeccionadasPlaca.has(p);

          pill.className = `carrusel-tire-pill rounded-xl border flex flex-col items-center justify-center text-xs font-black select-none ${
            esSel
              ? 'active bg-blue-600 text-white border-blue-600 shadow-md ring-2 ring-blue-300'
              : esInsp
                ? 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100'
                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`;
          if (esSel) {
            pill.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
          }
        });
      }
    }

    function irPosicionAnterior() {
      if (!listaPosicionesActual || listaPosicionesActual.length === 0) return;
      const posActual = parseInt(document.getElementById('posicion').value) || listaPosicionesActual[0];
      const idx = listaPosicionesActual.indexOf(posActual);
      if (idx > 0) {
        seleccionarPosicion(listaPosicionesActual[idx - 1]);
      } else {
        seleccionarPosicion(listaPosicionesActual[listaPosicionesActual.length - 1]);
      }
    }

    function irPosicionSiguiente() {
      if (!listaPosicionesActual || listaPosicionesActual.length === 0) return;
      const posActual = parseInt(document.getElementById('posicion').value) || listaPosicionesActual[0];
      const idx = listaPosicionesActual.indexOf(posActual);
      if (idx !== -1 && idx + 1 < listaPosicionesActual.length) {
        seleccionarPosicion(listaPosicionesActual[idx + 1]);
      } else {
        seleccionarPosicion(listaPosicionesActual[0]);
      }
    }

    function igualarProfundidades() {
      const pExt = document.getElementById('prof_ext').value.trim();
      const pCent = document.getElementById('prof_cent').value.trim();
      const pInt = document.getElementById('prof_int').value.trim();

      const valor = pExt || pCent || pInt;
      if (!valor) {
        mostrarToast('Ingresa al menos una profundidad para poder igualar', true);
        return;
      }

      document.getElementById('prof_ext').value = valor;
      document.getElementById('prof_cent').value = valor;
      document.getElementById('prof_int').value = valor;
      evaluarSugerenciaCambio();
      mostrarToast(`✅ Profundidades igualadas a ${valor} mm`);
    }

    function setPsiRapido(val) {
      document.getElementById('psi').value = val;
      mostrarToast(`Presión establecida en ${val} PSI`);
    }

    // ==========================================
    // VALIDACIÓN ESTÁNDAR DE FORMULARIOS & ERRORES
    // ==========================================
    function marcarErrorCampo(campoId, errorId, mensaje) {
      const el = document.getElementById(campoId);
      const err = document.getElementById(errorId);
      if (el) {
        el.classList.add('border-rose-500', 'bg-rose-50/50', 'ring-2', 'ring-rose-400/30');
      }
      if (err) {
        if (mensaje) {
          const span = err.querySelector('span');
          if (span) span.textContent = mensaje;
        }
        err.classList.remove('hidden');
      }
    }

    function limpiarErrorCampo(campoId) {
      if (campoId === 'placa') {
        const el = document.getElementById('placa');
        const err = document.getElementById('err_placa');
        if (el) el.classList.remove('border-rose-500', 'bg-rose-50/50', 'ring-2', 'ring-rose-400/30');
        if (err) err.classList.add('hidden');
      } else if (campoId === 'profundidades') {
        ['prof_ext', 'prof_cent', 'prof_int'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.remove('border-rose-500', 'bg-rose-50/50', 'ring-2', 'ring-rose-400/30');
        });
        const err = document.getElementById('err_profundidades');
        if (err) err.classList.add('hidden');
      } else if (campoId === 'psi') {
        const el = document.getElementById('psi');
        const err = document.getElementById('err_psi');
        if (el) el.classList.remove('border-rose-500', 'bg-rose-50/50', 'ring-2', 'ring-rose-400/30');
        if (err) err.classList.add('hidden');
      }
    }

    function limpiarTodosErroresFormulario() {
      limpiarErrorCampo('placa');
      limpiarErrorCampo('profundidades');
      limpiarErrorCampo('psi');
    }

    // ==========================================
    // NOVEDADES & FOTO DE EVIDENCIA (CÁMARA / GALERÍA)
    // ==========================================
    // ==========================================
    // GESTIÓN DE EVIDENCIAS FOTOGRÁFICAS (1 O VARIAS FOTOS) & VISOR
    // ==========================================
    function obtenerListaFotos(fotoCampo) {
      if (!fotoCampo) return [];
      if (Array.isArray(fotoCampo)) return fotoCampo.filter(Boolean);
      if (typeof fotoCampo === 'string') {
        const trimmed = fotoCampo.trim();
        if (!trimmed) return [];
        if (trimmed.startsWith('[')) {
          try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) return parsed.filter(Boolean);
          } catch (e) {
            console.error('Error parseando JSON de fotos:', e);
          }
        }
        if (trimmed.startsWith('data:image') || trimmed.startsWith('http') || trimmed.startsWith('/')) {
          return [trimmed];
        }
      }
      return [];
    }

    function evaluarHabilitarFotoNovedad() {
      const nov = document.getElementById('novedades');
      const box = document.getElementById('boxAdjuntarFotoNovedad');
      if (!box) return;
      const tieneTexto = nov && nov.value.trim().length > 0;
      const tieneFotos = fotosNovedadActuales && fotosNovedadActuales.length > 0;
      if (tieneTexto || tieneFotos) {
        box.classList.remove('hidden');
      } else {
        box.classList.add('hidden');
      }
    }

    function agregarNovedadRapida(texto) {
      const el = document.getElementById('novedades');
      if (!el) return;
      if (el.value.trim().length > 0) {
        el.value += `, ${texto}`;
      } else {
        el.value = texto;
      }
      evaluarHabilitarFotoNovedad();
    }

    function limpiarNovedades() {
      const nov = document.getElementById('novedades');
      if (nov) nov.value = '';
      if (!fotosNovedadActuales || fotosNovedadActuales.length === 0) {
        const box = document.getElementById('boxAdjuntarFotoNovedad');
        if (box) box.classList.add('hidden');
      }
    }

    function procesarFotosNovedad(input) {
      if (!input.files || input.files.length === 0) return;
      const files = Array.from(input.files);
      let procesadas = 0;
      const nuevasFotos = [];

      mostrarToast(`Procesando ${files.length} imagen(es)...`);

      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
          const img = new Image();
          img.onload = function() {
            // Comprimir mediante canvas (máx 1000px para nitidez y almacenamiento optimizado)
            const maxDim = 1000;
            let w = img.width;
            let h = img.height;
            if (w > h && w > maxDim) {
              h = Math.round((h * maxDim) / w);
              w = maxDim;
            } else if (h > maxDim) {
              w = Math.round((w * maxDim) / h);
              h = maxDim;
            }
            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, w, h);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.80);
            nuevasFotos.push(dataUrl);

            procesadas++;
            if (procesadas === files.length) {
              fotosNovedadActuales = fotosNovedadActuales.concat(nuevasFotos);
              actualizarUIFotosNovedad();
              mostrarToast(`📸 ${nuevasFotos.length} imagen(es) agregada(s) con éxito`);
            }
          };
          img.src = e.target.result;
        };
        reader.readAsDataURL(file);
      });
      input.value = '';
    }

    // Compatibilidad hacia atrás si algún script llama procesarFotoNovedad
    function procesarFotoNovedad(input) {
      procesarFotosNovedad(input);
    }

    function actualizarUIFotosNovedad() {
      const b64 = document.getElementById('foto_novedad_base64');
      if (b64) {
        b64.value = fotosNovedadActuales.length > 0 ? JSON.stringify(fotosNovedadActuales) : '';
      }

      const previewBox = document.getElementById('previewFotoNovedadBox');
      const grid = document.getElementById('gridPreviewFotosNovedad');
      const txtBtn = document.getElementById('txtBtnCamaraNovedad');
      const btnQuitarTodas = document.getElementById('btnQuitarTodasFotos');
      const lblConteo = document.getElementById('lblConteoFotosAdjuntas');

      if (!fotosNovedadActuales || fotosNovedadActuales.length === 0) {
        if (previewBox) previewBox.classList.add('hidden');
        if (grid) grid.innerHTML = '';
        if (txtBtn) txtBtn.textContent = 'Tomar Foto o Subir Imágenes (1 o varias)';
        if (btnQuitarTodas) btnQuitarTodas.classList.add('hidden');
        evaluarHabilitarFotoNovedad();
        return;
      }

      if (previewBox) previewBox.classList.remove('hidden');
      if (btnQuitarTodas) btnQuitarTodas.classList.remove('hidden');
      if (txtBtn) txtBtn.textContent = '+ Agregar más fotos';
      if (lblConteo) lblConteo.textContent = `${fotosNovedadActuales.length} imagen${fotosNovedadActuales.length > 1 ? 'es' : ''} adjunta${fotosNovedadActuales.length > 1 ? 's' : ''}`;

      if (grid) {
        grid.innerHTML = '';
        fotosNovedadActuales.forEach((foto, idx) => {
          const card = document.createElement('div');
          card.className = 'relative group w-14 h-14 sm:w-16 sm:h-16 rounded-xl overflow-hidden border-2 border-blue-400 bg-slate-900 shadow-sm flex-shrink-0 cursor-pointer transition-transform hover:scale-105';
          card.title = `Clic para ver foto ${idx + 1} en grande`;
          card.innerHTML = `
            <img src="${foto}" alt="Miniatura ${idx + 1}" class="w-full h-full object-cover">
            <button type="button" onclick="event.stopPropagation(); eliminarFotoNovedadIndex(${idx});" class="absolute top-1 right-1 w-5 h-5 bg-rose-600 hover:bg-rose-700 text-white rounded-full flex items-center justify-center text-[10px] shadow transition-all" title="Quitar esta foto">
              <i class="fa-solid fa-xmark"></i>
            </button>
            <span class="absolute bottom-0 left-0 right-0 bg-slate-900/80 text-white text-[8px] text-center font-mono font-bold leading-tight py-0.5">
              #${idx + 1}
            </span>
          `;
          card.onclick = () => abrirGaleriaFotosDirecta(fotosNovedadActuales, idx, 'Previsualización de fotos en formulario');
          grid.appendChild(card);
        });
      }

      evaluarHabilitarFotoNovedad();
    }

    function eliminarFotoNovedadIndex(idx) {
      if (idx >= 0 && idx < fotosNovedadActuales.length) {
        fotosNovedadActuales.splice(idx, 1);
        actualizarUIFotosNovedad();
        mostrarToast('Foto quitada de la lista');
      }
    }

    function quitarTodasFotosNovedad() {
      fotosNovedadActuales = [];
      const inp = document.getElementById('foto_novedad_input');
      if (inp) inp.value = '';
      actualizarUIFotosNovedad();
    }

    function quitarFotoNovedad() {
      quitarTodasFotosNovedad();
    }

    // ==========================================
    // VISOR MODAL DE GALERÍA DE FOTOS (BASE DE DATOS & FORMULARIO)
    // ==========================================
    function abrirGaleriaFotosPorId(inspeccionId) {
      const reg = cacheTodasInspecciones.find(x => x.id === inspeccionId);
      if (!reg) {
        mostrarToast('No se encontró la inspección en memoria', true);
        return;
      }
      const fotos = obtenerListaFotos(reg.foto_novedad);
      if (fotos.length === 0) {
        mostrarToast('Esta inspección no tiene fotos registradas', true);
        return;
      }

      const subtitulo = `Vehículo: ${reg.placa || '-'} · Posición ${reg.posicion} · Fecha: ${reg.fecha || '-'} · Cliente: ${reg.cliente || '-'}`;
      const novedadTexto = reg.novedades || 'Sin observaciones textuales';
      const infoLlanta = `Posición ${reg.posicion} · ${reg.marca || ''} ${reg.diseno || ''} (${reg.dimension || ''})`;

      abrirGaleriaFotosModal(fotos, 0, subtitulo, novedadTexto, infoLlanta);
    }

    function abrirGaleriaFotosDirecta(fotos, indexInicial, titulo) {
      if (!fotos || fotos.length === 0) return;
      abrirGaleriaFotosModal(fotos, indexInicial, titulo || 'Evidencia Fotográfica', 'Fotos listas para guardar en la inspección actual', 'Formulario de Patio');
    }

    function abrirGaleriaFotosModal(fotos, indexInicial, subtitulo, novedadTexto, infoLlanta) {
      galeriaFotosActivas = fotos || [];
      galeriaFotoIndexActual = (indexInicial >= 0 && indexInicial < galeriaFotosActivas.length) ? indexInicial : 0;

      const modal = document.getElementById('modalGaleriaFotos');
      const lblSub = document.getElementById('lblSubtituloGaleria');
      const lblNov = document.getElementById('lblTextoNovedadGaleria');
      const badgeLlanta = document.getElementById('badgeDatosLlantaGaleria');

      if (lblSub) lblSub.textContent = subtitulo || 'Evidencias fotográficas';
      if (lblNov) lblNov.textContent = novedadTexto || 'Sin observaciones registradas';
      if (badgeLlanta) badgeLlanta.textContent = infoLlanta || '';

      renderizarEstadoGaleria();

      if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      }
    }

    function cerrarModalGaleriaFotos() {
      const modal = document.getElementById('modalGaleriaFotos');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
      galeriaFotosActivas = [];
      galeriaFotoIndexActual = 0;
    }

    function cambiarFotoGaleriaActiva(idx) {
      if (idx >= 0 && idx < galeriaFotosActivas.length) {
        galeriaFotoIndexActual = idx;
        renderizarEstadoGaleria();
      }
    }

    function navegarFotoGaleria(dir) {
      if (!galeriaFotosActivas || galeriaFotosActivas.length <= 1) return;
      let nuevo = galeriaFotoIndexActual + dir;
      if (nuevo < 0) nuevo = galeriaFotosActivas.length - 1;
      if (nuevo >= galeriaFotosActivas.length) nuevo = 0;
      galeriaFotoIndexActual = nuevo;
      renderizarEstadoGaleria();
    }

    function renderizarEstadoGaleria() {
      if (!galeriaFotosActivas || galeriaFotosActivas.length === 0) return;
      const fotoActual = galeriaFotosActivas[galeriaFotoIndexActual];

      const imgP = document.getElementById('imgGaleriaPrincipal');
      const lblContador = document.getElementById('lblContadorGaleria');
      const btnDesc = document.getElementById('btnDescargarFotoGaleria');
      const contenedorMinis = document.getElementById('contenedorMiniaturasGaleria');
      const lblTotal = document.getElementById('lblTotalMiniaturasGaleria');
      const btnPrev = document.getElementById('btnGaleriaPrev');
      const btnNext = document.getElementById('btnGaleriaNext');

      if (imgP) imgP.src = fotoActual;
      if (lblContador) lblContador.textContent = `Foto ${galeriaFotoIndexActual + 1} de ${galeriaFotosActivas.length}`;
      if (btnDesc) btnDesc.href = fotoActual;
      if (lblTotal) lblTotal.textContent = `${galeriaFotosActivas.length} imagen${galeriaFotosActivas.length > 1 ? 'es' : ''}`;

      // Mostrar u ocultar flechas si solo hay 1 foto
      if (btnPrev && btnNext) {
        if (galeriaFotosActivas.length <= 1) {
          btnPrev.classList.add('hidden');
          btnNext.classList.add('hidden');
        } else {
          btnPrev.classList.remove('hidden');
          btnNext.classList.remove('hidden');
        }
      }

      // Renderizar miniaturas
      if (contenedorMinis) {
        contenedorMinis.innerHTML = '';
        galeriaFotosActivas.forEach((f, i) => {
          const esActiva = (i === galeriaFotoIndexActual);
          const thumb = document.createElement('button');
          thumb.type = 'button';
          thumb.className = `w-14 h-14 rounded-xl overflow-hidden border-2 transition-all flex-shrink-0 cursor-pointer shadow-xs ${
            esActiva ? 'border-blue-600 ring-2 ring-blue-500 scale-105' : 'border-slate-200 hover:border-slate-400 opacity-70 hover:opacity-100'
          }`;
          thumb.title = `Ver foto #${i + 1}`;
          thumb.onclick = () => cambiarFotoGaleriaActiva(i);
          thumb.innerHTML = `<img src="${f}" alt="Thumb ${i + 1}" class="w-full h-full object-cover">`;
          contenedorMinis.appendChild(thumb);
        });
      }
    }

    // Atajos de teclado para el visor
    document.addEventListener('keydown', function(e) {
      const modal = document.getElementById('modalGaleriaFotos');
      if (modal && !modal.classList.contains('hidden')) {
        if (e.key === 'Escape') {
          cerrarModalGaleriaFotos();
        } else if (e.key === 'ArrowLeft') {
          navegarFotoGaleria(-1);
        } else if (e.key === 'ArrowRight') {
          navegarFotoGaleria(1);
        }
      }
    });

    function dispararSubmitInspeccion() {
      const form = document.getElementById('inspectionForm');
      if (form) {
        if (typeof form.requestSubmit === 'function') {
          form.requestSubmit();
        } else {
          document.getElementById('btnGuardar').click();
        }
      }
    }

    function toggleColapsoCard(bodyId, iconId, resumenId, txtResumenId, tipo) {
      const body = document.getElementById(bodyId);
      const icon = document.getElementById(iconId);
      const resumen = document.getElementById(resumenId);
      const txt = document.getElementById(txtResumenId);
      if (!body) return;

      const estaOculto = body.classList.contains('hidden');
      if (estaOculto) {
        body.classList.remove('hidden');
        if (resumen) resumen.classList.add('hidden');
        if (icon) icon.className = 'fa-solid fa-chevron-up text-xs';
      } else {
        body.classList.add('hidden');
        if (resumen && txt) {
          if (tipo === 'cliente') {
            const cli = document.getElementById('cliente').value.trim() || 'Sin definir';
            const sub = document.getElementById('subcliente').value.trim() || 'Principal';
            const op = document.getElementById('tipo_operacion').value || 'Carga Seca';
            txt.textContent = `${cli} · ${sub} (${op})`;
          } else if (tipo === 'vehiculo') {
            const pl = document.getElementById('placa').value.trim() || 'Sin placa';
            const tip = document.getElementById('tipologia').value || 'Tipología';
            const km = document.getElementById('kilometraje').value.trim();
            txt.textContent = `${pl} · ${tip}${km ? ` · ${km} Km` : ''}`;
          } else if (tipo === 'llanta') {
            const m = document.getElementById('marca').value.trim() || 'Marca';
            const d = document.getElementById('diseno').value.trim() || 'Diseño';
            const dim = document.getElementById('dimension').value.trim() || '295/80R22.5';
            const v = document.getElementById('vida').value || 'Original';
            txt.textContent = `${m} ${d} · ${dim} · ${v}`;
          }
          resumen.classList.remove('hidden');
        }
        if (icon) icon.className = 'fa-solid fa-chevron-down text-xs';
      }
    }

    function actualizarResumenVehiculoMobile() {
      const txt = document.getElementById('txtResumenVehiculo');
      if (!txt) return;
      const pl = document.getElementById('placa').value.trim() || 'Sin placa';
      const tip = document.getElementById('tipologia').value || 'Tipología';
      const km = document.getElementById('kilometraje').value.trim();
      txt.textContent = `${pl} · ${tip}${km ? ` · ${km} Km` : ''}`;
    }

    /**
     * Selecciona una posición de neumático, actualiza el formulario y sincroniza el chasis.
     */
    function seleccionarPosicion(p) {
      document.getElementById('posicion').value = p;
      const lblPos = document.getElementById('lblPosActualForm');
      if (lblPos) lblPos.textContent = p;
      const lblPosEsp = document.getElementById('lblPosActualEspecificaciones');
      if (lblPosEsp) lblPosEsp.textContent = p;

      // Re-renderizar el chasis para actualizar el halo azul y el círculo numérico
      if (esquemaTipologiaCache) {
        renderizarChasisEjes(esquemaTipologiaCache, listaPosicionesActual);
      }

      // Sincronizar botones accesibles
      document.querySelectorAll('.pos-btn').forEach(b => b.classList.remove('active'));
      const b = document.getElementById(`btn_pos_${p}`);
      if (b) b.classList.add('active');

      actualizarBarraPosicionMobile(p);

      verificarInspeccionAnterior();
    }

    /**
     * Marca o desmarca la ausencia de llanta de repuesto en el vehículo.
     */
    function marcarSinRepuesto() {
      ruedaSinRepuestoMarcada = !ruedaSinRepuestoMarcada;
      const btn = document.getElementById('btnSinRepuesto');
      const txt = document.getElementById('txtBtnSinRepuesto');
      
      let posRepuesto = null;
      if (esquemaTipologiaCache) {
        const ejeRep = esquemaTipologiaCache.find(e => e.eje === 99 || (e.tipo || '').toLowerCase() === 'repuesto');
        if (ejeRep && ejeRep.posiciones && ejeRep.posiciones.length > 0) {
          posRepuesto = ejeRep.posiciones[0].pos;
        }
      }

      if (ruedaSinRepuestoMarcada) {
        if (txt) txt.textContent = 'Desmarcar: Vehículo SÍ tiene llanta de repuesto';
        if (btn) {
          btn.classList.remove('bg-slate-100', 'text-slate-600');
          btn.classList.add('bg-amber-100', 'text-amber-800', 'border-amber-300');
        }
        if (posRepuesto) {
          posicionesInspeccionadasPlaca.delete(posRepuesto);
          const posActual = parseInt(document.getElementById('posicion').value) || 1;
          if (posActual === posRepuesto) {
            seleccionarPosicion(listaPosicionesActual[0] || 1);
          }
        }
        mostrarToast('Marcado: El vehículo NO tiene llanta de repuesto.');
      } else {
        if (txt) txt.textContent = 'Marcar: Vehículo sin llanta de repuesto';
        if (btn) {
          btn.classList.add('bg-slate-100', 'text-slate-600');
          btn.classList.remove('bg-amber-100', 'text-amber-800', 'border-amber-300');
        }
        mostrarToast('Desmarcado: Vehículo con llanta de repuesto habilitada.');
      }

      if (esquemaTipologiaCache) {
        renderizarChasisEjes(esquemaTipologiaCache, listaPosicionesActual);
        renderizarBotonesPosicion(listaPosicionesActual, esquemaTipologiaCache);
        renderizarCarruselLlantasMobile();
      }
    }

    async function verificarInspeccionAnterior() {
      const placa = document.getElementById('placa').value.trim().toUpperCase();
      const pos = parseInt(document.getElementById('posicion').value) || 1;
      if (!placa) return;

      cargarPosicionesInspeccionadasPlaca(placa);

      try {
        const res = await fetch(`/api/inspeccion-anterior?placa=${encodeURIComponent(placa)}&posicion=${pos}`);
        if (res.ok) {
          const d = await res.json();
          if (d.encontrado && d.datos) {
            datosInspeccionAnterior = d.datos;
            document.getElementById('badgeHistorialPrevia').classList.remove('hidden');
            // Precargar datos fijos
            if (d.datos.marca && !document.getElementById('marca').value) document.getElementById('marca').value = d.datos.marca;
            if (d.datos.diseno && !document.getElementById('diseno').value) document.getElementById('diseno').value = d.datos.diseno;
            if (d.datos.dimension && !document.getElementById('dimension').value) document.getElementById('dimension').value = d.datos.dimension;
            if (d.datos.prof_inicial && !document.getElementById('prof_inicial').value) document.getElementById('prof_inicial').value = d.datos.prof_inicial;
            if (d.datos.numero_interno && !document.getElementById('numero_interno').value) document.getElementById('numero_interno').value = d.datos.numero_interno;
          } else {
            document.getElementById('badgeHistorialPrevia').classList.add('hidden');
            datosInspeccionAnterior = null;
          }
        }
      } catch (e) {}
    }

    async function cargarPosicionesInspeccionadasPlaca(placa) {
      try {
        const res = await fetch(`/api/posiciones-inspeccionadas?placa=${encodeURIComponent(placa)}`);
        if (res.ok) {
          const d = await res.json();
          posicionesInspeccionadasPlaca = new Set(d.posiciones || []);
          posicionesConNovedadPlaca = new Map();
          if (d.novedades) {
            for (const [k, v] of Object.entries(d.novedades)) {
              posicionesConNovedadPlaca.set(parseInt(k), v);
            }
          } else if (Array.isArray(d.posiciones_con_novedad)) {
            d.posiciones_con_novedad.forEach(p => posicionesConNovedadPlaca.set(p, 'Novedad registrada'));
          }

          if (esquemaTipologiaCache) renderizarChasisEjes(esquemaTipologiaCache, listaPosicionesActual);
          renderizarBotonesPosicion(listaPosicionesActual, esquemaTipologiaCache);
          actualizarBarraPosicionMobile(parseInt(document.getElementById('posicion').value) || 1);
        }
      } catch (e) {}
    }

    function validarVida() {
      const vida = document.getElementById('vida').value;
      const boxBanda = document.getElementById('box_banda');
      if (vida === 'Reencauche') {
        boxBanda.classList.remove('hidden');
        poblarDatalist('dl_bandas', '/api/valores-campo?campo=banda_reen');
      } else {
        boxBanda.classList.add('hidden');
      }
    }

    async function alCambiarMarcaMobile() {
      const m = document.getElementById('marca').value.trim();
      if (m) poblarDatalist('dl_disenos', `/api/valores-campo?campo=diseno&marca=${encodeURIComponent(m)}`);
    }

    async function autoCompletarProfInicial() {
      const m = document.getElementById('marca').value.trim();
      const d = document.getElementById('diseno').value.trim();
      const dim = document.getElementById('dimension').value.trim();
      const vida = document.getElementById('vida').value;
      if (!m || !d) return;

      const res = await fetch(`/api/profundidad-inicial?marca=${encodeURIComponent(m)}&diseno=${encodeURIComponent(d)}&dimension=${encodeURIComponent(dim)}&vida=${encodeURIComponent(vida)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.prof_inicial > 0) {
          document.getElementById('prof_inicial').value = data.prof_inicial;
        }
      }
    }

    async function buscarLlantaCatalogoEnVivo() {
      const q = `${document.getElementById('marca').value.trim()} ${document.getElementById('diseno').value.trim()}`.trim();
      const box = document.getElementById('boxSugerenciasCatalogo');
      const list = document.getElementById('listaSugerenciasCatalogo');

      if (q.length < 2) {
        box.classList.add('hidden');
        return;
      }

      try {
        const res = await fetch(`/api/buscar-modelos?query=${encodeURIComponent(q)}`);
        if (res.ok) {
          const matches = await res.json();
          if (matches.length > 0) {
            box.classList.remove('hidden');
            list.innerHTML = matches.slice(0, 3).map(m => `
              <div onclick='seleccionarLlantaCatalogo(${JSON.stringify(m)})' class="p-1.5 bg-white border border-blue-200 rounded-lg cursor-pointer hover:bg-blue-100 flex items-center justify-between">
                <span class="font-bold text-slate-900">${m.marca} ${m.diseno} (${m.dimension})</span>
                <span class="font-black text-blue-700 font-mono">${m.prof_inicial} mm</span>
              </div>
            `).join('');
          } else {
            box.classList.add('hidden');
          }
        }
      } catch (e) {}
    }

    function seleccionarLlantaCatalogo(m) {
      document.getElementById('marca').value = m.marca;
      document.getElementById('diseno').value = m.diseno;
      document.getElementById('dimension').value = m.dimension;
      document.getElementById('prof_inicial').value = m.prof_inicial;
      if (m.tipo_llanta === 'Reencauche') {
        document.getElementById('vida').value = 'Reencauche';
        validarVida();
      }
      document.getElementById('boxSugerenciasCatalogo').classList.add('hidden');
      mostrarToast(`Modelo seleccionado: ${m.marca} ${m.diseno}`);
    }

    function limpiarMediciones() {
      document.getElementById('prof_ext').value = '';
      document.getElementById('prof_cent').value = '';
      document.getElementById('prof_int').value = '';
      document.getElementById('novedades').value = '';
      document.getElementById('alertaRetiroInmediato').classList.add('hidden');
      quitarFotoNovedad();
      limpiarTodosErroresFormulario();
    }

    function limpiarFormulario(total = false) {
      limpiarMediciones();
      if (total) {
        document.getElementById('placa').value = '';
        document.getElementById('kilometraje').value = '';
        document.getElementById('numero_interno').value = '';
        posicionesInspeccionadasPlaca.clear();
        posicionesConNovedadPlaca.clear();
      }
    }

    // Modal de Operación & Tipología
    function abrirModalOperacion() { document.getElementById('modalOperacion').classList.remove('hidden'); document.getElementById('modalOperacion').classList.add('flex'); }
    function cerrarModalOperacion() { document.getElementById('modalOperacion').classList.add('hidden'); document.getElementById('modalOperacion').classList.remove('flex'); }
    async function guardarNuevaOperacion() {
      const nom = document.getElementById('nueva_op_nombre').value.trim();
      if (!nom) return;
      const res = await fetch('/api/operaciones', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nombre: nom})
      });
      if (res.ok) {
        cerrarModalOperacion();
        cargarCatalogos(nom, null);
        mostrarToast(`Operación "${nom}" guardada.`);
      }
    }

    function abrirModalTipologia() { document.getElementById('modalTipologia').classList.remove('hidden'); document.getElementById('modalTipologia').classList.add('flex'); }
    function cerrarModalTipologia() { document.getElementById('modalTipologia').classList.add('hidden'); document.getElementById('modalTipologia').classList.remove('flex'); }
    function alCambiarPresetEjesMobile() {
      const v = document.getElementById('sel_preset_ejes_mob').value;
      const cant = v === '4x2' ? 6 : v === 'liviano' ? 4 : (v === '8x4' || v === 'trailer3') ? 12 : v === 'trailer2' ? 8 : 10;
      document.getElementById('nueva_tip_cant').value = cant;
    }
    async function guardarNuevaTipologia() {
      const nom = document.getElementById('nueva_tip_nombre').value.trim();
      const cant = parseInt(document.getElementById('nueva_tip_cant').value) || 10;
      const desc = document.getElementById('nueva_tip_desc').value.trim();
      if (!nom) return;
      const res = await fetch('/api/tipologias', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nombre: nom, descripcion: desc, cant_llantas: cant})
      });
      if (res.ok) {
        cerrarModalTipologia();
        cargarCatalogos(null, nom);
        mostrarToast(`Tipología "${nom}" guardada.`);
      }
    }

    // Control de Jornada de Cliente
    function registrarInicioJornadaCliente() {
      const cli = document.getElementById('cliente').value.trim();
      const sub = document.getElementById('subcliente').value.trim();
      if (!cli) return;
      const key = `jornada_${cli}_${sub}`;
      if (!localStorage.getItem(key)) {
        localStorage.setItem(key, Date.now().toString());
      }
    }
    function confirmarContinuarMismoCliente() {
      document.getElementById('bannerRecordatorioCliente').classList.add('hidden');
    }
    function cambiarClienteRecordatorio() {
      document.getElementById('bannerRecordatorioCliente').classList.add('hidden');
      document.getElementById('cliente').value = '';
      document.getElementById('subcliente').value = '';
      document.getElementById('cliente').focus();
    }

    // Informes PDF & Modal Ejecutivo
    async function abrirModalInformePdf(placa) {
      document.getElementById('lblPlacaPdfModal').textContent = placa;
      const m = document.getElementById('modalInformePdf');
      m.classList.remove('hidden');
      m.classList.add('flex');

      // 1. Datos del encabezado
      const cli = document.getElementById('cliente').value.trim() || 'Flota';
      const tip = document.getElementById('tipologia').value || 'Tipología';
      const elTip = document.getElementById('lblTipologiaModal');
      const elCli = document.getElementById('lblClienteModal');
      if (elTip) elTip.textContent = tip;
      if (elCli) elCli.textContent = cli;

      // 2. Renderizar / Clonar Diagrama de Chasis en el Modal
      const contenedorChasis = document.getElementById('contenedorChasisEjes');
      const modalChasisBox = document.getElementById('modalChasisContainer');
      if (modalChasisBox && contenedorChasis) {
        modalChasisBox.innerHTML = '';
        const clone = contenedorChasis.cloneNode(true);
        clone.id = 'modal_clone_chasis';
        // Deshabilitar clicks interactivos en el clone para vista de solo lectura
        clone.querySelectorAll('.tire-interactive-node').forEach(node => {
          node.style.cursor = 'default';
          node.removeAttribute('onclick');
        });
        modalChasisBox.appendChild(clone);
      }

      // 3. Consultar datos de inspección del vehículo para KPIs y Planes
      try {
        const res = await fetch('/api/inspecciones?usuario=');
        if (res.ok) {
          const todas = await res.json();
          const filas = todas.filter(r => (r['Vehículo/Placa'] || r['placa'] || '').toUpperCase() === placa.toUpperCase());
          
          const totalAuditadas = filas.length;
          const limite = parseFloat(document.getElementById('lblMmRetiroCliente')?.textContent) || 3.0;
          let retiroCount = 0;
          let novedadCount = 0;
          let sumaPsi = 0;
          let planesDetectados = [];

          filas.forEach(f => {
            const pExt = parseFloat(f['Prof. Ext (mm)'] || f['prof_ext'] || 0);
            const pCen = parseFloat(f['Prof. Cent (mm)'] || f['prof_cent'] || 0);
            const pInt = parseFloat(f['Prof. Int (mm)'] || f['prof_int'] || 0);
            const val = [pExt, pCen, pInt].filter(v => v > 0);
            const pMin = val.length ? Math.min(...val) : 0;
            const psiVal = parseFloat(f['PSI'] || f['psi'] || 100);
            const nov = (f['Novedades / Daños'] || f['novedades'] || '').trim();
            const posNum = f['Posición'] || f['posicion'];

            sumaPsi += psiVal;
            if (pMin > 0 && pMin <= limite) {
              retiroCount++;
              planesDetectados.push(`⚠️ <b>Posición ${posNum}:</b> Profundidad (${pMin.toFixed(1)} mm) en límite de retiro (<= ${limite.toFixed(1)} mm). Acción: Retiro / Reencauche.`);
            }
            if (nov) {
              novedadCount++;
              planesDetectados.push(`🔧 <b>Posición ${posNum}:</b> Novedad reportada: "${nov}".`);
            }
          });

          const promPsi = totalAuditadas > 0 ? (sumaPsi / totalAuditadas).toFixed(0) : 100;
          
          const elTotal = document.getElementById('lblModalTotalLlantas');
          const elRetiro = document.getElementById('lblModalLlantasRetiro');
          const elNov = document.getElementById('lblModalLlantasNovedad');
          const elPsi = document.getElementById('lblModalPromedioPsi');

          if (elTotal) elTotal.textContent = `${totalAuditadas} / ${listaPosicionesActual.length || totalAuditadas}`;
          if (elRetiro) elRetiro.textContent = retiroCount;
          if (elNov) elNov.textContent = novedadCount;
          if (elPsi) elPsi.textContent = `${promPsi} PSI`;

          const listaBox = document.getElementById('modalPlanesAccionList');
          const saludBadge = document.getElementById('lblEstadoSaludVehiculo');

          if (listaBox) {
            if (planesDetectados.length === 0) {
              listaBox.innerHTML = `
                <div class="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center space-x-2">
                  <i class="fa-solid fa-circle-check text-emerald-600 text-base"></i>
                  <span><b>Vehículo en Estado Seguro y Óptimo:</b> Todas las llantas están sobre el límite de retiro (${limite.toFixed(1)} mm) y sin novedades mecánicas registradas.</span>
                </div>
              `;
              if (saludBadge) {
                saludBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200';
                saludBadge.textContent = 'Estado Óptimo';
              }
            } else {
              listaBox.innerHTML = planesDetectados.map(p => `
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 leading-snug">
                  ${p}
                </div>
              `).join('');
              if (saludBadge) {
                saludBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200';
                saludBadge.textContent = 'Requiere Atención';
              }
            }
          }
        }
      } catch(e) {}
    }
    function cerrarModalInformePdf() {
      const m = document.getElementById('modalInformePdf');
      m.classList.add('hidden');
      m.classList.remove('flex');
    }
    function descargarPdfVehiculoActual() {
      let p = (document.getElementById('lblPlacaPdfModal')?.textContent || '').trim();
      if (!p || p === '-') {
        p = (document.getElementById('placa')?.value || '').trim();
      }
      if (!p) {
        mostrarToast('Por favor ingrese o seleccione una placa primero.', true);
        return;
      }
      window.open(`/api/informe-pdf/${encodeURIComponent(p)}`, '_blank');
    }
    function descargarConsolidadoFlota() {
      const cli = document.getElementById('cliente').value.trim();
      const sub = document.getElementById('subcliente').value.trim();
      const url = `/api/informe-pdf-consolidado?cliente=${encodeURIComponent(cli)}&subcliente=${encodeURIComponent(sub)}`;
      window.open(url, '_blank');
    }
    function compartirWhatsAppPlan() {
      const p = document.getElementById('lblPlacaPdfModal').textContent;
      const ip = window.location.host;
      const url = `http://${ip}/api/informe-pdf/${encodeURIComponent(p)}`;
      const msg = encodeURIComponent(`Hola! Te comparto el Plan de Mantenimiento e Inspección de Llantas para el vehículo ${p}:\n${url}`);
      window.open(`https://api.whatsapp.com/send?text=${msg}`, '_blank');
    }

    // Cola Offline
    function obtenerColaOffline() {
      try { return JSON.parse(localStorage.getItem('tirecheck_offline_queue') || '[]'); } catch(e) { return []; }
    }
    function guardarColaOffline(cola) {
      localStorage.setItem('tirecheck_offline_queue', JSON.stringify(cola));
      actualizarBadgeRed();
    }
    function encolarInspeccionOffline(payload) {
      const cola = obtenerColaOffline();
      cola.push({ payload, timestamp: Date.now() });
      guardarColaOffline(cola);
    }
    function actualizarBadgeRed() {
      const online = navigator.onLine;
      const bRed = document.getElementById('badgeEstadoRed');
      const bSync = document.getElementById('btnSincronizarOffline');
      const lblCount = document.getElementById('lblPendientesCount');
      const cola = obtenerColaOffline();

      if (bRed) {
        bRed.className = `inline-flex items-center px-2 py-1 rounded-full text-[11px] font-bold ${
          online ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
        }`;
        bRed.innerHTML = `<span class="w-1.5 h-1.5 rounded-full ${online ? 'bg-emerald-400' : 'bg-rose-400'} mr-1.5 animate-pulse"></span><span>${online ? 'Online' : 'Offline'}</span>`;
      }

      if (cola.length > 0) {
        bSync.classList.remove('hidden');
        lblCount.textContent = cola.length;
      } else {
        bSync.classList.add('hidden');
      }
    }
    async function sincronizarColaOffline() {
      const cola = obtenerColaOffline();
      if (cola.length === 0 || !navigator.onLine || sincronizandoCola) return;

      sincronizandoCola = true;
      mostrarToast(`☁️ Sincronizando ${cola.length} inspección(es) guardadas offline...`);
      const restantes = [];
      let exitosos = 0;

      for (const item of cola) {
        try {
          const res = await fetch('/api/inspecciones', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(item.payload)
          });
          if (res.ok) exitosos++;
          else {
            const err = await res.json().catch(() => ({}));
            if (res.status === 400 && (err.detail || '').includes('ya fue inspeccionado')) exitosos++;
            else restantes.push(item);
          }
        } catch(e) {
          restantes.push(item);
        }
      }

      guardarColaOffline(restantes);
      sincronizandoCola = false;
      if (exitosos > 0) mostrarToast(`🎉 ¡${exitosos} inspección(es) sincronizadas con éxito!`);
      if (restantes.length > 0) mostrarToast(`Quedaron ${restantes.length} pendientes`, true);
    }

    // Eventos de red
    window.addEventListener('online', () => { actualizarBadgeRed(); sincronizarColaOffline(); });
    window.addEventListener('offline', () => { actualizarBadgeRed(); mostrarToast('Modo Offline activo', true); });

    // Envío del Formulario de Inspección de Patio
    document.getElementById('inspectionForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      limpiarTodosErroresFormulario();

      let hayErrores = false;
      const placa = document.getElementById('placa').value.trim().toUpperCase();
      if (!placa) {
        marcarErrorCampo('placa', 'err_placa');
        const elPlaca = document.getElementById('placa');
        if (elPlaca) {
          elPlaca.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(() => elPlaca.focus(), 250);
        }
        hayErrores = true;
      }

      const p_ext_val = document.getElementById('prof_ext').value.trim();
      const p_cent_val = document.getElementById('prof_cent').value.trim();
      const p_int_val = document.getElementById('prof_int').value.trim();
      const psi_val = document.getElementById('psi').value.trim();

      if (!p_ext_val && !p_cent_val && !p_int_val) {
        marcarErrorCampo('prof_ext', 'err_profundidades');
        marcarErrorCampo('prof_cent', 'err_profundidades');
        marcarErrorCampo('prof_int', 'err_profundidades');
        if (!hayErrores) {
          const elExt = document.getElementById('prof_ext');
          if (elExt) {
            elExt.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(() => elExt.focus(), 250);
          }
        }
        hayErrores = true;
      }

      if (!psi_val || parseFloat(psi_val) <= 0) {
        marcarErrorCampo('psi', 'err_psi');
        if (!hayErrores) {
          const elPsi = document.getElementById('psi');
          if (elPsi) {
            elPsi.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(() => elPsi.focus(), 250);
          }
        }
        hayErrores = true;
      }

      if (hayErrores) {
        mostrarToast('⚠️ Por favor completa los campos obligatorios resaltados en rojo', true);
        return;
      }

      const pos = parseInt(document.getElementById('posicion').value) || 1;
      const p_ext = parseFloat(p_ext_val) || 0;
      const p_cent = parseFloat(p_cent_val) || 0;
      const p_int = parseFloat(p_int_val) || 0;
      const dimension = document.getElementById('dimension').value.trim();
      const prof_inicial_num = parseFloat(document.getElementById('prof_inicial').value) || 0;

      if (dimension.includes('22.5') && (p_ext > 27 || p_cent > 27 || p_int > 27)) {
        mostrarToast('⛔ CANDADO: Para dimensión R22.5, ninguna profundidad puede superar los 27.0 mm', true);
        return;
      }
      if (prof_inicial_num > 0 && (p_ext > prof_inicial_num || p_cent > prof_inicial_num || p_int > prof_inicial_num)) {
        mostrarToast(`⛔ CANDADO: La profundidad no puede ser mayor a la inicial (${prof_inicial_num} mm)`, true);
        return;
      }

      function fechaLocalISO(d = new Date()) {
        const p = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
      }

      const payload = {
        fecha: document.getElementById('fecha').value || fechaLocalISO(),
        cliente: document.getElementById('cliente').value,
        subcliente: document.getElementById('subcliente').value,
        tipo_operacion: document.getElementById('tipo_operacion').value,
        placa: placa,
        posicion: pos,
        kilometraje: parseFloat(document.getElementById('kilometraje').value) || 0,
        tipologia: document.getElementById('tipologia').value,
        marca: document.getElementById('marca').value,
        diseno: document.getElementById('diseno').value,
        dimension: dimension,
        vida: document.getElementById('vida').value,
        banda_reen: document.getElementById('banda_reen').value,
        prof_ext: p_ext,
        prof_cent: p_cent,
        prof_int: p_int,
        psi: parseFloat(psi_val) || 100,
        novedades: document.getElementById('novedades').value,
        foto_novedad: (document.getElementById('foto_novedad_base64') || {}).value || '',
        precio: parseFloat(document.getElementById('precio').value) || 0,
        prof_inicial: prof_inicial_num,
        km_montaje: parseFloat(document.getElementById('km_montaje').value) || 0,
        numero_interno: document.getElementById('numero_interno').value.trim().toUpperCase(),
        usuario_registro: usuarioActual ? usuarioActual.username : ''
      };

      registrarInicioJornadaCliente();
      const btn = document.getElementById('btnGuardar');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Guardando...';
      }

      if (!navigator.onLine) {
        encolarInspeccionOffline(payload);
        posicionesInspeccionadasPlaca.add(pos);
        if (payload.novedades && payload.novedades.trim().length > 0) {
          posicionesConNovedadPlaca.set(pos, payload.novedades.trim());
        } else {
          posicionesConNovedadPlaca.delete(pos);
        }
        actualizarBarraPosicionMobile(pos);
        mostrarToast(`💾 Guardado en MODO OFFLINE (Posición ${payload.posicion} de ${placa}).`);
        avanzarSiguientePosicion(pos);
        limpiarMediciones();
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-circle-check text-base"></i><span>Guardar & Siguiente Llanta</span>';
        }
        return;
      }

      try {
        const res = await fetch('/api/inspecciones', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
          posicionesInspeccionadasPlaca.add(pos);
          if (payload.novedades && payload.novedades.trim().length > 0) {
            posicionesConNovedadPlaca.set(pos, payload.novedades.trim());
          } else {
            posicionesConNovedadPlaca.delete(pos);
          }
          actualizarBarraPosicionMobile(pos);
          mostrarToast(`✅ Guardada llanta Posición ${payload.posicion} de ${placa}`);
          const pendientes = listaPosicionesActual.filter(p => !posicionesInspeccionadasPlaca.has(p));
          if (pendientes.length === 0) {
            mostrarToast(`🎉 ¡Vehículo ${placa} COMPLETADO!`);
            setTimeout(() => abrirModalInformePdf(placa), 600);
          }
          avanzarSiguientePosicion(pos);
          limpiarMediciones();
        } else {
          mostrarToast(result.detail || result.message || 'Error al guardar', true);
        }
      } catch (err) {
        encolarInspeccionOffline(payload);
        posicionesInspeccionadasPlaca.add(pos);
        if (payload.novedades && payload.novedades.trim().length > 0) {
          posicionesConNovedadPlaca.set(pos, payload.novedades.trim());
        } else {
          posicionesConNovedadPlaca.delete(pos);
        }
        actualizarBarraPosicionMobile(pos);
        mostrarToast(`⚠️ Sin señal: guardado en MODO OFFLINE.`);
        avanzarSiguientePosicion(pos);
        limpiarMediciones();
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-circle-check text-base"></i><span>Guardar & Siguiente Llanta</span>';
        }
      }
    });

    function avanzarSiguientePosicion(posActual) {
      const pendientes = listaPosicionesActual.filter(p => !posicionesInspeccionadasPlaca.has(p));
      const idx = listaPosicionesActual.indexOf(posActual);
      if (idx !== -1 && idx + 1 < listaPosicionesActual.length) {
        seleccionarPosicion(listaPosicionesActual[idx + 1]);
      } else if (pendientes.length > 0) {
        seleccionarPosicion(pendientes[0]);
      }
      document.getElementById('numero_interno').value = '';
    }

    // Inicialización al cargar DOM
    window.addEventListener('DOMContentLoaded', () => {
      document.getElementById('fecha').value = fechaLocalISO();
      actualizarBadgeRed();
      const logueado = verificarSesionUsuario();
      if (logueado) {
        cargarCatalogos();
        validarVida();
        if (navigator.onLine) sincronizarColaOffline();
      }
    });
  