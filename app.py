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

        foto_perfil = request.files.get("foto_perfil")
        foto_lateral = request.files.get("foto_lateral")

        perfil_bytes = foto_perfil.read() if foto_perfil and foto_perfil.filename else None
        lateral_bytes = foto_lateral.read() if foto_lateral and foto_lateral.filename else None

        # REGISTRAR
        if accion == "registrar":
            nombre = request.form["nombre"]
            fecha = request.form["fecha"]
            cruze = request.form["cruze"] or "Sin conocer"
            sexo = request.form["sexo"]
            peso_actual = request.form.get("peso_actual") or None
            fk_productor = request.form["fk_productor"] or None
            fk_raza = request.form["fk_raza"] or None

            sql = """INSERT INTO Animales 
                (nombre, fecha_nacimiento, cruze, sexo, peso_actual,
                 fk_productor, fk_raza, foto_perfil, foto_lateral)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            cursor.execute(sql, (
                nombre, fecha, cruze, sexo, peso_actual, 
                fk_productor, fk_raza, perfil_bytes, lateral_bytes
            ))
            conn.commit()

        # MODIFICAR
        elif accion == "modificar":
            pk = request.form["pk"]
            nombre = request.form["nombre"]
            fecha = request.form["fecha"]
            cruze = request.form["cruze"]
            sexo = request.form["sexo"]
            peso_actual = request.form.get("peso_actual")
            fk_productor = request.form["fk_productor"]
            fk_raza = request.form["fk_raza"]

            cursor.execute("""
                UPDATE Animales
                SET nombre=%s, fecha_nacimiento=%s, cruze=%s,
                    sexo=%s, peso_actual=%s,
                    fk_productor=%s, fk_raza=%s
                WHERE pk_animal=%s
            """, (nombre, fecha, cruze, sexo, peso_actual, fk_productor, fk_raza, pk))

            if perfil_bytes:
                cursor.execute("UPDATE Animales SET foto_perfil=%s WHERE pk_animal=%s", (perfil_bytes, pk))
            if lateral_bytes:
                cursor.execute("UPDATE Animales SET foto_lateral=%s WHERE pk_animal=%s", (lateral_bytes, pk))

            conn.commit()

        # ELIMINAR
        elif accion == "eliminar":
            pk = request.form["pk"]
            cursor.execute("DELETE FROM Animales WHERE pk_animal=%s", (pk,))
            conn.commit()

    # CONSULTA CON NOMBRES
    cursor.execute("""
        SELECT 
            a.pk_animal,
            a.nombre,
            a.fecha_nacimiento,
            a.cruze,
            p.nombre AS productor,
            r.nombre AS raza,
            a.sexo,
            a.peso_actual
        FROM Animales a
        LEFT JOIN Productores p ON a.fk_productor = p.pk_productor
        LEFT JOIN Razas r ON a.fk_raza = r.pk_raza
    """)
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


@app.route("/pesajes")
def pesajes():
    return "<h2>Pendiente: Módulo Pesajes</h2>"

#_-------------------------------SIINIGA-------------------------------

@app.route("/registro_siniga", methods=["GET", "POST"])
def registro_siniga():
    conn,cursor = conectar_bd()

    # ----- Registrar -----
    if request.method == "POST" and request.form["accion"] == "registrar":
        fk_animal = request.form["fk_animal"]
        arete = request.form["arete"]

        cursor.execute("""
            INSERT INTO Registro_SINIGA (fk_animal, arete)
            VALUES (%s, %s)
        """, (fk_animal, arete))
        conn.commit()

    # ----- Modificar -----
    if request.method == "POST" and request.form["accion"] == "modificar":
        pk = request.form["pk"]
        fk_animal = request.form["fk_animal"]
        arete = request.form["arete"]

        cursor.execute("""
            UPDATE Registro_SINIGA
            SET fk_animal=%s, arete=%s
            WHERE id=%s
        """, (fk_animal, arete, pk))
        conn.commit()

    # ----- Eliminar -----
    if request.method == "POST" and request.form["accion"] == "eliminar":
        pk = request.form["pk"]
        cursor.execute("DELETE FROM Registro_SINIGA WHERE id=%s", (pk,))
        conn.commit()

    # ----- Consultar -----
    cursor.execute("""
        SELECT r.id, r.fk_animal, r.arete, a.nombre
        FROM Registro_SINIGA r
        INNER JOIN Animales a ON r.fk_animal = a.pk_animal
    """)
    registros = cursor.fetchall()

    # Animales para el select
    cursor.execute("SELECT pk_animal, nombre FROM Animales")
    animales = cursor.fetchall()

    conn.close()

    return render_template("registro_siniga.html",
                           animales=animales,
                           registros=registros)



# ---------------- SEGUIMIENTO VETERINARIO ----------------

@app.route("/seguimiento", methods=["GET", "POST"])
def seguimiento():
    conn = None
    cursor = None

    if request.method == "POST":
        accion = request.form.get("accion")

        try:
            conn,cursor = conectar_bd()
            # --- Obtener campos ---
            pk = request.form.get("pk")
            fk_animal = request.form.get("fk_animal")
            tipo_tratamiento = request.form.get("tipo_tratamiento")
            fecha_actual = request.form.get("fecha_actual")
            prox_fecha = request.form.get("prox_fecha")

            # --- REGISTRAR ---
            if accion == "registrar":
                cursor.execute("""
                    INSERT INTO Seguimiento_vet (fk_animal, tipo_tratamiento, fecha_actual, prox_fecha)
                    VALUES (%s, %s, %s, %s)
                """, (fk_animal, tipo_tratamiento, fecha_actual, prox_fecha))
                conn.commit()
                flash("Seguimiento registrado correctamente", "success")

            # --- MODIFICAR ---
            elif accion == "modificar":
                cursor.execute("""
                    UPDATE Seguimiento_vet SET 
                    fk_animal=%s, tipo_tratamiento=%s, fecha_actual=%s, prox_fecha=%s
                    WHERE pk_segui_vet=%s
                """, (fk_animal, tipo_tratamiento, fecha_actual, prox_fecha, pk))
                conn.commit()
                flash("Seguimiento modificado correctamente", "info")

            # --- ELIMINAR ---
            elif accion == "eliminar":
                cursor.execute("DELETE FROM Seguimiento_vet WHERE pk_segui_vet=%s", (pk,))
                conn.commit()
                flash("Seguimiento eliminado", "danger")

        except Exception as e:
            flash(f"Error: {e}", "danger")

    # --- CONSULTAR REGISTROS ---
    conn, cursor =conectar_bd()
    cursor.execute("""
        SELECT pk_segui_vet, fk_animal, tipo_tratamiento, fecha_actual, prox_fecha
        FROM Seguimiento_vet
        ORDER BY pk_segui_vet DESC
    """)
    seguimientos = cursor.fetchall()

    # --- obtener animales para el select ---
    cursor.execute("SELECT pk_animal, nombre FROM Animales")
    animales = cursor.fetchall()

    return render_template("seguimiento.html", seguimientos=seguimientos, animales=animales)
#------------------------------------------------------------------------------------------

@app.route("/ventas")
def ventas():
    return "<h2>Pendiente: Ventas</h2>"

@app.route("/razas")
def razas():
    return "<h2>Pendiente: Razas</h2>"

@app.route("/upp")
def upp():
    return "<h2>Pendiente: Inscripción UPP</h2>"


@app.route("/album_razas")
def album_razas():
    return render_template("album_razas.html")

# -------------------- PROGRAMA PRINCIPAL --------------------
if __name__ == "__main__":
    app.run(debug=True)
