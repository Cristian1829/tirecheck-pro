import os, sys, threading, socket, qrcode, uvicorn
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
from PIL import Image, ImageTk

import database
from server import app as fastapi_app

def obtener_ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class AppInspeccionLlantas(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('TireCheck Pro - Sistema Integral de Inspeccion de Llantas')
        self.geometry('1280x760')
        self.minsize(1050, 650)
        self.df_inspecciones = pd.DataFrame()
        self.df_analisis = pd.DataFrame()
        self.qr_photo = None
        self.iniciar_servidor_movil()
        self.configurar_estilos()
        self.crear_interfaz()
        self.cargar_datos_bd()

    def iniciar_servidor_movil(self):
        def run_srv():
            uvicorn.run(fastapi_app, host='0.0.0.0', port=8000, log_level='warning')
        t = threading.Thread(target=run_srv, daemon=True)
        t.start()

    def configurar_estilos(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.bg_color = '#f8fafc'
        self.header_bg = '#0f172a'
        self.configure(bg=self.bg_color)
        self.style.configure('.', background=self.bg_color, font=('Segoe UI', 9))
        self.style.configure('Header.TFrame', background=self.header_bg)
        self.style.configure('HeaderTitle.TLabel', background=self.header_bg, foreground='#ffffff', font=('Segoe UI', 14, 'bold'))
        self.style.configure('HeaderSubtitle.TLabel', background=self.header_bg, foreground='#94a3b8', font=('Segoe UI', 9))
        self.style.configure('Card.TFrame', background='#ffffff', relief='solid', borderwidth=1)
        self.style.configure('CardTitle.TLabel', background='#ffffff', foreground='#64748b', font=('Segoe UI', 8, 'bold'))
        self.style.configure('CardVal.TLabel', background='#ffffff', foreground='#0f172a', font=('Segoe UI', 16, 'bold'))
        self.style.configure('Primary.TButton', font=('Segoe UI', 9, 'bold'), background='#2563eb', foreground='#ffffff')
        self.style.map('Primary.TButton', background=[('active', '#1d4ed8')])
        self.style.configure('Success.TButton', font=('Segoe UI', 9, 'bold'), background='#16a34a', foreground='#ffffff')
        self.style.map('Success.TButton', background=[('active', '#15803d')])
        self.style.configure('Mobile.TButton', font=('Segoe UI', 9, 'bold'), background='#7c3aed', foreground='#ffffff')
        self.style.map('Mobile.TButton', background=[('active', '#6d28d9')])
        self.style.configure('Treeview', background='#ffffff', foreground='#1e293b', fieldbackground='#ffffff', rowheight=26, font=('Segoe UI', 9))
        self.style.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'), background='#e2e8f0', foreground='#0f172a')
        self.style.map('Treeview', background=[('selected', '#dbeafe')], foreground=[('selected', '#1e3a8a')])

    def crear_interfaz(self):
        header = ttk.Frame(self, style='Header.TFrame', padding=(18, 12))
        header.pack(fill='x', side='top')
        top_frame = ttk.Frame(header, style='Header.TFrame')
        top_frame.pack(fill='x')
        lbl_titulo = ttk.Label(top_frame, text='TireCheck Pro - Gestion y Diagnostico de Flotas', style='HeaderTitle.TLabel')
        lbl_titulo.pack(side='left', anchor='w')
        ip_local = obtener_ip_local()
        lbl_ip = ttk.Label(top_frame, text='Movil Conectado: http://' + ip_local + ':8000', background='#1e293b', foreground='#38bdf8', font=('Segoe UI', 9, 'bold'), padding=(8, 4))
        lbl_ip.pack(side='right')
        lbl_sub = ttk.Label(header, text='Cliente, subcliente y operacion | Tipologia dinamica | Inspeccion tactil desde celular', style='HeaderSubtitle.TLabel')
        lbl_sub.pack(anchor='w', pady=(2, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=15, pady=10)

        self.tab_bd = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_bd, text='Base de Inspecciones')
        self.crear_tab_inspecciones(self.tab_bd)

        self.tab_form = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_form, text='Nueva Inspeccion (PC)')
        self.crear_tab_formulario(self.tab_form)

        self.tab_movil = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab_movil, text='Conectar Celular (QR)')
        self.crear_tab_movil(self.tab_movil)

        self.tab_analisis = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_analisis, text='Planes de Accion & Diagnostico')
        self.crear_tab_analisis(self.tab_analisis)

        self.tab_kpis = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_kpis, text='📊 Trazabilidad & KPIs Llanta')
        self.crear_tab_kpis(self.tab_kpis)

        self.tab_catalogos = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_catalogos, text='⚙ Gestionar Catálogos')
        self.crear_tab_catalogos(self.tab_catalogos)

        self.status_bar = ttk.Label(self, text='Listo.', relief='sunken', anchor='w', padding=(10, 4))
        self.status_bar.pack(side='bottom', fill='x')

    def crear_tab_inspecciones(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 8))
        ttk.Button(toolbar, text='Agregar en PC', style='Primary.TButton', command=lambda: self.notebook.select(self.tab_form)).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Codigo QR Celular', style='Mobile.TButton', command=lambda: self.notebook.select(self.tab_movil)).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Recargar', command=self.cargar_datos_bd).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Importar Excel', command=self.importar_excel).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Descargar Plantilla', command=self.descargar_plantilla_excel).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Exportar Excel', style='Success.TButton', command=self.exportar_bd_excel).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Editar Fila', style='Primary.TButton', command=self.editar_fila_seleccionada).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text='Eliminar Fila', command=self.eliminar_fila_seleccionada).pack(side='left', padx=(0, 15))
        ttk.Label(toolbar, text='Buscar Placa/Cliente:').pack(side='left', padx=(8, 4))
        self.buscar_bd_var = tk.StringVar()
        self.buscar_bd_var.trace_add('write', lambda *args: self.filtrar_tabla_bd())
        ttk.Entry(toolbar, textvariable=self.buscar_bd_var, width=14).pack(side='left')

        cols = ('id', 'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'numero_interno', 'posicion', 'kilometraje', 'tipologia', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int', 'psi', 'novedades', 'precio', 'prof_inicial', 'km_montaje')
        headers = {'id': 'ID', 'fecha': 'Fecha', 'cliente': 'Cliente', 'subcliente': 'Subcliente', 'tipo_operacion': 'Operacion', 'placa': 'Placa', 'numero_interno': 'No. Interno', 'posicion': 'Pos', 'kilometraje': 'Km', 'tipologia': 'Tipologia', 'marca': 'Marca', 'diseno': 'Diseno', 'dimension': 'Dimension', 'vida': 'Vida', 'banda_reen': 'Banda', 'prof_ext': 'P.Ext', 'prof_cent': 'P.Cent', 'prof_int': 'P.Int', 'psi': 'PSI', 'novedades': 'Novedades', 'precio': 'Precio', 'prof_inicial': 'P.Ini', 'km_montaje': 'Km.Mont'}
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)
        self.tree_bd = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse')
        self.tree_bd.bind('<Double-1>', lambda e: self.editar_fila_seleccionada())
        for c in cols:
            w = 50 if c in ('id', 'posicion', 'prof_ext', 'prof_cent', 'prof_int', 'psi') else 80 if c in ('placa', 'fecha', 'vida') else 90 if c == 'numero_interno' else 100 if c in ('cliente', 'subcliente', 'tipo_operacion') else 115 if c in ('novedades', 'banda_reen') else 80
            self.tree_bd.heading(c, text=headers[c])
            self.tree_bd.column(c, width=w, anchor='center' if c not in ('novedades', 'marca', 'diseno', 'cliente', 'subcliente') else 'w')
        sb_y = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree_bd.yview)
        sb_x = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_bd.xview)
        self.tree_bd.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        self.tree_bd.pack(side='left', fill='both', expand=True)

    def crear_tab_formulario(self, parent):
        self._pos_btns_pc = {}
        self._ultima_placa_pc = ''
        self._posiciones_inspeccionadas_pc = set()

        paned = ttk.PanedWindow(parent, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # Panel Izquierdo: Formulario
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        # Canvas scrollable para formulario en pantallas pequeñas/medianas
        canvas_form = tk.Canvas(left_frame, bg=self.bg_color, highlightthickness=0)
        sb_form = ttk.Scrollbar(left_frame, orient='vertical', command=canvas_form.yview)
        scrollable_card = ttk.Frame(canvas_form, style='Card.TFrame', padding=14)

        scrollable_card.bind('<Configure>', lambda e: canvas_form.configure(scrollregion=canvas_form.bbox('all')))
        c_win = canvas_form.create_window((0, 0), window=scrollable_card, anchor='nw')
        canvas_form.bind('<Configure>', lambda e: canvas_form.itemconfig(c_win, width=e.width))
        canvas_form.configure(yscrollcommand=sb_form.set)

        sb_form.pack(side='right', fill='y')
        canvas_form.pack(side='left', fill='both', expand=True)

        card = scrollable_card
        ttk.Label(card, text='Formulario de Inspeccion de Llantas', font=('Segoe UI', 12, 'bold'), background='#ffffff').grid(row=0, column=0, columnspan=6, sticky='w', pady=(0, 10))
        self.form_vars = {
            'fecha': tk.StringVar(value=datetime.now().strftime('%Y-%m-%d')),
            'cliente': tk.StringVar(), 'subcliente': tk.StringVar(), 'tipo_operacion': tk.StringVar(value='Carga Seca'),
            'placa': tk.StringVar(), 'posicion': tk.StringVar(value='1'), 'kilometraje': tk.StringVar(),
            'tipologia': tk.StringVar(value='Cabezote (6x4)'), 'marca': tk.StringVar(), 'diseno': tk.StringVar(),
            'dimension': tk.StringVar(value='295/80R22.5'), 'vida': tk.StringVar(value='Original'), 'banda_reen': tk.StringVar(),
            'prof_ext': tk.StringVar(value='0'), 'prof_cent': tk.StringVar(value='0'), 'prof_int': tk.StringVar(value='0'),
            'psi': tk.StringVar(value='100'), 'novedades': tk.StringVar(), 'precio': tk.StringVar(value='0'),
            'prof_inicial': tk.StringVar(value='0'), 'km_montaje': tk.StringVar(value='0'),
            'numero_interno': tk.StringVar()
        }
        sec1 = ttk.LabelFrame(card, text='1. Datos del Cliente & Operación', padding=8)
        sec1.grid(row=1, column=0, columnspan=6, sticky='ew', pady=(0, 8))
        
        ttk.Label(sec1, text='Cliente:').grid(row=0, column=0, padx=5, pady=4, sticky='w')
        clis = database.obtener_valores_unicos_campo('cliente')
        self.cb_cli_pc = ttk.Combobox(sec1, textvariable=self.form_vars['cliente'], values=clis, width=18)
        self.cb_cli_pc.grid(row=0, column=1, padx=5, pady=4)
        self.cb_cli_pc.bind('<<ComboboxSelected>>', self.al_cambiar_cliente_pc)
        self.cb_cli_pc.bind('<FocusOut>', self.al_cambiar_cliente_pc)

        ttk.Label(sec1, text='Subcliente:').grid(row=0, column=2, padx=5, pady=4, sticky='w')
        self.cb_sub_pc = ttk.Combobox(sec1, textvariable=self.form_vars['subcliente'], width=16)
        self.cb_sub_pc.grid(row=0, column=3, padx=5, pady=4)

        ttk.Label(sec1, text='Operación:').grid(row=0, column=4, padx=5, pady=4, sticky='w')
        op_box = ttk.Frame(sec1)
        op_box.grid(row=0, column=5, padx=5, pady=4, sticky='w')
        ops_bd = database.obtener_todas_operaciones()
        self.cb_op_pc = ttk.Combobox(op_box, textvariable=self.form_vars['tipo_operacion'], values=ops_bd, width=14)
        self.cb_op_pc.pack(side='left', padx=(0, 4))
        ttk.Button(op_box, text='+', width=2, command=self.modal_agregar_operacion).pack(side='left')

        sec2 = ttk.LabelFrame(card, text='2. Vehículo & Tipología Dinámica', padding=8)
        sec2.grid(row=2, column=0, columnspan=6, sticky='ew', pady=(0, 8))
        
        ttk.Label(sec2, text='Placa:*', font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, padx=5, pady=4, sticky='w')
        self.ent_placa_pc = ttk.Entry(sec2, textvariable=self.form_vars['placa'], width=12)
        self.ent_placa_pc.grid(row=0, column=1, padx=5, pady=4)
        self.ent_placa_pc.bind('<FocusOut>', self.al_perder_foco_placa_pc)

        ttk.Label(sec2, text='Tipología:*', font=('Segoe UI', 9, 'bold')).grid(row=0, column=2, padx=5, pady=4, sticky='w')
        tip_box = ttk.Frame(sec2)
        tip_box.grid(row=0, column=3, padx=5, pady=4, sticky='w')
        tips_bd = [t['nombre'] if isinstance(t, dict) else str(t) for t in database.obtener_todas_tipologias()]
        self.cb_tip_pc = ttk.Combobox(tip_box, textvariable=self.form_vars['tipologia'], values=tips_bd, width=17)
        self.cb_tip_pc.pack(side='left', padx=(0, 4))
        self.cb_tip_pc.bind('<<ComboboxSelected>>', self.on_cambio_tipologia_pc)
        ttk.Button(tip_box, text='+', width=2, command=self.modal_agregar_tipologia).pack(side='left')

        ttk.Label(sec2, text='Posición:*', font=('Segoe UI', 9, 'bold')).grid(row=0, column=4, padx=5, pady=4, sticky='w')
        self.cb_pos_pc = ttk.Combobox(sec2, textvariable=self.form_vars['posicion'], state='readonly', width=6)
        self.cb_pos_pc.grid(row=0, column=5, padx=5, pady=4)
        self.cb_pos_pc.bind('<<ComboboxSelected>>', lambda e: self.seleccionar_posicion_pc(self.form_vars['posicion'].get()))

        ttk.Label(sec2, text='Kilometraje:').grid(row=1, column=0, padx=5, pady=4, sticky='w')
        ttk.Entry(sec2, textvariable=self.form_vars['kilometraje'], width=12).grid(row=1, column=1, padx=5, pady=4)
        ttk.Label(sec2, text='Fecha:').grid(row=1, column=2, padx=5, pady=4, sticky='w')
        ttk.Entry(sec2, textvariable=self.form_vars['fecha'], width=18).grid(row=1, column=3, padx=5, pady=4)

        # Botón para precargar datos de la llanta anterior
        btn_prev = ttk.Button(sec2, text='🔄 Copiar Anterior', command=lambda: self.copiar_datos_previa_pc(True))
        btn_prev.grid(row=1, column=4, padx=5, pady=4, sticky='w')

        ttk.Label(sec2, text='No. Interno:', font=('Segoe UI', 9, 'bold'), foreground='#1e3a8a').grid(row=1, column=5, padx=5, pady=4, sticky='w')
        ttk.Entry(sec2, textvariable=self.form_vars['numero_interno'], width=10).grid(row=1, column=5, padx=(80, 5), pady=4)

        sec3 = ttk.LabelFrame(card, text='3. Especificaciones de Llanta & 3 Profundidades', padding=8)
        sec3.grid(row=3, column=0, columnspan=6, sticky='ew', pady=(0, 8))
        
        # Fila de búsqueda rápida de modelos
        busc_frame = ttk.Frame(sec3)
        busc_frame.grid(row=0, column=0, columnspan=6, sticky='ew', pady=(0, 6))
        ttk.Label(busc_frame, text='⚡ Buscador de Llanta:', font=('Segoe UI', 9, 'bold'), foreground='#1d4ed8').pack(side='left', padx=(5, 4))
        self.var_busc_pc = tk.StringVar()
        self.cb_busc_pc = ttk.Combobox(busc_frame, textvariable=self.var_busc_pc, width=38)
        self.cb_busc_pc.pack(side='left', padx=(0, 8))
        self.cb_busc_pc.bind('<<ComboboxSelected>>', self.al_seleccionar_modelo_buscador_pc)
        self.actualizar_lista_buscador_pc()

        # Fila 1: Marca, Diseño, Dimensión (SIN solapamiento con Presión PSI)
        ttk.Label(sec3, text='Marca:').grid(row=1, column=0, padx=5, pady=4, sticky='w')
        marcas_bd = database.obtener_valores_unicos_campo('marca')
        self.cb_marca_pc = ttk.Combobox(sec3, textvariable=self.form_vars['marca'], values=marcas_bd, width=14)
        self.cb_marca_pc.grid(row=1, column=1, padx=5, pady=4)
        self.cb_marca_pc.bind('<FocusOut>', lambda e: self.auto_completar_prof_pc())

        ttk.Label(sec3, text='Diseño:').grid(row=1, column=2, padx=5, pady=4, sticky='w')
        disenos_bd = database.obtener_valores_unicos_campo('diseno')
        self.cb_diseno_pc = ttk.Combobox(sec3, textvariable=self.form_vars['diseno'], values=disenos_bd, width=16)
        self.cb_diseno_pc.grid(row=1, column=3, padx=5, pady=4)
        self.cb_diseno_pc.bind('<FocusOut>', lambda e: self.auto_completar_prof_pc())

        ttk.Label(sec3, text='Dimensión:').grid(row=1, column=4, padx=5, pady=4, sticky='w')
        dims_bd = database.obtener_valores_unicos_campo('dimension')
        self.cb_dim_pc = ttk.Combobox(sec3, textvariable=self.form_vars['dimension'], values=dims_bd, width=14)
        self.cb_dim_pc.grid(row=1, column=5, padx=5, pady=4)

        # Fila 2: Vida, Banda Reencauche, Presión PSI
        ttk.Label(sec3, text='Vida:').grid(row=2, column=0, padx=5, pady=4, sticky='w')
        cb_v = ttk.Combobox(sec3, textvariable=self.form_vars['vida'], values=['Original', 'Reencauche'], state='readonly', width=12)
        cb_v.grid(row=2, column=1, padx=5, pady=4)
        cb_v.bind('<<ComboboxSelected>>', self.actualizar_estado_banda_pc)

        ttk.Label(sec3, text='Banda Reencauche:').grid(row=2, column=2, padx=5, pady=4, sticky='w')
        bandas_bd = database.obtener_valores_unicos_campo('banda_reen')
        self.entry_banda_pc = ttk.Combobox(sec3, textvariable=self.form_vars['banda_reen'], values=bandas_bd, width=16, state='disabled')
        self.entry_banda_pc.grid(row=2, column=3, padx=5, pady=4)

        ttk.Label(sec3, text='Presion PSI:').grid(row=2, column=4, padx=5, pady=4, sticky='w')
        ttk.Entry(sec3, textvariable=self.form_vars['psi'], width=14).grid(row=2, column=5, padx=5, pady=4)

        # Fila 3: Mediciones de Profundidad (Exterior, Central, Interior y Prof. Inicial)
        p_frame = ttk.Frame(sec3)
        p_frame.grid(row=3, column=0, columnspan=6, sticky='w', pady=6)
        ttk.Label(p_frame, text='Prof. Exterior (mm):', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(5, 2))
        ttk.Entry(p_frame, textvariable=self.form_vars['prof_ext'], width=6).pack(side='left', padx=(0, 8))
        ttk.Label(p_frame, text='Prof. Central (mm):', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(5, 2))
        ttk.Entry(p_frame, textvariable=self.form_vars['prof_cent'], width=6).pack(side='left', padx=(0, 8))
        ttk.Label(p_frame, text='Prof. Interior (mm):', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(5, 2))
        ttk.Entry(p_frame, textvariable=self.form_vars['prof_int'], width=6).pack(side='left', padx=(0, 8))
        ttk.Label(p_frame, text='Prof. Inicial:').pack(side='left', padx=(5, 2))
        ttk.Entry(p_frame, textvariable=self.form_vars['prof_inicial'], width=6).pack(side='left', padx=(0, 8))

        sec4 = ttk.LabelFrame(card, text='4. Historico & Novedades', padding=8)
        sec4.grid(row=4, column=0, columnspan=6, sticky='ew', pady=(0, 8))
        ttk.Label(sec4, text='Precio:').grid(row=0, column=0, padx=5, pady=4, sticky='w')
        ttk.Entry(sec4, textvariable=self.form_vars['precio'], width=10).grid(row=0, column=1, padx=5, pady=4)
        ttk.Label(sec4, text='Km Montaje:').grid(row=0, column=2, padx=5, pady=4, sticky='w')
        ttk.Entry(sec4, textvariable=self.form_vars['km_montaje'], width=10).grid(row=0, column=3, padx=5, pady=4)
        ttk.Label(sec4, text='Novedades:').grid(row=0, column=4, padx=5, pady=4, sticky='w')
        ttk.Entry(sec4, textvariable=self.form_vars['novedades'], width=24).grid(row=0, column=5, padx=5, pady=4)

        btn_frame = ttk.Frame(card)
        btn_frame.grid(row=5, column=0, columnspan=6, pady=(10, 0), sticky='w')
        ttk.Button(btn_frame, text='Guardar & Siguiente Llanta', style='Success.TButton', command=self.guardar_formulario_pc).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text='Limpiar Mediciones', command=self.limpiar_formulario_pc).pack(side='left')

    def crear_panel_chasis_pc(self, parent):
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.pack(fill='both', expand=True)

        header_f = ttk.Frame(card, style='Card.TFrame')
        header_f.pack(fill='x', pady=(0, 8))
        ttk.Label(header_f, text='Mapeo Visual del Chasis', font=('Segoe UI', 11, 'bold'), background='#ffffff', foreground='#1e3a8a').pack(side='left')
        self.lbl_chasis_pos_pc = ttk.Label(header_f, text='Posición: 1', font=('Segoe UI', 9, 'bold'), background='#dbeafe', foreground='#1e40af', padding=(6, 2))
        self.lbl_chasis_pos_pc.pack(side='right')

        # Indicador de estado de inspección
        self.lbl_chasis_estado_pc = ttk.Label(card, text='Inspeccionadas: 0 / 0', font=('Segoe UI', 8, 'bold'), background='#ffffff', foreground='#059669')
        self.lbl_chasis_estado_pc.pack(anchor='w', pady=(0, 6))

        # Indicador visual del frente
        frente_f = ttk.Frame(card, style='Card.TFrame')
        frente_f.pack(fill='x', pady=(2, 6))
        ttk.Label(frente_f, text='▲ FRENTE / CABINA ▲', font=('Segoe UI', 8, 'bold'), background='#e2e8f0', foreground='#475569', anchor='center').pack(fill='x')

        # Contenedor con scroll para los ejes del chasis
        canvas_chasis = tk.Canvas(card, bg='#ffffff', highlightthickness=0)
        sb_ch = ttk.Scrollbar(card, orient='vertical', command=canvas_chasis.yview)
        self.frame_ejes_pc = ttk.Frame(canvas_chasis, style='Card.TFrame')

        self.frame_ejes_pc.bind('<Configure>', lambda e: canvas_chasis.configure(scrollregion=canvas_chasis.bbox('all')))
        cw_ch = canvas_chasis.create_window((0, 0), window=self.frame_ejes_pc, anchor='n')
        canvas_chasis.bind('<Configure>', lambda e: canvas_chasis.itemconfig(cw_ch, width=e.width))
        canvas_chasis.configure(yscrollcommand=sb_ch.set)

        sb_ch.pack(side='right', fill='y')
        canvas_chasis.pack(side='top', fill='both', expand=True)

        # Leyenda / Convenciones
        leyenda = ttk.Frame(card, style='Card.TFrame', padding=(0, 6))
        leyenda.pack(side='bottom', fill='x')
        ttk.Label(leyenda, text='Convenciones:', font=('Segoe UI', 8, 'bold'), background='#ffffff', foreground='#64748b').pack(anchor='w')
        f_conv = ttk.Frame(leyenda, style='Card.TFrame')
        f_conv.pack(fill='x', pady=2)
        ttk.Label(f_conv, text='■ Inspeccionada (✓)', font=('Segoe UI', 8, 'bold'), foreground='#059669', background='#ffffff').pack(side='left', padx=(0, 8))
        ttk.Label(f_conv, text='■ Seleccionada', font=('Segoe UI', 8, 'bold'), foreground='#2563eb', background='#ffffff').pack(side='left', padx=(0, 8))
        ttk.Label(f_conv, text='■ Pendiente', font=('Segoe UI', 8), foreground='#64748b', background='#ffffff').pack(side='left')

    def al_perder_foco_placa_pc(self, event=None):
        nueva_placa = self.form_vars['placa'].get().strip().upper()
        if nueva_placa != self.form_vars['placa'].get():
            self.form_vars['placa'].set(nueva_placa)
        
        ultima = getattr(self, '_ultima_placa_pc', '')
        if ultima and nueva_placa and nueva_placa != ultima:
            tipo = self.form_vars['tipologia'].get()
            posiciones_totales = database.obtener_posiciones_por_tipologia(tipo)
            pos_hechas = getattr(self, '_posiciones_inspeccionadas_pc', set())
            faltantes = [p for p in posiciones_totales if p not in pos_hechas]
            
            if faltantes:
                str_faltantes = ', '.join(f"Pos {p}" for p in faltantes)
                resp = messagebox.askyesno(
                    'Atención: Posiciones Pendientes',
                    f'¿Estás seguro de cambiar de placa?\n\n'
                    f'De la placa anterior [{ultima}] aún te faltan las siguientes posiciones por inspeccionar:\n'
                    f'▶ {str_faltantes}\n\n'
                    f'¿Deseas continuar y cambiar a la placa [{nueva_placa}]?'
                )
                if not resp:
                    self.form_vars['placa'].set(ultima)
                    return

        if nueva_placa:
            self._ultima_placa_pc = nueva_placa
            self.actualizar_estado_posiciones_inspeccionadas_pc()
            self.verificar_llanta_previa_pc()

    def actualizar_estado_posiciones_inspeccionadas_pc(self):
        placa = self.form_vars['placa'].get().strip()
        fecha = self.form_vars['fecha'].get().strip()
        if placa:
            insp = database.obtener_posiciones_inspeccionadas_actuales(placa, fecha)
            self._posiciones_inspeccionadas_pc = set(insp)
        else:
            self._posiciones_inspeccionadas_pc = set()
        
        self.renderizar_chasis_pc()

    def seleccionar_posicion_pc(self, pos):
        self.form_vars['posicion'].set(str(pos))
        if hasattr(self, 'lbl_chasis_pos_pc'):
            self.lbl_chasis_pos_pc.config(text=f'Posición: {pos}')
        self.verificar_llanta_previa_pc()
        self.renderizar_chasis_pc()

    def renderizar_chasis_pc(self):
        if not hasattr(self, 'frame_ejes_pc'):
            return
        
        for w in self.frame_ejes_pc.winfo_children():
            w.destroy()
        
        tipo = self.form_vars['tipologia'].get()
        info_esquema = database.obtener_esquema_ejes_por_tipologia(tipo)
        esquema = info_esquema.get('esquema', [])
        posiciones = info_esquema.get('posiciones', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        
        pos_actual = int(self.form_vars['posicion'].get() or 1)
        hechas = getattr(self, '_posiciones_inspeccionadas_pc', set())

        tot_pos = len(posiciones)
        tot_hechas = len(hechas.intersection(set(posiciones)))
        if hasattr(self, 'lbl_chasis_estado_pc'):
            self.lbl_chasis_estado_pc.config(
                text=f"Inspeccionadas: {tot_hechas} / {tot_pos}  ({(tot_hechas/tot_pos*100 if tot_pos else 0):.0f}%)",
                foreground='#059669' if tot_hechas == tot_pos and tot_pos > 0 else '#2563eb'
            )

        if not esquema:
            # Fallback simple si no hay esquema estructurado
            grid_f = ttk.Frame(self.frame_ejes_pc, style='Card.TFrame')
            grid_f.pack(pady=10)
            for idx, p in enumerate(posiciones):
                btn_bg = '#10b981' if p in hechas else ('#3b82f6' if p == pos_actual else '#e2e8f0')
                fg = '#ffffff' if (p in hechas or p == pos_actual) else '#1e293b'
                txt = f"✓ P{p}" if p in hechas else f"P{p}"
                b = tk.Button(grid_f, text=txt, bg=btn_bg, fg=fg, font=('Segoe UI', 9, 'bold'), width=5, relief='raised',
                              command=lambda p_sel=p: self.seleccionar_posicion_pc(p_sel))
                b.grid(row=idx//4, column=idx%4, padx=4, pady=4)
            return

        # Renderizar cada eje con visual realista
        for eje in esquema:
            tipo_eje = eje.get('tipo', 'traccion')
            nombre_eje = eje.get('nombre', '')
            
            # Encabezado del eje
            color_eje_bar = '#eab308' if tipo_eje == 'direccional' else ('#10b981' if tipo_eje == 'traccion' else '#06b6d4')
            eje_row = tk.Frame(self.frame_ejes_pc, bg='#ffffff', pady=6)
            eje_row.pack(fill='x', expand=True, padx=6)

            # Ruedas Izquierdas
            ruedas_izq = [p for p in eje.get('posiciones', []) if p.get('lado') == 'izq']
            f_izq = tk.Frame(eje_row, bg='#ffffff')
            f_izq.pack(side='left', padx=4)
            for r in ruedas_izq:
                self._crear_boton_rueda_pc(f_izq, r.get('pos'), r.get('rol', ''), pos_actual, hechas, tipo_eje)

            # Barra del eje con viga central
            f_centro = tk.Frame(eje_row, bg='#ffffff')
            f_centro.pack(side='left', fill='x', expand=True, padx=2)
            
            # Nombre/Rol del Eje
            lbl_eje = tk.Label(f_centro, text=nombre_eje.upper(), font=('Segoe UI', 7, 'bold'), bg='#ffffff', fg=color_eje_bar)
            lbl_eje.pack()
            # Viga física
            bar = tk.Frame(f_centro, bg=color_eje_bar, height=4)
            bar.pack(fill='x', pady=2)

            # Ruedas Derechas
            ruedas_der = [p for p in eje.get('posiciones', []) if p.get('lado') == 'der']
            f_der = tk.Frame(eje_row, bg='#ffffff')
            f_der.pack(side='right', padx=4)
            for r in ruedas_der:
                self._crear_boton_rueda_pc(f_der, r.get('pos'), r.get('rol', ''), pos_actual, hechas, tipo_eje)

    def _crear_boton_rueda_pc(self, parent, pos, rol, pos_actual, hechas, tipo_eje):
        es_actual = (pos == pos_actual)
        esta_inspeccionada = (pos in hechas)

        # Colores: Verde esmeralda si inspeccionada, azul eléctrico si seleccionada, pizarra si pendiente
        if es_actual and esta_inspeccionada:
            bg_color = '#047857' # Verde oscuro seleccionado
            fg_color = '#ffffff'
            border_c = '#facc15'
        elif es_actual:
            bg_color = '#2563eb' # Azul brillante
            fg_color = '#ffffff'
            border_c = '#1d4ed8'
        elif esta_inspeccionada:
            bg_color = '#10b981' # Verde esmeralda con check
            fg_color = '#ffffff'
            border_c = '#059669'
        else:
            bg_color = '#334155' # Pizarra oscuro
            fg_color = '#f8fafc'
            border_c = '#1e293b'

        txt = f"✓ {pos}" if esta_inspeccionada else str(pos)
        btn = tk.Button(
            parent,
            text=txt,
            bg=bg_color,
            fg=fg_color,
            activebackground='#3b82f6',
            activeforeground='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            width=4,
            height=2,
            relief='solid',
            bd=2 if es_actual else 1,
            cursor='hand2',
            command=lambda p_sel=pos: self.seleccionar_posicion_pc(p_sel)
        )
        btn.pack(side='left', padx=2)

    def al_cambiar_cliente_pc(self, event=None):
        cli = self.form_vars['cliente'].get().strip()
        subs = database.obtener_valores_unicos_campo('subcliente', cli)
        self.cb_sub_pc.config(values=subs)
        if subs and not self.form_vars['subcliente'].get():
            self.form_vars['subcliente'].set(subs[0])

    def actualizar_lista_buscador_pc(self):
        mods = database.obtener_catalogo_modelos()
        vals = [f"{m['marca']} {m['diseno']} ({m['dimension']}) - {m['prof_inicial']}mm [{m['tipo_llanta']}]" for m in mods]
        self.cb_busc_pc.config(values=vals)

    def al_seleccionar_modelo_buscador_pc(self, event=None):
        txt = self.var_busc_pc.get()
        mods = database.obtener_catalogo_modelos()
        for m in mods:
            rep = f"{m['marca']} {m['diseno']} ({m['dimension']}) - {m['prof_inicial']}mm [{m['tipo_llanta']}]"
            if rep == txt:
                self.form_vars['marca'].set(m['marca'])
                self.form_vars['diseno'].set(m['diseno'])
                self.form_vars['dimension'].set(m['dimension'])
                self.form_vars['prof_inicial'].set(str(m['prof_inicial']))
                if m['tipo_llanta'] == 'Reencauche':
                    self.form_vars['vida'].set('Reencauche')
                    self.form_vars['banda_reen'].set(m['diseno'])
                else:
                    self.form_vars['vida'].set('Original')
                self.actualizar_estado_banda_pc()
                break

    def verificar_llanta_previa_pc(self):
        placa = self.form_vars['placa'].get().strip()
        pos = int(self.form_vars['posicion'].get() or 1)
        prev = database.obtener_ultima_inspeccion_posicion(placa, pos)
        if prev:
            self._ultima_llanta_pc = prev
        else:
            self._ultima_llanta_pc = None

    def copiar_datos_previa_pc(self, avisar=False):
        self.verificar_llanta_previa_pc()
        prev = getattr(self, '_ultima_llanta_pc', None)
        if not prev:
            if avisar:
                messagebox.showinfo('Información', 'No hay inspección anterior registrada para esta placa y posición.')
            return
        if prev.get('numero_interno'): self.form_vars['numero_interno'].set(prev['numero_interno'])
        if prev.get('marca'): self.form_vars['marca'].set(prev['marca'])
        if prev.get('diseno'): self.form_vars['diseno'].set(prev['diseno'])
        if prev.get('dimension'): self.form_vars['dimension'].set(prev['dimension'])
        if prev.get('vida'):
            self.form_vars['vida'].set(prev['vida'])
            self.actualizar_estado_banda_pc()
        if prev.get('banda_reen'): self.form_vars['banda_reen'].set(prev['banda_reen'])
        if prev.get('prof_inicial'): self.form_vars['prof_inicial'].set(str(prev['prof_inicial']))
        if prev.get('precio'): self.form_vars['precio'].set(str(prev['precio']))
        if prev.get('km_montaje'): self.form_vars['km_montaje'].set(str(prev['km_montaje']))
        if prev.get('cliente') and not self.form_vars['cliente'].get(): self.form_vars['cliente'].set(prev['cliente'])
        if prev.get('subcliente') and not self.form_vars['subcliente'].get(): self.form_vars['subcliente'].set(prev['subcliente'])
        if prev.get('tipo_operacion') and not self.form_vars['tipo_operacion'].get(): self.form_vars['tipo_operacion'].set(prev['tipo_operacion'])
        if avisar:
            msg_txt = "Datos de inspección anterior cargados.\nNo. Interno: " + str(prev.get("numero_interno", "S/N")) + "\nÚltimas Profs: " + str(prev.get("prof_ext", 0)) + "/" + str(prev.get("prof_cent", 0)) + "/" + str(prev.get("prof_int", 0)) + " mm"
            messagebox.showinfo('Éxito', msg_txt)

    def auto_completar_prof_pc(self):
        m = self.form_vars['marca'].get().strip()
        d = self.form_vars['diseno'].get().strip()
        dim = self.form_vars['dimension'].get().strip()
        v = self.form_vars['vida'].get().strip()
        if m or d:
            prof = database.buscar_profundidad_inicial(m, d, dim, v)
            if prof > 0:
                p_actual = self.form_vars['prof_inicial'].get()
                if not p_actual or p_actual == '0':
                    self.form_vars['prof_inicial'].set(str(prof))

    def on_cambio_tipologia_pc(self, event=None):
        tipo = self.form_vars['tipologia'].get()
        posiciones = database.obtener_posiciones_por_tipologia(tipo)
        str_pos = [str(p) for p in posiciones]
        self.cb_pos_pc.config(values=str_pos)
        if self.form_vars['posicion'].get() not in str_pos and str_pos:
            self.form_vars['posicion'].set(str_pos[0])
        self.actualizar_estado_posiciones_inspeccionadas_pc()

    def actualizar_estado_banda_pc(self, event=None):
        vida = self.form_vars['vida'].get()
        if vida == 'Reencauche':
            self.entry_banda_pc.config(state='normal')
        else:
            self.form_vars['banda_reen'].set('')
            self.entry_banda_pc.config(state='disabled')
        self.auto_completar_prof_pc()

    def guardar_formulario_pc(self):
        placa = self.form_vars['placa'].get().strip().upper()
        if not placa:
            messagebox.showwarning('Atencion', 'Por favor ingresa la Placa.')
            return
        self.form_vars['placa'].set(placa)
        self._ultima_placa_pc = placa

        datos = {k: v.get() for k, v in self.form_vars.items()}
        
        # Validar Candados de Seguridad
        val = database.validar_inspeccion_candados(datos)
        if not val.get('valido', True):
            messagebox.showerror('Candado de Seguridad', val.get('mensaje', 'Operación denegada por seguridad.'))
            return

        try:
            database.insertar_inspeccion(datos)
            pos_actual = int(datos['posicion'])
            tipo = datos['tipologia']
            pos_disp = database.obtener_posiciones_por_tipologia(tipo)
            
            # Registrar posición como inspeccionada
            if not hasattr(self, '_posiciones_inspeccionadas_pc'):
                self._posiciones_inspeccionadas_pc = set()
            self._posiciones_inspeccionadas_pc.add(pos_actual)

            faltantes = [p for p in pos_disp if p not in self._posiciones_inspeccionadas_pc]
            if not faltantes:
                messagebox.showinfo('¡Vehículo Completo!', f'🎉 ¡Excelente! Todas las {len(pos_disp)} posiciones del vehículo [{placa}] han sido inspeccionadas exitosamente.')
            else:
                messagebox.showinfo('Éxito', f'Inspección de la Posición {pos_actual} guardada.')

            self.cargar_datos_bd()

            # Pasar a la siguiente posición automáticamente
            if pos_actual in pos_disp:
                idx = pos_disp.index(pos_actual)
                if idx + 1 < len(pos_disp):
                    self.form_vars['posicion'].set(str(pos_disp[idx + 1]))
            
            self.form_vars['prof_ext'].set('0')
            self.form_vars['prof_cent'].set('0')
            self.form_vars['prof_int'].set('0')
            self.form_vars['novedades'].set('')
            self.form_vars['numero_interno'].set('')
            
            # Refrescar Chasis Visual
            self.renderizar_chasis_pc()
            self.verificar_llanta_previa_pc()
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def limpiar_formulario_pc(self):
        self.form_vars['prof_ext'].set('0')
        self.form_vars['prof_cent'].set('0')
        self.form_vars['prof_int'].set('0')
        self.form_vars['novedades'].set('')
        self.actualizar_estado_banda_pc()

    def crear_tab_movil(self, parent):
        card = ttk.Frame(parent, style='Card.TFrame', padding=20)
        card.pack(fill='both', expand=True)
        ttk.Label(card, text='Conexión de Celulares en Campo y Patios (Internet / Wi-Fi / Offline)', font=('Segoe UI', 13, 'bold'), background='#ffffff').pack(anchor='w')
        ttk.Label(card, text='Permite que los inspectores en patios utilicen sus datos móviles (4G/5G) o trabajen en modo offline sin señal.', font=('Segoe UI', 9), background='#ffffff', foreground='#475569').pack(anchor='w', pady=(2, 10))

        top_box = ttk.Frame(card, style='Card.TFrame')
        top_box.pack(fill='x', pady=4)

        # Botón para activar túnel público de internet
        btn_box = ttk.Frame(top_box, style='Card.TFrame')
        btn_box.pack(side='left', padx=(0, 20))
        self.btn_tunel = ttk.Button(btn_box, text='🌐 Activar Enlace Público de Internet (ngrok)', style='Primary.TButton', command=self.alternar_tunel_ngrok)
        self.btn_tunel.pack(anchor='w', pady=2)

        self.lbl_estado_tunel = ttk.Label(btn_box, text='Estado: Solo Red Local / Wi-Fi', font=('Segoe UI', 9, 'italic'), foreground='#64748b', background='#ffffff')
        self.lbl_estado_tunel.pack(anchor='w', pady=1)

        # Contenedor QR y URLs
        qr_container = ttk.Frame(card, style='Card.TFrame')
        qr_container.pack(fill='x', pady=6)

        ip_local = obtener_ip_local()
        self.url_movil_actual = f'http://{ip_local}:8000'
        
        self.lbl_qr_img = ttk.Label(qr_container, background='#ffffff')
        self.lbl_qr_img.pack(side='left', padx=(0, 20))
        self.actualizar_imagen_qr(self.url_movil_actual)

        info_box = ttk.Frame(qr_container, style='Card.TFrame')
        info_box.pack(side='left', fill='both', expand=True)

        ttk.Label(info_box, text='Enlace para los Técnicos (Enviar por WhatsApp):', font=('Segoe UI', 10, 'bold'), background='#ffffff').pack(anchor='w')
        self.lbl_url_texto = ttk.Label(info_box, text=self.url_movil_actual, font=('Consolas', 11, 'bold'), foreground='#2563eb', background='#ffffff')
        self.lbl_url_texto.pack(anchor='w', pady=4)

        btn_copiar = ttk.Button(info_box, text='📋 Copiar Enlace para WhatsApp', command=self.copiar_enlace_movil)
        btn_copiar.pack(anchor='w', pady=2)

        instrucciones = (
            '📌 CÓMO OPERAN LOS TÉCNICOS EN LOS PATIOS:\n'
            '• Conexión por Internet (Datos Móviles 4G/5G): Haz clic en "Activar Enlace Público de Internet".\n'
            '  Copia el enlace seguro (HTTPS) y compártelo por WhatsApp con los inspectores para que ingresen desde cualquier patio.\n\n'
            '• Modo Desconectado / Offline (Sin Señal):\n'
            '  Si en el patio o sótano se pierde la señal celular, la aplicación seguirá guardando las inspecciones en la memoria del teléfono.\n'
            '  Aparecerá el indicador "Offline (Sin Señal)". En cuanto el técnico recupere señal o Wi-Fi, la app sincronizará\n'
            '  automáticamente todos los datos con este computador central sin perder ninguna medición.'
        )
        ttk.Label(card, text=instrucciones, font=('Segoe UI', 9), background='#ffffff', foreground='#1e293b', justify='left').pack(anchor='w', pady=10)

    def actualizar_imagen_qr(self, url):
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color='#0f172a', back_color='white')
        self.qr_photo = ImageTk.PhotoImage(img_qr)
        self.lbl_qr_img.config(image=self.qr_photo)

    def copiar_enlace_movil(self):
        url = getattr(self, 'url_movil_actual', '')
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            messagebox.showinfo('Enlace Copiado', f'Enlace copiado al portapapeles:\n\n{url}\n\nPégalo en el chat de WhatsApp con tus inspectores.')

    def alternar_tunel_ngrok(self):
        try:
            from pyngrok import ngrok
            if hasattr(self, '_ngrok_tunnel') and self._ngrok_tunnel:
                ngrok.disconnect(self._ngrok_tunnel.public_url)
                self._ngrok_tunnel = None
                ip_local = obtener_ip_local()
                self.url_movil_actual = f'http://{ip_local}:8000'
                self.actualizar_imagen_qr(self.url_movil_actual)
                self.lbl_url_texto.config(text=self.url_movil_actual)
                self.lbl_estado_tunel.config(text='Estado: Solo Red Local / Wi-Fi', foreground='#64748b')
                self.btn_tunel.config(text='🌐 Activar Enlace Público de Internet (ngrok)')
                messagebox.showinfo('Túnel Desconectado', 'Se ha cerrado el enlace público de internet.')
            else:
                self.lbl_estado_tunel.config(text='Iniciando túnel seguro...', foreground='#d97706')
                self.update_idletasks()
                tunnel = ngrok.connect(8000, "http")
                self._ngrok_tunnel = tunnel
                self.url_movil_actual = tunnel.public_url
                self.actualizar_imagen_qr(self.url_movil_actual)
                self.lbl_url_texto.config(text=self.url_movil_actual)
                self.lbl_estado_tunel.config(text=f'✅ EN LÍNEA POR INTERNET (Acceso Global)', foreground='#16a34a')
                self.btn_tunel.config(text='🛑 Desactivar Enlace Público de Internet')
                self.copiar_enlace_movil()
        except Exception as e:
            err_msg = str(e)
            if 'authtoken' in err_msg.lower():
                err_msg += "\n\nTip: Para usar ngrok gratis por primera vez, crea una cuenta gratuita en ngrok.com y ejecuta en la terminal:\nngrok config add-authtoken TU_TOKEN"
            messagebox.showerror('Error al Iniciar Túnel', f'No se pudo activar el enlace público:\n{err_msg}')

    def crear_tab_analisis(self, parent):
        resumen_frame = ttk.Frame(parent)
        resumen_frame.pack(fill='x', pady=(0, 10))
        self.card_total = self.crear_tarjeta(resumen_frame, 'VEHICULOS', '0', 0)
        self.card_cambio = self.crear_tarjeta(resumen_frame, 'SUGERENCIA CAMBIO', '0', 1, color_val='#b91c1c')
        self.card_alineacion = self.crear_tarjeta(resumen_frame, 'PLAN ALINEACION', '0', 2, color_val='#dc2626')
        self.card_dual = self.crear_tarjeta(resumen_frame, 'PLAN DUAL MAL APAREADO', '0', 3, color_val='#ea580c')
        self.card_ok = self.crear_tarjeta(resumen_frame, 'SIN NOVEDADES', '0', 4, color_val='#16a34a')
        bar1 = ttk.Frame(parent)
        bar1.pack(fill='x', pady=(0, 6))
        ttk.Button(bar1, text='Recalcular Diagnóstico', style='Primary.TButton', command=self.ejecutar_analisis).pack(side='left', padx=(0, 8))
        ttk.Button(bar1, text='📄 Plan PDF Vehículo', style='Primary.TButton', command=self.modal_generar_pdf_vehiculo).pack(side='left', padx=(0, 6))
        ttk.Button(bar1, text='📊 Consolidado Flota PDF', style='Success.TButton', command=self.modal_generar_pdf_consolidado).pack(side='left', padx=(0, 15))

        ttk.Label(bar1, text='Cliente:', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(5, 2))
        self.filtro_cliente_var = tk.StringVar(value='Todos')
        self.cb_filtro_cliente = ttk.Combobox(bar1, textvariable=self.filtro_cliente_var, state='readonly', width=16)
        self.cb_filtro_cliente.pack(side='left', padx=(0, 10))
        self.cb_filtro_cliente.bind('<<ComboboxSelected>>', self.al_cambiar_filtro_cliente)

        ttk.Label(bar1, text='Subcliente:', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(5, 2))
        self.filtro_subcliente_var = tk.StringVar(value='Todos')
        self.cb_filtro_subcliente = ttk.Combobox(bar1, textvariable=self.filtro_subcliente_var, state='readonly', width=16)
        self.cb_filtro_subcliente.pack(side='left', padx=(0, 10))
        self.cb_filtro_subcliente.bind('<<ComboboxSelected>>', lambda e: self.filtrar_tabla_analisis())

        bar2 = ttk.Frame(parent)
        bar2.pack(fill='x', pady=(0, 8))
        ttk.Label(bar2, text='Alerta:', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 5))
        self.filtro_analisis_var = tk.StringVar(value='Todos')
        for txt, val in [('Todos', 'Todos'), ('Sugerencia Cambio', 'Cambio'), ('Solo Alineacion', 'Alineacion'), ('Solo Dual', 'Dual'), ('Cualquier Alerta', 'Alerta'), ('OK', 'OK')]:
            ttk.Radiobutton(bar2, text=txt, value=val, variable=self.filtro_analisis_var, command=self.filtrar_tabla_analisis).pack(side='left', padx=4)
        ttk.Label(bar2, text='Buscar Placa:').pack(side='left', padx=(15, 4))
        self.buscar_analisis_var = tk.StringVar()
        self.buscar_analisis_var.trace_add('write', lambda *args: self.filtrar_tabla_analisis())
        ttk.Entry(bar2, textvariable=self.buscar_analisis_var, width=12).pack(side='left')
        cols_analisis = ('Vehículo/Placa', 'Cliente', 'Subcliente', 'Operación', 'Tipo', 'Km', 'Llantas Inspeccionadas', 'Límite Cambio', 'Sugerencia_Cambio', 'Plan_Alineacion', 'Plan_Dual_Mal_Apareado', 'Detalle_Cambio', 'Detalle_Alineacion', 'Detalle_Dual')
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)
        self.tree_analisis = ttk.Treeview(tree_frame, columns=cols_analisis, show='headings', selectmode='browse')
        for c in cols_analisis:
            self.tree_analisis.heading(c, text=c)
            self.tree_analisis.column(c, width=100 if 'Detalle' not in c else 230, anchor='center' if 'Detalle' not in c and c not in ('Cliente', 'Subcliente', 'Operación', 'Tipo') else 'w')
        self.tree_analisis.tag_configure('alerta_cambio', background='#fecaca')
        self.tree_analisis.tag_configure('alerta_ambos', background='#fee2e2')
        self.tree_analisis.tag_configure('alerta_uno', background='#fef3c7')
        self.tree_analisis.tag_configure('normal', background='#ffffff')
        sb_ay = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree_analisis.yview)
        sb_ax = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_analisis.xview)
        self.tree_analisis.configure(yscrollcommand=sb_ay.set, xscrollcommand=sb_ax.set)
        sb_ay.pack(side='right', fill='y')
        sb_ax.pack(side='bottom', fill='x')
        self.tree_analisis.pack(side='left', fill='both', expand=True)

    def crear_tarjeta(self, parent, titulo, valor_inicial, col_idx, color_val='#0f172a'):
        frame = ttk.Frame(parent, padding=(12, 8), style='Card.TFrame')
        frame.grid(row=0, column=col_idx, padx=5, sticky='nsew')
        parent.columnconfigure(col_idx, weight=1)
        ttk.Label(frame, text=titulo, style='CardTitle.TLabel').pack(anchor='w')
        lbl_val = ttk.Label(frame, text=valor_inicial, font=('Segoe UI', 16, 'bold'), foreground=color_val, background='#ffffff')
        lbl_val.pack(anchor='w', pady=(2, 0))
        return lbl_val

    def cargar_datos_bd(self):
        self.df_inspecciones = database.obtener_todas_inspecciones()
        self.filtrar_tabla_bd()
        self.ejecutar_analisis()

    def filtrar_tabla_bd(self):
        for item in self.tree_bd.get_children():
            self.tree_bd.delete(item)
        if self.df_inspecciones.empty:
            self.status_bar.config(text='Base de datos vacia.')
            return
        df = self.df_inspecciones.copy()
        filtro = self.buscar_bd_var.get().strip().upper()
        if filtro:
            cond = df['placa'].astype(str).str.upper().str.contains(filtro)
            if 'cliente' in df.columns:
                cond = cond | df['cliente'].astype(str).str.upper().str.contains(filtro)
            df = df[cond]
        for _, row in df.iterrows():
            valores = [row[c] for c in self.tree_bd['columns']]
            self.tree_bd.insert('', 'end', values=valores)
        self.status_bar.config(text=f'Total inspecciones: {len(self.df_inspecciones)}')

    def ejecutar_analisis(self):
        for item in self.tree_analisis.get_children():
            self.tree_analisis.delete(item)
        if self.df_inspecciones.empty:
            self.df_analisis = pd.DataFrame()
            self.card_total.config(text='0')
            self.card_alineacion.config(text='0')
            self.card_dual.config(text='0')
            self.card_ok.config(text='0')
            return
        self.df_analisis = database.analizar_inspecciones_df(self.df_inspecciones)
        total = len(self.df_analisis)
        cam_cnt = (self.df_analisis.get('Plan_Cambio_Llanta', pd.Series()) == 'SÍ').sum()
        al_cnt = (self.df_analisis['Plan_Alineacion'] == 'SÍ').sum()
        du_cnt = (self.df_analisis['Plan_Dual_Mal_Apareado'] == 'SÍ').sum()
        ok_cnt = ((self.df_analisis['Plan_Alineacion'] == 'NO') & (self.df_analisis['Plan_Dual_Mal_Apareado'] == 'NO') & (self.df_analisis.get('Plan_Cambio_Llanta', pd.Series()) == 'NO')).sum()
        self.card_total.config(text=str(total))
        self.card_cambio.config(text=str(cam_cnt))
        self.card_alineacion.config(text=str(al_cnt))
        self.card_dual.config(text=str(du_cnt))
        self.card_ok.config(text=str(ok_cnt))
        self.actualizar_combos_filtros_analisis()
        self.filtrar_tabla_analisis()

    def actualizar_combos_filtros_analisis(self):
        if self.df_analisis is None or self.df_analisis.empty:
            return
        clientes = ['Todos']
        if 'Cliente' in self.df_analisis.columns:
            cls = sorted([str(c) for c in self.df_analisis['Cliente'].dropna().unique() if str(c).strip()])
            clientes.extend(cls)
        self.cb_filtro_cliente.config(values=clientes)
        if self.filtro_cliente_var.get() not in clientes:
            self.filtro_cliente_var.set('Todos')
        self.al_cambiar_filtro_cliente()

    def al_cambiar_filtro_cliente(self, event=None):
        if self.df_analisis is None or self.df_analisis.empty:
            return
        c_sel = self.filtro_cliente_var.get()
        subclientes = ['Todos']
        df_sub = self.df_analisis
        if c_sel != 'Todos' and 'Cliente' in df_sub.columns:
            df_sub = df_sub[df_sub['Cliente'] == c_sel]
        if 'Subcliente' in df_sub.columns:
            subs = sorted([str(s) for s in df_sub['Subcliente'].dropna().unique() if str(s).strip()])
            subclientes.extend(subs)
        self.cb_filtro_subcliente.config(values=subclientes)
        if self.filtro_subcliente_var.get() not in subclientes:
            self.filtro_subcliente_var.set('Todos')
        self.filtrar_tabla_analisis()

    def filtrar_tabla_analisis(self):
        if self.df_analisis is None or self.df_analisis.empty:
            return
        for item in self.tree_analisis.get_children():
            self.tree_analisis.delete(item)
        filtro = self.filtro_analisis_var.get()
        busqueda = self.buscar_analisis_var.get().strip().upper()
        c_sel = getattr(self, 'filtro_cliente_var', tk.StringVar(value='Todos')).get()
        s_sel = getattr(self, 'filtro_subcliente_var', tk.StringVar(value='Todos')).get()
        df = self.df_analisis.copy()
        if c_sel != 'Todos' and 'Cliente' in df.columns:
            df = df[df['Cliente'] == c_sel]
        if s_sel != 'Todos' and 'Subcliente' in df.columns:
            df = df[df['Subcliente'] == s_sel]
        if busqueda:
            df = df[df['Vehículo/Placa'].astype(str).str.upper().str.contains(busqueda)]
        if filtro == 'Cambio':
            df = df[df.get('Plan_Cambio_Llanta', '') == 'SÍ']
        elif filtro == 'Alineacion':
            df = df[df['Plan_Alineacion'] == 'SÍ']
        elif filtro == 'Dual':
            df = df[df['Plan_Dual_Mal_Apareado'] == 'SÍ']
        elif filtro == 'Alerta':
            df = df[(df['Plan_Alineacion'] == 'SÍ') | (df['Plan_Dual_Mal_Apareado'] == 'SÍ') | (df.get('Plan_Cambio_Llanta', '') == 'SÍ')]
        elif filtro == 'OK':
            df = df[(df['Plan_Alineacion'] == 'NO') & (df['Plan_Dual_Mal_Apareado'] == 'NO') & (df.get('Plan_Cambio_Llanta', '') == 'NO')]
        for _, row in df.iterrows():
            tag = 'normal'
            if row.get('Plan_Cambio_Llanta', '') == 'SÍ':
                tag = 'alerta_cambio'
            elif row['Plan_Alineacion'] == 'SÍ' and row['Plan_Dual_Mal_Apareado'] == 'SÍ':
                tag = 'alerta_ambos'
            elif row['Plan_Alineacion'] == 'SÍ' or row['Plan_Dual_Mal_Apareado'] == 'SÍ':
                tag = 'alerta_uno'
            lim_mm = row.get('Limite_Retiro_mm', 3.0)
            self.tree_analisis.insert('', 'end', values=(
                row['Vehículo/Placa'],
                row.get('Cliente', ''),
                row.get('Subcliente', ''),
                row.get('Operación', ''),
                row['Tipo'],
                row['Km'],
                row['Llantas Inspeccionadas'],
                f"{lim_mm:.1f} mm",
                row.get('Plan_Cambio_Llanta', 'NO'),
                row['Plan_Alineacion'],
                row['Plan_Dual_Mal_Apareado'],
                row.get('Detalle_Cambio', 'OK'),
                row['Detalle_Alineacion'],
                row['Detalle_Dual']
            ), tags=(tag,))

    def importar_excel(self):
        ruta = filedialog.askopenfilename(title='Seleccionar Excel', filetypes=[('Archivos Excel', '*.xlsx *.xls')])
        if not ruta:
            return
        def tarea():
            try:
                cant = database.cargar_excel_a_bd(ruta)
                self.after(0, lambda: messagebox.showinfo('Completado', f'Se importaron {cant} registros.'))
                self.after(0, self.cargar_datos_bd)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Error', str(e)))
        threading.Thread(target=tarea, daemon=True).start()

    def descargar_plantilla_excel(self):
        ruta = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Libro Excel', '*.xlsx')],
            initialfile='Plantilla_Cargue_Masivo_Inspecciones.xlsx',
            title='Guardar Plantilla de Cargue Masivo'
        )
        if not ruta:
            return
        
        columnas = [
            'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'numero_interno',
            'posicion', 'kilometraje', 'tipologia', 'marca', 'diseno', 'dimension',
            'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int', 'psi',
            'novedades', 'precio', 'prof_inicial', 'km_montaje'
        ]
        
        datos_guia = [
            {
                'fecha': datetime.now().strftime('%Y-%m-%d'),
                'cliente': 'Axxom',
                'subcliente': 'Principal',
                'tipo_operacion': 'Carga Seca',
                'placa': 'ABC123',
                'numero_interno': 'LL-001',
                'posicion': 1,
                'kilometraje': 120500,
                'tipologia': 'Cabezote (6x4)',
                'marca': 'Michelin',
                'diseno': 'X Multi Z',
                'dimension': '295/80R22.5',
                'vida': 'Original',
                'banda_reen': '',
                'prof_ext': 14.5,
                'prof_cent': 14.2,
                'prof_int': 14.4,
                'psi': 110,
                'novedades': 'Buen estado',
                'precio': 1650000,
                'prof_inicial': 16.5,
                'km_montaje': 80000
            },
            {
                'fecha': datetime.now().strftime('%Y-%m-%d'),
                'cliente': 'Axxom',
                'subcliente': 'Principal',
                'tipo_operacion': 'Carga Seca',
                'placa': 'ABC123',
                'numero_interno': 'LL-002',
                'posicion': 2,
                'kilometraje': 120500,
                'tipologia': 'Cabezote (6x4)',
                'marca': 'Michelin',
                'diseno': 'X Multi Z',
                'dimension': '295/80R22.5',
                'vida': 'Original',
                'banda_reen': '',
                'prof_ext': 14.3,
                'prof_cent': 14.1,
                'prof_int': 14.0,
                'psi': 110,
                'novedades': '',
                'precio': 1650000,
                'prof_inicial': 16.5,
                'km_montaje': 80000
            }
        ]
        try:
            df = pd.DataFrame(datos_guia, columns=columnas)
            df.to_excel(ruta, index=False, sheet_name='Plantilla_Inspecciones')
            messagebox.showinfo('Éxito', f'Plantilla guardada en:\n{ruta}\n\nPuedes llenarla con tus inspecciones y luego cargarla con el botón "Importar Excel".')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def exportar_bd_excel(self):
        if self.df_inspecciones.empty:
            messagebox.showwarning('Sin datos', 'No hay registros para exportar.')
            return
        f_str = datetime.now().strftime('%Y%m%d')
        ruta = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Libro Excel', '*.xlsx')], initialfile=f'Base_Inspecciones_{f_str}.xlsx')
        if not ruta:
            return
        try:
            with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
                self.df_inspecciones.to_excel(writer, sheet_name='Inspecciones', index=False)
            messagebox.showinfo('Exportado', f'Archivo guardado en:\n{ruta}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def exportar_diagnostico_excel(self):
        if self.df_analisis is None or self.df_analisis.empty:
            messagebox.showwarning('Sin datos', 'No hay analisis disponible.')
            return
        f_str = datetime.now().strftime('%Y%m%d')
        ruta = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Libro Excel', '*.xlsx')], initialfile=f'Diagnostico_Flota_{f_str}.xlsx')
        if not ruta:
            return
        try:
            with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
                self.df_analisis.to_excel(writer, sheet_name='Planes_Accion', index=False)
                if not self.df_inspecciones.empty:
                    self.df_inspecciones.to_excel(writer, sheet_name='Detalle_Inspecciones', index=False)
            messagebox.showinfo('Exportado', f'Informe guardado en:\n{ruta}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def editar_fila_seleccionada(self):
        seleccion = self.tree_bd.selection()
        if not seleccion:
            messagebox.showwarning('Atención', 'Por favor selecciona la fila de la llanta que deseas editar.')
            return

        valores = self.tree_bd.item(seleccion[0])['values']
        cols = ('id', 'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'numero_interno', 'posicion', 'kilometraje', 'tipologia', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int', 'psi', 'novedades', 'precio', 'prof_inicial', 'km_montaje')
        datos_actuales = dict(zip(cols, valores))
        reg_id = datos_actuales.get('id')

        top = tk.Toplevel(self)
        top.title(f'Editar Inspección de Llanta (ID: {reg_id}) - {datos_actuales.get("placa")} Pos {datos_actuales.get("posicion")}')
        top.geometry('650x540')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        header_frame = tk.Frame(top, bg='#1e293b', padx=16, pady=12)
        header_frame.pack(fill='x')
        tk.Label(header_frame, text=f'Modificar Información de la Llanta (ID {reg_id})', font=('Segoe UI', 12, 'bold'), bg='#1e293b', fg='#ffffff').pack(anchor='w')
        tk.Label(header_frame, text=f'Vehículo: {datos_actuales.get("placa")} | Posición: {datos_actuales.get("posicion")} | Cliente: {datos_actuales.get("cliente")}', font=('Segoe UI', 9), bg='#1e293b', fg='#93c5fd').pack(anchor='w')

        body = ttk.Frame(top, padding=16)
        body.pack(fill='both', expand=True)

        campos_vars = {}
        
        # Fila 0: Fecha, Cliente, Subcliente
        ttk.Label(body, text='Fecha:').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        campos_vars['fecha'] = tk.StringVar(value=str(datos_actuales.get('fecha', '')))
        ttk.Entry(body, textvariable=campos_vars['fecha'], width=14).grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(body, text='Cliente:').grid(row=0, column=2, sticky='w', padx=4, pady=4)
        campos_vars['cliente'] = tk.StringVar(value=str(datos_actuales.get('cliente', '')))
        ttk.Entry(body, textvariable=campos_vars['cliente'], width=18).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(body, text='Sede/Subcli:').grid(row=0, column=4, sticky='w', padx=4, pady=4)
        campos_vars['subcliente'] = tk.StringVar(value=str(datos_actuales.get('subcliente', '')))
        ttk.Entry(body, textvariable=campos_vars['subcliente'], width=14).grid(row=0, column=5, padx=4, pady=4)

        # Fila 1: Operación, Placa, Posición
        ttk.Label(body, text='Operación:').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        campos_vars['tipo_operacion'] = tk.StringVar(value=str(datos_actuales.get('tipo_operacion', '')))
        ttk.Entry(body, textvariable=campos_vars['tipo_operacion'], width=14).grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(body, text='Placa:').grid(row=1, column=2, sticky='w', padx=4, pady=4)
        campos_vars['placa'] = tk.StringVar(value=str(datos_actuales.get('placa', '')))
        ttk.Entry(body, textvariable=campos_vars['placa'], width=18).grid(row=1, column=3, padx=4, pady=4)

        ttk.Label(body, text='Posición:').grid(row=1, column=4, sticky='w', padx=4, pady=4)
        campos_vars['posicion'] = tk.StringVar(value=str(datos_actuales.get('posicion', '1')))
        ttk.Entry(body, textvariable=campos_vars['posicion'], width=14).grid(row=1, column=5, padx=4, pady=4)

        # Fila 2: No. Interno, Kilometraje, Tipología
        ttk.Label(body, text='No. Interno:').grid(row=2, column=0, sticky='w', padx=4, pady=4)
        campos_vars['numero_interno'] = tk.StringVar(value=str(datos_actuales.get('numero_interno', '')))
        ttk.Entry(body, textvariable=campos_vars['numero_interno'], width=14).grid(row=2, column=1, padx=4, pady=4)

        ttk.Label(body, text='Kilometraje:').grid(row=2, column=2, sticky='w', padx=4, pady=4)
        campos_vars['kilometraje'] = tk.StringVar(value=str(datos_actuales.get('kilometraje', '0')))
        ttk.Entry(body, textvariable=campos_vars['kilometraje'], width=18).grid(row=2, column=3, padx=4, pady=4)

        ttk.Label(body, text='Tipología:').grid(row=2, column=4, sticky='w', padx=4, pady=4)
        campos_vars['tipologia'] = tk.StringVar(value=str(datos_actuales.get('tipologia', '')))
        ttk.Entry(body, textvariable=campos_vars['tipologia'], width=14).grid(row=2, column=5, padx=4, pady=4)

        # Separador visual
        ttk.Separator(body, orient='horizontal').grid(row=3, column=0, columnspan=6, sticky='ew', pady=10)

        # Fila 4: Marca, Diseño, Dimensión
        ttk.Label(body, text='Marca:').grid(row=4, column=0, sticky='w', padx=4, pady=4)
        campos_vars['marca'] = tk.StringVar(value=str(datos_actuales.get('marca', '')))
        ttk.Entry(body, textvariable=campos_vars['marca'], width=14).grid(row=4, column=1, padx=4, pady=4)

        ttk.Label(body, text='Diseño:').grid(row=4, column=2, sticky='w', padx=4, pady=4)
        campos_vars['diseno'] = tk.StringVar(value=str(datos_actuales.get('diseno', '')))
        ttk.Entry(body, textvariable=campos_vars['diseno'], width=18).grid(row=4, column=3, padx=4, pady=4)

        ttk.Label(body, text='Dimensión:').grid(row=4, column=4, sticky='w', padx=4, pady=4)
        campos_vars['dimension'] = tk.StringVar(value=str(datos_actuales.get('dimension', '')))
        ttk.Entry(body, textvariable=campos_vars['dimension'], width=14).grid(row=4, column=5, padx=4, pady=4)

        # Fila 5: Vida, Banda, PSI
        ttk.Label(body, text='Vida:').grid(row=5, column=0, sticky='w', padx=4, pady=4)
        campos_vars['vida'] = tk.StringVar(value=str(datos_actuales.get('vida', 'Original')))
        cb_v = ttk.Combobox(body, textvariable=campos_vars['vida'], values=['Original', 'Reencauche'], state='readonly', width=12)
        cb_v.grid(row=5, column=1, padx=4, pady=4)

        ttk.Label(body, text='Banda Reen:').grid(row=5, column=2, sticky='w', padx=4, pady=4)
        campos_vars['banda_reen'] = tk.StringVar(value=str(datos_actuales.get('banda_reen', '')))
        ttk.Entry(body, textvariable=campos_vars['banda_reen'], width=18).grid(row=5, column=3, padx=4, pady=4)

        ttk.Label(body, text='Presión (PSI):').grid(row=5, column=4, sticky='w', padx=4, pady=4)
        campos_vars['psi'] = tk.StringVar(value=str(datos_actuales.get('psi', '100')))
        ttk.Entry(body, textvariable=campos_vars['psi'], width=14).grid(row=5, column=5, padx=4, pady=4)

        # Separador visual de Mediciones
        ttk.Separator(body, orient='horizontal').grid(row=6, column=0, columnspan=6, sticky='ew', pady=10)

        # Fila 7: Prof Ext, Prof Cent, Prof Int
        ttk.Label(body, text='Prof. Ext (mm):', font=('Segoe UI', 9, 'bold')).grid(row=7, column=0, sticky='w', padx=4, pady=4)
        campos_vars['prof_ext'] = tk.StringVar(value=str(datos_actuales.get('prof_ext', '0.0')))
        ttk.Entry(body, textvariable=campos_vars['prof_ext'], width=14, font=('Consolas', 10, 'bold')).grid(row=7, column=1, padx=4, pady=4)

        ttk.Label(body, text='Prof. Cent (mm):', font=('Segoe UI', 9, 'bold')).grid(row=7, column=2, sticky='w', padx=4, pady=4)
        campos_vars['prof_cent'] = tk.StringVar(value=str(datos_actuales.get('prof_cent', '0.0')))
        ttk.Entry(body, textvariable=campos_vars['prof_cent'], width=18, font=('Consolas', 10, 'bold')).grid(row=7, column=3, padx=4, pady=4)

        ttk.Label(body, text='Prof. Int (mm):', font=('Segoe UI', 9, 'bold')).grid(row=7, column=4, sticky='w', padx=4, pady=4)
        campos_vars['prof_int'] = tk.StringVar(value=str(datos_actuales.get('prof_int', '0.0')))
        ttk.Entry(body, textvariable=campos_vars['prof_int'], width=14, font=('Consolas', 10, 'bold')).grid(row=7, column=5, padx=4, pady=4)

        # Fila 8: Novedades / Observación
        ttk.Label(body, text='Novedades/Obs:').grid(row=8, column=0, sticky='w', padx=4, pady=6)
        campos_vars['novedades'] = tk.StringVar(value=str(datos_actuales.get('novedades', '')))
        ttk.Entry(body, textvariable=campos_vars['novedades'], width=48).grid(row=8, column=1, columnspan=4, sticky='we', padx=4, pady=6)

        # Fila 9: Prof Inicial, Precio, Km Montaje
        ttk.Label(body, text='Prof Inicial:').grid(row=9, column=0, sticky='w', padx=4, pady=4)
        campos_vars['prof_inicial'] = tk.StringVar(value=str(datos_actuales.get('prof_inicial', '0')))
        ttk.Entry(body, textvariable=campos_vars['prof_inicial'], width=14).grid(row=9, column=1, padx=4, pady=4)

        ttk.Label(body, text='Precio ($):').grid(row=9, column=2, sticky='w', padx=4, pady=4)
        campos_vars['precio'] = tk.StringVar(value=str(datos_actuales.get('precio', '0')))
        ttk.Entry(body, textvariable=campos_vars['precio'], width=18).grid(row=9, column=3, padx=4, pady=4)

        ttk.Label(body, text='Km Montaje:').grid(row=9, column=4, sticky='w', padx=4, pady=4)
        campos_vars['km_montaje'] = tk.StringVar(value=str(datos_actuales.get('km_montaje', '0')))
        ttk.Entry(body, textvariable=campos_vars['km_montaje'], width=14).grid(row=9, column=5, padx=4, pady=4)

        def guardar_cambios():
            try:
                datos_nuevos = {k: v.get().strip() for k, v in campos_vars.items()}
                
                # Validar Candados de Seguridad (excluyendo el propio registro que se está editando)
                val = database.validar_inspeccion_candados(datos_nuevos, excluir_id=reg_id)
                if not val.get('valido', True):
                    messagebox.showerror('Candado de Seguridad', val.get('mensaje', 'Operación denegada por seguridad.'))
                    return

                ok = database.actualizar_inspeccion(reg_id, datos_nuevos)
                if ok:
                    top.destroy()
                    self.cargar_datos_bd()
                    self.ejecutar_analisis()
                    self.recargar_tabla_kpis()
                    messagebox.showinfo('Éxito', f'La llanta ID {reg_id} (Pos {datos_nuevos.get("posicion")}) fue actualizada correctamente.')
                else:
                    messagebox.showerror('Error', 'No se pudo guardar la modificación.')
            except Exception as ex:
                messagebox.showerror('Error al Actualizar', str(ex))

        btn_box = ttk.Frame(top, padding=12)
        btn_box.pack(fill='x', side='bottom')
        ttk.Button(btn_box, text='💾 Guardar Cambios en la BD', style='Success.TButton', command=guardar_cambios).pack(side='right', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='right', padx=6)

    def eliminar_fila_seleccionada(self):
        seleccion = self.tree_bd.selection()
        if not seleccion:
            messagebox.showwarning('Atencion', 'Por favor selecciona una fila para eliminar.')
            return
        reg_id = self.tree_bd.item(seleccion[0])['values'][0]
        if messagebox.askyesno('Confirmar', f'¿Eliminar el registro ID {reg_id}?'):
            database.eliminar_inspeccion(reg_id)
            self.cargar_datos_bd()

    def crear_tab_catalogos(self, parent):
        nb_cat = ttk.Notebook(parent)
        nb_cat.pack(fill='both', expand=True)

        # Subtab 1: Tipos de Operación y Tipologías
        sub1 = ttk.Frame(nb_cat, padding=8)
        nb_cat.add(sub1, text='Operaciones & Tipologías')

        paneles = ttk.PanedWindow(sub1, orient='horizontal')
        paneles.pack(fill='both', expand=True)

        # Panel Izquierdo: Tipos de Operación
        frame_ops = ttk.LabelFrame(paneles, text='1. Tipos de Operación', padding=10)
        paneles.add(frame_ops, weight=1)

        bar_ops = ttk.Frame(frame_ops)
        bar_ops.pack(fill='x', pady=(0, 8))
        ttk.Button(bar_ops, text='+ Nueva', style='Primary.TButton', command=self.modal_agregar_operacion).pack(side='left', padx=(0, 4))
        ttk.Button(bar_ops, text='Editar', command=self.modal_editar_operacion).pack(side='left', padx=(0, 4))
        ttk.Button(bar_ops, text='Eliminar', command=self.eliminar_operacion_seleccionada).pack(side='left', padx=(0, 4))

        self.listbox_ops = tk.Listbox(frame_ops, font=('Segoe UI', 10), height=14)
        self.listbox_ops.pack(fill='both', expand=True)

        # Panel Derecho: Tipologías de Vehículo
        frame_tips = ttk.LabelFrame(paneles, text='2. Tipologías de Vehículo', padding=10)
        paneles.add(frame_tips, weight=2)

        bar_tips = ttk.Frame(frame_tips)
        bar_tips.pack(fill='x', pady=(0, 8))
        ttk.Button(bar_tips, text='+ Nueva', style='Success.TButton', command=self.modal_agregar_tipologia).pack(side='left', padx=(0, 4))
        ttk.Button(bar_tips, text='Editar', command=self.modal_editar_tipologia).pack(side='left', padx=(0, 4))
        ttk.Button(bar_tips, text='Eliminar', command=self.eliminar_tipologia_seleccionada).pack(side='left', padx=(0, 4))

        cols_tip = ('nombre', 'llantas', 'descripcion')
        self.tree_tips = ttk.Treeview(frame_tips, columns=cols_tip, show='headings', height=14)
        self.tree_tips.heading('nombre', text='Nombre Tipología')
        self.tree_tips.heading('llantas', text='Cant Llantas')
        self.tree_tips.heading('descripcion', text='Descripción / Esquema')
        self.tree_tips.column('nombre', width=160)
        self.tree_tips.column('llantas', width=70, anchor='center')
        self.tree_tips.column('descripcion', width=220)
        self.tree_tips.pack(fill='both', expand=True)

        # Subtab 2: Catálogo de Llantas Nuevas y Reencauches
        sub2 = ttk.Frame(nb_cat, padding=8)
        nb_cat.add(sub2, text='Catálogo de Modelos (Prof. Iniciales)')

        bar_mod = ttk.Frame(sub2)
        bar_mod.pack(fill='x', pady=(0, 8))
        ttk.Button(bar_mod, text='+ Agregar Modelo de Llanta', style='Primary.TButton', command=self.modal_agregar_modelo_llanta).pack(side='left', padx=(0, 6))
        ttk.Button(bar_mod, text='Recargar Modelos', command=self.recargar_catalogo_modelos).pack(side='left', padx=(0, 15))
        ttk.Label(bar_mod, text='Filtro Tipo:').pack(side='left', padx=(0, 4))
        self.filtro_mod_tipo = tk.StringVar(value='Todos')
        for txt, val in [('Todos', 'Todos'), ('Nuevas', 'Nueva'), ('Reencauches', 'Reencauche')]:
            ttk.Radiobutton(bar_mod, text=txt, value=val, variable=self.filtro_mod_tipo, command=self.recargar_catalogo_modelos).pack(side='left', padx=3)

        cols_mod = ('tipo', 'marca', 'diseno', 'dimension', 'prof_inicial', 'desc')
        self.tree_modelos = ttk.Treeview(sub2, columns=cols_mod, show='headings', height=14)
        self.tree_modelos.heading('tipo', text='Tipo')
        self.tree_modelos.heading('marca', text='Marca')
        self.tree_modelos.heading('diseno', text='Diseño / Banda')
        self.tree_modelos.heading('dimension', text='Dimensión')
        self.tree_modelos.heading('prof_inicial', text='Prof. Inicial (mm)')
        self.tree_modelos.heading('desc', text='Aplicación / Observaciones')
        self.tree_modelos.column('tipo', width=90, anchor='center')
        self.tree_modelos.column('marca', width=120)
        self.tree_modelos.column('diseno', width=140)
        self.tree_modelos.column('dimension', width=110, anchor='center')
        self.tree_modelos.column('prof_inicial', width=110, anchor='center')
        self.tree_modelos.column('desc', width=220)
        self.tree_modelos.pack(fill='both', expand=True)

        # Subtab 3: Límites de Retiro / Cambio por Cliente
        sub3 = ttk.Frame(nb_cat, padding=8)
        nb_cat.add(sub3, text='Límites de Cambio por Cliente (mm)')

        bar_cli = ttk.Frame(sub3)
        bar_cli.pack(fill='x', pady=(0, 8))
        ttk.Button(bar_cli, text='+ Configurar Límite Cliente', style='Primary.TButton', command=self.modal_configurar_limite_cliente).pack(side='left', padx=(0, 6))
        ttk.Button(bar_cli, text='Recargar Límites', command=self.recargar_configuraciones_clientes).pack(side='left', padx=(0, 15))
        ttk.Label(bar_cli, text='Nota: Por defecto todos los clientes inician en 3.0 mm (profundidad más baja).', font=('Segoe UI', 8, 'italic'), foreground='#64748b').pack(side='left')

        cols_cli = ('cliente', 'limite_mm', 'observaciones', 'fecha_act')
        self.tree_clientes_lim = ttk.Treeview(sub3, columns=cols_cli, show='headings', height=14)
        self.tree_clientes_lim.heading('cliente', text='Cliente / Flota')
        self.tree_clientes_lim.heading('limite_mm', text='Límite de Cambio / Retiro')
        self.tree_clientes_lim.heading('observaciones', text='Observaciones / Política Técnica')
        self.tree_clientes_lim.heading('fecha_act', text='Última Actualización')
        self.tree_clientes_lim.column('cliente', width=200)
        self.tree_clientes_lim.column('limite_mm', width=160, anchor='center')
        self.tree_clientes_lim.column('observaciones', width=260)
        self.tree_clientes_lim.column('fecha_act', width=160, anchor='center')
        self.tree_clientes_lim.pack(fill='both', expand=True)

        self.recargar_listas_catalogos()
        self.recargar_catalogo_modelos()
        self.recargar_configuraciones_clientes()

    def recargar_listas_catalogos(self):
        # Actualizar Operaciones
        self.listbox_ops.delete(0, tk.END)
        ops = database.obtener_todas_operaciones()
        for op in ops:
            self.listbox_ops.insert(tk.END, f"  •  {op}")
        if hasattr(self, 'cb_op_pc'):
            self.cb_op_pc.config(values=ops)

        # Actualizar Tipologías
        for item in self.tree_tips.get_children():
            self.tree_tips.delete(item)
        tips = database.obtener_todas_tipologias()
        nombres_tips = []
        for t in tips:
            nom = t['nombre']
            nombres_tips.append(nom)
            self.tree_tips.insert('', tk.END, values=(nom, t.get('cant_llantas', 10), t.get('descripcion', '')))
        if hasattr(self, 'cb_tip_pc'):
            self.cb_tip_pc.config(values=nombres_tips)

    def modal_agregar_operacion(self):
        top = tk.Toplevel(self)
        top.title('Agregar Tipo de Operación')
        top.geometry('380x180')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text='Nombre de la Operación:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(16, 4))
        var_nom = tk.StringVar()
        ent = ttk.Entry(top, textvariable=var_nom, width=32, font=('Segoe UI', 10))
        ent.pack(padx=18, pady=4, fill='x')
        ent.focus()

        def guardar():
            nom = var_nom.get().strip()
            if not nom:
                messagebox.showwarning('Atención', 'Ingresa el nombre de la operación.')
                return
            database.guardar_operacion(nom)
            self.recargar_listas_catalogos()
            self.form_vars['tipo_operacion'].set(nom)
            top.destroy()
            messagebox.showinfo('Éxito', f'Operación "{nom}" registrada y disponible para todos los clientes.')

        btn_box = ttk.Frame(top)
        btn_box.pack(pady=16)
        ttk.Button(btn_box, text='Guardar', style='Primary.TButton', command=guardar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def modal_agregar_tipologia(self):
        top = tk.Toplevel(self)
        top.title('Agregar Tipología de Vehículo')
        top.geometry('440x330')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text='Nombre de Tipología:*', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(10, 2))
        var_nom = tk.StringVar()
        ent_nom = ttk.Entry(top, textvariable=var_nom, font=('Segoe UI', 10))
        ent_nom.pack(padx=18, fill='x')
        ent_nom.focus()

        ttk.Label(top, text='Descripción / Observaciones:', font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=(6, 2))
        var_desc = tk.StringVar()
        ttk.Entry(top, textvariable=var_desc, font=('Segoe UI', 10)).pack(padx=18, fill='x')

        f_mid = ttk.Frame(top)
        f_mid.pack(fill='x', padx=18, pady=(6, 2))

        ttk.Label(f_mid, text='Cantidad de Llantas:*', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 8))
        var_cant = tk.StringVar(value='10')
        ttk.Spinbox(f_mid, from_=2, to=36, textvariable=var_cant, width=8, font=('Segoe UI', 10)).pack(side='left')

        ttk.Label(top, text='Configuración / Esquema de Ejes:*', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(6, 2))
        var_cfg_ejes = tk.StringVar(value='Automático')
        opciones_ejes = [
            'Automático',
            'Articulado (1 Dir + 1 Tracción Dual + 1 Libre Dual - 10 llantas)',
            'Biarticulado (1 Dir + 1 Tracción Dual + 2 Libres Duales - 14 llantas)',
            'Camión 2 Ejes (1 Dir + 1 Tracción Dual - 6 llantas)',
            'Cabezote 6x4 (1 Dir + 2 Tracción Dual - 10 llantas)',
            'Cuatro Manos (2 Dir + 2 Tracción Dual - 12 llantas)',
            'Trailer 3 Ejes (3 Ejes Arrastre Duales - 12 llantas)',
            'Personalizado (ej: dir,trac,libre,libre)'
        ]
        cb_cfg = ttk.Combobox(top, textvariable=var_cfg_ejes, values=opciones_ejes, state='readonly', font=('Segoe UI', 9))
        cb_cfg.pack(padx=18, fill='x')

        var_custom = tk.StringVar()
        ent_custom = ttk.Entry(top, textvariable=var_custom, font=('Segoe UI', 9))

        def on_eje_change(*args):
            v = var_cfg_ejes.get()
            if 'Articulado (' in v:
                var_cant.set('10')
                ent_custom.pack_forget()
            elif 'Biarticulado (' in v:
                var_cant.set('14')
                ent_custom.pack_forget()
            elif 'Camión 2 Ejes' in v:
                var_cant.set('6')
                ent_custom.pack_forget()
            elif 'Cabezote 6x4' in v:
                var_cant.set('10')
                ent_custom.pack_forget()
            elif 'Cuatro Manos' in v:
                var_cant.set('12')
                ent_custom.pack_forget()
            elif 'Trailer 3 Ejes' in v:
                var_cant.set('12')
                ent_custom.pack_forget()
            elif 'Personalizado' in v:
                ent_custom.pack(padx=18, fill='x', pady=4)
                ent_custom.focus()
            else:
                ent_custom.pack_forget()

        cb_cfg.bind('<<ComboboxSelected>>', on_eje_change)

        def guardar():
            nom = var_nom.get().strip()
            if not nom:
                messagebox.showwarning('Atención', 'Ingresa el nombre de la tipología.')
                return
            try:
                cant = int(var_cant.get())
            except ValueError:
                cant = 10

            v = var_cfg_ejes.get()
            cfg_code = ''
            if 'Articulado (' in v: cfg_code = 'dir,trac,libre'
            elif 'Biarticulado (' in v: cfg_code = 'dir,trac,libre,libre'
            elif 'Camión 2 Ejes' in v: cfg_code = 'dir,trac'
            elif 'Cabezote 6x4' in v: cfg_code = 'dir,trac,trac'
            elif 'Cuatro Manos' in v: cfg_code = 'dir,dir,trac,trac'
            elif 'Trailer 3 Ejes' in v: cfg_code = 'remolque,remolque,remolque'
            elif 'Personalizado' in v: cfg_code = var_custom.get().strip()

            database.guardar_tipologia(nom, var_desc.get().strip(), cant, config_ejes=cfg_code)
            self.recargar_listas_catalogos()
            self.form_vars['tipologia'].set(nom)
            self.on_cambio_tipologia_pc()
            top.destroy()
            messagebox.showinfo('Éxito', f'Tipología "{nom}" ({cant} llantas) registrada correctamente.')

        btn_box = ttk.Frame(top)
        btn_box.pack(pady=14)
        ttk.Button(btn_box, text='Guardar Tipología', style='Success.TButton', command=guardar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')


    def recargar_catalogo_modelos(self):
        for item in self.tree_modelos.get_children():
            self.tree_modelos.delete(item)
        modelos = database.obtener_catalogo_modelos()
        filtro = getattr(self, 'filtro_mod_tipo', tk.StringVar(value='Todos')).get()
        for m in modelos:
            if filtro != 'Todos' and m['tipo_llanta'].lower() != filtro.lower():
                continue
            self.tree_modelos.insert('', tk.END, values=(
                m['tipo_llanta'],
                m['marca'],
                m['diseno'],
                m['dimension'],
                f"{m['prof_inicial']} mm",
                m.get('descripcion', '')
            ))

    
    def recargar_configuraciones_clientes(self):
        for item in self.tree_clientes_lim.get_children():
            self.tree_clientes_lim.delete(item)
        configs = database.obtener_todas_configuraciones_clientes()
        # Obtener todos los clientes que existen en la BD
        todos_clientes = database.obtener_lista_clientes_unicos()
        clientes_con_cfg = {c['cliente'].lower(): c for c in configs}

        # Mostrar los que tienen configuración expresa
        for c in configs:
            self.tree_clientes_lim.insert('', tk.END, values=(
                c['cliente'],
                f"{c['limite_retiro_mm']} mm",
                c.get('observaciones', ''),
                c.get('fecha_actualizacion', '')
            ))
        
        # Mostrar los que aún están por defecto (3.0 mm)
        for nom in todos_clientes:
            if nom.lower() not in clientes_con_cfg:
                self.tree_clientes_lim.insert('', tk.END, values=(
                    nom,
                    "3.0 mm (Por defecto)",
                    "Estándar inicial de operación",
                    "Automático"
                ))

    def modal_configurar_limite_cliente(self):
        top = tk.Toplevel(self)
        top.title('Configurar Límite de Cambio de Llanta por Cliente')
        top.geometry('450x260')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        f = ttk.Frame(top, padding=16)
        f.pack(fill='both', expand=True)

        ttk.Label(f, text='Cliente / Empresa:*', font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky='w', pady=6)
        var_cli = tk.StringVar()
        clientes_existentes = database.obtener_lista_clientes_unicos()
        cb_c = ttk.Combobox(f, textvariable=var_cli, values=clientes_existentes, font=('Segoe UI', 10), width=24)
        cb_c.grid(row=0, column=1, sticky='w', pady=6)
        if clientes_existentes:
            cb_c.set(clientes_existentes[0])

        ttk.Label(f, text='Límite de Cambio (mm):*', font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky='w', pady=6)
        var_lim = tk.StringVar(value='3.0')
        ttk.Spinbox(f, from_=1.6, to=8.0, increment=0.5, textvariable=var_lim, width=10, font=('Segoe UI', 10)).grid(row=1, column=1, sticky='w', pady=6)

        ttk.Label(f, text='Observaciones / Política:').grid(row=2, column=0, sticky='w', pady=6)
        var_obs = tk.StringVar(value='Política de retiro de flota')
        ttk.Entry(f, textvariable=var_obs, width=26, font=('Segoe UI', 10)).grid(row=2, column=1, sticky='w', pady=6)

        def guardar():
            cli = var_cli.get().strip()
            if not cli:
                messagebox.showwarning('Atención', 'Selecciona o escribe el nombre del cliente.')
                return
            try:
                lim = float(var_lim.get())
            except ValueError:
                lim = 3.0
            database.guardar_limite_retiro_cliente(cli, lim, var_obs.get().strip())
            self.recargar_configuraciones_clientes()
            self.ejecutar_analisis()
            self.recargar_tabla_kpis()
            top.destroy()
            messagebox.showinfo('Éxito', f'Límite de cambio para el cliente "{cli}" fijado en {lim} mm.')

        btn_box = ttk.Frame(f)
        btn_box.grid(row=3, column=0, columnspan=2, pady=16)
        ttk.Button(btn_box, text='Guardar Configuración', style='Primary.TButton', command=guardar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def modal_editar_operacion(self):
        sel = self.listbox_ops.curselection()
        if not sel:
            messagebox.showwarning('Atención', 'Selecciona una operación de la lista para editar.')
            return
        item_txt = self.listbox_ops.get(sel[0]).replace('  •  ', '').strip()
        top = tk.Toplevel(self)
        top.title('Editar Tipo de Operación')
        top.geometry('380x180')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text=f'Nuevo Nombre para "{item_txt}":', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(16, 4))
        var_nom = tk.StringVar(value=item_txt)
        ent = ttk.Entry(top, textvariable=var_nom, width=32, font=('Segoe UI', 10))
        ent.pack(padx=18, pady=4, fill='x')
        ent.focus()

        def guardar():
            nom = var_nom.get().strip()
            if not nom:
                messagebox.showwarning('Atención', 'Ingresa el nombre.')
                return
            database.actualizar_operacion(item_txt, nom)
            self.recargar_listas_catalogos()
            top.destroy()
            messagebox.showinfo('Éxito', 'Operación actualizada correctamente.')

        btn_box = ttk.Frame(top)
        btn_box.pack(pady=16)
        ttk.Button(btn_box, text='Guardar Cambios', style='Primary.TButton', command=guardar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def eliminar_operacion_seleccionada(self):
        sel = self.listbox_ops.curselection()
        if not sel:
            messagebox.showwarning('Atención', 'Selecciona una operación para eliminar.')
            return
        nom = self.listbox_ops.get(sel[0]).replace('  •  ', '').strip()
        if messagebox.askyesno('Confirmar', f'¿Eliminar la operación "{nom}"?'):
            database.eliminar_operacion(nom)
            self.recargar_listas_catalogos()

    def modal_editar_tipologia(self):
        sel = self.tree_tips.selection()
        if not sel:
            messagebox.showwarning('Atención', 'Selecciona una tipología para editar.')
            return
        vals = self.tree_tips.item(sel[0])['values']
        nom_orig, cant_orig, desc_orig = str(vals[0]), str(vals[1]), str(vals[2])

        top = tk.Toplevel(self)
        top.title('Editar Tipología de Vehículo')
        top.geometry('440x330')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text='Nombre de Tipología:*', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(10, 2))
        var_nom = tk.StringVar(value=nom_orig)
        ttk.Entry(top, textvariable=var_nom, font=('Segoe UI', 10)).pack(padx=18, fill='x')

        ttk.Label(top, text='Descripción / Observaciones:', font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=(6, 2))
        var_desc = tk.StringVar(value=desc_orig)
        ttk.Entry(top, textvariable=var_desc, font=('Segoe UI', 10)).pack(padx=18, fill='x')

        f_mid = ttk.Frame(top)
        f_mid.pack(fill='x', padx=18, pady=(6, 2))

        ttk.Label(f_mid, text='Cantidad de Llantas:*', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 8))
        var_cant = tk.StringVar(value=cant_orig)
        ttk.Spinbox(f_mid, from_=2, to=36, textvariable=var_cant, width=8, font=('Segoe UI', 10)).pack(side='left')

        ttk.Label(top, text='Configuración / Esquema de Ejes:*', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(6, 2))
        var_cfg_ejes = tk.StringVar(value='Mantener Esquema Actual')
        opciones_ejes = [
            'Mantener Esquema Actual',
            'Articulado (1 Dir + 1 Tracción Dual + 1 Libre Dual - 10 llantas)',
            'Biarticulado (1 Dir + 1 Tracción Dual + 2 Libres Duales - 14 llantas)',
            'Camión 2 Ejes (1 Dir + 1 Tracción Dual - 6 llantas)',
            'Cabezote 6x4 (1 Dir + 2 Tracción Dual - 10 llantas)',
            'Cuatro Manos (2 Dir + 2 Tracción Dual - 12 llantas)',
            'Trailer 3 Ejes (3 Ejes Arrastre Duales - 12 llantas)',
            'Personalizado (ej: dir,trac,libre,libre)'
        ]
        cb_cfg = ttk.Combobox(top, textvariable=var_cfg_ejes, values=opciones_ejes, state='readonly', font=('Segoe UI', 9))
        cb_cfg.pack(padx=18, fill='x')

        var_custom = tk.StringVar()
        ent_custom = ttk.Entry(top, textvariable=var_custom, font=('Segoe UI', 9))

        def on_eje_change_edit(*args):
            v = var_cfg_ejes.get()
            if 'Articulado (' in v:
                var_cant.set('10')
                ent_custom.pack_forget()
            elif 'Biarticulado (' in v:
                var_cant.set('14')
                ent_custom.pack_forget()
            elif 'Camión 2 Ejes' in v:
                var_cant.set('6')
                ent_custom.pack_forget()
            elif 'Cabezote 6x4' in v:
                var_cant.set('10')
                ent_custom.pack_forget()
            elif 'Cuatro Manos' in v:
                var_cant.set('12')
                ent_custom.pack_forget()
            elif 'Trailer 3 Ejes' in v:
                var_cant.set('12')
                ent_custom.pack_forget()
            elif 'Personalizado' in v:
                ent_custom.pack(padx=18, fill='x', pady=4)
                ent_custom.focus()
            else:
                ent_custom.pack_forget()

        cb_cfg.bind('<<ComboboxSelected>>', on_eje_change_edit)

        def guardar():
            nom = var_nom.get().strip()
            if not nom:
                messagebox.showwarning('Atención', 'Ingresa el nombre.')
                return
            try:
                c = int(var_cant.get())
            except ValueError:
                c = 10

            v = var_cfg_ejes.get()
            cfg_code = None
            if 'Articulado (' in v: cfg_code = 'dir,trac,libre'
            elif 'Biarticulado (' in v: cfg_code = 'dir,trac,libre,libre'
            elif 'Camión 2 Ejes' in v: cfg_code = 'dir,trac'
            elif 'Cabezote 6x4' in v: cfg_code = 'dir,trac,trac'
            elif 'Cuatro Manos' in v: cfg_code = 'dir,dir,trac,trac'
            elif 'Trailer 3 Ejes' in v: cfg_code = 'remolque,remolque,remolque'
            elif 'Personalizado' in v: cfg_code = var_custom.get().strip()

            database.actualizar_tipologia(nom_orig, nom, var_desc.get().strip(), c, config_ejes=cfg_code)
            self.recargar_listas_catalogos()
            self.on_cambio_tipologia_pc()
            top.destroy()
            messagebox.showinfo('Éxito', 'Tipología actualizada.')

        btn_box = ttk.Frame(top)
        btn_box.pack(pady=14)
        ttk.Button(btn_box, text='Guardar Cambios', style='Primary.TButton', command=guardar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def eliminar_tipologia_seleccionada(self):
        sel = self.tree_tips.selection()
        if not sel:
            messagebox.showwarning('Atención', 'Selecciona una tipología para eliminar.')
            return
        nom = str(self.tree_tips.item(sel[0])['values'][0])
        if messagebox.askyesno('Confirmar', f'¿Eliminar la tipología "{nom}"?'):
            database.eliminar_tipologia(nom)
            self.recargar_listas_catalogos()

    def modal_agregar_modelo_llanta(self):
        top = tk.Toplevel(self)
        top.title('Agregar Modelo al Catálogo de Llantas')
        top.geometry('440x330')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        f = ttk.Frame(top, padding=16)
        f.pack(fill='both', expand=True)

        ttk.Label(f, text='Tipo:').grid(row=0, column=0, sticky='w', pady=4)
        var_tipo = tk.StringVar(value='Nueva')
        cb_t = ttk.Combobox(f, textvariable=var_tipo, values=['Nueva', 'Reencauche'], state='readonly', width=18)
        cb_t.grid(row=0, column=1, sticky='w', pady=4)

        ttk.Label(f, text='Marca:*').grid(row=1, column=0, sticky='w', pady=4)
        var_m = tk.StringVar()
        ttk.Entry(f, textvariable=var_m, width=22).grid(row=1, column=1, sticky='w', pady=4)

        ttk.Label(f, text='Diseño / Banda:*').grid(row=2, column=0, sticky='w', pady=4)
        var_d = tk.StringVar()
        ttk.Entry(f, textvariable=var_d, width=22).grid(row=2, column=1, sticky='w', pady=4)

        ttk.Label(f, text='Dimensión:').grid(row=3, column=0, sticky='w', pady=4)
        var_dim = tk.StringVar(value='295/80R22.5')
        ttk.Entry(f, textvariable=var_dim, width=22).grid(row=3, column=1, sticky='w', pady=4)

        ttk.Label(f, text='Prof. Inicial (mm):*').grid(row=4, column=0, sticky='w', pady=4)
        var_prof = tk.StringVar(value='15.0')
        ttk.Entry(f, textvariable=var_prof, width=12).grid(row=4, column=1, sticky='w', pady=4)

        ttk.Label(f, text='Descripción / Posición:').grid(row=5, column=0, sticky='w', pady=4)
        var_desc = tk.StringVar()
        ttk.Entry(f, textvariable=var_desc, width=25).grid(row=5, column=1, sticky='w', pady=4)

        def guardar():
            m = var_m.get().strip()
            d = var_d.get().strip()
            if not m or not d:
                messagebox.showwarning('Atención', 'Marca y Diseño son obligatorios.')
                return
            try:
                prof = float(var_prof.get())
            except ValueError:
                prof = 15.0
            database.guardar_modelo_llanta(var_tipo.get(), m, d, var_dim.get().strip(), prof, var_desc.get().strip())
            self.recargar_catalogo_modelos()
            top.destroy()
            messagebox.showinfo('Éxito', f'Modelo "{m} {d}" ({prof} mm) agregado al catálogo.')

        btn_box = ttk.Frame(f)
        btn_box.grid(row=6, column=0, columnspan=2, pady=16)
        ttk.Button(btn_box, text='Guardar Modelo', style='Primary.TButton', command=guardar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def crear_tab_kpis(self, parent):
        # Barra de Búsqueda rápida y Acciones
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill='x', pady=(0, 6))

        ttk.Label(top_bar, text='No. Interno Llanta:', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 4))
        self.buscar_kpi_var = tk.StringVar()
        self.buscar_kpi_var.trace_add('write', lambda *args: self.recargar_tabla_kpis())
        ttk.Entry(top_bar, textvariable=self.buscar_kpi_var, width=14).pack(side='left', padx=(0, 10))

        ttk.Button(top_bar, text='Actualizar Indicadores', style='Primary.TButton', command=self.recargar_tabla_kpis).pack(side='left', padx=(0, 8))
        ttk.Button(top_bar, text='Limpiar Filtros', command=self.limpiar_filtros_kpis).pack(side='left', padx=(0, 8))
        ttk.Button(top_bar, text='Exportar KPIs a Excel', style='Success.TButton', command=self.exportar_kpis_excel).pack(side='left')

        # Barra de Filtros Avanzados (Cliente, Subcliente, Operación, Marca, Diseño, Dimensión, Vida, Banda)
        f_filtros = ttk.LabelFrame(parent, text='Filtros Avanzados de Flota y Llantas', padding=6)
        f_filtros.pack(fill='x', pady=(0, 8))

        self.kpi_filtros_vars = {
            'cliente': tk.StringVar(value='TODOS'),
            'subcliente': tk.StringVar(value='TODOS'),
            'tipo_operacion': tk.StringVar(value='TODOS'),
            'marca': tk.StringVar(value='TODOS'),
            'diseno': tk.StringVar(value='TODOS'),
            'dimension': tk.StringVar(value='TODOS'),
            'vida': tk.StringVar(value='TODOS'),
            'banda_reen': tk.StringVar(value='TODOS'),
            'usuario': tk.StringVar(value='TODOS')
        }

        # Fila 1 de Filtros
        row1 = ttk.Frame(f_filtros)
        row1.pack(fill='x', pady=2)

        ttk.Label(row1, text='Cliente:').pack(side='left', padx=(4, 2))
        self.cb_kpi_cli = ttk.Combobox(row1, textvariable=self.kpi_filtros_vars['cliente'], width=15, state='readonly')
        self.cb_kpi_cli.pack(side='left', padx=(0, 8))
        self.cb_kpi_cli.bind('<<ComboboxSelected>>', self.al_cambiar_cliente_kpi)

        ttk.Label(row1, text='Subcliente:').pack(side='left', padx=(4, 2))
        self.cb_kpi_sub = ttk.Combobox(row1, textvariable=self.kpi_filtros_vars['subcliente'], width=15, state='readonly')
        self.cb_kpi_sub.pack(side='left', padx=(0, 8))
        self.cb_kpi_sub.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        ttk.Label(row1, text='Operación:').pack(side='left', padx=(4, 2))
        self.cb_kpi_op = ttk.Combobox(row1, textvariable=self.kpi_filtros_vars['tipo_operacion'], width=15, state='readonly')
        self.cb_kpi_op.pack(side='left', padx=(0, 8))
        self.cb_kpi_op.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        ttk.Label(row1, text='Marca:').pack(side='left', padx=(4, 2))
        self.cb_kpi_marca = ttk.Combobox(row1, textvariable=self.kpi_filtros_vars['marca'], width=14, state='readonly')
        self.cb_kpi_marca.pack(side='left', padx=(0, 8))
        self.cb_kpi_marca.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        # Fila 2 de Filtros
        row2 = ttk.Frame(f_filtros)
        row2.pack(fill='x', pady=2)

        ttk.Label(row2, text='Diseño:').pack(side='left', padx=(4, 2))
        self.cb_kpi_dis = ttk.Combobox(row2, textvariable=self.kpi_filtros_vars['diseno'], width=15, state='readonly')
        self.cb_kpi_dis.pack(side='left', padx=(0, 8))
        self.cb_kpi_dis.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        ttk.Label(row2, text='Dimensión:').pack(side='left', padx=(4, 2))
        self.cb_kpi_dim = ttk.Combobox(row2, textvariable=self.kpi_filtros_vars['dimension'], width=15, state='readonly')
        self.cb_kpi_dim.pack(side='left', padx=(0, 8))
        self.cb_kpi_dim.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        ttk.Label(row2, text='Vida:').pack(side='left', padx=(4, 2))
        self.cb_kpi_vida = ttk.Combobox(row2, textvariable=self.kpi_filtros_vars['vida'], values=['TODOS', 'Original', 'Reencauche'], width=15, state='readonly')
        self.cb_kpi_vida.pack(side='left', padx=(0, 8))
        self.cb_kpi_vida.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        ttk.Label(row2, text='Banda:').pack(side='left', padx=(4, 2))
        self.cb_kpi_banda = ttk.Combobox(row2, textvariable=self.kpi_filtros_vars['banda_reen'], width=12, state='readonly')
        self.cb_kpi_banda.pack(side='left', padx=(0, 8))
        self.cb_kpi_banda.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        ttk.Label(row2, text='Usuario/Inspector:', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(4, 2))
        self.cb_kpi_user = ttk.Combobox(row2, textvariable=self.kpi_filtros_vars['usuario'], width=14, state='readonly')
        self.cb_kpi_user.pack(side='left', padx=(0, 8))
        self.cb_kpi_user.bind('<<ComboboxSelected>>', lambda e: self.recargar_tabla_kpis())

        # Tarjetas de resumen KPI
        kpi_resumen = ttk.Frame(parent)
        kpi_resumen.pack(fill='x', pady=(0, 8))
        self.card_kpi_total = self.crear_tarjeta(kpi_resumen, 'LLANTAS FILTRADAS', '0', 0)
        self.card_kpi_km_prom = self.crear_tarjeta(kpi_resumen, 'PROM. KM/MM RENDIMIENTO', '0', 1, color_val='#2563eb')
        self.card_kpi_cpk_prom = self.crear_tarjeta(kpi_resumen, 'PROM. CPK ($/KM)', '$0.00', 2, color_val='#059669')
        self.card_kpi_proy_prom = self.crear_tarjeta(kpi_resumen, 'PROY. VIDA PROMEDIO', '0 km', 3, color_val='#7c3aed')

        cols_kpi = (
            'No. Interno', 'Placa', 'Pos', 'Marca/Diseño', 'Dimensión', 'Vida', 'Banda',
            'Prof Ini', 'Prof Actual', 'Límite Retiro', 'Sugerir Cambio',
            'Desgaste (mm)', '% Desgaste', 'Km Rodados', 'Km / mm', 'Precio ($)', 'CPK ($/km)', 'Proy. Total Km', 'CPK Proy. ($/km)', 'Km Restantes'
        )
        tree_kpi_frame = ttk.Frame(parent)
        tree_kpi_frame.pack(fill='both', expand=True)

        self.tree_kpis = ttk.Treeview(tree_kpi_frame, columns=cols_kpi, show='headings', selectmode='browse')
        for c in cols_kpi:
            self.tree_kpis.heading(c, text=c)
            w = 85
            if c in ('Marca/Diseño',): w = 130
            elif c in ('No. Interno', 'Placa', 'Pos'): w = 65
            elif c in ('Proy. Total Km', 'Km Restantes', 'Km Rodados', 'CPK Proy. ($/km)'): w = 100
            elif c in ('% Desgaste', 'Dimensión', 'Banda'): w = 85
            self.tree_kpis.column(c, width=w, anchor='center' if c not in ('Marca/Diseño',) else 'w')

        sb_ky = ttk.Scrollbar(tree_kpi_frame, orient='vertical', command=self.tree_kpis.yview)
        sb_kx = ttk.Scrollbar(tree_kpi_frame, orient='horizontal', command=self.tree_kpis.xview)
        self.tree_kpis.configure(yscrollcommand=sb_ky.set, xscrollcommand=sb_kx.set)
        sb_ky.pack(side='right', fill='y')
        sb_kx.pack(side='bottom', fill='x')
        self.tree_kpis.pack(side='left', fill='both', expand=True)

        self.actualizar_combos_filtros_kpis()

    def actualizar_combos_filtros_kpis(self):
        if not hasattr(self, 'cb_kpi_cli'):
            return
        clis = ['TODOS'] + database.obtener_valores_unicos_campo('cliente')
        ops = ['TODOS'] + database.obtener_todas_operaciones()
        marcas = ['TODOS'] + database.obtener_valores_unicos_campo('marca')
        disenos = ['TODOS'] + database.obtener_valores_unicos_campo('diseno')
        dims = ['TODOS'] + database.obtener_valores_unicos_campo('dimension')
        bandas = ['TODOS'] + database.obtener_valores_unicos_campo('banda_reen')
        usrs_bd = [u['username'] for u in database.listar_usuarios()]
        usuarios = ['TODOS'] + usrs_bd

        self.cb_kpi_cli.config(values=clis)
        self.cb_kpi_op.config(values=ops)
        self.cb_kpi_marca.config(values=marcas)
        self.cb_kpi_dis.config(values=disenos)
        self.cb_kpi_dim.config(values=dims)
        self.cb_kpi_banda.config(values=bandas)
        if hasattr(self, 'cb_kpi_user'):
            self.cb_kpi_user.config(values=usuarios)
        self.al_cambiar_cliente_kpi()

    def modal_generar_pdf_vehiculo(self):
        sel = self.tree_analisis.selection()
        placa_default = ''
        if sel:
            placa_default = str(self.tree_analisis.item(sel[0])['values'][0]).split(' ')[0]

        top = tk.Toplevel(self)
        top.title('Generar Plan de Mantenimiento en PDF')
        top.geometry('420x240')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text='Generación de Plan de Mantenimiento (PDF)', font=('Segoe UI', 11, 'bold'), foreground='#1e3a8a').pack(anchor='w', padx=18, pady=(16, 4))
        ttk.Label(top, text='Selecciona o escribe la placa del vehículo inspeccionado:', font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=(0, 10))

        f_in = ttk.Frame(top)
        f_in.pack(fill='x', padx=18, pady=4)
        ttk.Label(f_in, text='Placa:*', font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 6))
        var_placa = tk.StringVar(value=placa_default)
        ent_p = ttk.Entry(f_in, textvariable=var_placa, font=('Segoe UI', 10, 'bold'), width=14)
        ent_p.pack(side='left')

        def generar():
            p = var_placa.get().strip().upper()
            if not p:
                messagebox.showwarning('Atención', 'Por favor ingresa la placa.')
                return
            try:
                import pdf_generator
                pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento(p)
                f_str = datetime.now().strftime('%Y%m%d')
                ruta = filedialog.asksaveasfilename(
                    defaultextension='.pdf',
                    filetypes=[('Documento PDF', '*.pdf')],
                    initialfile=f'Plan_Mantenimiento_{p}_{f_str}.pdf'
                )
                if not ruta:
                    return
                with open(ruta, 'wb') as f:
                    f.write(pdf_bytes)
                top.destroy()
                messagebox.showinfo('Éxito', f'Plan de Mantenimiento PDF generado con éxito en:\n{ruta}\n\nListo para entregar al cliente o enviar por WhatsApp.')
            except Exception as e:
                messagebox.showerror('Error', str(e))

        btn_box = ttk.Frame(top)
        btn_box.pack(pady=18)
        ttk.Button(btn_box, text='Generar y Guardar PDF', style='Primary.TButton', command=generar).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def modal_generar_pdf_consolidado(self):
        top = tk.Toplevel(self)
        top.title('Generar Informe Consolidado de Flota (PDF)')
        top.geometry('420x240')
        top.resizable(False, False)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text='Generar Informe Ejecutivo Consolidado', font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=18, pady=(16, 4))
        ttk.Label(top, text='Genera un reporte con todas las placas inspeccionadas, gráficos,\nresumen de alertas prioritarias y semáforo de estado de llantas.', font=('Segoe UI', 8), foreground='#64748b').pack(anchor='w', padx=18, pady=(0, 10))

        cli_actual = self.filtro_cliente_var.get()
        sub_actual = self.filtro_subcliente_var.get()

        ttk.Label(top, text=f'Cliente Seleccionado: {cli_actual}', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=2)
        ttk.Label(top, text=f'Sede / Operación: {sub_actual}', font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=2)

        def generar_consolidado():
            try:
                import pdf_generator
                cli = None if cli_actual == 'Todos' else cli_actual
                sub = None if sub_actual == 'Todos' else sub_actual
                pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada(cliente=cli, subcliente=sub)
                
                c_tag = (cli or 'Flota_General').replace(' ', '_')
                f_str = datetime.now().strftime('%Y%m%d')
                ruta = filedialog.asksaveasfilename(
                    defaultextension='.pdf',
                    filetypes=[('Documento PDF', '*.pdf')],
                    initialfile=f'Consolidado_Flota_{c_tag}_{f_str}.pdf'
                )
                if not ruta:
                    return
                with open(ruta, 'wb') as f:
                    f.write(pdf_bytes)
                top.destroy()
                messagebox.showinfo('Éxito', f'Informe Consolidado de Flota generado con éxito en:\n{ruta}\n\nListo para presentar a la gerencia o enviar al cliente.')
            except Exception as e:
                messagebox.showerror('Error', str(e))

        btn_box = ttk.Frame(top)
        btn_box.pack(pady=18)
        ttk.Button(btn_box, text='📊 Generar Consolidado PDF', style='Success.TButton', command=generar_consolidado).pack(side='left', padx=6)
        ttk.Button(btn_box, text='Cancelar', command=top.destroy).pack(side='left')

    def al_cambiar_cliente_kpi(self, event=None):
        cli = self.kpi_filtros_vars['cliente'].get().strip()
        if cli and cli != 'TODOS':
            subs = ['TODOS'] + database.obtener_valores_unicos_campo('subcliente', cli)
        else:
            subs = ['TODOS'] + database.obtener_valores_unicos_campo('subcliente')
        self.cb_kpi_sub.config(values=subs)
        if self.kpi_filtros_vars['subcliente'].get() not in subs:
            self.kpi_filtros_vars['subcliente'].set('TODOS')
        self.recargar_tabla_kpis()

    def limpiar_filtros_kpis(self):
        self.buscar_kpi_var.set('')
        for k in self.kpi_filtros_vars:
            self.kpi_filtros_vars[k].set('TODOS')
        self.recargar_tabla_kpis()

    def obtener_filtros_kpi_activos(self):
        filtros = {}
        for k, v in getattr(self, 'kpi_filtros_vars', {}).items():
            val = v.get().strip()
            if val and val != 'TODOS':
                filtros[k] = val
        return filtros

    def recargar_tabla_kpis(self):
        for item in self.tree_kpis.get_children():
            self.tree_kpis.delete(item)
        num_filtro = getattr(self, 'buscar_kpi_var', tk.StringVar()).get().strip()
        filtros = self.obtener_filtros_kpi_activos()
        data = database.obtener_trazabilidad_kpis_llanta(num_filtro, filtros)
        if not data:
            self.card_kpi_total.config(text='0')
            self.card_kpi_km_prom.config(text='0')
            self.card_kpi_cpk_prom.config(text='$0.00')
            self.card_kpi_proy_prom.config(text='0 km')
            return

        total = len(data)
        km_mms = [d['km_por_mm'] for d in data if d['km_por_mm'] > 0]
        cpks = [d['cpk'] for d in data if d['cpk'] > 0]
        proys = [d['proyeccion_total_km'] for d in data if d['proyeccion_total_km'] > 0]

        prom_kmmm = (sum(km_mms) / len(km_mms)) if km_mms else 0.0
        prom_cpk = (sum(cpks) / len(cpks)) if cpks else 0.0
        prom_proy = (sum(proys) / len(proys)) if proys else 0.0

        self.card_kpi_total.config(text=str(total))
        self.card_kpi_km_prom.config(text=f"{prom_kmmm:,.1f}")
        self.card_kpi_cpk_prom.config(text=f"${prom_cpk:,.4f}")
        self.card_kpi_proy_prom.config(text=f"{prom_proy:,.0f} km")

        for d in data:
            self.tree_kpis.insert('', tk.END, values=(
                d['numero_interno'],
                d['placa'],
                d['posicion'],
                f"{d['marca']} {d['diseno']}",
                d.get('dimension', ''),
                d['vida'],
                d.get('banda_reen', '') or '-',
                f"{d['prof_inicial']} mm",
                f"{d['prof_actual_min']} mm",
                f"{d.get('limite_retiro_mm', 3.0)} mm",
                d.get('requiere_cambio', 'NO'),
                f"{d['desgaste_mm']} mm",
                f"{d.get('porcentaje_desgaste', 0.0):.1f}%",
                f"{d['km_rodados']:,.0f}",
                f"{d['km_por_mm']:,.1f}",
                f"${d['precio']:,.2f}",
                f"${d['cpk']:,.4f}",
                f"{d['proyeccion_total_km']:,.0f}",
                f"${d.get('cpk_proyectado', 0.0):,.4f}",
                f"{d['km_restantes']:,.0f}"
            ))

    def exportar_kpis_excel(self):
        num_filtro = getattr(self, 'buscar_kpi_var', tk.StringVar()).get().strip()
        filtros = self.obtener_filtros_kpi_activos()
        data = database.obtener_trazabilidad_kpis_llanta(num_filtro, filtros)
        if not data:
            messagebox.showwarning('Sin datos', 'No hay datos de KPIs coincidentes con los filtros para exportar.')
            return
        df = pd.DataFrame(data)
        f_str = datetime.now().strftime('%Y%m%d_%H%M')
        ruta = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Libro Excel', '*.xlsx')], initialfile=f'KPIs_Llantas_TireCheck_{f_str}.xlsx')
        if not ruta:
            return
        try:
            df.to_excel(ruta, index=False, sheet_name='Trazabilidad_KPIs')
            messagebox.showinfo('Exportado', f'KPIs exportados exitosamente a:\n' + str(ruta))
        except Exception as e:
            messagebox.showerror('Error', str(e))

if __name__ == '__main__':
    app = AppInspeccionLlantas()
    app.mainloop()
