import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta

# === CONFIGURACIÓN ===
archivos = {
    "Static": "./tripinfo_static.csv",
    "Actuated": "./tripinfo_actuated.csv",
    "Fuzzy": "./tripinfo_fuzzy.csv"
}

intervalo_segundos = 60*5  # 10 minutos
inicio_dia = datetime(2025, 1, 1, 0, 0, 0)
ventana_suavizado = 4     # Tamaño de la ventana de suavizado (en n° de intervalos)

# Crear carpeta si no existe
os.makedirs("./results", exist_ok=True)

densidades = {}

for etiqueta, archivo in archivos.items():
    try:
        df = pd.read_csv(archivo, sep=None, engine="python")
        print(f"✅ Leyendo {archivo}... columnas: {list(df.columns)}")

        if "tripinfo_depart" not in df.columns:
            raise KeyError("Falta la columna 'tripinfo_depart'")

        # Agrupar por intervalos
        df["time_bin"] = (df["tripinfo_depart"] // intervalo_segundos).astype(int)
        conteo = df.groupby("time_bin").size()

        # Rellenar todos los intervalos posibles
        all_bins = range(0, df["time_bin"].max() + 1)
        conteo = conteo.reindex(all_bins, fill_value=0)

        # Aplicar suavizado (media móvil)
        conteo_suavizado = conteo.rolling(window=ventana_suavizado, center=True, min_periods=1).mean()

        # Convertir a datetime real
        conteo_suavizado.index = [inicio_dia + timedelta(seconds=i * intervalo_segundos) for i in conteo.index]
        densidades[etiqueta] = conteo_suavizado

    except Exception as e:
        print(f"⚠️ Error leyendo {archivo}: {e}")

# === GRAFICADO ===
plt.figure(figsize=(14, 6))

for etiqueta, serie in densidades.items():
    plt.plot(serie.index, serie.values, label=etiqueta, linewidth=2)

plt.title("Densidad de Vehículos vs Hora del Día", fontsize=14)
plt.xlabel("Hora del día", fontsize=12)
plt.ylabel("Vehículos por intervalo (suavizado)", fontsize=12)
plt.legend(title="Tipo de Control", fontsize=10)
plt.grid(True, linestyle="--", alpha=0.6)
plt.xticks(rotation=45)
plt.tight_layout()

# Guardar y mostrar
plt.savefig("./results/vehiculos_vs_tiempo.png", dpi=300)
plt.show()
