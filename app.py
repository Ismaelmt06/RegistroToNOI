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

# --- MOTOR DE CÁLCULO DE ESTADÍSTICAS ---
def calcular_todas_las_estadisticas(historial):
    if not historial:
        return {}
    clasificacion = {}
    rachas_actuales = {}
    portador_trofeo = None
    def asegurar_equipo(equipo):
        if equipo not in clasificacion:
            clasificacion[equipo] = {
                'V': 0, 'E': 0, 'D': 0, 'T': 0, 'P': 0, 'PPM': 0.0,
                'Mejor Racha': 0, 'Destronamientos': 0, 'Intentos': 0, 
                'Indice Destronamiento': 0.0, 'Partidos con Trofeo': 0
            }
            rachas_actuales[equipo] = 0
    for i, partido in enumerate(historial):
        ganador = partido.get('Equipo Ganador')
        perdedor = partido.get('Equipo Perdedor')
        resultado = partido.get('Resultado')
        if not all([ganador, perdedor, resultado]):
            continue
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
            portador_en_partido = portador_trofeo
            if ganador == portador_en_partido or perdedor == portador_en_partido:
                aspirante = ganador if perdedor == portador_en_partido else perdedor
                clasificacion[aspirante]['Intentos'] += 1
                if resultado == "Victoria" and ganador == aspirante:
                    clasificacion[aspirante]['Destronamientos'] += 1
                    portador_trofeo = aspirante
                else: 
                    clasificacion[portador_en_partido]['Partidos con Trofeo'] += 1
    for equipo, stats in clasificacion.items():
        stats['T'] = stats['V'] + stats['E'] + stats['D']
        stats['P'] = (stats['V'] * 2) + (stats['E'] * 1)
        stats['PPM'] = (stats['P'] / stats['T']) if stats['T'] > 0 else 0.0
        if stats['Intentos'] > 0:
            stats['Indice Destronamiento'] = (stats['Destronamientos'] / stats['Intentos']) * 100
    if portador_trofeo and portador_trofeo in clasificacion:
        clasificacion[portador_trofeo]['Portador'] = True
    return clasificacion

# --- GESTIÓN DE DATOS ---
def recargar_y_recalcular_todo():
    sh_historial = conectar_a_gsheets("HistorialPartidos")
    historial = sh_historial.get_all_records() if sh_historial else []
    clasificacion_calculada = calcular_todas_las_estadisticas(historial)
    st.session_state.clasificacion = clasificacion_calculada
    st.session_state.historial = historial
    st.session_state.portador_actual = None
    for equipo, stats in clasificacion_calculada.items():
        if stats.get('Portador'):
            st.session_state.portador_actual = equipo
            break
    st.session_state.app_cargada = True

def guardar_clasificacion_completa():
    sh_clasif = conectar_a_gsheets("Hoja1")
    if sh_clasif:
        clasif_para_guardar = st.session_state.get('clasificacion', {})
        encabezados = [
            "Equipo", "PJ", "V", "E", "D", "P", "PPP", "Partidos con Trofeo",
            "Mejor Racha", "Intentos", "Destronamientos", "Indice Destronamiento"
        ]
        datos = [encabezados]
        for eq, stats in clasif_para_guardar.items():
            fila = [
                eq, stats['T'], stats['V'], stats['E'], stats['D'], stats['P'], stats['PPM'],
                stats['Partidos con Trofeo'], stats['Mejor Racha'], stats['Intentos'],
                stats['Destronamientos'], stats['Indice Destronamiento']
            ]
            datos.append(fila)
        sh_clasif.clear()
        sh_clasif.update(datos, 'A1')

def guardar_partido_en_historial(ganador, resultado, perdedor):
    sh = conectar_a_gsheets("HistorialPartidos")
    if sh:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sh.append_row([fecha, ganador, resultado, perdedor], value_input_option='USER_ENTERED')

def reescribir_historial_completo(nuevo_historial):
    sh_historial = conectar_a_gsheets("HistorialPartidos")
    if sh_historial:
        encabezados = ["Fecha", "Equipo Ganador", "Resultado", "Equipo Perdedor"]
        datos = [encabezados]
        for partido in nuevo_historial:
            datos.append([partido['Fecha'], partido['Equipo Ganador'], partido['Resultado'], partido['Equipo Perdedor']])
        sh_historial.clear()
        sh_historial.update(datos, 'A1')

# --- CARGA INICIAL DE LA APP ---
if 'app_cargada' not in st.session_state:
    recargar_y_recalcular_todo()

# --- PÁGINAS DE LA APLICACIÓN ---
def pagina_añadir_partido():
    st.header("⚽ Añadir Nuevo Partido")
    portador = st.session_state.get('portador_actual', None)

    if not portador and not st.session_state.get('historial', []):
        st.info("No hay campeón actual. Se registrará el primer partido para determinarlo.")
    else:
        st.info(f"El campeón actual que debe defender el título es: **{portador}** 👑")

    with st.form(key="partido_form"):
        tipo_resultado = st.radio("Elige el tipo de resultado:", ("Victoria / Derrota", "Empate"))
        
        if tipo_resultado == "Victoria / Derrota":
            equipo_ganador = st.text_input("Equipo Ganador")
            equipo_perdedor = st.text_input("Equipo Perdedor")
        else:
            equipo_A = st.text_input("Equipo A")
            equipo_B = st.text_input("Equipo B")

        submit_button = st.form_submit_button(label="Registrar Partido")

    if submit_button:
        if tipo_resultado == "Victoria / Derrota":
            equipos = [equipo_ganador, equipo_perdedor]
            ganador, perdedor, resultado = equipo_ganador, equipo_perdedor, "Victoria"
        else:
            equipos = [equipo_A, equipo_B]

        if not all(equipos) or equipos[0].lower() == equipos[1].lower():
            st.error("Error: Introduce dos nombres de equipo válidos y diferentes.")
            return

        if portador and portador.lower() not in [e.lower() for e in equipos]:
            st.error(f"Error: El campeón actual ({portador}) debe jugar en este partido.")
            return

        if tipo_resultado == "Empate":
            aspirante = equipos[1] if equipos[0].lower() == portador.lower() else equipos[0]
            ganador, perdedor, resultado = portador, aspirante, "Empate"
            st.warning(f"Resultado de Empate: {portador} (campeón) retiene el título y suma 1 punto.")
        
        guardar_partido_en_historial(ganador, resultado, perdedor)
        recargar_y_recalcular_todo()
        guardar_clasificacion_completa()
        st.success("¡Partido registrado con éxito! La página se recargará.")
        st.rerun()

def pagina_mostrar_clasificacion():
    st.header("📊 Tabla de Clasificación General")
    clasif = st.session_state.get('clasificacion', {})
    if not clasif:
        st.info("Aún no hay datos. Añade el primer partido para empezar.")
    else:
        df = pd.DataFrame.from_dict(clasif, orient='index').sort_values(by="P", ascending=False)
        df['Equipo'] = df.index
        df['Equipo'] = df.apply(lambda row: f"{row['Equipo']} 👑" if row.get('Portador') else row['Equipo'], axis=1)
        df = df.set_index('Equipo')
        df['PPM'] = df['PPM'].map('{:,.2f}'.format)
        df['Indice Destronamiento'] = df['Indice Destronamiento'].map('{:,.2f}%'.format)

        nuevo_orden_display = ["T", "V", "E", "D", "P", "PPM", "Partidos con Trofeo", "Mejor Racha", "Intentos", "Destronamientos", "Indice Destronamiento"]
        nuevos_nombres = {
            "T": "PJ", "V": "V", "E": "E", "D": "D", "P": "P", "PPM": "PPP",
            "Partidos con Trofeo": "Partidos con Trofeo", "Mejor Racha": "Mejor Racha",
            "Intentos": "Intentos", "Destronamientos": "Destronamientos", "Indice Destronamiento": "Índice Éxito"
        }
        df_display = df[nuevo_orden_display].rename(columns=nuevos_nombres)
        st.dataframe(df_display)

def pagina_historial_partidos():
    st.header("📜 Historial de Partidos")
    historial = st.session_state.get('historial', [])
    if not historial:
        st.info("Aún no se ha registrado ningún partido.")
    else:
        st.dataframe(pd.DataFrame(historial).iloc[::-1])

def pagina_eliminar_partido():
    st.header("❌ Eliminar un Partido Concreto")
    historial = st.session_state.get('historial', [])
    if not historial:
        st.info("No hay partidos en el historial para eliminar.")
        return
    opciones_partidos = [f"Partido {i+1} ({p['Fecha']}): {p['Equipo Ganador']} vs {p['Equipo Perdedor']}" for i, p in enumerate(historial)]
    partido_a_eliminar = st.selectbox("Selecciona el partido a eliminar:", options=opciones_partidos, index=None, placeholder="Elige un partido...")
    if partido_a_eliminar:
        if st.button("Eliminar Partido Seleccionado"):
            indice = opciones_partidos.index(partido_a_eliminar)
            nuevo_historial = [p for i, p in enumerate(historial) if i != indice]
            reescribir_historial_completo(nuevo_historial)
            recargar_y_recalcular_todo()
            guardar_clasificacion_completa()
            st.success("¡Partido eliminado! La página se recargará.")
            st.rerun()

# --- CORRECCIÓN EN LA FUNCIÓN DE BORRADO ---
def pagina_borrar_datos():
    st.header("🗑️ Borrar Todo")
    st.warning("⚠️ ¡Atención! Esto borrará AMBAS hojas: la clasificación y el historial completo.")
    confirmacion = st.text_input("Para confirmar, escribe 'BORRAR TODO' en mayúsculas:")
    if st.button("Borrar toda la información"):
        if confirmacion == "BORRAR TODO":
            # Borramos y re-escribimos los encabezados para evitar errores futuros
            sh_clasif = conectar_a_gsheets("Hoja1")
            if sh_clasif:
                sh_clasif.clear()
                encabezados_clasif = [
                    "Equipo", "PJ", "V", "E", "D", "P", "PPP", "Partidos con Trofeo",
                    "Mejor Racha", "Intentos", "Destronamientos", "Indice Destronamiento"
                ]
                sh_clasif.update([encabezados_clasif], 'A1')

            sh_historial = conectar_a_gsheets("HistorialPartidos")
            if sh_historial:
                sh_historial.clear()
                encabezados_historial = ["Fecha", "Equipo Ganador", "Resultado", "Equipo Perdedor"]
                sh_historial.update([encabezados_historial], 'A1')
            
            st.session_state.clear()
            st.success("¡Todos los datos han sido borrados! La página se recargará.")
            st.rerun()
        else:
            st.error("Confirmación incorrecta.")

# --- MENÚ PRINCIPAL ---
st.set_page_config(page_title="ToNOI", page_icon="👑", layout="wide")
st.title("👑 Torneo No Oficial de Inglaterra (ToNOI)")
st.sidebar.title("Menú")

opciones = ("Añadir Partido", "Clasificación General", "Historial de Partidos", "Eliminar Partido", "Borrar Todo")
opcion = st.sidebar.radio("Elige una opción:", opciones)

if opcion == "Añadir Partido":
    pagina_añadir_partido()
elif opcion == "Clasificación General":
    pagina_mostrar_clasificacion()
elif opcion == "Historial de Partidos":
    pagina_historial_partidos()
elif opcion == "Eliminar Partido":
    pagina_eliminar_partido()
elif opcion == "Borrar Todo":
    pagina_borrar_datos()
