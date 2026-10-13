import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ARTIFACT_DIR = r"C:\Users\crist\.gemini\antigravity-ide\brain\36c1ded4-8d97-486d-9437-1d789fdc794f"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def setup_driver(width=1440, height=950):
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

def main():
    driver = setup_driver()
    driver.get("http://127.0.0.1:8000/")
    time.sleep(2)
    
    # 1. Login
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
    
    # 2. Seleccionar Cabezote 6x4 y simular llantas inspeccionadas con tintes sutiles
    print("-> Verificando Chasis con tintes sutiles de llantas inspeccionadas...")
    driver.execute_script("""
        const sel = document.getElementById('tipologia');
        for (let opt of sel.options) {
            if (opt.text.toLowerCase().includes('cabezote (6x4)')) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event('change'));
                break;
            }
        }
    """)
    time.sleep(1.5)
    
    # Simular:
    # Pos 1, 4, 5, 6 registradas OK (tinte sutil esmeralda)
    # Pos 2 con novedad (tinte sutil ámbar)
    # Pos 3 seleccionada
    driver.execute_script("""
        posicionesInspeccionadasPlaca = new Set([1, 2, 4, 5, 6]);
        posicionesConNovedadPlaca = new Map([[2, 'Corte en banda de rodamiento']]);
        seleccionarPosicion(3);
    """)
    time.sleep(0.8)
    capture(driver, "verif_chasis_color_sutil.png")
    
    # 3. Probar el nuevo Modal Ejecutivo de Finalización de Inspección
    print("-> Abriendo y verificando Modal Ejecutivo de Informe de Inspección...")
    driver.execute_script("""
        abrirModalInformePdf('FFF123');
    """)
    time.sleep(1.2)
    capture(driver, "verif_modal_informe_ejecutivo.png")
    
    driver.quit()
    print("-> Pruebas en navegador finalizadas con éxito!")

if __name__ == '__main__':
    main()
