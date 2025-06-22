import pandas as pd
import matplotlib.pyplot as plt

# === CONFIGURACIÓN GENERAL ===
semaforo_objetivo = "2496228891"
minuto_inicio = 150
minuto_fin = 152
duracion_verde_static = 42
duracion_amarillo = 3
segundos_por_minuto = 60

# Diccionario de entradas: leyenda -> (archivo, columna_duracion, columna_fase)
fuentes = {
    "Actuated": ("./datos_semaforos_actuated.csv", "duracion", "fase"),
    "Fuzzy": ("./datos_semaforos_fuzzy.csv", "duracion_verde", "fase")
}

# === FUNCIONES ===
def extraer_fases_csv(path, semaforo_id, col_duracion, col_fase, t_col="tiempo"):
    df = pd.read_csv(path, dtype={'semaforo_id': str})
    df = df[df['semaforo_id'] == semaforo_id].copy()
    df = df.sort_values(by=t_col)
    df['tiempo_inicio'] = df[t_col]
    df['tiempo_fin'] = df['tiempo_inicio'] + df[col_duracion]
    df['fase_amarilla'] = df[col_fase].apply(lambda f: 1 if f == 0 else 3)
    df['minuto'] = (df['tiempo_inicio'] // 60).astype(int)
    df = df[(df['tiempo_inicio'] >= minuto_inicio * 60) & (df['tiempo_inicio'] < minuto_fin * 60)]
    df = df.reset_index(drop=True)
    return df

def construir_onda_fases(df, minuto_inicio, minuto_fin, col_duracion, col_fase):
    duracion_total = (minuto_fin - minuto_inicio) * segundos_por_minuto
    onda = [-1] * duracion_total  # Inicializa con -1

    for _, fila in df.iterrows():
        t_inicio = int(fila['tiempo_inicio']) - minuto_inicio * segundos_por_minuto
        t_verde = int(fila[col_duracion])
        t_amarillo = duracion_amarillo
        fase = int(fila[col_fase])
        fase_amarilla = fila['fase_amarilla']

        # Fase verde
        for t in range(max(0, t_inicio), min(t_inicio + t_verde, duracion_total)):
            onda[t] = fase

        # Fase amarilla
        for t in range(t_inicio + t_verde, min(t_inicio + t_verde + t_amarillo, duracion_total)):
            onda[t] = fase_amarilla

    # 🔁 Rellenar huecos con la siguiente fase válida
    for i in reversed(range(duracion_total)):
        if onda[i] == -1:
            j = i + 1
            while j < duracion_total and onda[j] == -1:
                j += 1
            if j < duracion_total:
                onda[i] = onda[j]  # Asignar la siguiente fase conocida

    return onda



def construir_onda_estatica(duracion_verde, duracion_amarillo, minuto_inicio, minuto_fin):
    duracion_total = (minuto_fin - minuto_inicio) * segundos_por_minuto
    onda = []
    t = 0
    fase = 0
    while t < duracion_total:
        for _ in range(duracion_verde):
            if t >= duracion_total: break
            onda.append(fase)
            t += 1
        for _ in range(duracion_amarillo):
            if t >= duracion_total: break
            onda.append(1 if fase == 0 else 3)
            t += 1
        fase = 2 if fase == 0 else 0
    return onda

# === CONSTRUCCIÓN DE ONDAS ===
ondas = {}

# Static
ondas["Static"] = construir_onda_estatica(duracion_verde_static, duracion_amarillo, minuto_inicio, minuto_fin)

# Actuated y Fuzzy
for nombre, (archivo, col_duracion, col_fase) in fuentes.items():
    df = extraer_fases_csv(archivo, semaforo_objetivo, col_duracion, col_fase)
    onda = construir_onda_fases(df, minuto_inicio, minuto_fin, col_duracion, col_fase)
    ondas[nombre] = onda

# === GRAFICADO ===
plt.figure(figsize=(14, 5))
x = range((minuto_fin - minuto_inicio) * segundos_por_minuto)

# Para evitar superposición de curvas
desplazamientos = {"Static": 0, "Actuated": 5, "Fuzzy": 10}
for nombre, onda in ondas.items():
    shift = desplazamientos[nombre]
    onda_shifted = [f + shift if f >= 0 else None for f in onda]
    estilo = '--' if nombre == "Static" else 'solid'
    plt.step(x, onda_shifted, where='post', label=nombre, linewidth=2, linestyle=estilo)

# Ejes y etiquetas
yticks = []
yticklabels = []
for base in [0, 5, 10]:
    yticks += [base, base + 1, base + 2, base + 3]
    yticklabels += [f"Fase 0", "Fase 1", "Fase 2", "Fase 3"]

plt.yticks(yticks, yticklabels)
plt.ylim(-1, max(yticks) + 1)
plt.xlabel(f"Tiempo (segundos desde el minuto {minuto_inicio})")
plt.ylabel("Fase activa")
plt.title(f"Comparación de Secuencias de Fases - Semáforo {semaforo_objetivo}")
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()
plt.tight_layout()

# Guardar imagen ANTES de mostrarla
plt.savefig("./results/phases.png", dpi=300)
plt.show()

