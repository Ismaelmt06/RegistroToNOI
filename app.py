import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- CONFIGURACIÓN Y CONEXIÓN ---
CREDS = st.secrets["gcp_creds"]
ID_HOJA_CALCULO = "18x6wCv0E7FOpuvwZpWYRSFi56E-_RR2Gm1deHyCLo2Y" # ¡¡¡ASEGÚRATE DE QUE TU ID ESTÁ AQUÍ!!!

def conectar_a_gsheets(nombre_hoja):
    try:
        gc = gspread.service_account_from_dict(CREDS)
        sh = gc.open_by_key(ID_HOJA_CALCULO).worksheet(nombre_hoja)
        return sh
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# --- MOTOR DE CÁLCULO DE ESTADÍSTICAS (MODIFICADO) ---
def calcular_todas_las_estadisticas(historial):
    if not historial:
        return {}

    clasificacion = {}
    rachas = {}
    rachas_actuales = {}
    destronamiento = {}
    portador_trofeo = None

    def asegurar_equipo(equipo):
        if equipo not in clasificacion:
            clasificacion[equipo] = {
                'V': 0, 'E': 0, 'D': 0, 'T': 0, 'P': 0, 'PPM': 0.0,
                'Mejor Racha': 0, 'Destronamientos': 0, 'Intentos': 0, 'Indice Destronamiento': 0.0
            }
            rachas_actuales[equipo] = 0

    for i, partido in enumerate(historial):
        ganador = partido['Equipo Ganador']
        perdedor = partido['Equipo Perdedor']
        resultado = partido['Resultado']

        asegurar_equipo(ganador)
        asegurar_equipo(perdedor)

        if resultado == "Empate":
            clasificacion[ganador]['E'] += 1
        else:
            clasificacion[ganador]['V'] += 1
        clasificacion[perdedor]['D'] += 1

        rachas_actuales[ganador] += 1
        if rachas_actuales[ganador] > clasificacion[ganador]['Mejor Racha']:
            clasificacion[ganador]['Mejor Racha'] = rachas_actuales[ganador]
        rachas_actuales[perdedor] = 0

        if i == 0:
            portador_trofeo = ganador
        else:
            if ganador == portador_trofeo or perdedor == portador_trofeo:
                portador_en_partido = portador_trofeo
                aspirante = ganador if perdedor == portador_trofeo else perdedor
                
                clasificacion[aspirante]['Intentos'] += 1
                
                if resultado == "Victoria" and ganador == aspirante:
                    clasificacion[aspirante]['Destronamientos'] += 1
                    portador_trofeo = aspirante

    for equipo, stats in clasificacion.items():
        stats['T'] = stats['V'] + stats['E'] + stats['D']
        stats['P'] = (stats['V'] * 2) + (stats['E'] * 1)
        stats['PPM'] = (stats['P'] / stats['T']) if stats['T'] > 0 else 0.0
        if stats['Intentos'] > 0:
            stats['Indice Destronamiento'] = (stats['Destronamientos'] / stats['Intentos']) * 100
    
    # Añadimos el portador actual a los datos para mostrarlo en la tabla
    if portador_trofeo and portador_trofeo in clasificacion:
        clasificacion[portador_trofeo]['Portador'] = True

    return clasificacion

# --- GESTIÓN DE DATOS ---
def cargar_y_calcular_todo():
    """Función central que lee el historial y calcula todo."""
    historial = conectar_a_gsheets("HistorialPartidos").get_all_records() if conectar_a_gsheets("HistorialPartidos") else []
    clasificacion_calculada = calcular_todas_las_estadisticas(historial)
    st.session_state.clasificacion = clasificacion_calculada
    st.session_state.historial = historial
    # Identificamos al portador para la página de añadir partido
    st.session_state.portador_actual = None
    for equipo, stats in clasificacion_calculada.items():
        if stats.get('Portador'):
            st.session_state.portador_actual = equipo
            break

def guardar_datos_completos():
    """Guarda la clasificación con todas las estadísticas en la Hoja1."""
    sh_clasif = conectar_a_gsheets("Hoja1")
    sh_historial = st.session_state.get('sh_historial_conn', None) # Reutilizar conexión si es posible
    if not sh_historial:
        st.session_state.sh_historial_conn = conectar_a_gsheets("HistorialPartidos")
        sh_historial = st.session_state.sh_historial_conn

    if sh_clasif:
        clasif_para_guardar = st.session_state.get('clasificacion', {})
        # Preparamos los datos para guardarlos
        datos = [[
            "Equipo", "V", "E", "D", "T", "P", "PPM",
            "Mejor Racha", "Destronamientos", "Intentos", "Indice Destronamiento"
        ]]
        for eq, stats in clasif_para_guardar.items():
            fila = [
                eq, stats['V'], stats['E'], stats['D'], stats['T'], stats['P'], stats['PPM'],
                stats['Mejor Racha'], stats['Destronamientos'], stats['Intentos'], stats['Indice Destronamiento']
            ]
            datos.append(fila)
        
        sh_clasif.clear()
        sh_clasif.update(datos, 'A1')

def guardar_partido_en_historial(ganador, resultado, perdedor):
    sh = conectar_a_gsheets("HistorialPartidos")
    if sh:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sh.append_row([fecha, ganador, resultado, perdedor], value_input_option='USER_ENTERED')


# --- CARGA INICIAL DE LA APP ---
if 'app_cargada' not in st.session_state:
    cargar_y_calcular_todo()
    st.session_state.app_cargada = True


# --- PÁGINAS DE LA APLICACIÓN ---
def pagina_añadir_partido():
    st.header("⚔️ Defensa del Título")
    
    portador = st.session_state.get('portador_actual', None)

    if not portador and not st.session_state.get('historial', []):
        st.subheader("Inicio del Campeonato")
        st.info("Se registrará el primer partido para determinar al campeón inicial.")
        with st.form(key="primer_partido_form"):
            equipo1 = st.text_input("Nombre del Equipo 1")
            equipo2 = st.text_input("Nombre del Equipo 2")
            submit = st.form_submit_button("Registrar Primer Partido")

            if submit:
                if not equipo1 or not equipo2 or equipo1.lower() == equipo2.lower():
                    st.error("Introduce dos nombres de equipo válidos y diferentes.")
                else:
                    guardar_partido_en_historial(equipo1, "Victoria", equipo2)
                    cargar_y_calcular_todo() # Recalculamos todo
                    guardar_datos_completos() # Guardamos la nueva clasificación
                    st.success(f"¡{equipo1} es el primer campeón! La página se recargará.")
                    st.rerun()
    else:
        st.info(f"El campeón actual es: **{portador}** 👑")
        with st.form(key="defensa_form"):
            aspirante = st.text_input("Nombre del Aspirante")
            resultado = st.radio("Resultado del partido:", ("Victoria del Portador", "Victoria del Aspirante (¡Nuevo Campeón!)", "Empate (Portador retiene)"))
            submit = st.form_submit_button("Registrar Defensa")

            if submit:
                if not aspirante or aspirante.lower() == portador.lower():
                    st.error("Introduce un aspirante válido y diferente al portador.")
                else:
                    if resultado == "Victoria del Portador":
                        guardar_partido_en_historial(portador, "Victoria", aspirante)
                    elif resultado == "Victoria del Aspirante (¡Nuevo Campeón!)":
                        guardar_partido_en_historial(aspirante, "Victoria", portador)
                    elif resultado == "Empate (Portador retiene)":
                        guardar_partido_en_historial(portador, "Empate", aspirante)
                    
                    cargar_y_calcular_todo()
                    guardar_datos_completos()
                    st.success("¡Partido registrado! La página se recargará para actualizar todo.")
                    st.rerun()

def pagina_mostrar_clasificacion():
    st.header("📊 Tabla de Clasificación General")
    clasif = st.session_state.get('clasificacion', {})
    if not clasif:
        st.info("Aún no hay datos. Añade el primer partido para empezar.")
    else:
        df = pd.DataFrame.from_dict(clasif, orient='index').sort_values(by="P", ascending=False)
        
        # Añadir la corona al portador
        df['Equipo'] = df.index
        df['Equipo'] = df.apply(lambda row: f"{row['Equipo']} 👑" if row.get('Portador') else row['Equipo'], axis=1)
        df = df.set_index('Equipo')
        
        # Formateo y selección de columnas
        df['PPM'] = df['PPM'].map('{:,.2f}'.format)
        df['Indice Destronamiento'] = df['Indice Destronamiento'].map('{:,.2f}%'.format)

        columnas_a_mostrar = [
            "V", "E", "D", "Total", "Puntos", "Puntos/Partido",
            "Mejor Racha", "Destronamientos", "Intentos", "Indice Destronamiento"
        ]
        df_display = df[columnas_a_mostrar]
        df_display.columns = ["V", "E", "D", "T", "P", "PPM", "Racha", "Éxitos", "Intentos", "Índice Éxito"]

        st.dataframe(df_display)

def pagina_historial_partidos():
    st.header("📜 Historial de Partidos")
    historial = st.session_state.get('historial', [])
    if not historial:
        st.info("Aún no se ha registrado ningún partido.")
    else:
        df_historial = pd.DataFrame(historial)
        st.dataframe(df_historial.iloc[::-1])

def pagina_borrar_datos():
    st.header("🗑️ Borrar Todo")
    st.warning("⚠️ ¡Atención! Esto borrará AMBAS hojas: la clasificación y el historial completo.")
    confirmacion = st.text_input("Para confirmar, escribe 'BORRAR TODO' en mayúsculas:")
    if st.button("Borrar toda la información"):
        if confirmacion == "BORRAR TODO":
            sh_clasif = conectar_a_gsheets("Hoja1")
            sh_historial = conectar_a_gsheets("HistorialPartidos")
            if sh_clasif: sh_clasif.clear()
            if sh_historial: sh_historial.clear()
            st.session_state.clear()
            st.success("¡Todos los datos han sido borrados! La página se recargará.")
            st.rerun()

# --- MENÚ PRINCIPAL ---
st.set_page_config(page_title="Liga del Destronamiento", page_icon="👑", layout="wide")
st.title("👑 Liga del Destronamiento")
st.sidebar.title("Menú")

opciones = ("Añadir Partido", "Clasificación General", "Historial de Partidos", "Borrar Todo")
opcion = st.sidebar.radio("Elige una opción:", opciones)

if opcion == "Añadir Partido":
    pagina_añadir_partido()
elif opcion == "Clasificación General":
    pagina_mostrar_clasificacion()
elif opcion == "Historial de Partidos":
    pagina_historial_partidos()
elif opcion == "Borrar Todo":
    pagina_borrar_datos()