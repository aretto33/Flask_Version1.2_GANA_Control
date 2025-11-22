from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
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
        sql = """
        SELECT id_usuario, usuario, password, rol, fk_productor
        FROM usuarios 
        WHERE usuario=%s AND rol=%s
        """
        cursor.execute(sql, (usuario, rol))
        result = cursor.fetchone()

        if result:
            id_user, db_user, db_pass, db_rol, db_fk = result
            if db_pass == password:
                return True, {"id_usuario": id_user, "rol": db_rol, "fk_productor": db_fk}
            else:
                return False, "Contraseña incorrecta"
        else:
            return False, "Usuario o rol no encontrado"

    except Exception as e:
        return False, f"Error: {e}"
    finally:
        conn.close()


# -------------------- LOGIN --------------------
@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    conn, cursor = conectar_bd()

    # OBTENER PRODUCTORES PARA EL SELECT
    cursor.execute("SELECT pk_productor, nombre FROM Productores")
    productores = cursor.fetchall()

    if request.method == "POST":
        usuario = request.form["usuario"]
        contra = request.form["password"]
        rol = request.form["rol"]

        exito, info = verificar_credenciales(usuario, contra, rol)

        if exito:
            session["usuario"] = usuario
            session["rol"] = rol

            # SI ES PRODUCTOR, GUARDAMOS EL FK
            if rol == "Productor":
                session["fk_productor"] = request.form.get("fk_productor")

            flash(f"Bienvenido {usuario} ({rol})", "success")
            return redirect(url_for("dashboard"))
        else:
            flash(info, "danger")

    conn.close()

    return render_template("login.html", productores=productores)


#--------------- REGISTRAR -----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        usuario = request.form["usuario"]
        contra = request.form["password"]
        rol = request.form["rol"]

        prod_id = None  # Por defecto no tiene productor asignado

        conn, cursor = conectar_bd()
        if not conn:
            flash("Error al conectar con la base de datos", "danger")
            return redirect(url_for("register"))

        try:
            # SI ES PRODUCTOR, PRIMERO INSERTAR EN TABLA PRODUCTORES
            if rol == "Productor":
                nombre = request.form["prod_nombre"]
                ap_pat = request.form["prod_apellido_pat"]
                ap_mat = request.form["prod_apellido_mat"]

                sql_prod = """
                INSERT INTO Productores (nombre, apellido_pat, apellido_mat, fk_predio, UPP)
                VALUES (%s, %s, %s, NULL, 'No inscrito')
                """
                cursor.execute(sql_prod, (nombre, ap_pat, ap_mat))
                conn.commit()

                prod_id = cursor.lastrowid

            # INSERTAR USUARIO
            sql = """
            INSERT INTO usuarios (usuario, password, rol, fk_productor)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (usuario, contra, rol, prod_id))
            conn.commit()

            flash("Usuario registrado correctamente", "success")
            return redirect(url_for("login"))

        except mariadb.Error as e:
            flash(f"No se pudo registrar: {e}", "danger")

        finally:
            conn.close()

    return render_template("register.html")


#----------------- Dashboard -----------------
@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))

    productor_nombre = None

    if session.get("fk_productor"):
        conn, cursor = conectar_bd()
        cursor.execute("SELECT nombre FROM productores WHERE pk_productor=%s", (session["fk_productor"],))
        row = cursor.fetchone()
        conn.close()

        if row:
            productor_nombre = row[0]

    return render_template(
        "dashboard.html",
        usuario=session["usuario"],
        rol=session["rol"],
        productor=productor_nombre
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('inicio'))

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

            cursor.execute(sql, (
                nombre, fecha, cruze,
                fk_productor, fk_raza,
                perfil_bytes, lateral_bytes
            ))
            conn.commit()

        # --- MODIFICAR ---
        elif accion == "modificar":
            pk = request.form["pk"]
            nombre = request.form["nombre"]
            fecha = request.form["fecha"]
            cruze = request.form["cruze"]
            fk_productor = request.form["fk_productor"]
            fk_raza = request.form["fk_raza"]

            sql = """UPDATE Animales
                     SET nombre=%s, fecha_nacimiento=%s, cruze=%s,
                         fk_productor=%s, fk_raza=%s
                     WHERE pk_animal=%s"""

            cursor.execute(sql, (nombre, fecha, cruze, fk_productor, fk_raza, pk))

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

    cursor.execute("SELECT pk_productor, nombre FROM Productores")
    productores = cursor.fetchall()

    cursor.execute("SELECT pk_raza, nombre FROM Razas")
    razas = cursor.fetchall()

    conn.close()

    return render_template("animales.html", animales=animales, productores=productores, razas=razas)


# ------------------ Mostrar imágenes ------------------
@app.route("/imagen_animal/<int:id>/<string:tipo>")
def imagen_animal(id, tipo):
    conn, cursor = conectar_bd()
    cursor.execute(f"SELECT {tipo} FROM Animales WHERE pk_animal=%s", (id,))
    imagen = cursor.fetchone()[0]
    conn.close()

    if imagen is None:
        return "", 404

    return Response(imagen, mimetype="image/jpeg")


#------------------- PREDIOS -------------------
@app.route("/predios", methods=["GET", "POST"])
def predios():

    if "fk_productor" not in session:
        flash("Inicia sesión para acceder a Predios.", "warning")
        return redirect(url_for("login"))

    fk_productor = session["fk_productor"]

    conn, cursor = conectar_bd()

    # --------------------
    # Obtener productores
    # --------------------
    cursor.execute("SELECT pk_productor, nombre FROM Productores")
    productores = cursor.fetchall()

    # --------------------
    # POST
    # --------------------
    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "registrar":
            direccion = request.form.get("direccion")
            estado = request.form.get("estado")
            municipio = request.form.get("municipio")
            fk_prod = request.form.get("fk_productor")  # 👈 nuevo

            sql = """
                INSERT INTO Predios (direccion, estado, municipio, fk_productor)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (direccion, estado, municipio, fk_prod))
            conn.commit()

        elif accion == "modificar":
            pk = request.form.get("pk")
            direccion = request.form.get("direccion")
            estado = request.form.get("estado")
            municipio = request.form.get("municipio")
            fk_prod = request.form.get("fk_productor")

            sql = """
                UPDATE Predios
                SET direccion=%s, estado=%s, municipio=%s, fk_productor=%s
                WHERE pk_predio=%s
            """
            cursor.execute(sql, (direccion, estado, municipio, fk_prod, pk))
            conn.commit()

        elif accion == "eliminar":
            pk = request.form.get("pk")
            cursor.execute("DELETE FROM Predios WHERE pk_predio=%s", (pk,))
            conn.commit()

        return redirect(url_for("predios"))

    # --------------------
    # GET
    # --------------------
    cursor.execute("""
        SELECT pk_predio, direccion, estado, municipio
        FROM Predios
        WHERE fk_productor=%s
    """, (fk_productor,))
    predios = cursor.fetchall()

    conn.close()

    return render_template("predios.html", predios=predios, productores=productores)

#----------------Modificar los datos del productor--------------
@app.route("/mi_productor", methods=["GET", "POST"])
def mi_productor():
    if "fk_productor" not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for("login"))

    fk_productor = session["fk_productor"]
    conn, cursor = conectar_bd()

    # --- GUARDAR CAMBIOS ---
    if request.method == "POST":
        nombre = request.form.get("nombre")
        apellido_pat = request.form.get("apellido_pat")
        apellido_mat = request.form.get("apellido_mat")
        upp = request.form.get("UPP")
        rfc = request.form.get("RFC")

        sql = """
            UPDATE Productores
            SET nombre=%s, apellido_pat=%s, apellido_mat=%s, UPP=%s, RFC=%s
            WHERE pk_productor=%s
        """

        try:
            cursor.execute(sql, (nombre, apellido_pat, apellido_mat, upp, rfc, fk_productor))
            conn.commit()
            flash("Datos actualizados correctamente.", "success")
        except mariadb.IntegrityError:
            flash(" El RFC ya está registrado en otro productor.", "danger")

        return redirect(url_for("mi_productor"))

    # --- OBTENER DATOS DEL PRODUCTOR LOGUEADO ---
    cursor.execute("""
        SELECT pk_productor, nombre, apellido_pat, apellido_mat, UPP, RFC
        FROM Productores
        WHERE pk_productor=%s
    """, (fk_productor,))

    productor = cursor.fetchone()
    conn.close()

    return render_template("mi_productor.html", productor=productor)

# ------------------ RUTAS TEMPORALES ------------------
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
