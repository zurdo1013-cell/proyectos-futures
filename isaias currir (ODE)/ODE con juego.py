import calendar
import csv
import hashlib
import hmac
import io
import json
import os
import random
import sys
import time
import tkinter as tk
import psycopg2
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk


try:
    from plyer import notification
except ImportError:
    notification = None

# Para fotos de perfil:  pip install pillow
try:
    from PIL import Image, ImageDraw, ImageOps, ImageTk
except ImportError:
    Image = None

DB_CONFIG = {
    "host": "localhost",
    "port": "5433",
    "database": "organizador",
    "user": "postgres",
    # Mejor: definir la variable de entorno ODE_DB_PASS y no dejar la clave en el código.
    "password": os.environ.get("ODE_DB_PASS", "446544"),
}
FORMATO_FECHA = "%d/%m/%Y"


SESION = {"id": None, "usuario": ""}

TABLAS_USUARIO = ("registros_estudio", "perfil", "aviso", "asistencia", "horario", "comentario")

FONDO = "#FFFFFF"
PANEL = "#03324D"
LINEA = "#0B8A6A"
TEXTO = "#F0F1F7"
SUAVE = "#01030C"


AZUL = "#050224"
AZUL_SB = "#0E90B1"
VERDE = "#106805"
ROJO = "#7E0606"
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
    "rojo": "#5E0404"
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
     ("Comentarios", "💬", "Comentarios"),
       ("Juegos", "🎮", "Juegos")]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

# ---- personalización del perfil
AVATARES = ["🧑", "👩", "👨", "🎓", "🦊", "🐱", "🐶", "🦉", "🚀", "🎮", "🤖", "🌟"]
COLORES_AVATAR = {"Azul": "#dbe7ff", "Verde": "#c9f2dc", "Morado": "#e2d6ff",
                  "Naranja": "#ffe0bf", "Rosa": "#ffd6e7", "Gris": "#e1e5ee"}
LEMA_DEFECTO = "Mantente al día con tu recorrido académico."


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


def asegurar_columna(cursor, tabla, columna, definicion):
    """Agrega la columna si la tabla ya existía sin ella (sirve en cualquier versión de PostgreSQL)."""
    cursor.execute("SELECT 1 FROM information_schema.columns "
                   "WHERE table_name = %s AND column_name = %s", (tabla, columna))
    if not cursor.fetchone():
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def preparar_bd():
    """Crea las tablas propias de la app (el catálogo anios/materias ya lo tienes)."""
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuario (
                    id SERIAL PRIMARY KEY,
                    usuario VARCHAR(50) NOT NULL UNIQUE,
                    sal VARCHAR(64) NOT NULL,
                    clave_hash VARCHAR(128) NOT NULL,
                    creado TIMESTAMP NOT NULL DEFAULT NOW()
                );
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jardin (
                    usuario_id INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
                    monedas INTEGER NOT NULL DEFAULT 0,
                    sesiones INTEGER NOT NULL DEFAULT 0,
                    minutos INTEGER NOT NULL DEFAULT 0,
                    plantas TEXT NOT NULL DEFAULT ''
                )
            """)
            # Cada tabla de datos queda ligada a su dueño. Los datos que ya tenías
            # (sin dueño) se asignan a la primera cuenta que se cree.
            for tabla in TABLAS_USUARIO:
                asegurar_columna(cursor, tabla, "usuario_id",
                                 "INTEGER REFERENCES usuario(id) ON DELETE CASCADE")
            # Personalización del perfil (avatar, color, lema, biografía y foto)
            for col, defin in (("avatar", "VARCHAR(8) DEFAULT '🧑'"),
                               ("color_avatar", "VARCHAR(20) DEFAULT 'Azul'"),
                               ("bio", "TEXT"),
                               ("lema", "VARCHAR(120)"),
                               ("foto", "BYTEA")):
                asegurar_columna(cursor, "perfil", col, defin)
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


# ------------------------------------------------------------------ PERFIL
def cargar_perfil():
    fila = consultar_seguro(
        "SELECT nombre, COALESCE(carrera,''), COALESCE(anio_cursa,''), COALESCE(correo,''), "
        "COALESCE(avatar,'🧑'), COALESCE(color_avatar,'Azul'), COALESCE(bio,''), "
        "COALESCE(lema,'') FROM perfil WHERE usuario_id = %s", (SESION["id"],))
    if fila:
        n, c, a, e, av, col, bio, lema = fila[0]
        return {"nombre": n, "carrera": c, "anio_cursa": a, "correo": e,
                "avatar": av, "color_avatar": col, "bio": bio, "lema": lema}
    return {"nombre": SESION["usuario"] or "Estudiante", "carrera": "Ingeniería Informática",
            "anio_cursa": "", "correo": "", "avatar": "🧑", "color_avatar": "Azul",
            "bio": "", "lema": ""}


def guardar_perfil_db(d):
    con = conectar_db()
    try:
        with con.cursor() as cur:
            cur.execute("UPDATE perfil SET nombre=%s, carrera=%s, anio_cursa=%s, correo=%s, "
                        "avatar=%s, color_avatar=%s, bio=%s, lema=%s WHERE usuario_id=%s",
                        (d["nombre"], d["carrera"], d["anio_cursa"], d["correo"], d["avatar"],
                         d["color_avatar"], d["bio"], d["lema"], SESION["id"]))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO perfil (id, usuario_id, nombre, carrera, anio_cursa, "
                            "correo, avatar, color_avatar, bio, lema) "
                            "SELECT COALESCE(MAX(id), 0) + 1, %s, %s, %s, %s, %s, %s, %s, %s, %s "
                            "FROM perfil",
                            (SESION["id"], d["nombre"], d["carrera"], d["anio_cursa"],
                             d["correo"], d["avatar"], d["color_avatar"], d["bio"], d["lema"]))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def cargar_foto_db():
    fila = consultar_seguro("SELECT foto FROM perfil WHERE usuario_id = %s", (SESION["id"],))
    return bytes(fila[0][0]) if fila and fila[0][0] else None


def guardar_foto_db(datos):
    ejecutar("UPDATE perfil SET foto = %s WHERE usuario_id = %s",
             (psycopg2.Binary(datos) if datos else None, SESION["id"]))


def procesar_foto(ruta):
    """Abre cualquier imagen, la endereza, la recorta cuadrada y la deja en 256x256 PNG."""
    img = Image.open(ruta)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (256, 256), Image.LANCZOS)
    salida = io.BytesIO()
    img.save(salida, format="PNG")
    return salida.getvalue()


def foto_circular(datos, tam):
    grande = tam * 4                                    # máscara suavizada
    img = Image.open(io.BytesIO(datos)).convert("RGBA").resize((tam, tam), Image.LANCZOS)
    mascara = Image.new("L", (grande, grande), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, grande - 1, grande - 1), fill=255)
    img.putalpha(mascara.resize((tam, tam), Image.LANCZOS))
    return ImageTk.PhotoImage(img)


def dibujar_avatar(cv, tam, emoji, color_nombre, foto=None):
    """Dibuja la foto en círculo; si no hay foto, el avatar emoji sobre un círculo de color."""
    cv.delete("all")
    if foto and Image is not None:
        try:
            cv.imagen = foto_circular(foto, tam)       # referencia para que no se borre
            cv.create_image(tam // 2, tam // 2, image=cv.imagen)
            return
        except Exception as error:
            print("No se pudo mostrar la foto:", error)
    color = COLORES_AVATAR.get(color_nombre, COLORES_AVATAR["Azul"])
    cv.create_oval(2, 2, tam - 2, tam - 2, fill=color, outline=color)
    cv.create_text(tam // 2, tam // 2 + 1, text=emoji or "🧑",
                   font=("Segoe UI Emoji", int(tam * 0.4)))


# ------------------------------------------------------- REGISTROS DE ESTUDIO
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
    """Lee desde PostgreSQL los registros del usuario con sesión abierta."""
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
                WHERE r.usuario_id = %s
                ORDER BY a.numero, m.semestre, m.nombre
            """, (SESION["id"],))
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
    """Guarda los registros del usuario en PostgreSQL, sin tocar el catálogo ni a otros usuarios."""
    conexion = conectar_db()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM registros_estudio WHERE usuario_id = %s",
                           (SESION["id"],))
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
                        (materia_id, profesor, nota, fecha_entrega, estado, usuario_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (fila[0], registro["profesor"], registro["nota"],
                      parsear_fecha(registro["fecha"]), registro["estado"], SESION["id"]))
        conexion.commit()
    except Exception as error:
        conexion.rollback()
        messagebox.showerror("Error de PostgreSQL",
                             f"No se pudieron guardar los datos:\n{error}")
    finally:
        conexion.close()


# ------------------------------------------------------- CUENTAS Y CONTRASEÑAS
ITERACIONES = 200_000


def hashear_clave(clave, sal=None):
    """La contraseña nunca se guarda: solo un hash PBKDF2 con sal aleatoria."""
    sal = sal or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal),
                            ITERACIONES).hex()
    return sal, h


def verificar_clave(clave, sal, hash_guardado):
    return hmac.compare_digest(hashear_clave(clave, sal)[1], hash_guardado)


def hay_usuarios():
    return consultar("SELECT COUNT(*) FROM usuario")[0][0] > 0


def crear_usuario(usuario, clave, nombre):
    """Crea la cuenta y su perfil. La primera cuenta adopta los datos que ya existían."""
    sal, h = hashear_clave(clave)
    con = conectar_db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM usuario")
            primero = cur.fetchone()[0] == 0
            cur.execute("SELECT 1 FROM usuario WHERE LOWER(usuario) = LOWER(%s)", (usuario,))
            if cur.fetchone():
                raise ValueError("Ese nombre de usuario ya existe. Elige otro.")
            cur.execute("INSERT INTO usuario (usuario, sal, clave_hash) VALUES (%s, %s, %s) "
                        "RETURNING id", (usuario, sal, h))
            uid = cur.fetchone()[0]
            if primero:
                for tabla in TABLAS_USUARIO:
                    cur.execute(f"UPDATE {tabla} SET usuario_id = %s WHERE usuario_id IS NULL",
                                (uid,))
            cur.execute("SELECT 1 FROM perfil WHERE usuario_id = %s", (uid,))
            if cur.fetchone():
                cur.execute("UPDATE perfil SET nombre = %s WHERE usuario_id = %s", (nombre, uid))
            else:
                cur.execute("INSERT INTO perfil (id, usuario_id, nombre) "
                            "SELECT COALESCE(MAX(id), 0) + 1, %s, %s FROM perfil", (uid, nombre))
        con.commit()
        return uid
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def autenticar(usuario, clave):
    """Devuelve (id, usuario) si los datos son correctos; si no, None."""
    fila = consultar("SELECT id, usuario, sal, clave_hash FROM usuario "
                     "WHERE LOWER(usuario) = LOWER(%s)", (usuario,))
    if not fila:
        hashear_clave(clave)          # mismo tiempo de respuesta si el usuario no existe
        return None
    uid, nombre, sal, h = fila[0]
    return (uid, nombre) if verificar_clave(clave, sal, h) else None


def restablecer_clave_consola(usuario):
    """Recuperación local: python archivo.py --restablecer USUARIO"""
    import getpass
    try:
        fila = consultar("SELECT id FROM usuario WHERE LOWER(usuario) = LOWER(%s)", (usuario,))
        if not fila:
            print(f"No existe el usuario «{usuario}».")
            return
        nueva = getpass.getpass("Nueva contraseña (mínimo 6 caracteres): ")
        if len(nueva) < 6:
            print("La contraseña es demasiado corta.")
            return
        if nueva != getpass.getpass("Repite la nueva contraseña: "):
            print("Las contraseñas no coinciden.")
            return
        sal, h = hashear_clave(nueva)
        ejecutar("UPDATE usuario SET sal = %s, clave_hash = %s WHERE id = %s",
                 (sal, h, fila[0][0]))
        print("Contraseña actualizada. Ya puedes iniciar sesión.")
    except Exception as error:
        print("No se pudo restablecer:", error)


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
    # Texto oscuro: con el TEXTO claro del tema sobre fondo blanco no se leería lo escrito.
    return tk.Entry(padre, textvariable=var, bg="white", fg="#111827", insertbackground="#111827",
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
    """Formulario + tabla con Guardar / Actualizar / Limpiar / Eliminar (tabla en PostgreSQL).
    Cada usuario ve y modifica solo sus propios registros."""

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
            filas = consultar(self.sql, (SESION["id"],))
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
        fila = consultar(f"SELECT {cols} FROM {self.tabla_bd} WHERE id=%s AND usuario_id=%s",
                         (self.id_actual, SESION["id"]))[0]
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
        cols = [c[0] for c in self.campos] + ["usuario_id"]
        self._correr(f"INSERT INTO {self.tabla_bd} ({','.join(cols)}) "
                     f"VALUES ({','.join(['%s'] * len(cols))})",
                     datos + [SESION["id"]], "✔ Guardado.")

    def actualizar(self):
        if self.id_actual is None:
            return self.msg("Selecciona una fila de la tabla para actualizarla.", True)
        datos = self.leer()
        if datos is None:
            return
        sets = ",".join(f"{c[0]}=%s" for c in self.campos)
        self._correr(f"UPDATE {self.tabla_bd} SET {sets} WHERE id=%s AND usuario_id=%s",
                     datos + [self.id_actual, SESION["id"]], "✔ Actualizado.")

    def eliminar(self):
        if self.id_actual is None:
            return self.msg("Selecciona una fila de la tabla para eliminarla.", True)
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro?"):
            self._correr(f"DELETE FROM {self.tabla_bd} WHERE id=%s AND usuario_id=%s",
                         (self.id_actual, SESION["id"]), "Registro eliminado.")


# ------------------------------------------------------------------- LOGIN
class Login(tk.Tk):
    """Inicio de sesión: entrar con una cuenta o crear una nueva."""

    def __init__(self):
        super().__init__()
        self.autenticado, self.usuario, self.uid = False, "", None
        self.intentos, self.bloqueado_hasta = 0, 0.0
        self.registro = not hay_usuarios()
        self.title("Organizador de Estudios(ODE)")
        self.geometry("820x600")
        self.resizable(False, False)
        self.configure(bg=PANEL)

        izq = tk.Frame(self, bg=AZUL_SB, width=300)
        izq.pack(side="left", fill="y")
        izq.pack_propagate(False)
        tk.Label(izq, text="🎓", bg=AZUL_SB, fg="white", font=("Segoe UI Emoji", 54)).pack(
            pady=(120, 6))
        tk.Label(izq, text="Organizador", bg=AZUL_SB, fg="white", font=fnt(22, "bold")).pack()
        tk.Label(izq, text="de Estudios(ODE)", bg=AZUL_SB, fg="#dbe7ff", font=fnt(14)).pack()
        tk.Label(izq, text="Pequeños avances,\ngrandes logros", bg=AZUL_SB, fg="#dbe7ff",
                 font=("Segoe Script", 12, "italic"), justify="center").pack(pady=(26, 0))

        self.der = tk.Frame(self, bg=PANEL)
        self.der.pack(side="left", fill="both", expand=True)
        self.construir_form()
        self.bind("<Return>", self.enviar)

    def campo(self, padre, texto, var, secreto=False):
        etiqueta(padre, texto, fg=TEXTO).pack(fill="x", pady=(8, 0))
        fila = tk.Frame(padre, bg=PANEL)
        fila.pack(fill="x")
        e = entrada(fila, var)
        e.pack(side="left", fill="x", expand=True, ipady=5)
        if secreto:
            e.config(show="•")
            ojo = tk.Label(fila, text="👁", bg=PANEL, fg=TEXTO, cursor="hand2",
                           font=("Segoe UI Emoji", 12))
            ojo.pack(side="left", padx=(6, 0))
            ojo.bind("<Button-1>", lambda ev, e=e: e.config(show="" if e.cget("show") else "•"))
        return e

    def enlace_login(self, padre, texto, comando):
        l = tk.Label(padre, text=texto, bg=PANEL, fg=TEXTO, font=fnt(9, "bold"),
                     cursor="hand2")
        l.pack(pady=(10, 0))
        l.bind("<Button-1>", lambda e: comando())

    def construir_form(self):
        for w in self.der.winfo_children():
            w.destroy()
        caja = tk.Frame(self.der, bg=PANEL)
        caja.place(relx=0.5, rely=0.5, anchor="center", width=340)
        tk.Label(caja, text="Crear cuenta" if self.registro else "Iniciar sesión", bg=PANEL,
                 fg=TEXTO, font=fnt(20, "bold")).pack(anchor="w")
        tk.Label(caja, text=("Elige un usuario y una contraseña. Cada usuario tiene sus "
                             "propios datos." if self.registro
                             else "Ingresa para continuar con tus estudios."),
                 bg=PANEL, fg=TEXTO, font=fnt(9), wraplength=340, justify="left").pack(
            anchor="w", pady=(2, 10))
        self.v_nombre, self.v_usuario = tk.StringVar(), tk.StringVar()
        self.v_clave, self.v_rep = tk.StringVar(), tk.StringVar()
        if self.registro:
            self.campo(caja, "Tu nombre", self.v_nombre)
        self.e_usuario = self.campo(caja, "Usuario", self.v_usuario)
        self.campo(caja, "Contraseña", self.v_clave, secreto=True)
        if self.registro:
            self.campo(caja, "Repetir contraseña", self.v_rep, secreto=True)
        self.lbl_error = tk.Label(caja, text="", bg=PANEL, fg="#FFE08A", font=fnt(9, "bold"),
                                  wraplength=340, justify="left", anchor="w")
        self.lbl_error.pack(fill="x", pady=(8, 2))
        boton(caja, "Crear cuenta y entrar" if self.registro else "Iniciar sesión",
              self.enviar, AZUL).pack(fill="x", pady=(6, 0), ipady=4)
        if self.registro:
            if hay_usuarios():
                self.enlace_login(caja, "Ya tengo cuenta · Iniciar sesión",
                                  lambda: self.cambiar_modo(False))
        else:
            self.enlace_login(caja, "¿No tienes cuenta? Crear una nueva",
                              lambda: self.cambiar_modo(True))
            self.enlace_login(caja, "¿Olvidaste tu contraseña?", self.olvido)
        self.e_usuario.focus_set()

    def cambiar_modo(self, registro):
        self.registro = registro
        self.construir_form()

    def olvido(self):
        archivo = os.path.basename(sys.argv[0]) or "programa.py"
        messagebox.showinfo(
            "Contraseña olvidada",
            "Por seguridad la contraseña no se puede recuperar (se guarda cifrada), "
            "pero puedes ponerle una nueva.\n\n"
            "Abre una terminal en la carpeta del programa y ejecuta:\n\n"
            f"    python {archivo} --restablecer TU_USUARIO\n\n"
            "Tus datos de estudio no se borran.")

    def error(self, texto):
        self.lbl_error.config(text=texto)

    def entrar(self, uid, usuario):
        self.autenticado, self.uid, self.usuario = True, uid, usuario
        self.destroy()

    def enviar(self, evento=None):
        ahora = time.time()
        if ahora < self.bloqueado_hasta:
            return self.error(f"Demasiados intentos. Espera {int(self.bloqueado_hasta - ahora) + 1} s.")
        usuario = self.v_usuario.get().strip()
        clave = self.v_clave.get()
        if self.registro:
            nombre = self.v_nombre.get().strip()
            if not nombre:
                return self.error("Escribe tu nombre.")
            if len(usuario) < 3 or " " in usuario:
                return self.error("El usuario debe tener al menos 3 caracteres y no llevar espacios.")
            if len(clave) < 6:
                return self.error("La contraseña debe tener al menos 6 caracteres.")
            if clave != self.v_rep.get():
                return self.error("Las contraseñas no coinciden.")
            try:
                uid = crear_usuario(usuario, clave, nombre)
            except Exception as error:
                return self.error(f"No se pudo crear la cuenta: {error}")
            return self.entrar(uid, usuario)
        if not usuario or not clave:
            return self.error("Escribe tu usuario y tu contraseña.")
        try:
            datos = autenticar(usuario, clave)
        except Exception as error:
            return self.error(f"Error de base de datos: {error}")
        if datos:
            return self.entrar(*datos)
        self.intentos += 1
        if self.intentos >= 5:
            self.intentos, self.bloqueado_hasta = 0, ahora + 30
            self.error("Demasiados intentos fallidos. Espera 30 segundos.")
        else:
            self.error("Usuario o contraseña incorrectos.")
        self.v_clave.set("")


# --------------------------------------------------------------------- APP
class App(tk.Tk):
    def __init__(self, usuario=""):
        super().__init__()
        self.ok = False
        self.usuario = usuario
        self.cerrar_sesion = False
        self.title("Organizador de Estudios(ODE)")
        self.geometry(f"1200x{min(800, max(680, self.winfo_screenheight() - 70))}")
        self.minsize(1100, 680)
        self.configure(bg=FONDO)
        # Esc = volver al Panel Central desde cualquier sección
        self.bind("<Escape>", lambda e: self.mostrar("Panel Central")
                  if self.actual != "Panel Central" else None)

        try:
            self.anios_db = obtener_anios_db()
            self.materias = cargar()
            self.catalogo = obtener_catalogo_completo()
            self.perfil = cargar_perfil()
            self.foto = cargar_foto_db()
            self.foto_pend = self.foto
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
        """Cierra la sesión y vuelve al inicio de sesión (para entrar con otro usuario)."""
        if messagebox.askyesno("Cerrar sesión", "¿Cerrar sesión y volver al inicio?"):
            self.cerrar_sesion = True
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
        # Botón «← Panel»: solo se muestra cuando no estás en el Panel Central
        self.btn_volver = tk.Label(top, text="←  Panel", bg=AZUL_SB, fg="white",
                                   font=fnt(10, "bold"), cursor="hand2", padx=12, pady=6)
        self.btn_volver.bind("<Button-1>", lambda e: self.mostrar("Panel Central"))

        usuario = tk.Frame(top, bg=PANEL, cursor="hand2")
        usuario.pack(side="right", padx=(8, 22))
        self.av_top = av = tk.Canvas(usuario, width=42, height=42, bg=PANEL,
                                     highlightthickness=0)
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
        self.lbl_lema.config(text=p.get("lema") or LEMA_DEFECTO)
        dibujar_avatar(self.av_top, 42, p.get("avatar"), p.get("color_avatar"), self.foto)

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
        self.p_juegos(self.paginas["Juegos"])

        self.paginas["Asistencia"] = PaginaCrud(
            cont, self, "Registrar asistencia", "asistencia",
            [("materia_id", "Materia", "materia", None, True),
             ("fecha", "Fecha de la clase", "fecha", None, True),
             ("presente", "Asistencia", "bool", ("Presente", "Ausente"), True)],
            "SELECT a.id, m.nombre, a.fecha, CASE WHEN a.presente THEN 'Presente' "
            "ELSE 'Ausente' END FROM asistencia a JOIN materias m ON m.id = a.materia_id "
            "WHERE a.usuario_id = %s ORDER BY a.fecha DESC, a.id DESC",
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
            "FROM horario h JOIN materias m ON m.id = h.materia_id WHERE h.usuario_id = %s "
            "ORDER BY CASE h.dia "
            "WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3 "
            "WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 ELSE 6 END, h.hora_inicio",
            ("ID", "Materia", "Día", "Inicio", "Fin", "Aula"), (40, 220, 90, 70, 70, 90),
            con_anio=True)
        self.paginas["Avisos"] = PaginaCrud(
            cont, self, "Nuevo aviso", "aviso",
            [("titulo", "Título", "texto", None, True),
             ("detalle", "Detalle", "largo", None, False),
             ("fecha", "Fecha", "fecha", None, True)],
            "SELECT id, titulo, COALESCE(detalle,''), fecha FROM aviso WHERE usuario_id = %s "
            "ORDER BY fecha DESC, id DESC",
            ("ID", "Título", "Detalle", "Fecha"), (40, 220, 300, 100))
        self.paginas["Comentarios"] = PaginaCrud(
            cont, self, "Enviar comentario", "comentario",
            [("texto", "Tu comentario o sugerencia", "largo", None, True)],
            "SELECT id, texto, fecha FROM comentario WHERE usuario_id = %s ORDER BY fecha DESC",
            ("ID", "Comentario", "Enviado"), (40, 480, 130), texto_guardar="📨 Enviar")
        for p in self.paginas.values():
            p.grid(row=0, column=0, sticky="nsew")

    def p_juegos(self, p):
        """Página de minijuegos vinculada a la cuenta que inició sesión."""
        tk.Label(p, text="Zona de juegos", bg=FONDO, fg=TEXTO,
                 font=fnt(24, "bold")).pack(anchor="w", padx=24, pady=(24, 4))
        tk.Label(p, text="Tómate un descanso breve y vuelve a tus estudios con energía.",
                 bg=FONDO, fg=SUAVE, font=fnt(10)).pack(anchor="w", padx=26, pady=(0, 18))

        fila = tk.Frame(p, bg=FONDO)
        fila.pack(fill="both", expand=True, padx=20, pady=8)
        fila.grid_columnconfigure(0, weight=1)
        fila.grid_columnconfigure(1, weight=1)

        tetris = Tarjeta(fila)
        tetris.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        tk.Label(tetris.body, text="🧩", bg=PANEL, fg=TEXTO,
                 font=("Segoe UI Emoji", 42)).pack(pady=(22, 4))
        tk.Label(tetris.body, text="TETRIS", bg=PANEL, fg=TEXTO,
                 font=fnt(18, "bold")).pack()
        tk.Label(tetris.body, text="Ordena las piezas, completa filas y consigue puntos.\n"
                 "Controles: flechas, espacio, P y R.",
                 bg=PANEL, fg=SUAVE, font=fnt(10), justify="center").pack(pady=12)
        boton(tetris.body, "▶ Jugar Tetris", lambda: TetrisJuego(self), AZUL).pack(
            padx=24, pady=(4, 24), fill="x")

        jardin = Tarjeta(fila)
        jardin.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        tk.Label(jardin.body, text="🌱", bg=PANEL, fg=TEXTO,
                 font=("Segoe UI Emoji", 42)).pack(pady=(22, 4))
        tk.Label(jardin.body, text="JARDÍN DE ESTUDIO", bg=PANEL, fg=TEXTO,
                 font=fnt(18, "bold")).pack()
        tk.Label(jardin.body, text="Completa sesiones Pomodoro para ganar monedas,\n"
                 "comprar semillas y hacer crecer tu jardín.",
                 bg=PANEL, fg=SUAVE, font=fnt(10), justify="center").pack(pady=12)
        boton(jardin.body, "🌼 Abrir mi jardín",
              lambda: self.abrir_jardin(), VERDE).pack(
                  padx=24, pady=(4, 24), fill="x")

    def abrir_jardin(self):
        try:
            JardinEstudio(self, SESION["id"])
        except Exception as error:
            messagebox.showerror("Jardín de estudio",
                                 f"No se pudo abrir el jardín:\n{error}", parent=self)

    def resumen_asistencia(self):
        fila = consultar_seguro("SELECT COALESCE(SUM(CASE WHEN presente THEN 1 ELSE 0 END),0), "
                                "COUNT(*) FROM asistencia WHERE usuario_id = %s", (SESION["id"],))
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
        # Botón «← Panel» visible en todas las secciones menos en el Panel Central
        if nombre == "Panel Central":
            self.btn_volver.pack_forget()
        elif not self.btn_volver.winfo_ismapped():
            self.btn_volver.pack(side="left", padx=(0, 14), before=self.titulo)
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

    # ------------------------------------------------------- PANEL CENTRAL
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
        self.lbl_lema = tk.Label(izq, text=LEMA_DEFECTO, bg=BANNER, fg=SUAVE, font=fnt(9),
                                 anchor="w")
        self.lbl_lema.pack(anchor="w", pady=(2, 0))
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
        """Pila de libros con birrete, planta y destellos (todo dibujado con formas simples)."""
        def estrella(cx, cy, r, color):
            k = r * 0.3
            cv.create_polygon(cx, cy - r, cx + k, cy - k, cx + r, cy, cx + k, cy + k,
                              cx, cy + r, cx - k, cy + k, cx - r, cy, cx - k, cy - k,
                              fill=color, outline=color)

        def libro(x1, y1, x2, y2, tapa, detalle):
            mid = (y1 + y2) // 2
            rect_redondo(cv, x1, y1, x2, y2, 6, fill=tapa, outline=tapa)
            # lomo con dos franjas
            cv.create_rectangle(x1 + 8, y1 + 3, x1 + 11, y2 - 3, fill=detalle, outline=detalle)
            cv.create_rectangle(x1 + 15, y1 + 3, x1 + 17, y2 - 3, fill=detalle, outline=detalle)
            # "título" en la tapa
            cv.create_line(x1 + 34, mid - 3, x1 + 92, mid - 3, fill=detalle, width=3,
                           capstyle="round")
            cv.create_line(x1 + 34, mid + 4, x1 + 68, mid + 4, fill=detalle, width=2,
                           capstyle="round")
            # páginas a la derecha
            cv.create_rectangle(x2 - 26, y1 + 4, x2 - 3, y2 - 4, fill="#fdf6e3",
                                outline="#e6dcc0")
            for dy in (7, 12, 17):
                cv.create_line(x2 - 23, y1 + dy, x2 - 6, y1 + dy, fill="#d9cfb2")

        # nubes suaves de fondo
        for x1, y1, x2, y2 in ((8, 62, 96, 94), (50, 44, 140, 80), (306, 52, 374, 86),
                               (256, 26, 326, 56)):
            cv.create_oval(x1, y1, x2, y2, fill="#5148c9", outline="#5148c9")
        # sombra bajo los libros
        cv.create_oval(104, 103, 352, 112, fill="#241b7a", outline="#241b7a")

        # planta en maceta
        cv.create_polygon(60, 82, 112, 82, 106, 111, 66, 111, fill="#e2e8f2", outline="#c4cddd")
        rect_redondo(cv, 56, 76, 116, 86, 4, fill="#f4f6fb", outline="#c4cddd")
        cv.create_line(86, 76, 86, 30, fill="#3f9d4f", width=3)
        for pts, col in (((86, 58, 62, 50, 72, 70), "#58b868"),
                         ((86, 50, 110, 40, 102, 62), "#3f9d4f"),
                         ((86, 40, 68, 24, 82, 18), "#58b868"),
                         ((86, 36, 102, 20, 94, 14), "#3f9d4f")):
            cv.create_polygon(*pts, fill=col, outline=col, smooth=True)

        # pila de libros (de abajo hacia arriba, ligeramente desfasados)
        libro(118, 84, 336, 108, "#2c5fd1", "#9db8f5")
        libro(134, 60, 322, 84, "#f5a623", "#b9770e")
        libro(152, 38, 298, 60, "#22a06b", "#a7f0cd")
        # marcapáginas
        cv.create_polygon(278, 38, 286, 38, 286, 52, 282, 48, 278, 52,
                          fill="#ef4444", outline="#ef4444")

        # birrete de graduación sobre la pila
        cv.create_polygon(208, 21, 208, 30, 226, 36, 244, 30, 244, 21,
                          fill="#1b1464", outline="#1b1464")
        cv.create_polygon(226, 8, 260, 18, 226, 28, 192, 18,
                          fill="#2a1f8f", outline=DORADO, width=1)
        cv.create_line(260, 18, 260, 31, fill=DORADO, width=2)
        cv.create_oval(257, 30, 263, 36, fill=DORADO, outline=DORADO)

        # destellos
        estrella(344, 22, 7, DORADO)
        estrella(364, 44, 4, "#ffffff")
        estrella(30, 26, 5, "#ffffff")
        estrella(150, 12, 4, DORADO)

    def actualizar_Panel_Central(self):
        ms, hoy = self.materias, date.today()
        estados = [estado_real(m) for m in ms]
        prom = sum(m["nota"] for m in ms) / len(ms) if ms else None
        aprob = sum(1 for m in ms if m["nota"] >= 60)
        fila = consultar_seguro("SELECT COALESCE(SUM(CASE WHEN presente THEN 1 ELSE 0 END),0), "
                                "COUNT(*) FROM asistencia WHERE usuario_id = %s", (SESION["id"],))
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
            "SELECT titulo, COALESCE(detalle,''), fecha FROM aviso WHERE usuario_id = %s "
            "ORDER BY fecha DESC, id DESC LIMIT 3", (SESION["id"],))]
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
            # sin resultados todavía: círculo rojo completo
            c.create_oval(14, 14, 126, 126, outline=ROJO, width=20)
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
        p.grid_rowconfigure(0, weight=1)
        nb = ttk.Notebook(p)
        nb.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        tab_perfil = tk.Frame(nb, bg=FONDO)
        tab_seg = tk.Frame(nb, bg=FONDO)
        nb.add(tab_perfil, text="  👤 Mi perfil  ")
        nb.add(tab_seg, text="  🔒 Seguridad  ")
        self.pf = {}

        # ---- datos personales
        t = Tarjeta(tab_perfil)
        t.grid(row=0, column=0, sticky="nw", padx=(10, 10), pady=10)
        c = t.body
        tk.Frame(c, width=380, height=1, bg=PANEL).pack()
        tk.Label(c, text="Datos personales", bg=PANEL, fg=TEXTO, font=fnt(13, "bold")).pack(
            anchor="w", padx=14, pady=(10, 0))
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

        # ---- personalización (foto, avatar, color, lema, biografía)
        t2 = Tarjeta(tab_perfil)
        t2.grid(row=0, column=1, sticky="nw", padx=(10, 10), pady=10)
        s = t2.body
        tk.Frame(s, width=340, height=1, bg=PANEL).pack()
        tk.Label(s, text="Personalizar", bg=PANEL, fg=TEXTO, font=fnt(13, "bold")).pack(
            anchor="w", padx=14, pady=(10, 4))
        self.av_prev = tk.Canvas(s, width=90, height=90, bg=PANEL, highlightthickness=0)
        self.av_prev.pack(pady=(0, 4))
        bf = tk.Frame(s, bg=PANEL)
        bf.pack(pady=(0, 6))
        boton(bf, "📷 Subir foto", self.elegir_foto, VERDE, 8).pack(side="left", padx=4)
        boton(bf, "✖ Quitar", self.quitar_foto, GRIS, 8).pack(side="left", padx=4)
        fila = tk.Frame(s, bg=PANEL)
        fila.pack(fill="x", padx=14)
        for i in range(2):
            fila.columnconfigure(i, weight=1, uniform="p")
        etiqueta(fila, "Avatar (si no hay foto)").grid(row=0, column=0, sticky="w")
        etiqueta(fila, "Color").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.pf["avatar"], self.pf["color_avatar"] = tk.StringVar(), tk.StringVar()
        for col, clave, vals in ((0, "avatar", AVATARES),
                                 (1, "color_avatar", list(COLORES_AVATAR))):
            cb = ttk.Combobox(fila, textvariable=self.pf[clave], values=vals, state="readonly",
                              font=fnt(11))
            cb.grid(row=1, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
            cb.bind("<<ComboboxSelected>>", lambda e: self.vista_previa_avatar())
        etiqueta(s, "Lema personal").pack(fill="x", padx=14, pady=(10, 0))
        self.pf["lema"] = tk.StringVar()
        entrada(s, self.pf["lema"]).pack(fill="x", padx=14, ipady=3)
        etiqueta(s, "Sobre mí").pack(fill="x", padx=14, pady=(10, 0))
        self.t_bio = tk.Text(s, height=4, width=32, relief="flat", font=fnt(10), wrap="word",
                             highlightthickness=1, highlightbackground=LINEA,
                             highlightcolor=AZUL)
        self.t_bio.pack(fill="x", padx=14)
        boton(s, "💾 Guardar perfil", self.guardar_perfil, AZUL).pack(
            anchor="w", padx=14, pady=(14, 6))
        self.lbl_pf = tk.Label(s, text="", bg=PANEL, font=fnt(10, "bold"), wraplength=300,
                               justify="left")
        self.lbl_pf.pack(anchor="w", padx=14, pady=(0, 10))
        p.refrescar = self.cargar_form_perfil

        # ---- seguridad
        t3 = Tarjeta(tab_seg)
        t3.grid(row=0, column=0, sticky="nw", padx=10, pady=10)
        s = t3.body
        tk.Frame(s, width=360, height=1, bg=PANEL).pack()
        tk.Label(s, text="🔒 Seguridad", bg=PANEL, fg=TEXTO, font=fnt(13, "bold")).pack(
            anchor="w", padx=14, pady=(10, 0))
        tk.Label(s, text=f"Sesión iniciada como «{self.usuario}»", bg=PANEL, fg=SUAVE,
                 font=fnt(9)).pack(anchor="w", padx=14)
        self.pw = {}
        for k, texto in (("actual", "Contraseña actual"),
                         ("nueva", "Nueva contraseña (mín. 6 caracteres)"),
                         ("rep", "Repetir nueva contraseña")):
            etiqueta(s, texto).pack(fill="x", padx=14, pady=(10, 0))
            var = tk.StringVar()
            e = entrada(s, var)
            e.config(show="•")
            e.pack(fill="x", padx=14, ipady=3)
            self.pw[k] = var
        boton(s, "🔒 Cambiar contraseña", self.cambiar_clave, AZUL).pack(
            anchor="w", padx=14, pady=(16, 6))
        self.lbl_pw = tk.Label(s, text="", bg=PANEL, font=fnt(10, "bold"), wraplength=320,
                               justify="left")
        self.lbl_pw.pack(anchor="w", padx=14, pady=(0, 12))

    def vista_previa_avatar(self):
        dibujar_avatar(self.av_prev, 90, self.pf["avatar"].get(),
                       self.pf["color_avatar"].get(), self.foto_pend)

    def elegir_foto(self):
        if Image is None:
            return messagebox.showinfo(
                "Foto de perfil", "Falta la librería Pillow.\n\nEn una terminal ejecuta:\n"
                "    pip install pillow")
        ruta = filedialog.askopenfilename(
            title="Elige tu foto",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                       ("Todos los archivos", "*.*")])
        if not ruta:
            return
        try:
            self.foto_pend = procesar_foto(ruta)
        except Exception as error:
            return messagebox.showerror("Foto de perfil",
                                        f"No se pudo abrir la imagen:\n{error}")
        self.vista_previa_avatar()
        self.lbl_pf.config(text="Pulsa «Guardar perfil» para conservar la foto.", fg=NARANJA)

    def quitar_foto(self):
        self.foto_pend = None
        self.vista_previa_avatar()
        self.lbl_pf.config(text="Pulsa «Guardar perfil» para confirmar.", fg=NARANJA)

    def cargar_form_perfil(self):
        for k, var in self.pf.items():
            var.set(self.perfil.get(k, ""))
        self.t_bio.delete("1.0", "end")
        self.t_bio.insert("1.0", self.perfil.get("bio", ""))
        self.foto_pend = self.foto
        self.vista_previa_avatar()
        self.lbl_pf.config(text="")

    def guardar_perfil(self):
        datos = {k: v.get().strip() for k, v in self.pf.items()}
        datos["bio"] = self.t_bio.get("1.0", "end-1c").strip()
        if not datos["nombre"]:
            self.lbl_pf.config(text="Escribe tu nombre.", fg=ROJO)
            return
        try:
            guardar_perfil_db(datos)
            if self.foto_pend != self.foto:
                guardar_foto_db(self.foto_pend)
        except Exception as error:
            messagebox.showerror("Error de PostgreSQL", str(error))
            return
        self.perfil = datos
        self.foto = self.foto_pend
        self.pintar_perfil()
        self.lbl_pf.config(text="✔ Perfil guardado.", fg="#146C3F")

    def cambiar_clave(self):
        actual, nueva, rep = (self.pw[k].get() for k in ("actual", "nueva", "rep"))
        try:
            if not autenticar(self.usuario, actual):
                return self.lbl_pw.config(text="La contraseña actual no es correcta.", fg=ROJO)
            if len(nueva) < 6:
                return self.lbl_pw.config(text="La nueva contraseña necesita 6 caracteres o más.",
                                          fg=ROJO)
            if nueva != rep:
                return self.lbl_pw.config(text="Las contraseñas nuevas no coinciden.", fg=ROJO)
            sal, h = hashear_clave(nueva)
            ejecutar("UPDATE usuario SET sal = %s, clave_hash = %s WHERE id = %s",
                     (sal, h, SESION["id"]))
        except Exception as error:
            return messagebox.showerror("Error de PostgreSQL", str(error))
        for var in self.pw.values():
            var.set("")
        self.lbl_pw.config(text="✔ Contraseña actualizada.", fg="#146C3F")

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



# ------------------------------------------------------------------ JUEGOS
# Tetris y Jardín de estudio. El progreso del jardín se guarda por usuario.
class TetrisJuego(tk.Toplevel):
    CELDA = 28
    COLUMNAS = 10
    FILAS = 20
    FORMAS = [
        [[1, 1, 1, 1]],
        [[1, 1], [1, 1]],
        [[0, 1, 0], [1, 1, 1]],
        [[1, 0, 0], [1, 1, 1]],
        [[0, 0, 1], [1, 1, 1]],
        [[0, 1, 1], [1, 1, 0]],
        [[1, 1, 0], [0, 1, 1]],
    ]
    COLORES = ["#38BDF8", "#FBBF24", "#A78BFA", "#FB923C",
               "#F472B6", "#34D399", "#60A5FA"]

    def __init__(self, master):
        super().__init__(master)
        self.title("Tetris · Organizador de Estudios")
        self.configure(bg=FONDO)
        self.resizable(False, False)
        self.tablero = [[None for _ in range(self.COLUMNAS)] for _ in range(self.FILAS)]
        self.puntos = 0
        self.nivel = 1
        self.pausado = False
        self.terminado = False
        self.pieza = None
        self.color = None

        cab = tk.Frame(self, bg=PANEL)
        cab.pack(fill="x", padx=12, pady=10)
        self.lbl_puntos = tk.Label(cab, text="Puntos: 0   Nivel: 1",
                                   bg=PANEL, fg=TEXTO, font=fnt(12, "bold"))
        self.lbl_puntos.pack(side="left")
        boton(cab, "Pausar (P)", self.pausar, AZUL, 8).pack(side="right")
        self.cv = tk.Canvas(self, width=self.COLUMNAS*self.CELDA,
                            height=self.FILAS*self.CELDA, bg="#071827",
                            highlightthickness=2, highlightbackground=LINEA)
        self.cv.pack(padx=12, pady=(0, 8))
        tk.Label(self, text="← → mover   ↑ girar   ↓ bajar   Espacio: caída   P: pausa   R: reiniciar",
                 bg=FONDO, fg=SUAVE, font=fnt(9)).pack(pady=(0, 10))
        self.bind("<Left>", lambda e: self.mover(-1, 0))
        self.bind("<Right>", lambda e: self.mover(1, 0))
        self.bind("<Down>", lambda e: self.mover(0, 1))
        self.bind("<Up>", lambda e: self.girar())
        self.bind("<space>", lambda e: self.caida())
        self.bind("p", lambda e: self.pausar())
        self.bind("r", lambda e: self.reiniciar())
        self.focus_force()
        self.nueva_pieza()
        self.dibujar()
        self.programar()

    def nueva_pieza(self):
        forma = random.choice(self.FORMAS)
        self.pieza = [fila[:] for fila in forma]
        self.color = random.choice(self.COLORES)
        self.x = self.COLUMNAS // 2 - len(self.pieza[0]) // 2
        self.y = 0
        if self.colision(self.x, self.y, self.pieza):
            self.terminado = True
            messagebox.showinfo("Tetris", f"Fin del juego. Puntuación: {self.puntos}",
                                parent=self)

    def colision(self, x, y, forma):
        for fy, fila in enumerate(forma):
            for fx, valor in enumerate(fila):
                if valor:
                    xx, yy = x + fx, y + fy
                    if xx < 0 or xx >= self.COLUMNAS or yy >= self.FILAS:
                        return True
                    if yy >= 0 and self.tablero[yy][xx] is not None:
                        return True
        return False

    def mover(self, dx, dy):
        if self.terminado or self.pausado:
            return
        if not self.colision(self.x + dx, self.y + dy, self.pieza):
            self.x += dx
            self.y += dy
            self.dibujar()
        elif dy:
            self.fijar()

    def girar(self):
        if self.terminado or self.pausado:
            return
        girada = [list(fila) for fila in zip(*self.pieza[::-1])]
        if not self.colision(self.x, self.y, girada):
            self.pieza = girada
            self.dibujar()

    def caida(self):
        if self.terminado or self.pausado:
            return
        while not self.colision(self.x, self.y + 1, self.pieza):
            self.y += 1
        self.fijar()

    def fijar(self):
        for fy, fila in enumerate(self.pieza):
            for fx, valor in enumerate(fila):
                if valor and 0 <= self.y + fy < self.FILAS:
                    self.tablero[self.y + fy][self.x + fx] = self.color
        llenas = [fila for fila in self.tablero if all(c is not None for c in fila)]
        if llenas:
            cantidad = len(llenas)
            self.puntos += (0, 100, 300, 500, 800)[cantidad]
            self.tablero = [[None for _ in range(self.COLUMNAS)]
                            for _ in range(cantidad)] + [
                                fila for fila in self.tablero if not all(c is not None for c in fila)]
            self.nivel = self.puntos // 500 + 1
        self.lbl_puntos.config(text=f"Puntos: {self.puntos}   Nivel: {self.nivel}")
        self.nueva_pieza()
        self.dibujar()

    def dibujar(self):
        self.cv.delete("all")
        for y, fila in enumerate(self.tablero):
            for x, color in enumerate(fila):
                if color:
                    self.celda(x, y, color)
        if self.pieza and not self.terminado:
            for fy, fila in enumerate(self.pieza):
                for fx, valor in enumerate(fila):
                    if valor:
                        self.celda(self.x + fx, self.y + fy, self.color)
        if self.pausado:
            self.cv.create_text(140, 280, text="PAUSA", fill="white",
                                font=fnt(24, "bold"))

    def celda(self, x, y, color):
        s = self.CELDA
        self.cv.create_rectangle(x*s+1, y*s+1, (x+1)*s-1, (y+1)*s-1,
                                 fill=color, outline="#071827", width=2)

    def programar(self):
        if not self.terminado and self.winfo_exists():
            if not self.pausado:
                self.mover(0, 1)
            self.after(max(100, 650 - (self.nivel-1)*45), self.programar)

    def pausar(self):
        if not self.terminado:
            self.pausado = not self.pausado
            self.dibujar()

    def reiniciar(self):
        self.tablero = [[None for _ in range(self.COLUMNAS)] for _ in range(self.FILAS)]
        self.puntos, self.nivel = 0, 1
        self.pausado, self.terminado = False, False
        self.lbl_puntos.config(text="Puntos: 0   Nivel: 1")
        self.nueva_pieza()
        self.dibujar()


class JardinEstudio(tk.Toplevel):
    PLANTAS = ["🌱", "🌿", "🌷", "🌻", "🌵", "🌳", "🌸", "🍀", "🌼", "🌴"]

    def __init__(self, master, uid):
        super().__init__(master)
        self.uid = uid
        self.title("Jardín de estudio · Organizador")
        self.geometry("600x520")
        self.minsize(520, 460)
        self.configure(bg=FONDO)
        self.monedas, self.sesiones, self.minutos, self.plantas = 0, 0, 0, []
        self.segundos = 25 * 60
        self.descanso = False
        self.activo = False
        self.after_id = None
        self.cargar_datos()

        tk.Label(self, text="🌱 Jardín de estudio", bg=FONDO, fg=TEXTO,
                 font=fnt(22, "bold")).pack(pady=(16, 4))
        tk.Label(self, text="Estudia 25 minutos, gana monedas y cultiva tu jardín.",
                 bg=FONDO, fg=SUAVE, font=fnt(10)).pack()
        tarjeta = tk.Frame(self, bg=PANEL, padx=18, pady=16)
        tarjeta.pack(fill="x", padx=18, pady=16)
        self.lbl_tiempo = tk.Label(tarjeta, text="25:00", bg=PANEL, fg=CIAN,
                                   font=("Segoe UI", 34, "bold"))
        self.lbl_tiempo.pack()
        self.lbl_modo = tk.Label(tarjeta, text="Sesión de estudio", bg=PANEL,
                                 fg=TEXTO, font=fnt(11, "bold"))
        self.lbl_modo.pack(pady=(0, 8))
        fila = tk.Frame(tarjeta, bg=PANEL)
        fila.pack()
        boton(fila, "▶ Iniciar", self.iniciar, VERDE).pack(side="left", padx=4)
        boton(fila, "Ⅱ Pausar", self.pausar, NARANJA).pack(side="left", padx=4)
        boton(fila, "↻ Reiniciar", self.reiniciar_reloj, ROJO).pack(side="left", padx=4)

        self.lbl_stats = tk.Label(self, text="", bg=FONDO, fg=DORADO,
                                  font=fnt(11, "bold"))
        self.lbl_stats.pack(pady=4)
        tk.Label(self, text="Tu jardín", bg=FONDO, fg=TEXTO,
                 font=fnt(14, "bold")).pack(pady=(8, 2))
        self.lbl_jardin = tk.Label(self, text="", bg=PANEL, fg=TEXTO,
                                   font=("Segoe UI Emoji", 28), padx=14, pady=12)
        self.lbl_jardin.pack(fill="x", padx=18, pady=6)
        boton(self, "🌼 Comprar semilla (15 monedas)", self.comprar, AZUL).pack(pady=8)
        self.actualizar_vista()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

    def cargar_datos(self):
        con = conectar_db()
        try:
            with con.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS jardin (
                        usuario_id INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
                        monedas INTEGER NOT NULL DEFAULT 0,
                        sesiones INTEGER NOT NULL DEFAULT 0,
                        minutos INTEGER NOT NULL DEFAULT 0,
                        plantas TEXT NOT NULL DEFAULT ''
                    )
                """)
                cur.execute("SELECT monedas, sesiones, minutos, plantas FROM jardin WHERE usuario_id=%s",
                            (self.uid,))
                fila = cur.fetchone()
                if fila:
                    self.monedas, self.sesiones, self.minutos = fila[:3]
                    self.plantas = [int(x) for x in fila[3].split(",") if x.strip().isdigit()]
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def guardar_datos(self):
        texto = ",".join(map(str, self.plantas))
        con = conectar_db()
        try:
            with con.cursor() as cur:
                cur.execute("""
                    UPDATE jardin SET monedas=%s, sesiones=%s, minutos=%s, plantas=%s
                    WHERE usuario_id=%s
                """, (self.monedas, self.sesiones, self.minutos, texto, self.uid))
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO jardin (usuario_id, monedas, sesiones, minutos, plantas)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (self.uid, self.monedas, self.sesiones, self.minutos, texto))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def actualizar_vista(self):
        self.lbl_tiempo.config(text=f"{self.segundos//60:02d}:{self.segundos%60:02d}")
        self.lbl_stats.config(
            text=f"🪙 {self.monedas} monedas    ·    📚 {self.sesiones} sesiones    ·    ⏱ {self.minutos} minutos")
        self.lbl_jardin.config(text="  ".join(self.PLANTAS[i] for i in self.plantas)
                                or "Todavía no tienes plantas. ¡Completa una sesión!")

    def iniciar(self):
        if not self.activo:
            self.activo = True
            self.contar()

    def pausar(self):
        self.activo = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def reiniciar_reloj(self):
        self.pausar()
        self.descanso = False
        self.segundos = 25 * 60
        self.lbl_modo.config(text="Sesión de estudio")
        self.actualizar_vista()

    def contar(self):
        if not self.activo or not self.winfo_exists():
            return
        if self.segundos > 0:
            self.segundos -= 1
            self.actualizar_vista()
            self.after_id = self.after(1000, self.contar)
        else:
            self.activo = False
            self.after_id = None
            if not self.descanso:
                self.sesiones += 1
                self.minutos += 25
                self.monedas += 10
                self.guardar_datos()
                messagebox.showinfo("¡Buen trabajo!", "Terminaste 25 minutos de estudio. Ganaste 10 monedas.",
                                    parent=self)
                self.descanso = True
                self.segundos = 5 * 60
                self.lbl_modo.config(text="Descanso de 5 minutos")
            else:
                messagebox.showinfo("Descanso terminado", "¡Es hora de volver a estudiar!",
                                    parent=self)
                self.descanso = False
                self.segundos = 25 * 60
                self.lbl_modo.config(text="Sesión de estudio")
            self.actualizar_vista()

    def comprar(self):
        if self.monedas < 15:
            return messagebox.showwarning("Jardín", "Necesitas 15 monedas para comprar una semilla.",
                                          parent=self)
        self.monedas -= 15
        self.plantas.append(random.randrange(len(self.PLANTAS)))
        self.guardar_datos()
        self.actualizar_vista()

    def cerrar(self):
        self.pausar()
        self.destroy()


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--restablecer":
        restablecer_clave_consola(sys.argv[2])
        return
    try:
        preparar_bd()
    except Exception as error:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(
            "Error de PostgreSQL",
            "No se pudo conectar a la base de datos. Revisa la contraseña, "
            "el servidor y las tablas anios/materias.\n\n" + str(error))
        raiz.destroy()
        return
    while True:
        login = Login()
        login.mainloop()
        if not login.autenticado:
            break
        SESION.update(id=login.uid, usuario=login.usuario)
        app = App(usuario=login.usuario)
        if not app.ok:
            break
        app.mainloop()
        SESION.update(id=None, usuario="")
        if not app.cerrar_sesion:
            break


if __name__ == "__main__":
    main()