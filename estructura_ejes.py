"""Estructura de ejes de un vehículo a partir del esquema de su tipología.

Es la única fuente para saber, de cada posición: su eje, el tipo de eje (DIRECCIONAL, TRACCIÓN,
LIBRE o REPUESTO), el lado y si es interior o exterior de un dual. Diagnóstico, KPIs, trazabilidad,
PDF y bodegas deben preguntar aquí en lugar de suponer por el número de posición
("la 1 y la 2 son direccionales", "3-4 es un dual"), que falla en tráileres, 8x4 o biarticulados.

El esquema es la lista JSON guardada en catalogo_tipologias.esquema_json:
    [{"eje": 1, "tipo": "direccional", "posiciones": [{"pos": 1, "lado": "izq", "rol": "direccional"}, ...]}, ...]
"""
import functools
import re
import unicodedata

DIRECCIONAL, TRACCION, LIBRE, REPUESTO = 'DIRECCIONAL', 'TRACCIÓN', 'LIBRE', 'REPUESTO'
TIPOS_EJE = (DIRECCIONAL, TRACCION, LIBRE, REPUESTO)


def _sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto or '')) if unicodedata.category(c) != 'Mn')


@functools.lru_cache(maxsize=4096)
def _clave_tipologia(nombre):
    return re.sub(r'[^a-z0-9]', '', _sin_tildes(nombre).lower())


def clave_tipologia(nombre):
    """'Camión Sencillo (4x2)', 'CAMION SENCILLO 4X2' -> 'camionsencillo4x2' (para emparejar con el catálogo)."""
    # Se llama miles de veces por consulta con pocas tipologías distintas: se recuerda el resultado
    try:
        return _clave_tipologia(nombre)
    except TypeError:  # valor no hashable
        return re.sub(r'[^a-z0-9]', '', _sin_tildes(nombre).lower())


def normalizar_tipo_eje(tipo):
    t = _sin_tildes(tipo).lower()
    if 'dir' in t:
        return DIRECCIONAL
    if 'trac' in t:
        return TRACCION
    if 'rep' in t:
        return REPUESTO
    return LIBRE  # libre, remolque, arrastre, portante


class EstructuraVehiculo:
    """Ejes y posiciones de un vehículo. `inferida=True` si no vino de un esquema del catálogo."""

    def __init__(self, esquema, nombre='', inferida=False):
        self.nombre = nombre
        self.inferida = inferida
        self.ejes = []           # [{'num', 'tipo', 'posiciones': [pos...]}]
        self._eje_de = {}        # pos -> índice en self.ejes
        self._lado = {}          # pos -> 'izq' | 'der' | 'centro'
        self._rol = {}           # pos -> 'ext' | 'int' | 'sencillo' | 'direccional' | 'repuesto'
        for i, eje in enumerate(sorted(esquema or [], key=lambda e: int(e.get('eje', 0) or 0))):
            tipo = normalizar_tipo_eje(eje.get('tipo'))
            posiciones = []
            for p in eje.get('posiciones', []):
                try:
                    pos = int(p.get('pos'))
                except (TypeError, ValueError, AttributeError):
                    continue
                posiciones.append(pos)
                self._eje_de[pos] = len(self.ejes)
                self._lado[pos] = _sin_tildes(p.get('lado', '')).lower() or 'centro'
                rol = _sin_tildes(p.get('rol', '')).lower()
                if tipo == REPUESTO or rol.startswith('rep'):
                    rol = 'repuesto'
                elif rol.startswith('ext'):
                    rol = 'ext'
                elif rol.startswith('int'):
                    rol = 'int'
                elif tipo == DIRECCIONAL:
                    rol = 'direccional'
                else:
                    rol = 'sencillo'
                self._rol[pos] = rol
            self.ejes.append({'num': int(eje.get('eje', i + 1) or i + 1), 'tipo': tipo, 'posiciones': posiciones})

    # ------------------------------------------------------------------ consultas por posición
    def tiene(self, pos):
        return int(pos) in self._eje_de

    def tipo_eje(self, pos):
        i = self._eje_de.get(int(pos))
        return self.ejes[i]['tipo'] if i is not None else None

    def num_eje(self, pos):
        i = self._eje_de.get(int(pos))
        return self.ejes[i]['num'] if i is not None else None

    def lado(self, pos):
        return self._lado.get(int(pos))

    def rol(self, pos):
        return self._rol.get(int(pos))

    def es_repuesto(self, pos):
        return self.tipo_eje(pos) == REPUESTO

    # ------------------------------------------------------------------ consultas por eje
    def posiciones(self, *tipos, incluir_repuesto=False):
        """Posiciones de los ejes de los tipos pedidos (todos si no se pasa ninguno)."""
        res = []
        for e in self.ejes:
            if e['tipo'] == REPUESTO and not incluir_repuesto and REPUESTO not in tipos:
                continue
            if not tipos or e['tipo'] in tipos:
                res.extend(e['posiciones'])
        return res

    def ejes_de(self, tipo):
        return [e for e in self.ejes if e['tipo'] == tipo]

    def _por_lado(self, eje):
        lados = {}
        for pos in eje['posiciones']:
            lados.setdefault(self._lado.get(pos), []).append(pos)
        return lados

    def pares_direccionales(self):
        """[(izq, der)] de cada eje direccional con una llanta por lado."""
        pares = []
        for e in self.ejes_de(DIRECCIONAL):
            lados = self._por_lado(e)
            if len(lados.get('izq', [])) == 1 and len(lados.get('der', [])) == 1:
                pares.append((lados['izq'][0], lados['der'][0]))
        return pares

    def duales(self):
        """[(interior, exterior)] de cada conjunto dual (dos llantas del mismo lado de un eje)."""
        res = []
        for e in self.ejes:
            if e['tipo'] == REPUESTO:
                continue
            for lado, posiciones in sorted(self._por_lado(e).items(), key=lambda x: str(x[0])):
                if len(posiciones) != 2:
                    continue
                interior = next((p for p in posiciones if self._rol[p] == 'int'), None)
                exterior = next((p for p in posiciones if self._rol[p] == 'ext'), None)
                if interior is None or exterior is None:
                    interior, exterior = sorted(posiciones)[1], sorted(posiciones)[0]
                res.append((interior, exterior))
        return res

    def cruce_equis(self, eje_a, eje_b):
        """
        Rotación en equis larga entre dos ejes con duales: cada llanta pasa al otro eje y al
        lado contrario conservando su rol (ext izq <-> int der, int izq <-> ext der...).
        Retorna [(pos_a, pos_b)] o [] si los ejes no tienen la forma de dos duales.
        """
        def clave(eje):
            return {(self._lado[p], self._rol[p]): p for p in eje['posiciones']}
        a, b = clave(eje_a), clave(eje_b)
        opuesto = {'izq': 'der', 'der': 'izq'}
        rol_contrario = {'ext': 'int', 'int': 'ext'}
        pares = []
        for (lado, rol), pos in sorted(a.items()):
            destino = b.get((opuesto.get(lado), rol_contrario.get(rol)))
            if destino is None:
                return []
            pares.append((pos, destino))
        return pares if len(pares) == len(eje_a['posiciones']) == 4 else []

    def posiciones_alineacion(self):
        """Donde el desgaste entre hombros indica alineación: ejes direccionales y libres (remolque)."""
        return self.posiciones(DIRECCIONAL, LIBRE)


def estructura_inferida(tipologia, posiciones_presentes):
    """
    Estructura aproximada para tipologías que no están en el catálogo. Se marca `inferida=True`
    para poder informar que esos vehículos necesitan su tipología bien creada.
    """
    t = _sin_tildes(tipologia).lower()
    posiciones = sorted({int(p) for p in posiciones_presentes if str(p).strip() not in ('', 'None')})
    max_pos = max(posiciones) if posiciones else 0
    es_remolque = any(k in t for k in ('trailer', 'remolque', 'patineta', 'semirremolque'))
    cuatro_manos = 'cuatro manos' in t or '8x4' in t
    esquema, num, pos_actual = [], 1, 1

    def eje(tipo, n_llantas):
        nonlocal num, pos_actual
        roles = (['direccional', 'direccional'] if n_llantas == 2 and tipo == 'direccional'
                 else ['sencillo', 'sencillo'] if n_llantas == 2 else ['ext', 'int', 'int', 'ext'])
        lados = ['izq', 'der'] if n_llantas == 2 else ['izq', 'izq', 'der', 'der']
        esquema.append({'eje': num, 'tipo': tipo, 'posiciones': [
            {'pos': pos_actual + k, 'lado': lados[k], 'rol': roles[k]} for k in range(n_llantas)]})
        num += 1
        pos_actual += n_llantas

    if es_remolque:
        while pos_actual + 3 <= max(max_pos, 4):
            eje('libre', 4)
    else:
        eje('direccional', 2)
        if cuatro_manos:
            eje('direccional', 2)
        while pos_actual + 3 <= max(max_pos, pos_actual + 3):
            eje('traccion', 4)
            if pos_actual > max_pos:
                break
    return EstructuraVehiculo(esquema, nombre=tipologia, inferida=True)
