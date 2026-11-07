
import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk, messagebox

import psycopg2

DB= {
    "host": "localhost",
    "port": "5433",
    "database": "organizador",
    "user": "postgres",
    "password": "446544",
}
FORMATO_FECHA = "%d/%m/%Y"

USUARIO = "Estudiante"      
NOTA_MAX = 5                

AZUL, AZUL_OSC = "#072974", "#1d4ed8"
FONDO, BLANCO = "#829ECC", "#0ce994"
TEXTO, GRIS, BORDE = "#1f2937", "#6b7280", "#e5e9f2"
FUENTE = "Segoe UI"
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MENU = [("Panel Central", "🏠"), ("Materias", "📚"), ("Resultados", "📊"),
        ("Entregas", "📝"), ("Avisos", "📢"), ("Calendario", "📅")]


# ------------------------------------------------------------ BASE DE DATOS
class BD:
    def __init__(self):
        self.con = psycopg2.connect(**DB)
        self.con.autocommit = True
        self.crear_tablas()

    def ejecutar(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)

    def consultar(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def crear_tablas(self):
        self.ejecutar("""
            CREATE TABLE IF NOT EXISTS materia(
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                profesor VARCHAR(100),
                semestre INT);
            CREATE TABLE IF NOT EXISTS resultado(
                id SERIAL PRIMARY KEY,
                id_materia INT NOT NULL REFERENCES materia(id) ON DELETE CASCADE,
                tipo VARCHAR(30),
                nota NUMERIC(5,2),
                fecha DATE);
            CREATE TABLE IF NOT EXISTS entrega(
                id SERIAL PRIMARY KEY,
                id_materia INT NOT NULL REFERENCES materia(id) ON DELETE CASCADE,
                titulo VARCHAR(150) NOT NULL,
                fecha DATE NOT NULL,
                estado VARCHAR(20) DEFAULT 'Pendiente');
            CREATE TABLE IF NOT EXISTS aviso(
                id SERIAL PRIMARY KEY,
                titulo VARCHAR(150) NOT NULL,
                detalle TEXT,
                fecha DATE DEFAULT CURRENT_DATE);
        """)


# --------------------------------------------------------------- UTILIDADES
def tarjeta(master):
    return tk.Frame(master, bg=BLANCO, highlightbackground=BORDE,
                    highlightthickness=1)


def boton(master, texto, color, comando):
    return tk.Button(master, text=texto, bg=color, fg="white", relief="flat",
                     font=(FUENTE, 10, "bold"), cursor="hand2", pady=6,
                     activebackground=color, activeforeground="white",
                     command=comando)


def enlace(master, texto, comando):
    l = tk.Label(master, text=texto, bg=BLANCO, fg=AZUL, cursor="hand2",
                 font=(FUENTE, 9, "bold"))
    l.bind("<Button-1>", lambda e: comando())
    return l


# --------------------------------------------------------------- CALENDARIO
class Calendario(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BLANCO)
        self.app = app
        hoy = date.today()
        self.anio, self.mes = hoy.year, hoy.month
        cab = tk.Frame(self, bg=BLANCO)
        cab.pack(fill="x")
        tk.Button(cab, text="◀", relief="flat", bg=BLANCO, cursor="hand2",
                  command=lambda: self.mover(-1)).pack(side="left")
        tk.Button(cab, text="▶", relief="flat", bg=BLANCO, cursor="hand2",
                  command=lambda: self.mover(1)).pack(side="right")
        self.titulo = tk.Label(cab, bg=BLANCO, font=(FUENTE, 10, "bold"))
        self.titulo.pack(expand=True)
        self.grilla = tk.Frame(self, bg=BLANCO)
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
        ini = date(self.anio, self.mes, 1)
        fin = date(self.anio + (self.mes == 12), self.mes % 12 + 1, 1)
        marcadas = {f for (f,) in self.app.bd.consultar(
            "SELECT DISTINCT fecha FROM entrega WHERE fecha >= %s AND fecha < %s",
            (ini, fin))}
        for c, d in enumerate(["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]):
            tk.Label(self.grilla, text=d, bg=BLANCO, fg=GRIS, width=4,
                     font=(FUENTE, 8)).grid(row=0, column=c)
        for f, semana in enumerate(calendar.monthcalendar(self.anio, self.mes), 1):
            for c, dia in enumerate(semana):
                if dia == 0:
                    continue
                d = date(self.anio, self.mes, dia)
                bg, fg, peso = BLANCO, TEXTO, "normal"
                if d in marcadas:
                    fg, peso = "#dc2626", "bold"
                if d == date.today():
                    bg, fg = AZUL, "white"
                lbl = tk.Label(self.grilla, text=str(dia), bg=bg, fg=fg, width=4,
                               font=(FUENTE, 9, peso), cursor="hand2")
                lbl.grid(row=f, column=c, padx=1, pady=1)
                lbl.bind("<Button-1>", lambda e, d=d: self.al_clic(d))

    def al_clic(self, d):
        filas = self.app.bd.consultar(
            "SELECT titulo, estado FROM entrega WHERE fecha=%s", (d,))
        txt = "\n".join(f"• {t} ({e})" for t, e in filas) or "Sin entregas ese día."
        messagebox.showinfo(d.strftime("%d/%m/%Y"), txt)

    def refrescar(self):
        self.dibujar()


# ------------------------------------------------------------ PÁGINA CRUD
class PaginaCrud(tk.Frame):
    """Tabla + formulario con Guardar / Actualizar / Eliminar / Limpiar."""

    def __init__(self, master, app, tabla, campos, sql, cabeceras):
        super().__init__(master, bg=FONDO)
        self.app, self.tabla, self.campos, self.sql = app, tabla, campos, sql
        self.id_actual, self.filtro = None, ""

        izq = tarjeta(self)
        izq.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)
        self.tree = ttk.Treeview(izq, columns=cabeceras, show="headings")
        for c in cabeceras:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=60 if c == "ID" else 140, anchor="w")
        sb = ttk.Scrollbar(izq, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.seleccionar)

        der = tarjeta(self)
        der.pack(side="right", fill="y", padx=(10, 20), pady=20)
        form = tk.Frame(der, bg=BLANCO, width=290)
        form.pack(fill="y", padx=16, pady=16)
        tk.Label(form, text="Datos", bg=BLANCO, font=(FUENTE, 13, "bold")).pack(anchor="w")
        self.vars, self.widgets = {}, {}
        for col, etiqueta, tipo, extra, oblig in campos:
            tk.Label(form, text=etiqueta + (" *" if oblig else ""), bg=BLANCO,
                     fg=GRIS, font=(FUENTE, 9)).pack(anchor="w", pady=(10, 0))
            var = tk.StringVar()
            if tipo in ("combo", "materia"):
                w = ttk.Combobox(form, textvariable=var, state="readonly",
                                 values=extra or [], width=32)
            else:
                w = ttk.Entry(form, textvariable=var, width=34)
            w.pack(fill="x")
            self.vars[col], self.widgets[col] = var, w
            if tipo == "fecha":
                tk.Label(form, text="Formato AAAA-MM-DD", bg=BLANCO, fg=GRIS,
                         font=(FUENTE, 8)).pack(anchor="w")
        bt = tk.Frame(form, bg=BLANCO)
        bt.pack(fill="x", pady=(18, 0))
        for texto, color, cmd in [("Guardar", AZUL, self.agregar),
                                  ("Actualizar", "#0ea5e9", self.actualizar),
                                  ("Eliminar", "#ef4444", self.eliminar),
                                  ("Limpiar", "#64748b", self.limpiar)]:
            boton(bt, texto, color, cmd).pack(fill="x", pady=3)
        self.limpiar()

    # ---- datos
    def refrescar(self):
        mapa = self.app.mapa_materias()
        for col, _, tipo, _, _ in self.campos:
            if tipo == "materia":
                self.widgets[col]["values"] = list(mapa)
        self.cargar()

    def cargar(self):
        self.tree.delete(*self.tree.get_children())
        for fila in self.app.bd.consultar(self.sql):
            if self.filtro and self.filtro not in " ".join(map(str, fila)).lower():
                continue
            self.tree.insert("", "end", values=[("" if v is None else v) for v in fila])

    def filtrar(self, texto):
        self.filtro = texto.lower().strip()
        self.cargar()

    def seleccionar(self, _evento=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.id_actual = int(self.tree.item(sel[0])["values"][0])
        cols = ",".join(c[0] for c in self.campos)
        fila = self.app.bd.consultar(
            f"SELECT {cols} FROM {self.tabla} WHERE id=%s", (self.id_actual,))[0]
        mapa = self.app.mapa_materias()
        for (col, _, tipo, _, _), valor in zip(self.campos, fila):
            if tipo == "materia":
                txt = next((n for n, i in mapa.items() if i == valor), "")
            else:
                txt = "" if valor is None else str(valor)
            self.vars[col].set(txt)

    def limpiar(self):
        self.id_actual = None
        for col, _, tipo, _, _ in self.campos:
            self.vars[col].set(date.today().isoformat() if tipo == "fecha" else "")
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def leer(self):
        datos = []
        mapa = self.app.mapa_materias()
        for col, etiqueta, tipo, _, oblig in self.campos:
            txt = self.vars[col].get().strip()
            if not txt:
                if oblig:
                    messagebox.showwarning("Falta un dato", f"Completa «{etiqueta}».")
                    return None
                datos.append(None)
                continue
            try:
                if tipo == "entero":
                    v = int(txt)
                elif tipo == "decimal":
                    v = float(txt.replace(",", "."))
                elif tipo == "fecha":
                    v = datetime.strptime(txt, "%Y-%m-%d").date()
                elif tipo == "materia":
                    v = mapa[txt]
                else:
                    v = txt
            except (ValueError, KeyError):
                messagebox.showwarning("Dato inválido", f"Revisa el campo «{etiqueta}».")
                return None
            datos.append(v)
        return datos

    def _correr(self, sql, params):
        try:
            self.app.bd.ejecutar(sql, params)
        except psycopg2.Error as e:
            messagebox.showerror("Error de base de datos", str(e))
            return
        self.limpiar()
        self.app.refrescar_todo()

    # ---- botones
    def agregar(self):
        datos = self.leer()
        if datos is None:
            return
        cols = [c[0] for c in self.campos]
        self._correr(f"INSERT INTO {self.tabla} ({','.join(cols)}) "
                     f"VALUES ({','.join(['%s'] * len(cols))})", datos)

    def actualizar(self):
        if self.id_actual is None:
            messagebox.showinfo("Actualizar", "Primero selecciona un registro de la tabla.")
            return
        datos = self.leer()
        if datos is None:
            return
        sets = ",".join(f"{c[0]}=%s" for c in self.campos)
        self._correr(f"UPDATE {self.tabla} SET {sets} WHERE id=%s",
                     datos + [self.id_actual])

    def eliminar(self):
        if self.id_actual is None:
            messagebox.showinfo("Eliminar", "Primero selecciona un registro de la tabla.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro?"):
            self._correr(f"DELETE FROM {self.tabla} WHERE id=%s", (self.id_actual,))



class PaginaDashboard(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=FONDO)
        self.app = app

        ban = tk.Frame(self, bg="#e3edff")
        ban.pack(fill="x", padx=20, pady=(14, 8))
        tk.Label(ban, text="¡Buen día! 👋", bg="#e3edff", font=(FUENTE, 12)).pack(
            anchor="w", padx=22, pady=(12, 0))
        tk.Label(ban, text=f"{USUARIO}!", bg="#e3edff", fg=AZUL,
                 font=(FUENTE, 20, "bold")).pack(anchor="w", padx=22)
        tk.Label(ban, text="Mantente al día con tu recorrido académico.", bg="#e3edff",
                 fg=GRIS, font=(FUENTE, 9)).pack(anchor="w", padx=22, pady=(0, 12))

        # tarjetas de estadísticas
        fila = tk.Frame(self, bg=FONDO)
        fila.pack(fill="x", padx=14)
        self.stats = {}
        for i, (clave, titulo, icono) in enumerate([
                ("prom", "Promedio", "📈"), ("mat", "Materias", "🎓"),
                ("res", "Evaluaciones", "📋"), ("pen", "Entregas pendientes", "⏳"),
                ("cum", "Cumplimiento", "✅")]):
            c = tarjeta(fila)
            c.grid(row=0, column=i, sticky="nsew", padx=6)
            fila.grid_columnconfigure(i, weight=1, uniform="s")
            tk.Label(c, text=icono, bg=BLANCO, font=("Segoe UI Emoji", 22)).pack(
                side="left", padx=14, pady=12)
            col = tk.Frame(c, bg=BLANCO)
            col.pack(side="left")
            tk.Label(col, text=titulo, bg=BLANCO, fg=GRIS, font=(FUENTE, 9)).pack(anchor="w")
            v = tk.Label(col, text="–", bg=BLANCO, font=(FUENTE, 18, "bold"))
            v.pack(anchor="w")
            self.stats[clave] = v

        # resultados recientes + avisos
        medio = tk.Frame(self, bg=FONDO)
        medio.pack(fill="x", padx=14, pady=8)
        medio.grid_columnconfigure(0, weight=3, uniform="m")
        medio.grid_columnconfigure(1, weight=2, uniform="m")

        rr = tarjeta(medio)
        rr.grid(row=0, column=0, sticky="nsew", padx=6)
        cab = tk.Frame(rr, bg=BLANCO)
        cab.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(cab, text="Resultados recientes", bg=BLANCO,
                 font=(FUENTE, 11, "bold")).pack(side="left")
        enlace(cab, "Ver todos", lambda: app.mostrar("Resultados")).pack(side="right")
        self.tabla = ttk.Treeview(rr, columns=("Materia", "Tipo", "Nota", "Fecha"),
                                  show="headings", height=5)
        for c in ("Materia", "Tipo", "Nota", "Fecha"):
            self.tabla.heading(c, text=c)
            self.tabla.column(c, width=90 if c != "Materia" else 180)
        self.tabla.pack(fill="x", padx=14, pady=(0, 12))

        nb = tarjeta(medio)
        nb.grid(row=0, column=1, sticky="nsew", padx=6)
        cab = tk.Frame(nb, bg=BLANCO)
        cab.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(cab, text="Tablón de avisos", bg=BLANCO,
                 font=(FUENTE, 11, "bold")).pack(side="left")
        enlace(cab, "Ver todos", lambda: app.mostrar("Avisos")).pack(side="right")
        self.avisos = tk.Frame(nb, bg=BLANCO)
        self.avisos.pack(fill="x", padx=14, pady=(0, 10))

        # calendario, accesos rápidos, rendimiento
        bajo = tk.Frame(self, bg=FONDO)
        bajo.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        for i in range(3):
            bajo.grid_columnconfigure(i, weight=1, uniform="b")
        bajo.grid_rowconfigure(0, weight=1)

        cal = tarjeta(bajo)
        cal.grid(row=0, column=0, sticky="nsew", padx=6)
        cab = tk.Frame(cal, bg=BLANCO)
        cab.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(cab, text="Calendario académico", bg=BLANCO,
                 font=(FUENTE, 11, "bold")).pack(side="left")
        enlace(cab, "Ver", lambda: app.mostrar("Calendario")).pack(side="right")
        self.calendario = Calendario(cal, app)
        self.calendario.pack(padx=10, pady=6)

        qa = tarjeta(bajo)
        qa.grid(row=0, column=1, sticky="nsew", padx=6)
        tk.Label(qa, text="Accesos rápidos", bg=BLANCO,
                 font=(FUENTE, 11, "bold")).pack(anchor="w", padx=14, pady=(10, 6))
        grid = tk.Frame(qa, bg=BLANCO)
        grid.pack(padx=10)
        for i, (txt, ico, pag, color) in enumerate([
                ("Resultados", "📊", "Resultados", "#e8f0ff"),
                ("Materias", "📚", "Materias", "#e6f6ec"),
                ("Calendario", "📅", "Calendario", "#efe9ff"),
                ("Entregas", "📝", "Entregas", "#fff3e0"),
                ("Avisos", "📢", "Avisos", "#e8f0ff"),
                ("Nueva entrega", "➕", "Entregas", "#ffe9ee")]):
            b = tk.Button(grid, text=f"{ico}\n{txt}", bg=color, relief="flat",
                          font=(FUENTE, 9), width=11, height=3, cursor="hand2",
                          command=lambda p=pag: app.mostrar(p))
            b.grid(row=i // 3, column=i % 3, padx=5, pady=5)

        pf = tarjeta(bajo)
        pf.grid(row=0, column=2, sticky="nsew", padx=6)
        tk.Label(pf, text="Rendimiento general", bg=BLANCO,
                 font=(FUENTE, 11, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        cont = tk.Frame(pf, bg=BLANCO)
        cont.pack(expand=True)
        self.dona = tk.Canvas(cont, width=170, height=170, bg=BLANCO, highlightthickness=0)
        self.dona.pack(side="left", padx=6)
        leyenda = tk.Frame(cont, bg=BLANCO)
        leyenda.pack(side="left", padx=6)
        self.cats = [("Excelente", "#22c55e", 0.8), ("Bueno", "#2563eb", 0.6),
                     ("Regular", "#f59e0b", 0.4), ("A mejorar", "#ef4444", 0.0)]
        self.pct = []
        for nombre, color, _ in self.cats:
            f = tk.Frame(leyenda, bg=BLANCO)
            f.pack(anchor="w", pady=2)
            tk.Label(f, text="●", fg=color, bg=BLANCO).pack(side="left")
            tk.Label(f, text=nombre, bg=BLANCO, font=(FUENTE, 9), width=10,
                     anchor="w").pack(side="left")
            p = tk.Label(f, text="0%", bg=BLANCO, font=(FUENTE, 9, "bold"))
            p.pack(side="left")
            self.pct.append(p)

    def refrescar(self):
        bd = self.app.bd
        prom = bd.consultar("SELECT AVG(nota) FROM resultado")[0][0]
        n_mat = bd.consultar("SELECT COUNT(*) FROM materia")[0][0]
        n_res = bd.consultar("SELECT COUNT(*) FROM resultado")[0][0]
        pend = bd.consultar("SELECT COUNT(*) FROM entrega WHERE estado<>'Entregado'")[0][0]
        tot = bd.consultar("SELECT COUNT(*) FROM entrega")[0][0]
        self.stats["prom"].config(text=f"{prom:.2f}" if prom is not None else "–")
        self.stats["mat"].config(text=str(n_mat))
        self.stats["res"].config(text=str(n_res))
        self.stats["pen"].config(text=str(pend))
        self.stats["cum"].config(text=f"{round((tot - pend) * 100 / tot)}%" if tot else "–")

        self.tabla.delete(*self.tabla.get_children())
        for fila in bd.consultar(
                "SELECT m.nombre, r.tipo, r.nota, r.fecha FROM resultado r "
                "JOIN materia m ON m.id=r.id_materia ORDER BY r.fecha DESC, r.id DESC LIMIT 5"):
            self.tabla.insert("", "end", values=fila)

        for w in self.avisos.winfo_children():
            w.destroy()
        avisos = bd.consultar("SELECT titulo, COALESCE(detalle,''), fecha FROM aviso "
                              "ORDER BY fecha DESC, id DESC LIMIT 3")
        if not avisos:
            tk.Label(self.avisos, text="Sin avisos todavía.", bg=BLANCO, fg=GRIS).pack(anchor="w")
        for t, d, f in avisos:
            tk.Label(self.avisos, text="📢  " + t, bg=BLANCO,
                     font=(FUENTE, 10, "bold")).pack(anchor="w", pady=(6, 0))
            tk.Label(self.avisos, text=d, bg=BLANCO, fg=GRIS, font=(FUENTE, 9),
                     wraplength=330, justify="left").pack(anchor="w")
            tk.Label(self.avisos, text=f.strftime("%d/%m/%Y"), bg=BLANCO, fg=AZUL,
                     font=(FUENTE, 9, "bold")).pack(anchor="w")

        self.calendario.refrescar()
        self.dibujar_dona([n for (n,) in bd.consultar(
            "SELECT nota FROM resultado WHERE nota IS NOT NULL")], prom)

    def dibujar_dona(self, notas, prom):
        c = self.dona
        c.delete("all")
        cont = [0] * len(self.cats)
        for n in notas:
            p = float(n) / NOTA_MAX
            for i, (_, _, minimo) in enumerate(self.cats):
                if p >= minimo:
                    cont[i] += 1
                    break
        total = sum(cont)
        if total == 0:
            c.create_arc(15, 15, 155, 155, start=0, extent=359.9, style="arc",
                         width=22, outline="#e5e7eb")
        else:
            ini = 90
            for (_, color, _), k in zip(self.cats, cont):
                if k:
                    ext = 360 * k / total
                    c.create_arc(15, 15, 155, 155, start=ini, extent=-min(ext, 359.9),
                                 style="arc", width=22, outline=color)
                    ini -= ext
        pct = round(float(prom) / NOTA_MAX * 100) if prom is not None else 0
        c.create_text(85, 78, text=f"{pct}%", font=(FUENTE, 18, "bold"))
        c.create_text(85, 102, text="Rendimiento", font=(FUENTE, 8), fill=GRIS)
        for lbl, k in zip(self.pct, cont):
            lbl.config(text=f"{round(k * 100 / total) if total else 0}%")


# --------------------------------------------------------------------- APP
class App(tk.Tk):
    def __init__(self, bd):
        super().__init__()
        self.bd = bd
        self.title("Organizador de Estudios")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.configure(bg=FONDO)
        self.actual = "Dashboard"
        self.proximas = []

        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Treeview", rowheight=28, font=(FUENTE, 9), background=BLANCO,
                     fieldbackground=BLANCO, borderwidth=0)
        st.configure("Treeview.Heading", font=(FUENTE, 9, "bold"), background="#eef2f9",
                     foreground=GRIS, relief="flat")
        st.map("Treeview", background=[("selected", "#dbe7ff")],
               foreground=[("selected", TEXTO)])

        self.crear_sidebar()
        self.crear_contenido()
        self.mostrar("Dashboard")

    def crear_sidebar(self):
        sb = tk.Frame(self, bg=AZUL_OSC, width=230)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Label(sb, text="🎓", bg=AZUL_OSC, fg="white",
                 font=("Segoe UI Emoji", 34)).pack(pady=(20, 0))
        tk.Label(sb, text="Organizador", bg=AZUL_OSC, fg="white",
                 font=(FUENTE, 17, "bold")).pack()
        tk.Label(sb, text="de Estudios", bg=AZUL_OSC, fg="#dbe7ff",
                 font=(FUENTE, 11)).pack()
        panel = tk.Frame(sb, bg=BLANCO)
        panel.pack(fill="both", expand=True, padx=8, pady=(16, 8))
        self.items = {}
        for nombre, icono in MENU:
            l = self._item(panel, f"  {icono}   {nombre}")
            l.bind("<Button-1>", lambda e, n=nombre: self.mostrar(n))
            l.bind("<Enter>", lambda e, n=nombre: self._hover(n, True))
            l.bind("<Leave>", lambda e, n=nombre: self._hover(n, False))
            self.items[nombre] = l
        salir = self._item(panel, "  ⎋   Cerrar sesión")
        salir.pack_forget()
        salir.pack(side="bottom", fill="x", padx=8, pady=10)
        salir.bind("<Button-1>", lambda e: self.salir())

    def _item(self, panel, texto):
        l = tk.Label(panel, text=texto, anchor="w", bg=BLANCO, fg=TEXTO,
                     font=(FUENTE, 11), padx=12, pady=10, cursor="hand2")
        l.pack(fill="x", padx=8, pady=2)
        return l

    def _hover(self, nombre, dentro):
        if nombre != self.actual:
            self.items[nombre].config(bg="#eef4ff" if dentro else BLANCO)

    def crear_contenido(self):
        der = tk.Frame(self, bg=FONDO)
        der.pack(side="left", fill="both", expand=True)

        top = tk.Frame(der, bg=BLANCO, height=62, highlightbackground=BORDE,
                       highlightthickness=1)
        top.pack(fill="x")
        top.pack_propagate(False)
        self.titulo = tk.Label(top, bg=BLANCO, font=(FUENTE, 15, "bold"))
        self.titulo.pack(side="left", padx=24)
        tk.Label(top, text=f"Hola, {USUARIO}  👤", bg=BLANCO,
                 font=(FUENTE, 10, "bold")).pack(side="right", padx=20)
        self.campana = tk.Label(top, text="🔔 0", bg=BLANCO, cursor="hand2",
                                font=("Segoe UI Emoji", 12))
        self.campana.pack(side="right", padx=10)
        self.campana.bind("<Button-1>", lambda e: self.ver_proximas())
        caja = tk.Frame(top, bg="#eef2f9")
        caja.pack(side="right", padx=14)
        tk.Label(caja, text="🔍", bg="#eef2f9").pack(side="left", padx=(8, 0))
        self.busqueda = tk.StringVar()
        ent = tk.Entry(caja, textvariable=self.busqueda, relief="flat", bg="#eef2f9",
                       width=28, font=(FUENTE, 10))
        ent.pack(side="left", ipady=6, padx=6)
        ent.bind("<KeyRelease>", self.buscar)

        cont = tk.Frame(der, bg=FONDO)
        cont.pack(fill="both", expand=True)
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        self.paginas = {
            "Dashboard": PaginaDashboard(cont, self),
            "Materias": PaginaCrud(
                cont, self, "materia",
                [("nombre", "Nombre de la materia", "texto", None, True),
                 ("profesor", "Profesor", "texto", None, False),
                 ("semestre", "Semestre", "entero", None, False)],
                "SELECT id, nombre, COALESCE(profesor,''), COALESCE(semestre::text,'') "
                "FROM materia ORDER BY semestre NULLS LAST, nombre",
                ("ID", "Materia", "Profesor", "Semestre")),
            "Resultados": PaginaCrud(
                cont, self, "resultado",
                [("id_materia", "Materia", "materia", None, True),
                 ("tipo", "Tipo de evaluación", "combo",
                  ["Parcial", "Final", "Trabajo práctico", "Examen oral", "Otro"], True),
                 ("nota", "Nota", "decimal", None, True),
                 ("fecha", "Fecha", "fecha", None, True)],
                "SELECT r.id, m.nombre, r.tipo, r.nota, r.fecha FROM resultado r "
                "JOIN materia m ON m.id=r.id_materia ORDER BY r.fecha DESC, r.id DESC",
                ("ID", "Materia", "Tipo", "Nota", "Fecha")),
            "Entregas": PaginaCrud(
                cont, self, "entrega",
                [("id_materia", "Materia", "materia", None, True),
                 ("titulo", "Título", "texto", None, True),
                 ("fecha", "Fecha de entrega", "fecha", None, True),
                 ("estado", "Estado", "combo",
                  ["Pendiente", "En progreso", "Entregado"], True)],
                "SELECT e.id, m.nombre, e.titulo, e.fecha, e.estado FROM entrega e "
                "JOIN materia m ON m.id=e.id_materia ORDER BY e.fecha",
                ("ID", "Materia", "Título", "Fecha", "Estado")),
            "Avisos": PaginaCrud(
                cont, self, "aviso",
                [("titulo", "Título", "texto", None, True),
                 ("detalle", "Detalle", "texto", None, False),
                 ("fecha", "Fecha", "fecha", None, True)],
                "SELECT id, titulo, COALESCE(detalle,''), fecha FROM aviso "
                "ORDER BY fecha DESC, id DESC",
                ("ID", "Título", "Detalle", "Fecha")),
        }
        # Página de calendario grande
        pc = tk.Frame(cont, bg=FONDO)
        card = tarjeta(pc)
        card.pack(padx=20, pady=20, anchor="n")
        self.cal_grande = Calendario(card, self)
        self.cal_grande.pack(padx=40, pady=30)
        tk.Label(card, text="Los días en rojo tienen entregas. Haz clic en un día para verlas.",
                 bg=BLANCO, fg=GRIS, font=(FUENTE, 9)).pack(pady=(0, 20))
        pc.refrescar = self.cal_grande.refrescar
        self.paginas["Calendario"] = pc

        for p in self.paginas.values():
            p.grid(row=0, column=0, sticky="nsew")

    # ---- navegación y datos
    def mostrar(self, nombre):
        self.actual = nombre
        for n, l in self.items.items():
            activo = n == nombre
            l.config(bg=AZUL if activo else BLANCO, fg="white" if activo else TEXTO)
        self.titulo.config(text=nombre)
        self.busqueda.set("")
        pagina = self.paginas[nombre]
        if hasattr(pagina, "filtrar"):
            pagina.filtro = ""
        self.actualizar_campana()
        pagina.refrescar()
        pagina.tkraise()

    def refrescar_todo(self):
        self.actualizar_campana()
        for p in self.paginas.values():
            p.refrescar()

    def buscar(self, _evento=None):
        p = self.paginas[self.actual]
        if hasattr(p, "filtrar"):
            p.filtrar(self.busqueda.get())

    def mapa_materias(self):
        return {nombre: i for i, nombre in
                self.bd.consultar("SELECT id, nombre FROM materia ORDER BY nombre")}

    def actualizar_campana(self):
        self.proximas = self.bd.consultar(
            "SELECT titulo, fecha FROM entrega WHERE estado<>'Entregado' "
            "AND fecha BETWEEN CURRENT_DATE AND CURRENT_DATE+7 ORDER BY fecha")
        self.campana.config(text=f"🔔 {len(self.proximas)}")

    def ver_proximas(self):
        txt = "\n".join(f"• {t} — {f.strftime('%d/%m')}" for t, f in self.proximas)
        messagebox.showinfo("Próximas entregas",
                            txt or "No tienes entregas en los próximos 7 días.")

    def salir(self):
        if messagebox.askyesno("Salir", "¿Cerrar la aplicación?"):
            self.destroy()


if __name__ == "__main__":
    try:
        bd = BD()
    except psycopg2.Error as e:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Conexión", f"No se pudo conectar a PostgreSQL:\n\n{e}")
        raise SystemExit
    App(bd).mainloop()
