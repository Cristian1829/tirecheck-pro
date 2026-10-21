import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

df = pd.read_excel('Plantilla_Cargue_Masivo_Inspecciones CIUDAD LIMPIA_AJUSTADA.xlsx')

wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Proyeccion Llantas'

headers = [
    'Placa', 'Pos', 'No. Interno', 'P.Ext (mm)', 'P.Cent (mm)', 'P.Int (mm)',
    'P.Minima (mm)', 'P.Inicial (mm)', 'Limite (mm)', 'mm Utiles', 'Desgaste Δmm',
    'Km Actual', 'Km Montaje', 'Km Rodados', '¿Asentamiento?', 'Rendimiento (Km/mm)', 'Proyeccion Total (km)'
]

ws.append(headers)

# Formatos y estilos
header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid') # Azul oscuro
header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
border_thin = Side(border_style='thin', color='CBD5E1')
cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

for col_num, h in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col_num)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

# Parámetro dinámico del Catálogo de Límites (Columna S y T)
ws.cell(row=1, column=19, value="CATALOGO DE LIMITES")
ws.merge_cells("S1:T1")
ws.cell(row=1, column=19).fill = PatternFill(start_color='B45309', end_color='B45309', fill_type='solid') # Ámbar oscuro
ws.cell(row=1, column=19).font = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
ws.cell(row=1, column=19).alignment = Alignment(horizontal='center')

ws.cell(row=2, column=19, value="Limite Cambio Ciudad Limpia (mm):")
ws.cell(row=2, column=19).font = Font(name='Calibri', size=10, bold=True, color='1E293B')

param_celda = ws.cell(row=2, column=20, value=4.0)
param_celda.font = Font(name='Calibri', size=12, bold=True, color='B45309')
param_celda.fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid') # Fondo ámbar suave
param_celda.alignment = Alignment(horizontal='center')
param_celda.number_format = '0.0'
param_celda.border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

ws.cell(row=3, column=19, value="* Si modificas esta celda (T2), todas las formulas recalculan en vivo.")
ws.merge_cells("S3:T3")
ws.cell(row=3, column=19).font = Font(name='Calibri', size=8, italic=True, color='64748B')

row_idx = 2
for _, r in df.iterrows():
    placa = r['placa']
    pos = int(r['posicion'])
    num_int = r['numero_interno']
    pe = float(r['prof_ext'])
    pc = float(r['prof_cent'])
    pi = float(r['prof_int'])
    pini = float(r['prof_inicial'])
    km_act = float(r['kilometraje'])
    km_mont = float(r['km_montaje'])
    
    # Formulas en openpyxl vinculadas dinámicamente a la celda del catálogo ($T$2)
    f_pmin = f"=MIN(D{row_idx}:F{row_idx})"
    f_lim = "=$T$2"  # Límite dinámico del catálogo de 4.0 mm
    f_mm_ut = f"=H{row_idx}-I{row_idx}"
    f_delta = f"=H{row_idx}-G{row_idx}"
    f_km_rod = f"=L{row_idx}-M{row_idx}"
    f_asent = f'=IF(OR(K{row_idx}<0.5, N{row_idx}<500), "SI", "NO")'
    f_kmmm = f'=IF(O{row_idx}="SI", 0, N{row_idx}/K{row_idx})'
    f_proy = f'=IF(O{row_idx}="SI", 0, P{row_idx}*J{row_idx})'
    
    ws.append([
        placa, pos, num_int, pe, pc, pi,
        f_pmin, pini, f_lim, f_mm_ut, f_delta,
        km_act, km_mont, f_km_rod, f_asent, f_kmmm, f_proy
    ])
    
    for col_idx in range(1, 18):
        c = ws.cell(row=row_idx, column=col_idx)
        c.border = cell_border
        c.font = Font(name='Calibri', size=10)
        if col_idx in [1, 2, 3, 15]:
            c.alignment = Alignment(horizontal='center')
        elif col_idx in [4, 5, 6, 7, 8, 9, 10, 11]:
            c.number_format = '0.0'
            c.alignment = Alignment(horizontal='right')
        elif col_idx in [12, 13, 14, 16, 17]:
            c.number_format = '#,##0'
            c.alignment = Alignment(horizontal='right')
            
    row_idx += 1

total_row = row_idx
ws.cell(row=total_row, column=1, value='PROMEDIO GENERAL FLOTA (TARJETA DASHBOARD)')
ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=13)
tot_label = ws.cell(row=total_row, column=1)
tot_label.font = Font(name='Calibri', size=11, bold=True, color='1E3A8A')
tot_label.alignment = Alignment(horizontal='right', vertical='center')

# Promedio km rodados
c_rod_prom = ws.cell(row=total_row, column=14, value=f"=AVERAGE(N2:N{total_row-1})")
c_rod_prom.number_format = '#,##0'
c_rod_prom.font = Font(name='Calibri', size=11, bold=True, color='1E3A8A')
c_rod_prom.alignment = Alignment(horizontal='right')

# Promedio Proyección (Tarjeta Principal)
c_proy_prom = ws.cell(row=total_row, column=17, value=f'=AVERAGEIF(O2:O{total_row-1}, "NO", Q2:Q{total_row-1})')
c_proy_prom.number_format = '#,##0'
c_proy_prom.font = Font(name='Calibri', size=12, bold=True, color='047857')
c_proy_prom.fill = PatternFill(start_color='D1FAE5', end_color='D1FAE5', fill_type='solid')
c_proy_prom.alignment = Alignment(horizontal='right')

border_double = Border(top=Side(style='thin', color='1E3A8A'), bottom=Side(style='double', color='1E3A8A'))
for col_idx in range(1, 18):
    c = ws.cell(row=total_row, column=col_idx)
    c.border = border_double

for col in ws.columns:
    max_len = max(len(str(cell.value or '')) for cell in col)
    col_letter = get_column_letter(col[0].column)
    ws.column_dimensions[col_letter].width = max(max_len + 4, 13)

ws.column_dimensions['S'].width = 30
ws.column_dimensions['T'].width = 12

output_file = 'Calculo_Proyecciones_CIUDAD_LIMPIA_4MM.xlsx'
try:
    wb.save('Calculo_Proyecciones_CIUDAD_LIMPIA.xlsx')
    output_file = 'Calculo_Proyecciones_CIUDAD_LIMPIA.xlsx'
except PermissionError:
    wb.save(output_file)

print(f"Archivo Excel generado con formulas y catalogo dinamico: {output_file}")
