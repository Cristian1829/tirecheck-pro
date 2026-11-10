    // ==========================================
    // MODALES ACCESIBLES (auditoría H-28)
    // ==========================================
    // Los 37 modales de la aplicación se abren y cierran quitando o poniendo la clase «hidden». En vez de
    // cambiar cada función abrir/cerrar, este módulo observa esa clase y a todos les da lo mismo:
    //   - role="dialog", aria-modal y aria-labelledby (el primer título del modal);
    //   - al abrir: foco en el primer campo (o el primer control) y Tab / Shift+Tab sin salir del modal;
    //   - ESC cierra con el botón «Cerrar» del modal (no aplica al ingreso ni a los que ya tienen su ESC);
    //   - al cerrar: el foco vuelve al botón que lo abrió.
    (function () {
      const SIN_ESC = new Set(['modalLogin', 'modalGaleriaFotos']);
      const ENFOCABLES = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
      const origenFoco = new Map();
      let consecutivo = 0;

      function esVisible(el) {
        return !!el && !el.classList.contains('hidden') && getComputedStyle(el).display !== 'none';
      }

      function enfocables(modal) {
        return Array.from(modal.querySelectorAll(ENFOCABLES)).filter(el => el.offsetParent !== null || getComputedStyle(el).position === 'fixed');
      }

      function prepararModal(modal) {
        if (modal.dataset.dialogoListo) return;
        modal.dataset.dialogoListo = '1';
        if (!modal.hasAttribute('role')) modal.setAttribute('role', 'dialog');
        if (!modal.hasAttribute('aria-modal')) modal.setAttribute('aria-modal', 'true');
        if (!modal.hasAttribute('aria-labelledby') && !modal.hasAttribute('aria-label')) {
          const titulo = modal.querySelector('h1, h2, h3, h4');
          if (titulo) {
            if (!titulo.id) titulo.id = `tituloDialogo${++consecutivo}`;
            modal.setAttribute('aria-labelledby', titulo.id);
          }
        }
        let abierto = esVisible(modal);
        new MutationObserver(() => {
          const ahora = esVisible(modal);
          if (ahora === abierto) return;
          abierto = ahora;
          if (ahora) alAbrir(modal); else alCerrar(modal);
        }).observe(modal, { attributes: true, attributeFilter: ['class', 'style'] });
      }

      function alAbrir(modal) {
        const activo = document.activeElement;
        if (activo && activo !== document.body && !modal.contains(activo)) origenFoco.set(modal, activo);
        // Tras pintar: las funciones abrir* suelen llenar el modal justo después de mostrarlo
        setTimeout(() => {
          if (!esVisible(modal) || modal.contains(document.activeElement)) return;
          const lista = enfocables(modal);
          const campo = lista.find(el => /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName) && !el.readOnly);
          const destino = campo || lista.find(el => el.getAttribute('aria-label') !== 'Cerrar') || lista[0];
          if (destino) destino.focus({ preventScroll: false });
        }, 60);
      }

      function alCerrar(modal) {
        const origen = origenFoco.get(modal);
        origenFoco.delete(modal);
        if (origen && document.contains(origen) && typeof origen.focus === 'function') origen.focus();
      }

      function modalSuperior() {
        const abiertos = Array.from(document.querySelectorAll('[data-dialogo-listo]')).filter(esVisible);
        return abiertos.length ? abiertos[abiertos.length - 1] : null;
      }

      document.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab' && e.key !== 'Escape') return;
        const modal = modalSuperior();
        if (!modal) return;
        if (e.key === 'Escape') {
          if (SIN_ESC.has(modal.id)) return;
          const cerrar = modal.querySelector('button[aria-label="Cerrar"]');
          if (cerrar) { e.preventDefault(); cerrar.click(); }
          return;
        }
        const lista = enfocables(modal);
        if (!lista.length) return;
        const primero = lista[0], ultimo = lista[lista.length - 1];
        if (!modal.contains(document.activeElement)) { e.preventDefault(); primero.focus(); return; }
        if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
      });

      window.prepararModalAccesible = prepararModal;  // para modales creados después de cargar la página

      function prepararTodos() {
        document.querySelectorAll('[id^="modal"].fixed.inset-0').forEach(prepararModal);
      }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', prepararTodos);
      else prepararTodos();
    })();
