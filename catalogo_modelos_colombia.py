"""Modelos de llanta de uso comercial común en Colombia (camión, tractomula, volqueta, bus y buseta).

Se cargan una sola vez (migración 'catalogo_modelos_colombia_v1') sin tocar lo que el cliente ya tenga.
La profundidad inicial es una referencia típica del tipo de banda (tracción, direccional, remolque);
debe validarse contra la ficha técnica del fabricante y ajustarse en Catálogos → Catálogo de Modelos.
"""

D295, D315, D11, D385 = '295/80R22.5', '315/80R22.5', '11R22.5', '385/65R22.5'
B235, B215, B225, B245 = '235/75R17.5', '215/75R17.5', '225/70R19.5', '245/70R19.5'
TRAC, DIR, TODA, REM = 'Tracción', 'Direccional', 'Toda posición', 'Remolque / Arrastre'

# (marca, diseño, descripción, [(dimensión, profundidad inicial mm), ...])
_NUEVAS = [
    ('MICHELIN', 'X Multi D', TRAC, [(D315, 21.5), (D11, 20.0)]),
    ('MICHELIN', 'X Multi Z', TODA, [(D315, 16.5), (D11, 16.0)]),
    ('MICHELIN', 'X Multi T', REM, [(D385, 14.0)]),
    ('MICHELIN', 'XDE2+', TRAC, [(D295, 21.0), (D11, 20.0)]),
    ('MICHELIN', 'XZA2 Energy', DIR, [(D295, 16.0), (D11, 15.5)]),
    ('MICHELIN', 'XZE2+', TODA, [(D295, 16.0)]),
    ('BRIDGESTONE', 'M726 EL', TRAC, [(D315, 24.5)]),
    ('BRIDGESTONE', 'R268 Ecopia', DIR, [(D315, 16.0)]),
    ('BRIDGESTONE', 'M748', TRAC, [(D295, 21.0), (D11, 20.0)]),
    ('BRIDGESTONE', 'R297', DIR, [(D295, 16.0), (D11, 15.5)]),
    ('BRIDGESTONE', 'R170', TODA, [(D11, 15.0)]),
    ('GOODYEAR', 'KMax D', TRAC, [(D315, 22.0), (D11, 21.0)]),
    ('GOODYEAR', 'KMax S', DIR, [(D315, 16.0), (D11, 15.5)]),
    ('GOODYEAR', 'KMax T', REM, [(D385, 14.0)]),
    ('GOODYEAR', 'Endurance RSD', TRAC, [(D11, 21.0), (D295, 21.0)]),
    ('GOODYEAR', 'Endurance RSA', DIR, [(D11, 15.5), (D295, 16.0)]),
    ('CONTINENTAL', 'Hybrid HD3', TRAC, [(D295, 21.0), (D315, 21.0)]),
    ('CONTINENTAL', 'Hybrid HS3', DIR, [(D295, 16.0), (D315, 16.0)]),
    ('CONTINENTAL', 'Hybrid HT3', REM, [(D385, 14.0)]),
    ('PIRELLI', 'TG01', TRAC, [(D315, 22.5), (D11, 21.0)]),
    ('PIRELLI', 'FG01', DIR, [(D315, 16.5), (D11, 15.5)]),
    ('HANKOOK', 'DH35', TRAC, [(D315, 20.5), (D11, 19.5)]),
    ('HANKOOK', 'AH35', DIR, [(D315, 15.5), (D11, 15.0)]),
    ('HANKOOK', 'DL10+', TRAC, [(D295, 20.5), (D315, 20.5)]),
    ('HANKOOK', 'AL10+', DIR, [(D295, 15.5), (D315, 15.5)]),
    ('HANKOOK', 'TL10+', REM, [(D385, 13.5)]),
    ('DOUBLE COIN', 'RLB450', TRAC, [(D295, 20.0), (D315, 20.0)]),
    ('DOUBLE COIN', 'RLB400', TRAC, [(D295, 20.0), (D11, 19.0)]),
    ('DOUBLE COIN', 'RR900', DIR, [(D295, 15.0), (D11, 15.0)]),
    ('DOUBLE COIN', 'RT600', REM, [(D385, 13.5)]),
    ('LINGLONG', 'LLD33', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('LINGLONG', 'LLF02', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('TRIANGLE', 'TRD06', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('TRIANGLE', 'TRS02', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('TRIANGLE', 'TRT02', REM, [(D385, 13.0)]),
    ('SAILUN', 'S747', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('SAILUN', 'S637', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('SAILUN', 'S696', REM, [(D385, 13.0)]),
    ('WESTLAKE', 'CM985', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('WESTLAKE', 'CR960A', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('AEOLUS', 'ADR35', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('AEOLUS', 'ASR35', DIR, [(D295, 15.0), (D11, 14.5)]),
    # Camión liviano, buseta y bus (rines 17.5 y 19.5)
    ('MICHELIN', 'XZE', TODA, [(B235, 12.0), (B225, 12.5)]),
    ('BRIDGESTONE', 'R173', DIR, [(B235, 12.0), (B215, 11.5)]),
    ('HANKOOK', 'AH11', DIR, [(B235, 12.0), (B215, 11.5)]),
    ('HANKOOK', 'DH05', TRAC, [(B235, 14.0), (B215, 13.5)]),
    ('DOUBLE COIN', 'RR300', DIR, [(B235, 12.0), (B215, 11.5)]),
    ('DOUBLE COIN', 'RLB200', TRAC, [(B235, 14.0), (B215, 13.5)]),
    ('GOODYEAR', 'G149 RSA', DIR, [(B245, 12.5), (B225, 12.0)]),
]

# Bandas de reencauche que ya existen en el catálogo, ahora en las otras medidas comunes
_REENCAUCHE = [
    ('BANDAG', 'BDM', 'Banda tracción alta adherencia', [(D315, 21.0), (D11, 20.0)]),
    ('BANDAG', 'B710', 'Banda tracción carretera', [(D315, 20.0), (D11, 19.0)]),
    ('BANDAG', 'ECL Drive', 'Tracción severa', [(D315, 22.0), (D11, 21.0)]),
    ('BANDAG', 'B197 Trailer', 'Banda trailer / arrastre', [(D385, 14.5), (D11, 14.0)]),
    ('MARANGONI', 'Ringtread RD-G', 'Anillo tracción', [(D315, 21.5), (D11, 20.5)]),
    ('MARANGONI', 'RTL Energeia', 'Anillo remolque / trailer', [(D385, 14.0)]),
    ('VIPAL', 'VT100', 'Tracción urbana y regional', [(D315, 19.5), (D11, 19.0)]),
    ('VIPAL', 'VL110', 'Arrastre liviano y pesado', [(D385, 14.0), (D11, 13.5)]),
]


def modelos_colombia():
    """Filas (tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion) listas para insertar."""
    filas = []
    for tipo, lista in (('Nueva', _NUEVAS), ('Reencauche', _REENCAUCHE)):
        for marca, diseno, desc, medidas in lista:
            for dimension, prof in medidas:
                filas.append((tipo, marca.strip().upper(), diseno.strip().upper(), dimension.strip().upper(), prof, desc))
    return filas
