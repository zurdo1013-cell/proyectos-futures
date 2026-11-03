import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": "5433",
    "database": "organizador",
    "user": "postgres",
    "password": "446544"
}

FONDO = "#EEF4FC"
PANEL = "#FFFFFF"
LINEA = "#DBE4F2"
TEXTO = "#0F2347"
SUAVE = "#5B6B88"
CABECERA = "#D3E5FB"
TITULO = "#0B2F6B"
AZUL = "#2D6BE4"
VERDE = "#2FB872"
ROJO = "#EF5350"
NARANJA = "#E28A07"
NAV_SEL = "#CFE2FB"
FUENTE = ("Segoe UI", 10)
FUENTE_B = ("Segoe UI", 10, "bold")


def conectar_db():
    """Abre una conexión nueva con PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)


def preparar_base():
    """Crea la tabla de registros personales si todavía no existe."""
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
                        CHECK (estado IN ('Pendiente', 'Completada')),
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conexion.commit()
    finally:
        conexion.close()


def obtener_anios():
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, numero, nombre FROM anios ORDER BY numero")
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_materias(anio_id):
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre
                FROM materias
                WHERE anio_id = %s
                ORDER BY semestre, id
            """, (anio_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_registros():
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT r.id, a.nombre, m.nombre, r.profesor, r.nota,
                       r.fecha_entrega, r.estado, r.materia_id
                FROM registros_estudio r
                JOIN materias m ON m.id = r.materia_id
                JOIN anios a ON a.id = m.anio_id
                ORDER BY a.numero, r.fecha_entrega, m.nombre
            """)
            return cursor.fetchall()
    finally:
        conexion.close()


def estado_real(estado, fecha):
    if estado == "Completada":
        return "Completada"
    return "Vencida" if fecha < date.today() else "Pendiente"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Estudios")
        self.geometry("1180x760")
        self.minsize(1000, 680)
        self.configure(bg=FONDO)

        self.anios = []
        self.materias_catalogo = []
        self.registros = []
        self.edit_id = None
        self.materia_ids = {}
        self.anio_ids = {}
        self.materia_actual_ids = {}

        try:
            preparar_base()
            self.anios = obtener_anios()
            if not self.anios:
                messagebox.showwarning(
                    "Sin años",
                    "No hay años registrados en la tabla anios. "
                    "Ejecuta primero el SQL de creación y carga de materias."
                )
        except Exception as error:
            messagebox.showerror(
                "Error de PostgreSQL",
                f"No se pudo conectar o preparar la base de datos.\n\n{error}"
            )
            self.destroy()
            return

        self.crear_interfaz()
        self.cargar_tabla()
        self.actualizar_reloj()

    def crear_interfaz(self):
        cabecera = tk.Frame(self, bg=CABECERA)
        cabecera.pack(fill="x")
        tk.Label(
            cabecera, text="🎓", font=("Segoe UI Emoji", 30), bg=CABECERA
        ).pack(side="left", padx=24, pady=10)
        centro = tk.Frame(cabecera, bg=CABECERA)
        centro.pack(side="left", expand=True, fill="x", pady=8)
        tk.Label(
            centro, text="Gestor de Estudios",
            font=("Segoe UI", 25, "bold"), fg=TITULO, bg=CABECERA
        ).pack()
        tk.Label(
            centro, text="Organiza tus materias, controla tus notas y cumple tus metas",
            font=("Segoe UI", 10), fg=TITULO, bg=CABECERA
        ).pack()

        cuerpo = tk.Frame(self, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=14, pady=14)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        formulario = tk.Frame(
            cuerpo, bg=PANEL, highlightbackground=LINEA, highlightthickness=1
        )
        formulario.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        formulario.configure(width=330)
        formulario.pack_propagate(False)

        tk.Label(
            formulario, text="Registrar / Editar materia",
            bg=PANEL, fg=TEXTO, font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=18, pady=(18, 10))

        self.c_anio = self.crear_combo(
            formulario, "Año de la carrera:",
            [a[2] for a in self.anios], self.seleccionar_anio
        )

        self.c_materia = self.crear_combo(
            formulario, "Materia:", [], None
        )

        self.e_profesor = self.crear_entrada(formulario, "Profesor:")
        self.e_nota = self.crear_entrada(formulario, "Nota (0-100):")
        self.e_fecha = self.crear_entrada(formulario, "Fecha de entrega (DD/MM/AAAA):")

        tk.Label(
            formulario, text="Estado:", bg=PANEL, fg=TEXTO,
            font=FUENTE_B, anchor="w"
        ).pack(fill="x", padx=18, pady=(8, 2))
        self.c_estado = ttk.Combobox(
            formulario, values=["Pendiente", "Completada"],
            state="readonly", font=("Segoe UI", 10)
        )
        self.c_estado.set("Pendiente")
        self.c_estado.pack(fill="x", padx=18)

        botones = tk.Frame(formulario, bg=PANEL)
        botones.pack(fill="x", padx=18, pady=14)
        botones.columnconfigure(0, weight=1)
        botones.columnconfigure(1, weight=1)
        self.b_registrar = self.boton(
            botones, "💾 Registrar", self.registrar, AZUL
        )
        self.b_registrar.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.boton(
            botones, "✏️ Cargar para editar", self.cargar_para_editar, NARANJA
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)
        self.boton(
            botones, "🧹 Limpiar", self.limpiar, VERDE
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.boton(
            botones, "🗑 Eliminar", self.eliminar, ROJO
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)

        self.lbl_mensaje = tk.Label(
            formulario, text="", bg=PANEL, fg=VERDE,
            font=FUENTE_B, wraplength=285, justify="left"
        )
        self.lbl_mensaje.pack(fill="x", padx=18, pady=5)

        # Tabla de registros
        panel_tabla = tk.Frame(
            cuerpo, bg=PANEL, highlightbackground=LINEA, highlightthickness=1
        )
        panel_tabla.grid(row=0, column=1, sticky="nsew")
        tk.Label(
            panel_tabla, text="📚 Materias y registros guardados",
            bg=PANEL, fg=TEXTO, font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=16, pady=(15, 8))

        barra = tk.Frame(panel_tabla, bg=PANEL)
        barra.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(
            barra, text="Buscar:", bg=PANEL, fg=SUAVE, font=FUENTE
        ).pack(side="left", padx=(0, 8))
        self.busqueda = tk.StringVar()
        self.busqueda.trace_add("write", lambda *_: self.mostrar_registros())
        tk.Entry(
            barra, textvariable=self.busqueda, font=("Segoe UI", 10),
            relief="solid", bd=1
        ).pack(side="left", fill="x", expand=True, ipady=5)

        marco = tk.Frame(panel_tabla, bg=PANEL)
        marco.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        columnas = ("anio", "materia", "profesor", "nota", "fecha", "estado")
        self.tabla = ttk.Treeview(
            marco, columns=columnas, show="headings", selectmode="browse"
        )
        encabezados = [
            ("anio", "Año", 105),
            ("materia", "Materia", 190),
            ("profesor", "Profesor", 130),
            ("nota", "Nota", 55),
            ("fecha", "Entrega", 100),
            ("estado", "Estado", 95)
        ]
        for col, titulo, ancho in encabezados:
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor="w")
        self.tabla.tag_configure("Pendiente", background="#FFF6D6")
        self.tabla.tag_configure("Completada", background="#E1F7EB")
        self.tabla.tag_configure("Vencida", background="#FDE3E3")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        pie = tk.Frame(self, bg="#F5F9FF")
        pie.pack(fill="x", side="bottom")
        tk.Label(
            pie, text="● PostgreSQL conectado  •  Gestor de Estudios",
            bg="#F5F9FF", fg=SUAVE, font=("Segoe UI", 9)
        ).pack(side="left", padx=14, pady=7)
        self.lbl_reloj = tk.Label(
            pie, text="", bg="#F5F9FF", fg=SUAVE, font=("Segoe UI", 9)
        )
        self.lbl_reloj.pack(side="right", padx=14)

        if self.anios:
            self.c_anio.current(0)
            self.seleccionar_anio()

    def crear_combo(self, padre, etiqueta, valores, callback):
        tk.Label(
            padre, text=etiqueta, bg=PANEL, fg=TEXTO,
            font=FUENTE_B, anchor="w"
        ).pack(fill="x", padx=18, pady=(7, 2))
        combo = ttk.Combobox(
            padre, values=valores, state="readonly", font=("Segoe UI", 10)
        )
        combo.pack(fill="x", padx=18)
        if callback:
            combo.bind("<<ComboboxSelected>>", callback)
        return combo

    def crear_entrada(self, padre, etiqueta):
        tk.Label(
            padre, text=etiqueta, bg=PANEL, fg=TEXTO,
            font=FUENTE_B, anchor="w"
        ).pack(fill="x", padx=18, pady=(8, 2))
        entrada = tk.Entry(
            padre, font=("Segoe UI", 10), relief="solid", bd=1
        )
        entrada.pack(fill="x", padx=18, ipady=4)
        return entrada

    def boton(self, padre, texto, comando, color):
        return tk.Button(
            padre, text=texto, command=comando, bg=color, fg="white",
            activebackground=color, activeforeground="white",
            relief="flat", bd=0, cursor="hand2",
            font=FUENTE_B, padx=5, pady=8
        )

    def seleccionar_anio(self, evento=None):
        nombre = self.c_anio.get()
        anio = next((a for a in self.anios if a[2] == nombre), None)
        self.materia_ids = {}
        if not anio:
            self.c_materia["values"] = []
            self.c_materia.set("")
            return
        try:
            self.materias_catalogo = obtener_materias(anio[0])
            nombres = []
            for materia_id, nombre_materia in self.materias_catalogo:
                nombres.append(nombre_materia)
                self.materia_ids[nombre_materia] = materia_id
            self.c_materia["values"] = nombres
            self.c_materia.set("")
            self.mensaje(f"Materias de {nombre} cargadas.")
        except Exception as error:
            messagebox.showerror("Error", f"No se pudieron cargar las materias:\n{error}")

    def cargar_tabla(self):
        try:
            self.registros = obtener_registros()
            self.mostrar_registros()
        except Exception as error:
            messagebox.showerror("Error", f"No se pudieron leer los registros:\n{error}")

    def mostrar_registros(self):
        if not hasattr(self, "tabla"):
            return
        filtro = self.busqueda.get().strip().casefold()
        self.tabla.delete(*self.tabla.get_children())
        for registro in getattr(self, "registros", []):
            registro_id, anio, materia, profesor, nota, fecha, estado, materia_id = registro
            if filtro and filtro not in " ".join(
                [anio, materia, profesor, estado]
            ).casefold():
                continue
            estado_mostrar = estado_real(estado, fecha)
            self.tabla.insert(
                "", "end", iid=str(registro_id),
                values=(
                    anio, materia, profesor, f"{float(nota):g}",
                    fecha.strftime("%d/%m/%Y"), estado_mostrar
                ),
                tags=(estado_mostrar,)
            )

    def registrar(self):
        nombre_materia = self.c_materia.get().strip()
        profesor = self.e_profesor.get().strip()
        nota_texto = self.e_nota.get().strip().replace(",", ".")
        fecha_texto = self.e_fecha.get().strip()
        estado = self.c_estado.get()

        if not nombre_materia or not profesor or not nota_texto or not fecha_texto:
            self.mensaje("Completa todos los campos.", True)
            return

        materia_id = self.materia_ids.get(nombre_materia)
        if not materia_id:
            self.mensaje("Selecciona un año y una materia válidos.", True)
            return

        try:
            nota = float(nota_texto)
            fecha = datetime.strptime(fecha_texto, "%d/%m/%Y").date()
            if not 0 <= nota <= 100:
                raise ValueError("La nota debe estar entre 0 y 100.")
        except ValueError as error:
            self.mensaje(
                f"Revisa la nota y la fecha DD/MM/AAAA. {error}", True
            )
            return

        conexion = conectar_db()
        try:
            with conexion.cursor() as cursor:
                if self.edit_id:
                    cursor.execute("""
                        UPDATE registros_estudio
                        SET materia_id=%s, profesor=%s, nota=%s,
                            fecha_entrega=%s, estado=%s
                        WHERE id=%s
                    """, (materia_id, profesor, nota, fecha, estado, self.edit_id))
                else:
                    cursor.execute("""
                        INSERT INTO registros_estudio
                            (materia_id, profesor, nota, fecha_entrega, estado)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (materia_id, profesor, nota, fecha, estado))
            conexion.commit()
        except Exception as error:
            conexion.rollback()
            messagebox.showerror("Error al guardar", str(error))
            return
        finally:
            conexion.close()

        self.limpiar()
        self.cargar_tabla()
        self.mensaje("Registro guardado correctamente.")

    def cargar_para_editar(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            self.mensaje("Selecciona un registro de la tabla.", True)
            return
        registro_id = int(seleccion[0])
        registro = next((r for r in self.registros if r[0] == registro_id), None)
        if not registro:
            return

        _, anio, materia, profesor, nota, fecha, estado, materia_id = registro
        self.c_anio.set(anio)
        self.seleccionar_anio()
        self.c_materia.set(materia)
        self.e_profesor.delete(0, tk.END)
        self.e_profesor.insert(0, profesor)
        self.e_nota.delete(0, tk.END)
        self.e_nota.insert(0, f"{float(nota):g}")
        self.e_fecha.delete(0, tk.END)
        self.e_fecha.insert(0, fecha.strftime("%d/%m/%Y"))
        self.c_estado.set(estado)
        self.edit_id = registro_id
        self.b_registrar.config(text="💾 Guardar cambios")
        self.mensaje("Editando registro seleccionado.")

    def eliminar(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            self.mensaje("Selecciona un registro para eliminar.", True)
            return
        registro_id = int(seleccion[0])
        if not messagebox.askyesno(
            "Confirmar eliminación",
            "¿Seguro que deseas eliminar el registro seleccionado?"
        ):
            return
        conexion = conectar_db()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM registros_estudio WHERE id = %s",
                    (registro_id,)
                )
            conexion.commit()
        except Exception as error:
            conexion.rollback()
            messagebox.showerror("Error", str(error))
            return
        finally:
            conexion.close()
        self.cargar_tabla()
        self.limpiar()
        self.mensaje("Registro eliminado.")

    def limpiar(self):
        self.c_anio.set("")
        self.c_materia.set("")
        self.c_materia["values"] = []
        for entrada in (self.e_profesor, self.e_nota, self.e_fecha):
            entrada.delete(0, tk.END)
        self.c_estado.set("Pendiente")
        self.edit_id = None
        self.b_registrar.config(text="💾 Registrar")
        self.mensaje("")

    def mensaje(self, texto, error=False):
        if hasattr(self, "lbl_mensaje"):
            self.lbl_mensaje.config(
                text=texto, fg=ROJO if error else "#146C3F"
            )

    def actualizar_reloj(self):
        if hasattr(self, "lbl_reloj"):
            self.lbl_reloj.config(text=datetime.now().strftime("%d/%m/%Y %H:%M"))
            self.after(1000, self.actualizar_reloj)


if __name__ == "__main__":
    try:
        App().mainloop()
    except psycopg2.OperationalError as error:
        messagebox.showerror(
            "Error de conexión",
            "No se pudo conectar con PostgreSQL.\n"
            "Revisa que el servidor esté iniciado, que exista la base de datos "
            "y que la contraseña sea correcta.\n\n" + str(error)
        )
