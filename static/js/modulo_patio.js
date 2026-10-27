    // ==========================================
    // FUNCIONES DEL MOTOR DE PATIO Y CAPTURA
    // ==========================================
    function asignarValorSelect(selectId, valor) {
      const sel = document.getElementById(selectId);
      if (!sel || valor === undefined || valor === null || valor === '') return;
      let valStr = String(valor).trim();
      if (selectId === 'marca' || selectId === 'diseno' || selectId === 'dimension' || selectId === 'banda_reen') {
        valStr = valStr.toUpperCase();
      }
      let opt = Array.from(sel.options).find(o => o.value.trim().toUpperCase() === valStr.toUpperCase());
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
          let valLimpio = nuevo.trim();
          if (sel.id === 'marca' || sel.id === 'diseno' || sel.id === 'dimension' || sel.id === 'banda_reen') {
            valLimpio = valLimpio.toUpperCase();
          }
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
                body: JSON.stringify({ cliente: cli.toUpperCase(), marca: valLimpio.toUpperCase() })
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

      let marcas = null;
      try {
        const res = await fetchConTimeoutPatio(url, {}, 3500);
        if (res.ok) {
          marcas = await res.json();
        }
      } catch (err) {}

      if (!marcas) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat) {
            if (cliente && !mostrarTodas && cat.marcas_por_cliente && cat.marcas_por_cliente[cliente]) {
              marcas = cat.marcas_por_cliente[cliente];
            } else if (cat.catalogos_campos && cat.catalogos_campos.marcas) {
              marcas = cat.catalogos_campos.marcas;
            }
          }
        } catch (eDb) {}
      }
      if (!marcas) return;

      try {
        const unicos = [];
        const vistos = new Set();
        (marcas || []).forEach(m => {
          const norm = String(m || '').trim().toUpperCase();
          if (norm && !vistos.has(norm)) {
            vistos.add(norm);
            unicos.push(norm);
          }
        });

        const placeholder = cliente && !mostrarTodas
          ? `ej. MICHELIN (Marcas de ${cliente})`
          : `ej. MICHELIN (Catálogo completo de marcas)`;

        let html = `<option value="" disabled ${!valorPrevio ? 'selected' : ''} class="text-slate-400 font-normal">${placeholder}</option>`;

        if (mostrarTodas && cliente) {
          html += `<option value="__solo_cliente__" class="font-bold text-emerald-700 bg-emerald-50">🔍 Volver a marcas frecuentes de ${cliente}</option>`;
        }

        unicos.forEach(m => {
          const isSel = (valorPrevio && valorPrevio.trim().toUpperCase() === m);
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
      let items = null;

      try {
        const res = await fetchConTimeoutPatio(endpoint, {}, 3500);
        if (res.ok) {
          items = await res.json();
        }
      } catch(e) {}

      if (!items) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.catalogos_campos) {
            const cc = cat.catalogos_campos;
            if (endpoint.includes('campo=cliente')) {
              items = cc.clientes || [];
            } else if (endpoint.includes('campo=subcliente')) {
              const urlObj = new URL('http://dummy.com' + endpoint);
              const cliParam = urlObj.searchParams.get('cliente') || document.getElementById('cliente')?.value?.trim();
              items = (cc.subclientes_por_cliente && cliParam && cc.subclientes_por_cliente[cliParam]) ? cc.subclientes_por_cliente[cliParam] : [];
            } else if (endpoint.includes('campo=dimension')) {
              items = cc.dimensiones || [];
            } else if (endpoint.includes('campo=marca')) {
              items = cc.marcas || [];
            } else if (endpoint.includes('campo=diseno')) {
              const urlObj = new URL('http://dummy.com' + endpoint);
              const marcaParam = (urlObj.searchParams.get('marca') || document.getElementById('marca')?.value || '').trim();
              if (marcaParam && marcaParam !== '__nuevo__' && !marcaParam.includes('(Seleccionar')) {
                const marcaNorm = marcaParam.toUpperCase();
                const setDisenos = new Set();

                // 1. Del diccionario precargado disenos_por_marca (catálogo + histórico)
                if (cc.disenos_por_marca) {
                  for (const [mk, dList] of Object.entries(cc.disenos_por_marca)) {
                    if (mk.trim().toUpperCase() === marcaNorm && Array.isArray(dList)) {
                      dList.forEach(d => { if (d) setDisenos.add(String(d).trim().toUpperCase()); });
                    }
                  }
                }

                // 2. Del catálogo de modelos offline
                if (Array.isArray(cat.modelos)) {
                  cat.modelos.forEach(m => {
                    if (m && String(m.marca || '').trim().toUpperCase() === marcaNorm && m.diseno) {
                      setDisenos.add(String(m.diseno).trim().toUpperCase());
                    }
                  });
                }

                // 3. De posiciones previas de vehículos offline
                if (cat.vehiculos_perfil) {
                  Object.values(cat.vehiculos_perfil).forEach(perfil => {
                    if (perfil && Array.isArray(perfil.posiciones_previas)) {
                      perfil.posiciones_previas.forEach(pos => {
                        if (pos && String(pos.marca || '').trim().toUpperCase() === marcaNorm && pos.diseno) {
                          setDisenos.add(String(pos.diseno).trim().toUpperCase());
                        }
                      });
                    }
                  });
                }

                // 4. De la cola offline local (inspecciones recién guardadas offline)
                try {
                  const pendientes = await TireAnalyzeOfflineDB.obtenerPendientes();
                  if (Array.isArray(pendientes)) {
                    pendientes.forEach(p => {
                      if (p && String(p.marca || '').trim().toUpperCase() === marcaNorm && p.diseno) {
                        setDisenos.add(String(p.diseno).trim().toUpperCase());
                      }
                    });
                  }
                } catch(ePend) {}

                // Filtrado estricto: SÓLO los diseños asociados a esta marca
                items = Array.from(setDisenos).sort();
                // OJO: Si se especificó marca, NUNCA caer en cc.disenos para evitar mezclar marcas
              } else {
                // Solo si NO se especificó marca, mostrar catálogo global
                items = cc.disenos || [];
              }
            } else if (endpoint.includes('campo=banda')) {
              items = cc.bandas || [];
            }
          }
        } catch(eDb) {}
      }

      if (items) {
        try {
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
        } catch(ePop) {}
      }
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

      let ops = null;
      try {
        const resOps = await fetchConTimeoutPatio('/api/operaciones', {}, 3500);
        if (resOps.ok) ops = await resOps.json();
      } catch(e) {}
      if (!ops) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.operaciones) ops = cat.operaciones;
        } catch(eDb) {}
      }
      if (ops) {
        const selOp = document.getElementById('tipo_operacion');
        if (selOp) {
          selOp.innerHTML = ops.map(op => `<option value="${op}">${op}</option>`).join('');
          if (seleccionarOp) selOp.value = seleccionarOp;
        }
      }

      let tips = null;
      try {
        const resTips = await fetchConTimeoutPatio('/api/tipologias', {}, 3500);
        if (resTips.ok) tips = await resTips.json();
      } catch(e) {}
      if (!tips) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.tipologias) tips = cat.tipologias;
        } catch(eDb) {}
      }
      if (tips) {
        const selTip = document.getElementById('tipologia');
        if (selTip) {
          selTip.innerHTML = tips.map(t => `<option value="${t.nombre}">${t.nombre}</option>`).join('');
          if (seleccionarTip) selTip.value = seleccionarTip;
          cambioTipologia();
        }
      }
    }

    async function poblarDatalist(elementId, endpoint) {
      // Wrapper de compatibilidad hacia atrás
      const idCampo = elementId.replace(/^dl_/, '').replace(/s$/, '');
      if (document.getElementById(idCampo)?.tagName === 'SELECT') {
        return poblarSelect(idCampo, endpoint, `Seleccionar ${idCampo}...`);
      }
      try {
        const res = await fetchConTimeoutPatio(endpoint, {}, 3500);
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
      let d = null;
      try {
        const res = await fetchConTimeoutPatio(`/api/limite-cliente?cliente=${encodeURIComponent(cli)}`, {}, 3500);
        if (res.ok) {
          d = await res.json();
        }
      } catch(e) {}

      if (!d) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.limites) {
            const limEncontrado = cat.limites.find(l => (l.cliente || '').trim().toUpperCase() === cli.toUpperCase());
            if (limEncontrado) {
              d = { limite_retiro_mm: limEncontrado.limite_retiro_mm, tipo_licencia: limEncontrado.tipo_licencia || 'LIGHT' };
            }
          }
        } catch(eDb) {}
      }

      if (d) {
        const mm = d.limite_retiro_mm || 3.0;
        document.getElementById('lblMmRetiroCliente').textContent = fmtDec(Number(mm), 1);
        document.getElementById('lblMmAlerta').textContent = fmtDec(Number(mm), 1);
        if (d.tipo_licencia) {
          clienteLicenciaCaptura = d.tipo_licencia;
          window.clienteLicenciaCaptura = d.tipo_licencia;
        }
        // Sincronizar el panel de taller en patio con el licenciamiento del cliente
        const posSel = document.getElementById('posicion')?.value;
        if (posSel && typeof actualizarPanelTallerPosicion === 'function') {
          actualizarPanelTallerPosicion(posSel);
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
      let d = null;
      try {
        const res = await fetchConTimeoutPatio(`/api/esquema?tipologia=${encodeURIComponent(tip)}`, {}, 3500);
        if (res.ok) {
          d = await res.json();
        }
      } catch (e) {}

      if (!d) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.tipologias) {
            const match = cat.tipologias.find(t => t.nombre === tip);
            if (match) {
              d = match;
            }
          }
        } catch(eDb) {}
      }

      if (d) {
        esquemaTipologiaCache = d.esquema;
        window.tipologiaPermiteReencaucheCache = !!d.permite_reencauche_direccion;
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
        aplicarRestriccionEjeDireccional(posActual);
      }
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
      const optsReencauche = selVida ? Array.from(selVida.querySelectorAll('option')).filter(o => /^R\d+$/.test(o.value)) : [];
      const badge = document.getElementById('badgeDireccionalOriginal');
      const permiteReen = (window.tipologiaPermiteReencaucheCache === true);

      if (esDir && !permiteReen) {
        optsReencauche.forEach(o => { o.disabled = true; o.classList.add('text-slate-400'); });
        if (selVida && esVidaReencauche(selVida.value)) {
          selVida.value = 'Original';
          validarVida();
        }
        if (badge) {
          badge.classList.remove('hidden');
          badge.className = "mt-1 text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1 flex items-center space-x-1.5";
          badge.innerHTML = `<i class="fa-solid fa-shield-halved text-amber-600"></i><span>Eje Direccional: Por norma solo se permite Original.</span>`;
        }
      } else {
        optsReencauche.forEach(o => { o.disabled = false; o.classList.remove('text-slate-400'); });
        if (badge) {
          if (esDir && permiteReen) {
            badge.classList.remove('hidden');
            badge.className = "mt-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-1 flex items-center space-x-1.5";
            badge.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-600"></i><span>Eje Direccional: Tipología autorizada para Reencauche.</span>`;
          } else {
            badge.classList.add('hidden');
          }
        }
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

      let d = null;
      try {
        const res = await fetchConTimeoutPatio(`/api/vehiculo-perfil?placa=${encodeURIComponent(placa)}`, {}, 3500);
        if (res.ok) {
          d = await res.json();
        }
      } catch (err) {}

      if (!d) {
        try {
          const veh = await TireAnalyzeOfflineDB.obtenerVehiculo(placa);
          if (veh) {
            d = {
              encontrado: true,
              placa: veh.placa,
              tipologia: veh.tipologia,
              cliente: veh.cliente,
              subcliente: veh.subcliente,
              tipo_operacion: veh.tipo_operacion,
              ultimo_km: veh.ultimo_km || 0,
              dimension: veh.dimension,
              ultima_fecha_inspeccion: veh.ultima_fecha_inspeccion || '',
              fecha_minima_permitida: veh.fecha_minima_permitida || '',
              en_periodo_restringido: Boolean(veh.en_periodo_restringido),
              ultima_marca: veh.ultima_marca || '',
              ultimo_diseno: veh.ultimo_diseno || ''
            };
          }
        } catch(eDb) {}
      }

      const placaActual = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      if (placaActual !== placa) return;

      if (d) {
        // Combinar con kilometraje o datos de la cola pendiente offline si los hay
        try {
          const pendientes = await TireAnalyzeOfflineDB.obtenerTodasPendientes();
          const itemsPlaca = pendientes.filter(p => p.placa && p.placa.trim().toUpperCase() === placa);
          itemsPlaca.forEach(it => {
            const kmIt = parseFloat(it.kilometraje) || 0;
            if (kmIt > (d.ultimo_km || 0)) d.ultimo_km = kmIt;
          });
        } catch(eDb) {}

        perfilVehiculoActual = d;
        aplicarUnidadPlacaPatio();
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
      } else {
        const b = document.getElementById('badgePlacaVinculada');
        if (b) b.classList.add('hidden');
        desbloquearTipologia();
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
          const pendientes = await TireAnalyzeOfflineDB.obtenerTodasPendientes();
          const itemsPlaca = pendientes.filter(p => p.placa && p.placa.trim().toUpperCase() === placa);
          if (itemsPlaca.length > 0) {
            const ult = itemsPlaca[itemsPlaca.length - 1];
            if (ult.marca) marca = ult.marca;
            if (ult.diseno) diseno = ult.diseno;
            if (ult.dimension) dimension = ult.dimension;
          }
        } catch (e) {}

        if (!marca || !diseno) {
          try {
            const veh = await TireAnalyzeOfflineDB.obtenerVehiculo(placa);
            if (veh) {
              marca = marca || veh.ultima_marca || '';
              diseno = diseno || veh.ultimo_diseno || '';
              dimension = dimension || veh.dimension || '';
            }
          } catch(e) {}
        }
      }

      if (!marca || !diseno) {
        try {
          const resp = await fetchConTimeoutPatio(`/api/inspecciones/ultima-marca-diseno?placa=${encodeURIComponent(placa)}`, {}, 3500);
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

      let d = null;
      try {
        let url = `/api/llanta-por-cliente?numero_interno=${encodeURIComponent(num)}`;
        if (cli && cli !== '__nuevo__') url += `&cliente=${encodeURIComponent(cli)}`;
        if (placa) url += `&placa=${encodeURIComponent(placa)}`;

        const res = await fetchConTimeoutPatio(url, {}, 3500);
        if (res.ok) {
          d = await res.json();
        }
      } catch (err) {}

      if (!d) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.llantas_catalogo_cliente) {
            const keyDirecta = `${(cli || '').toUpperCase()}|||${num}`;
            if (cat.llantas_catalogo_cliente[keyDirecta]) {
              d = { encontrado: true, datos: cat.llantas_catalogo_cliente[keyDirecta] };
            } else {
              for (const [k, v] of Object.entries(cat.llantas_catalogo_cliente)) {
                if (k.endsWith(`|||${num}`)) {
                  d = { encontrado: true, datos: v };
                  break;
                }
              }
            }
          }
        } catch(eDb) {}
      }

      try {
        if (d) {
          const numActual = (document.getElementById('numero_interno')?.value || '').trim().toUpperCase();
          if (numActual !== num) return;

          if (d.encontrado && d.datos) {
            const lt = d.datos;
            const bLlanta = document.getElementById('badgeLlantaCliente');
            if (bLlanta) bLlanta.classList.remove('hidden');

            const bHist = document.getElementById('badgeHistorialPrevia');
            if (bHist) {
              bHist.classList.remove('hidden');
              bHist.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i>Llanta de ${lt.cliente || 'Flota'} (Pos ${lt.ult_posicion || 'ant'}${lt.ult_prof_min ? ' • ' + fmtDec(lt.ult_prof_min, 1) + ' mm' : ''})`;
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
            const vidaLt = vidaExactaLlanta(vLt, lt.banda_reen);
            const esReenLt = vidaLt !== 'Original';
            asignarValorSelect('vida', vidaLt);
            if (lt.banda_reen && esReenLt) {
              asignarValorSelect('banda_reen', lt.banda_reen);
            }
            validarVida();
            if (lt.prof_inicial && (!document.getElementById('prof_inicial').value || document.getElementById('prof_inicial').value === '0')) {
              document.getElementById('prof_inicial').value = lt.prof_inicial;
            }
            await autoCompletarProfInicial();
            const posVal = parseInt(document.getElementById('posicion')?.value) || 1;
            await actualizarPanelTallerPosicion(posVal);
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

      let d = null;
      let esDeColaPendiente = false;

      // 1. Revisar si la posición ya fue registrada en la cola local pendiente (Modo Offline)
      try {
        const pendientes = await TireAnalyzeOfflineDB.obtenerTodasPendientes();
        const itemCola = pendientes.find(item => (item.placa || '').toUpperCase() === placa && parseInt(item.posicion) === pos);
        if (itemCola) {
          d = { encontrado: true, datos: itemCola };
          esDeColaPendiente = true;
          posicionesInspeccionadasPlaca.add(pos);
        }
      } catch (eDb) {}

      // 2. Si no estaba en cola, consultar al servidor con timeout rápido
      if (!d) {
        try {
          const res = await fetchConTimeoutPatio(`/api/inspeccion-anterior?placa=${encodeURIComponent(placa)}&posicion=${pos}`, {}, 3500);
          if (res.ok) {
            d = await res.json();
          }
        } catch(eNet) {}
      }

      // 3. Si no hay conexión o falló el endpoint, buscar en vehiculos_offline (posiciones_previas)
      if (!d) {
        try {
          const veh = await TireAnalyzeOfflineDB.obtenerVehiculo(placa);
          if (veh && veh.posiciones_previas && veh.posiciones_previas[String(pos)]) {
            d = { encontrado: true, datos: veh.posiciones_previas[String(pos)] };
          }
        } catch (eDb) {}
      }

      try {
        if (d) {
          if (token !== idInspeccionActiva) return;
          const placaFin = (document.getElementById('placa')?.value || '').trim().toUpperCase();
          if (!placaFin || placaFin !== placa) return;

          // Si esta posición ya fue inspeccionada en la sesión actual
          const yaInspeccionadaHoy = posicionesInspeccionadasPlaca.has(pos) || esDeColaPendiente;

          if (d.encontrado && d.datos) {
            datosInspeccionAnterior = d.datos;
            if (d.datos.marca) cacheUltimaMarcaVehiculo = d.datos.marca;
            if (d.datos.diseno) cacheUltimoDisenoVehiculo = d.datos.diseno;
            if (d.datos.dimension) cacheUltimaDimensionVehiculo = d.datos.dimension;
            const badgeHist = document.getElementById('badgeHistorialPrevia');
            if (badgeHist) {
              badgeHist.classList.remove('hidden');
              badgeHist.innerHTML = esDeColaPendiente 
                ? '<i class="fa-solid fa-cloud-arrow-up mr-1 text-blue-500"></i>En Cola Offline: ' + (d.datos.numero_interno || 'S/N')
                : '<i class="fa-solid fa-clock-rotate-left mr-1"></i>Previa: ' + (d.datos.numero_interno || 'S/N');
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
              const vidaDato = vidaExactaLlanta(vDato, d.datos.banda_reen);
              const esReenDato = vidaDato !== 'Original';
              asignarValorSelect('vida', vidaDato);
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
              await actualizarPanelTallerPosicion(pos);
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
                const vidaPos = vidaExactaLlanta(vDatoPos, d.datos.banda_reen);
                const esReenPos = vidaPos !== 'Original';
                asignarValorSelect('vida', vidaPos);
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
              await actualizarPanelTallerPosicion(pos);

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
        const res = await fetchConTimeoutPatio(url, {}, 3500);
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
        }
      } catch (e) {}

      // Fusionar siempre las posiciones guardadas en cola local de IndexedDB
      try {
        const pendientes = await TireAnalyzeOfflineDB.obtenerTodasPendientes();
        const plNorm = placa.trim().toUpperCase();
        pendientes.forEach(item => {
          if ((item.placa || '').trim().toUpperCase() === plNorm) {
            const pNum = parseInt(item.posicion);
            if (!isNaN(pNum)) {
              posicionesInspeccionadasPlaca.add(pNum);
              if (item.novedades && item.novedades.trim().length > 0) {
                posicionesConNovedadPlaca.set(pNum, item.novedades.trim());
              }
            }
          }
        });
      } catch (errDb) {}

      if (esquemaTipologiaCache) renderizarChasisEjes(esquemaTipologiaCache, listaPosicionesActual);
      renderizarBotonesPosicion(listaPosicionesActual, esquemaTipologiaCache);
      actualizarBarraPosicionMobile(parseInt(document.getElementById('posicion').value) || 1);
    }

    // Unidad de medida de la placa: kilómetros u horas de motor (se elige solo al crear la placa)
    function unidadPlacaPatio() {
      if (perfilVehiculoActual && perfilVehiculoActual.encontrado && perfilVehiculoActual.unidad_medida) {
        return String(perfilVehiculoActual.unidad_medida).toUpperCase() === 'HORAS' ? 'HORAS' : 'KM';
      }
      return document.getElementById('unidad_medida_placa')?.value === 'HORAS' ? 'HORAS' : 'KM';
    }

    function aplicarUnidadPlacaPatio() {
      const placaNueva = !(perfilVehiculoActual && perfilVehiculoActual.encontrado);
      const sel = document.getElementById('unidad_medida_placa');
      if (sel) sel.classList.toggle('hidden', !placaNueva);
      const horas = unidadPlacaPatio() === 'HORAS';
      const lbl = document.getElementById('lblKilometraje');
      if (lbl) lbl.textContent = horas ? 'Horómetro (horas)' : 'Kilometraje / Odóm.';
      const lblM = document.getElementById('lblKmMontaje');
      if (lblM) lblM.textContent = horas ? 'Horas al montaje' : 'Km de Montaje';
      const inp = document.getElementById('kilometraje');
      if (inp) inp.placeholder = horas ? 'ej. 4500' : 'ej. 125000';
    }

    function validarVida() {
      const pos = parseInt(document.getElementById('posicion')?.value) || 1;
      const selVida = document.getElementById('vida');
      if (selVida) {
        // Vacío = pendiente de elegir (no se asume Original); solo se aceptan Original y R1, R2…
        if (selVida.value && selVida.value !== 'Original' && !/^R\d+$/.test(selVida.value)) {
          selVida.value = '';
        }
        if (esVidaReencauche(selVida.value) && esPosicionDireccionalActual(pos) && !window.tipologiaPermiteReencaucheCache) {
          selVida.value = 'Original';
          mostrarToast('⛔ En eje direccional solo se permite condición Original por seguridad vial.', true);
        }
      }
      const vida = selVida ? selVida.value : 'Original';
      const boxBanda = document.getElementById('box_banda');
      if (boxBanda) {
        if (esVidaReencauche(vida)) {
          boxBanda.classList.remove('hidden');
          poblarSelect('banda_reen', '/api/valores-campo?campo=banda_reen', 'ej. BDM Bandag (Seleccionar banda)');
        } else {
          boxBanda.classList.add('hidden');
        }
      }
    }

    async function alCambiarMarcaMobile() {
      const m = (document.getElementById('marca')?.value || '').trim();
      const selDis = document.getElementById('diseno');
      if (m && m !== '__nuevo__' && !m.includes('(Seleccionar')) {
        await poblarSelect('diseno', `/api/valores-campo?campo=diseno&marca=${encodeURIComponent(m)}`, `ej. Diseños de ${m}`);
      } else {
        if (selDis) {
          selDis.innerHTML = '<option value="" disabled selected class="text-slate-400 font-normal">Primero selecciona una marca...</option><option value="__nuevo__" class="font-bold text-blue-600 bg-blue-50">+ Agregar nuevo valor...</option>';
          selDis.value = '';
        }
      }
      await autoCompletarProfInicial();
      const posVal = parseInt(document.getElementById('posicion')?.value) || 1;
      await actualizarPanelTallerPosicion(posVal);
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

    // Al elegir el diseño/modelo, completa la dimensión con la medida de ese modelo en el catálogo.
    // Si el modelo existe en varias medidas y la actual es una de ellas, se respeta; si no, se usa la primera.
    async function autoCompletarDimensionModelo() {
      const m = (document.getElementById('marca')?.value || '').trim();
      const d = (document.getElementById('diseno')?.value || '').trim();
      if (!d || d === '__nuevo__' || d.includes('(Seleccionar')) return;
      const mValida = m && m !== '__nuevo__' && !m.includes('(Seleccionar');

      let dims = [];
      try {
        const res = await fetchConTimeoutPatio(`/api/dimensiones-modelo?marca=${encodeURIComponent(mValida ? m : '')}&diseno=${encodeURIComponent(d)}`, {}, 3500);
        if (res.ok) dims = (await res.json()).dimensiones || [];
      } catch (e) {}

      if (!dims.length) {  // sin conexión: catálogo guardado en el dispositivo
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          const lista = (cat && cat.modelos) ? cat.modelos : [];
          dims = [...new Set(lista
            .filter(it => (!mValida || (it.marca || '').toLowerCase() === m.toLowerCase()) && (it.diseno || '').toLowerCase() === d.toLowerCase())
            .map(it => String(it.dimension || '').trim()).filter(Boolean))];
        } catch (e) {}
      }
      if (!dims.length) return;

      const selDim = document.getElementById('dimension');
      const actual = (selDim?.value || '').trim();
      if (dims.some(x => x.toLowerCase() === actual.toLowerCase())) return;  // la medida actual ya es válida para el modelo

      asignarValorSelect('dimension', dims[0]);
      alCambiarDimensionMobile();
      mostrarToast(dims.length === 1
        ? `📐 Dimensión ${dims[0]} (medida del modelo ${d})`
        : `📐 Dimensión ${dims[0]}. El modelo ${d} también existe en: ${dims.slice(1).join(', ')}`);
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

      let data = null;
      try {
        let url = `/api/profundidad-inicial?marca=${encodeURIComponent(mValida ? m : '')}&diseno=${encodeURIComponent(dValida ? d : '')}&dimension=${encodeURIComponent(dim)}&vida=${encodeURIComponent(vida)}`;
        if (bValida) {
          url += `&banda=${encodeURIComponent(banda)}`;
        }
        const res = await fetchConTimeoutPatio(url, {}, 3500);
        if (res.ok) {
          data = await res.json();
        }
      } catch (err) {}

      if (!data || !(data.prof_inicial > 0)) {
        try {
          const cat = await TireAnalyzeOfflineDB.obtenerCatalogos();
          if (cat && cat.modelos) {
            const mod = cat.modelos.find(item => {
              const matchMarca = !mValida || (item.marca || '').toLowerCase() === m.toLowerCase();
              const matchDiseno = !dValida || (item.diseno || '').toLowerCase() === d.toLowerCase();
              return matchMarca && matchDiseno;
            });
            if (mod && (mod.profundidad_original_mm > 0 || mod.prof_inicial > 0)) {
              data = { prof_inicial: mod.profundidad_original_mm || mod.prof_inicial };
            }
          }
        } catch(eDb) {}
      }

      if (data && data.prof_inicial > 0) {
        const inp = document.getElementById('prof_inicial');
        if (inp) {
          inp.value = data.prof_inicial;
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
        // Modelo de banda de reencauche: la vida debe ser R1, R2…; si estaba en Original se deja por elegir
        const selV = document.getElementById('vida');
        if (!esVidaReencauche(selV.value)) {
          selV.value = '';
          mostrarToast('Seleccione el número de reencauche (R1, R2…) de esta llanta');
        }
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
      const chkReen = document.getElementById('tip_permite_reencauche_dir');
      if (chkReen) chkReen.checked = false;
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
      const chkReen = document.getElementById('tip_permite_reencauche_dir');
      if (chkReen) chkReen.checked = !!t.permite_reencauche_direccion;
      recalcularLlantasTipologia();

      document.getElementById('modalTipologia').classList.remove('hidden');
      document.getElementById('modalTipologia').classList.add('flex');
    }

    function cerrarModalTipologia() {
      tipologiaEditando = null;
      const chkReen = document.getElementById('tip_permite_reencauche_dir');
      if (chkReen) chkReen.checked = false;
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
      const permiteReenDir = !!document.getElementById('tip_permite_reencauche_dir')?.checked;

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
          cant_repuestos: eRep,
          permite_reencauche_direccion: permiteReenDir
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
          cant_repuestos: eRep,
          permite_reencauche_direccion: permiteReenDir
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

      // 2. Resumen del informe: el servidor usa el mismo motor que el PDF (conteo y recomendaciones coinciden)
      const placaUp = placa.toUpperCase();
      let resumen = null;
      try {
        let url = `/api/informe-resumen/${encodeURIComponent(placaUp)}`;
        if (fecha) url += `?fecha=${encodeURIComponent(fecha)}`;
        const res = await fetchConTimeoutPatio(url, {}, 6000);
        if (res.ok) resumen = await res.json();
      } catch(eRed) {}

      // Sin conexión: resumen básico con las llantas de ESTA inspección en la cola local
      if (!resumen) {
        try {
          const pendientes = await TireAnalyzeOfflineDB.obtenerTodasPendientes();
          resumen = resumenInformeOffline(pendientes, placaUp, fecha);
        } catch(eDb) {}
      }
      if (resumen) pintarResumenInformeModal(resumen);
    }

    // Frases que no son novedad (misma regla que el servidor: "Normal sin novedad", "OK"...)
    function esNovedadReal(texto) {
      const benignas = ['desgaste normal y parejo', 'desgaste normal', 'desgaste parejo', 'en buen estado', 'buen estado',
        'sin novedades', 'sin novedad', 'sin problemas', 'sin problema', 'ninguna', 'ninguno', 'normal', 'optimo', 'óptimo', 'bien', 'ok'];
      let t = ` ${String(texto || '').toLowerCase().replace(/[-/,;:.()]+/g, ' ').replace(/\s+/g, ' ').trim()} `;
      benignas.forEach(b => {
        while (t.includes(` ${b} `)) t = t.replace(` ${b} `, ' ');
      });
      return t.trim().length > 0;
    }

    function resumenInformeOffline(pendientes, placaUp, fecha) {
      let locales = (pendientes || []).filter(r => (r.placa || '').toUpperCase() === placaUp);
      if (fecha) locales = locales.filter(r => !r.fecha || String(r.fecha).slice(0, 10) === String(fecha).slice(0, 10));
      if (!locales.length) return null;
      // Una fila por posición (la última registrada): antes se contaban todas las capturas de la placa
      const porPosicion = new Map();
      locales.forEach(r => porPosicion.set(String(r.posicion), r));
      const filas = [...porPosicion.values()];
      const limite = parseFloat(document.getElementById('lblMmRetiroCliente')?.textContent) || 3.0;
      const fmt = v => v.toFixed(1).replace('.', ',');
      const alertas = [];
      const psis = [];
      filas.forEach(f => {
        const val = [f.prof_ext, f.prof_cent, f.prof_int].map(v => parseFloat(v) || 0).filter(v => v > 0);
        const pMin = val.length ? Math.min(...val) : 0;
        const psi = parseFloat(f.psi) || 0;
        if (psi > 0) psis.push(psi);
        if (pMin > 0 && pMin <= limite) {
          alertas.push({ grupo: 'retiro', tipo: 'Cambio', tipo_color: '#DC2626', posicion: String(f.posicion),
            detalle: `Remanente ${fmt(pMin)} mm ≤ ${fmt(limite)} mm de límite.`,
            accion: 'Retirar la llanta y programar su cambio.' });
        }
        if (esNovedadReal(f.novedades)) {
          alertas.push({ grupo: 'novedades', tipo: 'Novedad mecánica', tipo_color: '#D97706', posicion: String(f.posicion),
            detalle: String(f.novedades).trim(), accion: 'Revisar componente y corregir condición.' });
        }
      });
      const orden = ['retiro', 'novedades'];
      alertas.sort((a, b) => orden.indexOf(a.grupo) - orden.indexOf(b.grupo));
      return {
        offline: true,
        limite_retiro: limite,
        total_auditadas: filas.length,
        total_posiciones: listaPosicionesActual.length || filas.length,
        posiciones_pendientes: [],
        llantas_retiro: alertas.filter(a => a.tipo === 'Cambio').length,
        llantas_con_novedad: alertas.filter(a => a.grupo === 'novedades').length,
        promedio_psi: psis.length ? Math.round(psis.reduce((a, b) => a + b, 0) / psis.length) : null,
        grupos: [{ id: 'retiro', nombre: 'Retiros y reemplazos' }, { id: 'novedades', nombre: 'Novedades reportadas por el inspector' }],
        alertas
      };
    }

    function pintarResumenInformeModal(r) {
      const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      setTxt('lblModalTotalLlantas', `${r.total_auditadas} / ${r.total_posiciones}`);
      setTxt('lblModalLlantasRetiro', r.llantas_retiro);
      setTxt('lblModalLlantasNovedad', r.llantas_con_novedad);
      setTxt('lblModalPromedioPsi', r.promedio_psi ? `${r.promedio_psi} PSI` : '— PSI');

      const listaBox = document.getElementById('modalPlanesAccionList');
      const saludBadge = document.getElementById('lblEstadoSaludVehiculo');
      if (!listaBox) return;
      const limiteTxt = Number(r.limite_retiro || 3).toFixed(1).replace('.', ',');
      const alertas = r.alertas || [];
      const pendientes = r.posiciones_pendientes || [];
      const avisoPendientes = pendientes.length
        ? `<div class="p-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-600">
             <i class="fa-solid fa-circle-info text-slate-400 mr-1"></i>${pendientes.length} posición(es) sin inspeccionar: ${escapeHtml(pendientes.join(', '))}.
           </div>` : '';
      const avisoOffline = r.offline
        ? `<div class="p-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
             <i class="fa-solid fa-wifi mr-1"></i>Sin conexión: resumen básico. Las demás recomendaciones (cruces, rotaciones, presión) aparecen al sincronizar.
           </div>` : '';

      if (!alertas.length) {
        listaBox.innerHTML = `${avisoOffline}
          <div class="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center space-x-2">
            <i class="fa-solid fa-circle-check text-emerald-600 text-base"></i>
            <span><b>Vehículo en estado seguro:</b> todas las llantas inspeccionadas están sobre el límite de retiro (${limiteTxt} mm) y sin novedades.</span>
          </div>${avisoPendientes}`;
        if (saludBadge) {
          saludBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200';
          saludBadge.textContent = 'Estado Óptimo';
        }
        return;
      }

      // Una sección por grupo, en el mismo orden de prioridad del PDF
      const secciones = (r.grupos || []).map(g => {
        const delGrupo = alertas.filter(a => a.grupo === g.id);
        if (!delGrupo.length) return '';
        const items = delGrupo.map(a => `
          <div class="p-2.5 rounded-xl bg-white border border-slate-200 leading-snug" style="border-left: 4px solid ${escapeHtml(a.tipo_color)}">
            <div class="flex items-center justify-between gap-2">
              <b style="color: ${escapeHtml(a.tipo_color)}">${escapeHtml(a.tipo)}</b>
              <span class="text-[11px] font-bold text-slate-500 whitespace-nowrap">${/^\d/.test(String(a.posicion)) ? 'Pos. ' : ''}${escapeHtml(a.posicion)}</span>
            </div>
            <div class="text-slate-600 mt-0.5">${escapeHtml(a.detalle)}</div>
            <div class="text-slate-800 mt-0.5"><i class="fa-solid fa-arrow-right text-[10px] text-slate-400 mr-1"></i>${escapeHtml(a.accion)}</div>
          </div>`).join('');
        return `
          <div class="space-y-1.5">
            <div class="text-[11px] font-black uppercase tracking-wider text-slate-500 pt-1">${escapeHtml(g.nombre)} (${delGrupo.length})</div>
            ${items}
          </div>`;
      }).join('');

      listaBox.innerHTML = avisoOffline + secciones + avisoPendientes;
      if (saludBadge) {
        const urgente = alertas.some(a => a.grupo === 'retiro');
        saludBadge.className = urgente
          ? 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200'
          : 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200';
        saludBadge.textContent = urgente ? 'Requiere Retiro' : 'Requiere Atención';
      }
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
      if (!navigator.onLine) {
        mostrarToast('📡 El informe PDF oficial se generará automáticamente apenas sincronices las inspecciones al conectarte a internet.', true);
        return;
      }
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

      function fechaLocalISO(d = new Date()) {
        const p = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
      }

      const fechaVal = document.getElementById('fecha').value || fechaLocalISO();
      let numInterno = (document.getElementById('numero_interno')?.value || '').trim().toUpperCase();
      if (!numInterno) {
        numInterno = `TMP-${placa}-P${String(pos).padStart(2, '0')}`;
      }
      const dedup_key = `${placa}_${pos}_${fechaVal.slice(0, 10)}`;

      const payload = {
        dedup_key: dedup_key,
        timestamp_local: new Date().toISOString(),
        fecha: fechaVal,
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
        marca: (document.getElementById('marca')?.value || '').trim().toUpperCase(),
        diseno: (document.getElementById('diseno')?.value || '').trim().toUpperCase(),
        dimension: dimension,
        vida: (document.getElementById('vida')?.value || '').trim(),  // sin elegir no se asume Original
        banda_reen: (document.getElementById('banda_reen')?.value || '').trim().toUpperCase(),
        prof_ext: p_ext,
        prof_cent: p_cent,
        prof_int: p_int,
        psi: parseFloat(psi_val) || 0,  // sin lectura = sin dato (antes se guardaban 100 PSI)
        novedades: document.getElementById('novedades').value,
        foto_novedad: (document.getElementById('foto_novedad_base64') || {}).value || '',
        precio: parseFloat(document.getElementById('precio').value) || 0,
        prof_inicial: prof_inicial_num,
        km_montaje: parseFloat(document.getElementById('km_montaje').value) || 0,
        unidad_medida: unidadPlacaPatio(),
        numero_interno: numInterno,
        tipo_licencia: (typeof clienteLicenciaCaptura !== 'undefined' && clienteLicenciaCaptura) ? clienteLicenciaCaptura : (typeof modoLicenciaGraficos !== 'undefined' ? modoLicenciaGraficos : 'LIGHT'),
        usuario_registro: usuarioActual ? usuarioActual.username : '',
        _ultimo_km_previo: (perfilVehiculoActual && perfilVehiculoActual.ultimo_km > 0 && (perfilVehiculoActual.ultima_fecha_inspeccion || '') < fechaVal.slice(0, 10)) ? perfilVehiculoActual.ultimo_km : 0
      };

      // Validación local de candados de seguridad en el navegador (Candados 1, 2, 3, 4)
      const validacionCandados = validarCandadosOfflineLocal(payload);
      if (!validacionCandados.valido) {
        mostrarToast(validacionCandados.mensaje, true);
        return;
      }

      registrarInicioJornadaCliente();
      const btn = document.getElementById('btnGuardar');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Guardando...';
      }

      async function completarGuardadoRueda(esOffline = false) {
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

        if (esOffline) {
          mostrarToast(`📡 Guardada en el teléfono (Modo Sin Señal) — Posición ${payload.posicion} de ${placa}`);
        } else {
          mostrarToast(`✅ Guardada llanta Posición ${payload.posicion} de ${placa}`);
        }

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
      }

      async function guardarEnColaOffline() {
        try {
          await TireAnalyzeOfflineDB.guardarPendiente(payload);
          await actualizarVehiculoOfflineConNuevaInspeccion(payload);
          await actualizarIndicadorConexionOffline();
        } catch (eDb) {
          console.warn('Error guardando en cola offline:', eDb);
        }
        await completarGuardadoRueda(true);
      }

      try {
        if (!navigator.onLine) {
          await guardarEnColaOffline();
        } else {
          try {
            const res = await fetchConTimeoutPatio('/api/inspecciones', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify(payload)
            }, 4500);
            const result = await res.json();
            if (res.ok) {
              actualizarVehiculoOfflineConNuevaInspeccion(payload).catch(() => {});
              await completarGuardadoRueda(false);
            } else {
              mostrarToast(result.detail || result.message || 'Error al guardar', true);
            }
          } catch (errRed) {
            console.warn('Red lenta o sin cobertura (Lie-Fi). Conmutando a guardado local en cola IndexedDB:', errRed);
            await guardarEnColaOffline();
          }
        }
      } catch (errGlobal) {
        console.error('Error procesando inspección:', errGlobal);
        mostrarToast('Error al procesar la inspección localmente', true);
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

