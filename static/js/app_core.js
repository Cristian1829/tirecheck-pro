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

    // Desvanecido de la barra de pestañas en el lado que tiene pestañas ocultas (ver #navTabs en el CSS)
    function actualizarDesvanecidoNav() {
      const nav = document.getElementById('navTabs');
      if (!nav) return;
      nav.classList.toggle('fade-izq', nav.scrollLeft > 2);
      nav.classList.toggle('fade-der', nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 2);
    }
    document.addEventListener('DOMContentLoaded', () => {
      const nav = document.getElementById('navTabs');
      if (!nav) return;
      nav.addEventListener('scroll', actualizarDesvanecidoNav, { passive: true });
      window.addEventListener('resize', actualizarDesvanecidoNav);
      actualizarDesvanecidoNav();
    });

    // Formatos de pantalla (colombianos). Los campos de formulario siguen con punto decimal.
    // Número con coma decimal: fmtDec(3, 1) -> "3,0"; fmtDec(1234.5, 1) -> "1.234,5"
    function fmtDec(valor, decimales = 1) {
      const n = Number(valor);
      if (!isFinite(n)) return '-';
      return n.toLocaleString('es-CO', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
    }

    // Fecha 'AAAA-MM-DD[...]' -> 'DD/MM/AAAA' (lo que no sea una fecha se devuelve igual)
    function fmtFecha(valor) {
      const m = String(valor || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
      return m ? `${m[3]}/${m[2]}/${m[1]}` : (valor || '-');
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

      let response;
      try {
        response = await _originalFetch(resource, init);
      } catch (netErr) {
        // En caso de corte de red o falla de conexión en patio, NUNCA cerrar sesión ni borrar localStorage
        throw netErr;
      }

      if (response && response.status === 401 && urlStr.includes('/api/') && !urlStr.includes('/api/login')) {
        // Preservar la cola de pendientes intacta en IndexedDB (TireAnalyzeOfflineDB)
        localStorage.removeItem('tireanalyze_token');
        localStorage.removeItem('tirecheck_token');
        localStorage.removeItem('tireanalyze_usuario_sesion');
        localStorage.removeItem('tirecheck_usuario_sesion');
        usuarioActual = null;
        mostrarToast('⚠️ Sesión expirada. Sus inspecciones pendientes se conservan en el dispositivo para sincronizar.', true);
        const modalLogin = document.getElementById('modalLogin');
        if (modalLogin) {
          modalLogin.classList.remove('hidden');
        }
      }

      return response;
    };

    // ==========================================
    // PWA SERVICE WORKER Y ALMACENAMIENTO PERSISTENTE
    // ==========================================
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js', { scope: '/' })
          .then(reg => console.log('[PWA] Service Worker registrado:', reg.scope))
          .catch(err => console.warn('[PWA] Error registrando Service Worker:', err));
      });
    }
    if (navigator.storage && navigator.storage.persist) {
      navigator.storage.persist().then(persistent => {
        console.log('[Storage] Almacenamiento persistente activado:', persistent);
      }).catch(() => {});
    }

    // ==========================================
    // MOTOR DE BASE DE DATOS LOCAL (INDEXEDDB)
    // ==========================================
    const TireAnalyzeOfflineDB = {
      dbName: 'TireAnalyzeOfflineDB',
      dbVersion: 1,
      _db: null,

      async abrir() {
        if (this._db) return this._db;
        return new Promise((resolve, reject) => {
          const req = indexedDB.open(this.dbName, this.dbVersion);
          req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains('catalogos_offline')) {
              db.createObjectStore('catalogos_offline', { keyPath: 'clave' });
            }
            if (!db.objectStoreNames.contains('vehiculos_offline')) {
              db.createObjectStore('vehiculos_offline', { keyPath: 'placa' });
            }
            if (!db.objectStoreNames.contains('cola_pendientes')) {
              db.createObjectStore('cola_pendientes', { keyPath: 'dedup_key' });
            }
          };
          req.onsuccess = (e) => {
            this._db = e.target.result;
            resolve(this._db);
          };
          req.onerror = (e) => reject(e.target.error);
        });
      },

      async guardarCatalogos(datos) {
        const db = await this.abrir();
        return new Promise((resolve, reject) => {
          const tx = db.transaction('catalogos_offline', 'readwrite');
          const store = tx.objectStore('catalogos_offline');
          store.put({ clave: 'paquete_patio', valor: datos, timestamp: Date.now() });
          tx.oncomplete = () => resolve(true);
          tx.onerror = () => reject(tx.error);
        });
      },

      async obtenerCatalogos() {
        const db = await this.abrir();
        return new Promise((resolve) => {
          const tx = db.transaction('catalogos_offline', 'readonly');
          const store = tx.objectStore('catalogos_offline');
          const req = store.get('paquete_patio');
          req.onsuccess = () => resolve(req.result ? req.result.valor : null);
          req.onerror = () => resolve(null);
        });
      },

      async guardarVehiculo(vehiculo) {
        if (!vehiculo || !vehiculo.placa) return false;
        const db = await this.abrir();
        return new Promise((resolve, reject) => {
          const tx = db.transaction('vehiculos_offline', 'readwrite');
          const store = tx.objectStore('vehiculos_offline');
          store.put(vehiculo);
          tx.oncomplete = () => resolve(true);
          tx.onerror = () => reject(tx.error);
        });
      },

      async guardarVehiculosBatch(vehiculosDict) {
        const db = await this.abrir();
        return new Promise((resolve, reject) => {
          const tx = db.transaction('vehiculos_offline', 'readwrite');
          const store = tx.objectStore('vehiculos_offline');
          for (const [placa, v] of Object.entries(vehiculosDict || {})) {
            if (v && v.placa) store.put(v);
          }
          tx.oncomplete = () => resolve(true);
          tx.onerror = () => reject(tx.error);
        });
      },

      async obtenerVehiculo(placa) {
        if (!placa) return null;
        const pl = String(placa).trim().toUpperCase();
        const db = await this.abrir();
        return new Promise((resolve) => {
          const tx = db.transaction('vehiculos_offline', 'readonly');
          const store = tx.objectStore('vehiculos_offline');
          const req = store.get(pl);
          req.onsuccess = () => resolve(req.result || null);
          req.onerror = () => resolve(null);
        });
      },

      async guardarPendiente(item) {
        const db = await this.abrir();
        return new Promise((resolve, reject) => {
          const tx = db.transaction('cola_pendientes', 'readwrite');
          const store = tx.objectStore('cola_pendientes');
          store.put(item); // Upsert por dedup_key
          tx.oncomplete = () => resolve(true);
          tx.onerror = () => reject(tx.error);
        });
      },

      async obtenerPendientes() {
        const db = await this.abrir();
        return new Promise((resolve) => {
          const tx = db.transaction('cola_pendientes', 'readonly');
          const store = tx.objectStore('cola_pendientes');
          const req = store.getAll();
          req.onsuccess = () => resolve(req.result || []);
          req.onerror = () => resolve([]);
        });
      },

      async eliminarPendiente(dedup_key) {
        const db = await this.abrir();
        return new Promise((resolve, reject) => {
          const tx = db.transaction('cola_pendientes', 'readwrite');
          const store = tx.objectStore('cola_pendientes');
          store.delete(dedup_key);
          tx.oncomplete = () => resolve(true);
          tx.onerror = () => reject(tx.error);
        });
      },

      async contarPendientes() {
        const db = await this.abrir();
        return new Promise((resolve) => {
          const tx = db.transaction('cola_pendientes', 'readonly');
          const store = tx.objectStore('cola_pendientes');
          const req = store.count();
          req.onsuccess = () => resolve(req.result || 0);
          req.onerror = () => resolve(0);
        });
      }
    };

    // Helper para prevención de Lie-Fi (Falsa señal celular en patio)
    async function fetchConTimeoutPatio(url, options = {}, timeoutMs = 3500) {
      if (!navigator.onLine) {
        throw new Error('Dispositivo sin conexión a internet');
      }
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(timer);
        return response;
      } catch (err) {
        clearTimeout(timer);
        throw err;
      }
    }

    // Vida exacta de la llanta: 'Original', 'R1', 'R2'…; '' si es reencauche sin número (dato antiguo)
    function vidaExactaLlanta(vida, banda) {
      const v = String(vida || '').trim().toUpperCase();
      const m = v.match(/^R\s*(\d+)$/) || v.match(/REENCAUCHE\s*(\d+)/);
      if (m) return parseInt(m[1], 10) > 0 ? 'R' + parseInt(m[1], 10) : 'Original';
      if (!v || v.includes('ORIG') || v === 'NUEVA') return (banda && String(banda).trim() && String(banda).trim() !== '-') ? '' : 'Original';
      return '';
    }
    function esVidaReencauche(vida) {
      const v = String(vida || '').trim().toUpperCase();
      return v !== '' && v !== 'ORIGINAL' && !v.includes('ORIG') && v !== 'NUEVA';
    }

    // Profundidad máxima local (misma tabla por rin del servidor; sin conexión no hay catálogo)
    const PROF_MAXIMA_POR_RIN_LOCAL = {13: 12, 14: 12, 15: 14, 16: 16, 17: 16, 17.5: 18, 19.5: 22, 20: 24, 22.5: 27, 24: 30, 24.5: 30};
    function profundidadMaximaLocal(dimension) {
      const m = String(dimension || '').trim().toUpperCase().match(/(?:R|-|\s)(\d{2}(?:\.\d)?)\s*(?:LT|C)?\s*$/);
      if (!m) return 27;
      const rin = parseFloat(m[1]);
      if (rin >= 25) return 120;
      return PROF_MAXIMA_POR_RIN_LOCAL[rin] || 27;
    }

    // Helper para validación local de candados de seguridad en el navegador
    function validarCandadosOfflineLocal(payload) {
      const pExt = parseFloat(payload.prof_ext) || 0;
      const pCent = parseFloat(payload.prof_cent) || 0;
      const pInt = parseFloat(payload.prof_int) || 0;
      const profs = [pExt, pCent, pInt];

      // 1. Profundidad máxima según el rin de la dimensión (antes 27 mm fijos para todo rin)
      const profMax = profundidadMaximaLocal(payload.dimension);
      if (profs.some(p => p > profMax)) {
        return {
          valido: false,
          mensaje: `⛔ CANDADO DE SEGURIDAD: Ninguna profundidad puede superar ${profMax} mm para la medida ${payload.dimension || ''} (Valores ingresados: ${profs.join(', ')}).`
        };
      }

      // 1.1 La vida exacta es obligatoria (Original, R1, R2…)
      if (!String(payload.vida || '').trim()) {
        return { valido: false, mensaje: '⚠️ Seleccione la vida de la llanta (Original, R1, R2…).' };
      }

      // 2. prof <= prof_inicial si prof_inicial > 0
      const profIni = parseFloat(payload.prof_inicial) || 0;
      if (profIni > 0 && profs.some(p => p > profIni)) {
        return {
          valido: false,
          mensaje: `⛔ CANDADO DE SEGURIDAD: Ninguna profundidad (${profs.join(', ')}) puede superar la Profundidad Inicial (${profIni} mm).`
        };
      }

      // 3. Eje Direccional: vida debe ser Original (salvo autorización explícita de la tipología)
      const pos = parseInt(payload.posicion) || 1;
      const vida = String(payload.vida || 'Original').trim().toUpperCase();
      const tipologia = String(payload.tipologia || '').trim();
      const permiteReenDir = payload.permite_reencauche_direccion || (window.tipologiaPermiteReencaucheCache === true);
      if (esPosicionDireccionalLocal(tipologia, pos) && esVidaReencauche(vida) && !permiteReenDir) {
        return {
          valido: false,
          mensaje: `⛔ CANDADO DE SEGURIDAD VIAL: En el eje direccional (Posición ${pos}) no se permite Reencauche, únicamente condición Original.`
        };
      }

      // 4. Kilometraje no regresivo si hay ultimo_km previo de fecha anterior
      const kmActual = parseFloat(payload.kilometraje) || 0;
      const ultimoKm = parseFloat(payload._ultimo_km_previo || 0);
      if (ultimoKm > 0 && kmActual > 0 && kmActual < ultimoKm) {
        return {
          valido: false,
          mensaje: `⛔ CANDADO: El kilometraje ingresado (${kmActual}) no puede ser menor al último registrado (${ultimoKm}).`
        };
      }

      return { valido: true };
    }

    function esPosicionDireccionalLocal(tipologia, pos) {
      const tip = String(tipologia || '').toLowerCase();
      const p = parseInt(pos) || 1;
      if (tip.includes('cuatro manos') || tip.includes('4 manos') || tip.includes('8x4')) {
        return [1, 2, 3, 4].includes(p);
      }
      return [1, 2].includes(p);
    }

    async function actualizarVehiculoOfflineConNuevaInspeccion(payload) {
      const pl = String(payload.placa || '').trim().toUpperCase();
      if (!pl) return;
      let veh = await TireAnalyzeOfflineDB.obtenerVehiculo(pl);
      if (!veh) {
        veh = {
          placa: pl,
          tipologia: payload.tipologia || 'Cabezote',
          cliente: payload.cliente || '',
          subcliente: payload.subcliente || '',
          tipo_operacion: payload.tipo_operacion || '',
          ultimo_km: payload.kilometraje || 0,
          dimension: payload.dimension || '295/80R22.5',
          posiciones_previas: {}
        };
      }
      if (payload.kilometraje > (veh.ultimo_km || 0)) {
        veh.ultimo_km = payload.kilometraje;
      }
      if (!veh.posiciones_previas) veh.posiciones_previas = {};
      const posKey = String(payload.posicion);
      veh.posiciones_previas[posKey] = {
        numero_interno: payload.numero_interno || '',
        marca: payload.marca || '',
        diseno: payload.diseno || '',
        dimension: payload.dimension || '',
        vida: payload.vida || 'Original',
        banda_reen: payload.banda_reen || '',
        prof_inicial: payload.prof_inicial || 0,
        precio: payload.precio || 0,
        km_montaje: payload.km_montaje || 0,
        prof_ext: payload.prof_ext || 0,
        prof_cent: payload.prof_cent || 0,
        prof_int: payload.prof_int || 0,
        psi: payload.psi || 100,
        novedades: payload.novedades || '',
        fecha: (payload.fecha || '').slice(0, 10)
      };
      await TireAnalyzeOfflineDB.guardarVehiculo(veh);
    }

    async function descargarPaquetePatioOffline(manual = false) {
      const btn = document.getElementById('btnDescargarPaqueteOffline');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Preparando...';
      }
      try {
        const cliSel = (document.getElementById('cliente')?.value || '').trim();
        const url = `/api/offline/paquete-patio?cliente=${encodeURIComponent(cliSel)}`;
        const res = await fetchConTimeoutPatio(url, {}, 8500);
        if (!res.ok) throw new Error('Error HTTP ' + res.status);
        const paquete = await res.json();
        
        await TireAnalyzeOfflineDB.guardarCatalogos(paquete);
        if (paquete.vehiculos_perfil) {
          await TireAnalyzeOfflineDB.guardarVehiculosBatch(paquete.vehiculos_perfil);
        }
        
        const ahora = new Date().toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' });
        localStorage.setItem('tireanalyze_offline_fecha_descarga', ahora);
        
        const lblDesc = document.getElementById('lblFechaDescargaOffline');
        if (lblDesc) lblDesc.textContent = ahora;
        
        await actualizarIndicadorConexionOffline();
        if (manual) {
          mostrarToast('✅ Datos de Flota listos para trabajo sin señal en Patio');
        }
      } catch (err) {
        console.warn('[Offline] Error descargando paquete patio:', err);
        if (manual) {
          mostrarToast('⚠️ No se pudo descargar el paquete de patio: ' + (err.message || 'Error de red'), true);
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down mr-1.5"></i> Preparar Datos de Flota para Patio';
        }
      }
    }

    async function actualizarIndicadorConexionOffline() {
      const btn = document.getElementById('btnEstadoConexionOffline');
      const dot = document.getElementById('dotEstadoConexion');
      const lbl = document.getElementById('lblTextoEstadoConexion');
      if (!btn || !dot || !lbl) return;

      const pendientes = await TireAnalyzeOfflineDB.contarPendientes();
      const online = navigator.onLine;

      if (!online) {
        // 🟠 Sin señal
        btn.className = 'flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-200 shadow-sm cursor-pointer bg-amber-950/40 text-amber-300 border-amber-500/40 hover:bg-amber-900/50';
        dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
        lbl.textContent = `Modo Sin Señal · ${pendientes} llantas guardadas`;
      } else if (pendientes > 0) {
        // 🔵 Con pendientes por subir
        btn.className = 'flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-200 shadow-sm cursor-pointer bg-blue-950/40 text-blue-300 border-blue-500/40 hover:bg-blue-900/50';
        dot.className = 'w-2.5 h-2.5 rounded-full bg-blue-400 animate-ping';
        lbl.textContent = `🔄 Sincronizar Ahora (${pendientes})`;
      } else {
        // 🟢 En línea (0 pendientes)
        btn.className = 'flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-200 shadow-sm cursor-pointer bg-emerald-950/40 text-emerald-300 border-emerald-500/40 hover:bg-emerald-900/50';
        dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
        lbl.textContent = 'En línea · Flota Lista Offline';
      }

      const lblTot = document.getElementById('lblTotalPendientesOffline');
      if (lblTot) lblTot.textContent = pendientes;
    }

    async function abrirModalColaOffline() {
      const modal = document.getElementById('modalColaOffline');
      if (!modal) return;
      modal.classList.remove('hidden');
      modal.classList.add('flex');

      const fechaDesc = localStorage.getItem('tireanalyze_offline_fecha_descarga') || 'Sin descargar';
      const lblDesc = document.getElementById('lblFechaDescargaOffline');
      if (lblDesc) lblDesc.textContent = fechaDesc;

      await renderizarListaColaOffline();
    }

    function cerrarModalColaOffline() {
      const modal = document.getElementById('modalColaOffline');
      if (!modal) return;
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }

    async function renderizarListaColaOffline() {
      const items = await TireAnalyzeOfflineDB.obtenerPendientes();
      const lblTot = document.getElementById('lblTotalPendientesOffline');
      const lblVeh = document.getElementById('lblTotalVehiculosOffline');
      const contenedor = document.getElementById('listaLlantasColaOffline');

      if (lblTot) lblTot.textContent = items.length;
      const placasUnicas = new Set(items.map(it => it.placa));
      if (lblVeh) lblVeh.textContent = placasUnicas.size;

      if (!contenedor) return;

      if (items.length === 0) {
        contenedor.innerHTML = `
          <div class="p-6 text-center text-slate-400 bg-slate-50 rounded-2xl border border-dashed border-slate-200 font-medium">
            <i class="fa-solid fa-circle-check text-emerald-500 text-2xl mb-2 block"></i>
            Todas las inspecciones están sincronizadas con el servidor.
          </div>
        `;
        return;
      }

      contenedor.innerHTML = items.map(it => `
        <div class="p-3 bg-slate-50 hover:bg-white rounded-2xl border border-slate-200 transition-all flex items-center justify-between gap-3 shadow-2xs">
          <div class="min-w-0">
            <div class="flex items-center space-x-2">
              <span class="font-black text-slate-900 font-mono tracking-wider">${escapeHtml(it.placa)}</span>
              <span class="px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 font-bold text-[10px]">Pos. ${escapeHtml(it.posicion)}</span>
              <span class="text-[10px] text-slate-400">${escapeHtml(it.fecha || '')}</span>
            </div>
            <div class="text-[11px] text-slate-600 mt-0.5 truncate">
              <b>${escapeHtml(it.marca || '')}</b> ${escapeHtml(it.diseno || '')} · ${escapeHtml(it.dimension || '')} · ${it.prof_cent || 0} mm · ${it.psi || 0} PSI
            </div>
            ${it.novedades ? `<div class="text-[10px] text-amber-700 font-semibold mt-0.5 truncate"><i class="fa-solid fa-triangle-exclamation mr-1"></i>${escapeHtml(it.novedades)}</div>` : ''}
          </div>
          <button type="button" onclick="eliminarItemColaOffline('${escapeHtml(it.dedup_key)}')" class="px-2.5 py-1.5 text-rose-600 hover:bg-rose-50 rounded-lg text-xs font-bold border border-rose-200 transition-all cursor-pointer" title="Eliminar de la cola">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
      `).join('');
    }

    async function eliminarItemColaOffline(dedup_key) {
      if (!confirm('¿Deseas descartar esta inspección de la cola local?')) return;
      await TireAnalyzeOfflineDB.eliminarPendiente(dedup_key);
      await renderizarListaColaOffline();
      await actualizarIndicadorConexionOffline();
      mostrarToast('Inspección eliminada de la cola local');
    }

    async function descargarRespaldoJSONOffline() {
      const items = await TireAnalyzeOfflineDB.obtenerPendientes();
      if (!items || items.length === 0) {
        mostrarToast('No hay inspecciones pendientes en la cola para respaldar');
        return;
      }
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(items, null, 2));
      const a = document.createElement('a');
      a.setAttribute("href", dataStr);
      a.setAttribute("download", `respaldo_patio_offline_${new Date().toISOString().slice(0, 10)}.json`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      mostrarToast(`💾 Respaldo .JSON descargado (${items.length} llantas)`);
    }

    async function sincronizarColaOffline() {
      const items = await TireAnalyzeOfflineDB.obtenerPendientes();
      if (!items || items.length === 0) {
        mostrarToast('No hay inspecciones pendientes por sincronizar');
        return;
      }
      if (!navigator.onLine) {
        mostrarToast('⚠️ Dispositivo sin conexión. La sincronización se ejecutará apenas recupere señal.', true);
        return;
      }

      const btn = document.getElementById('btnSincronizarColaModal');
      const barra = document.getElementById('barraProgresoSincronizacionOffline');
      const barraFill = document.getElementById('progresoSincronizacionFill');
      const barraTxt = document.getElementById('progresoSincronizacionTexto');

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Sincronizando...';
      }
      if (barra) barra.classList.remove('hidden');

      const tamanoLote = 5;
      let totalSinc = 0;
      let totalAct = 0;
      let listaRechazadas = [];
      const totalItems = items.length;

      try {
        for (let i = 0; i < totalItems; i += tamanoLote) {
          const lote = items.slice(i, i + tamanoLote);
          const res = await fetch('/api/inspecciones/sincronizar-lote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: lote })
          });
          if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || 'Error en servidor al sincronizar');
          }
          const data = await res.json();
          totalSinc += (data.sincronizadas || 0);
          totalAct += (data.actualizadas || 0);

          const rechKeys = new Set((data.rechazadas || []).map(r => r.dedup_key));
          for (const it of lote) {
            if (!rechKeys.has(it.dedup_key)) {
              await TireAnalyzeOfflineDB.eliminarPendiente(it.dedup_key);
            }
          }
          if (data.rechazadas && data.rechazadas.length > 0) {
            listaRechazadas.push(...data.rechazadas);
          }

          const procesados = Math.min(i + tamanoLote, totalItems);
          const pct = Math.round((procesados / totalItems) * 100);
          if (barraFill) barraFill.style.width = pct + '%';
          if (barraTxt) barraTxt.textContent = `${procesados} / ${totalItems} (${pct}%)`;
        }

        mostrarToast(`✅ Sincronización exitosa: ${totalSinc} insertadas, ${totalAct} actualizadas`);
        if (listaRechazadas.length > 0) {
          alert(`Atención: ${listaRechazadas.length} llanta(s) fueron rechazadas por candados de seguridad:\n` +
            listaRechazadas.map(r => `• ${r.placa} Pos.${r.posicion}: ${r.motivo}`).join('\n')
          );
        }
      } catch (err) {
        console.warn('[Sync] Error sincronizando cola:', err);
        mostrarToast('Error durante la sincronización: ' + (err.message || 'Error de red'), true);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-rotate mr-1.5"></i> Sincronizar Cola con Servidor';
        }
        if (barra) {
          setTimeout(() => barra.classList.add('hidden'), 2000);
        }
        await renderizarListaColaOffline();
        await actualizarIndicadorConexionOffline();
      }
    }

    window.addEventListener('online', () => {
      actualizarIndicadorConexionOffline();
      mostrarToast('🌐 Conexión restablecida. Sincronizando inspecciones de patio...');
      sincronizarColaOffline();
    });

    window.addEventListener('offline', () => {
      actualizarIndicadorConexionOffline();
      mostrarToast('📡 Modo Sin Señal activado. Las inspecciones se guardarán en el dispositivo.', false);
    });

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
          vistasPermitidas = esUsuarioJefatura() ? ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'] : (esUsuarioGerencia() ? ['basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas'] : ['patio']);
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
          descargarPaquetePatioOffline(false);
          actualizarIndicadorConexionOffline();
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
        // Sin nombre completo registrado se muestra el usuario (antes salía "undefined")
        lbl.textContent = `${usuarioActual.nombre_completo || usuarioActual.username || 'Usuario'} [${rolTag}]`;
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
          vistasPermitidas = esJefe ? ['patio', 'basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas', 'catalogos'] : (esGere ? ['basedatos', 'diagnostico', 'kpis', 'composicion', 'bodegas'] : ['patio']);
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
      // REGLA: solo el administrador carga el parque automotor de los clientes
      const subtabParque = document.getElementById('subtab-btn-parque');
      if (subtabParque) subtabParque.classList.toggle('hidden', !esAdmin);

      // REGLA: Gerencia es estrictamente de auditoría y análisis (solo lectura). No puede crear inspecciones.
      const btnNuevaInspBD = document.getElementById('btnNuevaInspBD');
      if (btnNuevaInspBD) btnNuevaInspBD.classList.toggle('hidden', esGere);

      // REGLA: Solo el Administrador puede realizar importaciones o ediciones de múltiples registros en Base de Inspecciones
      const btnImportarExcelBD = document.getElementById('btnImportarExcelBD');
      if (btnImportarExcelBD) btnImportarExcelBD.classList.toggle('hidden', !esAdmin);
      const thCheckTodos = document.getElementById('thCheckTodosBD');
      if (thCheckTodos) thCheckTodos.classList.toggle('hidden', !esAdmin);
      const btnEdicionMultipleBD = document.getElementById('btnEdicionMultipleBD');
      if (btnEdicionMultipleBD && !esAdmin) btnEdicionMultipleBD.classList.add('hidden');

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

