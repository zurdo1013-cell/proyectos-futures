import calendar
import csv
import json
import tkinter as tk
import psycopg2
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

try:
    from plyer import notification
except ImportError:
    notification = None

DB_CONFIG = {
    "host": "localhost",
    "port": "5433",
    "database": "organizador",
    "user": "postgres",
    "password": "446544",
}
FORMATO_FECHA = "%d/%m/%Y"

FONDO = "#FFFFFF"
PANEL = "#0B75B3"
LINEA = "#0B8A6A"
TEXTO = "#F0F1F7"
SUAVE = "#0A0D1D"


AZUL = "#000000"
AZUL_SB = "#0E90B1"
VERDE = "#106805"
ROJO = "#9B0A20"
NARANJA = "#A0530C"
MORADO = "#077453"
BANNER = "#372BA3"
GRIS = "#222944"
CIAN = "#45D9FF"
VIOLETA = "#795CD1"
DORADO = "#FBBF24"
TURQUESA = "#2DD4BF"

TINTE = {
    "azul": "#2457E6",
    "verde": "#075C20",
    "morado": "#2D086D",
    "naranja": "#D86106",
    "rojo": "#DA0707"
}

FILAS = {
    "Pendiente": ("#302619", "#A5670A"),
    "Completada": ("#102D25", "#10AC18"),
    "Vencida": ("#351B28", "#910E22"),
    "Sin registrar": ("#25283A", "#A5A9C5"),
}

COLOR_LETRA = {
    "A+": ("#102D25", "#19C37D"),
    "A": ("#102D25", "#19C37D"),
    "B+": ("#172747", "#45A3FF"),
    "B": ("#172747", "#45A3FF"),
    "C": ("#302619", "#FFB547"),
    "D": ("#351B28", "#FF4560")
}

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
NAV = [("Panel Central", "🏠", "Panel Central"), ("Perfil", "👤", "Perfil"),
       ("Materias", "📖", "Materias"), ("Resultados", "📊", "Resultados"),
       ("Asistencia", "🗓", "Asistencia"), ("Exámenes", "📝", "Exámenes"),
       ("Horario", "🕘", "Horario"), ("Avisos", "📢", "Avisos"),
       ("Calendario", "📆", "Calendario académico"), ("Descargas", "⬇", "Descargas"),
       ("Comentarios", "💬", "Comentarios")]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]


def fnt(tam, peso="normal"):
    return ("Segoe UI", tam, peso)



def parsear_fecha(texto):
    return datetime.strptime(texto, FORMATO_FECHA).date()


def estado_real(m):
    """'Vencida' se calcula al vuelo; en la BD solo se guarda Pendiente/Completada."""
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


def letra(nota):
    for minimo, l in ((90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C")):
        if nota >= minimo:
            return l
    return "D"


def saludo():
    h = datetime.now().hour
    return "Buenos días" if h < 12 else ("Buenas tardes" if h < 19 else "Buenas noches")


def llave(m):
    """Identificador único de un registro: año + materia."""
    return f"{m.get('anio', 'Primer año')}|{m['materia']}".casefold()


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime(FORMATO_FECHA)
    if isinstance(v, bool):
        return "Sí" if v else "No"
    return str(v)


def conectar_db():
    return psycopg2.connect(**DB_CONFIG)


def consultar(sql, params=None):
    con = conectar_db()
    try:
        with con.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        con.close()


def consultar_seguro(sql, params=None):
    try:
        return consultar(sql, params)
    except Exception as error:
        print("Consulta fallida:", error)
        return []


def ejecutar(sql, params=None):
    con = conectar_db()
    try:
        with con.cursor() as cur:
            cur.execute(sql, params)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def preparar_bd():
    """Crea las tablas propias de la app (el catálogo anios/materias ya lo tienes)."""
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
                );
                CREATE TABLE IF NOT EXISTS perfil (
                    id INTEGER PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL DEFAULT 'Estudiante',
                    carrera VARCHAR(120) DEFAULT 'Ingeniería Informática',
                    anio_cursa VARCHAR(60),
                    correo VARCHAR(120)
                );
                INSERT INTO perfil (id) SELECT 1
                    WHERE NOT EXISTS (SELECT 1 FROM perfil WHERE id = 1);
                CREATE TABLE IF NOT EXISTS aviso (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(150) NOT NULL,
                    detalle TEXT,
                    fecha DATE NOT NULL DEFAULT CURRENT_DATE
                );
                CREATE TABLE IF NOT EXISTS asistencia (
                    id SERIAL PRIMARY KEY,
                    materia_id INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
                    fecha DATE NOT NULL,
                    presente BOOLEAN NOT NULL DEFAULT TRUE
                );
                CREATE TABLE IF NOT EXISTS horario (
                    id SERIAL PRIMARY KEY,
                    materia_id INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
                    dia VARCHAR(12) NOT NULL,
                    hora_inicio VARCHAR(5) NOT NULL,
                    hora_fin VARCHAR(5) NOT NULL,
                    aula VARCHAR(40)
                );
                CREATE TABLE IF NOT EXISTS comentario (
                    id SERIAL PRIMARY KEY,
                    texto TEXT NOT NULL,
                    fecha TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def obtener_anios_db():
    return consultar("SELECT id, numero, nombre FROM anios ORDER BY numero")


def obtener_catalogo_materias(anio_nombre):
    return consultar("""
        SELECT m.id, m.nombre
        FROM materias m
        JOIN anios a ON a.id = m.anio_id
        WHERE a.nombre = %s
        ORDER BY m.semestre, m.id
    """, (anio_nombre,))


def obtener_catalogo_completo():
    return consultar("""
        SELECT m.id, m.nombre, m.semestre, a.id, a.numero, a.nombre
        FROM materias m
        JOIN anios a ON a.id = m.anio_id
        ORDER BY a.numero, m.semestre, m.id
    """)


def cargar_perfil():
    fila = consultar_seguro(
        "SELECT nombre, COALESCE(carrera,''), COALESCE(anio_cursa,''), COALESCE(correo,'') "
        "FROM perfil WHERE id = 1")
    if fila:
        n, c, a, e = fila[0]
        return {"nombre": n, "carrera": c, "anio_cursa": a, "correo": e}
    return {"nombre": "Estudiante", "carrera": "Ingeniería Informática",
            "anio_cursa": "", "correo": ""}


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
                """, (fila[0], registro["profesor"], registro["nota"],
                      parsear_fecha(registro["fecha"]), registro["estado"]))
        conexion.commit()
    except Exception as error:
        conexion.rollback()
        messagebox.showerror("Error de PostgreSQL",
                             f"No se pudieron guardar los datos:\n{error}")
    finally:
        conexion.close()


# ------------------------------------------------------------ WIDGETS BASE
def rect_redondo(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class Tarjeta(tk.Frame):
    """Tarjeta con esquinas redondeadas. El contenido va dentro de `.body`."""

    def __init__(self, master, fondo=PANEL, fuera=FONDO, borde=LINEA, radio=14, margen=8):
        super().__init__(master, bg=fuera)
        self.fondo, self.borde, self.radio = fondo, borde, radio
        self.cv = tk.Canvas(self, bg=fuera, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=fondo)
        self.body.pack(fill="both", expand=True, padx=margen, pady=margen)
        self.cv.bind("<Configure>", self._dibujar)

    def _dibujar(self, ev):
        self.cv.delete("all")
        rect_redondo(self.cv, 1, 1, ev.width - 2, ev.height - 2, self.radio,
                     fill=self.fondo, outline=self.borde)


def chip(padre, icono, fondo, tam=46, fuera=PANEL):
    cv = tk.Canvas(padre, width=tam, height=tam, bg=fuera, highlightthickness=0, bd=0)
    rect_redondo(cv, 1, 1, tam - 1, tam - 1, 12, fill=fondo, outline=fondo)
    cv.create_text(tam // 2, tam // 2, text=icono, font=("Segoe UI Emoji", max(12, tam // 3)))
    return cv


def boton(padre, texto, comando, color, padx=12):
    return tk.Button(padre, text=texto, command=comando, bg=color, fg="white",
                     activebackground=color, activeforeground="white", relief="flat",
                     bd=0, cursor="hand2", font=fnt(10, "bold"), padx=padx, pady=7)


def entrada(padre, var=None):
    return tk.Entry(padre, textvariable=var, bg="white", fg=TEXTO, insertbackground=TEXTO,
                    relief="flat", font=fnt(11), highlightthickness=1,
                    highlightbackground=LINEA, highlightcolor=AZUL)


def etiqueta(padre, texto, **kw):
    return tk.Label(padre, text=texto, bg=PANEL, fg=kw.pop("fg", SUAVE),
                    font=kw.pop("font", fnt(9)), anchor="w", **kw)


def enlace(padre, texto, comando):
    l = tk.Label(padre, text=texto, bg=PANEL, fg=AZUL, cursor="hand2", font=fnt(9, "bold"))
    l.bind("<Button-1>", lambda e: comando())
    return l


def titulo_tarjeta(padre, texto, enlace_texto=None, comando=None):
    cab = tk.Frame(padre, bg=PANEL)
    cab.pack(fill="x", padx=10, pady=(6, 4))
    tk.Label(cab, text=texto, bg=PANEL, fg=TEXTO, font=fnt(11, "bold")).pack(side="left")
    if enlace_texto:
        enlace(cab, enlace_texto, comando).pack(side="right")
    return cab


def estilo_tabla(tabla):
    for nombre, (bg, fg) in FILAS.items():
        tabla.tag_configure(nombre, background=bg, foreground=fg)


class Pagina(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=FONDO)

    def refrescar(self):
        pass


class ItemMenu(tk.Frame):
    """Opción del menú lateral: píldora azul cuando está activa."""

    def __init__(self, master, texto, icono, comando, color_texto=TEXTO):
        super().__init__(master, bg=PANEL)
        self.activo, self.hover, self.color_texto = False, False, color_texto
        self.cv = tk.Canvas(self, bg=PANEL, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.lbl = tk.Label(self, text=f"{icono}   {texto}", anchor="w", bg=PANEL,
                            fg=color_texto, font=fnt(10), cursor="hand2")
        self.lbl.pack(fill="x", padx=(14, 6), pady=8)
        for w in (self, self.cv, self.lbl):
            w.bind("<Button-1>", lambda e: comando())
            w.bind("<Enter>", lambda e: self.poner(hover=True))
            w.bind("<Leave>", lambda e: self.poner(hover=False))
        self.cv.bind("<Configure>", lambda e: self.pintar())

    def poner(self, activo=None, hover=None):
        if activo is not None:
            self.activo = activo
        if hover is not None:
            self.hover = hover
        self.pintar()

    def pintar(self):
        color = AZUL if self.activo else ("#eef4ff" if self.hover else PANEL)
        self.cv.delete("all")
        if color != PANEL:
            rect_redondo(self.cv, 2, 1, max(self.cv.winfo_width() - 2, 10),
                         max(self.cv.winfo_height() - 1, 10), 10, fill=color, outline=color)
        self.lbl.config(bg=color, fg="white" if self.activo else self.color_texto,
                        font=fnt(10, "bold" if self.activo else "normal"))


class Calendario(tk.Frame):
    """Calendario mensual. Naranja = entregas pendientes, verde = completadas."""

    def __init__(self, master, app, grande=False):
        super().__init__(master, bg=PANEL)
        self.app, self.grande = app, grande
        hoy = date.today()
        self.anio, self.mes = hoy.year, hoy.month
        cab = tk.Frame(self, bg=PANEL)
        cab.pack(fill="x")
        tk.Button(cab, text="◀", relief="flat", bd=0, bg=PANEL, fg=SUAVE, cursor="hand2",
                  command=lambda: self.mover(-1)).pack(side="left")
        tk.Button(cab, text="▶", relief="flat", bd=0, bg=PANEL, fg=SUAVE, cursor="hand2",
                  command=lambda: self.mover(1)).pack(side="right")
        self.titulo = tk.Label(cab, bg=PANEL, fg=TEXTO, font=fnt(12 if grande else 9, "bold"))
        self.titulo.pack(expand=True)
        self.grilla = tk.Frame(self, bg=PANEL)
        self.grilla.pack()
        self.dibujar()

    def mover(self, delta):
        self.mes += delta
        if self.mes == 0:
            self.mes, self.anio = 12, self.anio - 1
        elif self.mes == 13:
            self.mes, self.anio = 1, self.anio + 1
        self.dibujar()

    def dibujar(self):
        for w in self.grilla.winfo_children():
            w.destroy()
        self.titulo.config(text=f"{MESES[self.mes - 1]} {self.anio}")
        marcas = {}
        for m in self.app.materias:
            marcas.setdefault(parsear_fecha(m["fecha"]), []).append(m)
        ancho = 7 if self.grande else 4
        for c, d in enumerate(["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]):
            tk.Label(self.grilla, text=d, bg=PANEL, fg=SUAVE, width=ancho,
                     font=fnt(9 if self.grande else 8, "bold")).grid(row=0, column=c)
        semanas = calendar.Calendar(0).monthdatescalendar(self.anio, self.mes)
        for f, semana in enumerate(semanas, 1):
            for c, d in enumerate(semana):
                bg, fg, peso = PANEL, TEXTO, "normal"
                if d.month != self.mes:
                    fg = "#c3cad6"
                elif d.weekday() == 6:
                    fg = ROJO
                if d in marcas and d.month == self.mes:
                    todas = all(m["estado"] == "Completada" for m in marcas[d])
                    bg, peso = ("#dcf5e4" if todas else "#fde7c7"), "bold"
                if d == date.today():
                    bg, fg, peso = AZUL, "white", "bold"
                lbl = tk.Label(self.grilla, text=str(d.day), bg=bg, fg=fg, width=ancho,
                               font=fnt(10 if self.grande else 8, peso), cursor="hand2",
                               pady=5 if self.grande else 0)
                lbl.grid(row=f, column=c, padx=1, pady=1)
                lbl.bind("<Button-1>", lambda e, d=d: self.al_clic(d))

    def al_clic(self, d):
        filas = [m for m in self.app.materias if parsear_fecha(m["fecha"]) == d]
        txt = "\n".join(f"• {m['materia']} ({estado_real(m)})" for m in filas) \
            or "Sin entregas ese día."
        messagebox.showinfo(d.strftime(FORMATO_FECHA), txt)


# ------------------------------------------------------------ PÁGINA CRUD
class PaginaCrud(Pagina):
    """Formulario + tabla con Guardar / Actualizar / Limpiar / Eliminar (tabla en PostgreSQL)."""

    def __init__(self, master, app, titulo, tabla, campos, sql, cabeceras, anchos,
                 con_anio=False, resumen=None, texto_guardar="💾 Guardar"):
        super().__init__(master)
        self.app, self.tabla_bd, self.campos, self.sql = app, tabla, campos, sql
        self.resumen, self.id_actual, self.filtro, self.id_msg = resumen, None, "", None
        self.con_anio = con_anio
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        fc = Tarjeta(self)
        fc.grid(row=0, column=0, sticky="ns", padx=(20, 10), pady=20)
        f = fc.body
        tk.Frame(f, width=300, height=1, bg=PANEL).pack()
        cab = tk.Frame(f, bg=PANEL)
        cab.pack(fill="x", padx=12, pady=(6, 2))
        chip(cab, "➕", TINTE["azul"], 38).pack(side="left")
        tk.Label(cab, text=titulo, bg=PANEL, fg=TEXTO, font=fnt(12, "bold")).pack(
            side="left", padx=10)

        self.var_anio = tk.StringVar()
        self.info = tk.StringVar()
        if con_anio:
            etiqueta(f, "Año de la carrera").pack(fill="x", padx=14, pady=(8, 0))
            ca = ttk.Combobox(f, textvariable=self.var_anio, state="readonly",
                              values=[a[2] for a in app.anios_db], font=fnt(10))
            ca.pack(fill="x", padx=14)
            ca.bind("<<ComboboxSelected>>", lambda e: self.actualizar_materias())

        self.vars, self.widgets = {}, {}
        for col, texto, tipo, extra, oblig in campos:
            etiqueta(f, texto + (" *" if oblig else "")).pack(fill="x", padx=14, pady=(8, 0))
            if tipo == "largo":
                var = None
                w = tk.Text(f, height=5, width=32, relief="flat", font=fnt(10), wrap="word",
                            highlightthickness=1, highlightbackground=LINEA,
                            highlightcolor=AZUL)
            elif tipo in ("combo", "materia", "bool"):
                var = tk.StringVar()
                w = ttk.Combobox(f, textvariable=var, state="readonly",
                                 values=list(extra or []), font=fnt(10))
            else:
                var = tk.StringVar()
                w = entrada(f, var)
            w.pack(fill="x", padx=14, ipady=0 if tipo == "largo" else 3)
            self.vars[col], self.widgets[col] = var, w
            if tipo == "materia":
                w.bind("<<ComboboxSelected>>", lambda e: self.mostrar_info())
                tk.Label(f, textvariable=self.info, bg=PANEL, fg=AZUL, font=fnt(9, "italic"),
                         anchor="w").pack(fill="x", padx=14)
            if tipo == "fecha":
                etiqueta(f, "Formato DD/MM/AAAA", font=fnt(8)).pack(fill="x", padx=14)
            if tipo == "hora":
                etiqueta(f, "Formato HH:MM", font=fnt(8)).pack(fill="x", padx=14)

        bt = tk.Frame(f, bg=PANEL)
        bt.pack(fill="x", padx=14, pady=(12, 4))
        for i in range(2):
            bt.columnconfigure(i, weight=1, uniform="bt")
        boton(bt, texto_guardar, self.agregar, AZUL, 4).grid(
            row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        boton(bt, "✏️ Actualizar", self.actualizar, NARANJA, 4).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        boton(bt, "🧹 Limpiar", self.limpiar, VERDE, 4).grid(
            row=1, column=0, sticky="ew", padx=(0, 4))
        boton(bt, "🗑 Eliminar", self.eliminar, ROJO, 4).grid(
            row=1, column=1, sticky="ew", padx=(4, 0))
        self.lbl_msg = tk.Label(f, text="", bg=PANEL, font=fnt(10, "bold"), wraplength=280,
                                justify="left")
        self.lbl_msg.pack(fill="x", padx=14, pady=(4, 6))

        tc = Tarjeta(self)
        tc.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        t = tc.body
        titulo_tarjeta(t, "Registros")
        self.lbl_resumen = tk.Label(t, text="", bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w")
        self.lbl_resumen.pack(fill="x", padx=10)
        marco = tk.Frame(t, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        self.tree = ttk.Treeview(marco, columns=cabeceras, show="headings",
                                 displaycolumns=cabeceras[1:], selectmode="browse")
        for c, ancho in zip(cabeceras, anchos):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=ancho, anchor="w")
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.seleccionar)
        self.limpiar()

    # ---- helpers de campos
    def valor(self, col):
        if self.vars[col] is None:
            return self.widgets[col].get("1.0", "end-1c").strip()
        return self.vars[col].get().strip()

    def poner(self, col, txt):
        if self.vars[col] is None:
            self.widgets[col].delete("1.0", "end")
            self.widgets[col].insert("1.0", txt)
        else:
            self.vars[col].set(txt)

    def msg(self, texto, error=False):
        self.lbl_msg.config(text=texto, fg=ROJO if error else "#146C3F")
        if self.id_msg:
            self.after_cancel(self.id_msg)
        self.id_msg = self.after(4000, lambda: self.lbl_msg.config(text=""))

    # ---- automatización año -> materia
    def actualizar_materias(self):
        anio = self.var_anio.get() if self.con_anio else None
        mapa = self.app.mapa_materias(anio or None)
        for col, _t, tipo, _e, _o in self.campos:
            if tipo == "materia":
                self.widgets[col]["values"] = list(mapa)

    def mostrar_info(self):
        etiq = next((self.valor(c) for c, _t, tipo, _e, _o in self.campos
                     if tipo == "materia"), "")
        fila = self.app.datos_materia(etiq)
        if not fila:
            self.info.set("")
            return
        if self.con_anio:
            self.var_anio.set(fila[5])
        self.info.set(f"{fila[5]} · Semestre {fila[2] or '–'}")

    # ---- datos
    def refrescar(self):
        self.actualizar_materias()
        self.cargar()

    def filtrar(self, texto):
        self.filtro = texto.casefold().strip()
        self.cargar()

    def cargar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            filas = consultar(self.sql)
        except Exception as error:
            messagebox.showerror("Error de PostgreSQL", str(error))
            return
        for fila in filas:
            vals = [fmt(v) for v in fila]
            if self.filtro and self.filtro not in " ".join(vals).casefold():
                continue
            self.tree.insert("", "end", values=vals)
        self.lbl_resumen.config(text=self.resumen() if self.resumen else f"{len(filas)} registro(s)")

    def seleccionar(self, _evento=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.id_actual = int(self.tree.item(sel[0])["values"][0])
        cols = ",".join(c[0] for c in self.campos)
        fila = consultar(f"SELECT {cols} FROM {self.tabla_bd} WHERE id=%s", (self.id_actual,))[0]
        mapa = self.app.mapa_materias()
        for (col, _t, tipo, extra, _o), val in zip(self.campos, fila):
            if tipo == "materia":
                txt = next((n for n, i in mapa.items() if i == val), "")
            elif tipo == "fecha":
                txt = val.strftime(FORMATO_FECHA) if val else ""
            elif tipo == "bool":
                txt = extra[0] if val else extra[1]
            else:
                txt = "" if val is None else str(val)
            self.poner(col, txt)
        self.mostrar_info()

    def limpiar(self):
        self.id_actual = None
        self.var_anio.set("")
        self.info.set("")
        for col, _t, tipo, extra, _o in self.campos:
            if tipo == "fecha":
                self.poner(col, date.today().strftime(FORMATO_FECHA))
            elif tipo == "bool":
                self.poner(col, extra[0])
            else:
                self.poner(col, "")
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def leer(self):
        datos = []
        mapa = self.app.mapa_materias()
        for col, texto, tipo, extra, oblig in self.campos:
            txt = self.valor(col)
            if not txt:
                if oblig:
                    self.msg(f"Completa «{texto}».", True)
                    return None
                datos.append(None)
                continue
            try:
                if tipo == "entero":
                    v = int(txt)
                elif tipo == "fecha":
                    v = datetime.strptime(txt, FORMATO_FECHA).date()
                elif tipo == "hora":
                    datetime.strptime(txt, "%H:%M")
                    v = txt
                elif tipo == "materia":
                    v = mapa[txt]
                elif tipo == "bool":
                    v = txt == extra[0]
                else:
                    v = txt
            except (ValueError, KeyError):
                self.msg(f"Revisa el campo «{texto}».", True)
                return None
            datos.append(v)
        return datos

    def _correr(self, sql, params, mensaje):
        try:
            ejecutar(sql, params)
        except Exception as error:
            messagebox.showerror("Error de PostgreSQL", str(error))
            return
        self.limpiar()
        self.refrescar()
        self.app.actualizar_Panel_Central()
        self.msg(mensaje)

    def agregar(self):
        datos = self.leer()
        if datos is None:
            return
        cols = [c[0] for c in self.campos]
        self._correr(f"INSERT INTO {self.tabla_bd} ({','.join(cols)}) "
                     f"VALUES ({','.join(['%s'] * len(cols))})", datos, "✔ Guardado.")

    def actualizar(self):
        if self.id_actual is None:
            return self.msg("Selecciona una fila de la tabla para actualizarla.", True)
        datos = self.leer()
        if datos is None:
            return
        sets = ",".join(f"{c[0]}=%s" for c in self.campos)
        self._correr(f"UPDATE {self.tabla_bd} SET {sets} WHERE id=%s",
                     datos + [self.id_actual], "✔ Actualizado.")

    def eliminar(self):
        if self.id_actual is None:
            return self.msg("Selecciona una fila de la tabla para eliminarla.", True)
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro?"):
            self._correr(f"DELETE FROM {self.tabla_bd} WHERE id=%s", (self.id_actual,),
                         "Registro eliminado.")


# --------------------------------------------------------------------- APP
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.ok = False
        self.title("Organizador de Estudios(ODE)")
        self.geometry(f"1200x{min(800, max(680, self.winfo_screenheight() - 70))}")
        self.minsize(1100, 680)
        self.configure(bg=FONDO)

        try:
            preparar_bd()
            self.anios_db = obtener_anios_db()
            self.materias = cargar()
            self.catalogo = obtener_catalogo_completo()
            self.perfil = cargar_perfil()
        except Exception as error:
            messagebox.showerror(
                "Error de PostgreSQL",
                "No se pudo conectar a la base de datos. Revisa la contraseña, "
                "el servidor y las tablas anios/materias.\n\n" + str(error)
            )
            self.destroy()
            return
        self.ok = True
        self.avisos = set()
        self.alertas = []
        self.edit_key = None
        self.id_msg = None
        self.actual = "Panel Central"
        self.paginas, self.items = {}, {}

        self.estilos()
        self.construir_sidebar()
        self.der = tk.Frame(self, bg=FONDO)
        self.der.pack(side="left", fill="both", expand=True)
        self.construir_topbar()
        self.construir_pie()
        cont = tk.Frame(self.der, bg=FONDO)
        cont.pack(fill="both", expand=True)
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)
        self.construir_paginas(cont)

        self.pintar_perfil()
        self.mostrar("Panel Central")
        self.ciclo()

    # ------------------------------------------------------------ estilos
    def estilos(self):
        e = ttk.Style(self)
        e.theme_use("clam")
        e.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXTO,
                    rowheight=34, font=fnt(10), borderwidth=0)
        e.configure("Treeview.Heading", background=GRIS, foreground=SUAVE,
                    font=fnt(10, "bold"), relief="flat", padding=(6, 8))
        e.configure("TCombobox", padding=5)
        e.map("Treeview", background=[("selected", "#dbe7ff")],
              foreground=[("selected", TEXTO)])

    # ------------------------------------------------------------ sidebar
    def construir_sidebar(self):
        self.sidebar = sb = tk.Frame(self, bg=AZUL_SB, width=196)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Label(sb, text="🎓", bg=AZUL_SB, fg="white", font=("Segoe UI Emoji", 30)).pack(
            pady=(16, 0))
        tk.Label(sb, text="Organizador", bg=AZUL_SB, fg="white", font=fnt(16, "bold")).pack()
        tk.Label(sb, text="de Estudios(ODE)", bg=AZUL_SB, fg="#dbe7ff", font=fnt(10)).pack()

        panel = Tarjeta(sb, fuera=AZUL_SB, borde=PANEL, radio=16)
        panel.pack(fill="both", expand=True, padx=8, pady=(14, 14))
        cuerpo = panel.body
        salir = ItemMenu(cuerpo, "Cerrar sesión", "⎋", self.salir, color_texto=ROJO)
        salir.pack(side="bottom", fill="x", padx=2, pady=(0, 2))
        tk.Frame(cuerpo, bg=LINEA, height=1).pack(side="bottom", fill="x", padx=10, pady=4)
        for clave, icono, texto in NAV:
            it = ItemMenu(cuerpo, texto, icono, lambda c=clave: self.mostrar(c))
            it.pack(fill="x", padx=2, pady=1)
            self.items[clave] = it

    def alternar_sidebar(self):
        if self.sidebar.winfo_ismapped():
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side="left", fill="y", before=self.der)

    def salir(self):
        if messagebox.askyesno("Cerrar sesión", "¿Cerrar la aplicación?"):
            self.destroy()

    # ------------------------------------------------------------- topbar
    def construir_topbar(self):
        top = tk.Frame(self.der, bg=PANEL, height=66, highlightbackground=LINEA,
                       highlightthickness=1)
        top.pack(fill="x")
        top.pack_propagate(False)
        ham = tk.Label(top, text="☰", bg=PANEL, fg=TEXTO, font=fnt(17), cursor="hand2")
        ham.pack(side="left", padx=(20, 16))
        ham.bind("<Button-1>", lambda e: self.alternar_sidebar())
        self.titulo = tk.Label(top, text="Panel Central", bg=PANEL, fg=TEXTO, font=fnt(14, "bold"))
        self.titulo.pack(side="left")

        usuario = tk.Frame(top, bg=PANEL, cursor="hand2")
        usuario.pack(side="right", padx=(8, 22))
        av = tk.Canvas(usuario, width=42, height=42, bg=PANEL, highlightthickness=0)
        av.create_oval(2, 2, 40, 40, fill="#dbe7ff", outline="#c7d8fb")
        av.create_text(21, 22, text="🧑", font=("Segoe UI Emoji", 15))
        av.pack(side="left")
        txt = tk.Frame(usuario, bg=PANEL)
        txt.pack(side="left", padx=8)
        self.lbl_user_n = tk.Label(txt, text="", bg=PANEL, fg=TEXTO, font=fnt(10, "bold"),
                                   anchor="w")
        self.lbl_user_n.pack(anchor="w")
        self.lbl_user_s = tk.Label(txt, text="", bg=PANEL, fg=SUAVE, font=fnt(8), anchor="w")
        self.lbl_user_s.pack(anchor="w")
        chev = tk.Label(usuario, text="⌄", bg=PANEL, fg=SUAVE, font=fnt(12))
        chev.pack(side="left")
        for w in (usuario, av, txt, self.lbl_user_n, self.lbl_user_s, chev):
            w.bind("<Button-1>", lambda e: self.mostrar("Perfil"))

        self.campana = tk.Canvas(top, width=44, height=44, bg=PANEL, highlightthickness=0,
                                 cursor="hand2")
        self.campana.pack(side="right", padx=6)
        self.campana.bind("<Button-1>", lambda e: self.ver_alertas())

        caja = tk.Frame(top, bg=GRIS, highlightthickness=1, highlightbackground=LINEA)
        caja.pack(side="right", padx=14)
        tk.Label(caja, text="🔍", bg=GRIS).pack(side="left", padx=(10, 0))
        self.q = tk.StringVar()
        ent = tk.Entry(caja, textvariable=self.q, relief="flat", bd=0, bg=GRIS, fg=TEXTO,
                       width=24, font=fnt(10), insertbackground=TEXTO)
        ent.pack(side="left", ipady=8, padx=6)
        self.ph = tk.Label(ent, text="Buscar en todo...", bg=GRIS, fg=SUAVE, font=fnt(10),
                           cursor="xterm")
        self.ph.place(x=2, rely=0.5, anchor="w")
        self.ph.bind("<Button-1>", lambda e: ent.focus_set())
        self.q.trace_add("write", lambda *a: self.al_buscar())

    def pintar_campana(self):
        c = self.campana
        c.delete("all")
        c.create_text(20, 24, text="🔔", fill=TEXTO, font=("Segoe UI Emoji", 16))
        n = len(self.alertas)
        if n:
            c.create_oval(24, 3, 41, 20, fill=AZUL, outline=PANEL, width=2)
            c.create_text(32, 12, text=str(n), fill="white", font=fnt(8, "bold"))

    def ver_alertas(self):
        txt = "\n".join(f"• {m['materia']} — {m['fecha']} ({texto_dias(m)})"
                        for m in self.alertas)
        messagebox.showinfo("Entregas próximas o vencidas",
                            txt or "No tienes entregas en los próximos 7 días.")

    def pintar_perfil(self):
        p = self.perfil
        self.lbl_user_n.config(text=f"Hola, {p['nombre']}")
        sub = " · ".join(x for x in (p["carrera"], p["anio_cursa"]) if x)
        self.lbl_user_s.config(text=sub[:34])
        self.lbl_saludo.config(text=f"{saludo()}, 👋")
        self.lbl_nombre.config(text=f"{p['nombre']}!")

    def construir_pie(self):
        pie = tk.Frame(self.der, bg=PANEL, height=34, highlightbackground=LINEA,
                       highlightthickness=1)
        pie.pack(side="bottom", fill="x")
        pie.pack_propagate(False)
        tk.Label(pie, text=f"© {date.today().year} Organizador de Estudios(ODE). "
                           "Todos los derechos reservados.", bg=PANEL, fg=SUAVE,
                 font=fnt(8)).pack(side="left", padx=20)
        f = tk.Frame(pie, bg=PANEL)
        f.pack(side="right", padx=20)
        tk.Label(f, text="HECHO CON ", bg=PANEL, fg=SUAVE, font=fnt(8)).pack(side="left")
        tk.Label(f, text="INGENIO ASTUCIA(IA)", bg=PANEL, fg=ROJO, font=fnt(9)).pack(side="left")
        tk.Label(f, text="PARA VAGOS", bg=PANEL, fg=SUAVE, font=fnt(8)).pack(side="left")

    # ------------------------------------------------------------ páginas
    def construir_paginas(self, cont):
        for clave, _i, _t in NAV:
            if clave in ("Asistencia", "Horario", "Avisos", "Comentarios"):
                continue
            p = Pagina(cont)
            self.paginas[clave] = p
        self.p_Panel_Central(self.paginas["Panel Central"])
        self.p_perfil(self.paginas["Perfil"])
        self.p_materias(self.paginas["Materias"])
        self.p_resultados(self.paginas["Resultados"])
        self.p_examenes(self.paginas["Exámenes"])
        self.p_calendario(self.paginas["Calendario"])
        self.p_descargas(self.paginas["Descargas"])

        self.paginas["Asistencia"] = PaginaCrud(
            cont, self, "Registrar asistencia", "asistencia",
            [("materia_id", "Materia", "materia", None, True),
             ("fecha", "Fecha de la clase", "fecha", None, True),
             ("presente", "Asistencia", "bool", ("Presente", "Ausente"), True)],
            "SELECT a.id, m.nombre, a.fecha, CASE WHEN a.presente THEN 'Presente' "
            "ELSE 'Ausente' END FROM asistencia a JOIN materias m ON m.id = a.materia_id "
            "ORDER BY a.fecha DESC, a.id DESC",
            ("ID", "Materia", "Fecha", "Asistencia"), (40, 260, 110, 110),
            con_anio=True, resumen=self.resumen_asistencia)
        self.paginas["Horario"] = PaginaCrud(
            cont, self, "Clase del horario", "horario",
            [("materia_id", "Materia", "materia", None, True),
             ("dia", "Día", "combo", DIAS, True),
             ("hora_inicio", "Hora de inicio", "hora", None, True),
             ("hora_fin", "Hora de fin", "hora", None, True),
             ("aula", "Aula", "texto", None, False)],
            "SELECT h.id, m.nombre, h.dia, h.hora_inicio, h.hora_fin, COALESCE(h.aula,'') "
            "FROM horario h JOIN materias m ON m.id = h.materia_id ORDER BY CASE h.dia "
            "WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3 "
            "WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 ELSE 6 END, h.hora_inicio",
            ("ID", "Materia", "Día", "Inicio", "Fin", "Aula"), (40, 220, 90, 70, 70, 90),
            con_anio=True)
        self.paginas["Avisos"] = PaginaCrud(
            cont, self, "Nuevo aviso", "aviso",
            [("titulo", "Título", "texto", None, True),
             ("detalle", "Detalle", "largo", None, False),
             ("fecha", "Fecha", "fecha", None, True)],
            "SELECT id, titulo, COALESCE(detalle,''), fecha FROM aviso "
            "ORDER BY fecha DESC, id DESC",
            ("ID", "Título", "Detalle", "Fecha"), (40, 220, 300, 100))
        self.paginas["Comentarios"] = PaginaCrud(
            cont, self, "Enviar comentario", "comentario",
            [("texto", "Tu comentario o sugerencia", "largo", None, True)],
            "SELECT id, texto, fecha FROM comentario ORDER BY fecha DESC",
            ("ID", "Comentario", "Enviado"), (40, 480, 130), texto_guardar="📨 Enviar")
        for p in self.paginas.values():
            p.grid(row=0, column=0, sticky="nsew")

    def resumen_asistencia(self):
        fila = consultar_seguro("SELECT COALESCE(SUM(CASE WHEN presente THEN 1 ELSE 0 END),0), "
                                "COUNT(*) FROM asistencia")
        pres, tot = fila[0] if fila else (0, 0)
        return (f"Asistencia total: {round(pres * 100 / tot)}% ({pres} de {tot} clases)"
                if tot else "Aún no registraste clases.")

    # ---- catálogo de materias (para los formularios)
    def mapa_materias(self, anio=None):
        return {f"{n} ({num}°)": mid for mid, n, _s, _aid, num, an in self.catalogo
                if not anio or an == anio}

    def datos_materia(self, etiq):
        mid = self.mapa_materias().get(etiq)
        return next((f for f in self.catalogo if f[0] == mid), None)

    # --------------------------------------------------------- navegación
    def mostrar(self, nombre, limpiar=True):
        self.actual = nombre
        for k, it in self.items.items():
            it.poner(activo=(k == nombre))
        self.titulo.config(text=next(t for c, _i, t in NAV if c == nombre))
        if limpiar and self.q.get():
            self.q.set("")
        p = self.paginas[nombre]
        p.refrescar()
        p.tkraise()

    def al_buscar(self):
        texto = self.q.get().strip()
        if texto:
            self.ph.place_forget()
        else:
            self.ph.place(x=2, rely=0.5, anchor="w")
        p = self.paginas.get(self.actual)
        if self.actual == "Resultados":
            self.actualizar_tabla()
        elif self.actual == "Materias":
            self.actualizar_materias()
        elif isinstance(p, PaginaCrud):
            p.filtrar(texto)
        elif texto:
            self.mostrar("Resultados", limpiar=False)

    def refrescar_todo(self):
        self.actualizar_tabla()
        self.actualizar_Panel_Central()
        self.actualizar_calendario()
        self.actualizar_examenes()
        self.actualizar_materias()

   
    def p_Panel_Central(self, p):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(3, weight=1)

        ban = Tarjeta(p, fondo=BANNER, borde=BANNER, radio=16)
        ban.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 8))
        izq = tk.Frame(ban.body, bg=BANNER)
        izq.pack(side="left", padx=22, pady=10)
        self.lbl_saludo = tk.Label(izq, text="", bg=BANNER, fg=TEXTO, font=fnt(14), anchor="w")
        self.lbl_saludo.pack(anchor="w")
        self.lbl_nombre = tk.Label(izq, text="", bg=BANNER, fg=AZUL, font=fnt(22, "bold"),
                                   anchor="w")
        self.lbl_nombre.pack(anchor="w")
        tk.Label(izq, text="Mantente al día con tu recorrido académico.", bg=BANNER,
                 fg=SUAVE, font=fnt(9), anchor="w").pack(anchor="w", pady=(2, 0))
        ilus = tk.Canvas(ban.body, width=380, height=112, bg=BANNER, highlightthickness=0)
        ilus.pack(side="right", padx=16)
        self.dibujar_ilustracion(ilus)

        fila = tk.Frame(p, bg=FONDO)
        fila.grid(row=1, column=0, sticky="ew", padx=14)
        self.stats = {}
        for i, (k, titulo, icono, tinte, color) in enumerate([
                ("prom", "Promedio", "📈", "azul", AZUL),
                ("tot", "Materias", "🎓", "verde", VERDE),
                ("ok", "Completadas", "📋", "morado", MORADO),
                ("apr", "Aprobadas", "🏆", "naranja", NARANJA),
                ("asi", "Asistencia", "✅", "rojo", ROJO)]):
            t = Tarjeta(fila)
            t.grid(row=0, column=i, sticky="nsew", padx=6)
            fila.grid_columnconfigure(i, weight=1, uniform="stat")
            chip(t.body, icono, TINTE[tinte]).pack(side="left", padx=(6, 10), pady=6)
            col = tk.Frame(t.body, bg=PANEL)
            col.pack(side="left")
            tk.Label(col, text=titulo, bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w").pack(anchor="w")
            v = tk.Label(col, text="–", bg=PANEL, fg=TEXTO, font=fnt(18, "bold"), anchor="w")
            v.pack(anchor="w")
            s = tk.Label(col, text="", bg=PANEL, fg=color, font=fnt(8, "bold"), anchor="w")
            s.pack(anchor="w")
            self.stats[k] = (v, s)

        medio = tk.Frame(p, bg=FONDO)
        medio.grid(row=2, column=0, sticky="ew", padx=14, pady=10)
        medio.grid_columnconfigure(0, weight=11, uniform="m")
        medio.grid_columnconfigure(1, weight=9, uniform="m")

        rr = Tarjeta(medio)
        rr.grid(row=0, column=0, sticky="nsew", padx=6)
        titulo_tarjeta(rr.body, "Resultados recientes", "Ver todos",
                       lambda: self.mostrar("Resultados"))
        self.tabla_rec = tk.Frame(rr.body, bg=PANEL)
        self.tabla_rec.pack(fill="x", padx=8, pady=(2, 6))

        nb = Tarjeta(medio)
        nb.grid(row=0, column=1, sticky="nsew", padx=6)
        titulo_tarjeta(nb.body, "Tablón de avisos", "Ver todos", lambda: self.mostrar("Avisos"))
        self.caja_avisos = tk.Frame(nb.body, bg=PANEL)
        self.caja_avisos.pack(fill="x", padx=8, pady=(0, 6))

        bajo = tk.Frame(p, bg=FONDO)
        bajo.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 10))
        bajo.grid_rowconfigure(0, weight=1)
        bajo.grid_columnconfigure(0, weight=3, uniform="b")
        bajo.grid_columnconfigure(1, weight=3, uniform="b")
        bajo.grid_columnconfigure(2, weight=4, uniform="b")

        cal = Tarjeta(bajo)
        cal.grid(row=0, column=0, sticky="nsew", padx=6)
        titulo_tarjeta(cal.body, "Calendario académico", "Ver calendario",
                       lambda: self.mostrar("Calendario"))
        self.cal_mini = Calendario(cal.body, self)
        self.cal_mini.pack(padx=6, pady=(0, 4))

        qa = Tarjeta(bajo)
        qa.grid(row=0, column=1, sticky="nsew", padx=6)
        titulo_tarjeta(qa.body, "Accesos rápidos")
        grid = tk.Frame(qa.body, bg=PANEL)
        grid.pack(expand=True)
        for i, (txt, ico, tinte, destino) in enumerate([
                ("Mis resultados", "📋", "azul", "Resultados"),
                ("Mis materias", "📖", "verde", "Materias"),
                ("Horario", "🕘", "morado", "Horario"),
                ("Asistencia", "🗓", "naranja", "Asistencia"),
                ("Descargas", "⬇", "azul", "Descargas"),
                ("Comentarios", "💬", "rojo", "Comentarios")]):
            tile = tk.Frame(grid, bg=PANEL, cursor="hand2")
            tile.grid(row=i // 3, column=i % 3, padx=6, pady=4)
            c = chip(tile, ico, TINTE[tinte], 46)
            c.pack()
            l = tk.Label(tile, text=txt, bg=PANEL, fg=TEXTO, font=fnt(8), cursor="hand2")
            l.pack()
            for w in (tile, c, l):
                w.bind("<Button-1>", lambda e, d=destino: self.mostrar(d))

        pf = Tarjeta(bajo)
        pf.grid(row=0, column=2, sticky="nsew", padx=6)
        titulo_tarjeta(pf.body, "Rendimiento general", "Ver detalles",
                       lambda: self.mostrar("Resultados"))
        cont = tk.Frame(pf.body, bg=PANEL)
        cont.pack(expand=True)
        self.dona = tk.Canvas(cont, width=140, height=140, bg=PANEL, highlightthickness=0)
        self.dona.pack(side="left", padx=(4, 14))
        ley = tk.Frame(cont, bg=PANEL)
        ley.pack(side="left", padx=(0, 6))
        self.cats = [("Excelente", "#22c55e", 80), ("Bueno", AZUL, 60),
                     ("Regular", "#facc15", 40), ("A mejorar", ROJO, 0)]
        self.pct = []
        for i, (nombre, color, _m) in enumerate(self.cats):
            tk.Label(ley, text="●", fg=color, bg=PANEL, font=fnt(10)).grid(
                row=i, column=0, pady=3)
            tk.Label(ley, text=nombre, bg=PANEL, fg=TEXTO, font=fnt(9), anchor="w",
                     width=10).grid(row=i, column=1, sticky="w")
            l = tk.Label(ley, text="0%", bg=PANEL, fg=TEXTO, font=fnt(9, "bold"), anchor="e",
                         width=5)
            l.grid(row=i, column=2, sticky="e")
            self.pct.append(l)

    def dibujar_ilustracion(self, cv):
        for x1, y1, x2, y2 in ((10, 66, 100, 98), (60, 48, 150, 84), (300, 56, 372, 90),
                               (250, 30, 320, 60)):
            cv.create_oval(x1, y1, x2, y2, fill="#d9e6fb", outline="#d9e6fb")
        # maceta y planta
        cv.create_polygon(66, 80, 112, 80, 106, 110, 72, 110, fill="#f4f6fb", outline="#d4dbe8")
        cv.create_line(89, 80, 89, 34, fill="#3f9d4f", width=3)
        for pts, col in (((89, 58, 66, 50, 76, 70), "#58b868"), ((89, 50, 112, 40, 104, 62), "#3f9d4f"),
                         ((89, 40, 72, 24, 86, 18), "#58b868"), ((89, 36, 104, 20, 96, 14), "#3f9d4f")):
            cv.create_polygon(*pts, fill=col, outline=col, smooth=True)
        # libros
        for x1, y1, x2, y2, col in ((130, 80, 340, 110, "#2c5fd1"), (146, 52, 320, 80, "#f5a623"),
                                    (164, 24, 296, 52, "#3a70e3")):
            rect_redondo(cv, x1, y1, x2, y2, 5, fill=col, outline=col)
            cv.create_rectangle(x2 - 18, y1 + 4, x2 - 3, y2 - 4, fill="#f4f6fb", outline="#f4f6fb")
            cv.create_line(x2 - 18, y1 + 10, x2 - 3, y1 + 10, fill="#cfd6e4")
            cv.create_line(x2 - 18, y1 + 16, x2 - 3, y1 + 16, fill="#cfd6e4")
            cv.create_line(x1 + 10, y1 + 8, x1 + 10, y2 - 8, fill="#ffffff", width=1)
        cv.create_text(352, 22, text="⌄", fill="#2c5fd1", font=fnt(10, "bold"))
        cv.create_text(368, 36, text="⌄", fill="#2c5fd1", font=fnt(8, "bold"))

    def actualizar_Panel_Central(self):
        ms, hoy = self.materias, date.today()
        estados = [estado_real(m) for m in ms]
        prom = sum(m["nota"] for m in ms) / len(ms) if ms else None
        aprob = sum(1 for m in ms if m["nota"] >= 60)
        fila = consultar_seguro("SELECT COALESCE(SUM(CASE WHEN presente THEN 1 ELSE 0 END),0), "
                                "COUNT(*) FROM asistencia")
        pres, tot_as = fila[0] if fila else (0, 0)
        datos = {
            "prom": (f"{prom:.1f}" if prom is not None else "–", "Promedio actual"),
            "tot": (str(len(ms)), "Registradas"),
            "ok": (str(estados.count("Completada")), "Entregas listas"),
            "apr": (str(aprob), f"de {len(ms)}"),
            "asi": (f"{round(pres * 100 / tot_as)}%" if tot_as else "–",
                    f"{tot_as} clase(s)" if tot_as else "Sin registros"),
        }
        for k, (valor, sub) in datos.items():
            v, s = self.stats[k]
            v.config(text=valor)
            s.config(text=sub)

        self.alertas = sorted(
            (m for m in ms if m["estado"] != "Completada"
             and (parsear_fecha(m["fecha"]) - hoy).days <= 7),
            key=lambda m: parsear_fecha(m["fecha"]))
        self.pintar_campana()
        self.pintar_resultados_recientes()
        self.pintar_avisos()
        self.cal_mini.dibujar()
        self.dibujar_dona([m["nota"] for m in ms], prom)

    def pintar_resultados_recientes(self):
        for w in self.tabla_rec.winfo_children():
            w.destroy()
        t = self.tabla_rec
        pesos = (5, 2, 1, 2, 2)
        for c, peso in enumerate(pesos):
            t.grid_columnconfigure(c, weight=peso)
        cab = tk.Frame(t, bg=GRIS)
        cab.grid(row=0, column=0, columnspan=5, sticky="ew")
        for c, texto in enumerate(("Materia", "Estado", "Grado", "Nota", "Fecha")):
            tk.Label(t, text=texto, bg=GRIS, fg=SUAVE, font=fnt(8), anchor="w").grid(
                row=0, column=c, sticky="ew", padx=(8, 0), ipady=4)
        recientes = sorted(self.materias, key=lambda m: parsear_fecha(m["fecha"]),
                           reverse=True)[:5]
        if not recientes:
            tk.Label(t, text="Aún no registraste resultados.", bg=PANEL, fg=SUAVE,
                     font=fnt(9)).grid(row=1, column=0, columnspan=5, pady=18)
        for r, m in enumerate(recientes, 1):
            g = letra(m["nota"])
            bg, fg = COLOR_LETRA[g]
            tk.Label(t, text=m["materia"], bg=PANEL, fg=TEXTO, font=fnt(9, "bold"),
                     anchor="w").grid(row=r, column=0, sticky="ew", padx=(8, 0), pady=4)
            tk.Label(t, text=estado_real(m), bg=PANEL, fg=SUAVE, font=fnt(9),
                     anchor="w").grid(row=r, column=1, sticky="ew", padx=(8, 0))
            tk.Label(t, text=g, bg=bg, fg=fg, font=fnt(8, "bold"), padx=8).grid(
                row=r, column=2, sticky="w", padx=(8, 0))
            tk.Label(t, text=f"{formatear_nota(m['nota'])}/100", bg=PANEL, fg=TEXTO,
                     font=fnt(9), anchor="w").grid(row=r, column=3, sticky="ew", padx=(8, 0))
            tk.Label(t, text=m["fecha"], bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w").grid(
                row=r, column=4, sticky="ew", padx=(8, 0))

    def pintar_avisos(self):
        for w in self.caja_avisos.winfo_children():
            w.destroy()
        items = [(t, d, f) for t, d, f in consultar_seguro(
            "SELECT titulo, COALESCE(detalle,''), fecha FROM aviso "
            "ORDER BY fecha DESC, id DESC LIMIT 3")]
        pend = sorted((m for m in self.materias if m["estado"] != "Completada"),
                      key=lambda m: parsear_fecha(m["fecha"]))
        for m in pend:
            if len(items) >= 3:
                break
            items.append((f"Entrega: {m['materia']}", f"{texto_dias(m)} · {m['profesor']}",
                          parsear_fecha(m["fecha"])))
        if not items:
            tk.Label(self.caja_avisos, text="Sin avisos por ahora. 🎉", bg=PANEL, fg=SUAVE,
                     font=fnt(9)).pack(pady=18)
        for titulo, detalle, fecha in items[:3]:
            f = tk.Frame(self.caja_avisos, bg=PANEL)
            f.pack(fill="x", pady=4)
            chip(f, "📢", TINTE["azul"], 38).pack(side="left", padx=(0, 10))
            col = tk.Frame(f, bg=PANEL)
            col.pack(side="left", fill="x", expand=True)
            tk.Label(col, text=titulo, bg=PANEL, fg=TEXTO, font=fnt(9, "bold"), anchor="w",
                     wraplength=250, justify="left").pack(anchor="w")
            if detalle:
                tk.Label(col, text=detalle[:70], bg=PANEL, fg=SUAVE, font=fnt(8), anchor="w",
                         wraplength=250, justify="left").pack(anchor="w")
            tk.Label(col, text=fmt(fecha), bg=PANEL, fg=AZUL, font=fnt(8, "bold"),
                     anchor="w").pack(anchor="w")

    def dibujar_dona(self, notas, prom):
        c = self.dona
        c.delete("all")
        cont = [0] * len(self.cats)
        for n in notas:
            for i, (_n, _c, minimo) in enumerate(self.cats):
                if n >= minimo:
                    cont[i] += 1
                    break
        total = sum(cont)
        if total == 0:
            c.create_arc(14, 14, 126, 126, start=0, extent=359.9, style="arc", width=20,
                         outline="#e5e9f2")
        else:
            ini = 90
            for (_n, color, _m), k in zip(self.cats, cont):
                if k:
                    ext = 360 * k / total
                    c.create_arc(14, 14, 126, 126, start=ini, extent=-min(ext, 359.9),
                                 style="arc", width=20, outline=color)
                    ini -= ext
        c.create_text(70, 62, text=f"{round(prom)}%" if prom is not None else "–",
                      fill=TEXTO, font=fnt(18, "bold"))
        c.create_text(70, 84, text="Rendimiento", fill=SUAVE, font=fnt(8))
        for l, k in zip(self.pct, cont):
            l.config(text=f"{round(k * 100 / total) if total else 0}%")

    # ------------------------------------------------------------- PERFIL
    def p_perfil(self, p):
        p.grid_columnconfigure(0, weight=1)
        t = Tarjeta(p)
        t.grid(row=0, column=0, sticky="nw", padx=20, pady=20)
        c = t.body
        tk.Frame(c, width=470, height=1, bg=PANEL).pack()
        cab = tk.Frame(c, bg=PANEL)
        cab.pack(fill="x", padx=14, pady=(10, 4))
        av = tk.Canvas(cab, width=70, height=70, bg=PANEL, highlightthickness=0)
        av.create_oval(2, 2, 68, 68, fill="#dbe7ff", outline="#c7d8fb")
        av.create_text(35, 36, text="🧑", font=("Segoe UI Emoji", 26))
        av.pack(side="left")
        tk.Label(cab, text="Mi perfil", bg=PANEL, fg=TEXTO, font=fnt(15, "bold")).pack(
            side="left", padx=14)
        self.pf = {}
        for k, texto in (("nombre", "Nombre"), ("carrera", "Carrera"),
                         ("anio_cursa", "Año que cursas"), ("correo", "Correo electrónico")):
            etiqueta(c, texto).pack(fill="x", padx=14, pady=(10, 0))
            var = tk.StringVar()
            if k == "anio_cursa":
                w = ttk.Combobox(c, textvariable=var, values=[a[2] for a in self.anios_db],
                                 state="readonly", font=fnt(11))
            else:
                w = entrada(c, var)
            w.pack(fill="x", padx=14, ipady=3)
            self.pf[k] = var
        boton(c, "💾 Guardar cambios", self.guardar_perfil, AZUL).pack(
            anchor="w", padx=14, pady=(16, 6))
        self.lbl_pf = tk.Label(c, text="", bg=PANEL, font=fnt(10, "bold"))
        self.lbl_pf.pack(anchor="w", padx=14, pady=(0, 10))
        p.refrescar = self.cargar_form_perfil

    def cargar_form_perfil(self):
        for k, var in self.pf.items():
            var.set(self.perfil.get(k, ""))
        self.lbl_pf.config(text="")

    def guardar_perfil(self):
        datos = {k: v.get().strip() for k, v in self.pf.items()}
        if not datos["nombre"]:
            self.lbl_pf.config(text="Escribe tu nombre.", fg=ROJO)
            return
        try:
            ejecutar("UPDATE perfil SET nombre=%s, carrera=%s, anio_cursa=%s, correo=%s "
                     "WHERE id = 1", (datos["nombre"], datos["carrera"], datos["anio_cursa"],
                                      datos["correo"]))
        except Exception as error:
            messagebox.showerror("Error de PostgreSQL", str(error))
            return
        self.perfil = datos
        self.pintar_perfil()
        self.lbl_pf.config(text="✔ Perfil guardado.", fg="#146C3F")

    # ----------------------------------------------------------- MATERIAS
    def p_materias(self, p):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(0, weight=1)
        t = Tarjeta(p)
        t.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        c = t.body
        cab = tk.Frame(c, bg=PANEL)
        cab.pack(fill="x", padx=10, pady=(6, 4))
        chip(cab, "📖", TINTE["azul"], 38).pack(side="left")
        tk.Label(cab, text="Materias de la carrera", bg=PANEL, fg=TEXTO,
                 font=fnt(12, "bold")).pack(side="left", padx=10)
        boton(cab, "📊 Registrar resultado", self.registrar_desde_catalogo, AZUL).pack(
            side="right")
        self.c_filtro_anio = ttk.Combobox(
            cab, values=["Todos los años"] + [a[2] for a in self.anios_db], state="readonly",
            width=18, font=fnt(10))
        self.c_filtro_anio.set("Todos los años")
        self.c_filtro_anio.pack(side="right", padx=10)
        self.c_filtro_anio.bind("<<ComboboxSelected>>", lambda e: self.actualizar_materias())
        self.lbl_cat = tk.Label(c, text="", bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w")
        self.lbl_cat.pack(fill="x", padx=10)
        marco = tk.Frame(c, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        cols = ("materia", "anio", "semestre", "estado", "nota", "profesor")
        self.t_mat = ttk.Treeview(marco, columns=cols, show="headings", selectmode="browse")
        for col, texto, ancho, ancla in (
                ("materia", "Materia", 260, "w"), ("anio", "Año", 110, "w"),
                ("semestre", "Semestre", 80, "center"), ("estado", "Estado", 110, "center"),
                ("nota", "Nota", 70, "center"), ("profesor", "Profesor", 170, "w")):
            self.t_mat.heading(col, text=texto)
            self.t_mat.column(col, width=ancho, anchor=ancla, stretch=col in ("materia", "profesor"))
        estilo_tabla(self.t_mat)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.t_mat.yview)
        self.t_mat.configure(yscrollcommand=sb.set)
        self.t_mat.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.t_mat.bind("<Double-1>", lambda e: self.registrar_desde_catalogo())
        p.refrescar = self.refrescar_materias

    def refrescar_materias(self):
        try:
            self.catalogo = obtener_catalogo_completo()
        except Exception as error:
            print("No se pudo recargar el catálogo:", error)
        self.actualizar_materias()

    def actualizar_materias(self):
        reg = {llave(m): m for m in self.materias}
        filtro = self.c_filtro_anio.get()
        texto = self.q.get().strip().casefold() if self.actual == "Materias" else ""
        self.t_mat.delete(*self.t_mat.get_children())
        total = hechas = 0
        for _mid, nombre, sem, _aid, _num, anio in self.catalogo:
            if filtro != "Todos los años" and anio != filtro:
                continue
            if texto and texto not in nombre.casefold():
                continue
            m = reg.get(f"{anio}|{nombre}".casefold())
            total += 1
            hechas += 1 if m else 0
            est = estado_real(m) if m else "Sin registrar"
            self.t_mat.insert("", tk.END, tags=(est,), values=(
                nombre, anio, sem or "–", est, formatear_nota(m["nota"]) if m else "—",
                m["profesor"] if m else ""))
        self.lbl_cat.config(text=f"{hechas} de {total} materias con resultado registrado · "
                                 "doble clic para registrar o editar")

    def registrar_desde_catalogo(self):
        sel = self.t_mat.selection()
        if not sel:
            return messagebox.showinfo("Materias", "Selecciona una materia de la lista.")
        vals = self.t_mat.item(sel[0])["values"]
        nombre, anio = str(vals[0]), str(vals[1])
        k = llave({"anio": anio, "materia": nombre})
        self.mostrar("Resultados")
        if self.buscar(k):
            self.editar(k)
        else:
            self.limpiar_form()
            self.c_anio.set(anio)
            self.seleccionar_anio()
            self.e_materia.set(nombre)
            self.e_profesor.focus()

    # --------------------------------------------------------- RESULTADOS
    def p_resultados(self, p):
        p.grid_columnconfigure(1, weight=1)
        p.grid_rowconfigure(0, weight=1)
        fc = Tarjeta(p)
        fc.grid(row=0, column=0, sticky="ns", padx=(20, 10), pady=20)
        c = fc.body
        tk.Frame(c, width=300, height=1, bg=PANEL).pack()
        cab = tk.Frame(c, bg=PANEL)
        cab.pack(fill="x", padx=12, pady=(6, 2))
        chip(cab, "➕", TINTE["azul"], 38).pack(side="left")
        self.lbl_form = tk.Label(cab, text="Registrar resultado", bg=PANEL, fg=TEXTO,
                                 font=fnt(12, "bold"))
        self.lbl_form.pack(side="left", padx=10)

        etiqueta(c, "Año de la carrera").pack(fill="x", padx=14, pady=(8, 0))
        self.c_anio = ttk.Combobox(c, values=[a[2] for a in self.anios_db], state="readonly",
                                   font=fnt(10))
        self.c_anio.pack(fill="x", padx=14)
        self.c_anio.bind("<<ComboboxSelected>>", self.seleccionar_anio)
        etiqueta(c, "Materia").pack(fill="x", padx=14, pady=(8, 0))
        self.e_materia = ttk.Combobox(c, values=[], state="readonly", font=fnt(10))
        self.e_materia.pack(fill="x", padx=14)
        for texto, attr in (("Profesor", "e_profesor"), ("Nota", "e_nota"),
                            ("Fecha de entrega (DD/MM/AAAA)", "e_fecha")):
            etiqueta(c, texto).pack(fill="x", padx=14, pady=(8, 0))
            e = entrada(c)
            e.pack(fill="x", padx=14, ipady=3)
            e.bind("<Return>", lambda ev: self.registrar())
            setattr(self, attr, e)
        etiqueta(c, "Estado").pack(fill="x", padx=14, pady=(8, 0))
        self.c_estado = ttk.Combobox(c, values=["Pendiente", "Completada"], state="readonly",
                                     font=fnt(10))
        self.c_estado.set("Pendiente")
        self.c_estado.pack(fill="x", padx=14)

        f = tk.Frame(c, bg=PANEL)
        f.pack(fill="x", padx=14, pady=(12, 4))
        for i in range(2):
            f.columnconfigure(i, weight=1, uniform="b")
        self.b_reg = boton(f, "💾 Registrar", self.registrar, AZUL, 4)
        self.b_reg.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        boton(f, "✏️ Editar", self.editar_seleccionada, NARANJA, 4).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        boton(f, "🧹 Limpiar", self.limpiar_form, VERDE, 4).grid(
            row=1, column=0, sticky="ew", padx=(0, 4))
        boton(f, "🗑 Eliminar", self.eliminar_actual, ROJO, 4).grid(
            row=1, column=1, sticky="ew", padx=(4, 0))
        self.lbl_msg = tk.Label(c, text="", bg=PANEL, font=fnt(10, "bold"), wraplength=280,
                                justify="left")
        self.lbl_msg.pack(fill="x", padx=14, pady=(4, 6))

        tc = Tarjeta(p)
        tc.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        t = tc.body
        titulo_tarjeta(t, "Resultados registrados")
        tk.Label(t, text="Clic en «Estado» para alternar · ✎ editar · 🗑 eliminar",
                 bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w").pack(fill="x", padx=10)
        marco = tk.Frame(t, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        cols = ("materia", "profesor", "nota", "fecha", "estado", "ed", "el")
        self.tabla = ttk.Treeview(marco, columns=cols, show="headings", selectmode="browse")
        for col, texto, ancho, ancla in (
                ("materia", "Materia", 190, "w"), ("profesor", "Profesor", 140, "w"),
                ("nota", "Nota", 60, "center"), ("fecha", "Entrega", 100, "center"),
                ("estado", "Estado", 100, "center"), ("ed", "", 40, "center"),
                ("el", "", 40, "center")):
            self.tabla.heading(col, text=texto)
            self.tabla.column(col, width=ancho, anchor=ancla, stretch=col in ("materia", "profesor"))
        estilo_tabla(self.tabla)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=sb.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tabla.bind("<Button-1>", self.clic_tabla)
        self.tabla.bind("<Motion>", self.mover_tabla)
        self.limpiar_form()
        p.refrescar = self.actualizar_tabla

    def seleccionar_anio(self, evento=None):
        """Al elegir el año se cargan solas las materias de ese año."""
        anio = self.c_anio.get()
        try:
            materias = obtener_catalogo_materias(anio)
            self.e_materia["values"] = [nombre for _mid, nombre in materias]
            self.e_materia.set("")
        except Exception as error:
            self.e_materia["values"] = []
            self.e_materia.set("")
            self.msg(f"No se pudieron cargar las materias: {error}", True)

    def actualizar_tabla(self):
        texto = self.q.get().strip().casefold() if self.actual == "Resultados" else ""
        self.tabla.delete(*self.tabla.get_children())
        for m in self.materias:
            if texto and texto not in m["materia"].casefold() \
                    and texto not in m["profesor"].casefold():
                continue
            est = estado_real(m)
            self.tabla.insert("", tk.END, iid=llave(m), tags=(est,), values=(
                m["materia"], m["profesor"], formatear_nota(m["nota"]), m["fecha"], est,
                "✎", "🗑"))

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
                self.refrescar_todo()

    def mover_tabla(self, ev):
        col = self.tabla.identify_column(ev.x)
        sobre = self.tabla.identify_row(ev.y) and col in ("#5", "#6", "#7")
        self.tabla.configure(cursor="hand2" if sobre else "")

    def buscar(self, k):
        return next((m for m in self.materias if llave(m) == k), None)

    def limpiar_form(self):
        self.c_anio.set("")
        self.e_materia.set("")
        self.e_materia["values"] = []
        for e in (self.e_profesor, self.e_nota, self.e_fecha):
            e.delete(0, tk.END)
        self.e_fecha.insert(0, date.today().strftime(FORMATO_FECHA))
        self.c_estado.set("Pendiente")
        self.edit_key = None
        self.b_reg.config(text="💾 Registrar")
        self.lbl_form.config(text="Registrar resultado")

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
        if any(m is not actual and llave(m) == llave(reg) for m in self.materias):
            return self.msg("Esa materia ya está registrada para ese año.", True)

        if actual:
            actual.update(reg)
        else:
            self.materias.append(reg)
        guardar(self.materias)
        self.limpiar_form()
        self.refrescar_todo()
        self.msg(f"✔ {materia} {'actualizada' if actual else 'registrada correctamente'}.")
        self.revisar_fechas()

    def editar(self, k):
        m = self.buscar(k)
        if not m:
            return
        self.mostrar("Resultados")
        self.c_anio.set(m.get("anio", "Primer año"))
        self.seleccionar_anio()
        self.e_materia.set(m["materia"])
        for e, valor in ((self.e_profesor, m["profesor"]),
                         (self.e_nota, formatear_nota(m["nota"])), (self.e_fecha, m["fecha"])):
            e.delete(0, tk.END)
            e.insert(0, valor)
        self.c_estado.set(m["estado"])
        self.edit_key = k
        self.b_reg.config(text="💾 Guardar")
        self.lbl_form.config(text="Editar resultado")

    def editar_seleccionada(self):
        sel = self.tabla.selection()
        if not sel:
            return self.msg("Selecciona una fila de la tabla para editarla.", True)
        self.editar(sel[0])

    def eliminar_actual(self):
        sel = self.tabla.selection()
        k = self.edit_key or (sel[0] if sel else None)
        if not k:
            return self.msg("Pulsa ✎ en una fila (o selecciónala) para eliminarla.", True)
        self.eliminar(k)

    def eliminar(self, k):
        m = self.buscar(k)
        if not m or not messagebox.askyesno("Confirmar", f"¿Eliminar la materia {m['materia']}?"):
            return
        self.materias.remove(m)
        if self.edit_key == k:
            self.limpiar_form()
        guardar(self.materias)
        self.refrescar_todo()
        self.msg(f"{m['materia']} eliminada.")

    def msg(self, texto, error=False):
        self.lbl_msg.config(text=texto, fg=ROJO if error else "#146C3F")
        if self.id_msg:
            self.after_cancel(self.id_msg)
        self.id_msg = self.after(4000, lambda: self.lbl_msg.config(text=""))

    # ----------------------------------------------------------- EXÁMENES
    def p_examenes(self, p):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(0, weight=1)
        t = Tarjeta(p)
        t.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        c = t.body
        cab = tk.Frame(c, bg=PANEL)
        cab.pack(fill="x", padx=10, pady=(6, 4))
        chip(cab, "📝", TINTE["morado"], 38).pack(side="left")
        tk.Label(cab, text="Exámenes y entregas pendientes", bg=PANEL, fg=TEXTO,
                 font=fnt(12, "bold")).pack(side="left", padx=10)
        boton(cab, "✔ Marcar completada", self.completar_examen, VERDE).pack(side="right")
        boton(cab, "✎ Editar", self.editar_examen, NARANJA).pack(side="right", padx=8)
        self.lbl_exa = tk.Label(c, text="", bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w")
        self.lbl_exa.pack(fill="x", padx=10)
        marco = tk.Frame(c, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        self.t_exa = ttk.Treeview(marco, columns=("materia", "fecha", "situacion", "estado"),
                                  show="headings", selectmode="browse")
        for col, texto, ancho in (("materia", "Materia", 300), ("fecha", "Fecha", 120),
                                  ("situacion", "Situación", 200), ("estado", "Estado", 120)):
            self.t_exa.heading(col, text=texto)
            self.t_exa.column(col, width=ancho, anchor="w")
        estilo_tabla(self.t_exa)
        self.t_exa.pack(side="left", fill="both", expand=True)
        p.refrescar = self.actualizar_examenes

    def actualizar_examenes(self):
        self.t_exa.delete(*self.t_exa.get_children())
        pend = sorted((m for m in self.materias if m["estado"] != "Completada"),
                      key=lambda m: parsear_fecha(m["fecha"]))
        for m in pend:
            est = estado_real(m)
            self.t_exa.insert("", tk.END, iid=llave(m), tags=(est,),
                              values=(m["materia"], m["fecha"], texto_dias(m), est))
        hechas = len(self.materias) - len(pend)
        self.lbl_exa.config(text=f"{len(pend)} pendiente(s) · {hechas} completada(s)")

    def completar_examen(self):
        sel = self.t_exa.selection()
        m = self.buscar(sel[0]) if sel else None
        if not m:
            return messagebox.showinfo("Exámenes", "Selecciona una fila de la lista.")
        m["estado"] = "Completada"
        guardar(self.materias)
        self.refrescar_todo()

    def editar_examen(self):
        sel = self.t_exa.selection()
        if not sel:
            return messagebox.showinfo("Exámenes", "Selecciona una fila de la lista.")
        self.editar(sel[0])

    # --------------------------------------------------------- CALENDARIO
    def p_calendario(self, p):
        p.grid_columnconfigure(1, weight=1)
        p.grid_rowconfigure(0, weight=1)
        izq = Tarjeta(p)
        izq.grid(row=0, column=0, sticky="n", padx=(20, 10), pady=20)
        self.cal_grande = Calendario(izq.body, self, grande=True)
        self.cal_grande.pack(padx=22, pady=14)
        tk.Label(izq.body, text="Naranja: entregas pendientes · Verde: completadas\n"
                                "Haz clic en un día para ver sus entregas.",
                 bg=PANEL, fg=SUAVE, font=fnt(9)).pack(pady=(0, 12))
        der = Tarjeta(p)
        der.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        titulo_tarjeta(der.body, "Próximas entregas")
        marco = tk.Frame(der.body, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=8, pady=(4, 6))
        self.t_cal = ttk.Treeview(marco, columns=("fecha", "materia", "situacion"),
                                  show="headings", selectmode="none")
        for col, texto, ancho in (("fecha", "Fecha", 110), ("materia", "Materia", 240),
                                  ("situacion", "Situación", 170)):
            self.t_cal.heading(col, text=texto)
            self.t_cal.column(col, width=ancho, anchor="w")
        estilo_tabla(self.t_cal)
        self.t_cal.pack(fill="both", expand=True)
        p.refrescar = self.actualizar_calendario

    def actualizar_calendario(self):
        self.cal_mini.dibujar()
        self.cal_grande.dibujar()
        self.t_cal.delete(*self.t_cal.get_children())
        for m in sorted(self.materias, key=lambda m: parsear_fecha(m["fecha"])):
            self.t_cal.insert("", tk.END, tags=(estado_real(m),),
                              values=(m["fecha"], m["materia"], texto_dias(m)))

    # ---------------------------------------------------------- DESCARGAS
    def p_descargas(self, p):
        p.grid_columnconfigure(0, weight=1)
        t = Tarjeta(p)
        t.grid(row=0, column=0, sticky="nw", padx=20, pady=20)
        c = t.body
        tk.Frame(c, width=620, height=1, bg=PANEL).pack()
        tk.Label(c, text="Descargas y respaldos", bg=PANEL, fg=TEXTO, font=fnt(14, "bold")).pack(
            anchor="w", padx=14, pady=(10, 2))
        tk.Label(c, text="Tus datos viven en PostgreSQL. Aquí puedes sacar copias o restaurarlas.",
                 bg=PANEL, fg=SUAVE, font=fnt(9)).pack(anchor="w", padx=14, pady=(0, 8))
        for icono, tinte, titulo, desc, texto_b, cmd, color in (
                ("⬇", "azul", "Respaldo JSON", "Copia completa de tus resultados.",
                 "Exportar", self.exportar, AZUL),
                ("📄", "verde", "Hoja para Excel (CSV)", "Tus resultados en una tabla.",
                 "Exportar", self.exportar_csv, VERDE),
                ("⬆", "naranja", "Restaurar respaldo", "Reemplaza tus resultados por los del JSON.",
                 "Importar", self.importar, NARANJA),
                ("🗑", "rojo", "Borrar resultados", "Elimina todos tus resultados registrados.",
                 "Borrar todo", self.borrar_todo, ROJO)):
            f = tk.Frame(c, bg=PANEL)
            f.pack(fill="x", padx=14, pady=8)
            chip(f, icono, TINTE[tinte], 46).pack(side="left")
            col = tk.Frame(f, bg=PANEL)
            col.pack(side="left", padx=12, fill="x", expand=True)
            tk.Label(col, text=titulo, bg=PANEL, fg=TEXTO, font=fnt(10, "bold"),
                     anchor="w").pack(anchor="w")
            tk.Label(col, text=desc, bg=PANEL, fg=SUAVE, font=fnt(9), anchor="w").pack(anchor="w")
            boton(f, texto_b, cmd, color).pack(side="right")

    def exportar(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="respaldo_estudios.json",
                                            filetypes=[("JSON", "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(self.materias, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportar", "Respaldo guardado correctamente.")
        except OSError as error:
            messagebox.showerror("Error", f"No se pudo guardar:\n{error}")

    def exportar_csv(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile="resultados_estudios.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Año", "Materia", "Profesor", "Nota", "Entrega", "Estado"])
                for m in self.materias:
                    w.writerow([m["anio"], m["materia"], m["profesor"],
                                formatear_nota(m["nota"]), m["fecha"], estado_real(m)])
            messagebox.showinfo("Exportar", "Archivo CSV guardado correctamente.")
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
                    it.get("anio", self.anios_db[0][2] if self.anios_db else "Primer año"))
                if r and llave(r) not in vistos:
                    vistos.add(llave(r))
                    nuevas.append(r)
        except (OSError, json.JSONDecodeError, AttributeError, TypeError) as error:
            return messagebox.showerror("Error", f"Archivo no válido:\n{error}")
        if messagebox.askyesno("Importar",
                               f"Se reemplazarán tus datos por {len(nuevas)} materia(s). ¿Continuar?"):
            self.materias[:] = nuevas
            guardar(self.materias)
            self.refrescar_todo()

    def borrar_todo(self):
        if messagebox.askyesno("Borrar todo", "¿Borrar todos tus resultados? No se puede deshacer."):
            self.materias.clear()
            guardar(self.materias)
            self.limpiar_form()
            self.refrescar_todo()

    # ------------------------------------------------------ recordatorios
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
            k = (llave(m), m["fecha"], dias)
            if k not in self.avisos:
                self.avisos.add(k)
                self.notificar(mensaje)

    def ciclo(self):
        """Único bucle de la app: avisos y pantallas se refrescan cada 60 s."""
        self.revisar_fechas()
        self.refrescar_todo()
        self.pintar_perfil()
        self.after(60000, self.ciclo)


if __name__ == "__main__":
    app = App()
    if app.ok:
        app.mainloop()