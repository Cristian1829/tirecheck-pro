with open('database.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update obtener_posiciones_por_tipologia to check the actual schema in catalogo_tipologias
old_obt_pos = """def obtener_posiciones_por_tipologia(tipologia):
    \"\"\"
    Retorna el listado de números de posición correspondientes a la tipología seleccionada.
    \"\"\"
    t = (tipologia or "").lower().strip()
    if "cuatro manos" in t or "4 manos" in t or "8x4" in t:
        # Cabezote 4 Manos (Ejes directores 1,2,3,4 y tracción 5-12)
        return list(range(1, 13))
    elif "trailer" in t or "remolque" in t:
        # Trailer 2 o 3 ejes (habitualmente 8 a 12 llantas)
        return list(range(1, 13))
    elif "camioneta" in t or "liviano" in t or "4x2" in t:
        return [1, 2, 3, 4]
    elif "volqueta" in t or "camilero" in t:
        return list(range(1, 11))
    elif "camion sencillo" in t or "sencillo" in t or "turbo" in t:
        return [1, 2, 3, 4, 5, 6]
    else:
        # Cabezote estándar (6x4 - 10 llantas) por defecto
        return list(range(1, 11))"""

new_obt_pos = """def obtener_posiciones_por_tipologia(tipologia):
    \"\"\"
    Retorna el listado de números de posición correspondientes a la tipología seleccionada,
    consultando dinámicamente su esquema configurado.
    \"\"\"
    import json
    t_nom = str(tipologia or '').strip().lower()
    if t_nom:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT nombre, cant_llantas, esquema_json FROM catalogo_tipologias')
            for r in cursor.fetchall():
                if r[0].strip().lower() == t_nom or t_nom in r[0].strip().lower():
                    if r[2]:
                        try:
                            esq = json.loads(r[2])
                            pos_set = []
                            for eje in esq:
                                for p in eje.get('posiciones', []):
                                    pos_set.append(int(p['pos']))
                            if pos_set:
                                return sorted(list(set(pos_set)))
                        except Exception:
                            pass
                    if r[1]:
                        return list(range(1, int(r[1]) + 1))

    # Reglas heurísticas de respaldo
    if "cuatro manos" in t_nom or "4 manos" in t_nom or "8x4" in t_nom or "biarticulado" in t_nom:
        return list(range(1, 15)) if "biarticulado" in t_nom else list(range(1, 13))
    elif "trailer" in t_nom or "remolque" in t_nom:
        return list(range(1, 13))
    elif "camioneta" in t_nom or "liviano" in t_nom or "4x2" in t_nom:
        return [1, 2, 3, 4]
    elif "volqueta" in t_nom or "camilero" in t_nom or "articulado" in t_nom:
        return list(range(1, 11))
    elif "camion sencillo" in t_nom or "sencillo" in t_nom or "turbo" in t_nom:
        return [1, 2, 3, 4, 5, 6]
    else:
        return list(range(1, 11))"""

assert old_obt_pos in text, 'old_obt_pos not found'
text = text.replace(old_obt_pos, new_obt_pos, 1)

# 2. Update guardar_tipologia to accept optional custom esquema_json
old_guardar_tip = """def guardar_tipologia(nombre, descripcion='', cant_llantas=10):
    nom = (nombre or '').strip()
    if not nom:
        return None
    import json
    cant = int(cant_llantas or 10)
    # Generar esquema automatico
    esquema = [
        {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]}
    ]
    resto = cant - 2
    pos_actual = 3
    eje_num = 2
    while resto > 0:
        if resto >= 4:
            esquema.append({
                'eje': eje_num,
                'nombre': f'Eje {eje_num} (Dual)',
                'tipo': 'traccion',
                'posiciones': [
                    {'pos': pos_actual, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_actual+1},
                    {'pos': pos_actual+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_actual},
                    {'pos': pos_actual+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_actual+3},
                    {'pos': pos_actual+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_actual+2}
                ]
            })
            pos_actual += 4
            resto -= 4
        else:
            esquema.append({
                'eje': eje_num,
                'nombre': f'Eje {eje_num}',
                'tipo': 'traccion',
                'posiciones': [
                    {'pos': pos_actual, 'lado': 'izq', 'rol': 'sencillo', 'dual': False},
                    {'pos': pos_actual+1, 'lado': 'der', 'rol': 'sencillo', 'dual': False}
                ]
            })
            pos_actual += 2
            resto -= 2
        eje_num += 1

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, ?, ?, ?)',
                       (nom, descripcion, cant, json.dumps(esquema)))
        conn.commit()
    return nom"""

new_guardar_tip = """def guardar_tipologia(nombre, descripcion='', cant_llantas=10, esquema_custom=None):
    nom = (nombre or '').strip()
    if not nom:
        return None
    import json
    cant = int(cant_llantas or 10)

    # Si se pasa un esquema personalizado válido
    if esquema_custom and isinstance(esquema_custom, list) and len(esquema_custom) > 0:
        esquema = esquema_custom
    else:
        # Generar esquema inteligente según tipología conocida
        nom_l = nom.lower()
        if 'biarticulado' in nom_l:
            # 1er eje dir (2), 2do eje tracción (4 dual), 3er eje libre (4 dual), 4to eje libre (4 dual) -> 14 llantas
            cant = 14
            esquema = [
                {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]},
                {'eje': 2, 'nombre': 'Eje 2 (Tracción)', 'tipo': 'traccion', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 4}, {'pos': 4, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 3}, {'pos': 5, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 6}, {'pos': 6, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 5}]},
                {'eje': 3, 'nombre': 'Eje 3 (Libre / Arrastre)', 'tipo': 'libre', 'posiciones': [{'pos': 7, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 8}, {'pos': 8, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 7}, {'pos': 9, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 10}, {'pos': 10, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 9}]},
                {'eje': 4, 'nombre': 'Eje 4 (Libre / Arrastre)', 'tipo': 'libre', 'posiciones': [{'pos': 11, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 12}, {'pos': 12, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 11}, {'pos': 13, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 14}, {'pos': 14, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 13}]}
            ]
        elif 'articulado' in nom_l and 'bi' not in nom_l:
            # 1er eje dir (2), 2do eje tracción (4 dual), 3er eje libre (4 dual) -> 10 llantas
            cant = 10
            esquema = [
                {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]},
                {'eje': 2, 'nombre': 'Eje 2 (Tracción)', 'tipo': 'traccion', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 4}, {'pos': 4, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 3}, {'pos': 5, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 6}, {'pos': 6, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 5}]},
                {'eje': 3, 'nombre': 'Eje 3 (Libre / Arrastre)', 'tipo': 'libre', 'posiciones': [{'pos': 7, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 8}, {'pos': 8, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 7}, {'pos': 9, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 10}, {'pos': 10, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 9}]}
            ]
        else:
            # Generar esquema automático estándar
            esquema = [
                {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]}
            ]
            resto = cant - 2
            pos_actual = 3
            eje_num = 2
            while resto > 0:
                if resto >= 4:
                    esquema.append({
                        'eje': eje_num,
                        'nombre': f'Eje {eje_num} (Dual)',
                        'tipo': 'traccion',
                        'posiciones': [
                            {'pos': pos_actual, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_actual+1},
                            {'pos': pos_actual+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_actual},
                            {'pos': pos_actual+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_actual+3},
                            {'pos': pos_actual+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_actual+2}
                        ]
                    })
                    pos_actual += 4
                    resto -= 4
                else:
                    esquema.append({
                        'eje': eje_num,
                        'nombre': f'Eje {eje_num}',
                        'tipo': 'traccion',
                        'posiciones': [
                            {'pos': pos_actual, 'lado': 'izq', 'rol': 'sencillo', 'dual': False},
                            {'pos': pos_actual+1, 'lado': 'der', 'rol': 'sencillo', 'dual': False}
                        ]
                    })
                    pos_actual += 2
                    resto -= 2
                eje_num += 1

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, ?, ?, ?)',
                       (nom, descripcion, cant, json.dumps(esquema)))
        conn.commit()
    return nom"""

assert old_guardar_tip in text, 'old_guardar_tip not found'
text = text.replace(old_guardar_tip, new_guardar_tip, 1)

# 3. Update obtener_trazabilidad_kpis_llanta to calculate porcentaje_desgaste and cpk_proyectado
old_kpi_return = """        # Proyección útil de vida calculada hasta el límite de cambio programado por cliente (por defecto 3.0 mm)
        mm_utiles = max(0.0, prof_ini - limite_cambio) if prof_ini > limite_cambio else 0.0
        proyeccion_total_km = (km_por_mm * mm_utiles) if km_por_mm > 0 else 0.0
        km_restantes = max(0.0, proyeccion_total_km - km_rodados) if proyeccion_total_km > 0 else 0.0
        
        # Sugerencia de cambio si la profundidad actual más baja ya alcanzó o superó el límite de cambio
        requiere_cambio = (prof_actual_min > 0 and prof_actual_min <= limite_cambio)

        resultados.append({
            'numero_interno': num,
            'placa': ultima['placa'],
            'posicion': ultima['posicion'],
            'marca': ultima['marca'],
            'diseno': ultima['diseno'],
            'dimension': ultima['dimension'],
            'vida': ultima['vida'],
            'cliente': ultima.get('cliente', ''),
            'subcliente': ultima.get('subcliente', ''),
            'fecha_ult_insp': ultima['fecha'],
            'total_inspecciones': len(group),
            'prof_inicial': round(prof_ini, 1),
            'prof_actual_min': round(prof_actual_min, 1),
            'desgaste_mm': round(desgaste_mm, 1),
            'km_montaje': round(km_mont, 0),
            'km_actual': round(km_ult, 0),
            'km_rodados': round(km_rodados, 0),
            'km_por_mm': round(km_por_mm, 1),
            'precio': round(precio, 2),
            'cpk': round(cpk, 4),
            'limite_retiro_mm': round(limite_cambio, 1),
            'proyeccion_total_km': round(proyeccion_total_km, 0),
            'km_restantes': round(km_restantes, 0),
            'requiere_cambio': 'SÍ' if requiere_cambio else 'NO'
        })"""

new_kpi_return = """        # Proyección útil de vida calculada hasta el límite de cambio programado por cliente (por defecto 3.0 mm)
        mm_utiles = max(0.0, prof_ini - limite_cambio) if prof_ini > limite_cambio else 0.0
        proyeccion_total_km = (km_por_mm * mm_utiles) if km_por_mm > 0 else 0.0
        km_restantes = max(0.0, proyeccion_total_km - km_rodados) if proyeccion_total_km > 0 else 0.0
        
        # Porcentaje de desgaste respecto a la profundidad útil de la llanta
        if mm_utiles > 0 and desgaste_mm >= 0:
            pct_desgaste = min(100.0, (desgaste_mm / mm_utiles) * 100.0)
        else:
            pct_desgaste = 0.0

        # CPK Proyectado = Precio / Proyección Total Km (si hay proyección estimada)
        cpk_proyectado = (precio / proyeccion_total_km) if (precio > 0 and proyeccion_total_km > 0) else 0.0

        # Sugerencia de cambio si la profundidad actual más baja ya alcanzó o superó el límite de cambio
        requiere_cambio = (prof_actual_min > 0 and prof_actual_min <= limite_cambio)

        resultados.append({
            'numero_interno': num,
            'placa': ultima['placa'],
            'posicion': ultima['posicion'],
            'marca': ultima['marca'],
            'diseno': ultima['diseno'],
            'dimension': ultima['dimension'],
            'vida': ultima['vida'],
            'cliente': ultima.get('cliente', ''),
            'subcliente': ultima.get('subcliente', ''),
            'fecha_ult_insp': ultima['fecha'],
            'total_inspecciones': len(group),
            'prof_inicial': round(prof_ini, 1),
            'prof_actual_min': round(prof_actual_min, 1),
            'desgaste_mm': round(desgaste_mm, 1),
            'porcentaje_desgaste': round(pct_desgaste, 1),
            'km_montaje': round(km_mont, 0),
            'km_actual': round(km_ult, 0),
            'km_rodados': round(km_rodados, 0),
            'km_por_mm': round(km_por_mm, 1),
            'precio': round(precio, 2),
            'cpk': round(cpk, 4),
            'cpk_proyectado': round(cpk_proyectado, 4),
            'limite_retiro_mm': round(limite_cambio, 1),
            'proyeccion_total_km': round(proyeccion_total_km, 0),
            'km_restantes': round(km_restantes, 0),
            'requiere_cambio': 'SÍ' if requiere_cambio else 'NO'
        })"""

assert old_kpi_return in text, 'old_kpi_return not found'
text = text.replace(old_kpi_return, new_kpi_return, 1)

with open('database.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('database.py successfully updated with new KPIs and tipologia builder!')
