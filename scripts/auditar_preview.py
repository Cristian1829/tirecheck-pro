import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

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
    print(f"Screenshot saved: {path}")
    return path

def main():
    url = "http://127.0.0.1:8000/preview-chasis"
    
    # 1. ESCRITORIO (1440 x 900)
    print("--- 1. Pruebas en Escritorio (1440x900) ---")
    driver = setup_driver(1440, 950)
    driver.get(url)
    time.sleep(1.5)
    
    # Escenario 1: Algunas registradas (con novedad)
    driver.execute_script("aplicarEscenario(1);")
    time.sleep(0.5)
    capture(driver, "preview_desktop_algunas_registradas.png")
    
    # Escenario 0: 0 Registradas
    driver.execute_script("aplicarEscenario(0);")
    time.sleep(0.5)
    capture(driver, "preview_desktop_cero_registradas.png")
    
    # Escenario 2: Todas registradas
    driver.execute_script("aplicarEscenario(2);")
    time.sleep(0.5)
    capture(driver, "preview_desktop_todas_registradas.png")
    
    # Otra tipología en Escritorio: Trailer con repuesto
    driver.execute_script("cambiarTipologiaPrueba('Trailer (2 Ejes - 8 Llantas + Repuesto)');")
    driver.execute_script("aplicarEscenario(1);")
    time.sleep(0.5)
    capture(driver, "preview_desktop_trailer_repuesto.png")
    
    # Tipología: Cuatro Manos (8x4)
    driver.execute_script("cambiarTipologiaPrueba('Cabezote (Cuatro Manos / 8x4)');")
    driver.execute_script("aplicarEscenario(1);")
    time.sleep(0.5)
    capture(driver, "preview_desktop_cuatro_manos.png")
    
    driver.quit()

    # 2. TABLET (768 x 1024)
    print("--- 2. Pruebas en Tablet (768x1024) ---")
    driver = setup_driver(768, 1024)
    driver.get(url)
    time.sleep(1.5)
    driver.execute_script("cambiarTipologiaPrueba('Cabezote (6x4)');")
    driver.execute_script("aplicarEscenario(1);")
    time.sleep(0.5)
    capture(driver, "preview_tablet_cabezote.png")
    
    driver.execute_script("cambiarTipologiaPrueba('Camión Sencillo (4x2)');")
    driver.execute_script("aplicarEscenario(1);")
    time.sleep(0.5)
    capture(driver, "preview_tablet_sencillo.png")
    driver.quit()

    # 3. MÓVIL (390 x 844)
    print("--- 3. Pruebas en Móvil (390x844) ---")
    driver = setup_driver(390, 844)
    driver.get(url)
    time.sleep(1.5)
    driver.execute_script("cambiarTipologiaPrueba('Cabezote (6x4)');")
    driver.execute_script("aplicarEscenario(1);")
    time.sleep(0.5)
    capture(driver, "preview_mobile_cabezote.png")
    
    # Scroll hacia abajo en móvil para ver mediciones
    driver.execute_script("window.scrollTo(0, 600);")
    time.sleep(0.5)
    capture(driver, "preview_mobile_mediciones.png")
    driver.quit()

    print("Todas las pruebas y capturas de vista previa se ejecutaron exitosamente.")

if __name__ == "__main__":
    main()
