from flask import Flask, render_template, request, redirect, url_for, session, flash
import mariadb

app = Flask(__name__)
app.secret_key = "SECRET_KEY_GANACONTROL_2025"

# -------------------- CONEXIÓN A LA BD --------------------
def conectar_bd():
    try:
        conn = mariadb.connect(
            host="localhost",
            user="AdminGanaderia",
            password="2025",
            database="Proyecto_Ganaderia"
        )
        return conn, conn.cursor()
    except mariadb.Error as e:
        print("Error de conexión:", e)
        return None, None


# -------------------- VALIDAR CREDENCIALES --------------------
def verificar_credenciales(usuario, password, rol):
    conn, cursor = conectar_bd()
    if not conn:
        return False, "Error de conexión"

    try:
        sql = "SELECT usuario, password, rol FROM usuarios WHERE usuario=%s AND rol=%s"
        cursor.execute(sql, (usuario, rol))
        result = cursor.fetchone()

        if result:
            db_user, db_pass, db_rol = result
            if db_pass == password:
                return True, db_rol
            else:
                return False, "Contraseña incorrecta"
        else:
            return False, "Usuario o rol no encontrado"

    except Exception as e:
        return False, f"Error: {e}"
    finally:
        conn.close()


# -------------------- RUTAS PRINCIPALES --------------------
@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        contra = request.form["password"]
        rol = request.form["rol"]

        exito, info = verificar_credenciales(usuario, contra, rol)

        if exito:
            session["usuario"] = usuario
            session["rol"] = rol
            flash(f"Bienvenido {usuario} ({rol})", "success")
            return redirect(url_for("dashboard"))
        else:
            flash(info, "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        usuario = request.form["usuario"]
        contra = request.form["password"]
        rol = request.form["rol"]

        conn, cursor = conectar_bd()
        if not conn:
            flash("Error al conectar con la base de datos", "danger")
            return redirect(url_for("register"))

        try:
            sql = "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)"
            cursor.execute(sql, (usuario, contra, rol))
            conn.commit()
            flash("Usuario registrado correctamente", "success")
            return redirect(url_for("login"))
        except mariadb.Error as e:
            flash(f"No se pudo registrar: {e}", "danger")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", usuario=session["usuario"], rol=session["rol"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("inicio"))

# ------------------ Ventana Animales ------------------
@app.route("/animales", methods=["GET", "POST"])
def animales():
    conn, cursor = conectar_bd()

    if request.method == "POST":
        accion = request.form.get("accion")

        # Obtener imágenes si las mandaron
        foto_perfil = request.files.get("foto_perfil")
        foto_lateral = request.files.get("foto_lateral")

        perfil_bytes = foto_perfil.read() if foto_perfil and foto_perfil.filename else None
        lateral_bytes = foto_lateral.read() if foto_lateral and foto_lateral.filename else None

        # --- REGISTRAR ---
        if accion == "registrar":
            nombre = request.form["nombre"]
            fecha = request.form["fecha"]
            cruze = request.form["cruze"] or "Sin conocer"
            fk_productor = request.form["fk_productor"] or None
            fk_raza = request.form["fk_raza"] or None

            sql = """INSERT INTO Animales 
                (nombre, fecha_nacimiento, cruze, fk_productor, fk_raza, foto_perfil, foto_lateral)
                VALUES (%s, %s, %s, %s, %s, %s, %s)"""

            cursor.execute(sql, (nombre, fecha, cruze, fk_productor, fk_raza,
                                 perfil_bytes, lateral_bytes))
            conn.commit()

        # --- MODIFICAR ---
        elif accion == "modificar":
            pk = request.form["pk"]
            nombre = request.form["nombre"]
            fecha = request.form["fecha"]
            cruze = request.form["cruze"]
            fk_productor = request.form["fk_productor"]
            fk_raza = request.form["fk_raza"]

            # Actualizar datos principales
            sql = """UPDATE Animales
                     SET nombre=%s, fecha_nacimiento=%s, cruze=%s,
                         fk_productor=%s, fk_raza=%s
                     WHERE pk_animal=%s"""
            cursor.execute(sql, (nombre, fecha, cruze, fk_productor, fk_raza, pk))

            # Si el usuario subió nuevas imágenes → actualizarlas
            if perfil_bytes:
                cursor.execute("UPDATE Animales SET foto_perfil=%s WHERE pk_animal=%s",
                               (perfil_bytes, pk))

            if lateral_bytes:
                cursor.execute("UPDATE Animales SET foto_lateral=%s WHERE pk_animal=%s",
                               (lateral_bytes, pk))

            conn.commit()


        # --- ELIMINAR ---
        elif accion == "eliminar":
            pk = request.form["pk"]
            cursor.execute("DELETE FROM Animales WHERE pk_animal=%s", (pk,))
            conn.commit()

    # CONSULTAR LISTA
    cursor.execute(
        "SELECT pk_animal, nombre, fecha_nacimiento, cruze, fk_productor, fk_raza FROM Animales"
    )
    animales = cursor.fetchall()

    cursor.execute("SELECT pk_productor, nombre,apellido_pat, apellido_mat FROM Productores")
    productores = cursor.fetchall()

    cursor.execute("SELECT pk_raza, nombre FROM Razas")
    razas = cursor.fetchall()
    
    conn.close()
        
    return render_template("animales.html", animales=animales, productores=productores, razas=razas)



from flask import Response

@app.route("/imagen_animal/<int:id>/<string:tipo>")
def imagen_animal(id, tipo):
    conn, cursor = conectar_bd()
    cursor.execute(f"SELECT {tipo} FROM Animales WHERE pk_animal=%s", (id,))
    imagen = cursor.fetchone()[0]
    conn.close()

    if imagen is None:
        return "", 404

    return Response(imagen, mimetype="image/jpeg")

#-------------------Funciones PREDIOS-------------------
# Asegúrate de tener importadas estas cosas arriba de app.py
from flask import render_template, request, redirect, url_for, session, flash

# Ruta para Predios
@app.route("/predios", methods=["GET", "POST"])
def predios():
    # Asegúrate de que el usuario esté logueado
    if "id_usuario" not in session:
        flash("Inicia sesión para acceder a Predios.", "warning")
        return redirect(url_for("login"))

    id_usuario = session.get("id_usuario")

    conn, cursor = conectar_bd()
    if not conn:
        flash("Error al conectar la base de datos.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        accion = request.form.get("accion")

        # --- REGISTRAR ---
        if accion == "registrar":
            direccion = request.form.get("direccion", "").strip()
            estado = request.form.get("estado", "").strip()
            municipio = request.form.get("municipio", "").strip()

            if not direccion or not estado or not municipio:
                flash("Completa todos los campos para registrar.", "warning")
            else:
                try:
                    sql = """
                        INSERT INTO Predios (direccion, estado, municipio, fk_productor)
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(sql, (direccion, estado, municipio, id_usuario))
                    conn.commit()
                    flash("Predio registrado correctamente.", "success")
                except Exception as e:
                    conn.rollback()
                    flash(f"No se pudo registrar el predio: {e}", "danger")

        # --- MODIFICAR ---
        elif accion == "modificar":
            try:
                pk = int(request.form.get("pk", 0))
            except ValueError:
                pk = 0

            direccion = request.form.get("direccion", "").strip()
            estado = request.form.get("estado", "").strip()
            municipio = request.form.get("municipio", "").strip()

            if not pk or not direccion or not estado or not municipio:
                flash("Selecciona un predio y completa los campos para modificar.", "warning")
            else:
                try:
                    sql = """
                        UPDATE Predios
                        SET direccion=%s, estado=%s, municipio=%s
                        WHERE pk_predio=%s AND fk_productor=%s
                    """
                    cursor.execute(sql, (direccion, estado, municipio, pk, id_usuario))
                    conn.commit()
                    if cursor.rowcount > 0:
                        flash("Predio modificado correctamente.", "success")
                    else:
                        flash("No se encontró el predio o no tienes permiso para modificarlo.", "warning")
                except Exception as e:
                    conn.rollback()
                    flash(f"No se pudo modificar: {e}", "danger")

        # --- ELIMINAR ---
        elif accion == "eliminar":
            try:
                pk = int(request.form.get("pk", 0))
            except ValueError:
                pk = 0

            if not pk:
                flash("Selecciona un predio a eliminar.", "warning")
            else:
                try:
                    cursor.execute("DELETE FROM Predios WHERE pk_predio=%s AND fk_productor=%s", (pk, id_usuario))
                    conn.commit()
                    if cursor.rowcount > 0:
                        flash("Predio eliminado.", "success")
                    else:
                        flash("No se encontró el predio o no tienes permiso para eliminarlo.", "warning")
                except Exception as e:
                    conn.rollback()
                    flash(f"No se pudo eliminar: {e}", "danger")

        # Después de POST volvemos a la misma página para mostrar cambios
        return redirect(url_for("predios"))

    # --- CONSULTAR (solo los del usuario) ---
    try:
        cursor.execute(
            "SELECT pk_predio, direccion, estado, municipio FROM Predios WHERE fk_productor=%s ORDER BY pk_predio",
            (id_usuario,)
        )
        predios = cursor.fetchall()
    except Exception as e:
        predios = []
        flash(f"No se pudieron obtener los predios: {e}", "danger")
    finally:
        conn.close()
        
    return render_template("predios.html", predios=predios)

# ------------------ RUTAS DE MÓDULOS (TEMPORALES) ------------------


@app.route("/productor")
def productor():
    return "<h2>Pendiente: Módulo Productor</h2>"

@app.route("/pesajes")
def pesajes():
    return "<h2>Pendiente: Módulo Pesajes</h2>"

@app.route("/siniga")
def siniga():
    return "<h2>Pendiente: Registro SINIGA</h2>"

@app.route("/seguimiento")
def seguimiento():
    return "<h2>Pendiente: Seguimiento Veterinario</h2>"

@app.route("/ventas")
def ventas():
    return "<h2>Pendiente: Ventas</h2>"

@app.route("/razas")
def razas():
    return "<h2>Pendiente: Razas</h2>"

@app.route("/upp")
def upp():
    return "<h2>Pendiente: Inscripción UPP</h2>"


# -------------------- PROGRAMA PRINCIPAL --------------------
if __name__ == "__main__":
    app.run(debug=True)

