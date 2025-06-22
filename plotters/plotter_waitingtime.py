import pandas as pd
import matplotlib.pyplot as plt

# Cargar ambos archivos CSV
fuzzy = pd.read_csv('tripinfo_fuzzy.csv')
baseline = pd.read_csv('tripinfo_normal.csv')  

# Convertir 'tripinfo_arrival' a minutos
fuzzy['minute'] = (fuzzy['tripinfo_arrival'] // 600).astype(int)
baseline['minute'] = (baseline['tripinfo_arrival'] // 600).astype(int)

# Agrupar por minuto y sumar los waitingTime
fuzzy_grouped = fuzzy.groupby('minute')['tripinfo_waitingTime'].mean()
baseline_grouped = baseline.groupby('minute')['tripinfo_waitingTime'].mean()

# Crear la gráfica
plt.figure(figsize=(10, 6))
plt.plot(fuzzy_grouped.index, fuzzy_grouped.values, label='Lógica Difusa', marker='o')
plt.plot(baseline_grouped.index, baseline_grouped.values, label='Control Base', marker='x')

plt.xlabel('Tiempo (minutos)')
plt.ylabel('Tiempo total de espera (s)')
plt.title('Comparación de Waiting Time por minuto')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
