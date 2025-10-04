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
                'Mejor Racha': 0, 'Destronamientos': 0, 'Intentos': 0, 'Indice Destronamiento': 0.0
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
    
    if portador_trofeo and portador_trofeo in clasificacion:
        clasificacion[portador_trofeo]['Portador'] = True

    return clasificacion

# --- GESTIÓN DE DATOS ---
def recargar_y_recalcular_todo():
    """Función central que lee el historial y calcula todo."""
    historial = conectar_a_gsheets("HistorialPartidos").get_all_records() if conectar_a_gsheets("HistorialPartidos") else []
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
    """Guarda la clasificación con todas las estadísticas en la Hoja1."""
    sh_clasif = conectar_a_gsheets("Hoja1")
    if sh_clasif:
        clasif_para_guardar = st.session_state.get('clasificacion', {})
        encabezados = [
            "Equipo", "V", "E", "D", "T", "P", "PPM",
            "Mejor Racha", "Destronamientos", "Intentos", "Indice Destronamiento"
        ]
        datos = [encabezados]
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

# --- NUEVA FUNCIÓN ---
def reescribir_historial_completo(nuevo_historial):
    """Borra la hoja de historial y la reescribe con nuevos datos."""
    sh_historial = conectar_a_gsheets("HistorialPartidos")
    if sh_historial:
        encabezados = ["Fecha", "Equipo Ganador", "Resultado", "Equipo Perdedor"]
        datos = [encabezados]
        for partido in nuevo_historial:
            datos.append([partido['Fecha'], partido['Equipo Ganador'], partido['Resultado'], partido['Equipo Perdedor']])
        sh_historial.clear()
        sh_historial.update(datos, 'A1')

# --- CAR