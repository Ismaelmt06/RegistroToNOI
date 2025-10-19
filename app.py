import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from collections import Counter

# --- CONFIGURACIÓN Y CONEXIÓN ---
CREDS = st.secrets["gcp_creds"]
ID_HOJA_CALCULO = "18x6wCv0E7FOpuvwZpWYRSFi56E-_RR2Gm1deHyCLo2Y" # ¡¡¡ASEGÚRATE DE QUE TU ID ESTÁ AQUÍ!!!

def conectar_a_gsheets(nombre_hoja):
    try:
        gc = gspread.service_account_from_dict(CREDS)
        sh = gc.open_by_key(ID_HOJA_CALCULO).worksheet(nombre_hoja)
        return sh
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Error: No se encuentra la pestaña '{nombre_hoja}'. Por favor, créala con el nombre exacto.")
        return None
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# --- MOTORES DE CÁLCULO ---
def calcular_todas_las_estadisticas(historial):
    # (El código de esta función no cambia)
    if not historial: return {}
    clasificacion = {}
    rachas_actuales = {}
    portador_trofeo = None
    def asegurar_equipo(equipo):
        if equipo and equipo not in clasificacion:
            clasificacion[equipo] = {'V': 0, 'E': 0, 'D': 0, 'T': 0, 'P': 0, 'PPM': 0.0, 'Mejor Racha': 0, 'Destronamientos': 0, 'Intentos': 0, 'Indice Destronamiento': 0.0, 'Partidos con Trofeo': 0}
            rachas_actuales[equipo] = 0
    for i, partido in enumerate(historial):
        ganador, perdedor, resultado = partido.get('Equipo Ganador'), partido.get('Equipo Perdedor'), partido.get('Resultado')
        if not all([ganador, perdedor, resultado]): continue
        asegurar_equipo(ganador); asegurar_equipo(perdedor)
        if resultado == "Empate": clasificacion[ganador]['E'] += 1
        else: clasificacion[ganador]['V'] += 1
        clasificacion[perdedor]['D'] += 1
        rachas_actuales[ganador] += 1
        if rachas_actuales[ganador] > clasificacion[ganador]['Mejor Racha']: clasificacion[ganador]['Mejor Racha'] = rachas_actuales[ganador]
        rachas_actuales[perdedor] = 0
        if i == 0: portador_trofeo = ganador
        else:
            portador_en_partido = portador_trofeo
            if ganador == portador_en_partido or perdedor == portador_en_partido:
                aspirante = ganador if perdedor == portador_en_partido else perdedor
                clasificacion[aspirante]['Intentos'] += 1
                if resultado == "Victoria" and ganador == aspirante:
                    clasificacion[aspirante]['Destronamientos'] += 1
                    portador_trofeo = aspirante
        if portador_trofeo: clasificacion[portador_trofeo]['Partidos con Trofeo'] += 1
    for equipo, stats in clasificacion.items():
        stats['T'] = stats['V'] + stats['E'] + stats['D']
        stats['P'] = (stats['V'] * 2) + (stats['E'] * 1)
        stats['PPM'] = (stats['P'] / stats['T']) if stats['T'] > 0 else 0.0
        if stats['Intentos'] > 0: stats['Indice Destronamiento'] = (stats['Destronamientos'] / stats['Intentos']) * 100
    if portador_trofeo and portador_trofeo in clasificacion: clasificacion[portador_trofeo]['Portador'] = True
    return clasificacion

def calcular_estadisticas_individuales(historial_goles):
    if not historial_goles: return {}
    goleadores = Counter(evento['Goleador'] for evento in historial_goles if evento.get('Goleador'))
    asistentes = Counter(evento['Asistente'] for evento in historial_goles if evento.get('Asistente'))
    jugadores = set(goleadores.keys()) | set(asistentes.keys())
    clasificacion_individual = {}
    for jugador in jugadores:
        goles = goleadores.get(jugador, 0)
        asistencias = asistentes.get(jugador, 0)
        clasificacion_individual[jugador] = {'Goles': goles, 'Asistencias': asistencias, 'G/A': goles + asistencias}
    return clasificacion_individual

def calcular_estadisticas_porteros(historial_porterias):
    if not historial_porterias: return {}
    porteros = Counter(evento['Portero'] for evento in historial_porterias if evento.get('Portero'))
    return {portero: {'Porterías a 0': count} for portero, count in porteros.items()}

# --- GESTIÓN DE DATOS ---
def recargar_y_recalcular_todo():
    # Carga datos del torneo
    sh_historial = conectar_a_gsheets("HistorialPartidos")
    historial = sh_historial.get_all_records() if sh_historial else []
    st.session_state.clasificacion = calcular_todas_las_estadisticas(historial)
    st.session_state.historial = historial
    st.session_state.portador_actual = next((eq for eq, stats in st.session_state.clasificacion.items() if stats.get('Portador')), None)
    # Carga datos goles
    sh_goles = conectar_a_gsheets("HistorialGoles")
    historial_goles = sh_goles.get_all_records() if sh_goles else []
    st.session_state.clasificacion_individual = calcular_estadisticas_individuales(historial_goles)
    st.session_state.historial_goles = historial_goles
    # Carga datos porterías a cero
    sh_porterias = conectar_a_gsheets("HistorialPorteriasCero")
    historial_porterias = sh_porterias.get_all_records() if sh_porterias else []
    st.session_state.clasificacion_porteros = calcular_estadisticas_porteros(historial_porterias)
    st.session_state.historial_porterias = historial_porterias
    st.session_state.app_cargada = True

def guardar_datos_completos():
    # Guardar clasificación de equipos
    sh_clasif = conectar_a_gsheets("Hoja1")
    if sh_clasif:
        clasif_para_guardar = st.session_state.get('clasificacion', {})
        encabezados = ["Equipo", "PJ", "V", "E", "D", "P", "PPP", "Partidos con Trofeo", "Mejor Racha", "Intentos", "Destronamientos", "Indice Destronamiento"]
        datos = [encabezados] + [[eq, s['T'], s['V'], s['E'], s['D'], s['P'], s['PPM'], s['Partidos con Trofeo'], s['Mejor Racha'], s['Intentos'], s['Destronamientos'], s['Indice Destronamiento']] for eq, s in clasif_para_guardar.items()]
        sh_clasif.clear(); sh_clasif.update(datos, 'A1')
    # Guardar clasificación individual
    sh_goleadores = conectar_a_gsheets("ClasificacionGoleadores")
    if sh_goleadores:
        clasif_ind_guardar = st.session_state.get('clasificacion_individual', {})
        encabezados = ["Jugador", "Goles", "Asistencias", "G/A"]
        datos = [encabezados] + [[j, s['Goles'], s['Asistencias'], s['G/A']] for j, s in clasif_ind_guardar.items()]
        sh_goleadores.clear(); sh_goleadores.update(datos, 'A1')
    # Guardar clasificación porteros
    sh_porteros = conectar_a_gsheets("ClasificacionPorteros")
    if sh_porteros:
        clasif_porteros_guardar = st.session_state.get('clasificacion_porteros', {})
        encabezados = ["Portero", "Porterías a 0"]
        datos = [encabezados] + [[p, s['Porterías a 0']] for p, s in clasif_porteros_guardar.items()]
        sh_porteros.clear(); sh_porteros.update(datos, 'A1')

def guardar_evento_historial(sh_name, data_row):
    sh = conectar_a_gsheets(sh_name)
    if sh: sh.append_row(data_row, value_input_option='USER_ENTERED')

def reescribir_historial_completo(sh_name, nuevo_historial, encabezados):
    sh = conectar_a_gsheets(sh_name)
    if sh:
        datos = [encabezados] + [list(row.values()) for row in nuevo_historial]
        sh.clear(); sh.update(datos, 'A1')

# --- CARGA INICIAL ---
if 'app_cargada' not in st.session_state:
    recargar_y_recalcular_todo()

# --- DEFINICIÓN DE PÁGINAS ---
def pagina_añadir_partido():
    st.header("⚽ Añadir Nuevo Partido")
    portador = st.session_state.get('portador_actual')
    historial = st.session_state.get('historial', [])
    if historial:
        lp = historial[-1]
        msg = f"**{lp['Equipo Ganador']}** empató contra **{lp['Equipo Perdedor']}**" if lp['Resultado'] == "Empate" else f"**{lp['Equipo Ganador']}** ganó a **{lp['Equipo Perdedor']}**"
        st.info(f"⏪ **Último partido (Nº {len(historial)}):** {msg}")
    if not portador and not historial: st.info("No hay campeón actual. Se registrará el primer partido.")
    else: st.info(f"El campeón actual es: **{portador}** 👑")
    with st.form(key="partido_form"):
        tipo_resultado = st.radio("Resultado:", ("Victoria / Derrota", "Empate"))
        if tipo_resultado == "Victoria / Derrota":
            ganador, perdedor = st.text_input("Ganador"), st.text_input("Perdedor")
        else:
            ganador, perdedor = st.text_input("Equipo A"), st.text_input("Equipo B")
        submit = st.form_submit_button("Registrar Partido")
    if submit:
        equipos = [ganador, perdedor]
        if not all(equipos) or equipos[0].lower() == equipos[1].lower(): st.error("Introduce dos nombres de equipo válidos y diferentes."); return
        if portador and portador.lower() not in [e.lower() for e in equipos]: st.error(f"El campeón ({portador}) debe jugar."); return
        resultado_final = "Victoria"
        if tipo_resultado == "Empate":
            aspirante = equipos[1] if equipos[0].lower() == portador.lower() else equipos[0]
            ganador, perdedor, resultado_final = portador, aspirante, "Empate"
            st.warning(f"Empate: {portador} retiene el título y suma 1 punto.")
        guardar_evento_historial("HistorialPartidos", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ganador, resultado_final, perdedor])
        recargar_y_recalcular_todo(); guardar_datos_completos()
        st.success("¡Partido registrado!"); st.rerun()

def pagina_mostrar_clasificacion():
    st.header("📊 Clasificación General de Equipos")
    clasif = st.session_state.get('clasificacion', {})
    if not clasif: st.info("Aún no hay datos."); return
    df = pd.DataFrame.from_dict(clasif, orient='index').sort_values(by="P", ascending=False).reset_index().rename(columns={'index': 'Equipo'})
    df.insert(0, 'Pos.', range(1, len(df) + 1))
    df['Equipo'] = df.apply(lambda row: f"{row['Equipo']} 👑" if row.get('Portador') else row['Equipo'], axis=1)
    df['PPM'] = df['PPM'].map('{:,.2f}'.format)
    df['Indice Destronamiento'] = df['Indice Destronamiento'].map('{:,.2f}%'.format)
    df_display = df.rename(columns={"T": "PJ", "PPM": "PPP", "Indice Destronamiento": "Índice Éxito"})
    st.dataframe(df_display, hide_index=True)

def pagina_historial_partidos():
    st.header("📜 Historial de Partidos")
    historial = st.session_state.get('historial', [])
    if not historial: st.info("No hay partidos registrados."); return
    st.dataframe(pd.DataFrame(historial).iloc[::-1])

def pagina_eliminar_partido():
    st.header("❌ Eliminar un Partido")
    historial = st.session_state.get('historial', [])
    if not historial: st.info("No hay partidos para eliminar."); return
    opciones = [f"Nº{i+1} ({p['Fecha']}): {p['Equipo Ganador']} vs {p['Equipo Perdedor']}" for i, p in enumerate(historial)]
    seleccion = st.selectbox("Selecciona el partido a eliminar:", options=opciones, index=None)
    if seleccion and st.button("Eliminar Partido Seleccionado"):
        indice = opciones.index(seleccion)
        nuevo_historial = [p for i, p in enumerate(historial) if i != indice]
        reescribir_historial_completo("HistorialPartidos", nuevo_historial, ["Fecha", "Equipo Ganador", "Resultado", "Equipo Perdedor"])
        recargar_y_recalcular_todo(); guardar_datos_completos()
        st.success("¡Partido eliminado!"); st.rerun()

def pagina_añadir_gol():
    st.header("➕ Añadir Gol")
    with st.form(key="gol_form"):
        goleador = st.text_input("Goleador*")
        asistente = st.text_input("Asistente (opcional)")
        submit = st.form_submit_button("Registrar Gol")
    if submit:
        if not goleador: st.error("El nombre del goleador es obligatorio."); return
        guardar_evento_historial("HistorialGoles", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), goleador, asistente or ""])
        recargar_y_recalcular_todo(); guardar_datos_completos()
        st.success("¡Gol registrado!"); st.rerun()

def pagina_clasificacion_individual():
    st.header("🏆 Clasificación de Goleadores")
    clasif = st.session_state.get('clasificacion_individual', {})
    if not clasif: st.info("Aún no hay estadísticas individuales."); return
    df = pd.DataFrame.from_dict(clasif, orient='index').sort_values(by="G/A", ascending=False)
    st.dataframe(df)

def pagina_historial_goles():
    st.header("📋 Historial de Goles")
    historial = st.session_state.get('historial_goles', [])
    if not historial: st.info("No hay goles registrados."); return
    st.dataframe(pd.DataFrame(historial).iloc[::-1])

def pagina_eliminar_gol():
    st.header("❌ Eliminar un Gol")
    historial = st.session_state.get('historial_goles', [])
    if not historial: st.info("No hay goles para eliminar."); return
    opciones = [f"{p['Fecha']}: Gol de {p['Goleador']}" + (f" (Asis. de {p['Asistente']})" if p.get('Asistente') else "") for p in historial]
    seleccion = st.selectbox("Selecciona el gol a eliminar:", options=opciones, index=None)
    if seleccion and st.button("Eliminar Gol Seleccionado"):
        indice = opciones.index(seleccion)
        nuevo_historial = [p for i, p in enumerate(historial) if i != indice]
        reescribir_historial_completo("HistorialGoles", nuevo_historial, ["Fecha", "Goleador", "Asistente"])
        recargar_y_recalcular_todo(); guardar_datos_completos()
        st.success("¡Gol eliminado!"); st.rerun()

def pagina_añadir_porteria_cero():
    st.header("🧤 Añadir Portería a 0")
    with st.form(key="portero_form"):
        portero = st.text_input("Nombre del Portero*")
        submit = st.form_submit_button("Registrar Portería a 0")
    if submit:
        if not portero: st.error("El nombre del portero es obligatorio."); return
        guardar_evento_historial("HistorialPorteriasCero", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), portero])
        recargar_y_recalcular_todo(); guardar_datos_completos()
        st.success("¡Portería a 0 registrada!"); st.rerun()

def pagina_clasificacion_porteros():
    st.header("🥅 Clasificación de Porterías a 0")
    clasif = st.session_state.get('clasificacion_porteros', {})
    if not clasif: st.info("Aún no hay porterías a 0 registradas."); return
    df = pd.DataFrame.from_dict(clasif, orient='index').sort_values(by="Porterías a 0", ascending=False)
    st.dataframe(df)

def pagina_historial_porterias_cero():
    st.header("📋 Historial de Porterías a 0")
    historial = st.session_state.get('historial_porterias', [])
    if not historial: st.info("No hay registros."); return
    st.dataframe(pd.DataFrame(historial).iloc[::-1])

def pagina_eliminar_porteria_cero():
    st.header("❌ Eliminar Portería a 0")
    historial = st.session_state.get('historial_porterias', [])
    if not historial: st.info("No hay registros para eliminar."); return
    opciones = [f"{p['Fecha']}: {p['Portero']}" for p in historial]
    seleccion = st.selectbox("Selecciona el registro a eliminar:", options=opciones, index=None)
    if seleccion and st.button("Eliminar Registro Seleccionado"):
        indice = opciones.index(seleccion)
        nuevo_historial = [p for i, p in enumerate(historial) if i != indice]
        reescribir_historial_completo("HistorialPorteriasCero", nuevo_historial, ["Fecha", "Portero"])
        recargar_y_recalcular_todo(); guardar_datos_completos()
        st.success("¡Registro eliminado!"); st.rerun()

def pagina_borrar_datos():
    st.header("🗑️ Borrar Todo")
    st.warning("⚠️ ¡Atención! Esto borrará TODOS los datos de equipos, goles y porteros.")
    confirmacion = st.text_input("Para confirmar, escribe 'BORRAR TODO' en mayúsculas:")
    if st.button("Borrar toda la información"):
        if confirmacion == "BORRAR TODO":
            sheets_a_limpiar = {
                "Hoja1": ["Equipo", "PJ", "V", "E", "D", "P", "PPP", "Partidos con Trofeo", "Mejor Racha", "Intentos", "Destronamientos", "Indice Destronamiento"],
                "HistorialPartidos": ["Fecha", "Equipo Ganador", "Resultado", "Equipo Perdedor"],
                "ClasificacionGoleadores": ["Jugador", "Goles", "Asistencias", "G/A"],
                "HistorialGoles": ["Fecha", "Goleador", "Asistente"],
                "ClasificacionPorteros": ["Portero", "Porterías a 0"],
                "HistorialPorteriasCero": ["Fecha", "Portero"]
            }
            for nombre_hoja, encabezados in sheets_a_limpiar.items():
                sh = conectar_a_gsheets(nombre_hoja)
                if sh: sh.clear(); sh.update([encabezados], 'A1')
            st.session_state.clear()
            st.success("¡Todos los datos han sido borrados!"); st.rerun()
        else: st.error("Confirmación incorrecta.")

# --- MENÚ PRINCIPAL Y ROUTER ---
st.set_page_config(page_title="ToNOI", page_icon="👑", layout="wide")
st.title("👑 Torneo No Oficial de Inglaterra (ToNOI)")

if 'active_page' not in st.session_state:
    st.session_state.active_page = "Añadir Partido"

with st.sidebar:
    st.header("Torneo de Equipos")
    if st.button("Añadir Partido"): st.session_state.active_page = "Añadir Partido"
    if st.button("Clasificación General"): st.session_state.active_page = "Clasificación General"
    if st.button("Historial de Partidos"): st.session_state.active_page = "Historial de Partidos"
    if st.button("Eliminar Partido"): st.session_state.active_page = "Eliminar Partido"
    
    st.markdown("---")
    st.header("Estadísticas Individuales")
    with st.expander("Goles / Asistencias"):
        if st.button("Añadir Gol"): st.session_state.active_page = "Añadir Gol"
        if st.button("Clasificación G/A"): st.session_state.active_page = "Clasificación G/A"
        if st.button("Historial de Goles"): st.session_state.active_page = "Historial de Goles"
        if st.button("Eliminar Gol"): st.session_state.active_page = "Eliminar Gol"
    
    with st.expander("Porterías a 0"):
        if st.button("Añadir Portería a 0"): st.session_state.active_page = "Añadir Portería a 0"
        if st.button("Clasificación Porteros"): st.session_state.active_page = "Clasificación Porteros"
        if st.button("Historial de Porterías a 0"): st.session_state.active_page = "Historial Porterías a 0"
        if st.button("Eliminar Portería a 0"): st.session_state.active_page = "Eliminar Portería a 0"

    st.markdown("---")
    st.header("Administración")
    if st.button("🗑️ Borrar Todos los Datos"): st.session_state.active_page = "Borrar Todo"

# Ejecuta la página que está activa en la sesión
page_map = {
    "Añadir Partido": pagina_añadir_partido,
    "Clasificación General": pagina_mostrar_clasificacion,
    "Historial de Partidos": pagina_historial_partidos,
    "Eliminar Partido": pagina_eliminar_partido,
    "Añadir Gol": pagina_añadir_gol,
    "Clasificación G/A": pagina_clasificacion_individual,
    "Historial de Goles": pagina_historial_goles,
    "Eliminar Gol": pagina_eliminar_gol,
    "Añadir Portería a 0": pagina_añadir_porteria_cero,
    "Clasificación Porteros": pagina_clasificacion_porteros,
    "Historial de Porterías a 0": pagina_historial_porterias_cero,
    "Eliminar Portería a 0": pagina_eliminar_porteria_cero,
    "Borrar Todo": pagina_borrar_datos,
}
page_map[st.session_state.active_page]()