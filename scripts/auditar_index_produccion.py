import os
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ARTIFACT_DIR = r"C:\Users\crist\.gemini\antigravity-ide\brain\36c1ded4-8d97-486d-9437-1d789fdc794f"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def setup_driver(width, height):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={width},{height}")
    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(width, height)
    return driver

def capture(driver, filename):
    path = os.path.join(ARTIFACT_DIR, filename)
    driver.save_screenshot(path)
    print(f"Screenshot guardado: {filename}")
    return path

def login_and_goto_patio(driver):
    driver.execute_script("""
        localStorage.setItem('tirecheck_usuario_sesion', JSON.stringify({
            username: 'admin',
            nombre_completo: 'Administrador del Sistema',
            rol: 'admin'
        }));
        usuarioActual = {username: 'admin', nombre_completo: 'Administrador del Sistema', rol: 'admin'};
        const modal = document.getElementById('modalLogin');
        if (modal) modal.classList.add('hidden');
        if (typeof actualizarUIUsuario === 'function') actualizarUIUsuario();
        if (typeof cargarCatalogos === 'function') cargarCatalogos();
        if (typeof cambiarVista === 'function') cambiarVista('patio');
    """)
    time.sleep(1.5)

def select_tipologia_and_wait(driver, tip_text):
    driver.execute_script(f"""
        const sel = document.getElementById('tipologia');
        for (let opt of sel.options) {{
            if (opt.text.toLowerCase().includes('{tip_text.lower()}')) {{
                sel.value = opt.value;
                sel.dispatchEvent(new Event('change'));
                break;
            }}
        }}
    """)
    time.sleep(1.2)

def run_tests():
    url = "http://127.0.0.1:8000/"
    
    # -------------------------------------------------------------
    # 1. ESCRITORIO (1440 x 900)
    # -------------------------------------------------------------
    print("\n==============================================")
    print("EJECUTANDO AUDITORÍA EN ESCRITORIO (1440 x 950)")
    print("==============================================")
    driver = setup_driver(1440, 950)
    driver.get(url)
    time.sleep(2)
    login_and_goto_patio(driver)
    
    # Escenario 1: Cabezote 6x4 - 0 Llantas Registradas
    print("\n-> Escenario 1: Cabezote 6x4 (0 Llantas Registradas)")
    select_tipologia_and_wait(driver, "cabezote (6x4)")
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set();
        posicionesConNovedadPlaca = new Map();
        seleccionarPosicion(1);
    """)
    time.sleep(0.8)
    capture(driver, "prod_desktop_cabezote_0_registradas.png")
    
    # Escenario 2: Cabezote 6x4 - Algunas Llantas Registradas con Novedad (pos 2 con novedad, pos 1 y 4 registradas)
    print("\n-> Escenario 2: Cabezote 6x4 (Algunas Registradas + Novedad)")
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set([1, 2, 4]);
        posicionesConNovedadPlaca = new Map([[2, 'Corte superficial en hombro']]);
        seleccionarPosicion(2);
    """)
    time.sleep(0.8)
    capture(driver, "prod_desktop_cabezote_algunas_novedad.png")
    
    # Verificaciones DOM
    verif = driver.execute_script("""
        const ruedas = document.querySelectorAll('.tire-rubber-body');
        const fills = Array.from(ruedas).map(r => r.getAttribute('fill'));
        const todosGrafito = fills.every(f => f.includes('gradRubber') || f.includes('#1E293B'));
        
        const badgeOk1 = document.querySelector('#badge_ok_1');
        const badgeWarn2 = document.querySelector('#badge_warn_2');
        const ringSeleccion = document.querySelector('.tire-selection-ring');
        
        // Roles bajo la rueda (DIR, EXT, INT)
        const rolesTextos = Array.from(document.querySelectorAll('#contenedorChasisEjes text[letter-spacing]')).map(t => t.textContent.trim());
        const rolesValidos = rolesTextos.every(r => ['DIR', 'EXT', 'INT', 'SEN', 'REP'].includes(r));
        
        // Indicador de orientación
        const tieneOrientacion = document.body.innerText.includes('IZQUIERDA') && 
                                 document.body.innerText.includes('FRENTE') && 
                                 document.body.innerText.includes('DERECHA');
                                 
        // Títulos limpios
        const noHayNumero3 = !document.getElementById('moduloChasis').innerText.includes('3. Diagrama');
        const noHayNumero4 = !document.getElementById('moduloMediciones').innerText.includes('4. Mediciones');
        
        // Sufijos mm y PSI
        const extSpan = document.getElementById('prof_ext').parentElement.querySelector('span').textContent.trim();
        const psiSpan = document.getElementById('psi').parentElement.querySelector('span').textContent.trim();
        
        // Resumen derecha
        const panelResumen = document.getElementById('panelResumenPosicion').innerText;
        const tieneRegistradaOConNovedad = panelResumen.includes('Con Novedad') || panelResumen.includes('Registrada');
        const sinInspeccionadaOK = !document.body.innerText.includes('INSPECCIONADA (OK)') && !document.body.innerText.includes('Inspeccionada (OK)');
        
        return {
            todosGrafito,
            tieneBadgeOk1: !!badgeOk1,
            tieneBadgeWarn2: !!badgeWarn2,
            tieneRingSeleccion: !!ringSeleccion,
            rolesValidos,
            rolesEncontrados: Array.from(new Set(rolesTextos)),
            tieneOrientacion,
            noHayNumero3,
            noHayNumero4,
            extSpan,
            psiSpan,
            tieneRegistradaOConNovedad,
            sinInspeccionadaOK
        };
    """)
    print("DOM Verificación:", json.dumps(verif, indent=2, ensure_ascii=False))
    
    # Escenario 3: Cabezote 6x4 - Todas las Llantas Registradas (Selección visible)
    print("\n-> Escenario 3: Cabezote 6x4 (Todas Registradas)")
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set(listaPosicionesActual);
        posicionesConNovedadPlaca = new Map([[3, 'Baja presión de calibración']]);
        seleccionarPosicion(1);
    """)
    time.sleep(0.8)
    capture(driver, "prod_desktop_cabezote_todas_registradas.png")
    
    # Probar las demás tipologías en escritorio
    otras_tipologias = [
        ("sencillo", "Camion_Sencillo_4x2"),
        ("trailer (2 ejes - 8 llantas + repuesto)", "Trailer_2E_8Ll_Repuesto"),
        ("trailer (3 ejes - 12 llantas + repuesto)", "Trailer_3E_12Ll_Repuesto"),
        ("cuatro manos", "Cabezote_Cuatro_Manos_8x4"),
        ("liviano", "Liviano_Camioneta_4x2"),
        ("volqueta", "Volqueta_Dobletroque_6x4"),
        ("articulado", "Articulado"),
        ("biarticulado", "Biarticulado")
    ]
    
    for search_str, file_label in otras_tipologias:
        print(f"\n-> Probando tipología: {file_label}...")
        select_tipologia_and_wait(driver, search_str)
        driver.execute_script("""
            if (listaPosicionesActual && listaPosicionesActual.length > 0) {
                posicionesInspeccionadasPlaca = new Set([listaPosicionesActual[0]]);
                if (listaPosicionesActual.length > 1) {
                    posicionesConNovedadPlaca = new Map([[listaPosicionesActual[1], 'Desgaste irregular']]);
                }
                seleccionarPosicion(listaPosicionesActual[0]);
            }
        """)
        time.sleep(0.6)
        capture(driver, f"prod_desktop_tip_{file_label}.png")
        
    driver.quit()
    
    # -------------------------------------------------------------
    # 2. TABLET (768 x 1024)
    # -------------------------------------------------------------
    print("\n==============================================")
    print("EJECUTANDO AUDITORÍA EN TABLET (768 x 1024)")
    print("==============================================")
    driver = setup_driver(768, 1024)
    driver.get(url)
    time.sleep(2)
    login_and_goto_patio(driver)
    
    select_tipologia_and_wait(driver, "cabezote (6x4)")
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set([1, 2, 5]);
        posicionesConNovedadPlaca = new Map([[2, 'Corte en hombro']]);
        seleccionarPosicion(2);
    """)
    time.sleep(0.8)
    capture(driver, "prod_tablet_cabezote_view.png")
    
    select_tipologia_and_wait(driver, "sencillo")
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set([1, 3]);
        seleccionarPosicion(1);
    """)
    time.sleep(0.8)
    capture(driver, "prod_tablet_sencillo_view.png")
    
    driver.quit()
    
    # -------------------------------------------------------------
    # 3. MÓVIL (390 x 844)
    # -------------------------------------------------------------
    print("\n==============================================")
    print("EJECUTANDO AUDITORÍA EN MÓVIL (390 x 844)")
    print("==============================================")
    driver = setup_driver(390, 844)
    driver.get(url)
    time.sleep(2)
    login_and_goto_patio(driver)
    
    select_tipologia_and_wait(driver, "cabezote (6x4)")
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set([1, 3]);
        posicionesConNovedadPlaca = new Map([[3, 'Baja presión']]);
        seleccionarPosicion(3);
    """)
    time.sleep(0.8)
    capture(driver, "prod_mobile_cabezote_chasis.png")
    
    # Scroll a Mediciones en Móvil
    driver.execute_script("""
        document.getElementById('moduloMediciones').scrollIntoView({ behavior: 'instant', block: 'start' });
    """)
    time.sleep(0.8)
    capture(driver, "prod_mobile_mediciones_inputs.png")
    
    # Test Validación en Móvil
    print("-> Probando validación inline obligatoria...")
    driver.execute_script("""
        document.getElementById('prof_ext').value = '';
        document.getElementById('prof_cent').value = '';
        document.getElementById('prof_int').value = '';
        marcarErrorCampo('prof_ext', 'err_profundidades');
    """)
    time.sleep(0.5)
    capture(driver, "prod_mobile_validacion_error.png")
    
    # Rellenar con valores válidos
    driver.execute_script("""
        document.getElementById('prof_ext').value = '8.5';
        document.getElementById('prof_cent').value = '8.2';
        document.getElementById('prof_int').value = '8.0';
        document.getElementById('psi').value = '105';
        limpiarErrorCampo('profundidades');
    """)
    time.sleep(0.5)
    capture(driver, "prod_mobile_mediciones_rellenas.png")
    
    driver.quit()
    
    print("\n==============================================")
    print("AUDITORÍA DE PRODUCCIÓN COMPLETADA EXITOSAMENTE")
    print("==============================================")

if __name__ == '__main__':
    run_tests()
