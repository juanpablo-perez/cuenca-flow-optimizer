sumo_cfg = "./sumo_files/osm_fuzzy.sumocfg"

semaforos_ids = ["2496228891", 
                     "cluster_12013799525_12013799526_2496228894", 
                     "cluster_12013799527_12013799528_2190601967",
                     "cluster_12013799529_12013799530_473195061"]

"""
fases_lanes_dict = {
        "2496228891": {
            0: ["337277951#3_0", "337277951#3_1", "337277951#1_0"], 
            2: ["567060342#1_0", "567060342#0_0"], 
        },
        "cluster_12013799525_12013799526_2496228894": {
            0: ["42143912#5_0", "42143912#3_0"],
            2: ["337277973#1_0", "337277973#1_1"]
        },
        "cluster_12013799527_12013799528_2190601967": {
            0: ["40668087#1_0"],
            2: ["337277981#1_1", "337277981#1_0", "337277981#2_1", "337277981#2_0"]
        },
        "cluster_12013799529_12013799530_473195061": {
            0: ["49217102_0"],
            2: ["337277970#1_0", "337277970#1_1"]
        }
    }
"""
fases_lanes_dict = {
        "2496228891": {
            0: ["337277951#3_0", "337277951#3_1", "337277951#1_0", "337277951#1_0", "337277951#4_0", "337277951#4_1", "337277951#2_0", "337277951#2_1", "49217102_0"], 
            2: ["567060342#1_0", "567060342#0_0"], 
        },
        "cluster_12013799525_12013799526_2496228894": {
            0: ["42143912#5_0", "42143912#3_0", "42143912#4_0"],
            2: ["337277973#1_0", "337277973#1_1", "337277973#0_1", "337277973#0_0", "567060342#1_0", "567060342#0_0"]
        },
        "cluster_12013799527_12013799528_2190601967": {
            0: ["40668087#1_0"],
            2: ["337277981#1_1", "337277981#1_0", "337277981#2_1", "337277981#2_0", "42143912#5_0", "42143912#3_0", "42143912#4_0"]
        },
        "cluster_12013799529_12013799530_473195061": {
            0: ["49217102_0"],
            2: ["337277970#1_0", "337277970#1_1", "40668087#1_0"]
        }
    }

funciones = {
    "llegada": {
        "lmin": 0.0,
        "lmax": 1,
        "niveles": ["muy lenta", "lenta", "media", "moderada", "alta"]
    },
    "vehiculos": {
        "lmin": 0,
        "lmax": 30,
        "niveles": ["muy pocos", "pocos", "normal", "moderados", "muchos"]
    },
    "verde": {
        "lmin": 15,
        "lmax": 50,
        "niveles": ["muy corto", "corto", "normal", "alto", "muy alto"]
    }
}

reglas_definidas = [
    #   Vehiculos    Tasa         Verde
    ["muy pocos", "muy lenta", "muy corto"],
    ["muy pocos", "lenta", "muy corto"],
    ["muy pocos", "media", "muy corto"],
    ["muy pocos", "moderada", "muy corto"],
    ["muy pocos", "alta", "corto"],

    ["pocos", "muy lenta", "muy corto"],
    ["pocos", "lenta", "muy corto"],
    ["pocos", "media", "corto"],
    ["pocos", "moderada", "corto"],
    ["pocos", "alta", "corto"],

    ["normal", "muy lenta", "corto"],
    ["normal", "lenta", "corto"],
    ["normal", "media", "normal"],
    ["normal", "moderada", "normal"],
    ["normal", "alta", "normal"],

    ["moderados", "muy lenta", "normal"],
    ["moderados", "lenta", "normal"],
    ["moderados", "media", "normal"],
    ["moderados", "moderada", "normal"],
    ["moderados", "alta", "normal"],

    ["muchos", "muy lenta", "normal"],
    ["muchos", "lenta", "normal"],
    ["muchos", "media", "normal"],
    ["muchos", "moderada", "alto"],
    ["muchos", "alta", "alto"]
]
