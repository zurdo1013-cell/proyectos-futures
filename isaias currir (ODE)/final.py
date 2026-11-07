import json
import os
import tkinter as tk
import psycopg2
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

try:
    from plyer import notification
except ImportError:  
    notification = None

BASE = os.path.dirname(os.path.abspath(__file__))

DB_CONFIG = {
    "host": "localhost",
    "port": "5433",
    "database": "organizador",
    "user": "postgres",
    "password": "446544",
}
FORMATO_FECHA = "%d/%m/%Y"


FONDO = "#8FB1DF"
PANEL = "#FFFFFF"
LINEA = "#DBE4F2"
TEXTO = "#0F2347"
SUAVE = "#5B6B88"
CABECERA = "#D3E5FB"
TITULO = "#0B2F6B"
AZUL = "#021B4D"
VERDE = "#034D0F"
ROJO = "#F00D09"
NAV_SEL = "#7AA0D3"
C1, C2, C3, C4 = "#8DAFE6", "#7FDAAB", "#DFC06C", "#A586DD"

FUENTE = ("Segoe UI", 10)
FUENTE_B = ("Segoe UI", 10, "bold")

FILAS = {  
    "Pendiente": ("#FFF6D6", "#ABAD05"),
    "Completada": ("#E1F7EB", "#178800"),
    "Vencida": ("#FDE3E3", "#DD0101"),
}


def parsear_fecha(texto):
    return datetime.strptime(texto, FORMATO_FECHA).date()


def estado_real(m):
    """'Vencida' se calcula al vuelo; en el archivo solo se guarda Pendiente/Completada."""
    if m["estado"] == "Completada":
        return "Completada"
    return "Vencida" if parsear_fecha(m["fecha"]) < date.today() else "Pendiente"


def formatear_nota(nota):
    return f"{nota:g}"


def texto_dias(m):
    if m["estado"] == "Completada":
        return "Completada"
    d = (parsear_fecha(m["fecha"]) - date.today()).days
    if d == 0:
        return "Vence hoy"
    return f"Faltan {d} día(s)" if d > 0 else f"Venció hace {-d} día(s)"


def conectar_db():
    return psycopg2.connect(**DB_CONFIG)


def preparar_bd():
    """Crea la tabla donde se guardan los datos personales de cada materia."""
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registros_estudio (
                    id SERIAL PRIMARY KEY,
                    materia_id INTEGER NOT NULL REFERENCES materias(id),
                    profesor VARCHAR(150) NOT NULL,
                    nota NUMERIC(5,2) NOT NULL CHECK (nota >= 0 AND nota <= 100),
                    fecha_entrega DATE NOT NULL,
                    estado VARCHAR(20) NOT NULL
                        CHECK (estado IN ('Pendiente', 'Completada'))
                )
            """)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def obtener_anios_db():
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, numero, nombre FROM anios ORDER BY numero")
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_catalogo_materias(anio_nombre):
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT m.id, m.nombre
                FROM materias m
                JOIN anios a ON a.id = m.anio_id
                WHERE a.nombre = %s
                ORDER BY m.semestre, m.id
            """, (anio_nombre,))
            return cursor.fetchall()
    finally:
        conexion.close()


def validar_registro(materia, profesor, nota, fecha, estado, anio="Primer año"):
    """Valida los datos que se guardarán para una materia."""
    try:
        nota = float(str(nota).replace(",", "."))
        fecha = parsear_fecha(fecha)
    except (ValueError, TypeError):
        return None
    if not materia or not profesor or not anio:
        return None
    return {
        "anio": anio,
        "materia": materia,
        "profesor": profesor,
        "nota": nota,
        "fecha": fecha.strftime(FORMATO_FECHA),
        "estado": "Completada" if estado == "Completada" else "Pendiente",
    }


def cargar():
    """Lee desde PostgreSQL y devuelve registros con el formato que usa la interfaz."""
    datos = []
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT a.nombre, m.nombre, r.profesor, r.nota,
                       r.fecha_entrega, r.estado
                FROM registros_estudio r
                JOIN materias m ON m.id = r.materia_id
                JOIN anios a ON a.id = m.anio_id
                ORDER BY a.numero, m.semestre, m.nombre
            """)
            for anio, materia, profesor, nota, fecha, estado in cursor.fetchall():
                datos.append({
                    "anio": anio,
                    "materia": materia,
                    "profesor": profesor,
                    "nota": float(nota),
                    "fecha": fecha.strftime(FORMATO_FECHA),
                    "estado": estado,
                })
    finally:
        conexion.close()
    return datos


def guardar(materias):
    """Guarda los registros de la aplicación en PostgreSQL, sin tocar el catálogo."""
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM registros_estudio")
            for registro in materias:
                cursor.execute("""
                    SELECT m.id
                    FROM materias m
                    JOIN anios a ON a.id = m.anio_id
                    WHERE m.nombre = %s AND a.nombre = %s
                    ORDER BY m.id
                    LIMIT 1
                """, (registro["materia"], registro.get("anio", "Primer año")))
                fila = cursor.fetchone()
                if not fila:
                    raise ValueError(
                        f"La materia '{registro['materia']}' no existe en el catálogo "
                        f"del año '{registro.get('anio', 'Primer año')}'."
                    )
                cursor.execute("""
                    INSERT INTO registros_estudio
                        (materia_id, profesor, nota, fecha_entrega, estado)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    fila[0],
                    registro["profesor"],
                    registro["nota"],
                    parsear_fecha(registro["fecha"]),
                    registro["estado"],
                ))
        conexion.commit()
    except Exception as error:
        conexion.rollback()
        messagebox.showerror("Error de PostgreSQL", f"No se pudieron guardar los datos:\n{error}")
    finally:
        conexion.close()



def tarjeta(padre, **kw):
    return tk.Frame(padre, bg=PANEL, highlightbackground=LINEA, highlightthickness=1, **kw)


def boton(padre, texto, comando, color, padx=10):
    return tk.Button(
        padre, text=texto, command=comando, bg=color, fg="white",
        activebackground=color, activeforeground="white", relief="flat", bd=0,
        cursor="hand2", font=FUENTE_B, padx=padx, pady=9,
    )


def entrada(padre):
    return tk.Entry(
        padre, bg="white", fg=TEXTO, insertbackground=TEXTO, relief="flat",
        font=("Segoe UI", 11), highlightthickness=1,
        highlightbackground=LINEA, highlightcolor=AZUL,
    )



class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Organizador de Estudios")
        self.geometry("1150x800")
        self.minsize(1000, 740)
        self.configure(bg=FONDO)

        try:
            preparar_bd()
            self.anios_db = obtener_anios_db()
            self.materias = cargar()
        except Exception as error:
            messagebox.showerror(
                "Error de PostgreSQL",
                "No se pudo conectar a la base de datos. Revisa la contraseña, "
                "el servidor y las tablas anios/materias.\\n\\n" + str(error)
            )
            self.destroy()
            return
        self.avisos = set()
        self.edit_key = None
        self.id_msg = None

        self.estilos()
        self.construir_cabecera()
        self.construir_pie()  
        self.construir_cuerpo()

        if self.anios_db:
            self.c_anio.current(0)
            self.seleccionar_anio()
        self.mostrar("inicio")
        self.ciclo()

    
    def estilos(self):
        e = ttk.Style(self)
        e.theme_use("clam")
        e.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXTO,
                    rowheight=38, font=FUENTE, borderwidth=0)
        e.configure("Treeview.Heading", background="#E4EFFD", foreground=TITULO,
                    font=FUENTE_B, relief="flat", padding=(6, 9))
        e.configure("TCombobox", padding=6)

        def mapa(opcion, seleccion):
            previo = [x for x in e.map("Treeview", query_opt=opcion)
                      if x[:2] != ("!disabled", "!selected")]
            return [("selected", seleccion)] + previo

        e.map("Treeview", foreground=mapa("foreground", TEXTO),
              background=mapa("background", NAV_SEL))

   
    def construir_cabecera(self):
        h = tk.Frame(self, bg=CABECERA)
        h.pack(fill="x")
        tk.Label(h, text="🎓", font=("Segoe UI Emoji", 32), bg=CABECERA).pack(
            side="left", padx=(40, 10), pady=8)
        tk.Label(h, text="Pequeños avances,\ngrandes logros", font=("Segoe Script", 12, "italic"),
                 fg=AZUL, bg=CABECERA, justify="center").pack(side="right", padx=40)
        centro = tk.Frame(h, bg=CABECERA)
        centro.pack(expand=True)
        tk.Label(centro, text="Organizador de Estudios", font=("Segoe UI", 26, "bold"),
                 fg=TITULO, bg=CABECERA).pack()
        tk.Label(centro, text="Organizador tus materias, controla tus notas y cumple tus metas",
                 font=("Segoe UI", 11), fg=TITULO, bg=CABECERA).pack()

    def construir_pie(self):
        p = tk.Frame(self, bg="#F5F9FF", highlightbackground=LINEA, highlightthickness=1)
        p.pack(side="bottom", fill="x")
        tk.Label(p, text="●", fg=VERDE, bg="#F5F9FF").pack(side="left", padx=(14, 4), pady=6)
        tk.Label(p, text="Todo en orden  •  Organizador de Estudios v1.0", fg=SUAVE,
                 bg="#F5F9FF", font=("Segoe UI", 9)).pack(side="left")
        self.lbl_hora = tk.Label(p, text="", fg=SUAVE, bg="#F5F9FF", font=("Segoe UI", 9))
        self.lbl_hora.pack(side="right", padx=14)
        tk.Label(p, text="🕒", bg="#F5F9FF").pack(side="right")


    def construir_cuerpo(self):
        cuerpo = tk.Frame(self, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=14, pady=12)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

      
        lado = tarjeta(cuerpo, width=200)
        lado.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        lado.pack_propagate(False)
        self.nav = {}
        for clave, texto in [("inicio", "🏠   Inicio"), ("materias", "📖   Materias"),
                             ("calendario", "📅   Calendario"), ("config", "⚙️   Configuración")]:
            b = tk.Button(lado, text=texto, anchor="w", relief="flat", bd=0, cursor="hand2",
                          font=("Segoe UI", 11), bg=PANEL, fg=TEXTO, activebackground=NAV_SEL,
                          padx=14, pady=11, command=lambda c=clave: self.mostrar(c))
            b.pack(fill="x", padx=8, pady=(8 if clave == "inicio" else 2, 2))
            self.nav[clave] = b
        promo = tk.Frame(lado, bg=C1)
        promo.pack(side="bottom", fill="x", padx=10, pady=12)
        tk.Label(promo, text="🎯", font=("Segoe UI Emoji", 22), bg=C1).pack(pady=(14, 4))
        tk.Label(promo, text="Tu esfuerzo\nhoy, es tu éxito\nmañana.", bg=C1, fg=TEXTO,
                 font=FUENTE).pack(pady=(0, 16))

        
        cont = tk.Frame(cuerpo, bg=FONDO)
        cont.grid(row=0, column=1, sticky="nsew")
        cont.rowconfigure(0, weight=1)
        cont.columnconfigure(0, weight=1)

        self.v_inicio = tk.Frame(cont, bg=FONDO)
        self.v_cal = tk.Frame(cont, bg=FONDO)
        self.v_cfg = tk.Frame(cont, bg=FONDO)
        for v in (self.v_inicio, self.v_cal, self.v_cfg):
            v.grid(row=0, column=0, sticky="nsew")

        self.construir_inicio()
        self.construir_calendario()
        self.construir_config()

    def construir_inicio(self):
        v = self.v_inicio
        v.columnconfigure(1, weight=1)
        v.rowconfigure(0, weight=1)

        
        self.card_form = c = tarjeta(v)
        c.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        
       
        self.card_form = tarjeta(v)
        self.card_form.grid(row=0, column=0, sticky="ns", padx=(0, 12))

       
        canvas = tk.Canvas(
        self.card_form,
        bg=PANEL,
        highlightthickness=0,
        width=340
)

        barra_vertical = ttk.Scrollbar(
        self.card_form,
        orient="vertical",
        command=canvas.yview
)

        canvas.configure(yscrollcommand=barra_vertical.set)

        barra_vertical.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

    
        c   = tk.Frame(canvas, bg=PANEL)

        ventana_formulario = canvas.create_window(
        (0, 0),
        window=c,
        anchor="nw"
)

    
        def actualizar_scroll(event):
         canvas.configure(scrollregion=canvas.bbox("all"))

        c.bind("<Configure>", actualizar_scroll)

        canvas.bind(
        "<Configure>",
        lambda event: canvas.itemconfigure(
        ventana_formulario,
        width=event.width
    )
)

        tk.Frame(c, width=340, height=1, bg=PANEL).pack()  

        fila = tk.Frame(c, bg=PANEL)
        fila.pack(fill="x", padx=20, pady=(12, 2))
        lienzo = tk.Canvas(fila, width=36, height=36, bg=PANEL, highlightthickness=0)
        lienzo.create_oval(2, 2, 34, 34, fill=AZUL, outline=AZUL)
        lienzo.create_text(18, 17, text="+", fill="white", font=("Segoe UI", 17, "bold"))
        lienzo.pack(side="left")
        self.lbl_form = tk.Label(fila, text="Registrar / Editar Materia", bg=PANEL, fg=TEXTO,
                                 font=("Segoe UI", 13, "bold"))
        self.lbl_form.pack(side="left", padx=10)

        tk.Label(c, text="Año de la carrera:", bg=PANEL, fg=TEXTO,
                 font=FUENTE_B, anchor="w").pack(fill="x", padx=20, pady=(7, 2))
        self.c_anio = ttk.Combobox(
            c, values=[a[2] for a in self.anios_db], state="readonly",
            font=("Segoe UI", 11)
        )
        self.c_anio.pack(fill="x", padx=20)
        self.c_anio.bind("<<ComboboxSelected>>", self.seleccionar_anio)

        tk.Label(c, text="Materia:", bg=PANEL, fg=TEXTO,
                 font=FUENTE_B, anchor="w").pack(fill="x", padx=20, pady=(7, 2))
        self.e_materia = ttk.Combobox(c, values=[], state="readonly",
                                      font=("Segoe UI", 11))
        self.e_materia.pack(fill="x", padx=20)

        for texto, attr in [("Profesor:", "e_profesor"),
                            ("Nota:", "e_nota"),
                            ("Fecha de entrega:", "e_fecha")]:
            tk.Label(c, text=texto, bg=PANEL, fg=TEXTO, font=FUENTE_B, anchor="w").pack(
                fill="x", padx=20, pady=(7, 2))
            e = entrada(c)
            e.pack(fill="x", padx=20, ipady=4)
            e.bind("<Return>", lambda ev: self.registrar())
            setattr(self, attr, e)

        tk.Label(c, text="Estado:", bg=PANEL, fg=TEXTO, font=FUENTE_B, anchor="w").pack(
            fill="x", padx=20, pady=(7, 2))
        self.c_estado = ttk.Combobox(c, values=["Pendiente", "Completada"], state="readonly",
                                     font=("Segoe UI", 11))
        self.c_estado.set("Pendiente")
        self.c_estado.pack(fill="x", padx=20)

        f = tk.Frame(c, bg=PANEL)
        f.pack(fill="x", padx=20, pady=(14, 4))
        for i in range(2):
            f.columnconfigure(i, weight=1, uniform="b")
        self.b_reg = boton(f, "💾 Registrar", self.registrar, AZUL, padx=4)
        self.b_reg.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        boton(f, "✏️ Editar", self.editar_seleccionada, "#E28A07", padx=4).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        boton(f, "🧹 Limpiar", self.limpiar_form, VERDE, padx=4).grid(
            row=1, column=0, sticky="ew", padx=(0, 4))
        boton(f, "🗑 Eliminar", self.eliminar_actual, ROJO, padx=4).grid(
            row=1, column=1, sticky="ew", padx=(4, 0))

        self.lbl_msg = tk.Label(c, text="", bg=PANEL, font=FUENTE_B, wraplength=300, justify="left")
        self.lbl_msg.pack(fill="x", padx=20, pady=(4, 8))

       
        t = tarjeta(v)
        t.grid(row=0, column=1, sticky="nsew")
        barra = tk.Frame(t, bg="white", highlightthickness=1, highlightbackground=LINEA)
        barra.pack(fill="x", padx=16, pady=(16, 10))
        tk.Label(barra, text="🔍  Buscar materia o profesor:", bg="white", fg=SUAVE,
                 font=FUENTE).pack(side="left", padx=(10, 6))
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *a: self.actualizar())
        tk.Entry(barra, textvariable=self.q, relief="flat", bd=0, bg="white", fg=TEXTO,
                 font=("Segoe UI", 11)).pack(side="left", fill="x", expand=True, ipady=8)

        marco = tk.Frame(t, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        cols = ("materia", "profesor", "nota", "fecha", "estado", "ed", "el")
        self.tabla = ttk.Treeview(marco, columns=cols, show="headings", selectmode="browse")
        for col, texto, ancho, ancla in [
            ("materia", "Materia", 150, "w"), ("profesor", "Profesor", 130, "w"),
            ("nota", "Nota", 60, "center"), ("fecha", "Fecha entrega", 110, "center"),
            ("estado", "Estado", 110, "center"), ("ed", "", 46, "center"), ("el", "", 46, "center")]:
            self.tabla.heading(col, text=texto)
            self.tabla.column(col, width=ancho, anchor=ancla, stretch=col in ("materia", "profesor"))
        for nombre, (bg, fg) in FILAS.items():
            self.tabla.tag_configure(nombre, background=bg, foreground=fg)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=sb.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tabla.bind("<Button-1>", self.clic_tabla)
        self.tabla.bind("<Motion>", self.mover_tabla)

       
        r = tarjeta(v)
        r.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for i in range(4):
            r.columnconfigure(i, weight=1, uniform="s")
        self.stats = []
        for i, (bg, emoji) in enumerate([(C1, "📖"), (C2, "✅"), (C3, "⏳"), (C4, "📅")]):
            f = tk.Frame(r, bg=bg)
            f.grid(row=0, column=i, sticky="nsew", padx=8, pady=8)
            tk.Label(f, text=emoji, font=("Segoe UI Emoji", 24), bg=bg).pack(side="left", padx=14, pady=6)
            w = tk.Frame(f, bg=bg)
            w.pack(side="left", pady=8)
            n = tk.Label(w, text="0", font=("Segoe UI", 18, "bold"), bg=bg, fg=TEXTO, anchor="w")
            n.pack(anchor="w")
            s = tk.Label(w, text="", font=("Segoe UI", 9), bg=bg, fg=SUAVE, anchor="w")
            s.pack(anchor="w")
            self.stats.append((n, s))

    def seleccionar_anio(self, evento=None):
        anio = self.c_anio.get()
        try:
            materias = obtener_catalogo_materias(anio)
            self.catalogo_materias = {nombre: materia_id for materia_id, nombre in materias}
            self.e_materia["values"] = list(self.catalogo_materias.keys())
            self.e_materia.set("")
        except Exception as error:
            self.e_materia["values"] = []
            self.e_materia.set("")
            self.msg(f"No se pudieron cargar las materias: {error}", True)

    def construir_calendario(self):
        c = tarjeta(self.v_cal)
        c.pack(fill="both", expand=True)
        tk.Label(c, text="📅  Próximas entregas", bg=PANEL, fg=TEXTO,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=(18, 10))
        self.t_cal = ttk.Treeview(c, columns=("fecha", "materia", "situacion"),
                                  show="headings", selectmode="none")
        for col, texto, ancho in [("fecha", "Fecha", 120), ("materia", "Materia", 260),
                                  ("situacion", "Situación", 200)]:
            self.t_cal.heading(col, text=texto)
            self.t_cal.column(col, width=ancho, anchor="w")
        for nombre, (bg, fg) in FILAS.items():
            self.t_cal.tag_configure(nombre, background=bg, foreground=fg)
        self.t_cal.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def construir_config(self):
        c = tarjeta(self.v_cfg)
        c.pack(fill="both", expand=True)
        tk.Label(c, text="⚙️  Configuración", bg=PANEL, fg=TEXTO,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=(18, 6))
        tk.Label(c, text="Base de datos PostgreSQL. Puedes exportar o importar respaldos JSON.", bg=PANEL, fg=SUAVE,
                 font=FUENTE).pack(anchor="w", padx=20, pady=(0, 14))
        f = tk.Frame(c, bg=PANEL)
        f.pack(anchor="w", padx=20)
        boton(f, "Exportar respaldo", self.exportar, AZUL).pack(side="left", padx=(0, 8))
        boton(f, "Importar respaldo", self.importar, VERDE).pack(side="left", padx=8)
        boton(f, "Borrar todo", self.borrar_todo, ROJO).pack(side="left", padx=8)

    def mostrar(self, vista):
        for clave, b in self.nav.items():
            activo = clave == vista
            b.configure(bg=NAV_SEL if activo else PANEL, fg=AZUL if activo else TEXTO,
                        font=("Segoe UI", 11, "bold" if activo else "normal"))
        if vista in ("inicio", "materias"):
            self.v_inicio.tkraise()
            if vista == "materias":
                self.card_form.grid_remove()
            else:
                self.card_form.grid()
        elif vista == "calendario":
            self.v_cal.tkraise()
        else:
            self.v_cfg.tkraise()

    
    def msg(self, texto, error=False):
        self.lbl_msg.config(text=texto, fg=ROJO if error else "#146C3F")
        if self.id_msg:
            self.after_cancel(self.id_msg)
        self.id_msg = self.after(4000, lambda: self.lbl_msg.config(text=""))

    
    def actualizar(self):
        texto = self.q.get().strip().casefold()
        self.tabla.delete(*self.tabla.get_children())
        for m in self.materias:
            if texto and texto not in m["materia"].casefold() \
                    and texto not in m["profesor"].casefold():
                continue
            est = estado_real(m)
            self.tabla.insert("", tk.END, iid=m["materia"].casefold(), tags=(est,),
                              values=(m["materia"], m["profesor"], formatear_nota(m["nota"]),
                                      m["fecha"], est, "✎", "🗑"))

        estados = [estado_real(m) for m in self.materias]
        venc = estados.count("Vencida")
        hoy = date.today()
        futuras = [m for m in self.materias
                   if m["estado"] != "Completada" and parsear_fecha(m["fecha"]) >= hoy]
        prox = min(futuras, key=lambda m: parsear_fecha(m["fecha"]), default=None)
        datos = [
            (str(len(self.materias)), "Materias registradas"),
            (str(estados.count("Completada")), "Completadas"),
            (str(estados.count("Pendiente") + venc),
             "Pendientes" + (f" ({venc} vencida{'s' if venc > 1 else ''})" if venc else "")),
            (prox["fecha"] if prox else "—",
             f"Próxima: {prox['materia']}" if prox else "Próxima entrega"),
        ]
        for (n, s), (num, texto_s) in zip(self.stats, datos):
            n.config(text=num)
            s.config(text=texto_s)

        self.t_cal.delete(*self.t_cal.get_children())
        for m in sorted(self.materias, key=lambda m: parsear_fecha(m["fecha"])):
            self.t_cal.insert("", tk.END, tags=(estado_real(m),),
                              values=(m["fecha"], m["materia"], texto_dias(m)))

    def clic_tabla(self, ev):
        if self.tabla.identify_region(ev.x, ev.y) != "cell":
            return
        iid = self.tabla.identify_row(ev.y)
        col = self.tabla.identify_column(ev.x)
        if not iid:
            return
        if col == "#6":
            self.editar(iid)
        elif col == "#7":
            self.eliminar(iid)
        elif col == "#5":
            m = self.buscar(iid)
            if m:
                m["estado"] = "Pendiente" if m["estado"] == "Completada" else "Completada"
                guardar(self.materias)
                self.actualizar()

    def mover_tabla(self, ev):
        col = self.tabla.identify_column(ev.x)
        sobre = self.tabla.identify_row(ev.y) and col in ("#5", "#6", "#7")
        self.tabla.configure(cursor="hand2" if sobre else "")

  
    def buscar(self, clave):
        return next((m for m in self.materias if m["materia"].casefold() == clave), None)

    def limpiar_form(self):
        self.c_anio.set("")
        self.e_materia.set("")
        self.e_materia["values"] = []
        for e in (self.e_profesor, self.e_nota, self.e_fecha):
            e.delete(0, tk.END)
        self.c_estado.set("Pendiente")
        self.edit_key = None
        self.b_reg.config(text="💾 Registrar")
        self.lbl_form.config(text="Registrar / Editar Materia")
        self.e_materia.focus()

    def registrar(self):
        anio = self.c_anio.get().strip()
        materia = self.e_materia.get().strip()
        profesor = self.e_profesor.get().strip()
        nota = self.e_nota.get().strip()
        fecha = self.e_fecha.get().strip()

        if not (anio and materia and profesor and nota and fecha):
            return self.msg("Completa todos los campos y selecciona año y materia.", True)

        reg = validar_registro(materia, profesor, nota, fecha, self.c_estado.get(), anio)
        if reg is None or not 0 <= reg["nota"] <= 100:
            return self.msg("La nota debe estar entre 0 y 100 y la fecha usar DD/MM/AAAA.", True)

        actual = self.buscar(self.edit_key) if self.edit_key else None
        if any(m is not actual and m["materia"].casefold() == materia.casefold()
               and m.get("anio", "Primer año") == anio for m in self.materias):
            return self.msg("Esa materia ya está registrada para ese año.", True)

        if actual:
            actual.update(reg)
        else:
            self.materias.append(reg)

        guardar(self.materias)
        self.limpiar_form()
        self.actualizar()
        self.msg(f"✔ {materia} {'actualizada' if actual else 'registrada correctamente'}.")
        self.revisar_fechas()

    def editar(self, clave):
        m = self.buscar(clave)
        if not m:
            return
        self.mostrar("inicio")
        anio = m.get("anio", "Primer año")
        self.c_anio.set(anio)
        self.seleccionar_anio()
        self.e_materia.set(m["materia"])
        for e, valor in ((self.e_profesor, m["profesor"]),
                         (self.e_nota, formatear_nota(m["nota"])), (self.e_fecha, m["fecha"])):
            e.delete(0, tk.END)
            e.insert(0, valor)
        self.c_estado.set(m["estado"])
        self.edit_key = clave
        self.b_reg.config(text="💾 Guardar")
        self.lbl_form.config(text="Editar Materia")
        self.e_materia.focus()

    def editar_seleccionada(self):
        sel = self.tabla.selection()
        if not sel:
            return self.msg("Selecciona una fila de la tabla para editarla.", True)
        self.editar(sel[0])

    def eliminar_actual(self):
        sel = self.tabla.selection()
        clave = self.edit_key or (sel[0] if sel else None)
        if not clave:
            return self.msg("Pulsa ✎ en una fila (o selecciónala) para eliminarla.", True)
        self.eliminar(clave)

    def eliminar(self, clave):
        m = self.buscar(clave)
        if not m or not messagebox.askyesno("Confirmar", f"¿Eliminar la materia {m['materia']}?"):
            return
        self.materias.remove(m)
        if self.edit_key == clave:
            self.limpiar_form()
        guardar(self.materias)
        self.actualizar()
        self.msg(f"{m['materia']} eliminada.")

    # ----- Configuración -----
    def exportar(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".json", initialfile="respaldo_estudios.json",
                                            filetypes=[("JSON", "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(self.materias, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportar", "Respaldo guardado correctamente.")
        except OSError as error:
            messagebox.showerror("Error", f"No se pudo guardar:\n{error}")

    def importar(self):
        ruta = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                items = json.load(f)
            nuevas, vistos = [], set()
            for it in items:
                r = validar_registro(
                    it.get("materia", ""), it.get("profesor", ""), it.get("nota", ""),
                    it.get("fecha", ""), it.get("estado", ""),
                    it.get("anio", self.anios_db[0][2] if self.anios_db else "Primer año")
                )
                if r and r["materia"].casefold() not in vistos:
                    vistos.add(r["materia"].casefold())
                    nuevas.append(r)
        except (OSError, json.JSONDecodeError, AttributeError, TypeError) as error:
            return messagebox.showerror("Error", f"Archivo no válido:\n{error}")
        if messagebox.askyesno("Importar", f"Se reemplazarán tus datos por {len(nuevas)} materia(s). ¿Continuar?"):
            self.materias[:] = nuevas
            guardar(self.materias)
            self.actualizar()

    def borrar_todo(self):
        if messagebox.askyesno("Borrar todo", "¿Borrar todas las materias? No se puede deshacer."):
            self.materias.clear()
            guardar(self.materias)
            self.limpiar_form()
            self.actualizar()

    # ----- Recordatorios -----
    def notificar(self, mensaje):
        if notification is None:
            print("plyer no está instalado:", mensaje)
            return
        try:
            notification.notify(title="Recordatorio académico", message=mensaje,
                                timeout=10, app_name="Organizador de Estudios")
        except Exception as error:
            print("No se pudo mostrar la notificación:", error)

    def revisar_fechas(self):
        hoy = date.today()
        for m in self.materias:
            if m["estado"] == "Completada":
                continue
            dias = (parsear_fecha(m["fecha"]) - hoy).days
            if dias in (7, 3, 1):
                mensaje = f"{m['materia']}: entrega dentro de {dias} día(s)."
            elif dias == 0:
                mensaje = f"¡Hoy vence la entrega de {m['materia']}!"
            elif dias < 0:
                mensaje = f"La entrega de {m['materia']} está vencida."
            else:
                continue
            clave = (m["materia"], m["fecha"], dias)
            if clave not in self.avisos:
                self.avisos.add(clave)
                self.notificar(mensaje)

    def ciclo(self):
        """Único bucle de la app: avisos, tabla y reloj cada 60 s."""
        self.revisar_fechas()
        self.actualizar()
        self.lbl_hora.config(text=datetime.now().strftime("%d/%m/%Y %H:%M"))
        self.after(60000, self.ciclo)


if __name__ == "__main__":
    App().mainloop()