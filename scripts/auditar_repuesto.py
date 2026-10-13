import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1440,1100')
driver = webdriver.Chrome(options=opts)
driver.get('http://127.0.0.1:8000/')
time.sleep(1.5)
driver.execute_script("""
    localStorage.setItem('tirecheck_usuario_sesion', JSON.stringify({username: 'admin', nombre_completo: 'Administrador', rol: 'admin'}));
    usuarioActual = {username: 'admin', nombre_completo: 'Administrador', rol: 'admin'};
    const m = document.getElementById('modalLogin');
    if (m) m.classList.add('hidden');
    if (typeof cambiarVista === 'function') cambiarVista('patio');
""")
time.sleep(1.0)
driver.execute_script("""
    const sel = document.getElementById('tipologia');
    for (let opt of sel.options) {
        if (opt.text.toLowerCase().includes('trailer (2 ejes - 8 llantas + repuesto)')) {
            sel.value = opt.value;
            sel.dispatchEvent(new Event('change'));
            break;
        }
    }
""")
time.sleep(1.5)
# Scroll to repuesto
driver.execute_script("""
    document.getElementById('seccionRepuestoChasis').scrollIntoView({ behavior: 'instant', block: 'center' });
""")
time.sleep(0.5)
out_path = r'C:\Users\crist\.gemini\antigravity-ide\brain\36c1ded4-8d97-486d-9437-1d789fdc794f\prod_desktop_trailer_repuesto_scroll.png'
driver.save_screenshot(out_path)
driver.quit()
print(f'Screenshot guardado en {out_path}')
