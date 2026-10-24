
    // Prevención de XSS: Sanitizador de cadenas HTML
    function escapeHtml(val) {
      if (val === null || val === undefined) return '';
      return String(val)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    // ==========================================
    // INTERCEPTOR GLOBAL DE FETCH (AUTENTICACIÓN & 401)
    // ==========================================
    const _originalFetch = window.fetch;
    window.fetch = async function(resource, init = {}) {
      init = init || {};
      init.headers = init.headers || {};

      const token = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      const urlStr = typeof resource === 'string' ? resource : (resource && resource.url ? resource.url : '');

      if (token && urlStr.includes('/api/')) {
        if (init.headers instanceof Headers) {
          if (!init.headers.has('Authorization')) {
            init.headers.set('Authorization', `Bearer ${token}`);
          }
        } else if (Array.isArray(init.headers)) {
          if (!init.headers.some(([k]) => k.toLowerCase() === 'authorization')) {
            init.headers.push(['Authorization', `Bearer ${token}`]);
          }
        } else {
          if (!init.headers['Authorization']) {
            init.headers['Authorization'] = `Bearer ${token}`;
          }
        }
      }

      if (!init.credentials) {
        init.credentials = 'same-origin';
      }

      const response = await _originalFetch(resource, init);

      if (response.status === 401 && urlStr.includes('/api/') && !urlStr.includes('/api/login')) {
        localStorage.removeItem('tireanalyze_token');
        localStorage.removeItem('tirecheck_token');
        localStorage.removeItem('tireanalyze_usuario_sesion');
        localStorage.removeItem('tirecheck_usuario_sesion');
        usuarioActual = null;
        mostrarToast('⚠️ Sesión expirada o no autorizada. Por favor inicie sesión.', true);
        const modalLogin = document.getElementById('modalLogin');
        if (modalLogin) {
          modalLogin.classList.remove('hidden');
        }
      }

      return response;
    };

    // Variables globales de estado
    let idInspeccionActiva = 1;
    function fechaLocalISO(d = new Date()) {
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    }
    let listaPosicionesActual = [1, 3, 4, 7, 8, 2, 6, 5, 10, 9];
    let posicionesInspeccionadasPlaca = new Set();
    let posicionesConNovedadPlaca = new Map();
    let fotosNovedadActuales = [];
    let galeriaFotosActivas = [];
    let galeriaFotoIndexActual = 0;
    let ruedaSinRepuestoMarcada = false;
    let dimensionPredeterminadaVehiculo = '';
    let kilometrajeInspeccionActual = null;
    function alCambiarKilometrajeInput() {
      const v = parseFloat(document.getElementById('kilometraje')?.value) || 0;
      if (v > 0) {
        kilometrajeInspeccionActual = v;
        actualizarResumenVehiculoMobile();
      }
    }
    let usuarioActual = null;
    function esUsuarioAdmin() {
      if (!usuarioActual) return false;
      const rol = String(usuarioActual.rol || '').trim().toLowerCase();
      const user = String(usuarioActual.username || '').trim().toLowerCase();
      return rol === 'admin' || rol === 'administrador' || user === 'admin';
    }
    function esUsuarioJefatura() {
      if (!usuarioActual) return false;
      const rol = String(usuarioActual.rol || '').trim().toLowerCase();
      return rol === 'jefatura' || rol === 'jefe' || rol === 'jefe_llantas';
    }
    function esUsuarioGerencia() {
      if (!usuarioActual) return false;
      const rol = String(usuarioActual.rol || '').trim().toLowerCase();
      return rol === 'gerencia' || rol === 'gerente';
    }
    function esAdminOJefatura() {
      return esUsuarioAdmin() || esUsuarioJefatura();
    }
    let esquemaTipologiaCache = null;
    let sincronizandoCola = false;
    datosInspeccionAnterior = null;
    let cacheTodasInspecciones = [];
    let cacheDiagnostico = [];
    let cacheMatrizSemaforos = null;
    let cacheKpis = [];

    // ==========================================
    // NAVEGACIÓN ENTRE PESTAÑAS (SPA)
    // ==========================================
    function navegarTab(tabId) {
      if (!usuarioActual) {
        document.getElementById('modalLogin').classList.remove('hidden');
        return;
      }

      if (tabId === 'vista-composicion' || tabId === 'vista_composicion') {
        tabId = 'composicion';
      }

      // Regla: Inspectores no pueden ver ni ingresar a Base de Datos (solo admin, jefatura y gerencia)
      const puedeVerBD = esUsuarioAdmin() || esUsuarioJefatura() || esUsuarioGerencia();
      if (tabId === 'basedatos' && !puedeVerBD) {
        tabId = 'patio';
      }

      // Validar si el usuario tiene asignada la vista solicitada
      if (!esUsuarioAdmin()) {
        let rawV = usuarioActual.vistas_permitidas;
        let vistasPermitidas = [];
        if (Array.isArray(rawV)) {
          vistasPermitidas = rawV.map(v => String(v).trim().toLowerCase()).filter(Boolean);
        } else if (typeof rawV === 'string' && rawV.trim()) {
          vistasPermitidas = rawV.split(',').map(v => v.trim().toLowerCase()).filter(Boolean);
        } else {
          vistasPermitidas = esUsuarioJefatura() ? ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'] : (esUsuarioGerencia() ? ['basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas'] : ['patio', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos']);
        }
        if (!vistasPermitidas.includes(tabId)) {
          mostrarToast('⛔ Módulo no autorizado para su perfil de usuario', true);
          tabId = vistasPermitidas.includes('patio') ? 'patio' : (vistasPermitidas[0] || 'patio');
        }
      }

      const tabs = ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'];
      tabs.forEach(t => {
        const elVista = document.getElementById(`vista-${t}`) || document.getElementById(`vista_${t}`);
        const elBtn = document.getElementById(`nav-btn-${t}`);
        if (elVista) elVista.classList.add('hidden');
        if (elBtn) {
          elBtn.classList.remove('active', 'tab-active', 'font-semibold');
          elBtn.classList.add('text-slate-300', 'font-medium');
          elBtn.removeAttribute('aria-current');
        }
      });

      const vistaActiva = document.getElementById(`vista-${tabId}`) || document.getElementById(`vista_${tabId}`);
      const btnActivo = document.getElementById(`nav-btn-${tabId}`);
      if (vistaActiva) vistaActiva.classList.remove('hidden');
      if (btnActivo) {
        btnActivo.classList.add('active', 'tab-active', 'font-semibold');
        btnActivo.classList.remove('text-slate-300', 'font-medium');
        btnActivo.setAttribute('aria-current', 'page');
        try {
          btnActivo.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        } catch (e) {}
      }

      const stickyBar = document.getElementById('stickyBottomActionBarMobile');
      if (stickyBar) {
        if (tabId === 'patio') stickyBar.classList.remove('hidden');
        else stickyBar.classList.add('hidden');
      }

      // Carga perezosa de datos según la pestaña activa
      if (tabId === 'patio') {
        configurarClientesUsuarioEnInspeccion();
      }
      else if (tabId === 'basedatos') {
        cargarBaseInspecciones();
      }
      else if (tabId === 'diagnostico') cargarDiagnostico();
      else if (tabId === 'kpis') {
        cargarSuite20Kpis();
        cargarKpis();
      }
      else if (tabId === 'composicion') {
        if (typeof cargarComposicionFlotaWeb === 'function') {
          if (!cacheComposicionLlantas || cacheComposicionLlantas.length === 0) {
            cargarComposicionFlotaWeb();
          } else {
            renderizarComposicionFlotaWeb();
          }
        }
      }
      else if (tabId === 'bodegas') {
        if (typeof cargarModuloBodegasMRP === 'function') {
          cargarModuloBodegasMRP();
        }
      }
      else if (tabId === 'catalogos') {
        if (!esAdminOJefatura()) {
          mostrarSubtabCat('operaciones');
        } else {
          mostrarSubtabCat('directorio_clientes');
        }
        cargarGestionCatalogos();
      }
    }

    // ==========================================
    // AUTENTICACIÓN Y SESIÓN
    // ==========================================
    function verificarSesionUsuario() {
      const data = (localStorage.getItem('tireanalyze_usuario_sesion') || localStorage.getItem('tirecheck_usuario_sesion'));
      const token = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (data && token) {
        try {
          usuarioActual = JSON.parse(data);
          actualizarUIUsuario();
          document.getElementById('modalLogin').classList.add('hidden');
          // Sincronizar datos frescos del usuario en tiempo real con el servidor
          sincronizarUsuarioActualSesion();
          return true;
        } catch(e) {
          localStorage.removeItem('tireanalyze_usuario_sesion');
          localStorage.removeItem('tirecheck_usuario_sesion');
          localStorage.removeItem('tireanalyze_token');
          localStorage.removeItem('tirecheck_token');
        }
      }
      document.getElementById('modalLogin').classList.remove('hidden');
      return false;
    }

    async function sincronizarUsuarioActualSesion() {
      try {
        const res = await _originalFetch('/api/usuario-actual');
        if (res.ok) {
          const d = await res.json();
          if (d && d.usuario) {
            usuarioActual = d.usuario;
            localStorage.setItem('tireanalyze_usuario_sesion', JSON.stringify(usuarioActual));
            localStorage.setItem('tirecheck_usuario_sesion', JSON.stringify(usuarioActual));
            actualizarUIUsuario();
            configurarClientesUsuarioEnInspeccion();
          }
        } else if (res.status === 401) {
          cerrarSesionLocal();
        }
      } catch (e) {}
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
        const res = await _originalFetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          credentials: 'same-origin',
          body: JSON.stringify({username: u, password: p})
        });
        const d = await res.json();
        if (res.ok) {
          usuarioActual = d.usuario;
          if (d.token) {
            localStorage.setItem('tireanalyze_token', d.token);
            localStorage.setItem('tirecheck_token', d.token);
          }
          localStorage.setItem('tireanalyze_usuario_sesion', JSON.stringify(usuarioActual));
          localStorage.setItem('tirecheck_usuario_sesion', JSON.stringify(usuarioActual));
          document.getElementById('modalLogin').classList.add('hidden');
          actualizarUIUsuario();
          cargarCatalogos();
          validarVida();
          if (typeof cargarBaseInspecciones === 'function') cargarBaseInspecciones();
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

    async function cerrarSesionUsuario() {
      if (confirm('¿Deseas cerrar tu sesión actual?')) {
        try {
          await _originalFetch('/api/logout', { method: 'POST', credentials: 'same-origin' });
        } catch(e) {}
        localStorage.removeItem('tireanalyze_token');
        localStorage.removeItem('tirecheck_token');
        localStorage.removeItem('tireanalyze_usuario_sesion');
        localStorage.removeItem('tirecheck_usuario_sesion');
        usuarioActual = null;
        document.getElementById('modalLogin').classList.remove('hidden');
        mostrarToast('Sesión cerrada correctamente');
      }
    }

    function actualizarUIUsuario() {
      if (!usuarioActual) return;
      const lbl = document.getElementById('lblUsuarioActivo');
      if (lbl) {
        const rol = String(usuarioActual.rol || '').trim().toLowerCase();
        let rolTag = 'INSPECTOR';
        if (rol === 'admin' || rol === 'administrador') rolTag = 'ADMIN';
        else if (rol === 'jefatura' || rol === 'jefe' || rol === 'jefe_llantas') rolTag = 'JEFATURA LLANTAS';
        else if (rol === 'gerencia' || rol === 'gerente') rolTag = 'GERENCIA';
        lbl.textContent = `${usuarioActual.nombre_completo} [${rolTag}]`;
      }

      // Control de visibilidad de pestañas de navegación según permisos del perfil
      const esAdmin = esUsuarioAdmin();
      const esJefe = esUsuarioJefatura();
      const esGere = esUsuarioGerencia();
      const puedeVerBD = esAdmin || esJefe || esGere;
      const puedeGestionarCat = esAdmin || esJefe;

      let vistasPermitidas = [];
      if (esAdmin) {
        vistasPermitidas = ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'];
      } else {
        const rawV = usuarioActual.vistas_permitidas;
        if (Array.isArray(rawV)) {
          vistasPermitidas = rawV.map(v => String(v).trim().toLowerCase()).filter(Boolean);
        } else if (typeof rawV === 'string' && rawV.trim()) {
          vistasPermitidas = rawV.split(',').map(v => v.trim().toLowerCase()).filter(Boolean);
        } else {
          vistasPermitidas = esJefe ? ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'] : (esGere ? ['basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas'] : ['patio', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos']);
        }
      }

      ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'].forEach(tab => {
        const btnNav = document.getElementById(`nav-btn-${tab}`);
        if (btnNav) {
          // REGLA: inspectores no pueden ver la pestaña base de inspecciones
          if (!puedeVerBD && tab === 'basedatos') {
            btnNav.classList.add('hidden');
            btnNav.style.display = 'none';
          } else if (vistasPermitidas.includes(tab)) {
            btnNav.classList.remove('hidden');
            btnNav.style.display = 'flex';
          } else {
            btnNav.classList.add('hidden');
            btnNav.style.display = 'none';
          }
        }
      });

      // REGLA: Admin y Jefatura pueden agregar/editar operaciones, tipologías y modelos en catálogos
      const btnOp = document.getElementById('btnNuevaOperacionCat');
      if (btnOp) btnOp.classList.toggle('hidden', !puedeGestionarCat);
      const btnTip = document.getElementById('btnNuevaTipologiaCat');
      if (btnTip) btnTip.classList.toggle('hidden', !puedeGestionarCat);
      const btnMod = document.getElementById('btnNuevoModeloCat');
      if (btnMod) btnMod.classList.toggle('hidden', !puedeGestionarCat);

      // REGLA: Admin y Jefatura de Llantas pueden ver y configurar límites de retiro por cliente/eje
      const subtabCli = document.getElementById('subtab-btn-clientes');
      if (subtabCli) subtabCli.classList.toggle('hidden', !puedeGestionarCat);

      // REGLA: solo el superadmin puede ver y crear nuevos usuarios
      const subtabUsrs = document.getElementById('subtab-btn-usuarios');
      if (subtabUsrs) subtabUsrs.classList.toggle('hidden', !esAdmin);

      // REGLA: Gerencia es estrictamente de auditoría y análisis (solo lectura). No puede crear ni importar inspecciones.
      const btnNuevaInspBD = document.getElementById('btnNuevaInspBD');
      if (btnNuevaInspBD) btnNuevaInspBD.classList.toggle('hidden', esGere);
      const btnImportarExcelBD = document.getElementById('btnImportarExcelBD');
      if (btnImportarExcelBD) btnImportarExcelBD.classList.toggle('hidden', esGere);

      // Configurar estado de clientes asignados en la vista de Patio
      configurarClientesUsuarioEnInspeccion();
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

      toast.style.zIndex = '99999';
      toast.className = `fixed bottom-20 lg:bottom-6 right-4 sm:right-6 z-[99999] transform transition-all duration-300 p-3.5 sm:p-4 rounded-2xl text-xs sm:text-sm font-bold shadow-2xl max-w-md border backdrop-blur-md flex items-start space-x-3 ${
        esError || esCandado
          ? 'bg-rose-950/95 text-rose-100 border-rose-600 shadow-rose-950/50 ring-2 ring-rose-500/50' 
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
        tipo_licencia: (typeof clienteLicenciaCaptura !== 'undefined' && clienteLicenciaCaptura) ? clienteLicenciaCaptura : (typeof modoLicenciaGraficos !== 'undefined' ? modoLicenciaGraficos : 'PRO'),
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

    function cambiarModoLicenciaSuite(nuevoModo) {
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
      cargarSuite20Kpis();
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

        // Si el backend dictamina licencia del cliente, sincronizar si no se forzó manual
        if (data.licencia && data.licencia !== modoLicenciaSuite) {
          // mantenemos modo actual
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
            labels: ['Baja Severa (<-15%)', 'Baja Moderada (-15% a -5%)', 'Correcta (±5%)', 'Sobrepresión (>+10%)'],
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
        elGalones.textContent = `${formatCO_Miles(d.galones_desperdiciados_mes || 0)} gal/mes`;
      }
    }

    // KPI 10: Pareto de Novedades y Taller
    function renderChartKpi10(d) {
      destruirChartSuite('kpi10_pareto');
      const ctx = document.getElementById('canvasKpi10_pareto');
      if (!ctx || !d) return;

      const elEfect = document.getElementById('kpi10_efectividad_badge');
      if (elEfect && d.efectividad_taller_pct !== undefined) {
        elEfect.textContent = `Efectividad: ${formatCO_Decimal(d.efectividad_taller_pct, 1)}%`;
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
      if (elKmRec) elKmRec.textContent = `${formatCO_Miles(d.km_recorridos || 0)} km`;
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
              label: 'Km Reales Rodados',
              data: ds.km_reales || [],
              backgroundColor: gradientReales,
              borderColor: '#1e40af',
              borderWidth: 1.5,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(30, 64, 175, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} km`)
            },
            {
              label: 'Proyección Final al Retiro',
              data: ds.proyeccion_final || [],
              backgroundColor: gradientProy,
              borderColor: '#2563eb',
              borderWidth: 1.5,
              borderDash: [4, 4],
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(37, 99, 235, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} km`)
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
                label: (c) => `${c.dataset.label}: ${formatCO_Miles(c.raw)} km`,
                afterBody: (items) => {
                  const idx = items[0].dataIndex;
                  const r = ds.km_reales?.[idx] || 0;
                  const p = ds.proyeccion_final?.[idx] || 0;
                  const dif = Math.max(0, p - r);
                  return `Vida Remanente Est.: ${formatCO_Miles(dif)} km`;
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
              label: 'Proy. Km Final',
              data: ds.proyeccion_km || [],
              backgroundColor: gradProy,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(67, 56, 202, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} km`)
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Proyección: ${formatCO_Miles(c.raw)} km` } }
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
              label: 'Rendimiento Km/mm',
              data: ds.km_mm || [],
              backgroundColor: gradKmmm,
              borderRadius: 6,
              datalabels: pillDatalabelConfig('rgba(4, 120, 87, 0.9)', '#ffffff', (v) => `${formatCO_Decimal(v, 1)} km/mm`)
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26, right: 8, bottom: 8, left: 8 } },
            animation: animacionCascadaStandard,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (c) => `Rendimiento: ${formatCO_Decimal(c.raw, 1)} km/mm` } }
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
              label: 'CPK ($/km)',
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
              tooltip: { callbacks: { label: (c) => `CPK: $ ${formatCO_Decimal(c.raw, 2)} COP/km` } }
            },
            scales: {
              y: { beginAtZero: true, grace: '15%', ticks: { callback: (v) => `$${formatCO_Decimal(v, 1)}`, font: { size: 9 } } },
              x: { ticks: { font: { weight: 'bold', size: 10 } } }
            }
          }
        });
      }
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
                label: (c) => `${c.dataset.label}: ${formatCO_Miles(c.raw)} km`
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
              label: 'Proyección Promedio (km)',
              data: ds.proyeccion_promedio || [],
              borderColor: '#4f46e5',
              backgroundColor: 'rgba(79, 70, 229, 0.12)',
              fill: true,
              borderWidth: 2.8,
              pointRadius: 4,
              tension: 0.35,
              yAxisID: 'y1',
              datalabels: pillDatalabelConfig('rgba(67, 56, 202, 0.9)', '#ffffff', (v) => `${formatCO_Miles(v)} km`)
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
              title: { display: true, text: 'Proyección (km)', font: { weight: 'bold', size: 10 } },
              grid: { drawOnChartArea: false },
              ticks: { callback: (v) => `${formatCO_Miles(v)} km` }
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
        selCli.innerHTML = '<option value="Todos">Todos los Clientes</option>' +
          clientes.map(c => `<option value="${c}">${c}</option>`).join('');
        if (clientes.includes(valCli)) selCli.value = valCli;
      }

      actualizarCombosSedesDiagnostico();

      if (selOp) {
        const valOp = selOp.value || 'Todos';
        selOp.innerHTML = '<option value="Todos">Todas las Operaciones</option>' +
          operaciones.map(o => `<option value="${o}">${o}</option>`).join('');
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

      selSede.innerHTML = '<option value="Todos">Todas las Sedes</option>' +
        sedes.map(s => `<option value="${s}">${s}</option>`).join('');

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

    function renderizarTablaDiagnostico() {
      const tbody = getDiagEl('tbody_diagnostico_web', 'tbodyDiagnostico');
      const contenedorPaginacion = document.getElementById('contenedorPaginacionDiag');
      if (!tbody) return;

      if (!cacheFiltradasDiag || cacheFiltradasDiag.length === 0) {
        tbody.innerHTML = `<tr><td colspan="12" class="p-8 text-center text-slate-400 font-medium">No hay vehículos que coincidan con los filtros seleccionados.</td></tr>`;
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

      tbody.innerHTML = paginaItems.map(r => {
        const cantCambios = Number(r.Cant_Cambios) || (r.Plan_Cambio_Llanta === 'SÍ' ? 1 : 0);
        const cantProx = Number(r.Cant_Proximas) || 0;
        const esAlin = r.Plan_Alineacion === 'SÍ';
        const esDual = r.Plan_Dual_Mal_Apareado === 'SÍ';
        const esRotAuto = r.Badge_Rotacion === 'AUTO-AJUSTE';
        const esRot = r.Plan_Rotacion === 'SÍ';

        const bgRow = cantCambios > 0 ? 'bg-rose-50/50' : (esAlin || esDual || cantProx > 0) ? 'bg-amber-50/40' : '';

        // Bloques de prescripción formateados (Sección 5 Columna 11)
        let bloquesHtml = '';
        if (Array.isArray(r.Bloques_Recomendaciones) && r.Bloques_Recomendaciones.length > 0) {
          bloquesHtml = `<div class="flex flex-col gap-1 max-w-sm whitespace-normal">` +
            r.Bloques_Recomendaciones.map(b => {
              let cls = 'bg-slate-50 text-slate-700 border-slate-200';
              let ico = 'fa-circle-info';
              if (b.tipo === 'CAMBIO_YA' || b.tipo === 'RETIRO' || b.tipo === 'PAR_DIRECCIONAL') {
                cls = 'bg-rose-50 text-rose-800 border-rose-200 font-bold';
                ico = 'fa-triangle-exclamation text-rose-600';
              } else if (b.tipo === 'PROXIMO' || b.tipo === 'PROXIMA') {
                cls = 'bg-amber-50 text-amber-800 border-amber-200 font-medium';
                ico = 'fa-clock text-amber-600';
              } else if (b.tipo === 'ALINEACION') {
                cls = 'bg-orange-50 text-orange-800 border-orange-200 font-medium';
                ico = 'fa-arrows-left-right text-orange-600';
              } else if (b.tipo === 'DUAL') {
                cls = 'bg-purple-50 text-purple-800 border-purple-200 font-medium';
                ico = 'fa-scale-unbalanced text-purple-600';
              } else if (b.tipo === 'AUTO_AJUSTE') {
                cls = 'bg-indigo-50 text-indigo-800 border-indigo-200 font-bold';
                ico = 'fa-rotate text-indigo-600';
              } else if (b.tipo === 'ROTACION' || b.tipo === 'EQUIS_LARGA' || b.tipo === 'ROTACION_IRREGULAR' || b.tipo === 'ROTACION_ESCALONADO') {
                cls = 'bg-blue-50 text-blue-800 border-blue-200 font-medium';
                ico = 'fa-arrows-rotate text-blue-600';
              } else if (b.tipo === 'PRESION') {
                cls = 'bg-cyan-50 text-cyan-800 border-cyan-200 font-medium';
                ico = 'fa-gauge text-cyan-600';
              } else if (b.tipo === 'OK') {
                cls = 'bg-emerald-50 text-emerald-800 border-emerald-200 font-medium';
                ico = 'fa-check text-emerald-600';
              }
              return `<span class="inline-flex items-center text-[10px] px-2 py-0.5 rounded border ${cls} leading-snug">
                        <i class="fa-solid ${ico} mr-1.5 shrink-0 text-[9px]"></i>
                        <span>${b.texto}</span>
                      </span>`;
            }).join('') +
          `</div>`;
        } else {
          const lineas = [];
          if (r.Detalle_Cambio && r.Detalle_Cambio !== 'OK') lineas.push(`<span class="text-rose-700 font-bold">Cambio: ${r.Detalle_Cambio}</span>`);
          if (r.Detalle_Proximas && r.Detalle_Proximas !== 'OK') lineas.push(`<span class="text-amber-700">Próximas: ${r.Detalle_Proximas}</span>`);
          if (r.Detalle_Alineacion && r.Detalle_Alineacion !== 'OK') lineas.push(`<span class="text-orange-700">Alineación: ${r.Detalle_Alineacion}</span>`);
          if (r.Detalle_Dual && r.Detalle_Dual !== 'OK') lineas.push(`<span class="text-purple-700">Dual: ${r.Detalle_Dual}</span>`);
          if (r.Detalle_Auto_Ajuste && r.Detalle_Auto_Ajuste !== 'OK') lineas.push(`<span class="text-indigo-700 font-bold">Auto-Ajuste: ${r.Detalle_Auto_Ajuste}</span>`);
          if (r.Detalle_Calibracion_PSI && r.Detalle_Calibracion_PSI !== 'OK') lineas.push(`<span class="text-cyan-700">Presión: ${r.Detalle_Calibracion_PSI}</span>`);
          if (lineas.length === 0) lineas.push('<span class="text-emerald-700">Sin alertas activas (Vehículo OK)</span>');
          bloquesHtml = `<div class="text-[11px] max-w-sm whitespace-normal space-y-0.5">${lineas.join('<br>')}</div>`;
        }

        return `
          <tr class="${bgRow} hover:bg-slate-100 transition-colors">
            <!-- 1. Placa -->
            <td class="p-2.5 font-black text-slate-900">
              <div>${r['Vehículo/Placa']}</div>
              ${r.Fecha ? `<div class="text-[10px] text-slate-400 font-normal font-mono"><i class="fa-regular fa-calendar-days text-[9px] mr-1"></i>${r.Fecha}</div>` : ''}
            </td>
            <!-- 2. Cliente / Sede -->
            <td class="p-2.5">
              <div class="font-bold text-slate-800">${r.Cliente || '-'}</div>
              ${r.Subcliente ? `<div class="text-[10px] text-slate-400 font-normal">${r.Subcliente}</div>` : ''}
            </td>
            <!-- 3. Tipología -->
            <td class="p-2.5">
              <div class="font-bold text-slate-700">${r.Tipo || '-'}</div>
              ${r.Operación ? `<div class="text-[10px] text-slate-400">${r.Operación}</div>` : ''}
            </td>
            <!-- 4. Inspeccionadas -->
            <td class="p-2.5 text-center">
              <span class="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-slate-100 text-slate-800 font-bold font-mono text-xs">
                ${r['Llantas Inspeccionadas'] || 0}
              </span>
            </td>
            <!-- 5. Límite Retiro -->
            <td class="p-2.5 text-center font-mono font-bold text-slate-600">${r.Limite_Retiro_mm || 3.0} mm</td>
            <!-- 6. Alineación -->
            <td class="p-2.5 text-center">
              ${esAlin 
                ? '<span class="bg-amber-100 text-amber-800 font-black px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' 
                : '<span class="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full text-[10px]">OK</span>'}
            </td>
            <!-- 7. Dual Parejas -->
            <td class="p-2.5 text-center">
              ${esDual 
                ? '<span class="bg-purple-100 text-purple-800 font-black px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' 
                : '<span class="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full text-[10px]">OK</span>'}
            </td>
            <!-- 8. Cambio YA -->
            <td class="p-2.5 text-center">
              ${cantCambios > 0 
                ? `<span class="bg-rose-100 text-rose-800 font-black px-2 py-0.5 rounded-full text-[10px] animate-pulse">URGENTE (${cantCambios})</span>` 
                : '<span class="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full text-[10px]">OK</span>'}
            </td>
            <!-- 9. Próximas -->
            <td class="p-2.5 text-center">
              ${cantProx > 0 
                ? `<span class="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full text-[10px]">PRÓXIMO (${cantProx})</span>` 
                : '<span class="text-slate-400 font-mono text-[11px]">0</span>'}
            </td>
            <!-- 10. Rotación -->
            <td class="p-2.5 text-center">
              ${esRotAuto 
                ? '<span class="bg-indigo-100 text-indigo-800 font-black px-2 py-0.5 rounded-full text-[10px]">AUTO-AJUSTE</span>' 
                : esRot 
                  ? '<span class="bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded-full text-[10px]">SÍ</span>' 
                  : '<span class="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full text-[10px]">OK</span>'}
            </td>
            <!-- 11. Detalles & Recomendaciones -->
            <td class="p-2.5">${bloquesHtml}</td>
            <!-- 12. Plan PDF -->
            <td class="p-2.5 text-center">
              <button type="button" onclick="abrirModalInformePdf('${r['Vehículo/Placa']}', '${r.Fecha || ''}', '${r.Cliente || ''}', '${r.Tipo || ''}')" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg text-xs transition-all shadow-xs active:scale-95 cursor-pointer" title="Generar Informe Técnico PDF de ${r['Vehículo/Placa']}">
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

          const valTxt = pb > 0 ? pb.toFixed(1) : '0.0';
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

        const subClienteTxt = r.subcliente ? `<br><span class="text-[10px] text-slate-400 font-normal">${r.subcliente}</span>` : '';
        const tipoTxt = r.tipologia ? `<span class="truncate block max-w-[110px]" title="${r.tipologia}">${r.tipologia}</span>` : '-';
        const limTxt = (r.limite ? Number(r.limite).toFixed(1) : '3.0') + ' mm';

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-2.5 font-black text-slate-900 sticky left-0 z-10 bg-white border-r border-slate-100 text-left shadow-2xs">${r.placa}</td>
            <td class="p-2.5 text-left font-bold text-slate-700">${r.cliente || '-'}${subClienteTxt}</td>
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
                <td class="p-1.5 text-center border-l border-slate-200 font-mono text-[10px] whitespace-nowrap" title="Totales Pos P${p}: ${t.rojo} Retiro Urgente, ${t.amarillo} Próxima a Cambio, ${t.verde} Óptima">
                  <span class="text-rose-700 font-black">${t.rojo}</span>/<span class="text-amber-700 font-bold">${t.amarillo}</span>/<span class="text-emerald-700 font-bold">${t.verde}</span>
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

      const params = new URLSearchParams();
      if (qNum) params.append('numero_interno', qNum);
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);
      if (marca && marca !== 'TODOS') params.append('marca', marca);

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
          const lblTodos = clisAsignados.length > 1 ? 'Todas Mis Flotas Asignadas' : 'Todos los Clientes';
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
        selSub.innerHTML = '<option value="TODOS">Todas las Sedes</option>' +
          subclientes.map(s => `<option value="${s}">${s}</option>`).join('');
        if (valSubActual && subclientes.includes(valSubActual)) selSub.value = valSubActual;
        else selSub.value = 'TODOS';
      }

      // Operaciones
      const operaciones = Array.from(new Set((data || []).map(d => d.tipo_operacion).filter(Boolean))).sort();
      if (selOp) {
        selOp.innerHTML = '<option value="TODOS">Todas las Operaciones</option>' +
          operaciones.map(o => `<option value="${o}">${o}</option>`).join('');
        if (valOpActual && operaciones.includes(valOpActual)) selOp.value = valOpActual;
        else selOp.value = 'TODOS';
      }

      // Marcas
      const marcas = Array.from(new Set((data || []).map(d => d.marca).filter(Boolean))).sort();
      if (selMar) {
        selMar.innerHTML = '<option value="TODOS">Todas las Marcas</option>' +
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

      const prom_km_mm = km_mms.length ? (km_mms.reduce((a, b) => a + b, 0) / km_mms.length) : 0;
      const prom_cpk = cpks.length ? (cpks.reduce((a, b) => a + b, 0) / cpks.length) : 0;
      const prom_proy = proys.length ? (proys.reduce((a, b) => a + b, 0) / proys.length) : 0;

      if (elTotal) elTotal.textContent = data.length.toLocaleString();
      if (elKm) elKm.textContent = prom_km_mm.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
      if (elCpk) elCpk.textContent = `$${prom_cpk.toFixed(4)}`;
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
        selSub.innerHTML = '<option value="TODOS">Todas las Sedes</option>' +
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

      const params = new URLSearchParams();
      if (qNum) params.append('numero_interno', qNum);
      if (cli && cli !== 'TODOS') params.append('cliente', cli);
      if (sub && sub !== 'TODOS') params.append('subcliente', sub);
      if (op && op !== 'TODOS') params.append('tipo_operacion', op);
      if (marca && marca !== 'TODOS') params.append('marca', marca);

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
      return ['reenc', '1r', '2r', '3r', '4r', 'r1', 'r2', 'r3', 'renov'].some(token => v.includes(token));
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
            marca: normalizarTextoComp(item.marca, 'GENÉRICA'),
            diseno: normalizarTextoComp(item.diseno, 'ESTÁNDAR'),
            dimension: normalizarTextoComp(item.dimension, 'ESTÁNDAR'),
            cliente: normalizarTextoComp(item.cliente, 'FLOTA GENERAL'),
            subcliente: normalizarTextoComp(item.subcliente, 'SEDE PRINCIPAL'),
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

      let htmlCli = '<option value="TODOS">Todos los Clientes</option>';
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

      rellenarSelect(selSub, subs, 'Todas las Sedes');
      rellenarSelect(selMarca, marcas, 'Todas las Marcas');
      rellenarSelect(selDim, dims, 'Todas las Medidas');
      rellenarSelect(selDis, disenos, 'Todos los Diseños');
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
        const pctR = ((cntReenc / totalLlantas) * 100).toFixed(1);
        const pctO = ((cntOrig / totalLlantas) * 100).toFixed(1);
        if (elPctReenc) elPctReenc.textContent = `${pctR}%`;
        if (elCntReenc) elCntReenc.textContent = `${cntReenc} llanta(s) reencauchada(s)`;
        if (elPctOrig) elPctOrig.textContent = `${pctO}%`;
        if (elCntOrig) elCntOrig.textContent = `${cntOrig} llanta(s) originales`;

        const arrM = Object.entries(mapaMarcas).sort((a, b) => b[1] - a[1]);
        const arrDm = Object.entries(mapaDimensiones).sort((a, b) => b[1] - a[1]);
        const arrDs = Object.entries(mapaDisenos).sort((a, b) => b[1] - a[1]);

        if (arrM.length > 0) {
          const [mNom, mCant] = arrM[0];
          const mPct = ((mCant / totalLlantas) * 100).toFixed(1);
          if (elTopMarca) elTopMarca.textContent = mNom;
          if (elSubMarca) elSubMarca.textContent = `${mCant} llantas (${mPct}%)`;
        }
        if (arrDm.length > 0) {
          const [dNom, dCant] = arrDm[0];
          const dPct = ((dCant / totalLlantas) * 100).toFixed(1);
          if (elTopDim) elTopDim.textContent = dNom;
          if (elSubDim) elSubDim.textContent = `${dCant} llantas (${dPct}%)`;
        }
        if (arrDs.length > 0) {
          const [sNom, sCant] = arrDs[0];
          const sPct = ((sCant / totalLlantas) * 100).toFixed(1);
          if (elTopDis) elTopDis.textContent = sNom;
          if (elSubDis) elSubDis.textContent = `${sCant} llantas montadas (${sPct}%)`;
        }
      }

      // 4. Panel de Auditoría: "Las 4 Reglas de Oro de Negocio" (Sección 8 del Manual)
      // Regla de Oro 1: Cero Reencauches en Dirección
      const llantasDireccionales = dataFiltrada.filter(x => x.tipo_eje === 'direccional');
      const totalDir = llantasDireccionales.length;
      const reencEnDir = llantasDireccionales.filter(x => esLlantaReencauchadaComp(x.vida)).length;
      const pctReencDir = totalDir > 0 ? ((reencEnDir / totalDir) * 100).toFixed(1) : '0.0';

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
          descR1.textContent = `Se detectaron ${reencEnDir} llanta(s) reencauchada(s) en Eje Direccional (${pctReencDir}%). El estándar exige estrictamente 0.0%.`;
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
      const pctLibres = llantasLibres.length > 0 ? ((reencLibres / llantasLibres.length) * 100).toFixed(1) : '0.0';

      const llantasTrac = dataFiltrada.filter(x => x.tipo_eje === 'traccion');
      const reencTrac = llantasTrac.filter(x => esLlantaReencauchadaComp(x.vida)).length;
      const pctTrac = llantasTrac.length > 0 ? ((reencTrac / llantasTrac.length) * 100).toFixed(1) : '0.0';

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
          if (descR3) descR3.textContent = `Medida líder concentra ${topDimPct.toFixed(1)}% con ${totalDimsDistintas} medidas activas. Se sugiere racionalizar.`;
        } else {
          if (cardR3) cardR3.className = 'p-3 rounded-2xl border transition-all duration-300 bg-emerald-50 border-emerald-200';
          if (badgeR3) {
            badgeR3.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800';
            badgeR3.textContent = 'ESTANDARIZADA';
          }
          if (titR3) titR3.textContent = '✅ Estandarización Óptima';
          if (descR3) descR3.textContent = `Medida principal concentra ${topDimPct.toFixed(1)}% en ${totalDimsDistintas} dimensión(es).`;
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
          const pOrig = ((cntOrig / totVida) * 100).toFixed(1);
          const pReenc = ((cntReenc / totVida) * 100).toFixed(1);

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
            const p = ((cnt / totalLlantas) * 100).toFixed(1);
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
            const p = ((cnt / totalLlantas) * 100).toFixed(1);
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
                      const p = ((cnt / totalLlantas) * 100).toFixed(1);
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
        const pctFlota = totalLlantasFlota > 0 ? ((c.total / totalLlantasFlota) * 100).toFixed(1) : '0.0';
        let profPromText = '—';
        let semaforoProf = 'text-slate-600 bg-slate-100 border border-slate-200';
        let semaforoDot = 'bg-slate-400';

        if (c.cantProf > 0) {
          const prom = (c.sumaProf / c.cantProf);
          profPromText = `${prom.toFixed(1)} mm`;
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
      document.getElementById('nuevo_cliente_licencia').value = 'PRO';
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
      document.getElementById('nuevo_cliente_licencia').value = cli.tipo_licencia || 'PRO';
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


    // ==========================================
    // FUNCIONES DEL MOTOR DE PATIO Y CAPTURA
    // ==========================================
    function asignarValorSelect(selectId, valor) {
      const sel = document.getElementById(selectId);
      if (!sel || valor === undefined || valor === null || valor === '') return;
      const valStr = String(valor).trim();
      let opt = Array.from(sel.options).find(o => o.value.trim().toLowerCase() === valStr.toLowerCase());
      if (!opt) {
        opt = document.createElement('option');
        opt.value = valStr;
        opt.textContent = valStr;
        const optNuevo = Array.from(sel.options).find(o => o.value === '__nuevo__');
        if (optNuevo) {
          sel.insertBefore(opt, optNuevo);
        } else {
          sel.appendChild(opt);
        }
      }
      sel.value = opt.value;
    }

    function verificarOpcionNuevaSelect(sel, nombreCampo = 'valor') {
      if (sel.id === 'marca' && sel.value === '__ver_todas__') {
        const cli = document.getElementById('cliente')?.value?.trim() || '';
        actualizarMarcasCliente(cli, null, true);
        mostrarToast("Mostrando todas las marcas del catálogo");
        return;
      }
      if (sel.id === 'marca' && sel.value === '__solo_cliente__') {
        const cli = document.getElementById('cliente')?.value?.trim() || '';
        actualizarMarcasCliente(cli, null, false);
        mostrarToast(`Mostrando marcas habituales de ${cli}`);
        return;
      }
      if (sel.value === '__nuevo__') {
        const nuevo = prompt(`Ingresa nuevo ${nombreCampo}:`);
        if (nuevo && nuevo.trim()) {
          const valLimpio = nuevo.trim();
          asignarValorSelect(sel.id, valLimpio);
          mostrarToast(`Agregado: ${valLimpio}`);
          if (sel.id === 'marca') {
            alCambiarMarcaMobile();
            // Si hay cliente seleccionado, registrar automáticamente esta marca para el cliente en backend
            const cli = document.getElementById('cliente')?.value?.trim();
            if (cli && cli !== '__nuevo__') {
              fetch('/api/configuracion-marcas-cliente', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ cliente: cli, marca: valLimpio })
              }).catch(e => console.error("Error al guardar marca cliente:", e));
            }
          }
          if (sel.id === 'cliente') alCambiarClienteMobile();
          if (sel.id === 'dimension') {
            if (!dimensionPredeterminadaVehiculo || posicionesInspeccionadasPlaca.size === 0) {
              dimensionPredeterminadaVehiculo = valLimpio;
            }
          }
          if (sel.id === 'diseno' || sel.id === 'dimension') autoCompletarProfInicial();
        } else {
          sel.value = '';
        }
      }
    }

    async function actualizarMarcasCliente(cli, valorSeleccionado = null, mostrarTodas = false) {
      const selMarca = document.getElementById('marca');
      if (!selMarca) return;
      const cliente = cli || document.getElementById('cliente')?.value?.trim() || '';
      const valorPrevio = valorSeleccionado !== null ? valorSeleccionado : (selMarca.value || '');

      let url = `/api/valores-campo?campo=marca`;
      if (cliente && !mostrarTodas) {
        url += `&cliente=${encodeURIComponent(cliente)}`;
      }
      if (mostrarTodas) {
        url += `&todas=true`;
      }

      try {
        const res = await fetch(url);
        if (!res.ok) return;
        const marcas = await res.json();
        const unicos = [];
        const vistos = new Set();
        (marcas || []).forEach(m => {
          const norm = String(m || '').trim();
          if (norm && !vistos.has(norm.toLowerCase())) {
            vistos.add(norm.toLowerCase());
            unicos.push(norm);
          }
        });

        const placeholder = cliente && !mostrarTodas
          ? `ej. Michelin (Marcas de ${cliente})`
          : `ej. Michelin (Catálogo completo de marcas)`;

        let html = `<option value="" disabled ${!valorPrevio ? 'selected' : ''} class="text-slate-400 font-normal">${placeholder}</option>`;

        if (mostrarTodas && cliente) {
          html += `<option value="__solo_cliente__" class="font-bold text-emerald-700 bg-emerald-50">🔍 Volver a marcas frecuentes de ${cliente}</option>`;
        }

        unicos.forEach(m => {
          const isSel = (valorPrevio && valorPrevio.toLowerCase() === m.toLowerCase());
          html += `<option value="${m}" ${isSel ? 'selected' : ''}>${m}</option>`;
        });

        if (!mostrarTodas && cliente) {
          html += `<option value="__ver_todas__" class="font-bold text-indigo-700 bg-indigo-50">📋 Ver todas las marcas del catálogo...</option>`;
        }
        html += `<option value="__nuevo__" class="font-bold text-blue-600 bg-blue-50">+ Agregar nueva marca...</option>`;
        selMarca.innerHTML = html;

        if (valorPrevio) {
          asignarValorSelect('marca', valorPrevio);
        }

        const badge = document.getElementById('badgeMarcasModo');
        if (badge) {
          if (cliente && !mostrarTodas) {
            badge.textContent = `★ ${unicos.length} marcas de flota`;
            badge.className = "text-[10px] text-blue-600 font-bold block";
          } else if (mostrarTodas) {
            badge.textContent = `🌐 Catálogo completo (${unicos.length})`;
            badge.className = "text-[10px] text-indigo-600 font-bold block";
          } else {
            badge.className = "hidden";
          }
        }
      } catch (err) {
        console.error("Error al actualizar marcas de cliente:", err);
      }
    }

    async function poblarSelect(elementId, endpoint, placeholderTexto, valorSeleccionado = null) {
      const sel = document.getElementById(elementId);
      if (!sel) return;
      const valorPrevio = valorSeleccionado !== null ? valorSeleccionado : (sel.value || '');
      try {
        const res = await fetch(endpoint);
        if (res.ok) {
          const items = await res.json();
          const unicos = [];
          const vistos = new Set();
          (items || []).forEach(it => {
            const normal = String(it || '').trim();
            if (normal && !vistos.has(normal.toLowerCase())) {
              vistos.add(normal.toLowerCase());
              unicos.push(normal);
            }
          });

          let html = `<option value="" disabled ${!valorPrevio ? 'selected' : ''} class="text-slate-400 font-normal">${placeholderTexto}</option>`;
          unicos.forEach(it => {
            const isSel = (valorPrevio && valorPrevio.toLowerCase() === it.toLowerCase());
            html += `<option value="${it}" ${isSel ? 'selected' : ''}>${it}</option>`;
          });
          html += `<option value="__nuevo__" class="font-bold text-blue-600 bg-blue-50">+ Agregar nuevo valor...</option>`;
          sel.innerHTML = html;

          if (valorPrevio && !vistos.has(valorPrevio.toLowerCase())) {
            asignarValorSelect(elementId, valorPrevio);
          } else if (valorPrevio) {
            sel.value = valorPrevio;
          }

          // Mantener compatibilidad con datalist si existe en el DOM
          const dl = document.getElementById(`dl_${elementId}`) || document.getElementById(`dl_${elementId}s`);
          if (dl) dl.innerHTML = unicos.map(i => `<option value="${i}">`).join('');
        }
      } catch(e) {}
    }

    async function cargarCatalogos(seleccionarOp = null, seleccionarTip = null) {
      await Promise.all([
        poblarSelect('cliente', '/api/valores-campo?campo=cliente', 'ej. TransCarga (Seleccionar cliente)'),
        poblarSelect('dimension', '/api/valores-campo?campo=dimension', '295/80R22.5', '295/80R22.5')
      ]);

      // Aplicar predeterminación o filtrado de clientes asignados al usuario en sesión
      configurarClientesUsuarioEnInspeccion();

      const cliInicial = document.getElementById('cliente')?.value?.trim() || '';
      await actualizarMarcasCliente(cliInicial);

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
      // Wrapper de compatibilidad hacia atrás
      const idCampo = elementId.replace(/^dl_/, '').replace(/s$/, '');
      if (document.getElementById(idCampo)?.tagName === 'SELECT') {
        return poblarSelect(idCampo, endpoint, `Seleccionar ${idCampo}...`);
      }
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
      if (cli && cli !== '__nuevo__') {
        await Promise.all([
          poblarSelect('subcliente', `/api/valores-campo?campo=subcliente&cliente=${encodeURIComponent(cli)}`, 'ej. Principal (Seleccionar sede)'),
          actualizarLimiteCliente(),
          actualizarMarcasCliente(cli)
        ]);
        const numInt = (document.getElementById('numero_interno')?.value || '').trim();
        if (numInt) {
          consultarLlantaPorCliente(numInt);
        }
      }
    }

    let clienteLicenciaCaptura = 'PRO';

    async function actualizarLimiteCliente() {
      const cli = document.getElementById('cliente').value.trim();
      const res = await fetch(`/api/limite-cliente?cliente=${encodeURIComponent(cli)}`);
      if (res.ok) {
        const d = await res.json();
        const mm = d.limite_retiro_mm || 3.0;
        document.getElementById('lblMmRetiroCliente').textContent = mm.toFixed(1);
        document.getElementById('lblMmAlerta').textContent = mm.toFixed(1);
        if (d.tipo_licencia) {
          clienteLicenciaCaptura = d.tipo_licencia;
        }
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

    /**
     * Calcula el orden físico de inspección del vehículo caminando alrededor:
     * 1. Lado Izquierdo (ejes 1..N de adelante hacia atrás, exterior antes de interior).
     * 2. Lado Derecho (ejes 1..N de adelante hacia atrás, exterior antes de interior).
     * 3. Soporte de Repuesto al final.
     * Ejemplo en articulado: 1, 3, 4, 7, 8, 2, 6, 5, 10, 9.
     */
    function calcularOrdenInspeccion(esquema, posicionesFallback) {
      if (!esquema || !Array.isArray(esquema) || esquema.length === 0) {
        return posicionesFallback || [1, 3, 4, 7, 8, 2, 6, 5, 10, 9];
      }
      const izq = [];
      const der = [];
      const rep = [];

      const ejesRodantes = esquema.filter(e => e.eje !== 99 && (e.tipo || '').toLowerCase() !== 'repuesto');
      const ejesRepuesto = esquema.filter(e => e.eje === 99 || (e.tipo || '').toLowerCase() === 'repuesto');

      // Lado Izquierdo (ejes 1..N): primero ext, luego int
      ejesRodantes.forEach(eje => {
        const posEjeIzq = (eje.posiciones || []).filter(p => (p.lado || '').toLowerCase() === 'izq');
        posEjeIzq.sort((a, b) => {
          const rolA = (a.rol || '').toLowerCase();
          const rolB = (b.rol || '').toLowerCase();
          if (rolA === 'ext' && rolB === 'int') return -1;
          if (rolA === 'int' && rolB === 'ext') return 1;
          return a.pos - b.pos;
        });
        posEjeIzq.forEach(p => izq.push(p.pos));
      });

      // Lado Derecho (ejes 1..N): primero ext, luego int
      ejesRodantes.forEach(eje => {
        const posEjeDer = (eje.posiciones || []).filter(p => (p.lado || '').toLowerCase() === 'der');
        posEjeDer.sort((a, b) => {
          const rolA = (a.rol || '').toLowerCase();
          const rolB = (b.rol || '').toLowerCase();
          if (rolA === 'ext' && rolB === 'int') return -1;
          if (rolA === 'int' && rolB === 'ext') return 1;
          return a.pos - b.pos;
        });
        posEjeDer.forEach(p => der.push(p.pos));
      });

      // Repuesto(s)
      ejesRepuesto.forEach(eje => {
        (eje.posiciones || []).forEach(p => rep.push(p.pos));
      });

      const orden = [...izq, ...der, ...rep];
      return orden.length > 0 ? orden : (posicionesFallback || [1, 3, 4, 7, 8, 2, 6, 5, 10, 9]);
    }

    async function cambioTipologia() {
      const tip = document.getElementById('tipologia').value;
      try {
        const res = await fetch(`/api/esquema?tipologia=${encodeURIComponent(tip)}`);
        if (res.ok) {
          const d = await res.json();
          esquemaTipologiaCache = d.esquema;
          listaPosicionesActual = calcularOrdenInspeccion(d.esquema, d.posiciones);
          const posActual = parseInt(document.getElementById('posicion').value) || 1;
          renderizarChasisEjes(d.esquema, listaPosicionesActual);
          renderizarBotonesPosicion(listaPosicionesActual, d.esquema);
          renderizarCarruselLlantasMobile();

          // Si la posición actual no existe en la nueva tipología, cambiar a la primera del orden
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
        <svg viewBox="0 0 560 158" class="w-full h-auto max-w-[560px] overflow-visible select-none" xmlns="http://www.w3.org/2000/svg">
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
      const lblResumen = document.getElementById('lblConteoFotosResumen');
      if (lblResumen) {
        const cant = (fotosNovedadActuales && fotosNovedadActuales.length) || 0;
        lblResumen.textContent = cant === 0 ? '0 fotos' : `${cant} foto${cant > 1 ? 's' : ''}`;
      }
    }

    function dispararCamaraDirecta() {
      const inp = document.getElementById('foto_camara_directa_input');
      if (inp) {
        inp.click();
      } else {
        document.getElementById('foto_novedad_input')?.click();
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
    }

    function procesarFotosNovedad(input) {
      if (!input.files || input.files.length === 0) return;
      const files = Array.from(input.files);
      let procesadas = 0;
      const nuevasFotos = [];

      mostrarToast(`📸 Procesando ${files.length} foto(s)...`);

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
      const btnQuitarCont = document.getElementById('btnQuitarTodasContainer');
      const lblConteo = document.getElementById('lblConteoFotosAdjuntas');
      const badgeMob = document.getElementById('badgeFotosMobileSticky');
      const lblResumen = document.getElementById('lblConteoFotosResumen');

      if (!fotosNovedadActuales || fotosNovedadActuales.length === 0) {
        if (previewBox) previewBox.classList.add('hidden');
        if (grid) grid.innerHTML = '';
        if (btnQuitarCont) btnQuitarCont.classList.add('hidden');
        if (badgeMob) badgeMob.classList.add('hidden');
        if (lblResumen) lblResumen.textContent = '0 fotos';
        evaluarHabilitarFotoNovedad();
        return;
      }

      if (previewBox) previewBox.classList.remove('hidden');
      if (btnQuitarCont) btnQuitarCont.classList.remove('hidden');
      if (badgeMob) {
        badgeMob.textContent = fotosNovedadActuales.length;
        badgeMob.classList.remove('hidden');
      }
      if (lblResumen) lblResumen.textContent = `${fotosNovedadActuales.length} foto${fotosNovedadActuales.length > 1 ? 's' : ''}`;
      if (lblConteo) lblConteo.textContent = `${fotosNovedadActuales.length} imagen${fotosNovedadActuales.length > 1 ? 'es' : ''} adjunta${fotosNovedadActuales.length > 1 ? 's' : ''}`;

      if (grid) {
        grid.innerHTML = '';
        fotosNovedadActuales.forEach((foto, idx) => {
          const card = document.createElement('div');
          card.className = 'relative group w-14 h-14 sm:w-16 sm:h-16 rounded-xl overflow-hidden border-2 border-blue-400 bg-slate-900 shadow-sm flex-shrink-0 cursor-pointer transition-transform hover:scale-105';
          card.title = `Clic para ver foto ${idx + 1} en grande`;
          card.innerHTML = `
            <img src="${foto}" alt="Miniatura ${idx + 1}" class="w-full h-full object-cover">
            <button type="button" onclick="event.stopPropagation(); eliminarFotoNovedadIndex(${idx});" class="absolute top-1 right-1 w-5 h-5 bg-rose-600 hover:bg-rose-700 text-white rounded-full flex items-center justify-center text-[10px] shadow transition-all cursor-pointer" title="Quitar esta foto">
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
      const inpCam = document.getElementById('foto_camara_directa_input');
      if (inpCam) inpCam.value = '';
      actualizarUIFotosNovedad();
    }

    function quitarFotoNovedad() {
      quitarTodasFotosNovedad();
    }

    // ==========================================
    // FOTOS EN MODAL DE EDICIÓN DE INSPECCIÓN
    // ==========================================
    let fotosEdicionActuales = [];

    function dispararCamaraEdicion() {
      document.getElementById('edit_foto_camara_input')?.click();
    }

    function procesarFotosEdicion(input) {
      if (!input.files || input.files.length === 0) return;
      const files = Array.from(input.files);
      let procesadas = 0;
      const nuevasFotos = [];

      mostrarToast(`📸 Procesando ${files.length} foto(s)...`);

      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
          const img = new Image();
          img.onload = function() {
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
              fotosEdicionActuales = fotosEdicionActuales.concat(nuevasFotos);
              actualizarUIFotosEdicion();
              mostrarToast(`📸 ${nuevasFotos.length} foto(s) agregada(s) para guardar`);
            }
          };
          img.src = e.target.result;
        };
        reader.readAsDataURL(file);
      });
      input.value = '';
    }

    function actualizarUIFotosEdicion() {
      const b64 = document.getElementById('edit_foto_novedad_base64');
      if (b64) {
        b64.value = fotosEdicionActuales.length > 0 ? JSON.stringify(fotosEdicionActuales) : '';
      }
      const grid = document.getElementById('gridPreviewFotosEdicion');
      if (!grid) return;

      if (!fotosEdicionActuales || fotosEdicionActuales.length === 0) {
        grid.innerHTML = '<span class="text-slate-400 text-xs italic self-center">Sin fotos adjuntas</span>';
        return;
      }

      grid.innerHTML = '';
      fotosEdicionActuales.forEach((foto, idx) => {
        const card = document.createElement('div');
        card.className = 'relative group w-14 h-14 sm:w-16 sm:h-16 rounded-xl overflow-hidden border-2 border-blue-400 bg-slate-900 shadow-sm flex-shrink-0 cursor-pointer transition-transform hover:scale-105';
        card.title = `Clic para ver foto ${idx + 1} en grande`;
        card.innerHTML = `
          <img src="${foto}" alt="Miniatura ${idx + 1}" class="w-full h-full object-cover">
          <button type="button" onclick="event.stopPropagation(); eliminarFotoEdicionIndex(${idx});" class="absolute top-1 right-1 w-5 h-5 bg-rose-600 hover:bg-rose-700 text-white rounded-full flex items-center justify-center text-[10px] shadow transition-all cursor-pointer" title="Quitar esta foto">
            <i class="fa-solid fa-xmark"></i>
          </button>
          <span class="absolute bottom-0 left-0 right-0 bg-slate-900/80 text-white text-[8px] text-center font-mono font-bold leading-tight py-0.5">
            #${idx + 1}
          </span>
        `;
        card.onclick = () => abrirGaleriaFotosDirecta(fotosEdicionActuales, idx, 'Evidencias fotográficas en edición');
        grid.appendChild(card);
      });
    }

    function eliminarFotoEdicionIndex(idx) {
      if (idx >= 0 && idx < fotosEdicionActuales.length) {
        fotosEdicionActuales.splice(idx, 1);
        actualizarUIFotosEdicion();
      }
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

    function esPosicionDireccionalActual(pos) {
      const p = parseInt(pos) || 1;
      if (esquemaTipologiaCache && Array.isArray(esquemaTipologiaCache)) {
        for (const eje of esquemaTipologiaCache) {
          const tipoEje = (eje.tipo || '').toLowerCase();
          const esEjeDir = tipoEje.includes('direccional') || tipoEje === 'dir';
          for (const r of (eje.posiciones || [])) {
            if (parseInt(r.pos) === p) {
              const rol = (r.rol || '').toLowerCase();
              return esEjeDir || rol.includes('dir');
            }
          }
        }
      }
      const tip = (document.getElementById('tipologia')?.value || '').toLowerCase();
      if (tip.includes('cuatro manos') || tip.includes('8x4') || tip.includes('biarticulado')) {
        return [1, 2, 3, 4].includes(p);
      }
      return [1, 2].includes(p);
    }

    function aplicarRestriccionEjeDireccional(pos) {
      const p = parseInt(pos) || 1;
      const esDir = esPosicionDireccionalActual(p);
      const selVida = document.getElementById('vida');
      const optReencauche = selVida ? selVida.querySelector('option[value="Reencauche"]') : null;
      const badge = document.getElementById('badgeDireccionalOriginal');

      if (esDir) {
        if (optReencauche) {
          optReencauche.disabled = true;
          optReencauche.classList.add('text-slate-400');
        }
        if (selVida && selVida.value === 'Reencauche') {
          selVida.value = 'Original';
          validarVida();
        }
        if (badge) badge.classList.remove('hidden');
      } else {
        if (optReencauche) {
          optReencauche.disabled = false;
          optReencauche.classList.remove('text-slate-400');
        }
        if (badge) badge.classList.add('hidden');
      }
    }

    function alCambiarFechaFormulario() {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      if (placa) {
        cargarPosicionesInspeccionadasPlaca(placa);
      }
    }

    /**
     * Selecciona una posición de neumático, actualiza el formulario y sincroniza el chasis.
     */
    async function seleccionarPosicion(p) {
      // Capturar la dimensión ingresada en la primera llanta antes de cambiar si aún no se había fijado
      const dimActual = (document.getElementById('dimension')?.value || '').trim();
      if (dimActual && dimActual !== '__nuevo__' && (!dimensionPredeterminadaVehiculo || posicionesInspeccionadasPlaca.size === 0)) {
        dimensionPredeterminadaVehiculo = dimActual;
      }

      // Si el usuario ingresó un kilometraje en cualquier llanta, conservarlo y reflejarlo en todas las llantas
      const kmActual = parseFloat(document.getElementById('kilometraje')?.value) || 0;
      if (kmActual > 0) {
        kilometrajeInspeccionActual = kmActual;
      } else if (kilometrajeInspeccionActual > 0) {
        const inpKm = document.getElementById('kilometraje');
        if (inpKm) inpKm.value = Math.round(kilometrajeInspeccionActual);
      }

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

      // Candado UI: En eje direccional solo se permite condición Original
      aplicarRestriccionEjeDireccional(p);

      await verificarInspeccionAnterior();
      await autoCompletarProfInicial();
      await actualizarPanelTallerPosicion(p);
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

    // ==========================================
    // AUTOCOMPLETADO PERFIL PLACA <-> ESQUEMA & FLOTA
    // ==========================================
    let timerPlacaDebounce = null;
    let ultimaPlacaConsultadaPerfil = '';
    let ultimaPlacaPopupAlerta = '';
    let perfilVehiculoActual = null;
    let cacheUltimaMarcaVehiculo = '';
    let cacheUltimoDisenoVehiculo = '';
    let cacheUltimaDimensionVehiculo = '';

    function onInputPlacaDebounced() {
      clearTimeout(timerPlacaDebounce);
      timerPlacaDebounce = setTimeout(() => {
        const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
        if (placa && placa.length >= 3) {
          consultarPerfilPlaca(placa);
        }
      }, 300);
    }

    function consultarPerfilPlacaInmediato() {
      clearTimeout(timerPlacaDebounce);
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      if (placa && placa !== ultimaPlacaConsultadaPerfil) {
        consultarPerfilPlaca(placa);
      }
    }

    async function consultarPerfilPlaca(placa) {
      if (!placa) return;
      if (placa !== ultimaPlacaConsultadaPerfil) {
        dimensionPredeterminadaVehiculo = '';
      }
      ultimaPlacaConsultadaPerfil = placa;

      try {
        const res = await fetch(`/api/vehiculo-perfil?placa=${encodeURIComponent(placa)}`);
        if (res.ok) {
          const d = await res.json();
          const placaActual = (document.getElementById('placa')?.value || '').trim().toUpperCase();
          if (placaActual !== placa) return;

          perfilVehiculoActual = d;
          if (d.ultima_marca) cacheUltimaMarcaVehiculo = d.ultima_marca;
          if (d.ultimo_diseno) cacheUltimoDisenoVehiculo = d.ultimo_diseno;
          if (d.dimension) cacheUltimaDimensionVehiculo = d.dimension;

          // Alerta si el vehículo ya fue inspeccionado dentro del período de vigencia técnica
          if (d.en_periodo_restringido && ultimaPlacaPopupAlerta !== placa) {
            mostrarModalVehiculoYaInspeccionado(d);
            ultimaPlacaPopupAlerta = placa;
          }

          if (d.encontrado) {
            // 1. Mostrar badge de tipología fija vinculada al historial
            const b = document.getElementById('badgePlacaVinculada');
            if (b) {
              b.classList.remove('hidden');
              b.innerHTML = '<i class="fa-solid fa-lock text-[9px] mr-1"></i>Tipología Fija (Historial)';
            }

            // 2. Precargar Cliente, Subcliente y Operación de la inspección anterior
            if (d.cliente) {
              asignarValorSelect('cliente', d.cliente);
              await alCambiarClienteMobile();
            }

            if (d.subcliente && document.getElementById('subcliente')) {
              asignarValorSelect('subcliente', d.subcliente);
            }

            if (d.tipo_operacion && document.getElementById('tipo_operacion')) {
              asignarValorSelect('tipo_operacion', d.tipo_operacion);
            }

            // 2.1 Precargar dimensión histórica del vehículo si está disponible
            if (d.dimension) {
              dimensionPredeterminadaVehiculo = d.dimension;
              asignarValorSelect('dimension', d.dimension);
            }

            // 3. Odómetro / Km si está disponible
            const inputKm = document.getElementById('kilometraje');
            if (d.ultimo_km > 0) {
              kilometrajeInspeccionActual = d.ultimo_km;
              if (inputKm) inputKm.value = Math.round(d.ultimo_km);
            } else if (kilometrajeInspeccionActual > 0 && inputKm) {
              inputKm.value = Math.round(kilometrajeInspeccionActual);
            }

            // 4. Seleccionar Tipología y BLOQUEARLA estrictamente (un vehículo no cambia de tipología)
            if (d.tipologia) {
              const selTip = document.getElementById('tipologia');
              if (selTip) {
                asignarValorSelect('tipologia', d.tipologia);
                await cambioTipologia();
                selTip.disabled = true;
                selTip.classList.add('bg-slate-100', 'cursor-not-allowed', 'text-slate-600');
                selTip.title = 'Tipología fija: vehículo previamente registrado. No es modificable.';
                const btnDesb = document.getElementById('btnDesbloquearTipologia');
                if (btnDesb) btnDesb.classList.add('hidden');
              }
            }

            // 5. Garantizar profundidades en ceros/vacías para nueva inspección
            document.getElementById('prof_ext').value = '';
            document.getElementById('prof_cent').value = '';
            document.getElementById('prof_int').value = '';
            document.getElementById('novedades').value = '';
            await cargarPosicionesInspeccionadasPlaca(placa);
            await verificarInspeccionAnterior();
          } else {
            const b = document.getElementById('badgePlacaVinculada');
            if (b) b.classList.add('hidden');
            desbloquearTipologia();
          }
        }
      } catch (err) {
        console.warn('Error al consultar perfil del vehículo:', err);
      }
    }

    function mostrarModalVehiculoYaInspeccionado(d) {
      const modal = document.getElementById('modalVehiculoYaInspeccionado');
      if (!modal) return;

      const placaVal = d.placa || (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const elPlaca = document.getElementById('popup_placa_vehiculo');
      if (elPlaca) elPlaca.textContent = placaVal || '-';

      const elFUlt = document.getElementById('popup_fecha_ultima_inspeccion');
      if (elFUlt) elFUlt.textContent = d.ultima_fecha_inspeccion || 'Previa registrada';

      const elFMin = document.getElementById('popup_fecha_permitida_inspeccion');
      if (elFMin) elFMin.textContent = d.fecha_minima_permitida || 'No determinada';

      const elDias = document.getElementById('popup_dias_restantes_texto');
      if (elDias) {
        if (d.inspeccion_hoy) {
          elDias.textContent = 'Este vehículo ya registra inspección en la fecha de hoy. Se encuentra en período de vigencia técnica.';
        } else if (d.dias_para_nueva_inspeccion > 0) {
          const reglaTxt = d.regla_frecuencia_texto ? ` (regla: ${d.regla_frecuencia_texto})` : '';
          elDias.textContent = `Faltan ${d.dias_para_nueva_inspeccion} días para habilitar la próxima inspección periódica${reglaTxt}. Habilitada a partir del ${d.fecha_minima_permitida || 'siguiente fecha'}.`;
        } else {
          elDias.textContent = `Inspección periódica vigente. Próxima inspección habilitada a partir del ${d.fecha_minima_permitida || 'siguiente ciclo'}.`;
        }
      }

      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    function cerrarModalVehiculoYaInspeccionado() {
      const modal = document.getElementById('modalVehiculoYaInspeccionado');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
    }

    async function copiarMarcaDisenoAnterior() {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      if (!placa) {
        mostrarToast('⚠️ Por favor ingresa primero la placa del vehículo', true);
        return;
      }

      let marca = cacheUltimaMarcaVehiculo || (typeof datosInspeccionAnterior !== 'undefined' ? datosInspeccionAnterior?.marca : '') || perfilVehiculoActual?.ultima_marca || '';
      let diseno = cacheUltimoDisenoVehiculo || (typeof datosInspeccionAnterior !== 'undefined' ? datosInspeccionAnterior?.diseno : '') || perfilVehiculoActual?.ultimo_diseno || '';
      let dimension = cacheUltimaDimensionVehiculo || (typeof datosInspeccionAnterior !== 'undefined' ? datosInspeccionAnterior?.dimension : '') || perfilVehiculoActual?.dimension || '';

      if (!marca || !diseno) {
        try {
          const resp = await fetch(`/api/inspecciones/ultima-marca-diseno?placa=${encodeURIComponent(placa)}`);
          if (resp.ok) {
            const d = await resp.json();
            if (d.encontrado) {
              marca = d.marca || marca;
              diseno = d.diseno || diseno;
              dimension = d.dimension || dimension;
              if (d.marca) cacheUltimaMarcaVehiculo = d.marca;
              if (d.diseno) cacheUltimoDisenoVehiculo = d.diseno;
              if (d.dimension) cacheUltimaDimensionVehiculo = d.dimension;
            }
          }
        } catch (err) {
          console.warn('Error consultando última marca y diseño:', err);
        }
      }

      if (!marca) {
        mostrarToast('ℹ️ No hay marca y diseño registrados en la inspección anterior de este vehículo.', false);
        return;
      }

      // 1. Asignar marca en select
      asignarValorSelect('marca', marca);
      // Disparar carga reactiva de modelos asociados a la marca
      await alCambiarMarcaMobile();

      // 2. Asignar diseño en select
      if (diseno) {
        asignarValorSelect('diseno', diseno);
      }

      // 3. Asignar dimensión si está disponible
      if (dimension && document.getElementById('dimension')) {
        asignarValorSelect('dimension', dimension);
      }

      // 4. Autocompletar profundidad inicial según catálogo
      await autoCompletarProfInicial();
      await actualizarPanelTallerPosicion(p);

      // 5. Toast de confirmación al usuario
      mostrarToast(`✅ Marca y diseño copiados: ${marca} ${diseno ? '- ' + diseno : ''}`, false);
    }

    function desbloquearTipologia() {
      const selTip = document.getElementById('tipologia');
      if (selTip) {
        selTip.disabled = false;
        selTip.classList.remove('bg-slate-100', 'cursor-not-allowed', 'text-slate-600');
        selTip.focus();
      }
      const btnDesb = document.getElementById('btnDesbloquearTipologia');
      if (btnDesb) btnDesb.classList.add('hidden');
      const b = document.getElementById('badgePlacaVinculada');
      if (b) b.classList.add('hidden');
    }

    // ==========================================
    // AUTOCOMPLETADO DE LLANTA POR CLIENTE
    // ==========================================
    let timerNumeroInternoDebounce = null;

    function onInputNumeroInternoDebounced() {
      clearTimeout(timerNumeroInternoDebounce);
      timerNumeroInternoDebounce = setTimeout(() => {
        const num = (document.getElementById('numero_interno')?.value || '').trim().toUpperCase();
        if (num && num !== 'SN') {
          consultarLlantaPorCliente(num);
        } else if (num === 'SN') {
          const bLlanta = document.getElementById('badgeLlantaCliente');
          if (bLlanta) bLlanta.classList.add('hidden');
        }
      }, 350);
    }

    async function consultarLlantaPorCliente(numInterno) {
      const num = (numInterno || document.getElementById('numero_interno')?.value || '').trim().toUpperCase();
      if (!num || num === 'SN') {
        const bLlanta = document.getElementById('badgeLlantaCliente');
        if (bLlanta) bLlanta.classList.add('hidden');
        return;
      }

      const cli = (document.getElementById('cliente')?.value || '').trim();
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();

      try {
        let url = `/api/llanta-por-cliente?numero_interno=${encodeURIComponent(num)}`;
        if (cli && cli !== '__nuevo__') url += `&cliente=${encodeURIComponent(cli)}`;
        if (placa) url += `&placa=${encodeURIComponent(placa)}`;

        const res = await fetch(url);
        if (res.ok) {
          const d = await res.json();
          const numActual = (document.getElementById('numero_interno')?.value || '').trim().toUpperCase();
          if (numActual !== num) return;

          if (d.encontrado && d.datos) {
            const lt = d.datos;
            const bLlanta = document.getElementById('badgeLlantaCliente');
            if (bLlanta) bLlanta.classList.remove('hidden');

            const bHist = document.getElementById('badgeHistorialPrevia');
            if (bHist) {
              bHist.classList.remove('hidden');
              bHist.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i>Llanta de ${lt.cliente || 'Flota'} (Pos ${lt.ult_posicion || 'ant'}${lt.ult_prof_min ? ' • ' + lt.ult_prof_min.toFixed(1) + ' mm' : ''})`;
            }

            // Precargar especificaciones técnicas de la llanta
            if (lt.marca) {
              asignarValorSelect('marca', lt.marca);
              await alCambiarMarcaMobile();
            }
            if (lt.diseno) asignarValorSelect('diseno', lt.diseno);
            if (lt.dimension) {
              asignarValorSelect('dimension', lt.dimension);
              if (!dimensionPredeterminadaVehiculo || posicionesInspeccionadasPlaca.size === 0) {
                dimensionPredeterminadaVehiculo = lt.dimension;
              }
            }
            const vLt = String(lt.vida || 'Original').trim();
            const esReenLt = vLt.toLowerCase().includes('reen') || Boolean(lt.banda_reen);
            asignarValorSelect('vida', esReenLt ? 'Reencauche' : 'Original');
            if (lt.banda_reen && esReenLt) {
              asignarValorSelect('banda_reen', lt.banda_reen);
            }
            validarVida();
            if (lt.prof_inicial && (!document.getElementById('prof_inicial').value || document.getElementById('prof_inicial').value === '0')) {
              document.getElementById('prof_inicial').value = lt.prof_inicial;
            }
            await autoCompletarProfInicial();
      await actualizarPanelTallerPosicion(p);
            if (lt.precio && (!document.getElementById('precio').value || document.getElementById('precio').value === '0')) {
              document.getElementById('precio').value = lt.precio;
            }
            if (lt.km_montaje && (!document.getElementById('km_montaje').value || document.getElementById('km_montaje').value === '0')) {
              document.getElementById('km_montaje').value = lt.km_montaje;
            }
          } else {
            const bLlanta = document.getElementById('badgeLlantaCliente');
            if (bLlanta) bLlanta.classList.add('hidden');
          }
        }
      } catch (err) {
        console.warn('Error al consultar llanta por cliente:', err);
      }
    }

    async function verificarInspeccionAnterior() {
      const token = idInspeccionActiva;
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const pos = parseInt(document.getElementById('posicion')?.value) || 1;
      if (!placa) return;

      cargarPosicionesInspeccionadasPlaca(placa);

      try {
        const res = await fetch(`/api/inspeccion-anterior?placa=${encodeURIComponent(placa)}&posicion=${pos}`);
        if (res.ok) {
          if (token !== idInspeccionActiva) return;
          const placaFin = (document.getElementById('placa')?.value || '').trim().toUpperCase();
          if (!placaFin || placaFin !== placa) return;

          const d = await res.json();
          if (token !== idInspeccionActiva) return;

          // Si esta posición ya fue inspeccionada en la sesión actual
          const yaInspeccionadaHoy = posicionesInspeccionadasPlaca.has(pos);

          if (d.encontrado && d.datos) {
            datosInspeccionAnterior = d.datos;
            if (d.datos.marca) cacheUltimaMarcaVehiculo = d.datos.marca;
            if (d.datos.diseno) cacheUltimoDisenoVehiculo = d.datos.diseno;
            if (d.datos.dimension) cacheUltimaDimensionVehiculo = d.datos.dimension;
            const badgeHist = document.getElementById('badgeHistorialPrevia');
            if (badgeHist) {
              badgeHist.classList.remove('hidden');
              badgeHist.innerHTML = '<i class="fa-solid fa-clock-rotate-left mr-1"></i>Previa: ' + (d.datos.numero_interno || 'S/N');
            }

            if (yaInspeccionadaHoy) {
              // Cargar datos actuales de la inspección de hoy para esta posición
              if (d.datos.numero_interno) {
                const inpNum = document.getElementById('numero_interno');
                if (inpNum) inpNum.value = d.datos.numero_interno;
              }
              if (d.datos.marca) {
                asignarValorSelect('marca', d.datos.marca);
                await alCambiarMarcaMobile();
              }
              if (d.datos.diseno) {
                asignarValorSelect('diseno', d.datos.diseno);
              }
              if (d.datos.dimension) {
                asignarValorSelect('dimension', d.datos.dimension);
              }
              const vDato = String(d.datos.vida || 'Original').trim();
              const esReenDato = vDato.toLowerCase().includes('reen') || Boolean(d.datos.banda_reen);
              asignarValorSelect('vida', esReenDato ? 'Reencauche' : 'Original');
              if (d.datos.banda_reen && esReenDato) {
                asignarValorSelect('banda_reen', d.datos.banda_reen);
              }
              if (d.datos.precio) {
                const inpPrecio = document.getElementById('precio');
                if (inpPrecio) inpPrecio.value = d.datos.precio;
              }
              if (d.datos.km_montaje) {
                const inpKmMont = document.getElementById('km_montaje');
                if (inpKmMont) inpKmMont.value = d.datos.km_montaje;
              }
              if (d.datos.kilometraje && parseFloat(d.datos.kilometraje) > 0) {
                kilometrajeInspeccionActual = parseFloat(d.datos.kilometraje);
                const inpKm = document.getElementById('kilometraje');
                if (inpKm) inpKm.value = Math.round(kilometrajeInspeccionActual);
              } else if (kilometrajeInspeccionActual > 0) {
                const inpKm = document.getElementById('kilometraje');
                if (inpKm && (!inpKm.value || inpKm.value === '0')) {
                  inpKm.value = Math.round(kilometrajeInspeccionActual);
                }
              }
              validarVida();
              await autoCompletarProfInicial();
      await actualizarPanelTallerPosicion(p);
              if (d.datos.prof_inicial && (!document.getElementById('prof_inicial').value || document.getElementById('prof_inicial').value === '0')) {
                document.getElementById('prof_inicial').value = d.datos.prof_inicial;
              }
              if (d.datos.prof_ext !== undefined && d.datos.prof_ext !== null) document.getElementById('prof_ext').value = d.datos.prof_ext;
              if (d.datos.prof_cent !== undefined && d.datos.prof_cent !== null) document.getElementById('prof_cent').value = d.datos.prof_cent;
              if (d.datos.prof_int !== undefined && d.datos.prof_int !== null) document.getElementById('prof_int').value = d.datos.prof_int;
              if (d.datos.psi) document.getElementById('psi').value = d.datos.psi;
              if (d.datos.novedades) document.getElementById('novedades').value = d.datos.novedades;
            } else {
              // Precargar automáticamente todas las Especificaciones de la Llanta con las que se registró en la anterior inspección
              // 1. Número Interno
              const inpNum = document.getElementById('numero_interno');
              if (inpNum) inpNum.value = d.datos.numero_interno || '';

              // 2. Marca y Diseños asociados
              if (d.datos.marca) {
                asignarValorSelect('marca', d.datos.marca);
                await alCambiarMarcaMobile();
              }

              // 3. Diseño
              if (d.datos.diseno) {
                asignarValorSelect('diseno', d.datos.diseno);
              }

              // 4. Dimensión: Prevalecer la dimensión fijada en la primera llanta para este vehículo,
              // o cargar la dimensión histórica y fijarla como predeterminada del vehículo.
              const dimParaCargar = dimensionPredeterminadaVehiculo || d.datos.dimension || '295/80R22.5';
              if (dimParaCargar) {
                asignarValorSelect('dimension', dimParaCargar);
                if (!dimensionPredeterminadaVehiculo && d.datos.dimension) {
                  dimensionPredeterminadaVehiculo = d.datos.dimension;
                }
              }

              // 5. Profundidad Inicial (asignación previa como fallback, pero recalculada inmediatamente con catálogo)
              const inpProfIni = document.getElementById('prof_inicial');
              if (inpProfIni) {
                inpProfIni.value = (d.datos.prof_inicial !== null && d.datos.prof_inicial !== undefined && d.datos.prof_inicial !== '') ? d.datos.prof_inicial : '';
              }

              // 6. Precio y Km Montaje
              const inpPrecio = document.getElementById('precio');
              if (inpPrecio) {
                inpPrecio.value = (d.datos.precio !== null && d.datos.precio !== undefined && d.datos.precio !== '') ? d.datos.precio : '';
              }
              const inpKmMont = document.getElementById('km_montaje');
              if (inpKmMont) {
                inpKmMont.value = (d.datos.km_montaje !== null && d.datos.km_montaje !== undefined && d.datos.km_montaje !== '') ? d.datos.km_montaje : '';
              }

              // 7. Vida / Condición y Banda de Reencauche (respetando restricción de eje direccional)
              const esDir = esPosicionDireccionalActual(pos);
              const boxBanda = document.getElementById('box_banda');
              const selBanda = document.getElementById('banda_reen');

              if (esDir) {
                asignarValorSelect('vida', 'Original');
                if (selBanda) selBanda.value = '';
                if (boxBanda) boxBanda.classList.add('hidden');
              } else {
                const vDatoPos = String(d.datos.vida || 'Original').trim();
                const esReenPos = vDatoPos.toLowerCase().includes('reen') || Boolean(d.datos.banda_reen);
                asignarValorSelect('vida', esReenPos ? 'Reencauche' : 'Original');
                if (esReenPos) {
                  if (boxBanda) boxBanda.classList.remove('hidden');
                  if (d.datos.banda_reen) {
                    asignarValorSelect('banda_reen', d.datos.banda_reen);
                  }
                } else {
                  if (selBanda) selBanda.value = '';
                  if (boxBanda) boxBanda.classList.add('hidden');
                }
              }

              aplicarRestriccionEjeDireccional(pos);
              validarVida();

              // RECALCULAR PROFUNDIDAD INICIAL DESDE EL CATÁLOGO SEGÚN MARCA Y MODELO/DISEÑO
              await autoCompletarProfInicial();
      await actualizarPanelTallerPosicion(p);

              const bCli = document.getElementById('badgeLlantaCliente');
              if (bCli) {
                if (d.datos.numero_interno) {
                  bCli.classList.remove('hidden');
                } else {
                  bCli.classList.add('hidden');
                }
              }
              if (kilometrajeInspeccionActual > 0) {
                const inpKm = document.getElementById('kilometraje');
                if (inpKm && (!inpKm.value || inpKm.value === '0')) {
                  inpKm.value = Math.round(kilometrajeInspeccionActual);
                }
              }
            }
          } else {
            // Posición sin registro previo
            document.getElementById('badgeHistorialPrevia')?.classList.add('hidden');
            document.getElementById('badgeLlantaCliente')?.classList.add('hidden');
            datosInspeccionAnterior = null;

            if (kilometrajeInspeccionActual > 0) {
              const inpKm = document.getElementById('kilometraje');
              if (inpKm && (!inpKm.value || inpKm.value === '0')) {
                inpKm.value = Math.round(kilometrajeInspeccionActual);
              }
            }

            // Si aún no se ha inspeccionado hoy, limpiar las especificaciones para ingresar llanta nueva
            if (!yaInspeccionadaHoy) {
              const inpNum = document.getElementById('numero_interno');
              if (inpNum) inpNum.value = '';

              const selMarca = document.getElementById('marca');
              if (selMarca) {
                selMarca.value = '';
                if (selMarca.options && selMarca.options.length > 0) selMarca.selectedIndex = 0;
              }

              const selDis = document.getElementById('diseno');
              if (selDis) {
                selDis.innerHTML = '<option value="" disabled selected class="text-slate-400 font-normal">ej. X Multi Z (Seleccionar diseño)</option>';
                selDis.value = '';
              }

              const selDim = document.getElementById('dimension');
              const dimParaCargar = dimensionPredeterminadaVehiculo || '295/80R22.5';
              if (selDim) {
                asignarValorSelect('dimension', dimParaCargar);
              }

              const selVida = document.getElementById('vida');
              if (selVida) selVida.value = 'Original';

              const selBanda = document.getElementById('banda_reen');
              if (selBanda) selBanda.value = '';
              const boxBanda = document.getElementById('box_banda');
              if (boxBanda) boxBanda.classList.add('hidden');

              const pIni = document.getElementById('prof_inicial');
              if (pIni) pIni.value = '';

              const elPrecio = document.getElementById('precio');
              if (elPrecio) elPrecio.value = '';

              const elKm = document.getElementById('km_montaje');
              if (elKm) elKm.value = '';

              aplicarRestriccionEjeDireccional(pos);
              validarVida();
            }
          }

          // REQUERIMIENTO: Profundidades SIEMPRE en ceros / vacías para la nueva inspección
          if (!yaInspeccionadaHoy) {
            document.getElementById('prof_ext').value = '';
            document.getElementById('prof_cent').value = '';
            document.getElementById('prof_int').value = '';
            document.getElementById('psi').value = '100';
            document.getElementById('novedades').value = '';
            const panelRetiro = document.getElementById('panelAlertaRetiro');
            if (panelRetiro) panelRetiro.classList.add('hidden');
          }
        }
      } catch (e) {
        console.warn('Error al verificar inspección anterior:', e);
      }
    }

    async function cargarPosicionesInspeccionadasPlaca(placa) {
      const token = idInspeccionActiva;
      const placaActual = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      if (!placa || !placaActual || placa !== placaActual) return;
      const fActual = (document.getElementById('fecha')?.value || '').trim();

      try {
        let url = `/api/posiciones-inspeccionadas?placa=${encodeURIComponent(placa)}`;
        if (fActual) {
          url += `&fecha=${encodeURIComponent(fActual)}`;
        }
        const res = await fetch(url);
        if (res.ok) {
          if (token !== idInspeccionActiva) return;
          const placaFin = (document.getElementById('placa')?.value || '').trim().toUpperCase();
          if (!placaFin || placaFin !== placa) return;

          const d = await res.json();
          if (token !== idInspeccionActiva) return;

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
      const pos = parseInt(document.getElementById('posicion')?.value) || 1;
      const selVida = document.getElementById('vida');
      if (selVida) {
        if (!selVida.value || (selVida.value !== 'Original' && selVida.value !== 'Reencauche')) {
          selVida.value = 'Original';
        }
        if (selVida.value === 'Reencauche' && esPosicionDireccionalActual(pos)) {
          selVida.value = 'Original';
          mostrarToast('⛔ En eje direccional solo se permite condición Original por seguridad vial.', true);
        }
      }
      const vida = selVida ? selVida.value : 'Original';
      const boxBanda = document.getElementById('box_banda');
      if (boxBanda) {
        if (vida === 'Reencauche') {
          boxBanda.classList.remove('hidden');
          poblarSelect('banda_reen', '/api/valores-campo?campo=banda_reen', 'ej. BDM Bandag (Seleccionar banda)');
        } else {
          boxBanda.classList.add('hidden');
        }
      }
    }

    async function alCambiarMarcaMobile() {
      const m = (document.getElementById('marca')?.value || '').trim();
      if (m && m !== '__nuevo__' && !m.includes('(Seleccionar')) {
        await poblarSelect('diseno', `/api/valores-campo?campo=diseno&marca=${encodeURIComponent(m)}`, 'ej. X Multi Z (Seleccionar diseño)');
      }
      await autoCompletarProfInicial();
      await actualizarPanelTallerPosicion(p);
    }

    function alCambiarDimensionMobile() {
      const selDim = document.getElementById('dimension');
      const val = selDim ? selDim.value.trim() : '';
      if (val && val !== '__nuevo__') {
        if (!dimensionPredeterminadaVehiculo || posicionesInspeccionadasPlaca.size === 0) {
          dimensionPredeterminadaVehiculo = val;
        }
      }
    }

    async function autoCompletarProfInicial() {
      const m = (document.getElementById('marca')?.value || '').trim();
      const d = (document.getElementById('diseno')?.value || '').trim();
      const dim = (document.getElementById('dimension')?.value || '').trim();
      const vida = document.getElementById('vida')?.value || 'Original';
      const banda = (document.getElementById('banda_reen')?.value || '').trim();

      const mValida = m && m !== '__nuevo__' && !m.includes('(Seleccionar');
      const dValida = d && d !== '__nuevo__' && !d.includes('(Seleccionar');
      const bValida = banda && banda !== '__nuevo__' && !banda.includes('(Seleccionar');

      // Si no hay diseño/modelo ni banda válida seleccionada, no consultar
      if (!dValida && !bValida) return;

      try {
        let url = `/api/profundidad-inicial?marca=${encodeURIComponent(mValida ? m : '')}&diseno=${encodeURIComponent(dValida ? d : '')}&dimension=${encodeURIComponent(dim)}&vida=${encodeURIComponent(vida)}`;
        if (bValida) {
          url += `&banda=${encodeURIComponent(banda)}`;
        }
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (data && data.prof_inicial > 0) {
            const inp = document.getElementById('prof_inicial');
            if (inp) {
              inp.value = data.prof_inicial;
            }
          }
        }
      } catch (err) {
        console.warn('Error al autocompletar prof_inicial:', err);
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

    async function seleccionarLlantaCatalogo(m) {
      asignarValorSelect('marca', m.marca);
      await alCambiarMarcaMobile();
      asignarValorSelect('diseno', m.diseno);
      asignarValorSelect('dimension', m.dimension);
      if (m.dimension && (!dimensionPredeterminadaVehiculo || posicionesInspeccionadasPlaca.size === 0)) {
        dimensionPredeterminadaVehiculo = m.dimension;
      }
      document.getElementById('prof_inicial').value = m.prof_inicial;
      if (m.tipo_llanta === 'Reencauche') {
        document.getElementById('vida').value = 'Reencauche';
        validarVida();
      }
      document.getElementById('boxSugerenciasCatalogo').classList.add('hidden');
      mostrarToast(`Modelo seleccionado: ${m.marca} ${m.diseno}`);
    }

    function limpiarSoloMedicionesCaptura() {
      const pExt = document.getElementById('prof_ext'); if (pExt) pExt.value = '';
      const pCen = document.getElementById('prof_cent'); if (pCen) pCen.value = '';
      const pInt = document.getElementById('prof_int'); if (pInt) pInt.value = '';
      const psi = document.getElementById('psi'); if (psi) psi.value = '100';
      const nov = document.getElementById('novedades'); if (nov) nov.value = '';
      const panelRetiro = document.getElementById('panelAlertaRetiro');
      if (panelRetiro) panelRetiro.classList.add('hidden');
      const alertaRetiro = document.getElementById('alertaRetiroInmediato');
      if (alertaRetiro) alertaRetiro.classList.add('hidden');
      if (typeof quitarFotoNovedad === 'function') quitarFotoNovedad();
      limpiarTodosErroresFormulario();
    }

    function limpiarMediciones(mostrarAviso = false) {
      // 1. Limpiar especificaciones de la llanta en la posición actual
      const inpNum = document.getElementById('numero_interno');
      if (inpNum) inpNum.value = '';

      const selMarca = document.getElementById('marca');
      if (selMarca) {
        selMarca.value = '';
        if (selMarca.options && selMarca.options.length > 0) selMarca.selectedIndex = 0;
      }

      const selDis = document.getElementById('diseno');
      if (selDis) {
        selDis.innerHTML = '<option value="" disabled selected class="text-slate-400 font-normal">ej. X Multi Z (Seleccionar diseño)</option>';
        selDis.value = '';
      }

      const selDim = document.getElementById('dimension');
      const dimDefault = dimensionPredeterminadaVehiculo || '295/80R22.5';
      if (selDim) {
        asignarValorSelect('dimension', dimDefault);
      }

      const selVida = document.getElementById('vida');
      if (selVida) {
        selVida.value = 'Original';
        validarVida();
      }

      const pIni = document.getElementById('prof_inicial');
      if (pIni) pIni.value = '';

      const selBanda = document.getElementById('banda_reen');
      if (selBanda) selBanda.value = '';
      const boxBanda = document.getElementById('box_banda');
      if (boxBanda) boxBanda.classList.add('hidden');

      const elPrecio = document.getElementById('precio');
      if (elPrecio) elPrecio.value = '';

      const elKm = document.getElementById('km_montaje');
      if (elKm) elKm.value = '';

      // 2. Limpiar mediciones de profundidad y calibración
      const pExt = document.getElementById('prof_ext'); if (pExt) pExt.value = '';
      const pCen = document.getElementById('prof_cent'); if (pCen) pCen.value = '';
      const pInt = document.getElementById('prof_int'); if (pInt) pInt.value = '';
      const psi = document.getElementById('psi'); if (psi) psi.value = '100';
      const nov = document.getElementById('novedades'); if (nov) nov.value = '';

      // 3. Ocultar badges de reconocimiento, historial y alertas de retiro
      const bCli = document.getElementById('badgeLlantaCliente');
      if (bCli) bCli.classList.add('hidden');

      const bHist = document.getElementById('badgeHistorialPrevia');
      if (bHist) bHist.classList.add('hidden');

      const bSug = document.getElementById('boxSugerenciasCatalogo');
      if (bSug) bSug.classList.add('hidden');

      const alertaRetiro = document.getElementById('alertaRetiroInmediato');
      if (alertaRetiro) alertaRetiro.classList.add('hidden');

      datosInspeccionAnterior = null;

      const posActual = parseInt(document.getElementById('posicion')?.value) || 1;
      aplicarRestriccionEjeDireccional(posActual);

      quitarFotoNovedad();
      limpiarTodosErroresFormulario();

      // 4. Dejar listo para ingresar datos (enfocar campo No. Interno)
      if (inpNum) {
        try {
          inpNum.focus();
        } catch (e) {}
      }

      if (mostrarAviso) {
        mostrarToast('🧹 Datos de la llanta limpiados. Listo para ingresar datos.');
      }
    }

    function abrirModalConfirmarFinalizar() {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const total = (listaPosicionesActual && listaPosicionesActual.length > 0) ? listaPosicionesActual.length : 10;
      const auditadas = Array.from(posicionesInspeccionadasPlaca).filter(p => listaPosicionesActual.includes(p)).length;
      const pendientes = listaPosicionesActual.filter(p => !posicionesInspeccionadasPlaca.has(p));

      const lblPlaca = document.getElementById('lblModalFinalizarPlaca');
      if (lblPlaca) lblPlaca.textContent = placa || '(Sin placa definida)';

      const lblProgreso = document.getElementById('lblModalFinalizarProgreso');
      if (lblProgreso) lblProgreso.textContent = `${auditadas} de ${total}`;

      const boxPend = document.getElementById('boxModalFinalizarPendientes');
      const txtPend = document.getElementById('txtModalFinalizarPendientes');
      const boxComp = document.getElementById('boxModalFinalizarCompleto');

      if (pendientes.length > 0) {
        if (boxPend) boxPend.classList.remove('hidden');
        if (boxComp) boxComp.classList.add('hidden');
        if (txtPend) {
          txtPend.textContent = `Quedan ${pendientes.length} llanta(s) sin auditar: Posición(es) [ ${pendientes.join(', ')} ].`;
        }
      } else {
        if (boxPend) boxPend.classList.add('hidden');
        if (boxComp) boxComp.classList.remove('hidden');
      }

      const modal = document.getElementById('modalConfirmarFinalizar');
      if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      }
    }

    function cerrarModalConfirmarFinalizar() {
      const modal = document.getElementById('modalConfirmarFinalizar');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
    }

    function confirmarFinalizarInspeccion() {
      const placa = (document.getElementById('placa')?.value || '').trim();
      if (!placa && posicionesInspeccionadasPlaca.size === 0) {
        if (confirm('No hay ningún vehículo en inspección activo. ¿Deseas limpiar todos los campos del formulario?')) {
          limpiarTodoParaNuevaInspeccion();
          mostrarToast('Formulario en blanco.');
        }
        return;
      }
      abrirModalConfirmarFinalizar();
    }

    function ejecutarFinalizacionInspeccion() {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const fechaInsp = (document.getElementById('fecha')?.value || '').trim();
      const cli = document.getElementById('cliente')?.value.trim() || 'Flota';
      const tip = document.getElementById('tipologia')?.value || 'Tipología';
      const auditadas = posicionesInspeccionadasPlaca.size;

      cerrarModalConfirmarFinalizar();

      if (placa && auditadas > 0) {
        // Mostrar el mismo recuadro que cuando se inspeccionaron todas las llantas para generar PDF y compartir por WhatsApp
        abrirModalInformePdf(placa, fechaInsp, cli, tip);
        mostrarToast(`🏁 Inspección de ${placa} finalizada (${auditadas} llanta(s) registradas).`);
      } else {
        mostrarToast(`🏁 Inspección finalizada. Formulario y chasis en blanco.`);
      }

      // Reiniciar completamente el diagrama de chasis y los campos del formulario para la nueva inspección
      limpiarTodoParaNuevaInspeccion();
    }

    function limpiarTodoParaNuevaInspeccion() {
      // Invalida cualquier petición asíncrona en vuelo anterior para que no repinte el chasis
      idInspeccionActiva++;

      // 1. Limpiar campos de identificación del vehículo y errores visuales
      ['cliente', 'subcliente', 'placa', 'kilometraje', 'prof_ext', 'prof_cent', 'prof_int', 'psi', 'marca', 'diseno', 'dimension'].forEach(id => {
        if (typeof limpiarErrorCampo === 'function') limpiarErrorCampo(id);
      });
      const inpPlaca = document.getElementById('placa');
      if (inpPlaca) inpPlaca.value = '';
      const inpKm = document.getElementById('kilometraje');
      if (inpKm) inpKm.value = '';
      ultimaPlacaConsultadaPerfil = '';
      desbloquearTipologia();
      const bPlaca = document.getElementById('badgePlacaVinculada');
      if (bPlaca) bPlaca.classList.add('hidden');
      const bLlanta = document.getElementById('badgeLlantaCliente');
      if (bLlanta) bLlanta.classList.add('hidden');

      // Limpiar cliente y subcliente si no están fijados por rol de usuario
      if (typeof usuarioActual === 'undefined' || !usuarioActual || esUsuarioAdmin() || !usuarioActual.cliente_asignado) {
        const inpCli = document.getElementById('cliente');
        if (inpCli && !inpCli.readOnly && !inpCli.disabled) inpCli.value = '';
        const inpSub = document.getElementById('subcliente');
        if (inpSub) inpSub.value = '';
      } else {
        configurarClientesUsuarioEnInspeccion();
      }

      // Restablecer fecha a la fecha actual local
      const inpFecha = document.getElementById('fecha');
      if (inpFecha) inpFecha.value = fechaLocalISO();

      // 2. Limpiar especificaciones de la llanta
      const camposEspec = ['numero_interno', 'marca', 'diseno', 'dimension', 'prof_inicial', 'banda_reen', 'precio', 'km_montaje'];
      camposEspec.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      dimensionPredeterminadaVehiculo = '';
      kilometrajeInspeccionActual = null;
      perfilVehiculoActual = null;
      ultimaPlacaPopupAlerta = '';
      cacheUltimaMarcaVehiculo = '';
      cacheUltimoDisenoVehiculo = '';
      cacheUltimaDimensionVehiculo = '';
      const selDim = document.getElementById('dimension');
      if (selDim) selDim.value = '295/80R22.5';
      const selDis = document.getElementById('diseno');
      if (selDis) selDis.innerHTML = '<option value="" disabled selected class="text-slate-400 font-normal">ej. X Multi Z (Seleccionar diseño)</option>';
      const selVida = document.getElementById('vida');
      if (selVida) selVida.value = 'Original';
      validarVida();

      const boxSugerencias = document.getElementById('boxSugerenciasCatalogo');
      if (boxSugerencias) boxSugerencias.classList.add('hidden');
      const badgeHistorial = document.getElementById('badgeHistorialPrevia');
      if (badgeHistorial) badgeHistorial.classList.add('hidden');

      // 3. Limpiar mediciones completas (incluyendo PSI en 100 y novedades)
      limpiarMediciones();

      // 4. Limpiar sets de seguimiento del vehículo actual (100% vacíos)
      posicionesInspeccionadasPlaca = new Set();
      posicionesConNovedadPlaca = new Map();

      // 5. Restablecer botón sin repuesto
      ruedaSinRepuestoMarcada = false;
      const btnSinRep = document.getElementById('btnSinRepuesto');
      const txtSinRep = document.getElementById('txtBtnSinRepuesto');
      if (txtSinRep) txtSinRep.textContent = 'Marcar: Vehículo sin llanta de repuesto';
      if (btnSinRep) {
        btnSinRep.classList.add('bg-slate-100', 'text-slate-600');
        btnSinRep.classList.remove('bg-amber-100', 'text-amber-800', 'border-amber-300');
      }

      // 6. Restablecer posición actual al inicio del recorrido físico sin disparar verificarInspeccionAnterior
      const primerPos = (listaPosicionesActual && listaPosicionesActual.length > 0) ? listaPosicionesActual[0] : 1;
      const inpPos = document.getElementById('posicion');
      if (inpPos) inpPos.value = primerPos;
      const lblPos = document.getElementById('lblPosActualForm');
      if (lblPos) lblPos.textContent = primerPos;
      const lblPosEsp = document.getElementById('lblPosActualEspecificaciones');
      if (lblPosEsp) lblPosEsp.textContent = primerPos;

      // Sincronizar botones accesibles
      document.querySelectorAll('.pos-btn').forEach(b => b.classList.remove('active'));
      const bAct = document.getElementById(`btn_pos_${primerPos}`);
      if (bAct) bAct.classList.add('active');
      actualizarBarraPosicionMobile(primerPos);

      // 7. Renderizar chasis y selectores completamente limpios (sin ningún color verde ni alertas)
      if (esquemaTipologiaCache) {
        renderizarChasisEjes(esquemaTipologiaCache, listaPosicionesActual);
        renderizarBotonesPosicion(listaPosicionesActual, esquemaTipologiaCache);
        renderizarCarruselLlantasMobile();
      }

      // 8. Ocultar banner de completado
      const bannerComp = document.getElementById('bannerInspeccionCompletaPatio');
      if (bannerComp) bannerComp.classList.add('hidden');

      // 9. Foco en placa y confirmación visual
      if (inpPlaca) inpPlaca.focus();
      mostrarToast('🧹 Todo limpio. Formulario y chasis listos para una nueva inspección.');
    }

    function limpiarFormulario(total = true) {
      limpiarTodoParaNuevaInspeccion();
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

    function recalcularLlantasTipologia() {
      const eDir = Math.max(0, parseInt(document.getElementById('tip_ejes_dir_cant')?.value) || 0);
      const tDir = document.getElementById('tip_ejes_dir_tipo')?.value || 'sencilla';
      const llantasPorEjeDir = (tDir === 'dual') ? 4 : 2;
      const totalDir = eDir * llantasPorEjeDir;

      const eTrac = Math.max(0, parseInt(document.getElementById('tip_ejes_trac_cant')?.value) || 0);
      const tTrac = document.getElementById('tip_ejes_trac_tipo')?.value || 'dual';
      const llantasPorEjeTrac = (tTrac === 'sencilla') ? 2 : 4;
      const totalTrac = eTrac * llantasPorEjeTrac;

      const eLib = Math.max(0, parseInt(document.getElementById('tip_ejes_libre_cant')?.value) || 0);
      const tLib = document.getElementById('tip_ejes_libre_tipo')?.value || 'dual';
      const llantasPorEjeLib = (tLib === 'sencilla') ? 2 : 4;
      const totalLib = eLib * llantasPorEjeLib;

      const eRep = Math.max(0, parseInt(document.getElementById('tip_ejes_repuesto_cant')?.value) || 0);

      const totalLlantas = totalDir + totalTrac + totalLib + eRep;

      // Generar desglose descriptivo
      const partes = [];
      if (eDir > 0) {
        partes.push(`${eDir} Dir (${totalDir} llantas)`);
      }
      if (eTrac > 0) {
        const modoTrac = tTrac === 'dual' ? 'Dual' : 'Senc';
        partes.push(`${eTrac} Trac ${modoTrac} (${totalTrac} llantas)`);
      }
      if (eLib > 0) {
        const modoLib = tLib === 'dual' ? 'Dual' : 'Senc';
        partes.push(`${eLib} Libre ${modoLib} (${totalLib} llantas)`);
      }
      if (eRep > 0) {
        partes.push(`${eRep} Repuesto${eRep > 1 ? 's' : ''}`);
      }

      const txtDesglose = partes.length > 0 ? partes.join(' + ') : 'Sin ejes configurados (0 llantas)';
      const elDesglose = document.getElementById('tip_desglose_calculo');
      const elTotal = document.getElementById('tip_total_calculado');
      if (elDesglose) elDesglose.textContent = txtDesglose;
      if (elTotal) elTotal.textContent = totalLlantas;
      return totalLlantas;
    }

    function abrirModalTipologia() {
      tipologiaEditando = null;
      const elTit = document.getElementById('tituloModalTipologia');
      if (elTit) elTit.textContent = 'Crear Tipología de Vehículo';
      const elBtn = document.getElementById('btnGuardarTipologiaTexto');
      if (elBtn) elBtn.textContent = 'Guardar Tipología';
      const nomInput = document.getElementById('nueva_tip_nombre');
      if (nomInput) nomInput.value = '';
      const descInput = document.getElementById('nueva_tip_desc');
      if (descInput) descInput.value = '';
      document.getElementById('tip_ejes_dir_cant').value = '1';
      document.getElementById('tip_ejes_dir_tipo').value = 'sencilla';
      document.getElementById('tip_ejes_trac_cant').value = '2';
      document.getElementById('tip_ejes_trac_tipo').value = 'dual';
      document.getElementById('tip_ejes_libre_cant').value = '0';
      document.getElementById('tip_ejes_libre_tipo').value = 'dual';
      document.getElementById('tip_ejes_repuesto_cant').value = '0';
      document.getElementById('modalTipologia').classList.remove('hidden');
      document.getElementById('modalTipologia').classList.add('flex');
      recalcularLlantasTipologia();
    }

    function abrirModalEditarTipologia(tipologiaEncoded) {
      const t = JSON.parse(decodeURIComponent(tipologiaEncoded));
      tipologiaEditando = t.nombre;
      const elTit = document.getElementById('tituloModalTipologia');
      if (elTit) elTit.textContent = `Editar Tipología: ${t.nombre}`;
      const elBtn = document.getElementById('btnGuardarTipologiaTexto');
      if (elBtn) elBtn.textContent = 'Guardar Cambios';
      const nomInput = document.getElementById('nueva_tip_nombre');
      if (nomInput) nomInput.value = t.nombre;
      const descInput = document.getElementById('nueva_tip_desc');
      if (descInput) descInput.value = t.descripcion || '';

      let eDir = 0, tDir = 'sencilla', eTrac = 0, tTrac = 'dual', eLib = 0, tLib = 'dual', eRep = 0;
      if (t.esquema && Array.isArray(t.esquema) && t.esquema.length > 0) {
        t.esquema.forEach(eje => {
          const tipo = (eje.tipo || '').toLowerCase();
          const cantPos = (eje.posiciones || []).length;
          if (tipo === 'direccional') {
            eDir++;
            if (cantPos >= 4) tDir = 'dual';
          } else if (tipo === 'traccion') {
            eTrac++;
            if (cantPos <= 2) tTrac = 'sencilla';
          } else if (tipo === 'remolque' || tipo === 'libre') {
            eLib++;
            if (cantPos <= 2) tLib = 'sencilla';
          } else if (tipo === 'repuesto') {
            eRep += cantPos;
          }
        });
      } else {
        if (t.cant_llantas === 6) { eDir = 1; tDir = 'sencilla'; eTrac = 1; tTrac = 'dual'; }
        else if (t.cant_llantas === 10) { eDir = 1; tDir = 'sencilla'; eTrac = 2; tTrac = 'dual'; }
        else if (t.cant_llantas === 12) { eDir = 2; tDir = 'sencilla'; eTrac = 2; tTrac = 'dual'; }
        else { eDir = 1; tDir = 'sencilla'; eTrac = Math.max(0, Math.floor((t.cant_llantas - 2) / 4)); tTrac = 'dual'; }
      }

      document.getElementById('tip_ejes_dir_cant').value = eDir;
      document.getElementById('tip_ejes_dir_tipo').value = tDir;
      document.getElementById('tip_ejes_trac_cant').value = eTrac;
      document.getElementById('tip_ejes_trac_tipo').value = tTrac;
      document.getElementById('tip_ejes_libre_cant').value = eLib;
      document.getElementById('tip_ejes_libre_tipo').value = tLib;
      document.getElementById('tip_ejes_repuesto_cant').value = eRep;
      recalcularLlantasTipologia();

      document.getElementById('modalTipologia').classList.remove('hidden');
      document.getElementById('modalTipologia').classList.add('flex');
    }

    function cerrarModalTipologia() {
      tipologiaEditando = null;
      document.getElementById('modalTipologia').classList.add('hidden');
      document.getElementById('modalTipologia').classList.remove('flex');
    }

    async function guardarNuevaTipologia() {
      const nomInput = document.getElementById('nueva_tip_nombre');
      const nom = nomInput ? nomInput.value.trim().toUpperCase() : '';
      const descInput = document.getElementById('nueva_tip_desc');
      const desc = descInput ? descInput.value.trim().toUpperCase() : '';
      if (!nom) {
        alert('Por favor ingresa un nombre para la tipología');
        if (nomInput) nomInput.focus();
        return;
      }

      const eDir = Math.max(0, parseInt(document.getElementById('tip_ejes_dir_cant')?.value) || 0);
      const tDir = document.getElementById('tip_ejes_dir_tipo')?.value || 'sencilla';
      const eTrac = Math.max(0, parseInt(document.getElementById('tip_ejes_trac_cant')?.value) || 0);
      const tTrac = document.getElementById('tip_ejes_trac_tipo')?.value || 'dual';
      const eLib = Math.max(0, parseInt(document.getElementById('tip_ejes_libre_cant')?.value) || 0);
      const tLib = document.getElementById('tip_ejes_libre_tipo')?.value || 'dual';
      const eRep = Math.max(0, parseInt(document.getElementById('tip_ejes_repuesto_cant')?.value) || 0);

      const totalLlantas = recalcularLlantasTipologia();

      if (tipologiaEditando) {
        const editPayload = {
          nombre_antiguo: tipologiaEditando,
          nombre_nuevo: nom,
          descripcion: desc,
          cant_llantas: totalLlantas,
          ejes_dir: eDir,
          tipo_dir: tDir,
          ejes_trac: eTrac,
          tipo_trac: tTrac,
          ejes_libres: eLib,
          tipo_libres: tLib,
          cant_repuestos: eRep
        };
        try {
          const res = await fetch('/api/tipologias', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(editPayload)
          });
          if (res.ok) {
            cerrarModalTipologia();
            cargarCatalogos(null, nom);
            cargarTipologiasCat();
            mostrarToast(`✅ Tipología "${nom}" actualizada exitosamente.`);
          } else {
            const err = await res.json().catch(() => ({}));
            alert(err.detail || 'Error al actualizar la tipología.');
          }
        } catch (e) {
          alert('Error de conexión al actualizar tipología.');
        }
      } else {
        const payload = {
          nombre: nom,
          descripcion: desc,
          cant_llantas: totalLlantas,
          ejes_dir: eDir,
          tipo_dir: tDir,
          ejes_trac: eTrac,
          tipo_trac: tTrac,
          ejes_libres: eLib,
          tipo_libres: tLib,
          cant_repuestos: eRep
        };

        try {
          const res = await fetch('/api/tipologias', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
          });
          if (res.ok) {
            cerrarModalTipologia();
            if (nomInput) nomInput.value = '';
            if (descInput) descInput.value = '';
            cargarCatalogos(null, nom);
            cargarTipologiasCat();
            mostrarToast(`✅ Tipología "${nom}" guardada exitosamente (${totalLlantas} llantas).`);
          } else {
            const err = await res.json().catch(() => ({}));
            alert(err.detail || 'Error al guardar la tipología. Verifica que el nombre no esté duplicado.');
          }
        } catch (e) {
          alert('Error de conexión al guardar tipología.');
        }
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
    async function abrirModalInformePdf(placa, fecha = '', cliente = '', tipologia = '') {
      document.getElementById('lblPlacaPdfModal').textContent = placa;
      document.getElementById('lblPlacaPdfModal').dataset.fecha = fecha || '';
      const m = document.getElementById('modalInformePdf');
      m.classList.remove('hidden');
      m.classList.add('flex');

      // 1. Datos del encabezado
      const cli = cliente || document.getElementById('cliente')?.value.trim() || 'Flota';
      const tip = tipologia || document.getElementById('tipologia')?.value || 'Tipología';
      const elTip = document.getElementById('lblTipologiaModal');
      const elCli = document.getElementById('lblClienteModal');
      if (elTip) elTip.textContent = tip;
      if (elCli) elCli.textContent = cli;

      // 2. Consultar datos de inspección del vehículo para KPIs y Planes
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
      limpiarTodoParaNuevaInspeccion();
      const inpPlaca = document.getElementById('placa');
      if (inpPlaca) inpPlaca.focus();
    }
    function descargarPdfVehiculoActual() {
      let p = (document.getElementById('lblPlacaPdfModal')?.textContent || '').trim();
      let f = (document.getElementById('lblPlacaPdfModal')?.dataset?.fecha || '').trim();
      if (!p || p === '-') {
        p = (document.getElementById('placa')?.value || '').trim();
        if (!f) f = (document.getElementById('fecha')?.value || '').trim();
      }
      if (!p) {
        mostrarToast('Por favor ingrese o seleccione una placa primero.', true);
        return;
      }
      let url = `/api/informe-pdf/${encodeURIComponent(p)}`;
      if (f) url += `?fecha=${encodeURIComponent(f)}`;
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (tok) url += (url.includes('?') ? '&' : '?') + `token=${encodeURIComponent(tok)}`;
      window.open(url, '_blank');
    }
    function descargarConsolidadoFlota() {
      let cli = (document.getElementById('cliente')?.value || getDiagVal('filtro_diag_cliente', 'filtroDiagCliente', '')).trim();
      let sub = (document.getElementById('subcliente')?.value || getDiagVal('filtro_diag_subcliente', 'filtroDiagSede', '')).trim();
      if (!cli || cli === 'Todos') {
        mostrarToast('Por favor selecciona un Cliente para generar el informe consolidado.', true);
        return;
      }
      let url = `/api/informe-pdf-consolidado?cliente=${encodeURIComponent(cli)}`;
      if (sub && sub !== 'Todos') url += `&subcliente=${encodeURIComponent(sub)}`;
      const fDesde = getDiagVal('filtro_diag_fecha_desde', 'filtroDiagFechaDesde', '').trim();
      const fHasta = getDiagVal('filtro_diag_fecha_hasta', 'filtroDiagFechaHasta', '').trim();
      if (fDesde) url += `&fecha_desde=${encodeURIComponent(fDesde)}`;
      if (fHasta) url += `&fecha_hasta=${encodeURIComponent(fHasta)}`;
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (tok) url += `&token=${encodeURIComponent(tok)}`;
      window.open(url, '_blank');
    }
    function descargarConsolidadoDesdeDiagnostico() {
      const selectCliente = getDiagEl('filtro_diag_cliente', 'filtroDiagCliente') || document.getElementById('cliente');
      let cli = (selectCliente ? selectCliente.value : '').trim();

      // Si el select está en 'Todos' o vacío, pero la vista filtrada corresponde a un cliente específico
      if (!cli || cli === 'Todos') {
        const clientesEnVista = Array.from(new Set((cacheFiltradasDiag || cacheDiagnostico || []).map(r => r.Cliente).filter(Boolean)));
        if (clientesEnVista.length === 1) {
          cli = clientesEnVista[0];
          if (selectCliente) selectCliente.value = cli;
        }
      }

      if (!cli || cli === 'Todos') {
        mostrarToast('Por favor selecciona un Cliente en el filtro de diagnóstico para generar su informe consolidado.', true);
        if (selectCliente) {
          selectCliente.focus();
          selectCliente.classList.add('ring-2', 'ring-rose-500', 'border-rose-500');
          setTimeout(() => {
            selectCliente.classList.remove('ring-2', 'ring-rose-500', 'border-rose-500');
          }, 2000);
        }
        return;
      }

      const selectSede = getDiagEl('filtro_diag_subcliente', 'filtroDiagSede') || document.getElementById('subcliente');
      const sede = (selectSede ? selectSede.value : '').trim();
      const op = getDiagVal('filtro_diag_operacion', 'filtroDiagOperacion', '').trim();
      const fDesde = getDiagVal('filtro_diag_fecha_desde', 'filtroDiagFechaDesde', '').trim();
      const fHasta = getDiagVal('filtro_diag_fecha_hasta', 'filtroDiagFechaHasta', '').trim();

      let url = `/api/informe-pdf-consolidado?cliente=${encodeURIComponent(cli)}`;
      if (sede && sede !== 'Todos') {
        url += `&subcliente=${encodeURIComponent(sede)}`;
      }
      if (op && op !== 'Todos') {
        url += `&operacion=${encodeURIComponent(op)}`;
      }
      if (fDesde) {
        url += `&fecha_desde=${encodeURIComponent(fDesde)}`;
      }
      if (fHasta) {
        url += `&fecha_hasta=${encodeURIComponent(fHasta)}`;
      }
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (tok) url += `&token=${encodeURIComponent(tok)}`;
      window.open(url, '_blank');
    }
    async function compartirWhatsAppPlan() {
      let p = (document.getElementById('lblPlacaPdfModal')?.textContent || '').trim();
      let f = (document.getElementById('lblPlacaPdfModal')?.dataset?.fecha || '').trim();
      if (!p || p === '-') {
        p = (document.getElementById('placa')?.value || '').trim();
        if (!f) f = (document.getElementById('fecha')?.value || '').trim();
      }
      if (!p) {
        mostrarToast('Por favor ingrese o seleccione una placa primero.', true);
        return;
      }

      let url = `/api/informe-pdf/${encodeURIComponent(p)}`;
      if (f) url += `?fecha=${encodeURIComponent(f)}`;
      const tok = (localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token'));
      if (tok) url += (url.includes('?') ? '&' : '?') + `token=${encodeURIComponent(tok)}`;

      mostrarToast('Preparando archivo PDF para compartir...');

      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('No se pudo obtener el PDF del servidor');
        const blob = await resp.blob();
        const fileName = `Informe_Inspeccion_${p}.pdf`;
        const file = new File([blob], fileName, { type: 'application/pdf' });

        // 1. Web Share API con archivos (Soportado en móviles Android, iOS y navegadores compatibles)
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({
            files: [file],
            title: `Informe Técnico ${p}`,
            text: `Informe de Inspección Vehículo ${p}`
          });
          mostrarToast('Archivo PDF listo para enviar por WhatsApp.');
          return;
        }
      } catch (err) {
        if (err.name === 'AbortError') return; // Operación cancelada voluntariamente por el usuario
        console.warn('Web Share API con archivos no disponible o cancelada:', err);
      }

      // 2. Fallback para PC / Navegadores de escritorio sin Web Share de archivos:
      // Se descarga automáticamente el archivo PDF al equipo y se abre WhatsApp para adjuntarlo sin compartir links
      try {
        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = `Informe_Inspeccion_${p}.pdf`;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);

        mostrarToast('📄 PDF descargado. Adjunta el archivo en el chat de WhatsApp que se abrirá.');
        setTimeout(() => {
          const msg = encodeURIComponent(`Hola, te adjunto el Informe Técnico de Inspección TireAnalyze Pro del vehículo ${p}:`);
          window.open(`https://api.whatsapp.com/send?text=${msg}`, '_blank');
        }, 700);
      } catch (e) {
        window.open(url, '_blank');
      }
    }


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

      const subclienteVal = (document.getElementById('subcliente')?.value || '').trim();
      if (!subclienteVal || subclienteVal.includes('(Seleccionar') || subclienteVal === '__nuevo__') {
        marcarErrorCampo('subcliente', 'err_subcliente');
        if (!hayErrores) {
          const elSub = document.getElementById('subcliente');
          if (elSub) {
            elSub.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(() => elSub.focus(), 250);
          }
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

      if (p_ext > 27 || p_cent > 27 || p_int > 27) {
        mostrarToast('⛔ CANDADO: Ninguna profundidad puede superar el límite físico de 27.0 mm', true);
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
        kilometraje: (() => {
          const k = parseFloat(document.getElementById('kilometraje').value) || 0;
          if (k > 0) kilometrajeInspeccionActual = k;
          return k > 0 ? k : (kilometrajeInspeccionActual || 0);
        })(),
        tipologia: document.getElementById('tipologia').value,
        marca: document.getElementById('marca').value,
        diseno: document.getElementById('diseno').value,
        dimension: dimension,
        vida: (document.getElementById('vida')?.value || 'Original').trim() || 'Original',
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
        tipo_licencia: (typeof clienteLicenciaCaptura !== 'undefined' && clienteLicenciaCaptura) ? clienteLicenciaCaptura : (typeof modoLicenciaGraficos !== 'undefined' ? modoLicenciaGraficos : 'PRO'),
        usuario_registro: usuarioActual ? usuarioActual.username : ''
      };

      registrarInicioJornadaCliente();
      const btn = document.getElementById('btnGuardar');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Guardando...';
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
          if (payload.dimension && (!dimensionPredeterminadaVehiculo || posicionesInspeccionadasPlaca.size === 1)) {
            dimensionPredeterminadaVehiculo = payload.dimension;
          }
          if (payload.novedades && payload.novedades.trim().length > 0) {
            posicionesConNovedadPlaca.set(pos, payload.novedades.trim());
          } else {
            posicionesConNovedadPlaca.delete(pos);
          }
          actualizarBarraPosicionMobile(pos);
          if (payload.marca) cacheUltimaMarcaVehiculo = payload.marca;
          if (payload.diseno) cacheUltimoDisenoVehiculo = payload.diseno;
          if (payload.dimension) cacheUltimaDimensionVehiculo = payload.dimension;
          mostrarToast(`✅ Guardada llanta Posición ${payload.posicion} de ${placa}`);
          const pendientes = listaPosicionesActual.filter(p => !posicionesInspeccionadasPlaca.has(p));
          if (pendientes.length === 0) {
            mostrarToast(`🎉 ¡Vehículo ${placa} COMPLETADO!`);
            const fechaInspActual = (document.getElementById('fecha')?.value || '').trim();
            const cliActual = document.getElementById('cliente')?.value.trim() || 'Flota';
            const tipActual = document.getElementById('tipologia')?.value || 'Tipología';
            setTimeout(() => {
              abrirModalInformePdf(placa, fechaInspActual, cliActual, tipActual);
              limpiarTodoParaNuevaInspeccion();
            }, 600);
          } else {
            limpiarSoloMedicionesCaptura();
            avanzarSiguientePosicion(pos);
            if (kilometrajeInspeccionActual > 0) {
              const inpKm = document.getElementById('kilometraje');
              if (inpKm) inpKm.value = Math.round(kilometrajeInspeccionActual);
            }

            // En móvil: apenas guarde y pase a la siguiente, subir suavemente y mostrar el diagrama de chasis
            if (window.innerWidth < 1024) {
              if (document.activeElement && typeof document.activeElement.blur === 'function') {
                document.activeElement.blur();
              }
              setTimeout(() => {
                const modChasis = document.getElementById('moduloChasis');
                if (modChasis) {
                  modChasis.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
              }, 120);
            }
          }
        } else {
          mostrarToast(result.detail || result.message || 'Error al guardar', true);
        }
      } catch (err) {
        mostrarToast('Error de red o comunicación con el servidor al guardar la inspección.', true);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-circle-check text-base"></i><span>Guardar & Siguiente Llanta</span>';
        }
      }
    });

    function avanzarSiguientePosicion(posActual) {
      const idx = listaPosicionesActual.indexOf(posActual);
      let siguientePos = null;

      // 1. Buscar hacia adelante la siguiente posición del recorrido que aún esté pendiente
      if (idx !== -1) {
        for (let i = idx + 1; i < listaPosicionesActual.length; i++) {
          const p = listaPosicionesActual[i];
          if (!posicionesInspeccionadasPlaca.has(p)) {
            siguientePos = p;
            break;
          }
        }
      }

      // 2. Si hacia adelante no hay pendientes, buscar la primera pendiente desde el inicio
      if (siguientePos === null) {
        const primeraPendiente = listaPosicionesActual.find(p => !posicionesInspeccionadasPlaca.has(p));
        if (primeraPendiente !== undefined) {
          siguientePos = primeraPendiente;
        }
      }

      // 3. Fallback: avanzar a la siguiente posición secuencial en la lista o a la primera
      if (siguientePos === null) {
        if (idx !== -1 && idx + 1 < listaPosicionesActual.length) {
          siguientePos = listaPosicionesActual[idx + 1];
        } else {
          siguientePos = listaPosicionesActual[0] || 1;
        }
      }

      seleccionarPosicion(siguientePos);
    }

    function sincronizarSlotEspecificaciones() {
      // Orden de patio: 1. Cliente -> 2. Diagrama Chasis -> 3. Especificaciones de Llanta -> 4. Mediciones
    }

    // ==============================================================
    // MÓDULO: LAS 7 BODEGAS, KARDEX Y BALANCE MRP (KPI 20) [PRO]
    // ==============================================================
    let cacheInventarioBodegas = [];
    let cacheFiltradasInventario = [];
    let paginaActualInv = 1;
    const ITEMS_POR_PAGINA_INV = 25;
    let cacheResumenMrp = null;
    let chartMrpInstancia = null;
    let bodegaFiltroActiva = '';

    function formatearPesosBodega(val) {
      const num = Number(val) || 0;
      return '$ ' + num.toLocaleString('es-CO');
    }

    async function cargarModuloBodegasMRP() {
      // 1. Control de Licencia LIGHT vs PRO
      const bannerLic = document.getElementById('bannerLicenciaBodegasLight');
      if (bannerLic) {
        if (typeof modoLicenciaGraficos !== 'undefined' && modoLicenciaGraficos === 'LIGHT') {
          bannerLic.classList.remove('hidden');
        } else {
          bannerLic.classList.add('hidden');
        }
      }

      // 2. Poblar clientes en el selector si está vacío
      const selCli = document.getElementById('selBodegaCliente');
      if (selCli && selCli.options.length <= 1) {
        let clientes = [];
        if (typeof obtenerClientesDisponiblesUsuario === 'function') {
          clientes = obtenerClientesDisponiblesUsuario();
        } else if (usuarioActual?.cliente_asignado) {
          clientes = [usuarioActual.cliente_asignado];
        }
        if (!clientes || clientes.length === 0) {
          const selPatio = document.getElementById('cliente');
          if (selPatio && selPatio.options.length > 1) {
            clientes = Array.from(selPatio.options).map(o => o.value).filter(Boolean);
          }
        }
        clientes.forEach(c => {
          if (!Array.from(selCli.options).some(o => o.value === c)) {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            selCli.appendChild(opt);
          }
        });
        if (usuarioActual?.rol !== 'admin' && usuarioActual?.cliente_asignado) {
          selCli.value = usuarioActual.cliente_asignado;
          selCli.disabled = true;
        }
      }

      const clienteSel = selCli ? selCli.value : '';
      const dimSel = document.getElementById('selBodegaDimension') ? document.getElementById('selBodegaDimension').value : '';

      // 3. Consultar Resumen MRP y Estado de las 7 Bodegas
      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const urlMrp = `/api/bodegas/resumen-mrp?cliente=${encodeURIComponent(clienteSel)}&dimension=${encodeURIComponent(dimSel)}`;
        const res = await fetch(urlMrp, { headers });
        if (res.ok) {
          const data = await res.json();
          cacheResumenMrp = data;
          
          // Actualizar porcentaje de aprobación de reencauche
          const lblAprob = document.getElementById('lblPorcentajeAprobReen');
          if (lblAprob) {
            lblAprob.textContent = ((data.configuracion?.porcentaje_aprobacion_reencauche != null) ? data.configuracion.porcentaje_aprobacion_reencauche : 85) + '%';
          }

          // Actualizar dimensiones disponibles en el selector
          const listaMrp = (data.matriz_mrp && data.matriz_mrp.length > 0) ? data.matriz_mrp : (data.resumen_mrp || []);
          const selDim = document.getElementById('selBodegaDimension');
          if (selDim && listaMrp.length > 0) {
            const dims = listaMrp.map(r => r.dimension).filter(Boolean);
            dims.forEach(d => {
              if (!Array.from(selDim.options).some(o => o.value === d)) {
                const opt = document.createElement('option');
                opt.value = d;
                opt.textContent = d;
                selDim.appendChild(opt);
              }
            });
          }

          renderizarTarjetasBodegas(data.bodegas || {}, data.alertas || []);
          renderizarGraficoMrp(listaMrp);
          renderizarTablaMrp(listaMrp);
        } else {
          console.error('Error al cargar balance MRP de bodegas:', await res.text());
        }
      } catch (err) {
        console.error('Excepción al cargar balance MRP:', err);
      }

      // 4. Cargar inventario detallado de llantas
      await cargarInventarioBodegas();
    }

    function renderizarTarjetasBodegas(b, alertas) {
      // B1 Nuevas
      const b1 = b.BODEGA_1_NUEVAS || {};
      const cantB1 = b1.cantidad != null ? b1.cantidad : (b1.total != null ? b1.total : 0);
      const elB1 = document.getElementById('cardCant_B1');
      if (elB1) elB1.textContent = cantB1;
      const elSubB1 = document.getElementById('cardSub_B1');
      if (elSubB1) elSubB1.textContent = formatearPesosBodega(b1.valor_cop != null ? b1.valor_cop : (b1.valor_libros || 0));

      // B2 Recambio
      const b2 = b.BODEGA_2_RECAMBIO || {};
      const cantB2 = b2.cantidad != null ? b2.cantidad : (b2.total != null ? b2.total : 0);
      const elB2 = document.getElementById('cardCant_B2');
      if (elB2) elB2.textContent = cantB2;
      const elSubB2 = document.getElementById('cardSub_B2');
      if (elSubB2) elSubB2.textContent = `${b2.libres != null ? b2.libres : cantB2} libres / ${b2.reservadas || b2.reservadas_dual || 0} dual`;

      // B3 Reencauche
      const b3 = b.BODEGA_3_REENCAUCHE || {};
      const cantB3 = b3.cantidad != null ? b3.cantidad : (b3.total != null ? b3.total : 0);
      const elB3 = document.getElementById('cardCant_B3');
      if (elB3) elB3.textContent = cantB3;
      const elSubB3 = document.getElementById('cardSub_B3');
      if (elSubB3) {
        elSubB3.textContent = (b3.alerta_mas_15_dias > 0) ? `⚠️ ${b3.alerta_mas_15_dias} con >15 días` : 'En planta a tiempo';
        if (b3.alerta_mas_15_dias > 0) elSubB3.classList.add('text-rose-600', 'font-black');
        else elSubB3.classList.remove('text-rose-600', 'font-black');
      }

      // B4 Reencauchadas Listas
      const b4 = b.BODEGA_4_REENCAUCHADAS || {};
      const cantB4 = b4.cantidad != null ? b4.cantidad : (b4.total != null ? b4.total : 0);
      const elB4 = document.getElementById('cardCant_B4');
      if (elB4) elB4.textContent = cantB4;
      const elSubB4 = document.getElementById('cardSub_B4');
      if (elSubB4) elSubB4.textContent = b4.valor_cop ? formatearPesosBodega(b4.valor_cop) : 'Listas para patio';

      // B5 Reparación
      const b5 = b.BODEGA_5_REPARACION || {};
      const cantB5 = b5.cantidad != null ? b5.cantidad : (b5.total != null ? b5.total : 0);
      const elB5 = document.getElementById('cardCant_B5');
      if (elB5) elB5.textContent = cantB5;
      const elSubB5 = document.getElementById('cardSub_B5');
      if (elSubB5) elSubB5.textContent = `Rep: ${formatearPesosBodega(b5.costo_reparaciones_acum || b5.valor_cop || 0)}`;

      // B6 FVU Desecho
      const b6 = b.BODEGA_6_FVU || {};
      const cantB6 = b6.cantidad != null ? b6.cantidad : (b6.total != null ? b6.total : 0);
      const elB6 = document.getElementById('cardCant_B6');
      if (elB6) elB6.textContent = cantB6;
      const elSubB6 = document.getElementById('cardSub_B6');
      if (elSubB6) {
        elSubB6.textContent = `Pérdida: ${formatearPesosBodega(b6.dinero_perdido_fvu != null ? b6.dinero_perdido_fvu : (b6.valor_cop || 0))}`;
      }

      // B7 Chatarrizada
      const b7 = b.BODEGA_7_CHATARRIZADA || {};
      const cantB7 = b7.cantidad != null ? b7.cantidad : (b7.total != null ? b7.total : 0);
      const elB7 = document.getElementById('cardCant_B7');
      if (elB7) elB7.textContent = cantB7;
      const elSubB7 = document.getElementById('cardSub_B7');
      if (elSubB7) elSubB7.textContent = b7.valor_cop ? formatearPesosBodega(b7.valor_cop) : 'Acta Ambiental';

      // Montadas Operación
      const mo = b.MONTADA_OPERACION || {};
      const cantMo = mo.cantidad != null ? mo.cantidad : (mo.total != null ? mo.total : 0);
      const elMo = document.getElementById('cardCant_MONTADA');
      if (elMo) elMo.textContent = cantMo;
      const elSubMo = document.getElementById('cardSub_MONTADA');
      if (elSubMo) elSubMo.textContent = mo.valor_cop ? formatearPesosBodega(mo.valor_cop) : 'Rodando en Flota';

      // Alertas Inteligentes
      const contAlertas = document.getElementById('contenedorAlertasBodegas');
      if (contAlertas) {
        contAlertas.innerHTML = '';
        if (alertas && alertas.length > 0) {
          alertas.forEach(al => {
            const div = document.createElement('div');
            div.className = 'flex items-center space-x-2 bg-amber-50 border border-amber-300 text-amber-900 px-3.5 py-2 rounded-xl text-xs font-bold shadow-2xs';
            div.innerHTML = `<i class="fa-solid fa-bell text-amber-600 text-sm"></i><span>${al}</span>`;
            contAlertas.appendChild(div);
          });
        }
      }
    }

    function renderizarGraficoMrp(resumenMrp) {
      const ctx = document.getElementById('chartMrpBodegas');
      if (!ctx) return;

      if (chartMrpInstancia) {
        chartMrpInstancia.destroy();
        chartMrpInstancia = null;
      }

      if (!resumenMrp || resumenMrp.length === 0) {
        return;
      }

      const labels = resumenMrp.map(r => r.dimension);
      const dataBruta = resumenMrp.map(r => r.necesidad_bruta != null ? r.necesidad_bruta : 0);
      const dataStock = resumenMrp.map(r => r.stock_disponible_util != null ? r.stock_disponible_util : (r.stock_util_total || 0));
      const dataCompra = resumenMrp.map(r => r.compra_neta_sugerida != null ? r.compra_neta_sugerida : 0);

      chartMrpInstancia = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: '1. Necesidad Bruta (Demanda + Par Dir. + FVU + Stock Seg.)',
              data: dataBruta,
              backgroundColor: 'rgba(239, 68, 68, 0.85)',
              borderColor: '#dc2626',
              borderWidth: 1,
              borderRadius: 6
            },
            {
              label: '2. Stock Disponible Útil (B1 + B2 + B4 + ⌊B3×%⌋ + B5)',
              data: dataStock,
              backgroundColor: 'rgba(16, 185, 129, 0.85)',
              borderColor: '#059669',
              borderWidth: 1,
              borderRadius: 6
            },
            {
              label: '3. Compra Neta Sugerida (KPI 20)',
              data: dataCompra,
              backgroundColor: 'rgba(37, 99, 235, 0.95)',
              borderColor: '#1d4ed8',
              borderWidth: 1,
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: {
                boxWidth: 12,
                font: { size: 11, weight: 'bold' }
              }
            },
            tooltip: {
              backgroundColor: '#0f172a',
              titleFont: { size: 12, weight: 'bold' },
              bodyFont: { size: 11 }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
              grid: { color: '#f1f5f9' }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    }

    function renderizarTablaMrp(resumenMrp) {
      const tbody = document.getElementById('tbodyMatrizMrp');
      if (!tbody) return;

      if (!resumenMrp || resumenMrp.length === 0) {
        tbody.innerHTML = `<tr><td colspan="12" class="p-6 text-center text-slate-400 italic">No hay datos de flota para calcular el balance MRP con los filtros seleccionados.</td></tr>`;
        return;
      }

      let html = '';
      resumenMrp.forEach(r => {
        const demRetiro = r.demanda_flota != null ? r.demanda_flota : (r.demanda_retiro_flota != null ? r.demanda_retiro_flota : 0);
        const demDir = r.demanda_direccional != null ? r.demanda_direccional : (r.demanda_par_direccional != null ? r.demanda_par_direccional : 0);
        const parDirBadge = demDir > 0 
          ? `<span class="block text-[9px] text-amber-700 font-bold">(+${demDir} Dir. KPI 05)</span>` 
          : '';

        const compraNeta = r.compra_neta_sugerida != null ? r.compra_neta_sugerida : 0;
        const compraColor = compraNeta > 0 
          ? 'bg-blue-600 text-white font-black px-2.5 py-1 rounded-xl shadow-xs' 
          : 'bg-emerald-100 text-emerald-800 font-black px-2.5 py-1 rounded-xl';

        const sugNuevas = r.compra_nuevas_direccional != null ? r.compra_nuevas_direccional : (r.sugerencia_compra_nuevas || 0);
        const sugReenc = r.compra_adicional_reencauche != null ? r.compra_adicional_reencauche : (r.sugerencia_reencauche_o_traccion || 0);

        const desgloseCompra = compraNeta > 0
          ? `<div class="text-[10px] text-slate-500 mt-1">
               <span class="text-blue-700 font-bold">${sugNuevas} Nuevas Dir.</span> | 
               <span class="text-emerald-700 font-bold">${sugReenc} Reenc./Trac.</span>
             </div>`
          : '<span class="text-[10px] text-emerald-600 block mt-0.5">Stock Cubierto</span>';

        const bajasFvu = r.reposicion_bajas_fvu != null ? r.reposicion_bajas_fvu : (r.bajas_fvu || 0);
        const stockSeg = r.stock_seguridad != null ? r.stock_seguridad : 0;
        const necBruta = r.necesidad_bruta != null ? r.necesidad_bruta : 0;
        const b1Nuevas = r.b1_nuevas != null ? r.b1_nuevas : (r.stock_b1_nuevas || 0);
        const b2Rec = r.b2_recambio_libres != null ? r.b2_recambio_libres : (r.stock_b2_recambio || 0);
        const b3Pond = r.retorno_planta_estimado != null ? r.retorno_planta_estimado : (r.stock_b3_planta_ponderado || 0);
        const b4Reenc = r.b4_reenc_listas != null ? r.b4_reenc_listas : (r.stock_b4_reencauchadas || 0);
        const b5Rep = r.b5_reparacion != null ? r.b5_reparacion : (r.stock_b5_reparacion || 0);
        const stockUtil = r.stock_disponible_util != null ? r.stock_disponible_util : (r.stock_util_total || 0);

        html += `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-3 font-black text-slate-900">${r.dimension}</td>
            <td class="p-3 text-center bg-rose-50/30">
              <span class="font-bold">${demRetiro}</span>
              ${parDirBadge}
            </td>
            <td class="p-3 text-center bg-rose-50/30 font-bold">${bajasFvu}</td>
            <td class="p-3 text-center bg-rose-50/30 font-bold">${stockSeg}</td>
            <td class="p-3 text-center font-black bg-rose-100/60 text-rose-950">${necBruta}</td>
            <td class="p-3 text-center bg-emerald-50/30 font-bold">${b1Nuevas}</td>
            <td class="p-3 text-center bg-emerald-50/30 font-bold" title="Libres para apareo dual">${b2Rec}</td>
            <td class="p-3 text-center bg-emerald-50/30 font-bold" title="En planta estimado">${b3Pond}</td>
            <td class="p-3 text-center bg-emerald-50/30 font-bold">${b4Reenc}</td>
            <td class="p-3 text-center bg-emerald-50/30 font-bold">${b5Rep}</td>
            <td class="p-3 text-center font-black bg-emerald-100/60 text-emerald-950">${stockUtil}</td>
            <td class="p-3 text-center">
              <span class="${compraColor}">${compraNeta} uds</span>
              ${desgloseCompra}
            </td>
          </tr>
        `;
      });

      tbody.innerHTML = html;
    }

    async function cargarInventarioBodegas(bodega = bodegaFiltroActiva) {
      const tbody = document.getElementById('tbodyInventarioBodegas');
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="10" class="p-6 text-center text-slate-400 italic">Cargando llantas en inventario...</td></tr>`;
      }

      const clienteSel = document.getElementById('selBodegaCliente')?.value || '';
      const dimSel = document.getElementById('selBodegaDimension')?.value || '';
      const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      const urlInv = `/api/bodegas/inventario?cliente=${encodeURIComponent(clienteSel)}&dimension=${encodeURIComponent(dimSel)}&ubicacion_bodega=${encodeURIComponent(bodega)}`;
      try {
        const res = await fetch(urlInv, { headers });
        if (res.ok) {
          const data = await res.json();
          cacheInventarioBodegas = data.llantas || [];
          paginaActualInv = 1;
          const badgeCant = document.getElementById('badgeTotalInventarioBodegas');
          if (badgeCant) badgeCant.textContent = `${cacheInventarioBodegas.length} llantas`;
          renderizarTablaInventario(cacheInventarioBodegas);
        } else {
          if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="p-6 text-center text-rose-500 font-bold">Error cargando inventario.</td></tr>`;
        }
      } catch (err) {
        console.error('Error al cargar inventario de bodegas:', err);
      }
    }

    function filtrarInventarioPorBodega(bodega) {
      bodegaFiltroActiva = bodega;

      // Actualizar estilo de las tarjetas de las 7 bodegas
      document.querySelectorAll('.card-bodega').forEach(el => {
        el.classList.remove('ring-4', 'ring-blue-500', 'shadow-lg');
      });

      if (bodega) {
        const targetCard = document.getElementById(`cardBodega_${bodega}`);
        if (targetCard) {
          targetCard.classList.add('ring-4', 'ring-blue-500', 'shadow-lg');
        }
      }

      // Sincronizar el dropdown selector de bodega
      const selUbicacion = document.getElementById('selFiltroUbicacionBodega');
      if (selUbicacion) selUbicacion.value = bodega;

      // Limpiar filtro de texto al cambiar de bodega
      const inputTxt = document.getElementById('filtroTextoInventarioBodegas');
      if (inputTxt) inputTxt.value = '';

      cargarInventarioBodegas(bodega);
    }

    function cambiarFiltroDropdownBodega(bodega) {
      filtrarInventarioPorBodega(bodega);
    }

    function filtrarTablaInventarioEnVivo() {
      paginaActualInv = 1;
      const q = (document.getElementById('filtroTextoInventarioBodegas')?.value || '').toLowerCase().trim();
      if (!q) {
        renderizarTablaInventario(cacheInventarioBodegas);
        return;
      }
      const filtradas = cacheInventarioBodegas.filter(item => {
        return (item.numero_interno || '').toLowerCase().includes(q) ||
               (item.marca || '').toLowerCase().includes(q) ||
               (item.diseno || '').toLowerCase().includes(q) ||
               (item.placa_actual || '').toLowerCase().includes(q) ||
               (item.proveedor_actual || '').toLowerCase().includes(q);
      });
      renderizarTablaInventario(filtradas);
    }

    function renderizarBadgeUbicacionBodega(ubicacion) {
      switch (ubicacion) {
        case 'BODEGA_1_NUEVAS':
          return `<span class="bg-sky-100 text-sky-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-sky-300">B1: Nuevas</span>`;
        case 'BODEGA_2_RECAMBIO':
          return `<span class="bg-emerald-100 text-emerald-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-emerald-300">B2: Recambio</span>`;
        case 'BODEGA_3_REENCAUCHE':
          return `<span class="bg-indigo-100 text-indigo-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-indigo-300">B3: En Planta</span>`;
        case 'BODEGA_4_REENCAUCHADAS':
          return `<span class="bg-teal-100 text-teal-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-teal-300">B4: Reencauchada</span>`;
        case 'BODEGA_5_REPARACION':
          return `<span class="bg-amber-100 text-amber-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-amber-300">B5: Vulcanizadora</span>`;
        case 'BODEGA_6_FVU':
          return `<span class="bg-rose-100 text-rose-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-rose-300">B6: Desecho FVU</span>`;
        case 'BODEGA_7_CHATARRIZADA':
          return `<span class="bg-slate-200 text-slate-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-slate-300">B7: Chatarrizada</span>`;
        case 'MONTADA_OPERACION':
          return `<span class="bg-blue-100 text-blue-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-blue-300">En Operación</span>`;
        default:
          return `<span class="bg-slate-100 text-slate-700 text-[10px] font-bold px-2 py-0.5 rounded-full">${ubicacion || 'Bodega'}</span>`;
      }
    }

    function renderizarBadgeGarantia(estado) {
      if (!estado || estado === 'No Aplica') {
        return `<span class="text-slate-400 text-[10px]">No Aplica</span>`;
      }
      switch (estado) {
        case 'Posible Garantía':
          return `<span class="bg-amber-100 text-amber-800 font-black text-[10px] px-2 py-0.5 rounded-full border border-amber-300">🟡 Posible</span>`;
        case 'En Reclamación':
          return `<span class="bg-sky-100 text-sky-800 font-black text-[10px] px-2 py-0.5 rounded-full border border-sky-300">🔵 En Trámite</span>`;
        case 'Nota Crédito Reconocida':
          return `<span class="bg-emerald-100 text-emerald-800 font-black text-[10px] px-2 py-0.5 rounded-full border border-emerald-300">🟢 NC Aprobada</span>`;
        case 'Rechazada':
          return `<span class="bg-rose-100 text-rose-800 font-black text-[10px] px-2 py-0.5 rounded-full border border-rose-300">🔴 Rechazada</span>`;
        default:
          return `<span class="text-slate-500 text-[10px] font-semibold">${estado}</span>`;
      }
    }

    function renderizarTablaInventario(lista) {
      const tbody = document.getElementById('tbodyInventarioBodegas');
      const contenedorPaginacion = document.getElementById('contenedorPaginacionInvBodegas');
      if (!tbody) return;

      cacheFiltradasInventario = lista || [];

      if (!lista || lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="p-6 text-center text-slate-400 italic">No se encontraron llantas en esta bodega o criterio de búsqueda.</td></tr>`;
        if (contenedorPaginacion) contenedorPaginacion.classList.add('hidden');
        return;
      }

      // Paginación de 25 registros por página
      const totalRegistros = lista.length;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_INV) || 1;
      if (paginaActualInv > totalPaginas) paginaActualInv = totalPaginas;
      if (paginaActualInv < 1) paginaActualInv = 1;

      const inicio = (paginaActualInv - 1) * ITEMS_POR_PAGINA_INV;
      const fin = Math.min(inicio + ITEMS_POR_PAGINA_INV, totalRegistros);
      const paginaItems = lista.slice(inicio, fin);

      let html = '';
      paginaItems.forEach(ll => {
        let detalleVehiculo = '-';
        if (ll.ubicacion_bodega === 'MONTADA_OPERACION' && ll.placa_actual) {
          detalleVehiculo = `<span class="font-black text-blue-900">${ll.placa_actual}</span> <span class="text-slate-500 text-[10px]">Pos ${ll.posicion_actual || '-'}</span>`;
        } else if (ll.ubicacion_bodega === 'BODEGA_3_REENCAUCHE') {
          detalleVehiculo = `<span class="font-medium text-slate-700">${ll.proveedor_actual || 'En planta'}</span> ${ll.dias_en_planta > 0 ? `<span class="text-[10px] text-amber-700 font-bold">(${ll.dias_en_planta} d)</span>` : ''}`;
        } else if (ll.ubicacion_bodega === 'BODEGA_2_RECAMBIO' && ll.reservada_para_dual) {
          detalleVehiculo = `<span class="text-emerald-700 font-bold text-[10px]">Reservada para Dual (KPI 08)</span>`;
        } else if (ll.ubicacion_bodega === 'BODEGA_6_FVU') {
          detalleVehiculo = `<span class="text-rose-700 font-bold text-[10px]">${ll.causal_baja_fvu || 'Baja Prematura'}</span>`;
        } else if (ll.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA') {
          detalleVehiculo = `<span class="text-slate-500 text-[10px]">${ll.numero_acta_ambiental || 'Acta Ambiental'}</span>`;
        } else if (ll.proveedor_actual) {
          detalleVehiculo = `<span class="text-slate-600 text-[10px]">${ll.proveedor_actual}</span>`;
        }

        const costoTotalFormateado = formatearPesosBodega(ll.costo_acumulado_total || ll.costo_ciclo_actual || 0);
        const serialSeguro = String(ll.numero_interno || '').replace(/'/g, "\\'");

        html += `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-3 font-black text-slate-900 flex items-center space-x-1.5">
              <span>${ll.numero_interno}</span>
            </td>
            <td class="p-3">${renderizarBadgeUbicacionBodega(ll.ubicacion_bodega)}</td>
            <td class="p-3">
              <div class="font-bold text-slate-800">${ll.marca || ''}</div>
              <div class="text-[10px] text-slate-400 uppercase">${ll.diseno || ''}</div>
            </td>
            <td class="p-3 font-semibold text-slate-700">${ll.dimension || '-'}</td>
            <td class="p-3 text-center">
              <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${ll.vida_actual === 'Original' ? 'bg-sky-100 text-sky-800' : 'bg-teal-100 text-teal-800'}">
                ${ll.vida_actual || 'Original'}
              </span>
            </td>
            <td class="p-3 text-center font-black ${ll.prof_actual_min <= 3.0 ? 'text-rose-600' : 'text-slate-800'}">
              ${ll.prof_actual_min != null ? Number(ll.prof_actual_min).toFixed(1) + ' mm' : '-'}
            </td>
            <td class="p-3">${detalleVehiculo}</td>
            <td class="p-3 text-right font-bold text-slate-800">${costoTotalFormateado}</td>
            <td class="p-3 text-center">${renderizarBadgeGarantia(ll.estado_garantia)}</td>
            <td class="p-3 text-center">
              <div class="flex items-center justify-center space-x-1">
                <button type="button" onclick="abrirModalMoverBodega('${serialSeguro}')" title="Mover a otra bodega o vehículo" class="p-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold text-xs border border-blue-200">
                  <i class="fa-solid fa-arrows-turn-to-dots"></i>
                </button>
                <button type="button" onclick="abrirModalGarantia('${serialSeguro}')" title="Gestionar Garantía" class="p-1.5 rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs border border-purple-200">
                  <i class="fa-solid fa-shield-halved"></i>
                </button>
                <button type="button" onclick="abrirModalHojaVida('${serialSeguro}')" title="Ver Hoja de Vida Completa (Life Sheet)" class="p-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold text-xs border border-emerald-200 shadow-2xs">
                  <i class="fa-solid fa-file-waveform"></i>
                </button>
                <button type="button" onclick="abrirModalKardex('${serialSeguro}')" title="Ver Kardex y Timeline" class="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs border border-slate-300">
                  <i class="fa-solid fa-timeline"></i>
                </button>
                ${(ll.ubicacion_bodega === 'BODEGA_3_REENCAUCHE' || ll.estado_actual === 'Bodega_3_Reencauche') ? `
                  <button type="button" onclick="abrirModalDespachoPlanta('${serialSeguro}')" title="Despachar a Planta Reencauche" class="p-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs border border-indigo-200">
                    <i class="fa-solid fa-industry"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_4_REENCAUCHADAS' || ll.estado_actual === 'Bodega_4_EnPlanta') ? `
                  <button type="button" onclick="abrirModalRetornoReencauche('${serialSeguro}')" title="Recepcionar Reencauche" class="p-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-700 font-bold text-xs border border-teal-200">
                    <i class="fa-solid fa-arrows-spin"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_5_REPARACION' || ll.estado_actual === 'Bodega_5_Reparacion') ? `
                  <button type="button" onclick="abrirModalFinalizarReparacion('${serialSeguro}')" title="Finalizar Reparación" class="p-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold text-xs border border-amber-200">
                    <i class="fa-solid fa-wrench"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_6_FVU' || ll.estado_actual === 'Bodega_6_Garantia') ? `
                  <button type="button" onclick="abrirModalDictamenGarantia('${serialSeguro}')" title="Dictamen de Garantía" class="p-1.5 rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs border border-purple-200">
                    <i class="fa-solid fa-shield-halved"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA' || ll.estado_actual === 'Bodega_7_FVU') ? `
                  <a href="/api/bodegas/pdf-acta-chatarrizacion/${encodeURIComponent(ll.numero_interno)}" target="_blank" title="Descargar Acta Chatarrización PDF" class="p-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold text-xs border border-rose-200 flex items-center">
                    <i class="fa-solid fa-file-pdf"></i>
                  </a>
                ` : ''}
              </div>
            </td>
          </tr>
        `;
      });

      tbody.innerHTML = html;
      actualizarBarraPaginacionInv(totalRegistros, inicio, fin);
    }

    function cambiarPaginaInv(nuevaPagina) {
      const totalRegistros = cacheFiltradasInventario ? cacheFiltradasInventario.length : 0;
      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_INV) || 1;
      if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
      paginaActualInv = nuevaPagina;
      renderizarTablaInventario(cacheFiltradasInventario);
      const contTabla = document.querySelector('#vista-bodegas .overflow-x-auto');
      if (contTabla) contTabla.scrollTop = 0;
    }

    function actualizarBarraPaginacionInv(totalRegistros, inicio, fin) {
      const contenedor = document.getElementById('contenedorPaginacionInvBodegas');
      const lblInicio = document.getElementById('pagInicioInv');
      const lblFin = document.getElementById('pagFinInv');
      const lblTotal = document.getElementById('pagTotalInv');
      const controles = document.getElementById('controlesPaginacionInv');

      if (!contenedor || !controles) return;
      if (totalRegistros === 0) {
        contenedor.classList.add('hidden');
        return;
      }

      contenedor.classList.remove('hidden');
      if (lblInicio) lblInicio.textContent = (inicio + 1).toLocaleString();
      if (lblFin) lblFin.textContent = fin.toLocaleString();
      if (lblTotal) lblTotal.textContent = totalRegistros.toLocaleString();

      const totalPaginas = Math.ceil(totalRegistros / ITEMS_POR_PAGINA_INV) || 1;

      let html = '';

      // Botón Primero
      const deshabilitarPrimero = paginaActualInv <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaInv(1)" ${deshabilitarPrimero ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarPrimero ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Primera página">
          <i class="fa-solid fa-angles-left text-[11px]"></i>
        </button>
      `;

      // Botón Anterior
      const deshabilitarAnt = paginaActualInv <= 1;
      html += `
        <button type="button" onclick="cambiarPaginaInv(${paginaActualInv - 1})" ${deshabilitarAnt ? 'disabled' : ''}
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
        let start = Math.max(2, paginaActualInv - 1);
        let end = Math.min(totalPaginas - 1, paginaActualInv + 1);

        if (paginaActualInv <= 3) {
          end = 4;
        } else if (paginaActualInv >= totalPaginas - 2) {
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
        } else if (p === paginaActualInv) {
          html += `
            <button type="button" class="w-8 h-8 rounded-xl bg-blue-600 text-white font-black text-xs shadow-sm flex items-center justify-center cursor-default">
              ${p}
            </button>
          `;
        } else {
          html += `
            <button type="button" onclick="cambiarPaginaInv(${p})" class="w-8 h-8 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900 font-bold text-xs shadow-xs transition-all flex items-center justify-center cursor-pointer active:scale-95">
              ${p}
            </button>
          `;
        }
      });

      // Botón Siguiente
      const deshabilitarSig = paginaActualInv >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaInv(${paginaActualInv + 1})" ${deshabilitarSig ? 'disabled' : ''}
          class="inline-flex items-center space-x-1 px-2.5 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all ${
            deshabilitarSig ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Página siguiente">
          <span class="hidden sm:inline">Sig</span>
          <i class="fa-solid fa-chevron-right text-[11px]"></i>
        </button>
      `;

      // Botón Último
      const deshabilitarUltimo = paginaActualInv >= totalPaginas;
      html += `
        <button type="button" onclick="cambiarPaginaInv(${totalPaginas})" ${deshabilitarUltimo ? 'disabled' : ''}
          class="w-8 h-8 rounded-xl border border-slate-200 text-xs font-bold transition-all flex items-center justify-center ${
            deshabilitarUltimo ? 'text-slate-300 bg-slate-50 cursor-not-allowed opacity-50' : 'text-slate-600 bg-white hover:bg-slate-100 hover:text-slate-900 shadow-xs cursor-pointer active:scale-95'
          }" title="Última página">
          <i class="fa-solid fa-angles-right text-[11px]"></i>
        </button>
      `;

      controles.innerHTML = html;
    }

    // ==========================================
    // OPERACIONES DE MODALES (ALTA, MOVER, GARANTÍA, KARDEX)
    // ==========================================

    function abrirModalAltaBodega() {
      const cliSel = document.getElementById('selBodegaCliente')?.value || '';
      document.getElementById('alta_cliente').value = cliSel || (usuarioActual?.cliente_asignado || '');
      document.getElementById('alta_numero_interno').value = '';
      document.getElementById('alta_marca').value = '';
      document.getElementById('alta_diseno').value = '';
      document.getElementById('alta_proveedor').value = '';
      document.getElementById('alta_observaciones').value = '';
      document.getElementById('modalAltaLlantaBodega').classList.remove('hidden');
      document.getElementById('modalAltaLlantaBodega').classList.add('flex');
    }

    function cerrarModalAltaBodega() {
      document.getElementById('modalAltaLlantaBodega').classList.add('hidden');
      document.getElementById('modalAltaLlantaBodega').classList.remove('flex');
    }

    async function guardarAltaLlantaBodega(e) {
      e.preventDefault();
      const payload = {
        cliente: document.getElementById('alta_cliente').value.trim(),
        numero_interno: document.getElementById('alta_numero_interno').value.trim().toUpperCase(),
        bodega_inicial: document.getElementById('alta_bodega_inicial').value,
        dimension: document.getElementById('alta_dimension').value.trim(),
        marca: document.getElementById('alta_marca').value.trim().toUpperCase(),
        diseno: document.getElementById('alta_diseno').value.trim().toUpperCase(),
        vida_actual: document.getElementById('alta_vida_actual').value,
        banda_reen: document.getElementById('alta_banda_reen').value.trim().toUpperCase(),
        prof_inicial: parseFloat(document.getElementById('alta_prof_inicial').value) || 18.0,
        prof_actual_min: parseFloat(document.getElementById('alta_prof_inicial').value) || 18.0,
        costo_compra: parseFloat(document.getElementById('alta_costo_compra').value) || 1450000.0,
        proveedor_actual: document.getElementById('alta_proveedor').value.trim(),
        observaciones: document.getElementById('alta_observaciones').value.trim()
      };

      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
        const res = await fetch('/api/bodegas/alta', {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });
        const resp = await res.json();
        if (res.ok && resp.ok) {
          mostrarToast('✅ Llanta dada de alta en bodega exitosamente');
          cerrarModalAltaBodega();
          cargarModuloBodegasMRP();
        } else {
          mostrarToast('❌ Error: ' + (resp.detail || resp.mensaje || 'No se pudo dar de alta'), true);
        }
      } catch (err) {
        console.error('Error al dar de alta llanta:', err);
        mostrarToast('❌ Error de comunicación con el servidor', true);
      }
    }

    function nombreUbicacionBodega(cod) {
      const m = {
        'BODEGA_1_NUEVAS': 'Bodega 1 (Stock Nuevas)',
        'BODEGA_2_RECAMBIO': 'Bodega 2 (Recambio Patio)',
        'BODEGA_3_REENCAUCHE': 'Bodega 3 (En Planta Reencauche)',
        'BODEGA_4_REENCAUCHADAS': 'Bodega 4 (Reencauchada Lista)',
        'BODEGA_5_REPARACION': 'Bodega 5 (En Reparación / Taller)',
        'BODEGA_6_FVU': 'Bodega 6 (Fin de Vida Útil / Desecho)',
        'BODEGA_7_CHATARRIZADA': 'Bodega 7 (Chatarrizada)',
        'MONTADA_OPERACION': 'Montada en Operación'
      };
      return m[cod] || cod || 'Bodega';
    }

    function poblarDestinosPermitidos(llanta) {
      const selDestino = document.getElementById('mover_bodega_destino');
      if (!selDestino) return;
      selDestino.innerHTML = '';

      const origen = llanta ? llanta.ubicacion_bodega : '';
      const btnSubmit = document.getElementById('btnSubmitMoverBodega');

      if (origen === 'BODEGA_7_CHATARRIZADA') {
        selDestino.disabled = true;
        if (btnSubmit) btnSubmit.classList.add('hidden');
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '⛔ Llanta Chatarrizada (Baja Definitiva Inmutable)';
        selDestino.appendChild(opt);
        return;
      }

      selDestino.disabled = false;
      if (btnSubmit) btnSubmit.classList.remove('hidden');

      const destinos = [];
      if (origen === 'BODEGA_1_NUEVAS') {
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Montar en Vehículo (Operación rodante)' });
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Trasladar a Bodega 2 (Recambio en Patio)' });
        destinos.push({ val: 'BODEGA_5_REPARACION', text: '🔧 Enviar a Bodega 5 (Reparación Mayor / Taller)' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Dar de Baja a Bodega 6 (Garantía / Daño Mayor)' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Chatarrizar en Bodega 7 (Acta Ambiental)' });
      } else if (origen === 'MONTADA_OPERACION') {
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Desmontar a Bodega 2 (Recambio en Patio)' });
        destinos.push({ val: 'BODEGA_3_REENCAUCHE', text: '🏭 Desmontar y Enviar a Bodega 3 (Planta Reencauche)' });
        destinos.push({ val: 'BODEGA_5_REPARACION', text: '🔧 Desmontar a Bodega 5 (Taller / Vulcanizadora)' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Desmontar por Fin de Vida Útil / Baja (Bodega 6)' });
        destinos.push({ val: 'MONTADA_OPERACION', text: '🔀 Rotar de Posición o Cambiar de Vehículo' });
      } else if (origen === 'BODEGA_2_RECAMBIO') {
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Montar en Vehículo (Operación rodante)' });
        destinos.push({ val: 'BODEGA_3_REENCAUCHE', text: '🏭 Enviar a Bodega 3 (Planta de Reencauche)' });
        destinos.push({ val: 'BODEGA_5_REPARACION', text: '🔧 Enviar a Bodega 5 (Taller / Vulcanizadora)' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Dar de Baja a Bodega 6 (Fin de Vida / Daño)' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Chatarrizar en Bodega 7 (Acta Ambiental)' });
      } else if (origen === 'BODEGA_3_REENCAUCHE') {
        destinos.push({ val: 'BODEGA_4_REENCAUCHADAS', text: '✨ Retorno de Reencauche a Bodega 4 (Nueva Vida)' });
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Retorno sin Reencauchar a Bodega 2 (Patio)' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Carcasa Rechazada por Planta (Baja Bodega 6)' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Chatarrizar en Bodega 7 (Acta Ambiental)' });
      } else if (origen === 'BODEGA_4_REENCAUCHADAS') {
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Montar en Vehículo (Tracción o Remolque)' });
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Mover a Bodega 2 (Recambio en Patio)' });
        destinos.push({ val: 'BODEGA_5_REPARACION', text: '🔧 Enviar a Bodega 5 (Taller / Vulcanizadora)' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Dar de Baja a Bodega 6 (Desecho FVU)' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Chatarrizar en Bodega 7 (Acta Ambiental)' });
      } else if (origen === 'BODEGA_5_REPARACION') {
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Retorno Reparada a Bodega 2 (Recambio Patio)' });
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Retorno Reparada Directo a Vehículo' });
        destinos.push({ val: 'BODEGA_3_REENCAUCHE', text: '🏭 Enviar a Bodega 3 (Planta Reencauche)' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Declarar Irreparable / Baja Bodega 6' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Chatarrizar en Bodega 7 (Acta Ambiental)' });
      } else if (origen === 'BODEGA_6_FVU') {
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Chatarrización Final con Acta Ambiental (Bodega 7)' });
        destinos.push({ val: 'BODEGA_3_REENCAUCHE', text: '🏭 Reconsiderar Carcasa para Envío a Reencauche' });
      } else {
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Montar en Vehículo (Operación)' });
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Bodega 2: Recambio en Patio' });
        destinos.push({ val: 'BODEGA_3_REENCAUCHE', text: '🏭 Bodega 3: Planta de Reencauche' });
        destinos.push({ val: 'BODEGA_4_REENCAUCHADAS', text: '✨ Bodega 4: Reencauchada Lista' });
        destinos.push({ val: 'BODEGA_5_REPARACION', text: '🔧 Bodega 5: Taller / Vulcanizadora' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Bodega 6: Fin de Vida Útil' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Bodega 7: Chatarrización' });
      }

      destinos.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.val;
        opt.textContent = d.text;
        selDestino.appendChild(opt);
      });
    }

    function abrirModalMoverBodega(numeroInterno) {
      const cleanNum = String(numeroInterno || '').trim().toUpperCase();
      let llanta = cacheInventarioBodegas.find(l => String(l.numero_interno || '').trim().toUpperCase() === cleanNum);
      if (!llanta) {
        mostrarToast('❌ Llanta no encontrada en inventario', true);
        return;
      }

      if (document.getElementById('mover_cliente')) document.getElementById('mover_cliente').value = llanta.cliente || '';
      if (document.getElementById('mover_numero_interno')) document.getElementById('mover_numero_interno').value = llanta.numero_interno || '';
      if (document.getElementById('lblMoverDetalleLlanta')) {
        document.getElementById('lblMoverDetalleLlanta').textContent = `${llanta.numero_interno} (${llanta.marca || ''} ${llanta.diseno || ''} - ${llanta.dimension || ''}) | Ubicación actual: ${nombreUbicacionBodega(llanta.ubicacion_bodega)}`;
      }

      // Configurar fecha de hoy
      if (document.getElementById('mover_fecha')) {
        document.getElementById('mover_fecha').value = new Date().toISOString().split('T')[0];
      }

      // Resetear campos de forma segura y completa
      if (document.getElementById('mover_placa')) document.getElementById('mover_placa').value = llanta.placa_actual || '';
      if (document.getElementById('mover_posicion')) document.getElementById('mover_posicion').value = llanta.posicion_actual || '';
      if (document.getElementById('mover_km_vehiculo')) document.getElementById('mover_km_vehiculo').value = '';
      if (document.getElementById('mover_prof_montaje')) {
        document.getElementById('mover_prof_montaje').value = (llanta.prof_actual_min != null) ? Number(llanta.prof_actual_min).toFixed(1) : '';
      }
      if (document.getElementById('mover_prof_recambio')) {
        document.getElementById('mover_prof_recambio').value = (llanta.prof_actual_min != null) ? Number(llanta.prof_actual_min).toFixed(1) : '8.0';
      }
      if (document.getElementById('mover_motivo_recambio')) document.getElementById('mover_motivo_recambio').value = '';
      if (document.getElementById('mover_planta_reencauche')) document.getElementById('mover_planta_reencauche').value = llanta.proveedor_actual || '';
      if (document.getElementById('mover_remision_reencauche')) document.getElementById('mover_remision_reencauche').value = '';
      if (document.getElementById('mover_banda_reen')) document.getElementById('mover_banda_reen').value = llanta.banda_reen || '';
      if (document.getElementById('mover_nueva_prof')) document.getElementById('mover_nueva_prof').value = '20.0';
      if (document.getElementById('mover_costo_reencauche')) document.getElementById('mover_costo_reencauche').value = '';
      if (document.getElementById('mover_proveedor_rep')) document.getElementById('mover_proveedor_rep').value = llanta.proveedor_actual || '';
      if (document.getElementById('mover_motivo_reparacion')) document.getElementById('mover_motivo_reparacion').value = '';
      if (document.getElementById('mover_costo_reparacion')) document.getElementById('mover_costo_reparacion').value = '';
      if (document.getElementById('mover_causal_fvu')) document.getElementById('mover_causal_fvu').value = 'Corte en costado';
      if (document.getElementById('mover_prof_fvu')) {
        document.getElementById('mover_prof_fvu').value = (llanta.prof_actual_min != null) ? Number(llanta.prof_actual_min).toFixed(1) : '3.0';
      }
      if (document.getElementById('mover_acta_ambiental')) document.getElementById('mover_acta_ambiental').value = '';
      if (document.getElementById('mover_gestor_ambiental')) document.getElementById('mover_gestor_ambiental').value = '';

      // Poblar datalist con placas de flota disponibles
      const dlPlacas = document.getElementById('datalistPlacasBodega');
      if (dlPlacas) {
        dlPlacas.innerHTML = '';
        const placasVistas = new Set();
        const selPlacaPatio = document.getElementById('placa');
        if (selPlacaPatio && selPlacaPatio.options) {
          Array.from(selPlacaPatio.options).forEach(o => {
            const p = String(o.value || '').trim().toUpperCase();
            if (p && !placasVistas.has(p)) {
              placasVistas.add(p);
              const opt = document.createElement('option');
              opt.value = p;
              dlPlacas.appendChild(opt);
            }
          });
        }
        cacheInventarioBodegas.forEach(item => {
          const p = String(item.placa_actual || '').trim().toUpperCase();
          if (p && !placasVistas.has(p)) {
            placasVistas.add(p);
            const opt = document.createElement('option');
            opt.value = p;
            dlPlacas.appendChild(opt);
          }
        });
      }

      // Poblar opciones de destino permitidas según las reglas de negocio
      poblarDestinosPermitidos(llanta);

      // Adaptar campos y alertas dinámicas según la opción seleccionada por defecto
      const selDestino = document.getElementById('mover_bodega_destino');
      const destinoSugerido = selDestino ? selDestino.value : '';
      adaptarCamposModalMover(destinoSugerido, llanta);

      document.getElementById('modalMoverBodega').classList.remove('hidden');
      document.getElementById('modalMoverBodega').classList.add('flex');
    }

    function cerrarModalMoverBodega() {
      document.getElementById('modalMoverBodega').classList.add('hidden');
      document.getElementById('modalMoverBodega').classList.remove('flex');
    }

    function adaptarCamposModalMover(destino, llanta = null) {
      const serial = document.getElementById('mover_numero_interno')?.value || '';
      const cleanNum = String(serial || '').trim().toUpperCase();
      const ll = llanta || cacheInventarioBodegas.find(l => String(l.numero_interno || '').trim().toUpperCase() === cleanNum);

      if (document.getElementById('boxMoverMontaje')) {
        document.getElementById('boxMoverMontaje').classList.toggle('hidden', destino !== 'MONTADA_OPERACION');
      }
      if (document.getElementById('boxMoverRecambio')) {
        document.getElementById('boxMoverRecambio').classList.toggle('hidden', destino !== 'BODEGA_2_RECAMBIO');
      }
      if (document.getElementById('boxMoverPlanta')) {
        document.getElementById('boxMoverPlanta').classList.toggle('hidden', destino !== 'BODEGA_3_REENCAUCHE');
      }
      if (document.getElementById('boxMoverReencauche')) {
        document.getElementById('boxMoverReencauche').classList.toggle('hidden', destino !== 'BODEGA_4_REENCAUCHADAS');
      }
      if (document.getElementById('boxMoverReparacion')) {
        document.getElementById('boxMoverReparacion').classList.toggle('hidden', destino !== 'BODEGA_5_REPARACION');
      }
      if (document.getElementById('boxMoverFVU')) {
        document.getElementById('boxMoverFVU').classList.toggle('hidden', destino !== 'BODEGA_6_FVU');
      }
      if (document.getElementById('boxMoverChatarra')) {
        document.getElementById('boxMoverChatarra').classList.toggle('hidden', destino !== 'BODEGA_7_CHATARRIZADA');
      }

      const alertaBox = document.getElementById('alertaContextualMover');
      if (alertaBox) {
        alertaBox.classList.remove('hidden', 'bg-blue-50', 'text-blue-900', 'border-blue-200', 'bg-emerald-50', 'text-emerald-900', 'border-emerald-200', 'bg-amber-50', 'text-amber-900', 'border-amber-200', 'border-amber-300', 'bg-rose-50', 'text-rose-900', 'border-rose-200', 'border-rose-300', 'bg-indigo-50', 'text-indigo-900', 'border-indigo-200', 'bg-teal-50', 'text-teal-900', 'border-teal-200', 'bg-slate-100', 'text-slate-800', 'border-slate-300');

        if (ll && ll.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA') {
          alertaBox.className = 'text-xs p-3 rounded-xl border font-bold bg-slate-100 text-slate-800 border-slate-300 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-ban text-rose-600 text-base"></i><span>Esta carcasa tiene disposición final ambiental con acta de chatarrización inmutable. No puede trasladarse a ninguna otra bodega.</span>';
          return;
        }

        if (destino === 'MONTADA_OPERACION') {
          const esReen = ll && ((ll.vida_actual && String(ll.vida_actual).toUpperCase() !== 'ORIGINAL') || (Number(ll.num_reencauches) > 0) || (ll.ubicacion_bodega === 'BODEGA_4_REENCAUCHADAS'));
          if (esReen) {
            alertaBox.className = 'text-xs p-3 rounded-xl border font-bold bg-amber-50 text-amber-900 border-amber-300 flex items-start space-x-2';
            alertaBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-amber-600 mt-0.5"></i><div><span><strong>CANDADO VIAL ACTIVO:</strong> Llanta reencauchada (<strong>' + (ll.vida_actual || 'R1') + '</strong>). Solo permitida en ejes de <strong>Tracción o Remolque (Posiciones 3 a 24)</strong>. Las posiciones direccionales (1 y 2) están bloqueadas por seguridad.</span></div>';
          } else {
            alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-blue-50 text-blue-900 border-blue-200 flex items-center space-x-2';
            alertaBox.innerHTML = '<i class="fa-solid fa-truck text-blue-600"></i><span>Si la posición seleccionada ya tiene una llanta montada, el sistema la desmontará automáticamente a Bodega 2 (Recambio).</span>';
          }
        } else if (destino === 'BODEGA_2_RECAMBIO') {
          const profActual = (ll && ll.prof_actual_min != null) ? Number(ll.prof_actual_min) : 8.0;
          if (profActual <= 3.0) {
            alertaBox.className = 'text-xs p-3 rounded-xl border font-bold bg-rose-50 text-rose-900 border-rose-300 flex items-start space-x-2';
            alertaBox.innerHTML = '<i class="fa-solid fa-hand text-rose-600 mt-0.5"></i><div><span><strong>ADVERTENCIA TÉCNICA:</strong> La profundidad actual (' + profActual.toFixed(1) + ' mm) está en o por debajo del límite de retiro (3.0 mm). El sistema rechazará almacenarla en Bodega 2. Debe enviarse a Bodega 3 (Reencauche) o Bodega 6 (FVU).</span></div>';
          } else if (ll && ll.ubicacion_bodega === 'MONTADA_OPERACION') {
            alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-emerald-50 text-emerald-900 border-emerald-200 flex items-center space-x-2';
            alertaBox.innerHTML = `<i class="fa-solid fa-arrows-split-up-and-left text-emerald-600"></i><span>La llanta será desmontada del vehículo <strong>${ll.placa_actual}</strong> (Pos ${ll.posicion_actual}) y quedará disponible en patio para recambio o apareo dual.</span>`;
          } else {
            alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-emerald-50 text-emerald-900 border-emerald-200 flex items-center space-x-2';
            alertaBox.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-600"></i><span>La llanta estará en stock reutilizable en patio para servicio rápido.</span>';
          }
        } else if (destino === 'BODEGA_3_REENCAUCHE') {
          alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-indigo-50 text-indigo-900 border-indigo-200 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-industry text-indigo-600"></i><span>Envío de carcasa a la planta de reencauche para renovación de banda.</span>';
        } else if (destino === 'BODEGA_4_REENCAUCHADAS') {
          alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-teal-50 text-teal-900 border-teal-200 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-sparkles text-teal-600"></i><span>Retorno de planta: la llanta inicia ciclo renovado (' + (ll && ll.num_reencauches ? 'R' + (Number(ll.num_reencauches) + 1) : 'R1') + ') con costo de reencauche y nueva profundidad.</span>';
        } else if (destino === 'BODEGA_5_REPARACION') {
          alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-amber-50 text-amber-900 border-amber-200 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-wrench text-amber-600"></i><span>Traslado a vulcanizadora/taller para reparación mayor o parche seccional.</span>';
        } else if (destino === 'BODEGA_6_FVU') {
          alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-rose-50 text-rose-900 border-rose-200 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-rose-600"></i><span>Dar de baja en pila de desecho. Si el desgaste fue menor al 30%, se marcará automáticamente para gestión de garantía con fábrica.</span>';
        } else if (destino === 'BODEGA_7_CHATARRIZADA') {
          alertaBox.className = 'text-xs p-2.5 rounded-xl border font-bold bg-slate-100 text-slate-800 border-slate-300 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-recycle text-slate-700"></i><span>Disposición ambiental con acta de chatarrización. Este movimiento es definitivo e inmutable.</span>';
        } else {
          alertaBox.classList.add('hidden');
        }
      }
    }

    async function guardarMovimientoBodega(e) {
      e.preventDefault();
      const destino = document.getElementById('mover_bodega_destino').value;
      const serial = document.getElementById('mover_numero_interno').value;
      const cleanNum = String(serial || '').trim().toUpperCase();
      const ll = cacheInventarioBodegas.find(l => String(l.numero_interno || '').trim().toUpperCase() === cleanNum);

      if (!destino) {
        mostrarToast('⚠️ Debe seleccionar un destino válido para la llanta', true);
        return;
      }

      const payload = {
        cliente: document.getElementById('mover_cliente').value,
        numero_interno: serial,
        bodega_destino: destino,
        fecha_movimiento: document.getElementById('mover_fecha').value,
        proveedor: '',
        documento_soporte: '',
        placa: '',
        posicion: 0,
        km_vehiculo: 0,
        costo_asociado: 0,
        banda_reen: '',
        causal_o_motivo: ''
      };

      if (destino === 'MONTADA_OPERACION') {
        payload.placa = document.getElementById('mover_placa').value.trim().toUpperCase();
        payload.posicion = parseInt(document.getElementById('mover_posicion').value) || 0;
        payload.km_vehiculo = parseFloat(document.getElementById('mover_km_vehiculo').value) || 0.0;
        const pM = document.getElementById('mover_prof_montaje');
        if (pM && pM.value) payload.prof_min_mm = parseFloat(pM.value);

        if (!payload.placa || payload.posicion <= 0) {
          const inpPlaca = document.getElementById('mover_placa');
          const inpPos = document.getElementById('mover_posicion');
          if (!payload.placa && inpPlaca) {
            inpPlaca.focus();
            inpPlaca.classList.add('ring-2', 'ring-rose-500', 'border-rose-500');
            setTimeout(() => inpPlaca.classList.remove('ring-2', 'ring-rose-500', 'border-rose-500'), 3000);
          } else if (inpPos) {
            inpPos.focus();
            inpPos.classList.add('ring-2', 'ring-rose-500', 'border-rose-500');
            setTimeout(() => inpPos.classList.remove('ring-2', 'ring-rose-500', 'border-rose-500'), 3000);
          }
          mostrarToast('⚠️ Para montar llanta debes ingresar placa y posición válida (>= 1)', true);
          return;
        }

        // Validación preventiva en cliente del candado vial
        const esReen = ll && ((ll.vida_actual && String(ll.vida_actual).toUpperCase() !== 'ORIGINAL') || (Number(ll.num_reencauches) > 0) || (ll.ubicacion_bodega === 'BODEGA_4_REENCAUCHADAS'));
        if (esReen && (payload.posicion === 1 || payload.posicion === 2)) {
          const inpPos = document.getElementById('mover_posicion');
          if (inpPos) {
            inpPos.focus();
            inpPos.classList.add('ring-2', 'ring-rose-500', 'border-rose-500');
            setTimeout(() => inpPos.classList.remove('ring-2', 'ring-rose-500', 'border-rose-500'), 3000);
          }
          mostrarToast('⛔ CANDADO VIAL: No se permite montar llantas reencauchadas en posición direccional (1 o 2). Elige posición 3 en adelante.', true);
          return;
        }
      } else if (destino === 'BODEGA_2_RECAMBIO') {
        const pRec = document.getElementById('mover_prof_recambio');
        if (pRec && pRec.value) payload.prof_min_mm = parseFloat(pRec.value);
        const motRec = document.getElementById('mover_motivo_recambio');
        if (motRec && motRec.value) payload.causal_o_motivo = motRec.value.trim();

        // Alerta preventiva si prof <= 3.0 mm
        const profCheck = (payload.prof_min_mm != null) ? payload.prof_min_mm : ((ll && ll.prof_actual_min != null) ? Number(ll.prof_actual_min) : 8.0);
        if (profCheck <= 3.0) {
          if (pRec) {
            pRec.focus();
            pRec.classList.add('ring-2', 'ring-rose-500', 'border-rose-500');
            setTimeout(() => pRec.classList.remove('ring-2', 'ring-rose-500', 'border-rose-500'), 3000);
          }
          mostrarToast('⛔ La profundidad (' + profCheck.toFixed(1) + ' mm) está en o por debajo del límite de retiro (3.0 mm). No puede enviarse a Bodega 2. Debe enviarse a Bodega 3 (Reencauche) o Bodega 6 (FVU).', true);
          return;
        }
      } else if (destino === 'BODEGA_3_REENCAUCHE') {
        payload.proveedor = document.getElementById('mover_planta_reencauche')?.value.trim() || '';
        payload.documento_soporte = document.getElementById('mover_remision_reencauche')?.value.trim() || '';
      } else if (destino === 'BODEGA_4_REENCAUCHADAS') {
        const inpBanda = document.getElementById('mover_banda_reen');
        payload.banda_reen = inpBanda?.value.trim().toUpperCase() || '';
        payload.nueva_prof_inicial = parseFloat(document.getElementById('mover_nueva_prof')?.value) || 20.0;
        payload.costo_asociado = parseFloat(document.getElementById('mover_costo_reencauche')?.value) || 0.0;
        payload.prof_min_mm = payload.nueva_prof_inicial;
        if (!payload.banda_reen) {
          if (inpBanda) {
            inpBanda.focus();
            inpBanda.classList.add('ring-2', 'ring-rose-500', 'border-rose-500');
            setTimeout(() => inpBanda.classList.remove('ring-2', 'ring-rose-500', 'border-rose-500'), 3000);
          }
          mostrarToast('⚠️ Ingrese el nombre de la banda de reencauche aplicada', true);
          return;
        }
      } else if (destino === 'BODEGA_5_REPARACION') {
        payload.proveedor = document.getElementById('mover_proveedor_rep')?.value.trim() || '';
        const motRep = document.getElementById('mover_motivo_reparacion');
        if (motRep) payload.causal_o_motivo = motRep.value.trim();
        payload.costo_asociado = parseFloat(document.getElementById('mover_costo_reparacion')?.value) || 0.0;
      } else if (destino === 'BODEGA_6_FVU') {
        payload.causal_o_motivo = document.getElementById('mover_causal_fvu')?.value || 'Fin de Vida Útil';
        payload.prof_min_mm = parseFloat(document.getElementById('mover_prof_fvu')?.value) || 0.0;
      } else if (destino === 'BODEGA_7_CHATARRIZADA') {
        payload.documento_soporte = document.getElementById('mover_acta_ambiental')?.value.trim() || '';
        payload.proveedor = document.getElementById('mover_gestor_ambiental')?.value.trim() || '';
      }

      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
        const res = await fetch('/api/bodegas/movimiento', {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });
        const resp = await res.json();
        if (res.ok && resp.ok) {
          mostrarToast('✅ Movimiento registrado en Kardex exitosamente');
          cerrarModalMoverBodega();
          cargarModuloBodegasMRP();
        } else {
          mostrarToast('❌ Error: ' + (resp.detail || resp.mensaje || 'No se pudo mover la llanta'), true);
        }
      } catch (err) {
        console.error('Error al mover llanta:', err);
        mostrarToast('❌ Error de comunicación con el servidor', true);
      }
    }

    function abrirModalGarantia(numeroInterno) {
      const cleanNum = String(numeroInterno || '').trim().toUpperCase();
      const llanta = cacheInventarioBodegas.find(l => String(l.numero_interno || '').trim().toUpperCase() === cleanNum);
      if (!llanta) {
        mostrarToast('❌ Llanta no encontrada', true);
        return;
      }

      document.getElementById('garantia_cliente').value = llanta.cliente;
      document.getElementById('garantia_numero_interno').value = llanta.numero_interno;
      document.getElementById('lblGarantiaDetalleLlanta').textContent = `${llanta.numero_interno} (${llanta.marca || ''} ${llanta.dimension || ''}) | Estado actual: ${llanta.estado_garantia || 'No Aplica'}`;

      document.getElementById('garantia_estado').value = (llanta.estado_garantia && llanta.estado_garantia !== 'No Aplica') ? llanta.estado_garantia : 'Posible Garantía';
      document.getElementById('garantia_valor_reconocido').value = llanta.valor_reconocido_garantia || 0;
      document.getElementById('garantia_observaciones').value = llanta.observaciones || '';

      document.getElementById('modalGarantiaLlanta').classList.remove('hidden');
      document.getElementById('modalGarantiaLlanta').classList.add('flex');
    }

    function cerrarModalGarantia() {
      document.getElementById('modalGarantiaLlanta').classList.add('hidden');
      document.getElementById('modalGarantiaLlanta').classList.remove('flex');
    }

    async function guardarGarantiaLlanta(e) {
      e.preventDefault();
      const payload = {
        cliente: document.getElementById('garantia_cliente').value,
        numero_interno: document.getElementById('garantia_numero_interno').value,
        estado_garantia: document.getElementById('garantia_estado').value,
        valor_reconocido_garantia: parseFloat(document.getElementById('garantia_valor_reconocido').value) || 0.0,
        observaciones: document.getElementById('garantia_observaciones').value.trim()
      };

      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
        const res = await fetch('/api/bodegas/garantia', {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });
        const resp = await res.json();
        if (res.ok && resp.ok) {
          mostrarToast('✅ Garantía actualizada y pérdida recalculará');
          cerrarModalGarantia();
          cargarModuloBodegasMRP();
        } else {
          mostrarToast('❌ Error: ' + (resp.detail || resp.mensaje || 'No se pudo actualizar garantía'), true);
        }
      } catch (err) {
        console.error('Error al actualizar garantía:', err);
        mostrarToast('❌ Error al conectar con el servidor', true);
      }
    }

    async function abrirModalKardex(numeroInterno) {
      const cleanNum = String(numeroInterno || '').trim().toUpperCase();
      const llanta = cacheInventarioBodegas.find(l => String(l.numero_interno || '').trim().toUpperCase() === cleanNum);
      const cliente = llanta ? llanta.cliente : (document.getElementById('selBodegaCliente')?.value || '');

      document.getElementById('lblKardexTitulo').textContent = `Trazabilidad completa: Llanta ${cleanNum}`;

      const boxResumen = document.getElementById('boxKardexResumenLlanta');
      if (boxResumen && llanta) {
        boxResumen.innerHTML = `
          <div><span class="text-slate-400 block text-[10px]">Marca / Dimensión:</span><strong>${llanta.marca || '-'} ${llanta.dimension || ''}</strong></div>
          <div><span class="text-slate-400 block text-[10px]">Vida / Ubicación:</span><strong>${llanta.vida_actual || 'Original'} (${nombreUbicacionBodega(llanta.ubicacion_bodega)})</strong></div>
          <div><span class="text-slate-400 block text-[10px]">Profundidad:</span><strong>${llanta.prof_actual_min != null ? Number(llanta.prof_actual_min).toFixed(1) + ' mm' : '-'}</strong></div>
          <div><span class="text-slate-400 block text-[10px]">Costo Total Acum.:</span><strong class="text-emerald-700">${formatearPesosBodega(llanta.costo_acumulado_total || 0)}</strong></div>
        `;
      }

      const timeline = document.getElementById('timelineKardexEventos');
      if (timeline) {
        timeline.innerHTML = `<div class="text-slate-400 italic text-xs">Cargando eventos del Kardex...</div>`;
      }

      document.getElementById('modalKardexLlanta').classList.remove('hidden');
      document.getElementById('modalKardexLlanta').classList.add('flex');

      try {
        const token = localStorage.getItem('tireanalyze_token') || localStorage.getItem('tirecheck_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch(`/api/bodegas/kardex?cliente=${encodeURIComponent(cliente)}&numero_interno=${encodeURIComponent(numeroInterno)}`, { headers });
        if (res.ok) {
          const data = await res.json();
          renderizarEventosKardex(data.kardex || []);
        } else {
          if (timeline) timeline.innerHTML = `<div class="text-rose-500 font-bold text-xs">No se pudo cargar el Kardex de esta llanta.</div>`;
        }
      } catch (err) {
        console.error('Error al cargar kardex:', err);
      }
    }

    function cerrarModalKardex() {
      document.getElementById('modalKardexLlanta').classList.add('hidden');
      document.getElementById('modalKardexLlanta').classList.remove('flex');
    }

    function renderizarEventosKardex(eventos) {
      const timeline = document.getElementById('timelineKardexEventos');
      if (!timeline) return;

      if (!eventos || eventos.length === 0) {
        timeline.innerHTML = `<div class="text-slate-400 italic text-xs">Esta llanta no tiene registros de movimientos previos en el Kardex.</div>`;
        return;
      }

      let html = '';
      eventos.forEach(ev => {
        let iconClass = 'fa-arrow-right text-blue-600 bg-blue-100';
        let titulo = ev.tipo_movimiento;

        switch (ev.tipo_movimiento) {
          case 'ALTA_NUEVA':
            iconClass = 'fa-plus text-emerald-600 bg-emerald-100';
            titulo = 'Ingreso a Bodega (Alta Nueva)';
            break;
          case 'MONTAJE':
            iconClass = 'fa-truck text-sky-600 bg-sky-100';
            titulo = `Montaje en Vehículo ${ev.placa || ''} Pos ${ev.posicion || ''}`;
            break;
          case 'DESMONTE_RECAMBIO':
            iconClass = 'fa-arrows-turn-to-dots text-emerald-600 bg-emerald-100';
            titulo = 'Desmonte a Bodega de Recambio';
            break;
          case 'ENVIO_REENCAUCHE':
            iconClass = 'fa-industry text-indigo-600 bg-indigo-100';
            titulo = `Envío a Planta de Reencauche (${ev.proveedor || 'Planta'})`;
            break;
          case 'RETORNO_REENCAUCHE':
            iconClass = 'fa-circle-check text-teal-600 bg-teal-100';
            titulo = `Retorno de Reencauche (${ev.vida_ciclo || 'R1'})`;
            break;
          case 'ENVIO_REPARACION':
            iconClass = 'fa-wrench text-amber-600 bg-amber-100';
            titulo = `Envío a Vulcanizadora / Taller (${ev.proveedor || 'Taller'})`;
            break;
          case 'RETORNO_REPARACION':
            iconClass = 'fa-circle-check text-amber-600 bg-amber-100';
            titulo = 'Retorno de Vulcanizadora Reparada';
            break;
          case 'BAJA_FVU':
            iconClass = 'fa-triangle-exclamation text-rose-600 bg-rose-100';
            titulo = `Baja por Fin de Vida Útil (${escapeHtml(ev.causal_o_motivo) || 'Prematura'})`;
            break;
          case 'CHATARRIZACION':
            iconClass = 'fa-recycle text-slate-600 bg-slate-200';
            titulo = `Chatarrización y Disposición Ambiental (${escapeHtml(ev.documento_soporte) || 'Acta'})`;
            break;
          case 'AJUSTE_GARANTIA':
            iconClass = 'fa-shield-halved text-purple-600 bg-purple-100';
            titulo = 'Reconocimiento de Garantía / Nota Crédito';
            break;
        }

        const detalleCosto = ev.costo_asociado > 0 
          ? `<span class="text-amber-700 font-bold ml-2">Costo: ${formatearPesosBodega(ev.costo_asociado)}</span>` 
          : '';

        const detalleProf = ev.prof_min_mm > 0 
          ? `<span class="text-slate-500 ml-2">Prof: ${Number(ev.prof_min_mm).toFixed(1)} mm</span>` 
          : '';

        html += `
          <div class="relative group">
            <span class="absolute -left-[35px] top-1 w-6 h-6 rounded-full flex items-center justify-center text-xs shadow-xs ${iconClass}">
              <i class="fa-solid ${iconClass.split(' ')[0]}"></i>
            </span>
            <div class="bg-white p-3 rounded-2xl border border-slate-200/90 shadow-2xs hover:shadow-xs transition-shadow">
              <div class="flex items-center justify-between text-xs font-black text-slate-800">
                <span>${titulo}</span>
                <span class="text-[10px] text-slate-400 font-semibold">${ev.fecha_movimiento || ''}</span>
              </div>
              <div class="text-[11px] text-slate-600 mt-1 flex flex-wrap items-center">
                <span>De: <strong>${ev.bodega_origen || '-'}</strong> → A: <strong>${ev.bodega_destino || '-'}</strong></span>
                ${detalleProf}
                ${detalleCosto}
              </div>
              ${ev.causal_o_motivo || ev.documento_soporte ? `
                <div class="text-[10px] text-slate-500 italic mt-1 bg-slate-50 px-2 py-1 rounded-lg">
                  ${ev.causal_o_motivo ? `Motivo: ${escapeHtml(ev.causal_o_motivo)} ` : ''}
                  ${ev.documento_soporte ? `Soporte: ${escapeHtml(ev.documento_soporte)}` : ''}
                </div>
              ` : ''}
            </div>
          </div>
        `;
      });

      timeline.innerHTML = html;
    }

    // ==============================================================
    // LÓGICA DE TALLER EN PATIO, 7 BODEGAS Y HOJA DE VIDA (LIFE SHEET)
    // ==============================================================

    let posTallerActualInfo = null;
    let chartCurvaDesgasteInstance = null;

    /**
     * Consulta el estado en tiempo real de la posición seleccionada en el chasis
     * y actualiza el panel de Taller en Patio (#seccionTallerPatio).
     */
    async function actualizarPanelTallerPosicion(p) {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const badgePos = document.getElementById('badgeTallerPos');
      const boxVacio = document.getElementById('tallerLlantaVacia');
      const boxMontada = document.getElementById('tallerLlantaMontada');
      const btnDesm = document.getElementById('btnTallerDesmontar');
      const btnMont = document.getElementById('btnTallerMontar');

      if (!placa || !p) {
        if (badgePos) badgePos.textContent = `Posición ${p || '-'}`;
        if (boxVacio) boxVacio.classList.remove('hidden');
        if (boxMontada) boxMontada.classList.add('hidden');
        if (btnDesm) btnDesm.disabled = true;
        posTallerActualInfo = null;
        return;
      }

      try {
        const res = await fetch(`/api/taller/posicion-info?placa=${encodeURIComponent(placa)}&posicion=${p}`);
        if (!res.ok) return;
        const data = await res.json();
        posTallerActualInfo = data;

        if (badgePos) {
          const dirTxt = data.es_direccional ? 'Direccional ⚠️' : 'Tracción / Arrastre';
          badgePos.textContent = `Posición ${p} — ${dirTxt}`;
        }

        if (data.llanta_instalada) {
          const ll = data.llanta_instalada;
          if (boxVacio) boxVacio.classList.add('hidden');
          if (boxMontada) boxMontada.classList.remove('hidden');
          if (btnDesm) btnDesm.disabled = false;

          const serialEl = document.getElementById('txtTallerSerial');
          if (serialEl) serialEl.innerHTML = `<i class="fa-solid fa-ring text-blue-600 mr-1.5"></i>${ll.numero_interno}`;
          const badgeCond = document.getElementById('badgeTallerCondicion');
          if (badgeCond) {
            badgeCond.textContent = ll.vida_actual || (ll.ciclo_actual > 1 ? `Reencauche (R${ll.ciclo_actual - 1})` : 'Original');
            badgeCond.className = `px-2 py-0.5 rounded-full text-[10px] font-black ${ll.ciclo_actual > 1 ? 'bg-teal-100 text-teal-800' : 'bg-emerald-100 text-emerald-800'}`;
          }
          const marcaEl = document.getElementById('txtTallerMarca');
          if (marcaEl) marcaEl.textContent = ll.marca_origen || ll.marca || '-';
          const disenoEl = document.getElementById('txtTallerDiseno');
          if (disenoEl) disenoEl.textContent = ll.diseno_origen || ll.diseno || '-';
          const dimEl = document.getElementById('txtTallerDim');
          if (dimEl) dimEl.textContent = ll.dimension || '-';
          const profEl = document.getElementById('txtTallerProfMin');
          if (profEl) profEl.textContent = `${Number(ll.prof_actual_min || 0).toFixed(1)} mm`;
          const kmMontEl = document.getElementById('txtTallerKmMont');
          if (kmMontEl) kmMontEl.textContent = Number(ll.km_montaje_actual || 0).toLocaleString();
          const kmRodEl = document.getElementById('txtTallerKmRodados');
          if (kmRodEl) kmRodEl.textContent = `${Number(data.km_recorridos_en_posicion || 0).toLocaleString()} km`;

          // Autocompletar el formulario de inspección si está vacío
          const inpNum = document.getElementById('numero_interno');
          if (inpNum && !inpNum.value) inpNum.value = ll.numero_interno;
          const inpMarca = document.getElementById('marca');
          if (inpMarca && !inpMarca.value) inpMarca.value = ll.marca_origen || ll.marca;
          const inpDiseno = document.getElementById('diseno');
          if (inpDiseno && !inpDiseno.value) inpDiseno.value = ll.diseno_origen || ll.diseno;
        } else {
          if (boxVacio) boxVacio.classList.remove('hidden');
          if (boxMontada) boxMontada.classList.add('hidden');
          if (btnDesm) btnDesm.disabled = true;
        }
      } catch (e) {
        console.warn('Error al obtener info de taller de la posición:', e);
      }
    }

    // --- MODAL DESMONTAR ---
    function abrirModalTallerDesmontar() {
      if (!posTallerActualInfo || !posTallerActualInfo.llanta_instalada) {
        alert('No hay una llanta montada en esta posición para retirar.');
        return;
      }
      const ll = posTallerActualInfo.llanta_instalada;
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const pos = document.getElementById('posicion')?.value || 1;
      const kmVeh = document.getElementById('kilometraje')?.value || '';

      document.getElementById('desm_numero_interno').value = ll.numero_interno;
      document.getElementById('desm_placa').value = placa;
      document.getElementById('desm_posicion').value = pos;
      document.getElementById('lblDesmSerial').textContent = `${ll.numero_interno} (${ll.marca_origen || ll.marca} - ${ll.dimension})`;
      document.getElementById('desm_odometro').value = kmVeh || '';
      document.getElementById('desm_profundidad').value = Number(ll.prof_actual_min || 3.0).toFixed(1);
      document.getElementById('desm_motivo').value = '';
      document.getElementById('lblTallerDesmonteSub').textContent = `Vehículo ${placa} - Posición ${pos}`;

      document.getElementById('modalTallerDesmontar').classList.remove('hidden');
      document.getElementById('modalTallerDesmontar').classList.add('flex');
    }

    function cerrarModalTallerDesmontar() {
      document.getElementById('modalTallerDesmontar').classList.add('hidden');
      document.getElementById('modalTallerDesmontar').classList.remove('flex');
    }

    async function ejecutarDesmonteTaller(e) {
      e.preventDefault();
      const serial = document.getElementById('desm_numero_interno').value;
      const placa = document.getElementById('desm_placa').value;
      const pos = parseInt(document.getElementById('desm_posicion').value) || 1;
      const odo = parseFloat(document.getElementById('desm_odometro').value) || 0;
      const prof = parseFloat(document.getElementById('desm_profundidad').value) || 0;
      const dest = document.getElementById('desm_bodega_destino').value;
      const mot = document.getElementById('desm_motivo').value;

      try {
        const res = await fetch('/api/taller/desmontar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            numero_interno: serial,
            odometro_vehiculo: odo,
            profundidad: prof,
            bodega_destino: dest,
            motivo: mot
          })
        });
        const data = await res.json();
        if (data.ok) {
          cerrarModalTallerDesmontar();
          alert(`Llanta ${serial} desmontada exitosamente hacia ${dest}`);
          await actualizarPanelTallerPosicion(pos);
          if (typeof cargarInventarioBodegas === 'function') cargarInventarioBodegas();
        } else {
          alert('Error: ' + (data.message || data.mensaje || 'No se pudo desmontar la llanta'));
        }
      } catch (err) {
        alert('Error en conexión al desmontar llanta: ' + err.message);
      }
    }

    // --- MODAL MONTAR ---
    async function abrirModalTallerMontar() {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const pos = parseInt(document.getElementById('posicion')?.value) || 1;
      const kmVeh = document.getElementById('kilometraje')?.value || '';
      const cliente = (document.getElementById('cliente')?.value || '').trim();

      document.getElementById('mont_placa').value = placa;
      document.getElementById('mont_posicion').value = pos;
      document.getElementById('mont_odometro').value = kmVeh || '';
      document.getElementById('lblTallerMontarSub').textContent = `Vehículo ${placa} - Posición ${pos}`;

      const esDir = posTallerActualInfo ? posTallerActualInfo.es_direccional : (pos <= 2);
      const alertaCand = document.getElementById('alertaCandadoMontar');
      if (alertaCand) {
        if (esDir) alertaCand.classList.remove('hidden');
        else alertaCand.classList.add('hidden');
      }

      cambiarTabMontar('stock');

      // Cargar lista de stock disponible (B1 y B2)
      const selStock = document.getElementById('mont_sel_stock');
      selStock.innerHTML = `<option value="">Cargando stock disponible...</option>`;
      try {
        const r1 = await fetch(`/api/bodegas/inventario?cliente=${encodeURIComponent(cliente)}&ubicacion_bodega=BODEGA_1_NUEVAS`);
        const r2 = await fetch(`/api/bodegas/inventario?cliente=${encodeURIComponent(cliente)}&ubicacion_bodega=BODEGA_2_RECAMBIO`);
        const d1 = await r1.json();
        const d2 = await r2.json();
        const lista = [...(d1.llantas || []), ...(d2.llantas || [])];

        if (lista.length === 0) {
          selStock.innerHTML = `<option value="">No hay llantas en stock (B1 o B2) para este cliente</option>`;
        } else {
          let opts = `<option value="">-- Selecciona una llanta de stock --</option>`;
          lista.forEach(ll => {
            const cicloTxt = (ll.ciclo_actual && ll.ciclo_actual > 1) ? `R${ll.ciclo_actual - 1}` : 'Original';
            const disableDir = esDir && ll.ciclo_actual > 1 ? 'disabled' : '';
            const tagDir = esDir && ll.ciclo_actual > 1 ? ' [⛔ RECHAZADA EN DIRECCIONAL]' : '';
            opts += `<option value="${ll.numero_interno}" ${disableDir}>${ll.numero_interno} | ${ll.marca || ll.marca_origen} (${ll.dimension}) - ${cicloTxt} - ${ll.prof_actual_min || 0} mm${tagDir}</option>`;
          });
          selStock.innerHTML = opts;
        }
      } catch (err) {
        selStock.innerHTML = `<option value="">Error cargando stock</option>`;
      }

      document.getElementById('modalTallerMontar').classList.remove('hidden');
      document.getElementById('modalTallerMontar').classList.add('flex');
    }

    function cerrarModalTallerMontar() {
      document.getElementById('modalTallerMontar').classList.add('hidden');
      document.getElementById('modalTallerMontar').classList.remove('flex');
    }

    function cambiarTabMontar(modo) {
      document.getElementById('mont_modo').value = modo;
      const btnStock = document.getElementById('tabBtnMontarStock');
      const btnNueva = document.getElementById('tabBtnMontarNueva');
      const pStock = document.getElementById('panelMontarStock');
      const pNueva = document.getElementById('panelMontarNueva');

      if (modo === 'stock') {
        btnStock.className = 'pb-2 text-xs font-black border-b-2 border-blue-600 text-blue-600 flex items-center space-x-1.5';
        btnNueva.className = 'pb-2 text-xs font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-700 flex items-center space-x-1.5';
        pStock.classList.remove('hidden');
        pNueva.classList.add('hidden');
      } else {
        btnNueva.className = 'pb-2 text-xs font-black border-b-2 border-blue-600 text-blue-600 flex items-center space-x-1.5';
        btnStock.className = 'pb-2 text-xs font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-700 flex items-center space-x-1.5';
        pNueva.classList.remove('hidden');
        pStock.classList.add('hidden');
      }
    }

    async function ejecutarMontajeTaller(e) {
      e.preventDefault();
      const modo = document.getElementById('mont_modo').value;
      const placa = document.getElementById('mont_placa').value;
      const pos = parseInt(document.getElementById('mont_posicion').value) || 1;
      const odo = parseFloat(document.getElementById('mont_odometro').value) || 0;
      const cliente = (document.getElementById('cliente')?.value || '').trim();

      const payload = {
        placa: placa,
        posicion: pos,
        odometro_vehiculo: odo,
        cliente_propietario: cliente
      };

      if (modo === 'stock') {
        const serial = document.getElementById('mont_sel_stock').value;
        if (!serial) {
          alert('Por favor selecciona una llanta de stock.');
          return;
        }
        payload.numero_interno = serial;
        payload.es_nueva_directa = false;
      } else {
        const s = (document.getElementById('mont_nueva_serial')?.value || '').trim().toUpperCase();
        if (!s) {
          alert('Ingresa el número interno o serial de la llanta nueva.');
          return;
        }
        payload.numero_interno = s;
        payload.es_nueva_directa = true;
        payload.marca = document.getElementById('mont_nueva_marca').value;
        payload.diseno = document.getElementById('mont_nueva_diseno').value;
        payload.dimension = document.getElementById('mont_nueva_dimension').value;
        payload.prof_inicial = parseFloat(document.getElementById('mont_nueva_prof').value) || 16.0;
        payload.precio_compra = parseFloat(document.getElementById('mont_nueva_precio').value) || 1450000.0;
      }

      try {
        const res = await fetch('/api/taller/montar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.ok) {
          cerrarModalTallerMontar();
          alert(`Llanta ${payload.numero_interno} montada con éxito en ${placa} Posición ${pos}`);
          await actualizarPanelTallerPosicion(pos);
          if (typeof cargarInventarioBodegas === 'function') cargarInventarioBodegas();
        } else {
          alert(data.message || data.mensaje || 'Error al montar llanta');
        }
      } catch (err) {
        alert('Error en conexión al montar: ' + err.message);
      }
    }

    // --- HOJA DE VIDA COMPLETA (LIFE SHEET) ---
    function abrirModalHojaVidaDesdeTaller() {
      if (posTallerActualInfo && posTallerActualInfo.llanta_instalada) {
        abrirModalHojaVida(posTallerActualInfo.llanta_instalada.numero_interno);
      } else {
        alert('No hay una llanta montada en la posición seleccionada.');
      }
    }

    async function abrirModalHojaVida(numeroInterno) {
      if (!numeroInterno) return;
      const cliente = (document.getElementById('cliente')?.value || document.getElementById('selBodegaCliente')?.value || '').trim();

      try {
        const res = await fetch(`/api/llanta/hoja-vida/${encodeURIComponent(numeroInterno)}?cliente=${encodeURIComponent(cliente)}`);
        if (!res.ok) {
          alert('No se pudo cargar la hoja de vida para: ' + numeroInterno);
          return;
        }
        const data = await res.json();
        renderizarModalHojaVida(data);
      } catch (err) {
        alert('Error al consultar Hoja de Vida: ' + err.message);
      }
    }

    function renderizarModalHojaVida(data) {
      document.getElementById('hv_serial').textContent = data.numero_interno || '-';
      const ft = data.ficha_tecnica || {};
      const met = data.metricas_consolidadas || {};

      document.getElementById('hv_badge_estado').textContent = data.estado_actual || 'Bodega';
      document.getElementById('hv_badge_ciclo').textContent = `Ciclo ${data.ciclo_actual || 1}`;

      document.getElementById('hv_marca').textContent = ft.marca || '-';
      document.getElementById('hv_diseno').textContent = ft.diseno || '-';
      document.getElementById('hv_dimension').textContent = ft.dimension || '-';
      document.getElementById('hv_prof_act').textContent = `${Number(data.profundidad_actual_min || 0).toFixed(1)} mm`;
      document.getElementById('hv_ubicacion').textContent = data.ubicacion_bodega || data.estado_actual || '-';
      document.getElementById('hv_cliente').textContent = data.cliente_propietario || '-';

      // 5 Tarjetas KPIs
      document.getElementById('hv_kpi_km').textContent = `${Number(met.km_totales || 0).toLocaleString()} km`;
      document.getElementById('hv_kpi_costo').textContent = `$ ${Number(met.costo_total_invertido || 0).toLocaleString('es-CO')}`;
      document.getElementById('hv_kpi_cpk').textContent = `$ ${Number(met.cpk_global || 0).toFixed(2)} / km`;
      document.getElementById('hv_kpi_rendimiento').textContent = `${Number(met.rendimiento_km_mm || 0).toLocaleString()} km/mm`;
      document.getElementById('hv_kpi_ahorro').textContent = `$ ${Number(met.ahorro_estimado_vs_nueva || 0).toLocaleString('es-CO')}`;

      // Botón Acta PDF si está en FVU
      const btnActa = document.getElementById('btnHvPdfActa');
      if (btnActa) {
        if (data.estado_actual === 'Bodega_7_FVU' || data.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA') {
          btnActa.classList.remove('hidden');
        } else {
          btnActa.classList.add('hidden');
        }
      }

      // Tabla de Ciclos
      const tbodyCiclos = document.getElementById('tbodyHojaVidaCiclos');
      if (tbodyCiclos) {
        const ciclos = data.desglose_por_ciclos || [];
        if (ciclos.length === 0) {
          tbodyCiclos.innerHTML = `<tr><td colspan="8" class="p-4 text-center text-slate-400 italic">No hay ciclos registrados</td></tr>`;
        } else {
          let hCiclos = '';
          ciclos.forEach(c => {
            hCiclos += `
              <tr class="hover:bg-slate-50">
                <td class="p-2.5 font-black text-slate-900">Ciclo ${c.ciclo}</td>
                <td class="p-2.5 font-bold">${c.tipo}</td>
                <td class="p-2.5 text-slate-600">${c.banda_diseno || '-'}</td>
                <td class="p-2.5 text-center font-mono">${Number(c.prof_inicial || 0).toFixed(1)} mm</td>
                <td class="p-2.5 text-center font-mono font-bold">${Number(c.prof_final || 0).toFixed(1)} mm</td>
                <td class="p-2.5 text-right font-mono font-bold">${Number(c.km_recorridos || 0).toLocaleString()} km</td>
                <td class="p-2.5 text-right font-mono">$ ${Number(c.costo || 0).toLocaleString('es-CO')}</td>
                <td class="p-2.5 text-right font-mono font-black text-indigo-700">$ ${Number(c.cpk || 0).toFixed(2)}</td>
              </tr>
            `;
          });
          tbodyCiclos.innerHTML = hCiclos;
        }
      }

      // Timeline de Eventos
      const timeline = document.getElementById('timelineHojaVidaMovimientos');
      if (timeline) {
        const movs = data.historial_movimientos || [];
        if (movs.length === 0) {
          timeline.innerHTML = `<div class="text-slate-400 text-xs italic">Sin movimientos registrados</div>`;
        } else {
          let hMovs = '';
          movs.forEach(m => {
            hMovs += `
              <div class="relative group">
                <span class="absolute -left-[31px] top-1 w-5 h-5 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-[10px] shadow-xs">
                  <i class="fa-solid fa-circle-dot"></i>
                </span>
                <div class="bg-white p-2.5 rounded-xl border border-slate-200/90 text-xs">
                  <div class="flex items-center justify-between font-bold text-slate-800">
                    <span>${m.tipo_movimiento} (${m.bodega_origen || '-'} → ${m.bodega_destino || '-'})</span>
                    <span class="text-[10px] text-slate-400">${m.fecha_movimiento || ''}</span>
                  </div>
                  <div class="text-[11px] text-slate-500 mt-0.5">
                    ${m.odometro_vehiculo > 0 ? `Odómetro: ${Number(m.odometro_vehiculo).toLocaleString()} km | ` : ''}
                    ${m.profundidad_momento > 0 ? `Prof: ${Number(m.profundidad_momento).toFixed(1)} mm | ` : ''}
                    ${m.motivo ? `Motivo: ${m.motivo}` : ''}
                  </div>
                </div>
              </div>
            `;
          });
          timeline.innerHTML = hMovs;
        }
      }

      // Gráfica Chart.js Diente de Sierra
      renderizarCurvaDesgasteChart(data.curva_desgaste || []);

      document.getElementById('modalHojaVidaLlanta').classList.remove('hidden');
      document.getElementById('modalHojaVidaLlanta').classList.add('flex');
    }

    function renderizarCurvaDesgasteChart(curva) {
      const canvas = document.getElementById('chartCurvaDesgasteHojaVida');
      if (!canvas) return;

      if (chartCurvaDesgasteInstance) {
        chartCurvaDesgasteInstance.destroy();
        chartCurvaDesgasteInstance = null;
      }

      const labels = curva.map(pt => `${Number(pt.km || 0).toLocaleString()} km`);
      const valores = curva.map(pt => pt.prof_mm);

      const ctx = canvas.getContext('2d');
      const gradient = ctx.createLinearGradient(0, 0, 0, 240);
      gradient.addColorStop(0, 'rgba(2, 132, 199, 0.35)');
      gradient.addColorStop(1, 'rgba(2, 132, 199, 0.02)');

      chartCurvaDesgasteInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: 'Profundidad de Rodadura (mm)',
            data: valores,
            borderColor: '#0284c7',
            backgroundColor: gradient,
            borderWidth: 2.5,
            fill: true,
            tension: 0.1,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: '#0284c7',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(ctxTooltip) {
                  const pt = curva[ctxTooltip.dataIndex];
                  return `${pt.evento || 'Evento'}: ${pt.prof_mm} mm (${Number(pt.km || 0).toLocaleString()} km)`;
                }
              }
            }
          },
          scales: {
            y: {
              min: 0,
              max: 22,
              title: { display: true, text: 'Milímetros (mm)', font: { weight: 'bold', size: 11 } },
              grid: { color: 'rgba(226, 232, 240, 0.7)' }
            },
            x: {
              title: { display: true, text: 'Kilómetros Acumulados', font: { weight: 'bold', size: 11 } },
              grid: { display: false }
            }
          }
        }
      });
    }

    function cerrarModalHojaVida() {
      document.getElementById('modalHojaVidaLlanta').classList.add('hidden');
      document.getElementById('modalHojaVidaLlanta').classList.remove('flex');
    }

    function descargarActaPdfDesdeHv() {
      const serial = document.getElementById('hv_serial').textContent;
      if (serial && serial !== '-') {
        window.open(`/api/bodegas/pdf-acta-chatarrizacion/${encodeURIComponent(serial)}`, '_blank');
      }
    }

    // --- ACCIONES MODALES BODEGAS OPERATIVAS ---
    function abrirModalDespachoPlanta(serial) {
      document.getElementById('desp_numero_interno').value = serial;
      document.getElementById('lblDespSerial').textContent = serial;
      document.getElementById('modalDespachoPlanta').classList.remove('hidden');
      document.getElementById('modalDespachoPlanta').classList.add('flex');
    }
    function cerrarModalDespachoPlanta() {
      document.getElementById('modalDespachoPlanta').classList.add('hidden');
      document.getElementById('modalDespachoPlanta').classList.remove('flex');
    }
    async function ejecutarDespachoPlanta(e) {
      e.preventDefault();
      const serial = document.getElementById('desp_numero_interno').value;
      const prov = document.getElementById('desp_proveedor').value;
      const guia = document.getElementById('desp_guia').value;
      const transp = document.getElementById('desp_transportador').value;
      const fComp = document.getElementById('desp_fecha_compromiso').value;

      try {
        const res = await fetch('/api/bodegas/despacho-planta', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            numeros_internos: [serial],
            llantas_ids: [serial],
            proveedor_planta: prov,
            guia_remision: guia,
            transportador: transp,
            fecha_compromiso: fComp
          })
        });
        const data = await res.json();
        if (data.ok) {
          cerrarModalDespachoPlanta();
          alert(`Llanta ${serial} despachada a ${prov}`);
          if (typeof cargarInventarioBodegas === 'function') cargarInventarioBodegas();
        } else {
          alert('Error: ' + (data.message || data.mensaje));
        }
      } catch (err) {
        alert('Error despachando: ' + err.message);
      }
    }
    function descargarPlanillaRemisionPdf() {
      const prov = document.getElementById('desp_proveedor').value || 'PLANTA';
      const guia = document.getElementById('desp_guia').value || 'REM-001';
      window.open(`/api/bodegas/pdf-despacho-planta?proveedor=${encodeURIComponent(prov)}&guia=${encodeURIComponent(guia)}`, '_blank');
    }

    function abrirModalRetornoReencauche(serial) {
      document.getElementById('ret_numero_interno').value = serial;
      document.getElementById('lblRetSerial').textContent = serial;
      document.getElementById('modalRetornoReencauche').classList.remove('hidden');
      document.getElementById('modalRetornoReencauche').classList.add('flex');
    }
    function cerrarModalRetornoReencauche() {
      document.getElementById('modalRetornoReencauche').classList.add('hidden');
      document.getElementById('modalRetornoReencauche').classList.remove('flex');
    }
    async function ejecutarRetornoReencauche(e) {
      e.preventDefault();
      const serial = document.getElementById('ret_numero_interno').value;
      const prov = document.getElementById('ret_proveedor_banda').value;
      const dis = document.getElementById('ret_diseno_banda').value;
      const prof = parseFloat(document.getElementById('ret_prof_banda').value) || 18.0;
      const costo = parseFloat(document.getElementById('ret_costo').value) || 720000;
      const fac = document.getElementById('ret_factura').value;

      try {
        const res = await fetch('/api/bodegas/retorno-reencauche', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            numero_interno: serial,
            proveedor_banda: prov,
            diseno_banda: dis,
            prof_banda_nueva: prof,
            costo_factura_renovado: costo,
            factura_renovado: fac
          })
        });
        const data = await res.json();
        if (data.ok) {
          cerrarModalRetornoReencauche();
          alert(`Reencauche recibido con éxito para ${serial}. Ciclo ${data.ciclo_actual || 2} activo.`);
          if (typeof cargarInventarioBodegas === 'function') cargarInventarioBodegas();
        } else {
          alert('Error: ' + (data.message || data.mensaje));
        }
      } catch (err) {
        alert('Error al recibir reencauche: ' + err.message);
      }
    }

    function abrirModalFinalizarReparacion(serial) {
      document.getElementById('rep_numero_interno').value = serial;
      document.getElementById('modalFinalizarReparacion').classList.remove('hidden');
      document.getElementById('modalFinalizarReparacion').classList.add('flex');
    }
    function cerrarModalFinalizarReparacion() {
      document.getElementById('modalFinalizarReparacion').classList.add('hidden');
      document.getElementById('modalFinalizarReparacion').classList.remove('flex');
    }
    async function ejecutarFinalizarReparacion(e) {
      e.preventDefault();
      const serial = document.getElementById('rep_numero_interno').value;
      const costo = parseFloat(document.getElementById('rep_costo').value) || 0;
      const trab = document.getElementById('rep_trabajo').value;

      try {
        const res = await fetch('/api/bodegas/finalizar-reparacion', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            numero_interno: serial,
            costo_reparacion: costo,
            tipo_trabajo: trab
          })
        });
        const data = await res.json();
        if (data.ok) {
          cerrarModalFinalizarReparacion();
          alert(`Reparación finalizada para ${serial}. Pasó a Bodega 2.`);
          if (typeof cargarInventarioBodegas === 'function') cargarInventarioBodegas();
        } else {
          alert('Error: ' + (data.message || data.mensaje));
        }
      } catch (err) {
        alert('Error al finalizar reparación: ' + err.message);
      }
    }

    function abrirModalDictamenGarantia(serial) {
      document.getElementById('gar_numero_interno').value = serial;
      document.getElementById('modalDictamenGarantia').classList.remove('hidden');
      document.getElementById('modalDictamenGarantia').classList.add('flex');
    }
    function cerrarModalDictamenGarantia() {
      document.getElementById('modalDictamenGarantia').classList.add('hidden');
      document.getElementById('modalDictamenGarantia').classList.remove('flex');
    }
    async function ejecutarDictamenGarantia(e) {
      e.preventDefault();
      const serial = document.getElementById('gar_numero_interno').value;
      const dictamen = document.getElementById('gar_dictamen').value;
      const pct = parseFloat(document.getElementById('gar_pct').value) || 0;
      const valor = parseFloat(document.getElementById('gar_valor').value) || 0;

      try {
        const res = await fetch('/api/bodegas/dictamen-garantia', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            numero_interno: serial,
            dictamen: dictamen,
            pct_reconocido: pct,
            valor_reconocido: valor
          })
        });
        const data = await res.json();
        if (data.ok) {
          cerrarModalDictamenGarantia();
          alert(`Dictamen guardado para ${serial}`);
          if (typeof cargarInventarioBodegas === 'function') cargarInventarioBodegas();
        } else {
          alert('Error: ' + (data.message || data.mensaje));
        }
      } catch (err) {
        alert('Error en dictamen: ' + err.message);
      }
    }


    // Inicialización al cargar DOM
    window.addEventListener('DOMContentLoaded', () => {
      sincronizarSlotEspecificaciones();
      try {
        renderizarBarraCheckboxesDiag();
        sincronizarVisibilidadTarjetasGraficos();
      } catch (e) {
        console.warn('Error inicializando checkboxes de diagnóstico:', e);
      }
      document.getElementById('fecha').value = fechaLocalISO();
      const logueado = verificarSesionUsuario();
      if (logueado) {
        cargarCatalogos();
        validarVida();
        if (typeof cargarBaseInspecciones === 'function') cargarBaseInspecciones();
      }
    });
  