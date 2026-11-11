    // Inicialización al cargar DOM
    window.addEventListener('DOMContentLoaded', () => {
      sincronizarSlotEspecificaciones();
      try {
        if (typeof renderizarBarraCheckboxesDiag === 'function') renderizarBarraCheckboxesDiag();
        if (typeof sincronizarVisibilidadTarjetasGraficos === 'function') sincronizarVisibilidadTarjetasGraficos();
      } catch (e) {
        console.warn('Error inicializando checkboxes de diagnóstico:', e);
      }
      document.getElementById('fecha').value = fechaLocalISO();
      const logueado = verificarSesionUsuario();
      if (logueado) {
        cargarCatalogos();
        validarVida();
        if (typeof cargarBaseInspecciones === 'function') cargarBaseInspecciones();
        descargarPaquetePatioOffline(false);
      }
      actualizarIndicadorConexionOffline();
    });
