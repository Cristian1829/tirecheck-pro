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

    // Vida escrita siempre igual: 'Original', 'R1', 'R2'... ('ORIGINAL' / 'original' / vacío -> 'Original')
    function vidaLegible(vida) {
      const v = String(vida || '').trim();
      if (!v || v.toUpperCase() === 'ORIGINAL') return 'Original';
      if (/^R\d+$/i.test(v)) return v.toUpperCase();
      return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
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
        const horizonte = document.getElementById('inpHorizonteMrp')?.value || 3;
        const urlMrp = `/api/bodegas/resumen-mrp?cliente=${encodeURIComponent(clienteSel)}&dimension=${encodeURIComponent(dimSel)}&horizonte_meses=${encodeURIComponent(horizonte)}`;
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

        // Proyección: cuántas llegan al límite dentro del horizonte, retorno de reencauche y desecho
        const proyBadge = `<span class="block text-[9px] text-slate-500" title="Llegan al límite dentro de ${r.horizonte_meses ?? 3} meses; sin historial suficiente: ${r.llantas_sin_ritmo || 0}">${r.demanda_proyectada || 0} proyectadas a ${r.horizonte_meses ?? 3} m</span>
          <span class="block text-[9px] text-emerald-700" title="Cascos que volverán reencauchados / llantas que saldrán como desecho">↺ ${r.retorno_reencauche_proyectado || 0} · desecho ${r.desecho_proyectado || 0}</span>`;
        html += `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-3 font-black text-slate-900">${r.dimension}</td>
            <td class="p-3 text-center bg-rose-50/30">
              <span class="font-bold">${demRetiro}</span>
              ${parDirBadge}
              ${proyBadge}
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
          return `<span class="bg-amber-100 text-amber-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-amber-300">B5: Reparación</span>`;
        case 'BODEGA_6_FVU':
          return `<span class="bg-rose-100 text-rose-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-rose-300">B6: Desecho FVU</span>`;
        case 'BODEGA_7_CHATARRIZADA':
          return `<span class="bg-slate-200 text-slate-800 text-[10px] font-black px-2 py-0.5 rounded-full border border-slate-300">B7: Disposición final</span>`;
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
              <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${vidaLegible(ll.vida_actual) === 'Original' ? 'bg-sky-100 text-sky-800' : 'bg-teal-100 text-teal-800'}">
                ${vidaLegible(ll.vida_actual)}
              </span>
            </td>
            <td class="p-3 text-center font-black ${ll.prof_actual_min <= 3.0 ? 'text-rose-600' : 'text-slate-800'}">
              ${ll.prof_actual_min != null ? fmtDec(Number(ll.prof_actual_min), 1) + ' mm' : '-'}
            </td>
            <td class="p-3">${detalleVehiculo}</td>
            <td class="p-3 text-right font-bold text-slate-800 whitespace-nowrap">${costoTotalFormateado}</td>
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
                ${(ll.ubicacion_bodega === 'BODEGA_3_REENCAUCHE' && !ll.fecha_envio_planta) ? `
                  <button type="button" onclick="abrirModalDespachoPlanta('${serialSeguro}')" title="Despachar a Planta Reencauche" class="p-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs border border-indigo-200">
                    <i class="fa-solid fa-industry"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_3_REENCAUCHE' && ll.fecha_envio_planta) ? `
                  <button type="button" onclick="abrirModalRetornoReencauche('${serialSeguro}')" title="Recepcionar Reencauche" class="p-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-700 font-bold text-xs border border-teal-200">
                    <i class="fa-solid fa-arrows-spin"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_5_REPARACION') ? `
                  <button type="button" onclick="abrirModalFinalizarReparacion('${serialSeguro}')" title="Finalizar Reparación" class="p-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold text-xs border border-amber-200">
                    <i class="fa-solid fa-wrench"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_6_FVU') ? `
                  <button type="button" onclick="abrirModalDictamenGarantia('${serialSeguro}')" title="Dictamen de Garantía" class="p-1.5 rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs border border-purple-200">
                    <i class="fa-solid fa-shield-halved"></i>
                  </button>
                ` : ''}
                ${(ll.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA') ? `
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
        costo_compra: parseFloat(document.getElementById('alta_costo_compra').value) || null,
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
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Disposición final: retiro por empresa ambiental (con acta)' });
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Reingreso a vehículo (con motivo, responsable y foto)' });
      } else if (origen === 'BODEGA_7_CHATARRIZADA') {
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Reingreso a vehículo (con motivo, responsable y foto)' });
      } else {
        destinos.push({ val: 'MONTADA_OPERACION', text: '🚚 Montar en Vehículo (Operación)' });
        destinos.push({ val: 'BODEGA_2_RECAMBIO', text: '🔄 Bodega 2: Recambio en Patio' });
        destinos.push({ val: 'BODEGA_3_REENCAUCHE', text: '🏭 Bodega 3: Planta de Reencauche' });
        destinos.push({ val: 'BODEGA_4_REENCAUCHADAS', text: '✨ Bodega 4: Reencauchada Lista' });
        destinos.push({ val: 'BODEGA_5_REPARACION', text: '🔧 Bodega 5: Taller / Vulcanizadora' });
        destinos.push({ val: 'BODEGA_6_FVU', text: '⚠️ Bodega 6: Fin de Vida Útil' });
        destinos.push({ val: 'BODEGA_7_CHATARRIZADA', text: '♻️ Bodega 7: Chatarrización' });
      }

      // Solo los pasos que la regla permite (la misma tabla que valida el servidor)
      const permitidos = TRANSICIONES_LLANTA[origen] || [];
      destinos.filter(d => permitidos.includes(d.val)).forEach(d => {
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
      if (document.getElementById('mover_nueva_prof')) document.getElementById('mover_nueva_prof').value = '';
      ['mover_motivo_reingreso', 'mover_responsable_reingreso', 'mover_foto_reingreso'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
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

    // Transiciones permitidas entre ubicaciones (las mismas que valida el servidor)
    const TRANSICIONES_LLANTA = {
      BODEGA_1_NUEVAS: ['MONTADA_OPERACION', 'BODEGA_5_REPARACION', 'BODEGA_6_FVU'],
      BODEGA_2_RECAMBIO: ['MONTADA_OPERACION', 'BODEGA_3_REENCAUCHE', 'BODEGA_5_REPARACION', 'BODEGA_6_FVU'],
      BODEGA_3_REENCAUCHE: ['BODEGA_4_REENCAUCHADAS', 'BODEGA_2_RECAMBIO', 'BODEGA_6_FVU'],
      BODEGA_4_REENCAUCHADAS: ['MONTADA_OPERACION', 'BODEGA_5_REPARACION', 'BODEGA_6_FVU'],
      BODEGA_5_REPARACION: ['BODEGA_2_RECAMBIO', 'BODEGA_3_REENCAUCHE', 'BODEGA_4_REENCAUCHADAS', 'MONTADA_OPERACION', 'BODEGA_6_FVU'],
      BODEGA_6_FVU: ['BODEGA_7_CHATARRIZADA', 'MONTADA_OPERACION'],
      BODEGA_7_CHATARRIZADA: ['MONTADA_OPERACION'],
      MONTADA_OPERACION: ['MONTADA_OPERACION', 'BODEGA_2_RECAMBIO', 'BODEGA_3_REENCAUCHE', 'BODEGA_5_REPARACION', 'BODEGA_6_FVU']
    };
    const esLlantaDeBaja = (ll) => ll && (ll.ubicacion_bodega === 'BODEGA_6_FVU' || ll.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA');

    function leerArchivoComoDataUrl(input) {
      return new Promise((resolve) => {
        const f = input?.files?.[0];
        if (!f) return resolve('');
        const r = new FileReader();
        r.onload = () => resolve(String(r.result || ''));
        r.onerror = () => resolve('');
        r.readAsDataURL(f);
      });
    }

    function adaptarCamposModalMover(destino, llanta = null) {
      const serial = document.getElementById('mover_numero_interno')?.value || '';
      const cleanNum = String(serial || '').trim().toUpperCase();
      const ll = llanta || cacheInventarioBodegas.find(l => String(l.numero_interno || '').trim().toUpperCase() === cleanNum);
      destino = document.getElementById('mover_bodega_destino')?.value || destino;
      const boxReing = document.getElementById('boxMoverReingreso');
      if (boxReing) boxReing.classList.toggle('hidden', !(destino === 'MONTADA_OPERACION' && esLlantaDeBaja(ll)));

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

        if (esLlantaDeBaja(ll) && destino === 'MONTADA_OPERACION') {
          alertaBox.className = 'text-xs p-3 rounded-xl border font-bold bg-rose-50 text-rose-900 border-rose-300 flex items-center space-x-2';
          alertaBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-rose-600 text-base"></i><span>Llanta dada de baja (' + (ll.estado_display || ll.ubicacion_bodega) + '). Solo puede volver a montarse registrando el motivo, el responsable y una foto del reingreso.</span>';
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
            alertaBox.innerHTML = '<i class="fa-solid fa-hand text-rose-600 mt-0.5"></i><div><span><strong>ADVERTENCIA TÉCNICA:</strong> La profundidad actual (' + fmtDec(profActual, 1) + ' mm) está en o por debajo del límite de retiro (3,0 mm). El sistema rechazará almacenarla en Bodega 2. Debe enviarse a Bodega 3 (Reencauche) o Bodega 6 (FVU).</span></div>';
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
          alertaBox.innerHTML = '<i class="fa-solid fa-recycle text-slate-700"></i><span>Disposición final: la empresa ambiental retira la llanta. Registre el número de acta que entrega.</span>';
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
          mostrarToast('⛔ La profundidad (' + fmtDec(profCheck, 1) + ' mm) está en o por debajo del límite de retiro (3,0 mm). No puede enviarse a Bodega 2. Debe enviarse a Bodega 3 (Reencauche) o Bodega 6 (FVU).', true);
          return;
        }
      } else if (destino === 'BODEGA_3_REENCAUCHE') {
        payload.proveedor = document.getElementById('mover_planta_reencauche')?.value.trim() || '';
        payload.documento_soporte = document.getElementById('mover_remision_reencauche')?.value.trim() || '';
      } else if (destino === 'BODEGA_4_REENCAUCHADAS') {
        const inpBanda = document.getElementById('mover_banda_reen');
        payload.banda_reen = inpBanda?.value.trim().toUpperCase() || '';
        payload.nueva_prof_inicial = parseFloat(document.getElementById('mover_nueva_prof')?.value) || null;
        if (!payload.nueva_prof_inicial) {
          mostrarToast('⚠️ Ingrese la profundidad de la banda nueva (mm)', true);
          return;
        }
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
        if (!payload.documento_soporte) {
          mostrarToast('⚠️ Ingrese el número de acta de la empresa ambiental', true);
          return;
        }
      }
      if (destino === 'MONTADA_OPERACION' && esLlantaDeBaja(ll)) {
        payload.motivo_reingreso = document.getElementById('mover_motivo_reingreso')?.value.trim() || '';
        payload.responsable_reingreso = document.getElementById('mover_responsable_reingreso')?.value.trim() || '';
        payload.foto_reingreso = await leerArchivoComoDataUrl(document.getElementById('mover_foto_reingreso'));
        if (!payload.motivo_reingreso || !payload.responsable_reingreso || !payload.foto_reingreso) {
          mostrarToast('⚠️ Para el reingreso registre motivo, responsable y foto', true);
          return;
        }
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
          <div><span class="text-slate-400 block text-[10px]">Profundidad:</span><strong>${llanta.prof_actual_min != null ? fmtDec(Number(llanta.prof_actual_min), 1) + ' mm' : '-'}</strong></div>
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
          ? `<span class="text-slate-500 ml-2">Prof: ${fmtDec(Number(ev.prof_min_mm), 1)} mm</span>` 
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
     * Valida si el cliente seleccionado opera bajo Licencia FULL / PRO.
     * En caso de Licencia LIGHT, los montajes y desmontajes están restringidos.
     */
    function esLicenciaFullTaller() {
      if (posTallerActualInfo && typeof posTallerActualInfo.permite_taller !== 'undefined') {
        return Boolean(posTallerActualInfo.permite_taller);
      }
      if (posTallerActualInfo && posTallerActualInfo.tipo_licencia) {
        return String(posTallerActualInfo.tipo_licencia).toUpperCase() !== 'LIGHT';
      }
      if (typeof window !== 'undefined' && window.clienteLicenciaCaptura) {
        return String(window.clienteLicenciaCaptura).toUpperCase() !== 'LIGHT';
      }
      if (typeof clienteLicenciaCaptura !== 'undefined' && clienteLicenciaCaptura) {
        return String(clienteLicenciaCaptura).toUpperCase() !== 'LIGHT';
      }
      return true;
    }

    /**
     * Consulta el estado en tiempo real de la posición seleccionada en el chasis
     * y actualiza el panel de Taller en Patio (#seccionTallerPatio).
     */
    async function actualizarPanelTallerPosicion(p) {
      const placa = (document.getElementById('placa')?.value || '').trim().toUpperCase();
      const cliente = (document.getElementById('cliente')?.value || '').trim();
      const badgePos = document.getElementById('badgeTallerPos');
      const boxVacio = document.getElementById('tallerLlantaVacia');
      const boxMontada = document.getElementById('tallerLlantaMontada');
      const btnDesm = document.getElementById('btnTallerDesmontar');
      const btnMont = document.getElementById('btnTallerMontar');
      const badgeFull = document.getElementById('badgeTallerPlanFull');
      const badgeLight = document.getElementById('badgeTallerPlanLight');
      const bannerLight = document.getElementById('bannerTallerLight');
      const txtDesm = document.getElementById('txtBtnTallerDesmontar');
      const txtMont = document.getElementById('txtBtnTallerMontar');

      if (!placa || !p) {
        if (badgePos) badgePos.textContent = `Posición ${p || '-'}`;
        if (boxVacio) boxVacio.classList.remove('hidden');
        if (boxMontada) boxMontada.classList.add('hidden');
        if (btnDesm) btnDesm.disabled = true;
        posTallerActualInfo = null;
        return;
      }

      try {
        const res = await fetch(`/api/taller/posicion-info?placa=${encodeURIComponent(placa)}&posicion=${p}&cliente=${encodeURIComponent(cliente)}`);
        if (!res.ok) return;
        const data = await res.json();
        posTallerActualInfo = data;

        const esFull = (typeof data.permite_taller !== 'undefined')
          ? Boolean(data.permite_taller)
          : (String(data.tipo_licencia || window.clienteLicenciaCaptura || 'LIGHT').toUpperCase() !== 'LIGHT');

        // Actualizar badges de licenciamiento y banner explicativo
        if (esFull) {
          if (badgeFull) badgeFull.classList.remove('hidden');
          if (badgeLight) badgeLight.classList.add('hidden');
          if (bannerLight) bannerLight.classList.add('hidden');
          if (txtDesm) txtDesm.textContent = 'Desmontar';
          if (txtMont) txtMont.textContent = 'Montar Llanta';
          if (btnMont) {
            btnMont.disabled = false;
            btnMont.title = 'Montar llanta en esta posición';
          }
        } else {
          if (badgeFull) badgeFull.classList.add('hidden');
          if (badgeLight) badgeLight.classList.remove('hidden');
          if (bannerLight) bannerLight.classList.remove('hidden');
          if (txtDesm) txtDesm.textContent = 'Desmontar (Plan FULL)';
          if (txtMont) txtMont.textContent = 'Montar (Plan FULL)';
          if (btnMont) {
            btnMont.disabled = true;
            btnMont.title = 'Montajes de taller exclusivos de la Licencia FULL';
          }
          if (btnDesm) {
            btnDesm.disabled = true;
            btnDesm.title = 'Desmontes de taller exclusivos de la Licencia FULL';
          }
        }

        if (badgePos) {
          const dirTxt = data.es_direccional ? 'Direccional ⚠️' : 'Tracción / Arrastre';
          badgePos.textContent = `Posición ${p} — ${dirTxt}`;
        }

        if (data.llanta_instalada) {
          const ll = data.llanta_instalada;
          if (boxVacio) boxVacio.classList.add('hidden');
          if (boxMontada) boxMontada.classList.remove('hidden');
          if (btnDesm) {
            btnDesm.disabled = !esFull;
            if (esFull) btnDesm.title = 'Desmontar llanta instalada';
          }

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
          if (profEl) profEl.textContent = `${fmtDec(Number(ll.prof_actual_min || 0), 1)} mm`;
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
      if (!esLicenciaFullTaller()) {
        const msg = 'Los desmontajes en patio son una funcionalidad exclusiva de la Versión FULL (Gestión Integral de Bodegas y Taller).';
        if (typeof mostrarToast === 'function') mostrarToast(msg, 'warn');
        else alert(msg);
        return;
      }
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
      if (!esLicenciaFullTaller()) {
        const msg = 'Los montajes en patio son una funcionalidad exclusiva de la Versión FULL (Gestión Integral de Bodegas y Taller).';
        if (typeof mostrarToast === 'function') mostrarToast(msg, 'warn');
        else alert(msg);
        return;
      }
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
        payload.prof_inicial = parseFloat(document.getElementById('mont_nueva_prof').value) || null;  // sin dato: el servidor usa el catálogo del modelo
        payload.precio_compra = parseFloat(document.getElementById('mont_nueva_precio').value) || null;
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
      document.getElementById('hv_prof_act').textContent = `${fmtDec(Number(data.profundidad_actual_min || 0), 1)} mm`;
      document.getElementById('hv_ubicacion').textContent = data.ubicacion_bodega || data.estado_actual || '-';
      document.getElementById('hv_cliente').textContent = data.cliente_propietario || '-';

      // 5 Tarjetas KPIs
      document.getElementById('hv_kpi_km').textContent = `${Number(met.km_totales || 0).toLocaleString()} km`;
      // Sin precio registrado se dice así, en lugar de mostrar $0
      document.getElementById('hv_kpi_costo').textContent = met.costo_total_invertido ? `$ ${Number(met.costo_total_invertido).toLocaleString('es-CO')}` : 'Sin precio';
      document.getElementById('hv_kpi_cpk').textContent = met.cpk_global != null ? `$ ${fmtDec(Number(met.cpk_global), 2)} / km` : 'Sin precio';
      document.getElementById('hv_kpi_rendimiento').textContent = `${Number(met.rendimiento_km_mm || 0).toLocaleString()} km/mm`;
      document.getElementById('hv_kpi_ahorro').textContent = met.ahorro_generado_vs_nueva != null ? `$ ${Number(met.ahorro_generado_vs_nueva).toLocaleString('es-CO')}` : 'Sin precio';

      // Botón Acta PDF si está en FVU
      const btnActa = document.getElementById('btnHvPdfActa');
      if (btnActa) {
        if (data.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA' || data.estado_actual?.ubicacion_bodega === 'BODEGA_7_CHATARRIZADA') {
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
                <td class="p-2.5 text-center font-mono">${fmtDec(Number(c.prof_inicial || 0), 1)} mm</td>
                <td class="p-2.5 text-center font-mono font-bold">${fmtDec(Number(c.prof_final || 0), 1)} mm</td>
                <td class="p-2.5 text-right font-mono font-bold">${Number(c.km_recorridos || 0).toLocaleString()} km</td>
                <td class="p-2.5 text-right font-mono">$ ${Number(c.costo || 0).toLocaleString('es-CO')}</td>
                <td class="p-2.5 text-right font-mono font-black text-indigo-700">$ ${fmtDec(Number(c.cpk || 0), 2)}</td>
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
                    ${m.profundidad_momento > 0 ? `Prof: ${fmtDec(Number(m.profundidad_momento), 1)} mm | ` : ''}
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
      const prof = parseFloat(document.getElementById('ret_prof_banda').value) || null;
      const costo = parseFloat(document.getElementById('ret_costo').value) || null;  // sin precio: se excluye de los costos
      if (!prof) { alert('Ingrese la profundidad de la banda nueva (mm)'); return; }
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
          alert(`Reencauche recibido para ${serial}: queda como ${data.vida || 'reencauchada'} en Bodega 4.`);
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


