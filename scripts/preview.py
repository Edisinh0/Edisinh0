"""Renderiza un bloque de texto ASCII a PNG para poder revisarlo a ojo."""
import argparse

from PIL import Image, ImageDraw, ImageFont

FUENTE = "/System/Library/Fonts/Menlo.ttc"


def render(texto, salida, tam=14, fondo="#0d1117", tinta="#e6edf3"):
    fuente = ImageFont.truetype(FUENTE, tam)
    ancho_car = fuente.getlength("M")
    alto_lin = tam * 1.18
    lineas = texto.split("\n")
    w = int(ancho_car * max(len(l) for l in lineas)) + 24
    h = int(alto_lin * len(lineas)) + 24
    img = Image.new("RGB", (w, h), fondo)
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lineas):
        d.text((12, 12 + i * alto_lin), l, font=fuente, fill=tinta)
    img.save(salida)
    return w, h


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("entrada")
    p.add_argument("salida")
    p.add_argument("--tam", type=int, default=14)
    a = p.parse_args()
    print(render(open(a.entrada).read().rstrip("\n"), a.salida, a.tam))
