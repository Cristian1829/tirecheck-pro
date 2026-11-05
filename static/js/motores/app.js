/**
 * Sistema de Control y Certificación de Motores (Tirak, Tractel, Blocstop)
 * Frontend SPA Application Logic
 */

// Escapa el texto que se pinta en pantalla
function esc(v) {
  return String(v == null ? '' : v).replace(/[&<>"'`]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '`': '&#96;' }[c]));
}

// Todas las peticiones van a /api/motores/... y una sesión vencida regresa al login
async function apiFetch(url, opciones) {
  const res = await fetch(url.replace(/^\/api\//, '/api/motores/'), Object.assign({ credentials: 'same-origin' }, opciones || {}));
  if (res.status === 401) Acceso.mostrarLogin();
  else if (res.status === 403 && res.headers.get('X-Requiere-Cambio-Clave')) Acceso.mostrarCambioClave(true);
  return res;
}

// Fecha y hora local del equipo, sin zona (lo que se imprime en los PDF es la hora del taller)
function fechaLocalISO(d = new Date()) {
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// Estado Global de la Aplicación
const App = {
  presets: { makes: [], models: [], customers: [] },
  stats: {},
  clientes: [],
  usuarios: [],
  signaturePads: {},
  activeMotorRowIndex: 0,
  currentMotorForCert: null,

  async init() {
    this.setupTabs();
    this.setupSignaturePads();
    await this.loadPresets();
    await this.loadStats();
    this.loadOrdersList();
    this.initIngresoForm();
    this.setupEventListeners();
  },

  // ================= TABS NAVIGATION =================
  setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        this.switchTab(targetTab);
      });
    });
  },

  switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

    const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    const activePane = document.getElementById(`tab-${tabId}`);

    if (activeBtn) activeBtn.classList.add('active');
    if (activePane) activePane.classList.add('active');

    // Acciones específicas al cambiar de pestaña
    if (tabId === 'dashboard') {
      this.loadStats();
      this.loadRecentActivity();
    } else if (tabId === 'salidas') {
      this.loadOrdersForDispatch();
      if (this.signaturePads.dispatchEmpresa) this.signaturePads.dispatchEmpresa.resize();
      if (this.signaturePads.dispatchCliente) this.signaturePads.dispatchCliente.resize();
    } else if (tabId === 'certificados') {
      this.loadMotorsForCertificates();
    } else if (tabId === 'historial') {
      this.loadGlobalHistory();
    } else if (tabId === 'clientes') {
      this.loadClients();
    } else if (tabId === 'usuarios') {
      this.loadUsuarios();
    } else if (tabId === 'ingreso') {
      if (this.signaturePads.dropoff) this.signaturePads.dropoff.resize();
      if (this.signaturePads.received) this.signaturePads.received.resize();
    }
  },

  // ================= SIGNATURE PADS =================
  setupSignaturePads() {
    // Ingreso
    const dropoffCanvas = document.getElementById('canvas-dropoff');
    const dropoffPlaceholder = document.getElementById('placeholder-dropoff');
    if (dropoffCanvas) {
      this.signaturePads.dropoff = new SmoothSignaturePad(dropoffCanvas, dropoffPlaceholder);
      document.getElementById('btn-clear-dropoff').addEventListener('click', () => this.signaturePads.dropoff.clear());
    }

    const receivedCanvas = document.getElementById('canvas-received');
    const receivedPlaceholder = document.getElementById('placeholder-received');
    if (receivedCanvas) {
      this.signaturePads.received = new SmoothSignaturePad(receivedCanvas, receivedPlaceholder);
      document.getElementById('btn-clear-received').addEventListener('click', () => this.signaturePads.received.clear());
    }

    // Salidas
    const dispEmpCanvas = document.getElementById('canvas-dispatch-emp');
    const dispEmpPlaceholder = document.getElementById('placeholder-dispatch-emp');
    if (dispEmpCanvas) {
      this.signaturePads.dispatchEmpresa = new SmoothSignaturePad(dispEmpCanvas, dispEmpPlaceholder);
      document.getElementById('btn-clear-disp-emp').addEventListener('click', () => this.signaturePads.dispatchEmpresa.clear());
    }

    const dispCliCanvas = document.getElementById('canvas-dispatch-cli');
    const dispCliPlaceholder = document.getElementById('placeholder-dispatch-cli');
    if (dispCliCanvas) {
      this.signaturePads.dispatchCliente = new SmoothSignaturePad(dispCliCanvas, dispCliPlaceholder);
      document.getElementById('btn-clear-disp-cli').addEventListener('click', () => this.signaturePads.dispatchCliente.clear());
    }

    // Redimensionar al cambiar tamaño de pantalla
    window.addEventListener('resize', () => {
      Object.values(this.signaturePads).forEach(pad => pad && pad.resize());
    });
  },

  // ================= PRESETS Y DATALISTS =================
  async loadPresets() {
    try {
      const res = await apiFetch('/api/motors/common/presets');
      if (res.ok) {
        this.presets = await res.json();
        this.populateDatalists();
      }
    } catch (e) {
      console.error('Error cargando presets:', e);
    }
  },

  populateDatalists() {
    // Clientes
    const custDatalist = document.getElementById('datalist-customers');
    if (custDatalist) {
      custDatalist.innerHTML = this.presets.customers.map(c => `<option value="${esc(c)}">`).join('');
    }
    // Makes (marcas y nombres de equipos completos para búsqueda inmediata)
    const makesDatalist = document.getElementById('datalist-makes');
    if (makesDatalist) {
      const allMakesOptions = Array.from(new Set([...this.presets.models, ...this.presets.makes]));
      makesDatalist.innerHTML = allMakesOptions.map(m => `<option value="${esc(m)}">`).join('');
    }
    // Models (los 13 modelos oficiales)
    const modelsDatalist = document.getElementById('datalist-models');
    if (modelsDatalist) {
      modelsDatalist.innerHTML = this.presets.models.map(m => `<option value="${esc(m)}">`).join('');
    }
  },

  // ================= DASHBOARD & STATS =================
  async loadStats() {
    try {
      const res = await apiFetch('/api/motors/dashboard/stats');
      if (res.ok) {
        const stats = await res.json();
        this.stats = stats;
        document.getElementById('stat-total-ordenes').innerText = stats.total_ordenes;
        document.getElementById('stat-ordenes-taller').innerText = stats.ordenes_en_taller;
        document.getElementById('stat-motores-taller').innerText = stats.motores_en_taller;
        document.getElementById('stat-certificados').innerText = stats.certificados_emitidos;

        // Actualizar badges en tabs
        const badgeTaller = document.getElementById('badge-taller-count');
        if (badgeTaller) badgeTaller.innerText = stats.motores_en_taller;
      }
    } catch (e) {
      console.error('Error cargando estadísticas:', e);
    }
  },

  async loadRecentActivity() {
    try {
      const res = await apiFetch('/api/orders/?limit=8');
      if (res.ok) {
        const orders = await res.json();
        const tbody = document.getElementById('dashboard-recent-orders');
        if (!tbody) return;

        if (orders.length === 0) {
          tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="text-align:center; padding: 2rem;">No hay órdenes registradas.</td></tr>`;
          return;
        }

        tbody.innerHTML = orders.map(ord => {
          let badgeClass = 'status-taller';
          if (ord.estado_orden === 'Entregado Total') badgeClass = 'status-entregado';
          else if (ord.estado_orden === 'Entregado Parcial') badgeClass = 'status-parcial';

          const dateStr = ord.date_in ? new Date(ord.date_in).toLocaleString() : 'N/A';
          return `
            <tr>
              <td><strong>${esc(ord.numero_orden)}</strong></td>
              <td>${esc(ord.company_name)}</td>
              <td>${ord.motores ? ord.motores.length : 0} motor(es)</td>
              <td>${dateStr}</td>
              <td><span class="status-badge ${badgeClass}">${esc(ord.estado_orden)}</span></td>
              <td>
                <div style="display:flex; gap:0.4rem;">
                  ${ord.pdf_ingreso_url ? `<button class="btn btn-outline btn-sm" onclick="App.viewPdf('${ord.pdf_ingreso_url}', 'Orden')">📄 PDF Ingreso</button>` : ''}
                  <button class="btn btn-primary btn-sm" onclick="App.viewOrderDetail(${ord.id})">🔍 Ver Detalle</button>
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }
    } catch (e) {
      console.error('Error cargando actividad reciente:', e);
    }
  },

  // ================= ACCESO DESDE CELULAR O TABLET =================
  showNetworkModal() {
    const url = window.location.origin + '/motores';
    const body = `
      <div style="text-align: center; padding: 1rem;">
        <p style="margin-bottom: 0.75rem; color: var(--gray-700); font-weight:600;">
          Apunta la cámara de tu teléfono al código QR para ingresar directamente:
        </p>
        <div style="margin: 1rem auto; padding: 0.75rem; background:white; display:inline-block; border-radius:var(--radius-md); box-shadow:var(--shadow-sm); border:1px solid var(--gray-300);">
          <img src="/api/motores/network-qr" alt="Código QR Móvil" style="width:200px; height:200px; display:block;">
        </div>
        <p style="font-size: 0.85rem; color: var(--gray-500); margin-bottom: 0.5rem;">
          O escribe esta dirección en el navegador de tu celular:
        </p>
        <div style="background: var(--gray-100); padding: 0.6rem; border-radius: var(--radius-md); font-family: monospace; font-size: 1.15rem; font-weight: 700; color: var(--primary); margin-bottom: 1rem; word-break: break-all;">
          ${esc(url)}
        </div>
      </div>
    `;
    this.openModal('Acceso Móvil / Tablet en Taller', body);
  },

  // ================= COMPRESIÓN DE IMÁGENES (CLIENT-SIDE) =================
  compressImage(file, maxWidth = 1200, quality = 0.8) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = (event) => {
        const img = new Image();
        img.src = event.target.result;
        img.onload = () => {
          let width = img.width;
          let height = img.height;

          if (width > maxWidth) {
            height = Math.round((height * maxWidth) / width);
            width = maxWidth;
          }

          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);

          // Obtener data URL comprimido JPEG
          const compressedDataUrl = canvas.toDataURL('image/jpeg', quality);
          resolve(compressedDataUrl);
        };
        img.onerror = (err) => reject(err);
      };
      reader.onerror = (err) => reject(err);
    });
  },

  // ================= MÓDULO A: INGRESO DE MOTORES =================
  initIngresoForm() {
    const container = document.getElementById('motor-items-container');
    if (container) {
      container.innerHTML = '';
      this.activeMotorRowIndex = 0;
      this.addMotorRow(); // Agregar al menos uno por defecto
    }

    const addBtn = document.getElementById('btn-add-motor-row');
    if (addBtn) {
      addBtn.onclick = () => this.addMotorRow();
    }

    // Configurar fecha por defecto a ahora
    const dateInput = document.getElementById('ingreso-date-in');
    if (dateInput && !dateInput.value) {
      dateInput.value = fechaLocalISO().slice(0, 16);
    }
  },

  addMotorRow() {
    this.activeMotorRowIndex++;
    const idx = this.activeMotorRowIndex;
    const container = document.getElementById('motor-items-container');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'motor-entry-card';
    row.id = `motor-row-${idx}`;
    row.innerHTML = `
      <div class="motor-card-header">
        <span class="motor-badge-num">Motor #${idx}</span>
        ${idx > 1 ? `<button type="button" class="btn btn-outline btn-sm text-danger" style="color:var(--danger); border-color:var(--danger);" onclick="App.removeMotorRow(${idx})">🗑️ Eliminar</button>` : ''}
      </div>
      
      <!-- Selector Rápido de Marca / Modelo Oficial -->
      <div class="form-group" style="background:#eff6ff; border:1px solid #bfdbfe; padding:0.6rem 0.85rem; border-radius:var(--radius-sm); margin-bottom:0.75rem;">
        <label style="color:#1e3a8a; font-weight:700; font-size:0.85rem; margin-bottom:0.25rem;">
          ⭐ Seleccionar Marca / Equipo Oficial (13 Modelos)
        </label>
        <select class="form-control motor-preset-select" style="font-weight:600; color:#1e3a8a; background:white;" onchange="App.onSelectMotorPreset(this, ${idx})">
          <option value="">-- Toque aquí para elegir el equipo de la lista --</option>
          <optgroup label="TIRAK">
            <option value="TIRAK XE 500P" data-make="Tirak" data-model="TIRAK XE 500P">TIRAK XE 500P</option>
            <option value="TIRAK XE 501 P+" data-make="Tirak" data-model="TIRAK XE 501 P+">TIRAK XE 501 P+</option>
            <option value="TIRAK XE 501 P SAFWAY" data-make="Tirak" data-model="TIRAK XE 501 P SAFWAY">TIRAK XE 501 P SAFWAY</option>
            <option value="TIRAK XE 501 PA1" data-make="Tirak" data-model="TIRAK XE 501 PA1">TIRAK XE 501 PA1</option>
            <option value="TIRAK XE 600P" data-make="Tirak" data-model="TIRAK XE 600P">TIRAK XE 600P</option>
            <option value="TIRAK LE 501P" data-make="Tirak" data-model="TIRAK LE 501P">TIRAK LE 501P</option>
            <option value="TIRAK TE 401P" data-make="Tirak" data-model="TIRAK TE 401P">TIRAK TE 401P</option>
            <option value="TIRAK XE 500 P+" data-make="Tirak" data-model="TIRAK XE 500 P+">TIRAK XE 500 P+</option>
          </optgroup>
          <optgroup label="SKYCLIMBER">
            <option value="SKYCLIMBER BALDOR 1000" data-make="Sky Climber" data-model="SKYCLIMBER BALDOR 1000">SKYCLIMBER BALDOR 1000</option>
            <option value="SKYCLIMBER COMPACT 1000" data-make="Sky Climber" data-model="SKYCLIMBER COMPACT 1000">SKYCLIMBER COMPACT 1000</option>
            <option value="SKYCLIMBER COMPACT 1250" data-make="Sky Climber" data-model="SKYCLIMBER COMPACT 1250">SKYCLIMBER COMPACT 1250</option>
            <option value="SKYCLIMBER LNX1000" data-make="Sky Climber" data-model="SKYCLIMBER LNX1000">SKYCLIMBER LNX1000</option>
          </optgroup>
          <optgroup label="SPIDER">
            <option value="SPIDER Z-MAC 1000" data-make="Spider" data-model="SPIDER Z-MAC 1000">SPIDER Z-MAC 1000</option>
          </optgroup>
          <option value="__OTRO__">Otro / Personalizado...</option>
        </select>
      </div>

      <div class="form-grid">
        <div class="form-group">
          <label>Marca (Make) *</label>
          <input type="text" class="form-control motor-make" list="datalist-makes" placeholder="Ej: Tirak, Sky Climber, Spider" required>
        </div>
        <div class="form-group">
          <label>Modelo (Model) *</label>
          <input type="text" class="form-control motor-model" list="datalist-models" placeholder="Ej: TIRAK XE 500P, COMPACT 1000" required>
        </div>
        <div class="form-group">
          <label>Número de Serie (Serial #) *</label>
          <input type="text" class="form-control motor-serial" placeholder="Ej: 7037 o LE-10492" required>
        </div>
      </div>
      <div class="form-grid" style="margin-top:0.5rem;">
        <div class="form-group" style="grid-column: 1 / -1;">
          <label>Observaciones de Recepción / Daños iniciales</label>
          <input type="text" class="form-control motor-notes" placeholder="Ej: Cable desgastado, palanca floja, suciedad por cemento...">
        </div>
      </div>
      <div class="form-group" style="margin-top:0.5rem;">
        <label>Foto de Ingreso (Obligatoria) 📷</label>
        <div class="photo-uploader" id="photo-box-${idx}">
          <input type="file" accept="image/*" capture="environment" id="photo-input-${idx}" onchange="App.handlePhotoUpload(event, ${idx})">
          <div id="photo-prompt-${idx}">
            <div style="font-size: 1.8rem; margin-bottom: 0.25rem;">📸</div>
            <p style="font-weight: 600; font-size: 0.85rem; color: var(--primary);">Tomar Foto con Cámara o Subir Archivo</p>
            <p style="font-size: 0.75rem; color: var(--gray-500);">Toca aquí para abrir la cámara o seleccionar imagen</p>
          </div>
          <img id="photo-preview-${idx}" class="photo-preview" alt="Vista previa">
        </div>
        <input type="hidden" id="photo-data-${idx}" class="motor-photo-data">
      </div>
    `;

    // Autocompletar Marca según el Modelo seleccionado
    const modelInput = row.querySelector('.motor-model');
    const makeInput = row.querySelector('.motor-make');
    if (modelInput && makeInput) {
      const updateMake = () => {
        const val = modelInput.value.trim().toUpperCase();
        if (App.presets.model_to_make && App.presets.model_to_make[val]) {
          makeInput.value = App.presets.model_to_make[val];
        } else if (val.startsWith('TIRAK')) {
          makeInput.value = 'Tirak';
        } else if (val.startsWith('SKYCLIMBER') || val.startsWith('SKY CLIMBER')) {
          makeInput.value = 'Sky Climber';
        } else if (val.startsWith('SPIDER')) {
          makeInput.value = 'Spider';
        }
      };
      modelInput.addEventListener('change', updateMake);
      modelInput.addEventListener('input', updateMake);
    }

    container.appendChild(row);
  },

  onSelectMotorPreset(selectEl, idx) {
    const selectedOption = selectEl.options[selectEl.selectedIndex];
    const row = document.getElementById(`motor-row-${idx}`);
    if (!row || !selectedOption) return;

    const makeInput = row.querySelector('.motor-make');
    const modelInput = row.querySelector('.motor-model');

    const makeVal = selectedOption.getAttribute('data-make');
    const modelVal = selectedOption.getAttribute('data-model');

    if (makeVal && modelVal) {
      if (makeInput) makeInput.value = makeVal;
      if (modelInput) modelInput.value = modelVal;
    } else if (selectEl.value === '__OTRO__') {
      if (makeInput) { makeInput.value = ''; makeInput.focus(); }
      if (modelInput) modelInput.value = '';
    }
  },

  removeMotorRow(idx) {
    const row = document.getElementById(`motor-row-${idx}`);
    if (row) row.remove();
  },

  async handlePhotoUpload(event, idx) {
    const file = event.target.files[0];
    if (!file) return;

    try {
      this.showToast('Comprimiendo imagen...', 'info');
      const compressedDataUrl = await this.compressImage(file, 1200, 0.8);

      const preview = document.getElementById(`photo-preview-${idx}`);
      const prompt = document.getElementById(`photo-prompt-${idx}`);
      const hiddenInput = document.getElementById(`photo-data-${idx}`);

      if (preview && prompt && hiddenInput) {
        preview.src = compressedDataUrl;
        preview.classList.add('visible');
        prompt.style.display = 'none';
        hiddenInput.value = compressedDataUrl;
        this.showToast('Foto cargada correctamente', 'success');
      }
    } catch (e) {
      console.error('Error al procesar foto:', e);
      this.showToast('Error procesando imagen', 'error');
    }
  },

  async submitIngresoForm(event) {
    event.preventDefault();

    const companyName = document.getElementById('ingreso-company').value.trim();
    const dateIn = document.getElementById('ingreso-date-in').value;
    const dropoffName = document.getElementById('ingreso-dropoff-name').value.trim() || 'Customer';
    const receivedName = document.getElementById('ingreso-received-name').value.trim() || 'Marino Trejos';
    const notes = document.getElementById('ingreso-notes').value.trim();

    if (!companyName) {
      this.showToast('Por favor ingrese el nombre del Cliente / Compañía', 'warning');
      return;
    }

    // Recolectar motores
    const motorRows = document.querySelectorAll('.motor-entry-card');
    if (motorRows.length === 0) {
      this.showToast('Debe agregar al menos un motor', 'warning');
      return;
    }

    const motores = [];
    for (const row of motorRows) {
      const make = row.querySelector('.motor-make').value.trim();
      const model = row.querySelector('.motor-model').value.trim();
      const serial = row.querySelector('.motor-serial').value.trim();
      const obs = row.querySelector('.motor-notes').value.trim();
      const photoData = row.querySelector('.motor-photo-data').value;

      if (!make || !model || !serial) {
        this.showToast('Por favor complete Marca, Modelo y Serial de todos los motores', 'warning');
        return;
      }
      if (!photoData) {
        this.showToast(`Falta la foto de ingreso del motor ${serial}`, 'warning');
        return;
      }

      motores.push({
        make: make.toUpperCase(),
        model: model.toUpperCase(),
        serial_number: serial.toUpperCase(),
        observaciones: obs,
        foto_ingreso_url: photoData || null
      });
    }

    // Firmas
    const firmaDropoff = this.signaturePads.dropoff ? this.signaturePads.dropoff.toDataURL() : null;
    const firmaReceived = this.signaturePads.received ? this.signaturePads.received.toDataURL() : null;
    if (!firmaDropoff || !firmaReceived) {
      this.showToast('Faltan firmas: se requieren la de quien entrega y la de quien recibe', 'warning');
      return;
    }

    const payload = {
      company_name: companyName.toUpperCase(),
      date_in: dateIn || fechaLocalISO(),
      dropoff_name: dropoffName.toUpperCase(),
      firma_dropoff: firmaDropoff,
      received_name: receivedName.toUpperCase(),
      firma_received: firmaReceived,
      notas: notes,
      motores: motores
    };

    const submitBtn = document.getElementById('btn-submit-ingreso');
    submitBtn.disabled = true;
    submitBtn.innerText = '⏳ Guardando y generando PDF...';

    try {
      const res = await apiFetch('/api/orders/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al guardar orden');
      }

      const createdOrder = await res.json();
      this.showToast(`¡Orden ${createdOrder.numero_orden} registrada con éxito!`, 'success');

      // Limpiar formulario
      document.getElementById('form-ingreso').reset();
      if (this.signaturePads.dropoff) this.signaturePads.dropoff.clear();
      if (this.signaturePads.received) this.signaturePads.received.clear();
      this.initIngresoForm();

      // Abrir visor de PDF
      if (createdOrder.pdf_ingreso_url) {
        this.viewPdf(createdOrder.pdf_ingreso_url, `Recibo de Ingreso - ${createdOrder.numero_orden}`);
      }

      // Actualizar datos
      this.loadStats();
      this.loadOrdersList();
    } catch (e) {
      console.error('Error guardando orden:', e);
      this.showToast(`Error: ${e.message}`, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = '💾 Guardar Ingreso y Generar PDF (Formato 1)';
    }
  },

  // ================= MÓDULO B: SALIDAS Y DESPACHOS =================
  async loadOrdersForDispatch() {
    try {
      const res = await apiFetch('/api/orders/?limit=100');
      if (!res.ok) return;
      const orders = await res.json();

      const select = document.getElementById('dispatch-order-select');
      if (!select) return;

      // Filtrar únicamente órdenes que tengan al menos 1 motor pendiente en taller
      const activeOrders = orders.filter(o => {
        if (o.estado_orden === 'Entregado Total') return false;
        if (o.motores && o.motores.length > 0) {
          return o.motores.some(m => m.estado_motor === 'En Taller');
        }
        return true;
      });

      select.innerHTML = '<option value="">-- Seleccione una orden con motores por despachar --</option>' +
        activeOrders.map(o => {
          const pendientes = o.motores ? o.motores.filter(m => m.estado_motor === 'En Taller').length : 0;
          const total = o.motores ? o.motores.length : 1;
          const info = pendientes === total ? `${total} en taller` : `${pendientes} de ${total} pendientes`;
          return `<option value="${o.id}">${esc(o.numero_orden)} - ${esc(o.company_name)} [${info}]</option>`;
        }).join('');

      // Limpiar contenedor de motores
      document.getElementById('dispatch-motors-list').innerHTML = `
        <div style="text-align: center; color: var(--gray-500); padding: 2rem;">
          Seleccione una orden arriba para ver los motores disponibles para despacho.
        </div>
      `;
    } catch (e) {
      console.error('Error cargando órdenes para despacho:', e);
    }
  },

  async onDispatchOrderSelected() {
    const select = document.getElementById('dispatch-order-select');
    const orderId = select.value;
    const container = document.getElementById('dispatch-motors-list');
    if (!orderId) {
      container.innerHTML = '<div style="text-align:center; color:var(--gray-500); padding:2rem;">Seleccione una orden.</div>';
      return;
    }

    try {
      const res = await apiFetch(`/api/orders/${orderId}`);
      if (!res.ok) return;
      const order = await res.json();

      const availableMotors = order.motores.filter(m => m.estado_motor === 'En Taller');
      const deliveredMotors = order.motores.filter(m => m.estado_motor === 'Entregado');

      if (availableMotors.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:2rem; color:var(--success); font-weight:600; background:#f0fdf4; border-radius:8px; border:1px solid #bbf7d0;">
            ✅ Todos los motores (${order.motores.length}) de esta orden ya han sido despachados y entregados.
          </div>
          ${deliveredMotors.length > 0 ? `
            <div style="margin-top:1.5rem; padding:1rem; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
              <h4 style="font-size:0.95rem; font-weight:700; color:#166534; margin-bottom:0.75rem;">Motores entregados (${deliveredMotors.length}):</h4>
              <div style="display:flex; flex-direction:column; gap:0.5rem;">
                ${deliveredMotors.map(m => `
                  <div style="background:white; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:0.6rem 0.8rem; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <strong>${esc(m.make)} - ${esc(m.model)}</strong>
                      <span style="font-size:0.8rem; color:#64748b; margin-left:0.5rem;">Serial: <b>${esc(m.serial_number)}</b></span>
                    </div>
                    <span class="status-badge status-entregado">✓ Entregado</span>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}
        `;
        return;
      }

      container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; flex-wrap:wrap; gap:0.5rem;">
          <h4 style="font-size:0.95rem; font-weight:700; color:var(--secondary);">
            📦 Motores pendientes por despachar (${availableMotors.length}):
          </h4>
          <button type="button" class="btn btn-outline btn-sm" onclick="App.toggleSelectAllDispatch(true)">Marcar Todos</button>
        </div>
        ${availableMotors.map((m, idx) => `
          <div class="motor-entry-card dispatch-motor-item" data-motor-id="${m.id}" style="background:white; border-left:4px solid var(--secondary); margin-bottom:0.85rem;">
            <div style="display:flex; align-items:flex-start; gap:0.75rem;">
              <input type="checkbox" class="dispatch-check" id="chk-disp-${m.id}" value="${m.id}" style="width:20px; height:20px; margin-top:0.25rem; accent-color:var(--secondary);" onchange="App.updateDispatchTypeBadge()">
              <div style="flex:1;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <strong style="font-size:0.95rem;">${esc(m.make)} - ${esc(m.model)}</strong>
                  <span class="status-badge status-taller">Serial: ${esc(m.serial_number)}</span>
                </div>
                <p style="font-size:0.8rem; color:var(--gray-600); margin:0.25rem 0;">${esc(m.observaciones || 'Sin notas especiales')}</p>
                
                <!-- Foto de Salida -->
                <div style="margin-top:0.75rem;">
                  <label style="font-size:0.8rem; font-weight:600; color:var(--gray-700);">Foto de Salida / Despacho (Obligatoria) 📷</label>
                  <div class="photo-uploader" style="min-height:90px;" id="dispatch-photo-box-${m.id}">
                    <input type="file" accept="image/*" capture="environment" onchange="App.handleDispatchPhotoUpload(event, ${m.id})">
                    <div id="dispatch-prompt-${m.id}">
                      <span style="font-size:1.2rem;">📸</span>
                      <span style="font-size:0.8rem; font-weight:600; color:var(--secondary); margin-left:0.4rem;">Tomar Foto de Salida</span>
                    </div>
                    <img id="dispatch-preview-${m.id}" class="photo-preview" style="height:90px;" alt="Vista previa salida">
                  </div>
                  <input type="hidden" id="dispatch-photo-data-${m.id}" class="dispatch-photo-val">
                </div>
              </div>
            </div>
          </div>
        `).join('')}

        <!-- Motores ya entregados previamente en la parte de abajo -->
        ${deliveredMotors.length > 0 ? `
          <div style="margin-top:1.5rem; padding:1rem; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
              <h4 style="font-size:0.92rem; font-weight:700; color:#166534; display:flex; align-items:center; gap:0.4rem; margin:0;">
                <span>✅</span> Motores Previamente Entregados en esta Orden (${deliveredMotors.length}):
              </h4>
              <span class="status-badge status-entregado" style="font-size:0.75rem;">${deliveredMotors.length} Despachado(s)</span>
            </div>
            <p style="font-size:0.8rem; color:#64748b; margin:0 0 0.75rem 0;">
              Estos motores ya fueron inspeccionados y despachados. Solo marque arriba el o los motores pendientes.
            </p>
            <div style="display:flex; flex-direction:column; gap:0.6rem;">
              ${deliveredMotors.map(m => `
                <div style="background:white; border:1px solid #e2e8f0; border-left:4px solid #16a34a; border-radius:6px; padding:0.65rem 0.85rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                  <div>
                    <div style="font-weight:700; font-size:0.9rem; color:#1e293b;">
                      ${esc(m.make)} - ${esc(m.model)}
                    </div>
                    <div style="font-size:0.8rem; color:#64748b; margin-top:0.15rem;">
                      Serial: <strong style="color:#0f172a;">${esc(m.serial_number)}</strong>
                      ${m.observaciones ? ` &bull; <i>${esc(m.observaciones)}</i>` : ''}
                    </div>
                  </div>
                  <div style="display:flex; align-items:center; gap:0.6rem;">
                    ${m.foto_salida_url ? `
                      <a href="${m.foto_salida_url}" target="_blank" title="Ver foto despacho">
                        <img src="${m.foto_salida_url}" style="height:44px; width:44px; object-fit:cover; border-radius:4px; border:1px solid #cbd5e1;" alt="Foto">
                      </a>
                    ` : '<span style="font-size:0.75rem; color:#94a3b8; font-style:italic;">Sin foto</span>'}
                    <span class="status-badge status-entregado" style="font-size:0.75rem;">✓ Entregado</span>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      `;

      this.updateDispatchTypeBadge();
    } catch (e) {
      console.error('Error cargando detalle de orden:', e);
    }
  },

  toggleSelectAllDispatch(checkAll) {
    const checks = document.querySelectorAll('.dispatch-check');
    checks.forEach(c => c.checked = checkAll);
    this.updateDispatchTypeBadge();
  },

  updateDispatchTypeBadge() {
    const allChecks = document.querySelectorAll('.dispatch-check');
    const checked = document.querySelectorAll('.dispatch-check:checked');
    const badge = document.getElementById('dispatch-type-indicator');
    if (!badge) return;

    if (checked.length === 0) {
      badge.innerHTML = '<span class="status-badge" style="background:#f1f5f9; color:#64748b;">Ningún motor seleccionado</span>';
    } else if (checked.length === allChecks.length) {
      badge.innerHTML = '<span class="status-badge status-entregado">⭐ Entrega TOTAL (Todos los motores)</span>';
    } else {
      badge.innerHTML = `<span class="status-badge status-parcial">📦 Entrega PARCIAL (${checked.length} de ${allChecks.length} motores)</span>`;
    }
  },

  async handleDispatchPhotoUpload(event, motorId) {
    const file = event.target.files[0];
    if (!file) return;

    try {
      this.showToast('Comprimiendo foto de salida...', 'info');
      const compressed = await this.compressImage(file, 1200, 0.8);
      const preview = document.getElementById(`dispatch-preview-${motorId}`);
      const prompt = document.getElementById(`dispatch-prompt-${motorId}`);
      const hidden = document.getElementById(`dispatch-photo-data-${motorId}`);

      if (preview && prompt && hidden) {
        preview.src = compressed;
        preview.classList.add('visible');
        prompt.style.display = 'none';
        hidden.value = compressed;
        this.showToast('Foto de salida cargada', 'success');
      }
    } catch (e) {
      console.error('Error procesando foto salida:', e);
      this.showToast('Error procesando foto', 'error');
    }
  },

  async submitDispatchForm(event) {
    event.preventDefault();

    const orderId = document.getElementById('dispatch-order-select').value;
    if (!orderId) {
      this.showToast('Seleccione una orden para despachar', 'warning');
      return;
    }

    const checkedBoxes = document.querySelectorAll('.dispatch-check:checked');
    if (checkedBoxes.length === 0) {
      this.showToast('Seleccione al menos un motor para despachar', 'warning');
      return;
    }

    const allChecks = document.querySelectorAll('.dispatch-check');
    const tipoEntrega = checkedBoxes.length === allChecks.length ? 'Total' : 'Parcial';

    const motoresDespacho = [];
    let faltaFoto = false;
    checkedBoxes.forEach(chk => {
      const motorId = parseInt(chk.value);
      const photoVal = document.getElementById(`dispatch-photo-data-${motorId}`).value;
      if (!photoVal) faltaFoto = true;
      motoresDespacho.push({
        motor_id: motorId,
        foto_salida_url: photoVal || null
      });
    });

    const firmaEmpresa = this.signaturePads.dispatchEmpresa ? this.signaturePads.dispatchEmpresa.toDataURL() : null;
    const firmaCliente = this.signaturePads.dispatchCliente ? this.signaturePads.dispatchCliente.toDataURL() : null;
    if (faltaFoto) {
      this.showToast('Falta la foto de salida de un motor seleccionado', 'warning');
      return;
    }
    if (!firmaEmpresa || !firmaCliente) {
      this.showToast('Faltan firmas: se requieren la del taller y la del cliente', 'warning');
      return;
    }

    const payload = {
      orden_id: parseInt(orderId),
      tipo_entrega: tipoEntrega,
      fecha_salida: fechaLocalISO(),
      entrega_empresa_name: (document.getElementById('dispatch-emp-name').value.trim() || 'MARINO TREJOS').toUpperCase(),
      firma_entrega_empresa: firmaEmpresa,
      recibe_cliente_name: (document.getElementById('dispatch-cli-name').value.trim() || 'CUSTOMER').toUpperCase(),
      firma_recibe_cliente: firmaCliente,
      notas: document.getElementById('dispatch-notes').value.trim(),
      motores_despacho: motoresDespacho
    };

    const submitBtn = document.getElementById('btn-submit-dispatch');
    submitBtn.disabled = true;
    submitBtn.innerText = '⏳ Procesando despacho y generando PDF...';

    try {
      const res = await apiFetch('/api/dispatches/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error procesando despacho');
      }

      const dispatchResult = await res.json();
      this.showToast(`¡Despacho ${tipoEntrega} registrado con éxito!`, 'success');

      // Limpiar formulario y firmas
      document.getElementById('form-dispatch').reset();
      if (this.signaturePads.dispatchEmpresa) this.signaturePads.dispatchEmpresa.clear();
      if (this.signaturePads.dispatchCliente) this.signaturePads.dispatchCliente.clear();
      this.loadOrdersForDispatch();
      document.getElementById('dispatch-type-indicator').innerHTML = '<span class="status-badge" style="background:#f1f5f9; color:#64748b;">Seleccione una orden</span>';

      // Abrir PDF de Salida
      if (dispatchResult.pdf_salida_url) {
        this.viewPdf(dispatchResult.pdf_salida_url, `Recibo de Salida ${tipoEntrega}`);
      }

      this.loadStats();
    } catch (e) {
      console.error('Error al despachar:', e);
      this.showToast(`Error: ${e.message}`, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = '🚚 Procesar Despacho y Generar PDF de Salida';
    }
  },

  // ================= MÓDULO C: CERTIFICADOS DE CALIDAD (BAJO DEMANDA) =================
  async loadMotorsForCertificates(search = '') {
    try {
      const url = search ? `/api/motors/?search=${encodeURIComponent(search)}` : '/api/motors/?limit=50';
      const res = await apiFetch(url);
      if (!res.ok) return;
      const motors = await res.json();

      const tbody = document.getElementById('cert-motors-table');
      if (!tbody) return;

      if (motors.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="text-align:center; padding:2rem;">No se encontraron motores.</td></tr>`;
        return;
      }

      tbody.innerHTML = motors.map(m => `
        <tr>
          <td><strong>${esc(m.serial_number)}</strong></td>
          <td>${esc(m.make)}</td>
          <td>${esc(m.model)}</td>
          <td>
            <span class="status-badge ${m.estado_motor === 'Entregado' ? 'status-entregado' : 'status-taller'}">
              ${esc(m.estado_motor)}
            </span>
          </td>
          <td>
            ${m.foto_ingreso_url ? `<img src="${m.foto_ingreso_url}" style="width:40px; height:32px; object-fit:cover; border-radius:4px; cursor:pointer;" onclick="App.zoomImage('${m.foto_ingreso_url}')">` : '<span style="color:var(--gray-400); font-size:0.75rem;">Sin foto</span>'}
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="App.openCertificateModal(${m.id})">
              📜 Generar Certificado de Calidad
            </button>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('Error cargando motores para certificados:', e);
    }
  },

  async openCertificateModal(motorId) {
    try {
      const res = await apiFetch(`/api/motors/${motorId}`);
      if (!res.ok) return;
      const motor = await res.json();
      this.currentMotorForCert = motor;
      document.getElementById('form-cert-quality').reset();

      // Precargar datos en modal
      document.getElementById('cert-motor-id').value = motor.id;
      document.getElementById('cert-customer-display').innerText = motor.company_name || 'Cliente';
      document.getElementById('cert-model-display').innerText = `${motor.make} ${motor.model}`;
      document.getElementById('cert-serial-display').innerText = motor.serial_number;
      document.getElementById('cert-blocstop-serial').value = `BS-${motor.serial_number}`;

      // Configurar automáticamente capacidades según el modelo
      const modelUpper = (motor.model || '').toUpperCase();
      let capacity = '1000';
      let overload = '1250 POUNDS (125%)';
      let secondaryModel = 'BLOCSTOP BSO 1000';

      if (modelUpper.includes('1250')) {
        capacity = '1250';
        overload = '1562 POUNDS (125%)';
        secondaryModel = modelUpper.includes('SKYCLIMBER') ? 'SKY-LOCK 1250' : 'BLOCSTOP BSO 1250';
      } else if (modelUpper.includes('700') || modelUpper.includes('701')) {
        capacity = '1500';
        overload = '1850 POUNDS (125%)';
        secondaryModel = 'BLOCSTOP BSO 1500';
      } else if (modelUpper.includes('600')) {
        capacity = '1300';
        overload = '1625 POUNDS (125%)';
        secondaryModel = 'BLOCSTOP BSO 1000';
      } else if (modelUpper.includes('SKYCLIMBER') || modelUpper.includes('SKY CLIMBER')) {
        secondaryModel = 'SKY-LOCK';
      }

      document.getElementById('cert-rated-load').value = capacity;
      document.getElementById('cert-overload-pounds').value = overload;
      document.getElementById('cert-blocstop-model').value = secondaryModel;
      document.getElementById('cert-blocstop-load').value = `${capacity} POUNDS`;
      document.getElementById('cert-blocstop-ltest').value = `${capacity} POUNDS Pass`;

      // Fechas por defecto (hoy y próximo servicio + 1 año)
      const today = new Date();
      const nextYear = new Date();
      nextYear.setFullYear(today.getFullYear() + 1);

      document.getElementById('cert-test-date').value = fechaLocalISO(today).split('T')[0];
      document.getElementById('cert-next-service').value = fechaLocalISO(nextYear).split('T')[0];

      // Abrir modal
      const modal = document.getElementById('modal-certificate');
      if (modal) modal.classList.add('active');
    } catch (e) {
      console.error('Error abriendo modal de certificado:', e);
    }
  },

  closeCertificateModal() {
    const modal = document.getElementById('modal-certificate');
    if (modal) modal.classList.remove('active');
  },

  setAllCertChecks(checked) {
    const checks = document.querySelectorAll('.cert-chk');
    checks.forEach(c => c.checked = checked);
  },

  async submitCertificateForm(event) {
    event.preventDefault();
    if (!this.currentMotorForCert) return;

    const sinAprobar = [...document.querySelectorAll('.cert-chk')].filter(c => !c.checked).length;
    if (sinAprobar && !confirm(`${sinAprobar} punto(s) de la inspección quedan SIN APROBAR y el certificado lo dirá en rojo. ¿Emitirlo así?`)) return;

    const motorId = parseInt(document.getElementById('cert-motor-id').value);
    const testCertNo = document.getElementById('cert-number-input').value.trim();
    const testDate = document.getElementById('cert-test-date').value;
    const nextService = document.getElementById('cert-next-service').value;
    const voltage = document.getElementById('cert-voltage').value;

    const payload = {
      motor_id: motorId,
      test_certificate_no: testCertNo || null,
      test_date: testDate ? `${testDate}T00:00:00` : fechaLocalISO(),
      next_service: nextService ? `${nextService}T00:00:00` : null,
      voltage: voltage,

      // Parámetros eléctricos
      start_capacitor: document.getElementById('cert-start-cap').value.trim() || '100 uF',
      vr_start: document.getElementById('cert-vr-start').value.trim() || '330 V',
      run_capacitor: document.getElementById('cert-run-cap').value.trim() || '40 uF',
      vr_run: document.getElementById('cert-vr-run').value.trim() || '450 V',
      k1: document.getElementById('cert-k1').value.trim() || '1.8',
      k2: document.getElementById('cert-k2').value.trim() || '1.8',
      k3: document.getElementById('cert-k3').value.trim() || '2.1',

      // Checks de inspección
      rectifier: document.getElementById('chk-rectifier').checked,
      brake_release_lever: document.getElementById('chk-brake-lever').checked,
      brake_function: document.getElementById('chk-brake-func').checked,
      normal_noise: document.getElementById('chk-noise').checked,
      emergency_pin_descend: document.getElementById('chk-pin').checked,
      brake_disc: document.getElementById('chk-disc').checked,
      stirrup_adapter: document.getElementById('chk-stirrup').checked,
      rated_load_test: document.getElementById('chk-load-test').checked,

      // Pruebas de carga y Blocstop
      rated_load_capacity: document.getElementById('cert-rated-load').value.trim() || '1000',
      overload_test_pounds: document.getElementById('cert-overload-pounds').value.trim() || '1250 POUNDS (125%)',
      blocstop_model: document.getElementById('cert-blocstop-model').value.trim() || 'BLOCSTOP BSO 1000',
      blocstop_serial: document.getElementById('cert-blocstop-serial').value.trim(),
      blocstop_rated_load: document.getElementById('cert-blocstop-load').value.trim() || '1000 POUNDS',
      blocstop_trigger_speed: document.getElementById('cert-trigger-speed').value.trim() || 'Testing Pass',
      blocstop_load_test: document.getElementById('cert-blocstop-ltest').value.trim() || '1000 POUNDS Pass',
      blocstop_control_descent: document.getElementById('cert-control-descent').value.trim() || 'Testing Pass',

      // Servicio y técnico
      service_description: document.getElementById('cert-service-desc').value.trim(),
      certified_by: document.getElementById('cert-certified-by').value.trim() || 'Marino Trejos | Cert#061821JV1'
    };

    const submitBtn = document.getElementById('btn-submit-cert');
    submitBtn.disabled = true;
    submitBtn.innerText = '⏳ Generando Certificado...';

    try {
      const res = await apiFetch('/api/certificates/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error generando certificado');
      }

      const certResult = await res.json();
      this.showToast(`¡Certificado ${certResult.test_certificate_no} emitido con éxito!`, 'success');

      this.closeCertificateModal();
      this.loadStats();

      // Abrir PDF de Certificado
      if (certResult.pdf_certificado_url) {
        this.viewPdf(certResult.pdf_certificado_url, `Certificado ${certResult.test_certificate_no}`);
      }
    } catch (e) {
      console.error('Error emitiendo certificado:', e);
      this.showToast(`Error: ${e.message}`, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = '📜 Guardar y Emitir Certificado de Calidad (Formato 2)';
    }
  },

  // ================= MÓDULO D: TRAZABILIDAD E HISTORIAL =================
  async loadGlobalHistory(search = '') {
    try {
      const url = search ? `/api/motors/?search=${encodeURIComponent(search)}` : '/api/motors/?limit=50';
      const res = await apiFetch(url);
      if (!res.ok) return;
      const motors = await res.json();

      const container = document.getElementById('history-motors-list');
      if (!container) return;

      if (motors.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:3rem; color:var(--gray-500);">
            No se encontraron registros de motores.
          </div>
        `;
        return;
      }

      container.innerHTML = motors.map(m => `
        <div class="card" style="margin-bottom:1rem; padding:1.25rem;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.75rem;">
            <div>
              <h3 style="font-size:1.1rem; font-weight:700; color:var(--dark);">
                ${esc(m.make)} - ${esc(m.model)}
              </h3>
              <p style="font-size:0.85rem; color:var(--gray-500);">Serial: <strong style="color:var(--primary);">${esc(m.serial_number)}</strong> | ID: #${m.id}</p>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center;">
              <span class="status-badge ${m.estado_motor === 'Entregado' ? 'status-entregado' : 'status-taller'}">
                ${esc(m.estado_motor)}
              </span>
              <button class="btn btn-outline btn-sm" onclick="App.viewMotorTimeline(${m.id})">🔍 Ficha de Vida</button>
              <button class="btn btn-secondary btn-sm" onclick="App.openCertificateModal(${m.id})">📜 Certificar</button>
            </div>
          </div>
          <div style="display:flex; gap:1.5rem; flex-wrap:wrap; font-size:0.825rem; color:var(--gray-600); border-top:1px solid var(--gray-200); padding-top:0.75rem;">
            <div><strong>Foto Ingreso:</strong> ${m.foto_ingreso_url ? `<a href="javascript:void(0)" onclick="App.zoomImage('${m.foto_ingreso_url}')">Ver Foto 📷</a>` : 'Sin foto'}</div>
            <div><strong>Foto Salida:</strong> ${m.foto_salida_url ? `<a href="javascript:void(0)" onclick="App.zoomImage('${m.foto_salida_url}')">Ver Foto 📷</a>` : 'Aún en taller'}</div>
            <div><strong>Notas:</strong> ${esc(m.observaciones || 'Ninguna')}</div>
          </div>
        </div>
      `).join('');
    } catch (e) {
      console.error('Error cargando historial:', e);
    }
  },

  async viewMotorTimeline(motorId) {
    try {
      const res = await apiFetch(`/api/motors/${motorId}`);
      if (!res.ok) return;
      const m = await res.json();

      let certsHtml = '<p style="color:var(--gray-500); font-size:0.85rem;">No se han emitido certificados para este motor aún.</p>';
      if (m.certificados && m.certificados.length > 0) {
        certsHtml = m.certificados.map(c => `
          <div style="background:var(--gray-50); border:1px solid var(--gray-200); padding:0.6rem 0.85rem; border-radius:var(--radius-sm); margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong>Certificado No. ${esc(c.test_certificate_no)}</strong>
              <div style="font-size:0.75rem; color:var(--gray-500);">Fecha: ${new Date(c.test_date).toLocaleDateString()} | Técnico: ${esc(c.certified_by)}</div>
            </div>
            ${c.pdf_certificado_url ? `<button class="btn btn-secondary btn-sm" onclick="App.viewPdf('${c.pdf_certificado_url}', 'Certificado')">📄 Ver PDF</button>` : ''}
          </div>
        `).join('');
      }

      const body = `
        <div style="padding:0.5rem;">
          <div style="display:flex; gap:1rem; margin-bottom:1.25rem; flex-wrap:wrap;">
            <div style="flex:1;">
              <h4 style="font-size:1.1rem; font-weight:700;">${esc(m.make)} ${esc(m.model)}</h4>
              <p style="color:var(--gray-600); font-size:0.9rem;">Número de Serie: <strong>${esc(m.serial_number)}</strong></p>
              <p style="color:var(--gray-600); font-size:0.9rem;">Cliente: <strong>${esc(m.company_name)}</strong></p>
              <p style="color:var(--gray-600); font-size:0.9rem;">Orden de Ingreso: <strong>${esc(m.numero_orden)}</strong></p>
              <p style="color:var(--gray-600); font-size:0.9rem;">Estado Actual: <span class="status-badge ${m.estado_motor === 'Entregado' ? 'status-entregado' : 'status-taller'}">${esc(m.estado_motor)}</span></p>
            </div>
            <div style="display:flex; gap:0.5rem;">
              ${m.foto_ingreso_url ? `<div><p style="font-size:0.75rem; font-weight:700;">Ingreso</p><img src="${m.foto_ingreso_url}" style="width:110px; height:80px; object-fit:cover; border-radius:4px; border:1px solid var(--gray-300); cursor:pointer;" onclick="App.zoomImage('${m.foto_ingreso_url}')"></div>` : ''}
              ${m.foto_salida_url ? `<div><p style="font-size:0.75rem; font-weight:700;">Salida</p><img src="${m.foto_salida_url}" style="width:110px; height:80px; object-fit:cover; border-radius:4px; border:1px solid var(--gray-300); cursor:pointer;" onclick="App.zoomImage('${m.foto_salida_url}')"></div>` : ''}
            </div>
          </div>
          <hr style="margin:1rem 0; border:0; border-top:1px solid var(--gray-200);">
          <h5 style="font-size:0.95rem; font-weight:700; margin-bottom:0.5rem;">Certificados de Calidad Emitidos:</h5>
          ${certsHtml}
        </div>
      `;

      this.openModal(`Trazabilidad de Motor: ${esc(m.serial_number)}`, body);
    } catch (e) {
      console.error('Error cargando trazabilidad:', e);
    }
  },

  async viewOrderDetail(orderId) {
    try {
      const res = await apiFetch(`/api/orders/${orderId}`);
      if (!res.ok) return;
      const o = await res.json();

      const motorsHtml = o.motores.map((m, idx) => `
        <div style="background:var(--gray-50); border:1px solid var(--gray-200); padding:0.75rem; border-radius:var(--radius-sm); margin-bottom:0.5rem;">
          <div style="display:flex; justify-content:space-between;">
            <strong>#${idx + 1} - ${esc(m.make)} ${esc(m.model)} (Serial: ${esc(m.serial_number)})</strong>
            <span class="status-badge ${m.estado_motor === 'Entregado' ? 'status-entregado' : 'status-taller'}">${esc(m.estado_motor)}</span>
          </div>
          <p style="font-size:0.8rem; color:var(--gray-600); margin:0.25rem 0;">${esc(m.observaciones || 'Sin notas')}</p>
          <div style="display:flex; gap:0.5rem; margin-top:0.4rem;">
            ${m.foto_ingreso_url ? `<button class="btn btn-outline btn-sm" onclick="App.zoomImage('${m.foto_ingreso_url}')">📷 Foto Ingreso</button>` : ''}
            ${m.foto_salida_url ? `<button class="btn btn-outline btn-sm" onclick="App.zoomImage('${m.foto_salida_url}')">📷 Foto Salida</button>` : ''}
            <button class="btn btn-secondary btn-sm" onclick="App.openCertificateModal(${m.id})">📜 Certificar</button>
          </div>
        </div>
      `).join('');

      const body = `
        <div style="padding:0.5rem;">
          <div style="margin-bottom:1rem;">
            <p><strong>Compañía / Cliente:</strong> ${esc(o.company_name)}</p>
            <p><strong>Fecha Ingreso:</strong> ${new Date(o.date_in).toLocaleString()}</p>
            <p><strong>Estado:</strong> ${esc(o.estado_orden)}</p>
            <p><strong>Entrega (Drop off):</strong> ${esc(o.dropoff_name || 'N/A')}</p>
            <p><strong>Recibido Taller:</strong> ${esc(o.received_name || 'Marino Trejos')}</p>
            ${o.pdf_ingreso_url ? `<div style="margin-top:0.5rem;"><button class="btn btn-primary btn-sm" onclick="App.viewPdf('${o.pdf_ingreso_url}', 'Orden')">📄 Ver PDF de Ingreso</button></div>` : ''}
          </div>
          <h5 style="font-weight:700; margin-bottom:0.5rem;">Motores de la Orden (${o.motores.length}):</h5>
          ${motorsHtml}
        </div>
      `;

      this.openModal(`Detalle de Orden: ${esc(o.numero_orden)}`, body);
    } catch (e) {
      console.error('Error cargando orden:', e);
    }
  },

  // ================= VISOR DE PDF =================
  viewPdf(pdfUrl, title = 'Documento') {
    const iframeHtml = `
      <div style="width:100%; height:75vh; display:flex; flex-direction:column;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
          <span style="font-size:0.85rem; color:var(--gray-600);">${esc(title)}</span>
          <a href="${pdfUrl}" target="_blank" download class="btn btn-primary btn-sm">💾 Descargar Archivo PDF</a>
        </div>
        <iframe src="${pdfUrl}#toolbar=1" style="width:100%; height:100%; border:1px solid var(--gray-300); border-radius:var(--radius-sm);" frameborder="0"></iframe>
      </div>
    `;
    this.openModal(title, iframeHtml);
  },

  // ================= MODALES Y ZOOM =================
  openModal(title, contentHtml) {
    let modal = document.getElementById('generic-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'generic-modal';
      modal.className = 'modal-backdrop';
      modal.innerHTML = `
        <div class="modal-dialog">
          <div class="modal-header">
            <h3 id="generic-modal-title"></h3>
            <button type="button" class="close-btn" onclick="App.closeGenericModal()">&times;</button>
          </div>
          <div class="modal-body" id="generic-modal-body"></div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    document.getElementById('generic-modal-title').innerText = title;
    document.getElementById('generic-modal-body').innerHTML = contentHtml;
    modal.classList.add('active');
  },

  closeGenericModal() {
    const modal = document.getElementById('generic-modal');
    if (modal) modal.classList.remove('active');
  },

  zoomImage(imgUrl) {
    const content = `
      <div style="text-align:center; padding:1rem;">
        <img src="${imgUrl}" style="max-width:100%; max-height:70vh; border-radius:var(--radius-md); box-shadow:var(--shadow-md);">
      </div>
    `;
    this.openModal('Visualización de Imagen', content);
  },

  // ================= TOAST NOTIFICATIONS =================
  showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '❌';
    else if (type === 'warning') icon = '⚠️';

    const iconoEl = document.createElement('span');
    iconoEl.textContent = icon;
    const textoEl = document.createElement('span');
    textoEl.textContent = message;
    toast.append(iconoEl, ' ', textoEl);
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease-out';
      setTimeout(() => toast.remove(), 300);
    }, 3800);
  },

  // ================= MÓDULO E: DIRECTORIO Y GESTIÓN DE CLIENTES =================
  async loadClients(search = '') {
    try {
      const url = search ? `/api/clients/?search=${encodeURIComponent(search)}` : '/api/clients/';
      const res = await apiFetch(url);
      if (!res.ok) return;
      const clients = await res.json();
      this.clientes = clients;

      const tbody = document.getElementById('clients-table-body');
      if (!tbody) return;

      if (clients.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--gray-500);">No se encontraron clientes registrados.</td></tr>`;
        return;
      }

      tbody.innerHTML = clients.map(c => `
        <tr>
          <td><span style="font-family:monospace; font-weight:700; color:var(--primary); font-size:0.85rem;">${esc(c.id)}</span></td>
          <td><strong style="color:var(--dark); font-size:0.95rem;">${esc(c.company_name)}</strong></td>
          <td>${c.contacto_principal ? esc(c.contacto_principal) : '<span style="color:var(--gray-400); font-size:0.8rem;">-</span>'}</td>
          <td>${c.email ? `<a href="mailto:${esc(c.email)}" style="color:var(--primary); text-decoration:none;">${esc(c.email)}</a>` : '<span style="color:var(--gray-400); font-size:0.8rem;">-</span>'}</td>
          <td>${c.phone ? esc(c.phone) : '<span style="color:var(--gray-400); font-size:0.8rem;">-</span>'}</td>
          <td><span style="font-size:0.8rem; color:var(--gray-600);">${esc(c.address || '-')}</span></td>
          <td style="text-align:center;">
            <div style="display:inline-flex; gap:0.35rem;">
              <button type="button" class="btn btn-outline btn-sm" onclick="App.openClientModal('${esc(c.id)}')" title="Editar cliente">
                ✏️ Editar
              </button>
              <button type="button" class="btn btn-outline btn-sm" style="color:var(--danger); border-color:var(--danger);" onclick="App.deleteClient('${esc(c.id)}')" title="Eliminar cliente">
                🗑️
              </button>
            </div>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('Error cargando clientes:', e);
    }
  },

  async openClientModal(clientId = null) {
    const modal = document.getElementById('modal-client');
    const titleEl = document.getElementById('client-modal-title');
    const idInput = document.getElementById('client-id-input');
    const nameInput = document.getElementById('client-name-input');
    const contactInput = document.getElementById('client-contact-input');
    const emailInput = document.getElementById('client-email-input');
    const phoneInput = document.getElementById('client-phone-input');
    const addressInput = document.getElementById('client-address-input');

    if (clientId) {
      titleEl.innerText = 'Editar Datos de Cliente';
      idInput.readOnly = true;
      idInput.style.backgroundColor = '#f1f5f9';
      try {
        const res = await apiFetch(`/api/clients/${clientId}`);
        if (res.ok) {
          const c = await res.json();
          idInput.value = c.id;
          nameInput.value = c.company_name;
          contactInput.value = c.contacto_principal || '';
          emailInput.value = c.email || '';
          phoneInput.value = c.phone || '';
          addressInput.value = c.address || '';
        }
      } catch (e) {
        console.error('Error obteniendo cliente:', e);
      }
    } else {
      titleEl.innerText = 'Nuevo Cliente';
      idInput.readOnly = false;
      idInput.style.backgroundColor = 'white';
      idInput.value = '';
      nameInput.value = '';
      contactInput.value = '';
      emailInput.value = '';
      phoneInput.value = '';
      addressInput.value = '';
    }

    if (modal) modal.classList.add('active');
  },

  closeClientModal() {
    const modal = document.getElementById('modal-client');
    if (modal) modal.classList.remove('active');
  },

  async saveClient(event) {
    event.preventDefault();
    const idInput = document.getElementById('client-id-input');
    const clientId = idInput.value.trim();
    const isEdit = idInput.readOnly;

    const payload = {
      company_name: document.getElementById('client-name-input').value.trim().toUpperCase(),
      contacto_principal: document.getElementById('client-contact-input').value.trim().toUpperCase() || null,
      email: document.getElementById('client-email-input').value.trim() || null,
      phone: document.getElementById('client-phone-input').value.trim() || null,
      address: document.getElementById('client-address-input').value.trim() || null,
    };

    if (!payload.company_name) {
      this.showToast('El nombre de la empresa es obligatorio', 'warning');
      return;
    }

    const saveBtn = document.getElementById('btn-save-client');
    saveBtn.disabled = true;
    saveBtn.innerText = 'Guardando...';

    try {
      let res;
      if (isEdit) {
        res = await apiFetch(`/api/clients/${clientId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        if (clientId) payload.id = clientId;
        res = await apiFetch('/api/clients/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al guardar cliente');
      }

      const saved = await res.json();
      this.showToast(`Cliente "${saved.company_name}" guardado exitosamente`, 'success');
      this.closeClientModal();
      this.loadClients();
      await this.loadPresets(); // Actualizar datalists de órdenes

      // Si estábamos en ingreso y el campo está visible, preseleccionar este cliente
      const ingresoComp = document.getElementById('ingreso-company');
      if (ingresoComp && !ingresoComp.value) {
        ingresoComp.value = saved.company_name;
      }
    } catch (e) {
      console.error('Error guardando cliente:', e);
      this.showToast(`Error: ${e.message}`, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerText = '💾 Guardar Cliente';
    }
  },

  async deleteClient(clientId) {
    const companyName = (this.clientes.find(c => c.id === clientId) || {}).company_name || clientId;
    if (!confirm(`¿Está seguro de que desea eliminar al cliente "${companyName}" (ID: ${clientId})?`)) {
      return;
    }

    try {
      const res = await apiFetch(`/api/clients/${clientId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Error al eliminar cliente');
      this.showToast(`Cliente "${companyName}" eliminado`, 'info');
      this.loadClients();
      await this.loadPresets();
    } catch (e) {
      console.error('Error eliminando cliente:', e);
      this.showToast(`Error eliminando cliente: ${e.message}`, 'error');
    }
  },

  // ================= USUARIOS DE MOTORES (SOLO ADMINISTRADOR) =================
  async loadUsuarios() {
    const res = await apiFetch('/api/usuarios');
    if (!res.ok) return;
    this.usuarios = await res.json();
    const yo = Acceso.usuario ? Acceso.usuario.username : '';
    document.getElementById('usuarios-body').innerHTML = this.usuarios.map(u => `
      <tr>
        <td><strong>${esc(u.username)}</strong></td>
        <td>${esc(u.nombre || '-')}</td>
        <td>${u.rol === 'admin' ? 'Administrador' : 'Técnico'}</td>
        <td><span class="status-badge ${u.activo ? 'status-entregado' : 'status-parcial'}">${u.activo ? 'Activo' : 'Inactivo'}</span></td>
        <td>
          <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
            <button type="button" class="btn btn-outline btn-sm" onclick="App.restablecerClave(${u.id})">🔑 Restablecer clave</button>
            ${u.username === yo ? '' : `<button type="button" class="btn btn-outline btn-sm" onclick="App.alternarUsuario(${u.id})">${u.activo ? 'Desactivar' : 'Activar'}</button>`}
          </div>
        </td>
      </tr>
    `).join('');
  },

  async crearUsuario(event) {
    event.preventDefault();
    const clave = document.getElementById('usr-clave').value;
    const res = await apiFetch('/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: document.getElementById('usr-username').value.trim(),
        nombre: document.getElementById('usr-nombre').value.trim(),
        rol: document.getElementById('usr-rol').value,
        clave_nueva: clave
      })
    });
    if (!res.ok) {
      const err = await res.json();
      this.showToast(err.detail || 'No se pudo crear el usuario', 'error');
      return;
    }
    document.getElementById('form-usuario').reset();
    this.showToast('Usuario creado. Deberá cambiar la clave al ingresar.', 'success');
    this.loadUsuarios();
  },

  async alternarUsuario(id) {
    const u = this.usuarios.find(x => x.id === id);
    if (!u) return;
    const res = await apiFetch(`/api/usuarios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ activo: !u.activo })
    });
    if (!res.ok) {
      const err = await res.json();
      this.showToast(err.detail || 'No se pudo actualizar', 'error');
    }
    this.loadUsuarios();
  },

  async restablecerClave(id) {
    const u = this.usuarios.find(x => x.id === id);
    if (!u) return;
    const clave = prompt(`Clave temporal para ${u.username} (deberá cambiarla al ingresar):`);
    if (!clave) return;
    const res = await apiFetch(`/api/usuarios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clave_nueva: clave })
    });
    if (!res.ok) {
      const err = await res.json();
      this.showToast(err.detail || 'No se pudo restablecer', 'error');
      return;
    }
    this.showToast('Clave restablecida. Sus sesiones abiertas se cerraron.', 'success');
  },

  // ================= LISTAS AUXILIARES =================
  async loadOrdersList() {
    this.loadRecentActivity();
  },

  setupEventListeners() {
    // Buscadores
    const certSearch = document.getElementById('cert-search-input');
    if (certSearch) {
      let timeout = null;
      certSearch.addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => this.loadMotorsForCertificates(e.target.value.trim()), 300);
      });
    }

    const histSearch = document.getElementById('hist-search-input');
    if (histSearch) {
      let timeout = null;
      histSearch.addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => this.loadGlobalHistory(e.target.value.trim()), 300);
      });
    }

    const clientSearch = document.getElementById('client-search-input');
    if (clientSearch) {
      let timeout = null;
      clientSearch.addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => this.loadClients(e.target.value.trim()), 300);
      });
    }
  }
};

// ================= ACCESO: LOGIN, CAMBIO DE CLAVE Y SALIDA =================
const Acceso = {
  usuario: null,
  appIniciada: false,

  _ver(id) {
    ['vista-login', 'vista-cambio', 'vista-app'].forEach(v => { document.getElementById(v).hidden = v !== id; });
  },

  _error(id, texto) {
    const el = document.getElementById(id);
    el.textContent = texto || '';
    el.classList.toggle('visible', !!texto);
  },

  mostrarLogin() {
    this.usuario = null;
    this._ver('vista-login');
    this._error('login-error', '');
  },

  mostrarCambioClave(obligatorio) {
    this._ver('vista-cambio');
    this._error('cambio-error', '');
    document.getElementById('cambio-aviso').hidden = !obligatorio;
    document.getElementById('cambio-cancelar').hidden = !!obligatorio;
  },

  async entrarApp() {
    this._ver('vista-app');
    document.getElementById('nav-usuario').textContent = this.usuario.nombre || this.usuario.username;
    document.getElementById('tab-btn-usuarios').hidden = this.usuario.rol !== 'admin';
    if (!this.appIniciada) {
      this.appIniciada = true;
      await App.init();
    }
    App.switchTab('dashboard');
  },

  async arrancar() {
    const res = await fetch('/api/motores/me', { credentials: 'same-origin' });
    if (!res.ok) return this.mostrarLogin();
    this.usuario = (await res.json()).usuario;
    if (this.usuario.debe_cambiar_clave) return this.mostrarCambioClave(true);
    return this.entrarApp();
  },

  async login(event) {
    event.preventDefault();
    this._error('login-error', '');
    const boton = document.getElementById('login-boton');
    boton.disabled = true;
    try {
      const res = await fetch('/api/motores/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: document.getElementById('login-usuario').value.trim(),
          password: document.getElementById('login-clave').value
        })
      });
      const datos = await res.json();
      if (!res.ok) return this._error('login-error', datos.detail || 'No se pudo ingresar');
      document.getElementById('form-login').reset();
      this.usuario = datos.usuario;
      if (this.usuario.debe_cambiar_clave) return this.mostrarCambioClave(true);
      return this.entrarApp();
    } catch (e) {
      this._error('login-error', 'Sin conexión con el servidor. Intente de nuevo.');
    } finally {
      boton.disabled = false;
    }
  },

  async cambiarClave(event) {
    event.preventDefault();
    this._error('cambio-error', '');
    const nueva = document.getElementById('cambio-nueva').value;
    if (nueva !== document.getElementById('cambio-repetir').value) {
      return this._error('cambio-error', 'Las dos contraseñas nuevas no coinciden.');
    }
    const res = await fetch('/api/motores/mi-cuenta/cambiar-clave', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clave_actual: document.getElementById('cambio-actual').value, clave_nueva: nueva })
    });
    const datos = await res.json();
    if (!res.ok) return this._error('cambio-error', datos.detail || 'No se pudo cambiar la contraseña');
    document.getElementById('form-cambio').reset();
    this.usuario = datos.usuario;
    App.showToast('Contraseña actualizada', 'success');
    return this.entrarApp();
  },

  async salir() {
    await fetch('/api/motores/logout', { method: 'POST', credentials: 'same-origin' });
    this.mostrarLogin();
  }
};

document.addEventListener('DOMContentLoaded', () => {
  Acceso.arrancar();
});

window.App = App;
window.Acceso = Acceso;
