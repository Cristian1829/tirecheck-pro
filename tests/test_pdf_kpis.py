"""PDF de la suite de KPIs: secciones según licencia, gráficos capturados y tablas de cifras."""
import base64
import io

import pytest
from PIL import Image

import database
import pdf_kpis


def _data_url_jpeg(ancho=800, alto=300):
    """Igual a lo que manda el navegador: canvas sobre fondo blanco en JPEG."""
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), (37, 99, 235)).save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


_PNG = _data_url_jpeg()

_DATOS = {
    "licencia": "FULL", "unidad": "km",
    "ahorro_roi": {"ahorro_potencial_total_cop": 1500000, "cascos_en_ventana_salvamento": 2, "total_alertas_cambiazo": 1},
    "calidad_datos": {"llantas": 10, "sin_precio": 3},
    "kpi_01": {"porcentaje_cumplimiento": 80.0, "vehiculos_inspeccionados": 8, "total_padron_activo": 10,
               "placas_pendientes": [{"placa": "ABC123", "cliente": "C1", "tipologia": "TRACTO"}]},
    "kpi_07": {"rotaciones_sugeridas": [{"placa": "ABC123", "esquema": "P3 ↔ P9", "delta_ejes_mm": 2.4, "estado": "Reincidente"}]},
    "kpi_12": {"mm_gastados": 5.2, "profundidad_actual": 9.1, "pct_desgaste": 40, "km_recorridos": 52000},
    "kpi_cpk": {"flota": {"cpk_operativo": 12.5, "cpk_total": None, "llantas_con_cpk": 4, "llantas_sin_precio": 3},
                "por_vida": [{"vida": "Original", "llantas": 4, "cpk_operativo": 12.5, "cpk_proyectado": 9.0}],
                "administrativo": [{"mes": "2026-09", "inversion": 2000000, "km_flota": 100000, "cpk_administrativo": 20.0}]},
    "kpi_17": {"cantidad_fvu": 3, "indice_reencauchabilidad_ir": 1.2, "pct_reencauche_fvu": 33.3},
    "kpi_20": {"matriz_mrp": [{"dimension": "295/80R22.5", "demanda_flota": 4, "necesidad_bruta": 6,
                               "stock_disponible": 2, "compra_neta_sugerida": 4, "presupuesto_estimado_cop": 6000000}]},
    "kpi_tendencias": {"meses": [{"mes": "2026-09", "vehiculos_inspeccionados": 5, "pct_presion_correcta": 70.0,
                                  "pct_en_retiro": 10.0, "prof_minima_promedio": 8.4, "pct_alerta_alineacion": 5.0,
                                  "cpk_operativo": None}]},
}


def test_secciones_segun_licencia():
    light = [s[0] for s in pdf_kpis.secciones_por_licencia("LIGHT")]
    full = [s[0] for s in pdf_kpis.secciones_por_licencia("FULL")]
    assert light == [1, 2, 6]
    assert full == [1, 2, 3, 4, 5, 6]
    assert [s[0] for s in pdf_kpis.secciones_por_licencia("PRO")] == full


def test_cada_indicador_tiene_explicacion():
    for _, _, _, kpis in pdf_kpis.SECCIONES:
        for clave, titulo, explica, _ in kpis:
            assert titulo and len(explica) > 80, clave


def test_pdf_full_y_light_con_graficos():
    graficos = {c: _PNG for _, _, _, kpis in pdf_kpis.SECCIONES for _, _, _, ids in kpis for c in ids}
    full = pdf_kpis.generar_pdf_kpis(_DATOS, graficos, {"cliente": "C1"})
    light = pdf_kpis.generar_pdf_kpis({**_DATOS, "licencia": "LIGHT"}, graficos, {})
    assert full.startswith(b"%PDF") and light.startswith(b"%PDF")
    # LIGHT lleva menos páginas: no incluye proyecciones, bajas ni MRP
    assert full.count(b"/Type /Page\n") > light.count(b"/Type /Page\n") or len(full) > len(light)


def test_pdf_no_muestra_potencial_de_ahorro(monkeypatch):
    """El potencial de ahorro de la pantalla no va en el informe."""
    textos = []
    original = pdf_kpis.SimpleDocTemplate.build

    def capturar(self, flowables, **kw):
        def recorrer(f):
            if hasattr(f, 'getPlainText'):
                textos.append(f.getPlainText())
            for hijo in getattr(f, '_content', []) or []:
                recorrer(hijo)
            for fila in getattr(f, '_cellvalues', []) or []:
                for celda in fila:
                    for c in (celda if isinstance(celda, list) else [celda]):
                        recorrer(c)
        for f in flowables:
            recorrer(f)
        return original(self, flowables, **kw)

    monkeypatch.setattr(pdf_kpis.SimpleDocTemplate, "build", capturar)
    pdf_kpis.generar_pdf_kpis(_DATOS, {}, {})
    texto = " ".join(textos)
    assert "Informe de Indicadores" in texto
    assert "ahorro" not in texto.lower() and "1.500.000" not in texto


def test_pdf_sin_graficos_ni_datos():
    """Sin datos ni capturas el informe sale igual, con los avisos de 'sin datos'."""
    pdf = pdf_kpis.generar_pdf_kpis({"licencia": "FULL"}, {}, {})
    assert pdf.startswith(b"%PDF")


def test_graficos_anchos_van_en_fila_completa():
    """KPI 14 se captura apaisado: cada gráfico ocupa su propia fila a todo el ancho."""
    ancho = _data_url_jpeg(2200, 760)
    ids = ["canvasKpi14_proy", "canvasKpi14_kmmm", "canvasKpi14_cpk"]
    t = pdf_kpis._bloque_graficos(ids, {c: ancho for c in ids})
    assert len(t._cellvalues) == 3
    # Cada gráfico lleva su subtítulo y la imagen a más de media hoja
    assert all(fila[0][1].drawWidth > pdf_kpis.ANCHO / 2 for fila in t._cellvalues)
    assert "Rendimiento por milímetro" in t._cellvalues[1][0][0].getPlainText()
    # Los de proporción normal siguen de a dos por fila
    t2 = pdf_kpis._bloque_graficos(["a", "b", "c"], {k: _data_url_jpeg(600, 500) for k in "abc"})
    assert len(t2._cellvalues) == 2


def hojas_en_blanco(pdf_bytes):
    """Hojas que solo tienen el encabezado y el pie de página."""
    pypdfium2 = pytest.importorskip("pypdfium2")
    pdf = pypdfium2.PdfDocument(pdf_bytes)
    vacias = []
    for i in range(len(pdf)):
        lineas = [l for l in pdf[i].get_textpage().get_text_range().splitlines()
                  if l.strip() and not any(m in l for m in ("INFORME DE INDICADORES", "Corte:", "Página"))]
        if not lineas:
            vacias.append(i + 1)
    return vacias


def test_ninguna_hoja_queda_en_blanco():
    """Un indicador que llena la hoja justo antes de un salto de sección no deja una hoja vacía."""
    # Con KPI 02 de 1000x306 el KPI 04 termina justo al final de la hoja 2 (antes salía la hoja 3 en blanco)
    graficos = {'canvasKpi03_pct': _data_url_jpeg(600, 400), 'canvasKpi03_ciclos': _data_url_jpeg(600, 400),
                'canvasKpi04_tipologia': _data_url_jpeg(600, 500), 'canvasKpi04_marca': _data_url_jpeg(600, 500),
                'canvasKpi04_dimension': _data_url_jpeg(600, 500)}
    for alto in range(296, 317, 2):
        graficos['canvasKpi02_volumen'] = _data_url_jpeg(1000, alto)
        assert hojas_en_blanco(pdf_kpis.generar_pdf_kpis({'licencia': 'LIGHT'}, graficos, {})) == [], alto


def test_imagen_invalida_no_rompe():
    assert pdf_kpis._imagen("data:image/png;base64,no-es-imagen", 100, 100) is None


def test_pdf_con_suite_real_vacia(test_db):
    datos = database.obtener_suite_completa_20_kpis({})
    assert pdf_kpis.generar_pdf_kpis(datos, {}, {}).startswith(b"%PDF")


def test_pdf_composicion():
    """PDF de Composición con lo que muestra la pantalla: filtros, tarjetas, reglas, gráficas y matriz."""
    datos = {
        "filtros": {"Cliente": "COLTANQUES", "Sede / Patio": "Todas"},
        "eje": "Todos los ejes",
        "tarjetas": [{"etiqueta": "Total llantas", "valor": "32", "detalle": "6 vehículos activos"},
                     {"etiqueta": "Marca principal", "valor": "MICHELIN", "detalle": "8 llantas (25,0%)"}],
        "reglas": [{"titulo": "Cero Reencauches en Dirección", "estado": "CUMPLE", "detalle": "0,0% en eje direccional"}],
        "graficos": {c: _data_url_jpeg(900, 500) for c, _, _ in pdf_kpis.GRAFICAS_COMPOSICION},
        "matriz": {"encabezados": ["Marca", "Diseño", "Total"], "filas": [["MICHELIN", "X MULTI", "8"]] * 3},
    }
    pdf = pdf_kpis.generar_pdf_composicion(datos)
    assert pdf.startswith(b"%PDF")
    assert hojas_en_blanco(pdf) == []
    # Los emojis de la pantalla no llegan al PDF (la fuente no los tiene y salían como cuadros)
    assert pdf_kpis._sin_emojis("🚨 REGLA DE ORO 1 INCUMPLIDA · 0,0% ≥ 70%") == "REGLA DE ORO 1 INCUMPLIDA · 0,0% ≥ 70%"
    # Sin gráficas ni matriz también sale (con sus avisos de "sin datos")
    assert pdf_kpis.generar_pdf_composicion({}).startswith(b"%PDF")
