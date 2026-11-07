
import tkinter as tk
from tkinter import messagebox
import smtplib
import ssl
from email.message import EmailMessage

# COLORES
FONDO = "#080D1A"
PANEL = "#111B2E"
AZUL = "#1677FF"
TEXTO = "#FFFFFF"
VERDE = "#12B76A"


def enviar_notificacion():

    correo_gmail = entrada_correo.get().strip()
    contrasena = entrada_clave.get().replace(" ", "")
    
    if not correo_gmail or not contrasena:
        messagebox.showwarning(
            "Aviso",
            "Completa tu correo y contraseña de aplicación."
        )
        return

    boton.config(state="disabled", text="Enviando...")

    ventana.update_idletasks()

    try:
        email = EmailMessage()

        email["From"] = correo_gmail
        email["To"] = correo_gmail
        email["Subject"] = "Prueba de Gestor de Estudios"

        email.set_content(
            "¡Hola!\n\n"
            "Esta es una notificación de prueba.\n"
            "Tu Gestor de Estudios puede enviar correos reales.\n\n"
            "Sistema de notificaciones funcionando."
        )

        contexto = ssl.create_default_context()

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as servidor:
            servidor.ehlo()
            servidor.starttls(context=contexto)
            servidor.ehlo()
            servidor.login(correo_gmail, contrasena)
            servidor.send_message(email)

        estado.config(
            text="✓ Notificación enviada correctamente",
            fg=VERDE
        )

        messagebox.showinfo(
            "Éxito",
            "¡Correo enviado!\n\n"
            "Revisa la bandeja de entrada de tu Gmail."
        )

    except Exception as error:

        estado.config(
            text="Error al enviar la notificación",
            fg="#FF4444"
        )

        messagebox.showerror(
            "Error de Gmail",
            str(error)
        )

    finally:
        boton.config(state="normal", text="ENVIAR NOTIFICACIÓN")


# VENTANA
ventana = tk.Tk()
ventana.title("Prueba de correo - Gestor de Estudios")
ventana.geometry("520x490")
ventana.configure(bg=FONDO)
ventana.resizable(False, False)

tk.Label(
    ventana,
    text="GESTOR DE ESTUDIOS",
    bg=FONDO,
    fg=TEXTO,
    font=("Segoe UI", 21, "bold")
).pack(pady=(30, 5))

tk.Label(
    ventana,
    text="Sistema de notificaciones por Gmail",
    bg=FONDO,
    fg="#AAB7CC",
    font=("Segoe UI", 10)
).pack(pady=(0, 25))

panel = tk.Frame(ventana, bg=PANEL, padx=25, pady=25)
panel.pack(fill="x", padx=25)

tk.Label(
    panel,
    text="Tu correo Gmail",
    bg=PANEL,
    fg=TEXTO
).pack(anchor="w")

entrada_correo = tk.Entry(
    panel,
    font=("Segoe UI", 11),
    bg="#07101F",
    fg=TEXTO,
    insertbackground="white",
    relief="flat"
)
entrada_correo.pack(fill="x", ipady=9, pady=(5, 15))

tk.Label(
    panel,
    text="Contraseña de aplicación",
    bg=PANEL,
    fg=TEXTO
).pack(anchor="w")

entrada_clave = tk.Entry(
    panel,
    show="*",
    font=("Segoe UI", 11),
    bg="#07101F",
    fg=TEXTO,
    insertbackground="white",
    relief="flat"
)
entrada_clave.pack(fill="x", ipady=9, pady=(5, 20))

boton = tk.Button(
    panel,
    text="ENVIAR NOTIFICACIÓN",
    command=enviar_notificacion,
    bg=AZUL,
    fg="white",
    font=("Segoe UI", 11, "bold"),
    relief="flat",
    cursor="hand2"
)
boton.pack(fill="x", ipady=10)

estado = tk.Label(
    ventana,
    text="Esperando configuración...",
    bg=FONDO,
    fg="#AAB7CC",
    font=("Segoe UI", 10)
)
estado.pack(pady=25)

tk.Label(
    ventana,
    text="Gmail SMTP | Puerto 587 | TLS",
    bg=FONDO,
    fg="#AAB7CC",
    font=("Segoe UI", 9)
).pack()

ventana.mainloop()

def enviar_notificacion():

    import smtplib
    import ssl
    from email.message import EmailMessage
    from tkinter import messagebox

    correo_gmail = entrada_correo.get().strip()
    contrasena = entrada_clave.get().replace(" ", "")

    if not correo_gmail or not contrasena:
        messagebox.showwarning(
            "Aviso",
            "Completa tu Gmail y contraseña de aplicación."
        )
        return

    boton.config(state="disabled", text="Conectando con Gmail...")
    estado.config(text="Conectando...", fg="#1677FF")

    def proceso():

        try:
            email = EmailMessage()
            email["From"] = correo_gmail
            email["To"] = correo_gmail
            email["Subject"] = "Prueba Gestor de Estudios"

            email.set_content(
                "¡Hola!\n\n"
                "Esta es una notificación de prueba.\n"
                "Tu Gestor de Estudios está enviando correos reales."
            )

            contexto = ssl.create_default_context()

            with smtplib.SMTP(
                "smtp.gmail.com",
                587,
                timeout=60
            ) as servidor:

                servidor.set_debuglevel(0)
                servidor.ehlo()
                servidor.starttls(context=contexto)
                servidor.ehlo()
                servidor.login(correo_gmail, contrasena)
                servidor.send_message(email)

            ventana.after(
                0,
                lambda: resultado(True, "Correo enviado correctamente.")
            )

        except Exception as error:

            ventana.after(
                0,
                lambda e=str(error): resultado(False, e)
            )

    import threading
    threading.Thread(target=proceso, daemon=True).start()


def resultado(correcto, mensaje):

    boton.config(
        state="normal",
        text="ENVIAR NOTIFICACIÓN"
    )

    if correcto:
        estado.config(
            text="✓ Correo enviado",
            fg="#12B76A"
        )
        messagebox.showinfo("Éxito", mensaje)

    else:
        estado.config(
            text="Error de conexión",
            fg="#FF4444"
        )
        messagebox.showerror("Error Gmail", mensaje)
