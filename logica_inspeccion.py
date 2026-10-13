import pandas as pd
import unicodedata

def normalizar_texto(texto):
    if not isinstance(texto, str):
        return str(texto)
    # Remover tildes y caracteres especiales, strip y lower
    nfkd = unicodedata.normalize('NFKD', texto)
    sin_tildes = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return sin_tildes.strip().lower()

def clasificar_vehiculo(v):
    v_str = str(v).strip()
    if len(v_str) > 0 and v_str[0].isalpha():
        letters = sum(1 for c in v_str if c.isalpha())
        if letters == 3:
            return 'Cabezote'
        elif letters == 1:
            return 'Trailer'
    return 'Desconocido'

def to_float(val):
    try:
        if pd.isna(val):
            return 0.0
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0

def procesar_sabana_inspeccion_ampliada(file_path):
    """
    Procesa el archivo Excel de la sábana de inspección.
    Retorna un DataFrame con los resultados resumidos por vehículo.
    """
    df = pd.read_excel(file_path, sheet_name=0)
    
    # Mapeo flexible de columnas para tolerar acentos, mayúsculas y encoding
    cols_norm_map = {normalizar_texto(c): c for c in df.columns}
    
    alias_esperados = {
        'vehiculo': ['vehiculo', 'placa', 'equipo'],
        'posicion': ['posicion montaje', 'posicion', 'pos'],
        'prof_int': ['ult. prof interior', 'prof interior', 'prof. interior', 'ult prof interior'],
        'prof_ext': ['ult. prof exterior', 'prof exterior', 'prof. exterior', 'ult prof exterior'],
        'prof_baja': ['prof. mas baja', 'prof mas baja', 'prof. baja', 'prof baja'],
        'dimension': ['dimension', 'medida', 'dim']
    }
    
    col_encontradas = {}
    for canonico, lista_alias in alias_esperados.items():
        for alias in lista_alias:
            alias_norm = normalizar_texto(alias)
            if alias_norm in cols_norm_map:
                col_encontradas[canonico] = cols_norm_map[alias_norm]
                break
                
    faltantes = [canonico for canonico in alias_esperados if canonico not in col_encontradas]
    if faltantes:
        raise ValueError(f"No se encontraron columnas para los siguientes campos: {', '.join(faltantes)}. Columnas presentes: {list(df.columns)}")

    # Renombrar temporalmente para procesar de forma uniforme
    col_veh = col_encontradas['vehiculo']
    col_pos = col_encontradas['posicion']
    col_int = col_encontradas['prof_int']
    col_ext = col_encontradas['prof_ext']
    col_baja = col_encontradas['prof_baja']
    col_dim = col_encontradas['dimension']

    df[col_pos] = pd.to_numeric(df[col_pos], errors='coerce')
    df = df.dropna(subset=[col_veh, col_pos]).copy()
    df[col_pos] = df[col_pos].astype(int)

    df[col_int] = df[col_int].apply(to_float)
    df[col_ext] = df[col_ext].apply(to_float)
    df[col_baja] = df[col_baja].apply(to_float)

    df['Tipo_Vehiculo'] = df[col_veh].apply(clasificar_vehiculo)
    resultados = []
    
    for veh, group in df.groupby(col_veh):
        t_veh = group['Tipo_Vehiculo'].iloc[0]
        max_pos = group[col_pos].max()
        es_cuatro_manos = (t_veh == 'Cabezote' and max_pos >= 12)
        
        # 1. Alineación y Rotación Direccional
        plan_alineacion = False
        detalles_alineacion = []

        if t_veh == 'Cabezote':
            pos_dir = [1, 2, 3, 4] if es_cuatro_manos else [1, 2]
            for p in pos_dir:
                r = group[group[col_pos] == p]
                if not r.empty:
                    diff = abs(r[col_int].values[0] - r[col_ext].values[0])
                    if diff >= 2:
                        plan_alineacion = True
                        detalles_alineacion.append(f"Pos {p} (dif {diff:.1f}mm)")
        elif t_veh == 'Trailer':
            for _, r in group.iterrows():
                diff = r[col_int] - r[col_ext]
                if diff >= 2:
                    plan_alineacion = True
                    detalles_alineacion.append(f"Pos {int(r[col_pos])} (dif {diff:.1f}mm)")
                    
        # 2. Plan por Dual Mal Apareado (Por Profundidad o por Dimensión)
        plan_dual = False
        detalles_dual = []

        pairs = [(3,4), (5,6), (7,8), (9,10)] if t_veh == 'Cabezote' and not es_cuatro_manos else \
                [(5,6), (7,8), (9,10), (11,12)] if t_veh == 'Cabezote' and es_cuatro_manos else \
                [(1,2), (3,4), (5,6), (7,8), (9,10), (11,12)]
                
        for p_a, p_b in pairs:
            t_a = group[group[col_pos] == p_a]
            t_b = group[group[col_pos] == p_b]
            if not t_a.empty and not t_b.empty:
                pb_a = t_a[col_baja].values[0]
                pb_b = t_b[col_baja].values[0]
                dim_a = str(t_a[col_dim].values[0]).strip()
                dim_b = str(t_b[col_dim].values[0]).strip()
                
                diff_pb = abs(pb_a - pb_b)
                razones = []
                if diff_pb >= 2:
                    razones.append(f"desgaste dif {diff_pb:.1f}mm")
                if dim_a != dim_b:
                    razones.append(f"dims distintas ({dim_a} vs {dim_b})")
                
                if razones:
                    plan_dual = True
                    detalles_dual.append(f"Dual {p_a}-{p_b}: {', '.join(razones)}")
                    
        tipo_descr = f"{t_veh}{' (Cuatro Manos)' if es_cuatro_manos else ''}"
        
        resultados.append({
            'Vehículo': veh,
            'Tipo': tipo_descr,
            'Plan_Alineacion': "SÍ" if plan_alineacion else "NO",
            'Plan_Dual_Mal_Apareado': "SÍ" if plan_dual else "NO",
            'Detalle_Alineacion': "; ".join(detalles_alineacion) if detalles_alineacion else "OK",
            'Detalle_Dual': "; ".join(detalles_dual) if detalles_dual else "OK"
        })
        
    return pd.DataFrame(resultados)
