from PIL import Image
import numpy as np
entrada = "assets/characters/eris.png"
salida = "assets/characters/eris_sin_fondo.png"
im = Image.open(entrada).convert("RGBA")
datos = np.array(im).copy()
r = datos[:, :, 0].astype(int)
g = datos[:, :, 1].astype(int)
b = datos[:, :, 2].astype(int)
# Detectar únicamente píxeles claramente azulados.
azul = (b > r * 1.15) & (b > g * 1.05) & (b > 35)
# Solo borrar el azul cercano a los bordes para proteger al personaje.
from collections import deque
alto, ancho = azul.shape
visitado = np.zeros((alto, ancho), dtype=bool)
cola = deque()
for x in range(ancho):
    if azul[0, x]:
        cola.append((0, x))
    if azul[alto - 1, x]:
        cola.append((alto - 1, x))
for y in range(alto):
    if azul[y, 0]:
        cola.append((y, 0))
    if azul[y, ancho - 1]:
        cola.append((y, ancho - 1))
while cola:
    y, x = cola.popleft()
    if visitado[y, x] or not azul[y, x]:
        continue
    visitado[y, x] = True
    datos[y, x, 3] = 0
    for ny, nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
        if 0 <= ny < alto and 0 <= nx < ancho and not visitado[ny, nx]:
            if azul[ny, nx]:
                cola.append((ny, nx))
Image.fromarray(datos).save(salida)
print("Guardado:", salida)
