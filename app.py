import streamlit as st
import pandas as pd
import gspread # Nueva librería

# --- CONFIGURACIÓN Y CONEXIÓN CON GOOGLE SHEETS ---

# Usamos los "Secrets" de Streamlit para guardar las credenciales de forma segura
CREDS = st.secrets["gcp_creds"]
NOMBRE_HOJA_CALCULO = "BaseDeDatosLiga" # ¡Asegúrate de que este nombre coincida!

def conectar_a_gsheets():
    """Conecta con Google Sheets usando las credenciales guardadas."""
    try:
        gc = gspread.service_account_from_dict(CREDS)
        sh = gc.open(NOMBRE_HOJA_CALCULO).sheet1
        return sh
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

def cargar_datos():
    """Carga los datos desde Google Sheets y los convierte a un diccionario."""
    sh = conectar_a_gsheets()
    if sh:
        try:
            # get_all_records convierte la hoja en una lista de diccionarios
            records = sh.get_all_records()
            # Convertimos la lista a un diccionario con el formato que usa la app
            tabla = {str(rec['Equipo']): {
                'V': int(rec['V']), 'E': int(rec['E']), 'D': int(rec['D']),
                'T': int(rec['T']), 'P': int(rec['P']), 'PPM': float(rec['PPM'])
            } for rec in records}
            return tabla
        except Exception as e:
            st.error(f"Error al cargar los datos: {e}")
            return {}
    return {}

def guardar_datos():
    """Guarda el estado actual de la tabla en Google Sheets."""
    sh = conectar_a_gsheets()
    if sh:
        try:
            # Preparamos los datos para ser escritos
            datos_para_escribir = []
            # La primera fila son los encabezados
            encabezados = ["Equipo", "V", "E", "D", "T", "P", "PPM"]
            datos_para_escribir.append(encabezados)

            # Convertimos el diccionario de la app de nuevo a una lista de listas
            for equipo, stats in st.session_state.tabla_clasificacion.items():
                fila = [equipo, stats['V'], stats['E'], stats['D'], stats['T'], stats['P'], stats['PPM']]
                datos_para_escribir.append(fila)

            # Borramos la hoja y escribimos los nuevos datos
            sh.clear()
            sh.update(datos_para_escribir, 'A1')
        except Exception as e:
            st.error(f"Error al guardar los datos: {e}")

# El resto del código es casi idéntico...

# Al iniciar la app, cargamos los datos
if 'tabla_clasificacion' not in st.session_state:
    st.session_state.tabla_clasificacion = cargar_datos()

def registrar_equipo_si_no_existe(nombre_equipo):
    if nombre_equipo not in st.session_state.tabla_clasificacion:
        st.session_state.tabla_clasificacion[nombre_equipo] = {'V': 0, 'E': 0, 'D': 0, 'T': 0, 'P': 0, 'PPM': 0.0}
        st.info(f"Equipo '{nombre_equipo}' añadido a la clasificación.")

def actualizar_estadisticas_calculadas(nombre_equipo):
    stats = st.session_state.tabla_clasificacion[nombre_equipo]
    stats['T'] = stats['V'] + stats['E'] + stats['D']
    stats['P'] = (stats['V'] * 2) + (stats['E'] * 1)
    if stats['T'] > 0:
        stats['PPM'] = stats['P'] / stats['T']
    else:
        stats['PPM'] = 0.0

def pagina_añadir_partido():
    st.header("⚽ Añadir Nuevo Partido")
    with st.form(key="partido_form"):
        tipo_resultado = st.radio("¿Cuál fue el resultado?", ("Victoria / Derrota", "Empate (Regla especial)"))
        if tipo_resultado == "Victoria / Derrota":
            ganador = st.text_input("Equipo Ganador")
            perdedor = st.text_input("Equipo Perdedor")
        else:
            empatador = st.text_input("Equipo que suma 1 punto (Empate)")
            perdedor_empate = st.text_input("Equipo que suma 0 puntos (Derrota)")
        submit_button = st.form_submit_button(label="Registrar Partido")

    if submit_button:
        # La lógica de validación y actualización es la misma
        if tipo_resultado == "Victoria / Derrota":
            if not ganador or not perdedor or ganador.lower() == perdedor.lower():
                st.error("ERROR: Nombres no válidos o equipos idénticos.")
                return
            registrar_equipo_si_no_existe(ganador)
            registrar_equipo_si_no_existe(perdedor)
            st.session_state.tabla_clasificacion[ganador]['V'] += 1
            st.session_state.tabla_clasificacion[perdedor]['D'] += 1
            actualizar_estadisticas_calculadas(ganador)
            actualizar_estadisticas_calculadas(perdedor)
            guardar_datos() # <- ¡Guardamos en Google Sheets!
            st.success(f"¡Victoria para '{ganador}' registrada correctamente!")
        else: # Empate
            if not empatador or not perdedor_empate or empatador.lower() == perdedor_empate.lower():
                st.error("ERROR: Nombres no válidos o equipos idénticos.")
                return
            registrar_equipo_si_no_existe(empatador)
            registrar_equipo_si_no_existe(perdedor_empate)
            st.session_state.tabla_clasificacion[empatador]['E'] += 1
            st.session_state.tabla_clasificacion[perdedor_empate]['D'] += 1
            actualizar_estadisticas_calculadas(empatador)
            actualizar_estadisticas_calculadas(perdedor_empate)
            guardar_datos() # <- ¡Guardamos en Google Sheets!
            st.success(f"Empate para '{empatador}' y derrota para '{perdedor_empate}' registrados.")

def pagina_mostrar_clasificacion():
    st.header("📊 Tabla de Clasificación")
    if not st.session_state.tabla_clasificacion:
        st.info("Aún no se han registrado partidos.")
    else:
        df = pd.DataFrame.from_dict(st.session_state.tabla_clasificacion, orient='index')
        df = df.sort_values(by="P", ascending=False)
        df['PPM'] = df['PPM'].map('{:,.2f}'.format)
        df.columns = ["Victorias", "Empates", "Derrotas", "Total Partidos", "Puntos", "Puntos/Partido"]
        df.index.name = "Equipo"
        st.dataframe(df)

def pagina_buscar_equipo():
    st.header("🔍 Buscar un Equipo")
    if not st.session_state.tabla_clasificacion:
        st.info("No hay equipos para buscar.")
        return
    lista_equipos = ["Selecciona un equipo..."] + sorted(list(st.session_state.tabla_clasificacion.keys()))
    nombre_buscado = st.selectbox("Elige el equipo que quieres ver:", options=lista_equipos)
    if nombre_buscado != "Selecciona un equipo...":
        stats = st.session_state.tabla_clasificacion[nombre_buscado]
        st.subheader(f"Estadísticas de: {nombre_buscado}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Puntos Totales (P)", stats['P'])
        col2.metric("Partidos Jugados (T)", stats['T'])
        col3.metric("Puntos por Partido", f"{stats['PPM']:.2f}")
        st.write(f"**Victorias (V):** {stats['V']}")
        st.write(f"**Empates (E):** {stats['E']}")
        st.write(f"**Derrotas (D):** {stats['D']}")

# --- MENÚ PRINCIPAL Y EJECUCIÓN ---
st.set_page_config(page_title="Clasificación de Liga", page_icon="🏆", layout="wide")
st.title("🏆 Gestor de Clasificación de Liga")
st.sidebar.title("Menú Principal")
opcion = st.sidebar.radio("Elige una opción:", ("Añadir Partido", "Mostrar Clasificación", "Buscar Equipo"))

if opcion == "Añadir Partido":
    pagina_añadir_partido()
elif opcion == "Mostrar Clasificación":
    pagina_mostrar_clasificacion()
elif opcion == "Buscar Equipo":
    pagina_buscar_equipo()