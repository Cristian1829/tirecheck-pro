// ============================================================================
// Interfaz de la suite (rediseño, fase 2): banner ocultable, panel lateral contraíble,
// menú del teléfono, barra de ruta y cliente activo.
// Solo observa y acompaña: no cambia navegarTab(), los permisos por rol ni ningún dato.
// ============================================================================
(function () {
  'use strict';

  const CLAVE_BANNER = 'tireanalyze_banner_visible';
  const CLAVE_PANEL = 'tireanalyze_panel_contraido';
  const $ = (id) => document.getElementById(id);
  const leer = (clave) => { try { return localStorage.getItem(clave); } catch (e) { return null; } };
  const guardar = (clave, valor) => { try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ } };
  const esEscritorio = () => window.matchMedia('(min-width: 1024px)').matches;

  // ---------------------------------------------------------------- Banner («Vista compacta»)
  function aplicarBanner(visible) {
    document.body.classList.toggle('ta-sin-banner', !visible);
    const btn = $('btnBanner');
    if (!btn) return;
    btn.setAttribute('aria-pressed', String(!visible));
    btn.title = visible ? 'Ocultar el banner de marca' : 'Mostrar el banner de marca';
    btn.innerHTML = visible
      ? '<i class="fa-solid fa-compress" aria-hidden="true"></i><span>Vista compacta</span>'
      : '<i class="fa-solid fa-expand" aria-hidden="true"></i><span>Mostrar banner</span>';
  }

  // ---------------------------------------------------------------- Panel contraíble (escritorio)
  function aplicarPanelContraido(contraido) {
    document.body.classList.toggle('ta-panel-contraido', contraido);
    const btn = $('btnContraerPanel');
    if (!btn) return;
    btn.setAttribute('aria-expanded', String(!contraido));
    btn.setAttribute('aria-label', contraido ? 'Expandir el panel' : 'Contraer el panel');
    btn.title = contraido ? 'Expandir el panel' : 'Contraer el panel';
  }

  // ---------------------------------------------------------------- Menú del teléfono y la tableta
  function abrirMenu() {
    document.body.classList.add('ta-menu-abierto');
    const btn = $('btnMenuMovil');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    const activo = document.querySelector('#panelNavegacion .nav-tab.active') || document.querySelector('#panelNavegacion .nav-tab');
    if (activo) setTimeout(() => activo.focus(), 50);
  }
  function cerrarMenu(devolverFoco) {
    if (!document.body.classList.contains('ta-menu-abierto')) return;
    document.body.classList.remove('ta-menu-abierto');
    const btn = $('btnMenuMovil');
    if (btn) {
      btn.setAttribute('aria-expanded', 'false');
      if (devolverFoco) btn.focus();
    }
  }

  // ---------------------------------------------------------------- Ruta: grupo / sección actual
  function actualizarRuta() {
    const activo = document.querySelector('#panelNavegacion .nav-tab.active');
    if (!activo) return;
    const grupo = activo.closest('.ta-nav-grupo');
    const texto = activo.querySelector('.ta-nav-texto');
    if ($('rutaGrupo') && grupo) $('rutaGrupo').textContent = grupo.dataset.grupo || '';
    if ($('rutaSeccion') && texto) $('rutaSeccion').textContent = texto.textContent.trim();
  }

  // Un grupo sin secciones permitidas para el perfil no muestra su título
  const botonVisible = (b) => !b.classList.contains('hidden') && b.style.display !== 'none';
  function actualizarGruposYAcciones() {
    document.querySelectorAll('#panelNavegacion .ta-nav-grupo').forEach(g => {
      g.classList.toggle('ta-vacio', ![...g.querySelectorAll('.nav-tab')].some(botonVisible));
    });
    const patio = $('nav-btn-patio');
    const nueva = $('btnNuevaInspRuta');
    if (nueva) nueva.hidden = !(patio && botonVisible(patio));
  }

  // ---------------------------------------------------------------- Usuario al pie del panel
  function actualizarUsuarioPanel() {
    const lbl = $('lblUsuarioActivo');
    if (!lbl || !$('lblUsuarioPanel')) return;
    const texto = lbl.textContent.replace(/\s+/g, ' ').trim();
    const m = texto.match(/^(.*?)\s*\[([^\]]+)\]\s*$/);
    $('lblUsuarioPanel').textContent = m ? m[1] : texto;
    const ROLES = { 'ADMIN': 'Administrador', 'JEFATURA LLANTAS': 'Jefatura de llantas', 'GERENCIA': 'Gerencia', 'INSPECTOR': 'Inspector' };
    const rol = m ? m[2].trim().toUpperCase() : '';
    $('lblRolPanel').textContent = ROLES[rol] || (rol ? rol.charAt(0) + rol.slice(1).toLowerCase() : '');
  }

  // ---------------------------------------------------------------- Estado de conexión en la barra de ruta (tableta y teléfono)
  // Copia el punto y, si hay algo pendiente o no hay señal, el texto del indicador del panel (que la app actualiza)
  function actualizarConexionRuta() {
    const dot = $('dotEstadoConexion'), lbl = $('lblTextoEstadoConexion'), ind = $('indicadorConexionRuta');
    if (!dot || !lbl || !ind) return;
    ind.querySelector('.ta-conexion-punto').className = 'ta-conexion-punto ' + dot.className;
    const enOrden = dot.classList.contains('bg-emerald-400');
    ind.querySelector('.ta-conexion-texto').textContent = enOrden ? '' : lbl.textContent.trim();
    ind.title = lbl.textContent.trim();
  }

  // ---------------------------------------------------------------- Cliente activo (el de la inspección de patio)
  function textoOpcion(sel) {
    // «__nuevo__» es la opción «+ Agregar nuevo valor…», no un cliente
    if (!sel || !sel.value || sel.value.startsWith('__')) return '';
    const op = sel.options[sel.selectedIndex];
    return (op ? op.textContent : sel.value).replace(/\s+/g, ' ').trim();
  }
  function actualizarChipCliente() {
    const chip = $('chipClienteActivo');
    if (!chip) return;
    const cliente = textoOpcion($('cliente'));
    chip.hidden = !cliente;
    $('chipClienteNombre').textContent = cliente;
    $('chipClienteSede').textContent = textoOpcion($('subcliente'));
    chip.title = cliente ? `Cliente de la inspección: ${chip.textContent.replace(/\s+/g, ' ').trim()}` : '';
  }

  // ---------------------------------------------------------------- «Nueva insp.» de la barra de ruta
  function nuevaInspeccionDesdeRuta() {
    const patioActivo = $('nav-btn-patio') && $('nav-btn-patio').classList.contains('active');
    if (!patioActivo) {
      if (typeof navegarTab === 'function') navegarTab('patio');
      return;
    }
    // En el patio hace lo mismo que el botón «Nueva Inspección» del formulario, pero pregunta antes si hay una placa digitada
    const placa = $('placa');
    if (placa && placa.value.trim() && !window.confirm('¿Empezar una nueva inspección? Se limpiará el formulario actual (lo ya guardado no se pierde).')) return;
    if (typeof limpiarTodoParaNuevaInspeccion === 'function') limpiarTodoParaNuevaInspeccion();
    actualizarChipCliente();
    const modulo = $('moduloCliente');
    if (modulo) modulo.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---------------------------------------------------------------- Alto del panel
  // Como en el prototipo, el pie del panel (usuario, conexión, «Mi clave») siempre queda a la vista:
  // mientras la barra superior y el banner ocupan parte de la pantalla, el panel mide solo lo que queda.
  let pendienteAlto = false;
  function ajustarAltoPanel() {
    pendienteAlto = false;
    const layout = $('layoutSuite');
    if (!layout) return;
    const arriba = Math.max(0, layout.getBoundingClientRect().top);
    document.documentElement.style.setProperty('--ta-alto-panel', `${Math.max(240, window.innerHeight - arriba)}px`);
  }
  function pedirAjusteAlto() {
    if (pendienteAlto) return;
    pendienteAlto = true;
    window.requestAnimationFrame(ajustarAltoPanel);
  }

  // ---------------------------------------------------------------- Botón «Ver Suite KPIs» (Diagnóstico)
  // El botón llamaba a esta función, que no estaba definida en ningún archivo, y por eso no hacía nada.
  // Abre «Trazabilidad y KPI» en la sub-pestaña pedida (1 = Inspección y parque).
  window.irAVistaKpisTab = function (numero) {
    if (typeof navegarTab === 'function') navegarTab('kpis');
    window.setTimeout(() => {
      if (typeof cambiarSubpestanaKpis === 'function') cambiarSubpestanaKpis(Number(numero) || 1);
      const vista = $('vista-kpis');
      if (vista && !vista.classList.contains('hidden')) window.scrollTo({ top: 0, behavior: 'smooth' });
    }, 60);
  };

  // ---------------------------------------------------------------- Arranque
  document.addEventListener('DOMContentLoaded', () => {
    aplicarBanner(leer(CLAVE_BANNER) !== '0');
    aplicarPanelContraido(leer(CLAVE_PANEL) === '1');

    const btnBanner = $('btnBanner');
    if (btnBanner) btnBanner.addEventListener('click', () => {
      const visible = document.body.classList.contains('ta-sin-banner');
      aplicarBanner(visible);
      guardar(CLAVE_BANNER, visible ? '1' : '0');
    });
    const btnContraer = $('btnContraerPanel');
    if (btnContraer) btnContraer.addEventListener('click', () => {
      const contraido = !document.body.classList.contains('ta-panel-contraido');
      aplicarPanelContraido(contraido);
      guardar(CLAVE_PANEL, contraido ? '1' : '0');
    });
    const btnMenu = $('btnMenuMovil');
    if (btnMenu) btnMenu.addEventListener('click', abrirMenu);
    const btnCerrar = $('btnCerrarMenuMovil');
    if (btnCerrar) btnCerrar.addEventListener('click', () => cerrarMenu(true));
    const fondo = $('fondoMenuMovil');
    if (fondo) fondo.addEventListener('click', () => cerrarMenu(true));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') cerrarMenu(true); });
    window.addEventListener('resize', () => { if (esEscritorio()) cerrarMenu(false); });

    // Al elegir una sección en el menú del teléfono, el menú se cierra (navegarTab ya cambió la vista)
    const panel = $('panelNavegacion');
    if (panel) panel.addEventListener('click', (e) => {
      if (e.target.closest('.nav-tab') && !esEscritorio()) cerrarMenu(false);
    });

    const nueva = $('btnNuevaInspRuta');
    if (nueva) nueva.addEventListener('click', nuevaInspeccionDesdeRuta);

    // Observa lo que ya hace la app (pestaña activa, permisos por rol, usuario) sin modificarla
    const botones = document.querySelectorAll('#panelNavegacion .nav-tab');
    const obsBotones = new MutationObserver(() => { actualizarRuta(); actualizarGruposYAcciones(); actualizarChipCliente(); });
    botones.forEach(b => obsBotones.observe(b, { attributes: true, attributeFilter: ['class', 'style'] }));
    const lbl = $('lblUsuarioActivo');
    if (lbl) new MutationObserver(actualizarUsuarioPanel).observe(lbl, { childList: true, characterData: true, subtree: true });

    ['cliente', 'subcliente'].forEach(id => {
      const sel = $(id);
      if (!sel) return;
      sel.addEventListener('change', actualizarChipCliente);
      // Las opciones llegan después (catálogo del servidor o paquete offline)
      new MutationObserver(actualizarChipCliente).observe(sel, { childList: true });
    });

    const dotCon = $('dotEstadoConexion'), lblCon = $('lblTextoEstadoConexion');
    if (dotCon) new MutationObserver(actualizarConexionRuta).observe(dotCon, { attributes: true, attributeFilter: ['class'] });
    if (lblCon) new MutationObserver(actualizarConexionRuta).observe(lblCon, { childList: true, characterData: true, subtree: true });
    actualizarConexionRuta();

    window.addEventListener('scroll', pedirAjusteAlto, { passive: true });
    window.addEventListener('resize', pedirAjusteAlto);
    if (btnBanner) btnBanner.addEventListener('click', pedirAjusteAlto);
    ajustarAltoPanel();

    actualizarRuta();
    actualizarGruposYAcciones();
    actualizarUsuarioPanel();
    actualizarChipCliente();
  });
})();
