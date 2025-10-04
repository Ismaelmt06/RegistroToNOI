import streamlit as st
import pandas as pd
import json
import os # Necesario para comprobar si el archivo de datos existe

# --- CONFIGURACIÓN INICIAL Y PERSISTENCIA DE DATOS ---

# Nombre del archivo donde guardaremos los datos
NOMBRE_ARCHIVO = 'datos_liga.json'

def cargar_datos():
    """
    Carga la tabla de clasificación desde el archivo JSON.
    Si el archivo no existe o está vacío, devuelve un diccionario vacío.
    """
    if os.path.exists(NOMBRE_ARCHIVO):
        with open(NOMBRE_ARCHIVO, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # Si el archivo está corrupto o vacío, empezamos de cero
                return {}
    return {}

def guardar_datos():
    """Guarda la tabla de clasificación actual en el archivo JSON."""
    with open(NOMBRE_ARCHIVO, 'w', encoding='utf-8') as f:
        # Guardamos el diccionario de la sesión en el archivo
        json.dump(st.session_state.tabla_clasificacion, f, ensure_ascii=False, indent=4)

# Al iniciar la app, cargamos los datos del archivo a st.session_state
if 'tabla_clasificacion' not in st.session_state:
    st.session_state.tabla_clasificacion = cargar_datos()

# --- FUNCIONES AUXILIARES (Lógica del programa original) ---

def registrar_equipo_si_no_existe(nombre_equipo):
    """Añade un equipo a la tabla en st.session_state si no existe."""
    if nombre_equipo not in st.session_state.tabla_clasificacion:
        st.session_state.tabla_clasificacion[nombre_equipo] = {'V': 0, 'E': 0, 'D': 0, 'T': 0, 'P': 0, 'PPM': 0.0}
        st.info(f"Equipo '{nombre_equipo}' añadido a la clasificación.")

def actualizar_estadisticas_calculadas(nombre_equipo):
    """Recalcula los totales (P, T, PPM) para un equipo."""
    stats = st.session_state.tabla_clasificacion[nombre_equipo]
    stats['T'] = stats['V'] + stats['E'] + stats['D']
    stats['P'] = (stats['V'] * 2) + (stats['E'] * 1)
    if stats['T'] > 0:
        stats['PPM'] = stats['P'] / stats['T']
    else:
        stats['PPM'] = 0.0

# --- PÁGINAS DE LA APLICACIÓN ---

def pagina_añadir_partido():
    """Muestra el formulario para añadir un nuevo partido."""
    st.header("⚽ Añadir Nuevo Partido")

    with st.form(key="partido_form"):
        tipo_resultado = st.radio(
            "¿Cuál fue el resultado?",
            ("Victoria / Derrota", "Empate (Regla especial)")
        )

        if tipo_resultado == "Victoria / Derrota":
            ganador = st.text_input("Equipo Ganador")
            perdedor = st.text_input("Equipo Perdedor")
        else: # Empate
            empatador = st.text_input("Equipo que suma 1 punto (Empate)")
            perdedor_empate = st.text_input("Equipo que suma 0 puntos (Derrota)")

        submit_button = st.form_submit_button(label="Registrar Partido")

    if submit_button:
        if tipo_resultado == "Victoria / Derrota":
            if not ganador or not perdedor:
                st.error("ERROR: Ambos nombres de equipo son obligatorios.")
            elif ganador.lower() == perdedor.lower():
                st.error("ERROR: Debes introducir dos equipos diferentes.")
            else:
                registrar_equipo_si_no_existe(ganador)
                registrar_equipo_si_no_existe(perdedor)
                st.session_state.tabla_clasificacion[ganador]['V'] += 1
                st.session_state.tabla_clasificacion[perdedor]['D'] += 1
                actualizar_estadisticas_calculadas(ganador)
                actualizar_estadisticas_calculadas(perdedor)
                guardar_datos() # <- ¡NUEVO! Guardamos los datos tras el cambio
                st.success(f"¡Victoria para '{ganador}' registrada correctamente!")
        
        else: # Empate
            if not empatador or not perdedor_empate:
                st.error("ERROR: Ambos nombres de equipo son obligatorios.")
            elif empatador.lower() == perdedor_empate.lower():
                st.error("ERROR: Debes introducir dos equipos diferentes.")
            else:
                registrar_equipo_si_no_existe(empatador)
                registrar_equipo_si_no_existe(perdedor_empate)
                st.session_state.tabla_clasificacion[empatador]['E'] += 1
                st.session_state.tabla_clasificacion[perdedor_empate]['D'] += 1
                actualizar_estadisticas_calculadas(empatador)
                actualizar_estadisticas_calculadas(perdedor_empate)
                guardar_datos() # <- ¡NUEVO! Guardamos los datos tras el cambio
                st.success(f"Empate para '{empatador}' y derrota para '{perdedor_empate}' registrados.")


def pagina_mostrar_clasificacion():
    """Muestra la tabla de clasificación completa."""
    st.header("📊 Tabla de Clasificación")

    if not st.session_state.tabla_clasificacion:
        st.info("Aún no se han registrado partidos. Añade uno en el menú de la izquierda.")
    else:
        df = pd.DataFrame.from_dict(st.session_state.tabla_clasificacion, orient='index')
        df = df.sort_values(by="P", ascending=False)
        df['PPM'] = df['PPM'].map('{:,.2f}'.format)
        df.columns = ["Victorias", "Empates", "Derrotas", "Total Partidos", "Puntos", "Puntos/Partido"]
        df.index.name = "Equipo"
        st.dataframe(df)

def pagina_buscar_equipo():
    """Muestra las estadísticas de un equipo específico."""
    st.header("🔍 Buscar un Equipo")
    
    if not st.session_state.tabla_clasificacion:
        st.info("No hay equipos para buscar. Añade un partido primero.")
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

# Configuración de la página
st.set_page_config(page_title="Clasificación de Liga", page_icon="🏆", layout="wide")

st.title("🏆 Gestor de Clasificación de Liga")
st.sidebar.title("Menú Principal")
opcion = st.sidebar.radio(
    "Elige una opción:",
    ("Añadir Partido", "Mostrar Clasificación", "Buscar Equipo")
)

if opcion == "Añadir Partido":
    pagina_añadir_partido()
elif opcion == "Mostrar Clasificación":
    pagina_mostrar_clasificacion()
elif opcion == "Buscar Equipo":
    pagina_buscar_equipo()
