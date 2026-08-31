"""Convierte un retrato en arte ASCII para el panel del perfil.

El fondo se recorta con un flood fill desde los bordes: solo se descarta lo
que este conectado al borde y tenga el color del fondo, asi la polera oscura
no se confunde con el fondo aunque tengan un tono parecido. Dentro del sujeto
se normaliza el contraste y se mapea el brillo a una rampa de caracteres, de
modo que lo oscuro (pelo, polera) quede denso y lo claro (piel) liviano.
"""
import argparse
from collections import deque

from PIL import Image, ImageOps, ImageFilter

# Rampas de mas denso a mas liviano. Las cortas se leen mucho mejor que la
# clasica de 70 caracteres: en una fuente real esos simbolos no forman una
# gradiente de densidad, forman ruido. El fondo va siempre con espacios.
RAMPAS = {
    "bourke": "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. ",
    "bloques": "@%#*+=-:. ",
    "densa": "@@%%##**++==--::.. ",
    "suave": "@#%*o+=~-:,. ",
    "mixta": "@#8&WM*ohbdpqwmZO0QJXzcvunxrjft|()1{}[]?-_+~<>i!lI;:,^`'. ",
}
RAMP = RAMPAS["bloques"]

TRABAJO = 480  # ancho al que se reduce la foto antes del flood fill


def mascara_sujeto(img, tolerancia):
    """255 = sujeto, 0 = fondo. Flood fill BFS desde todos los bordes."""
    w, h = img.size
    px = img.load()
    fondo = bytearray(w * h)
    visto = bytearray(w * h)
    cola = deque()

    def semilla(x, y):
        i = y * w + x
        if not visto[i]:
            visto[i] = 1
            cola.append((x, y))

    for x in range(w):
        semilla(x, 0)
        semilla(x, h - 1)
    for y in range(h):
        semilla(0, y)
        semilla(w - 1, y)

    # Color de referencia: el promedio de las semillas del borde superior.
    muestras = [px[x, 0][:3] for x in range(0, w, max(1, w // 40))]
    br = sum(c[0] for c in muestras) // len(muestras)
    bg = sum(c[1] for c in muestras) // len(muestras)
    bb = sum(c[2] for c in muestras) // len(muestras)

    while cola:
        x, y = cola.popleft()
        r, g, b = px[x, y][:3]
        if abs(r - br) + abs(g - bg) + abs(b - bb) > tolerancia:
            continue
        fondo[y * w + x] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                i = ny * w + nx
                if not visto[i]:
                    visto[i] = 1
                    cola.append((nx, ny))

    m = Image.new("L", (w, h))
    m.putdata([0 if f else 255 for f in fondo])
    return m.filter(ImageFilter.MedianFilter(3))


def generar(ruta, cols, aspecto, tolerancia, gamma, recorte, invertir,
            local=0, nitidez=0, rampa="bloques"):
    img = Image.open(ruta).convert("RGB")
    if recorte:
        img = img.crop(recorte)
    img = img.resize((TRABAJO, round(TRABAJO * img.height / img.width)), Image.LANCZOS)

    mascara = mascara_sujeto(img, tolerancia)
    filas = max(1, round(cols * img.height / img.width * aspecto))

    gris = ImageOps.grayscale(img)
    if nitidez:
        # Radio grande + porcentaje alto = "claridad": sube el contraste local
        # (ojos, nariz, boca) sin aplanar el tono general de la foto.
        gris = gris.filter(
            ImageFilter.UnsharpMask(radius=local or 8, percent=nitidez, threshold=0)
        )
    gris = ImageOps.autocontrast(gris, cutoff=1, mask=mascara)
    if invertir:
        gris = ImageOps.invert(gris)

    gris = gris.resize((cols, filas), Image.LANCZOS)
    mascara = mascara.resize((cols, filas), Image.LANCZOS)
    gp, mp = gris.load(), mascara.load()

    lineas = []
    for y in range(filas):
        fila = []
        for x in range(cols):
            if mp[x, y] < 110:
                fila.append(" ")
                continue
            v = (gp[x, y] / 255) ** gamma
            r = RAMPAS[rampa]
            fila.append(r[min(len(r) - 2, int(v * (len(r) - 1)))])
        lineas.append("".join(fila).rstrip())
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    while lineas and not lineas[-1].strip():
        lineas.pop()
    return lineas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("imagen")
    p.add_argument("--cols", type=int, default=42)
    p.add_argument("--aspecto", type=float, default=0.48, help="alto/ancho del caracter")
    p.add_argument("--tolerancia", type=int, default=45)
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--recorte", help="x0,y0,x1,y1 sobre la foto original")
    p.add_argument("--invertir", action="store_true")
    p.add_argument("--local", type=float, default=0, help="radio del realce local")
    p.add_argument("--nitidez", type=int, default=0, help="porcentaje de unsharp mask")
    p.add_argument("--rampa", default="bloques", choices=sorted(RAMPAS))
    p.add_argument("--salida")
    a = p.parse_args()

    recorte = tuple(int(v) for v in a.recorte.split(",")) if a.recorte else None
    lineas = generar(a.imagen, a.cols, a.aspecto, a.tolerancia, a.gamma, recorte,
                     a.invertir, a.local, a.nitidez, a.rampa)
    texto = "\n".join(lineas)
    if a.salida:
        with open(a.salida, "w") as f:
            f.write(texto + "\n")
    print(texto)


if __name__ == "__main__":
    main()
