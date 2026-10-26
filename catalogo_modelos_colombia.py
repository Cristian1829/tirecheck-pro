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
    ('Michelin', 'X Multi D', TRAC, [(D315, 21.5), (D11, 20.0)]),
    ('Michelin', 'X Multi Z', TODA, [(D315, 16.5), (D11, 16.0)]),
    ('Michelin', 'X Multi T', REM, [(D385, 14.0)]),
    ('Michelin', 'XDE2+', TRAC, [(D295, 21.0), (D11, 20.0)]),
    ('Michelin', 'XZA2 Energy', DIR, [(D295, 16.0), (D11, 15.5)]),
    ('Michelin', 'XZE2+', TODA, [(D295, 16.0)]),
    ('Bridgestone', 'M726 EL', TRAC, [(D315, 24.5)]),
    ('Bridgestone', 'R268 Ecopia', DIR, [(D315, 16.0)]),
    ('Bridgestone', 'M748', TRAC, [(D295, 21.0), (D11, 20.0)]),
    ('Bridgestone', 'R297', DIR, [(D295, 16.0), (D11, 15.5)]),
    ('Bridgestone', 'R170', TODA, [(D11, 15.0)]),
    ('Goodyear', 'KMax D', TRAC, [(D315, 22.0), (D11, 21.0)]),
    ('Goodyear', 'KMax S', DIR, [(D315, 16.0), (D11, 15.5)]),
    ('Goodyear', 'KMax T', REM, [(D385, 14.0)]),
    ('Goodyear', 'Endurance RSD', TRAC, [(D11, 21.0), (D295, 21.0)]),
    ('Goodyear', 'Endurance RSA', DIR, [(D11, 15.5), (D295, 16.0)]),
    ('Continental', 'Hybrid HD3', TRAC, [(D295, 21.0), (D315, 21.0)]),
    ('Continental', 'Hybrid HS3', DIR, [(D295, 16.0), (D315, 16.0)]),
    ('Continental', 'Hybrid HT3', REM, [(D385, 14.0)]),
    ('Pirelli', 'TG01', TRAC, [(D315, 22.5), (D11, 21.0)]),
    ('Pirelli', 'FG01', DIR, [(D315, 16.5), (D11, 15.5)]),
    ('Hankook', 'DH35', TRAC, [(D315, 20.5), (D11, 19.5)]),
    ('Hankook', 'AH35', DIR, [(D315, 15.5), (D11, 15.0)]),
    ('Hankook', 'DL10+', TRAC, [(D295, 20.5), (D315, 20.5)]),
    ('Hankook', 'AL10+', DIR, [(D295, 15.5), (D315, 15.5)]),
    ('Hankook', 'TL10+', REM, [(D385, 13.5)]),
    ('Double Coin', 'RLB450', TRAC, [(D295, 20.0), (D315, 20.0)]),
    ('Double Coin', 'RLB400', TRAC, [(D295, 20.0), (D11, 19.0)]),
    ('Double Coin', 'RR900', DIR, [(D295, 15.0), (D11, 15.0)]),
    ('Double Coin', 'RT600', REM, [(D385, 13.5)]),
    ('Linglong', 'LLD33', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('Linglong', 'LLF02', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('Triangle', 'TRD06', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('Triangle', 'TRS02', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('Triangle', 'TRT02', REM, [(D385, 13.0)]),
    ('Sailun', 'S747', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('Sailun', 'S637', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('Sailun', 'S696', REM, [(D385, 13.0)]),
    ('Westlake', 'CM985', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('Westlake', 'CR960A', DIR, [(D295, 15.0), (D11, 14.5)]),
    ('Aeolus', 'ADR35', TRAC, [(D295, 19.5), (D11, 19.0)]),
    ('Aeolus', 'ASR35', DIR, [(D295, 15.0), (D11, 14.5)]),
    # Camión liviano, buseta y bus (rines 17.5 y 19.5)
    ('Michelin', 'XZE', TODA, [(B235, 12.0), (B225, 12.5)]),
    ('Bridgestone', 'R173', DIR, [(B235, 12.0), (B215, 11.5)]),
    ('Hankook', 'AH11', DIR, [(B235, 12.0), (B215, 11.5)]),
    ('Hankook', 'DH05', TRAC, [(B235, 14.0), (B215, 13.5)]),
    ('Double Coin', 'RR300', DIR, [(B235, 12.0), (B215, 11.5)]),
    ('Double Coin', 'RLB200', TRAC, [(B235, 14.0), (B215, 13.5)]),
    ('Goodyear', 'G149 RSA', DIR, [(B245, 12.5), (B225, 12.0)]),
]

# Bandas de reencauche que ya existen en el catálogo, ahora en las otras medidas comunes
_REENCAUCHE = [
    ('Bandag', 'BDM', 'Banda tracción alta adherencia', [(D315, 21.0), (D11, 20.0)]),
    ('Bandag', 'B710', 'Banda tracción carretera', [(D315, 20.0), (D11, 19.0)]),
    ('Bandag', 'ECL Drive', 'Tracción severa', [(D315, 22.0), (D11, 21.0)]),
    ('Bandag', 'B197 Trailer', 'Banda trailer / arrastre', [(D385, 14.5), (D11, 14.0)]),
    ('Marangoni', 'Ringtread RD-G', 'Anillo tracción', [(D315, 21.5), (D11, 20.5)]),
    ('Marangoni', 'RTL Energeia', 'Anillo remolque / trailer', [(D385, 14.0)]),
    ('Vipal', 'VT100', 'Tracción urbana y regional', [(D315, 19.5), (D11, 19.0)]),
    ('Vipal', 'VL110', 'Arrastre liviano y pesado', [(D385, 14.0), (D11, 13.5)]),
]


def modelos_colombia():
    """Filas (tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion) listas para insertar."""
    filas = []
    for tipo, lista in (('Nueva', _NUEVAS), ('Reencauche', _REENCAUCHE)):
        for marca, diseno, desc, medidas in lista:
            for dimension, prof in medidas:
                filas.append((tipo, marca, diseno, dimension, prof, desc))
    return filas
