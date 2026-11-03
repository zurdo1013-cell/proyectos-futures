import json
import os
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

try:
    from plyer import notification
except ImportError:
    notification = None

BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(BASE, "estudios.json")
ARCHIVO_VIEJO = os.path.join(BASE, "estudios.txt")  

FORMATO_FECHA = "%d/%m/%Y"

FONDO = "#000000"
PANEL = "#000000"
CAMPO = "#272525"
TEXTO = "#48EE06"
TEXTO_SUAVE = "#5D5D66"
TITULO = "#37F801"
VERDE = "#0C09CA"
PELIGRO = "#F50101"
AZUL = "#1005A5"
NEUTRO = "#053A85"

materias = []
avisos_mostrados = set()

def parsear_fecha(texto):
    return datetime.strptime(texto, FORMATO_FECHA).date()


def estado_real(m):
    """'Vencida' se calcula al vuelo; en el archivo solo se guarda Pendiente/Completada."""
    if m["estado"] == "Completada":
        return "Completada"
    if parsear_fecha(m["fecha"]) < date.today():
        return "Vencida"
    return "Pendiente"


def formatear_nota(nota):
    return f"{nota:g}"


def validar_registro(materia, profesor, nota, fecha, estado):
    """Devuelve un dict limpio o None si los datos no son válidos."""
    try:
        nota = float(str(nota).replace(",", "."))
        fecha = parsear_fecha(fecha)
    except (ValueError, TypeError):
        return None

    if not materia or not profesor:
        return None

    return {
        "materia": materia,
        "profesor": profesor,
        "nota": nota,
        "fecha": fecha.strftime(FORMATO_FECHA),
        "estado": "Completada" if estado == "Completada" else "Pendiente",
    }

def cargar():
    datos = []

    try:
        if os.path.exists(ARCHIVO):
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    registro = validar_registro(
                        item.get("materia", ""),
                        item.get("profesor", ""),
                        item.get("nota", ""),
                        item.get("fecha", ""),
                        item.get("estado", ""),
                    )
                    if registro:
                        datos.append(registro)

        elif os.path.exists(ARCHIVO_VIEJO):  # migración desde estudios.txt
            with open(ARCHIVO_VIEJO, "r", encoding="utf-8") as f:
                for linea in f:
                    partes = linea.strip().split("|")
                    if len(partes) == 5:
                        registro = validar_registro(*partes)
                        if registro:
                            datos.append(registro)

    except (OSError, json.JSONDecodeError, AttributeError) as error:
        messagebox.showerror("Error", f"No se pudo leer el archivo:\n{error}")

    return datos


def guardar():
    temporal = ARCHIVO + ".tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(materias, f, ensure_ascii=False, indent=2)
        os.replace(temporal, ARCHIVO)  
    except OSError as error:
        messagebox.showerror("Error", f"No se pudieron guardar los datos:\n{error}")



def mostrar_mensaje(texto, color=VERDE):
    etiqueta_mensaje.config(text=texto, fg=color)
    ventana.after(4000, lambda: etiqueta_mensaje.config(text=""))


def limpiar_formulario():
    for campo in (entrada_materia, entrada_profesor, entrada_nota, entrada_fecha):
        campo.delete(0, tk.END)
    entrada_materia.focus()


def actualizar():
    """Redibuja la tabla respetando siempre el texto de búsqueda actual."""
    texto = entrada_busqueda.get().strip().casefold()

    tabla.delete(*tabla.get_children())

    for m in materias:
        if texto and texto not in m["materia"].casefold() \
                and texto not in m["profesor"].casefold():
            continue

        estado = estado_real(m)
        tabla.insert(
            "",
            tk.END,
            iid=m["materia"].casefold(),
            values=(
                m["materia"],
                m["profesor"],
                formatear_nota(m["nota"]),
                m["fecha"],
                estado,
            ),
            tags=(estado.lower(),),
        )

    estados = [estado_real(m) for m in materias]
    etiqueta_resumen.config(
        text=(
            f"Total: {len(materias)}     "
            f"Pendientes: {estados.count('Pendiente')}     "
            f"Vencidas: {estados.count('Vencida')}     "
            f"Completadas: {estados.count('Completada')}"
        )
    )


def registrar():
    materia = entrada_materia.get().strip()
    profesor = entrada_profesor.get().strip()
    nota_texto = entrada_nota.get().strip()
    fecha_texto = entrada_fecha.get().strip()

    if not (materia and profesor and nota_texto and fecha_texto):
        messagebox.showwarning("Campos incompletos", "Completa todos los campos.")
        return

    registro = validar_registro(materia, profesor, nota_texto, fecha_texto, "Pendiente")

    if registro is None or not 0 <= registro["nota"] <= 100:
        messagebox.showerror(
            "Datos inválidos",
            "La nota debe estar entre 0 y 100 y la fecha debe usar DD/MM/AAAA.",
        )
        return

    if any(m["materia"].casefold() == materia.casefold() for m in materias):
        messagebox.showwarning("Materia existente", "Esa materia ya está registrada.")
        return

    materias.append(registro)
    guardar()
    limpiar_formulario()
    actualizar()
    mostrar_mensaje(f"✔ {materia} registrada correctamente.")
    revisar_fechas()


def eliminar():
    seleccion = tabla.selection()

    if not seleccion:
        messagebox.showwarning("Selecciona una materia", "Selecciona una fila para eliminar.")
        return

    clave = seleccion[0]
    nombre = tabla.set(clave, "Materia")

    if not messagebox.askyesno("Confirmar", f"¿Eliminar la materia {nombre}?"):
        return

    materias[:] = [m for m in materias if m["materia"].casefold() != clave]
    guardar()
    actualizar()
    mostrar_mensaje(f"{nombre} eliminada.", TEXTO_SUAVE)


def cambiar_estado():
    seleccion = tabla.selection()

    if not seleccion:
        messagebox.showwarning("Selecciona una materia", "Selecciona una fila.")
        return

    clave = seleccion[0]

    for m in materias:
        if m["materia"].casefold() == clave:
            m["estado"] = "Pendiente" if m["estado"] == "Completada" else "Completada"
            break

    guardar()
    actualizar()
    tabla.selection_set(clave) 
def editar(evento=None):
    seleccion = tabla.selection()

    if not seleccion:
        messagebox.showwarning("Selecciona una materia", "Selecciona una fila para editar.")
        return

    valores = tabla.item(seleccion[0], "values")
    original = None

    for m in materias:
        if (
            m["materia"] == valores[0]
            and m["profesor"] == valores[1]
            and m["fecha"] == valores[3]
        ):
            original = m
            break

    if original is None:
        return

    dialogo = tk.Toplevel(ventana)
    dialogo.title("Editar materia")
    dialogo.configure(bg=PANEL)
    dialogo.transient(ventana)
    dialogo.resizable(False, False)

    datos = (
        ("materia", "Materia", original["materia"]),
        ("profesor", "Profesor", original["profesor"]),
        ("nota", "Nota (0-100)", original["nota"]),
        ("fecha", "Entrega (DD/MM/AAAA)", original["fecha"]),
    )
    campos = {}

    for fila, (nombre, etiqueta, valor) in enumerate(datos):
        tk.Label(
            dialogo, text=etiqueta, bg=PANEL, fg=FONDO, font=("Segoe UI", 10)
        ).grid(row=fila, column=0, sticky="w", padx=(15, 8), pady=8)

        entrada = tk.Entry(
            dialogo,
            width=30,
            bg="#0F172A",
            fg=FONDO,
            insertbackground="white",
            relief="flat",
            font=("Segoe UI", 11),
        )
        entrada.insert(0, valor)
        entrada.grid(row=fila, column=1, padx=(0, 15), pady=8, ipady=5)
        campos[nombre] = entrada

    def guardar_cambios(evento=None):
        materia = campos["materia"].get().strip()
        profesor = campos["profesor"].get().strip()
        nota_texto = campos["nota"].get().strip()
        fecha_texto = campos["fecha"].get().strip()

        if not (materia and profesor and nota_texto and fecha_texto):
            messagebox.showwarning(
                "Campos incompletos", "Completa todos los campos.", parent=dialogo
            )
            return

        try:
            nota = float(nota_texto.replace(",", "."))
            if nota < 0 or nota > 100:
                raise ValueError
            fecha = datetime.strptime(fecha_texto, "%d/%m/%Y").date()
        except ValueError:
            messagebox.showerror(
                "Datos inválidos",
                "La nota debe estar entre 0 y 100 y la fecha debe usar DD/MM/AAAA.",
                parent=dialogo,
            )
            return

        if any(
            m is not original and m["materia"].casefold() == materia.casefold()
            for m in materias
        ):
            messagebox.showwarning(
                "Materia existente", "Ya existe otra materia con ese nombre.", parent=dialogo
            )
            return

        original["materia"] = materia
        original["profesor"] = profesor
        original["nota"] = str(nota)
        original["fecha"] = fecha.strftime("%d/%m/%Y")

        guardar()
        actualizar()
        dialogo.destroy()

    marco_botones = tk.Frame(dialogo, bg=PANEL)
    marco_botones.grid(row=len(datos), column=0, columnspan=2, pady=(5, 15))

    tk.Button(
        marco_botones, text="Guardar cambios", command=guardar_cambios,
        bg=VERDE, fg="white", relief="flat", cursor="hand2",
        font=("Segoe UI", 10, "bold"), padx=12, pady=8
    ).pack(side="left", padx=4)

    tk.Button(
        marco_botones, text="Cancelar", command=dialogo.destroy,
        bg=AZUL, fg="white", relief="flat", cursor="hand2",
        font=("Segoe UI", 10, "bold"), padx=12, pady=8
    ).pack(side="left", padx=4)

    dialogo.bind("<Return>", guardar_cambios)
    dialogo.bind("<Escape>", lambda e: dialogo.destroy())

    dialogo.update_idletasks()
    x = ventana.winfo_x() + (ventana.winfo_width() - dialogo.winfo_width()) // 2
    y = ventana.winfo_y() + (ventana.winfo_height() - dialogo.winfo_height()) // 2
    dialogo.geometry(f"+{x}+{y}")

    dialogo.grab_set()
    campos["materia"].focus()

def mostrar_todas():
    entrada_busqueda.delete(0, tk.END)
    actualizar()


def notificar(mensaje):
    if notification is None:
        print("plyer no está instalado:", mensaje)
        return

    try:
        notification.notify(
            title="Recordatorio académico",
            message=mensaje,
            timeout=10,
            app_name="Organizador de Estudios",
        )
    except Exception as error:
        print("No se pudo mostrar la notificación:", error)


def revisar_fechas():
    """Revisa las fechas UNA vez (no se reprograma sola)."""
    hoy = date.today()

    for m in materias:
        if m["estado"] == "Completada":
            continue

        dias = (parsear_fecha(m["fecha"]) - hoy).days
        clave = (m["materia"], m["fecha"], dias)

        if dias in (7, 3, 1):
            mensaje = f"{m['materia']}: entrega dentro de {dias} día(s)."
        elif dias == 0:
            mensaje = f"¡Hoy vence la entrega de {m['materia']}!"
        elif dias < 0:
            mensaje = f"La entrega de {m['materia']} está vencida."
        else:
            continue

        if clave not in avisos_mostrados:
            notificar(mensaje)
            avisos_mostrados.add(clave)


def ciclo_revision():
    """Único lugar donde se programa el bucle de 60 s."""
    revisar_fechas()
    actualizar()  # refresca "Vencida" si cambió el día
    ventana.after(60000, ciclo_revision)


ventana = tk.Tk()
ventana.title("ORGANIZADOR DE ESTUDIOS")
ventana.geometry("1050x680")
ventana.minsize(900, 600)
ventana.configure(bg=FONDO)

estilo = ttk.Style()
estilo.theme_use("clam")
estilo.configure(
    "Treeview",
    background=PANEL,
    foreground=TEXTO,
    fieldbackground=PANEL,
    rowheight=30,
    font=("Segoe UI", 10),
)
estilo.configure(
    "Treeview.Heading",
    background=AZUL,
    foreground="white",
    font=("Segoe UI", 10, "bold"),
)
estilo.map("Treeview", background=[("selected", "#334155")])
encabezado = tk.Frame(ventana, bg=FONDO)
encabezado.pack(fill="x", padx=25, pady=(20, 10))

tk.Label(
    encabezado,
    text="ORGANIZADOR DE ESTUDIOS",
    font=("Segoe UI", 22, "bold"),
    bg=FONDO,
    fg=TITULO,
).pack(fill="x", pady=5)

tk.Label(
    encabezado,
    text="Organiza tus materias, calificaciones y fechas de entrega",
    font=("Segoe UI", 10),
    bg=FONDO,
    fg=TEXTO_SUAVE,
).pack(anchor="center", pady=(4, 0))

formulario = tk.LabelFrame(
    ventana,
    text=" Datos de la materia ",
    bg=PANEL,
    fg=TEXTO,
    font=("Segoe UI", 11, "bold"),
    padx=15,
    pady=12,
)
formulario.pack(fill="x", padx=25, pady=10)

for columna in range(4):
    formulario.columnconfigure(columna, weight=1)


def crear_campo(texto, fila, columna):
    tk.Label(
        formulario, text=texto, bg=PANEL, fg=TEXTO, font=("Segoe UI", 10)
    ).grid(row=fila, column=columna, sticky="w", padx=6, pady=(4, 3))

    campo = tk.Entry(
        formulario,
        bg=CAMPO,
        fg=TEXTO,
        insertbackground="white",
        relief="flat",
        font=("Segoe UI", 11),
    )
    campo.grid(
        row=fila + 1, column=columna, sticky="ew", padx=6, pady=(0, 8), ipady=6
    )
    campo.bind("<Return>", lambda evento: registrar())  # Enter registra
    return campo


entrada_materia = crear_campo("Materia", 0, 0)
entrada_profesor = crear_campo("Profesor", 0, 1)
entrada_nota = crear_campo("Nota (0-100)", 0, 2)
entrada_fecha = crear_campo("Entrega (DD/MM/AAAA)", 0, 3)

botones = tk.Frame(formulario, bg=PANEL)
botones.grid(row=2, column=0, columnspan=4, pady=5)


def crear_boton(contenedor, texto, comando, color):
    return tk.Button(
        contenedor,
        text=texto,
        command=comando,
        bg=color,
        fg="white",
        activebackground=color,
        activeforeground="white",
        relief="flat",
        cursor="hand2",
        font=("Segoe UI", 10, "bold"),
        padx=12,
        pady=8,
    )


crear_boton(botones, "Registrar", registrar, VERDE).pack(side="left", padx=4)
crear_boton(botones, "Limpiar", limpiar_formulario, NEUTRO).pack(side="left", padx=4)
crear_boton(botones, "Eliminar", eliminar, PELIGRO).pack(side="left", padx=4)
crear_boton(botones, "Completar / Pendiente", cambiar_estado, AZUL).pack(side="left", padx=4)
crear_boton(botones, "Editar", editar, "#E28A07").pack(side="left", padx=4)
etiqueta_mensaje = tk.Label(
    formulario, text="", bg=PANEL, fg=VERDE, font=("Segoe UI", 10, "bold")
)
etiqueta_mensaje.grid(row=3, column=0, columnspan=4)


buscador = tk.Frame(ventana, bg=FONDO)
buscador.pack(fill="x", padx=25, pady=(5, 10))

tk.Label(
    buscador,
    text="Buscar materia o profesor:",
    bg=FONDO,
    fg=TEXTO,
    font=("Segoe UI", 10),
).pack(side="left", padx=(0, 8))

entrada_busqueda = tk.Entry(
    buscador,
    bg=CAMPO,
    fg=TEXTO,
    insertbackground="white",
    relief="flat",
    font=("Segoe UI", 11),
)
entrada_busqueda.pack(side="left", fill="x", expand=True, ipady=6)
entrada_busqueda.bind("<KeyRelease>", lambda evento: actualizar())  # filtro en vivo

crear_boton(buscador, "Mostrar todas", mostrar_todas, NEUTRO).pack(side="left", padx=5)

contenedor_tabla = tk.Frame(ventana, bg=PANEL)
contenedor_tabla.pack(fill="both", expand=True, padx=25, pady=(0, 10))

columnas = ("Materia", "Profesor", "Nota", "Entrega", "Estado")

tabla = ttk.Treeview(
    contenedor_tabla, columns=columnas, show="headings", selectmode="browse"
)

for columna in columnas:
    tabla.heading(columna, text=columna)
    tabla.column(columna, width=150, anchor="center")

tabla.column("Materia", width=220)
tabla.column("Profesor", width=180)

barra = ttk.Scrollbar(contenedor_tabla, orient="vertical", command=tabla.yview)
tabla.configure(yscrollcommand=barra.set)

tabla.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
barra.pack(side="right", fill="y", padx=(0, 8), pady=8)

tabla.tag_configure("completada", foreground="#06BB06")
tabla.tag_configure("vencida", foreground="#F50000")
tabla.tag_configure("pendiente", foreground="#F5B001")


pie = tk.Frame(ventana, bg=FONDO)
pie.pack(fill="x", padx=25, pady=(0, 15))

etiqueta_resumen = tk.Label(
    pie, text="", bg=FONDO, fg=TEXTO, font=("Segoe UI", 10, "bold")
)
etiqueta_resumen.pack(side="left")

tk.Label(
    pie,
    text="Los recordatorios funcionan mientras el programa está abierto.",
    bg=FONDO,
    fg=TEXTO_SUAVE,
    font=("Segoe UI", 9),
).pack(side="right")

materias.extend(cargar())
if os.path.exists(ARCHIVO_VIEJO) and not os.path.exists(ARCHIVO):
    guardar() 

actualizar()
ventana.after(1000, ciclo_revision)
ventana.mainloop()