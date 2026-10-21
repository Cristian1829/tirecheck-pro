# Especificación de Parámetros de Mantenimiento y Algoritmos de Rotación (Para Implementación en Software Externo)

Este documento detalla la lógica matemática, parámetros de ingeniería automotriz y algoritmos de optimización de neumáticos utilizados para generar planes de mantenimiento preventivo y correctivo automatizados en flotas.

---

## 1. Tabla de Parámetros Técnicos Configurables por Cliente / Operación

Cada empresa o tipo de operación (Carretera Nacional, Distribución Urbana, Minería / Fuera de Carretera) posee exigencias diferentes. El motor de mantenimiento debe parametrizarse mediante la siguiente estructura:

```json
{
  "ParametrosMantenimiento": {
    "mm_retiro_direccional": 4.0,
    "mm_retiro_traccion": 3.0,
    "mm_retiro_arrastre": 3.0,
    "rango_semaforo_amarillo_mm": 2.0,
    "criterio_profundidad_calculo": "MINIMO",
    
    "psi_objetivo_direccional": 110.0,
    "psi_objetivo_traccion": 100.0,
    "psi_objetivo_arrastre": 100.0,
    "tolerancia_psi_baja_pct": 10.0,
    "tolerancia_psi_alta_pct": 10.0,
    
    "tolerancia_desalineacion_hombros_mm": 2.0,
    "tolerancia_mal_apareo_pacha_mm": 2.5,
    "tolerancia_busqueda_recambio_bodega2_mm": 1.5,
    "tolerancia_simetria_eje_opuesto_mm": 3.5,
    "umbral_diferencia_rotacion_ejes_mm": 3.0,
    "tolerancia_inversion_trailer_mm": 1.5,
    "modo_rotacion_ejes": "ESTANDAR_FIJO"
  }
}
```

### Significado de cada Parámetro:
* **`mm_retiro_direccional` (4.0 mm):** Las llantas delanteras se retiran antes para evitar hidroplaneo, garantizar maniobrabilidad y preservar la carcasa intacta para su 1er reencauche (las llantas direccionales deben ser 100% originales nuevas).
* **`mm_retiro_traccion` y `mm_retiro_arrastre` (3.0 mm):** Límite seguro de retiro en ruedas motrices y remolques antes de exponer las lonas de la carcasa al agua o piedras.
* **`tolerancia_desalineacion_hombros_mm` (2.0 mm):** Si la diferencia entre la ranura externa y la ranura interna de la misma rueda supera los 2.0 mm, el vehículo tiene problemas de convergencia, divergencia o caída (camber).
* **`tolerancia_mal_apareo_pacha_mm` (2.5 mm):** Diferencia máxima tolerable de profundidad entre las dos ruedas gemelas de un mismo extremo. Si se supera, la rueda con mayor diámetro arrastra a la menor y absorbe sobrecarga destructiva.
* **`tolerancia_busqueda_recambio_bodega2_mm` (1.5 mm):** Rango de búsqueda para encontrar en la Bodega 2 una llanta compañera compatible.

---

## 2. Los 3 Algoritmos de Auto-Ajuste de Profundidades en el Mismo Vehículo

Cuando un vehículo ingresa a inspección con pachas disparejas o desgaste asimétrico, el sistema no debe limitarse a exigir la compra de llantas nuevas; **primero debe ejecutar el algoritmo de optimización interna para equilibrar el propio vehículo**:

---

### Algoritmo 1: Regla Exclusiva del Eje Direccional
* **Enunciado Técnico:** *En cualquier eje direccional (Eje 1 en cabezotes convencionales, o Eje 1 y Eje 2 en cabezotes 8x4 / "cuatro manos"), la llanta con MAYOR profundidad siempre debe ubicarse en el LADO IZQUIERDO (Posición 1 o Posición 3).*
* **Justificación Física y Vial:**
  - El peralte estándar de la calzada (inclinación de 2% hacia la berma derecha para desagüe) descarga mayor peso y esfuerzo transversal sobre el lado izquierdo del vehículo en curvas a la derecha.
  - Las intersecciones y retornos viales cargan mayor fuerza centrípeta sobre el hombro direccional izquierdo.
  - Colocar la llanta más alta a la izquierda contrarresta la tendencia del camión a desviarse ("jalar") hacia la cuneta.
* **Pseudocódigo de Implementación:**

```python
def evaluar_regla_direccional(pos_izq, pos_der, prof_izq, prof_der, serial_izq, serial_der):
    # Si la llanta derecha tiene mayor profundidad por 0.5 mm o más:
    if prof_der > prof_izq and (prof_der - prof_izq) >= 0.5:
        return {
            "accion": "ROTACION_DIRECCIONAL_CRUZADA",
            "prioridad": "ALTA",
            "instruccion": f"Cruzar P{pos_der} ({serial_der}: {prof_der}mm) <-> P{pos_izq} ({serial_izq}: {prof_izq}mm)",
            "resultado": f"Deja la llanta más alta ({prof_der}mm) en Posición {pos_izq} (Lado Izquierdo)",
            "gap_corregido": round(prof_der - prof_izq, 1)
        }
    return None
```

---

### Algoritmo 2: Emparejamiento Óptimo de Pachas (Duales)
* **Objetivo:** Tomar todas las llantas duales del camión (ej. 8 llantas en un 6x4, o 12 en un tráiler) y combinarlas de modo que la diferencia dentro de cada pacha sea la mínima matemáticamente posible.
* **Regla de Posición Exterior vs Interior (Bombeo Vial):**
  - En cada pacha resultante, **la llanta con MAYOR profundidad va al EXTERIOR** y la de **MENOR profundidad al INTERIOR**.
  - *Causa:* La corona de la vía hace que la llanta interna ruede en una cota más alta que la externa. Al colocar la llanta más alta en el exterior, ambos radios de rodadura dinámicos bajo carga se igualan, evitando el arrastre parasitario y el calentamiento por fricción.
* **Pseudocódigo de Implementación:**

```python
def emparejar_pachas_optimas(llantas_duales_vehiculo):
    # llantas_duales_vehiculo es una lista de dicts: [{'serial': 'L1', 'prof': 9.2}, ...]
    
    # 1. Ordenar todas las llantas duales por profundidad ascendente
    ordenadas = sorted(llantas_duales_vehiculo, key=lambda x: x['prof'])
    
    pares_optimos = []
    # 2. Tomar de a pares contiguos (0 con 1, 2 con 3, 4 con 5...)
    for i in range(0, len(ordenadas), 2):
        llanta_menor = ordenadas[i]
        llanta_mayor = ordenadas[i + 1]
        
        pares_optimos.append({
            "par_index": i // 2,
            "llanta_exterior": llanta_mayor,  # Mayor profundidad al exterior
            "llanta_interior": llanta_menor,  # Menor profundidad al interior
            "diferencia_pacha_mm": round(llanta_mayor['prof'] - llanta_menor['prof'], 1),
            "profundidad_promedio_mm": round((llanta_mayor['prof'] + llanta_menor['prof']) / 2.0, 2)
        })
        
    return pares_optimos
```

---

### Algoritmo 3: Jerarquía y Nivelación de Alturas por Eje
Una vez armados los pares óptimos del Algoritmo 2, ¿a cuál eje específico debe asignarse cada par?

#### Caso A: Tándem 6x4 o Doble Troque (4 Pachas)
* **Problema:** Si el Eje Motriz 1 (Delantero) tiene un promedio de 12 mm y el Eje Motriz 2 (Trasero) tiene 8 mm, el diferencial intermedio (Power Divider) sufre recalentamiento y desgaste prematuro por diferencia de revoluciones.
* **Solución Óptima:**
  - Ordenar los 4 pares por su profundidad promedio: `Par[0] < Par[1] < Par[2] < Par[3]`.
  - Asignar al **Eje Motriz 1**: `Par[0] + Par[3]` (Promedio balanceado).
  - Asignar al **Eje Motriz 2**: `Par[1] + Par[2]` (Promedio balanceado).
  - *Resultado:* La diferencia promedio entre ambos ejes motrices se reduce a menos de 0.5 mm.

#### Caso B: Tráiler / Semirremolque de 2 Ejes
* **Regla de Distribución:**
  $$\overline{\text{Prof}}_{\text{Eje 1 (Delantero)}} < \overline{\text{Prof}}_{\text{Eje 2 (Trasero)}}$$
* Las llantas con mayor caucho van al eje trasero porque absorbe mayor torsión durante giros cerrados (barrido de cola).

#### Caso C: Tráiler / Semirremolque de 3 Ejes
* **Regla de Distribución de Alturas:**
  $$\text{Eje 2 (Central)} < \text{Eje 1 (Delantero)} < \text{Eje 3 (Trasero)}$$
* El eje central sufre el menor arrastre lateral durante los radios de giro, por lo que debe recibir los pares con menor remanente; el eje 3 sufre el mayor esfuerzo de cizallamiento y debe tener las llantas con mayor profundidad.

---

## 3. Matriz de Diagnósticos y Acciones del Plan de Mantenimiento

Al evaluar una inspección completa, el motor genera un listado de tareas con la siguiente jerarquía de prioridades:

| Código | Condición Detectada | Acción Recomendada en Taller | Prioridad |
| :--- | :--- | :--- | :--- |
| **PLAN-01** | $\text{prof\_min} \le \text{mm\_retiro}$ | **Desmonte Inmediato a Reencauche / FVU** | 🔴 Crítica |
| **PLAN-02** | $\text{prof\_min} \le \text{mm\_retiro} + 1.0\text{ mm}$ | **Próximo Cambio Programado (< 15 días)** | 🟡 Alta |
| **PLAN-03** | $|\text{prof\_ext} - \text{prof\_int}| \ge 2.0\text{ mm}$ | **Alineación de Eje + Rotar sobre el mismo Rin** | 🟡 Alta |
| **PLAN-04** | $\text{prof\_der} > \text{prof\_izq}$ en Eje Dir ($\ge 0.5$) | **Invertir Rueda Izquierda con Rueda Derecha** | 🟡 Alta |
| **PLAN-05** | $\Delta \text{Pacha} > 2.5\text{ mm}$ (Sin cruce interno) | **Desmontar llanta baja a Bodega 2 y Aparear desde Stock** | 🟠 Media |
| **PLAN-06** | $\Delta \text{Pachas} > 2.5\text{ mm}$ (Con cruce interno) | **Ejecutar Auto-Ajuste Interno del Vehículo** | 🟢 Preventiva |
| **PLAN-07** | $\Delta \text{Tándem} \ge 1.5\text{ mm}$ en 6x4 | **Rotación en Equis Larga de Ejes de Tracción** | 🟢 Preventiva |
| **PLAN-08** | $|\Delta \text{PSI}| > 10\%$ | **Calibración de Presión de Inflado en Frío** | 🔴 Crítica |

---

## 4. Schema JSON del Plan de Mantenimiento por Vehículo

```json
{
  "vehiculo": {
    "placa": "TPX067",
    "tipologia": "CABEZOTE 6X4",
    "cliente": "TRANSPORTES DE LA SIERRA",
    "odometro": 105420.0,
    "fecha_inspeccion": "2026-10-20"
  },
  "diagnostico_global": {
    "estado_general": "REQUIERE_ACCION",
    "calificacion_salud_vehiculo": 76.5,
    "acciones_requeridas_total": 3
  },
  "ordenes_de_trabajo": [
    {
      "tipo": "DIRECCIONAMIENTO_ALTURA_EJE_DIRECCIONAL",
      "prioridad": "ALTA",
      "descripcion": "La llanta derecha tiene mayor profundidad que la izquierda en Eje 1.",
      "instruccion": "Desmontar P2 (LL-802: 13.5mm) y P1 (LL-801: 12.0mm) e intercambiarlas de lado.",
      "meta": "Garantizar la llanta más alta en Posición 1 (Izquierda)."
    },
    {
      "tipo": "AUTO_AJUSTE_INTERNO_PACHAS",
      "prioridad": "MEDIA",
      "descripcion": "Desbalance de apareo en pachas de tracción.",
      "matriz_reasignacion": [
        {"posicion_destino": 3, "serial_llanta": "LL-701", "prof_mm": 9.5, "origen": "P5"},
        {"posicion_destino": 4, "serial_llanta": "LL-702", "prof_mm": 9.2, "origen": "P6"},
        {"posicion_destino": 5, "serial_llanta": "LL-703", "prof_mm": 8.4, "origen": "P3"},
        {"posicion_destino": 6, "serial_llanta": "LL-704", "prof_mm": 8.1, "origen": "P4"}
      ],
      "gap_maximo_resultante_mm": 0.3
    },
    {
      "tipo": "CALIBRACION_PSI",
      "prioridad": "ALTA",
      "descripcion": "Subpresión en Posición 8",
      "instruccion": "Calibrar P8 de 88 PSI a 100 PSI en frío."
    }
  ]
}
```
