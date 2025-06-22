import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# Crear carpeta de salida si no existe
os.makedirs('../resultados', exist_ok=True)

# Archivos CSV y etiquetas
archivos = {
    'Estático': './tripinfo_static.csv',
    'Lógica Difusa': './tripinfo_fuzzy.csv',
    'Actuated (SUMO)': './tripinfo_actuated.csv'
}

# Métricas a graficar
metricas = [
    "tripinfo_arrivalSpeed",
    "tripinfo_duration",
    "tripinfo_routeLength",
    "tripinfo_timeLoss",
    "tripinfo_waitingTime"
]

# Leer datos
datos = {}
for etiqueta, archivo in archivos.items():
    datos[etiqueta] = pd.read_csv(archivo)

# Función para calcular media e intervalo de confianza
def calcular_estadisticas(columna):
    medias = []
    errores = []
    for etiqueta in archivos:
        serie = datos[etiqueta][columna].dropna()
        media = np.mean(serie)
        sem = stats.sem(serie)  # error estándar de la media
        intervalo = stats.t.interval(0.95, len(serie)-1, loc=media, scale=sem)
        error = media - intervalo[0]
        medias.append(media)
        errores.append(error)
    return medias, errores

# Graficar
for metrica in metricas:
    medias, errores = calcular_estadisticas(metrica)
    
    fig, ax = plt.subplots()
    etiquetas = list(archivos.keys())
    x = np.arange(len(etiquetas))
    ax.bar(x, medias, yerr=errores, capsize=10, color=['skyblue', 'salmon', 'lightgreen'])
    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas)
    ax.set_ylabel(metrica)
    ax.set_title(f'{metrica} con Intervalos de Confianza al 95%')
    ax.grid(True, linestyle='--', alpha=0.6)

    # Guardar gráfica
    ruta = f'./results/{metrica}.png'
    plt.tight_layout()
    plt.savefig(ruta)
    plt.close()

print("✅ Gráficas guardadas en ../resultados")
