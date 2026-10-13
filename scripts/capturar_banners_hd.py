import os
import sys
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from server import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")

def capturar_pantalla():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(2.0) # Esperar a que FastAPI inicie

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--force-device-scale-factor=2") # Calidad HD Retina 2x

    driver = webdriver.Chrome(options=chrome_options)
    
    server_url = "http://127.0.0.1:8765/"
    
    # 1. Captura Desktop HD (1440x900)
    driver.set_window_size(1440, 950)
    driver.get(server_url)
    time.sleep(2.0)
    
    # Ocultar modal de login si estuviera visible y setear usuario activo
    driver.execute_script("""
        const modal = document.getElementById('modalLogin');
        if (modal) modal.style.display = 'none';
        const usuario = document.getElementById('lblUsuarioActivo');
        if (usuario) usuario.textContent = 'Administrador General [ADMIN]';
    """)
    time.sleep(0.5)
    
    # Captura del header en Desktop
    header_el = driver.find_element("css selector", ".app-hd")
    header_el.screenshot("banner_desktop_hd.png")
    print("Capturado: banner_desktop_hd.png")

    # 2. Captura Mobile HD (iPhone 14 / 390x844)
    driver.set_window_size(390, 844)
    time.sleep(1.0)
    header_el = driver.find_element("css selector", ".app-hd")
    header_el.screenshot("banner_mobile_hd.png")
    print("Capturado: banner_mobile_hd.png")

    # 3. Captura Tablet HD (768x1024)
    driver.set_window_size(768, 1024)
    time.sleep(1.0)
    header_el = driver.find_element("css selector", ".app-hd")
    header_el.screenshot("banner_tablet_hd.png")
    print("Capturado: banner_tablet_hd.png")

    driver.quit()
    print("Capturas completadas con exito.")

if __name__ == "__main__":
    capturar_pantalla()
