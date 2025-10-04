import streamlit as st
import pandas as pd
import gspread
from datetime import datetime # <-- NUEVO: Para registrar la fecha

# --- CONFIGURACIÓN Y CONEXIÓN CON GOOGLE SHEETS ---
CREDS = st.secrets["gcp_creds"]

# PEGA AQUÍ LA ID QUE COPIASTE DE LA URL
ID_HOJA_CALCULO = "18x6wCv0E7FOpuvwZpWYRSFi56E-_RR2Gm1deHyCLo2Y" 

def conectar_a_gsheets(nombre_hoja):
    """Conecta con Google Sheets usando la ID única del archivo."""
    try:
        gc = gspread.service_account_from_dict(CREDS)
        # Usamos open_by_key para abrir por ID, es el método más fiable
        sh = gc.open_by_key(ID_HOJA_CALCULO).worksheet(nombre_hoja)
        return sh
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

def cargar_datos():
    """Carga los datos desde la hoja 'sheet1' (la principal) y los convierte a un diccionario."""
    sh = conectar_a_gsheets("Hoja1") # Usamos el nombre por defecto de la primera hoja
    if sh:
        try:
            records = sh.get_all_records()
            tabla = {}
            for rec in records:
                ppm_texto = str(rec.get('PPM', 0)).replace(',', '.')
                tabla[str(rec['Equipo'])] = {
                    'V': int(rec.get('V', 0)), 'E': int(rec.get('E', 0)), 'D': int(rec.get('D', 0)),
                    'T': int(rec.get('T', 0)), 'P': int(rec.get('P', 0)), 'PPM': float(ppm_texto)
                }
            return tabla
        except Exception as e:
            st.error(f"Error al cargar los datos de clasificación: {e}")
            return {}
    return {}

def guardar_datos():
    """Guarda el estado actual de la tabla de clasificación en Google Sheets."""
    sh = conectar_a_gsheets("Hoja1")
    if sh:
        try:
            datos_para_escribir = [["Equipo", "V", "E", "D", "T", "P", "PPM"]]
            for equipo, stats in st.session_state.tabla_clasificacion.items():
                fila = [equipo, stats['V'], stats['E'], stats['D'], stats['T'], stats['P'], stats['PPM']]
                datos_para_escribir.append(fila)
            sh.clear()
            sh.update(datos_para_escribir, 'A1')
        except Exception as e:
            st.error(f"Error al guardar los datos de clasificación: {e}")

# --- NUEVA FUNCIÓN PARA EL HISTORIAL ---
def guardar_partido_en_historial(ganador, resultado, perdedor):
    """Añade una nueva fila a la hoja 'HistorialPartidos'."""
    sh = conectar_a_gsheets("HistorialPartidos")
    if sh:
        try:
            # Formateamos la fecha y hora actual
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nueva_fila = [fecha_actual, ganador, resultado, perdedor]
            # append_row añade la fila al final sin borrar nada
            sh.append_row(nueva_fila, value_input_option='USER_ENTERED')
        except Exception as e:
            st.error(f"Error al guardar el partido en el historial: {e}")

# Al iniciar la app, cargamos los datos
if 'tabla_clasificacion' not in st.session_state:
    st.session_state.tabla_clasificacion = cargar_datos()

# --- FUNCIONES AUXILIARES (Sin cambios) ---
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

# --- PÁGINAS DE LA APLICACIÓN ---
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
            guardar_datos()
            guardar_partido_en_historial(ganador, "Victoria", perdedor) # <-- NUEVO
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
            guardar_datos()
            guardar_partido_en_historial(empatador, "Empate", perdedor_empate) # <-- NUEVO
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

# --- NUEVA PÁGINA PARA MOSTRAR EL HISTORIAL ---
def pagina_historial_partidos():
    """Muestra el historial de todos los partidos jugados."""
    st.header("📜 Historial de Partidos")
    sh = conectar_a_gsheets("HistorialPartidos")
    if sh:
        try:
            # Leemos todos los datos de la hoja de historial
            historial = sh.get_all_records()
            if not historial:
                st.info("Aún no se ha registrado ningún partido en el historial.")
            else:
                # Convertimos a DataFrame para mostrarlo en una tabla
                df_historial = pd.DataFrame(historial)
                # Mostramos los partidos más recientes primero
                st.dataframe(df_historial.iloc[::-1])
        except Exception as e:
            st.error(f"No se pudo cargar el historial: {e}")

# El resto de páginas no cambian...
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

def pagina_borrar_datos():
    st.header("🗑️ Borrar Clasificación")
    st.warning("⚠️ ¡Atención! Esta acción es irreversible y borrará todos los equipos y partidos registrados.")
    confirmacion = st.text_input("Para confirmar, escribe 'BORRAR' en mayúsculas:")
    if st.button("Borrar toda la clasificación"):
        if confirmacion == "BORRAR":
            st.session_state.tabla_clasificacion = {}
            guardar_datos()
            st.success("¡La clasificación ha sido borrada con éxito!")
            st.rerun()
        else:
            st.error("Confirmación incorrecta. La tabla no ha sido borrada.")

# --- MENÚ PRINCIPAL Y EJECUCIÓN ---
st.set_page_config(page_title="Clasificación de Liga", page_icon="🏆", layout="wide")
st.title("🏆 Gestor de Clasificación de Liga")
st.sidebar.title("Menú Principal")

# <-- AÑADIMOS LA NUEVA OPCIÓN AL MENÚ
opcion = st.sidebar.radio(
    "Elige una opción:",
    ("Añadir Partido", "Mostrar Clasificación", "Ver Historial", "Buscar Equipo", "Borrar Clasificación")
)

if opcion == "Añadir Partido":
    pagina_añadir_partido()
elif opcion == "Mostrar Clasificación":
    pagina_mostrar_clasificacion()
elif opcion == "Ver Historial": # <-- AÑADIMOS EL MANEJO DE LA NUEVA PÁGINA
    pagina_historial_partidos()
elif opcion == "Buscar Equipo":
    pagina_buscar_equipo()
elif opcion == "Borrar Clasificación":
    pagina_borrar_datos()