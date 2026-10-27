import io
import pandas as pd
import pytest
import database


def test_importar_precios_cliente_excel(test_db):
    data = [
        {"Cliente": "CLIENTE PRUEBA 1", "Marca": "MICHELIN", "Diseño": "X MULTI Z", "Dimensión": "295/80R22.5", "Tipo": "Llanta nueva", "Precio": 1850000, "Vigente Desde": "2026-01-01"},
        {"Cliente": "CLIENTE PRUEBA 1", "Marca": "BANDAG", "Diseño": "BDR-HT", "Dimensión": "295/80R22.5", "Tipo": "Reencauche", "Precio": 720000, "Vigente Desde": "2026-02-01"},
    ]
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(buf.getvalue())
        tmp_path = tmp.name

    try:
        res = database.importar_precios_cliente_excel(tmp_path)
        assert res["status"] == "ok"
        assert res["registros_guardados"] == 2
        assert res["total_errores"] == 0

        precios = database.listar_precios_cliente("CLIENTE PRUEBA 1")
        assert len(precios) == 2
        michelin = next(p for p in precios if p["marca"] == "MICHELIN")
        assert michelin["precio"] == 1850000
        assert michelin["tipo"] == "Original"
        bandag = next(p for p in precios if p["marca"] == "BANDAG")
        assert bandag["precio"] == 720000
        assert bandag["tipo"] == "Reencauche"
    finally:
        import os
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_api_precios_excel_endpoints(test_db, auth_client):
    # 1. Plantilla
    res_plantilla = auth_client.get("/api/precios-cliente/plantilla-excel")
    assert res_plantilla.status_code == 200
    assert "attachment" in res_plantilla.headers.get("content-disposition", "")
    
    # 2. Importar
    data = [
        {"Cliente": "FLOTA EXCEL TEST", "Marca": "BRIDGESTONE", "Diseño": "R268", "Dimensión": "11R22.5", "Tipo": "Llanta nueva", "Precio": 1600000, "Vigente Desde": "2026-03-01"}
    ]
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    files = {"file": ("precios_test.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res_import = auth_client.post("/api/precios-cliente/importar-excel", files=files)
    assert res_import.status_code == 200
    assert res_import.json()["registros_guardados"] == 1

    # 3. Exportar
    res_export = auth_client.get("/api/precios-cliente/exportar-excel?cliente=FLOTA EXCEL TEST")
    assert res_export.status_code == 200
    assert "Precios_Por_Cliente" in res_export.headers.get("content-disposition", "")
