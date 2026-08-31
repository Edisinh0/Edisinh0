"""Arma el panel SVG del perfil: retrato ASCII a la izquierda y ficha
estilo neofetch a la derecha.

El SVG se incrusta en el README con <picture>, asi que GitHub lo renderiza
en sandbox: no hay scripts ni fuentes remotas. Para que la grilla monoespaciada
calce igual en cualquier sistema se declara una @font-face que toma la Consolas
local y la normaliza con size-adjust, la misma tecnica del perfil de referencia.
"""
import argparse
import json
from datetime import datetime, timezone

FUENTE_PX = 16
ALTO_LINEA = 20
ANCHO_CAR = 9.6  # ancho de un caracter con la fuente normalizada
MARGEN = 15
SEPARACION_CAR = 3  # columnas en blanco entre el retrato y la ficha

TEMAS = {
    "dark": {
        "fondo": "#161b22", "texto": "#c9d1d9", "ascii": "#c9d1d9",
        "clave": "#ffa657", "valor": "#a5d6ff", "suma": "#3fb950",
        "resta": "#f85149", "tenue": "#616e7f", "titulo": "#d2a8ff",
    },
    "light": {
        "fondo": "#ffffff", "texto": "#24292f", "ascii": "#24292f",
        "clave": "#953800", "valor": "#0550ae", "suma": "#1a7f37",
        "resta": "#cf222e", "tenue": "#6e7781", "titulo": "#8250df",
    },
}


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def miles(n):
    return f"{n:,}".replace(",", ".")


class Ficha:
    """Acumula las lineas de la ficha como fragmentos (texto, clase)."""

    def __init__(self, ancho):
        self.ancho = ancho
        self.lineas = []

    def cruda(self, partes):
        self.lineas.append(partes)

    def vacia(self):
        self.lineas.append([])

    def titulo(self, texto):
        relleno = "-" * max(3, self.ancho - len(texto) - 3)
        self.cruda([(f"- {texto} {relleno}", "cc")])

    def cabecera(self, texto):
        relleno = "-" * max(3, self.ancho - len(texto) - 1)
        self.cruda([(texto, "key"), (" " + relleno, "cc")])

    def fila(self, clave, valor, clase="value"):
        """clave: ..... valor, con los puntos rellenando hasta alinear."""
        izq = f".  {clave}: "
        puntos = max(1, self.ancho - len(izq) - len(valor) - 1)
        self.cruda([(izq, "key"), ("." * puntos + " ", "cc"), (valor, clase)])

    def multi(self, clave, partes):
        """Igual que fila pero con el valor partido en tramos de color."""
        izq = f".  {clave}: "
        largo = sum(len(t) for t, _ in partes)
        puntos = max(1, self.ancho - len(izq) - largo - 1)
        self.cruda([(izq, "key"), ("." * puntos + " ", "cc"), *partes])


def antiguedad(desde, hasta):
    anios = hasta.year - desde.year
    meses = hasta.month - desde.month
    dias = hasta.day - desde.day
    if dias < 0:
        meses -= 1
    if meses < 0:
        anios -= 1
        meses += 12
    return f"{anios} años, {meses} meses"


def construir_ficha(perfil, stats, ancho):
    f = Ficha(ancho)
    ahora = datetime.fromisoformat(stats["generated_at"])
    f.cabecera(perfil["titulo"])

    for clave, valor in perfil["sistema"]:
        if clave == "Uptime":
            if not perfil.get("nacimiento"):
                continue
            nac = datetime.fromisoformat(perfil["nacimiento"]).replace(tzinfo=timezone.utc)
            valor = antiguedad(nac, ahora)
        if valor:
            f.fila(clave, valor)
    f.vacia()

    top = [l["name"] for l in stats["languages"]][:6]
    f.fila("Lenguajes.Programación", ", ".join(top[:4]))
    if top[4:]:
        f.fila("Lenguajes.Otros", ", ".join(top[4:]))
    f.fila("Lenguajes.Reales", perfil["idiomas_reales"])
    for clave, valor in perfil.get("hobbies", []):
        if valor:
            f.fila(clave, valor)
    f.vacia()

    f.titulo("Contacto")
    for clave, valor in perfil["contacto"]:
        if valor:
            f.fila(clave, valor)
    f.vacia()

    f.titulo("Estadísticas de GitHub")
    f.multi("Repos", [
        (str(stats["repos_total"]), "value"), (" {Contribuidos: ", "cc"),
        (str(stats["contributed"]), "value"), ("}", "cc"),
        ("  |  Stars: ", "cc"), (str(stats["stars"]), "value"),
    ])
    f.fila("Commits", miles(stats["commits"]))
    f.fila("Seguidores", str(stats["followers"]))
    f.multi("Líneas de código", [
        (miles(stats["lines_total"]), "value"), (" ( ", "cc"),
        (miles(stats["lines_added"]) + "++", "add"), (", ", "cc"),
        (miles(stats["lines_deleted"]) + "--", "del"), (" )", "cc"),
    ])
    return f.lineas


def render(ascii_txt, perfil, stats, tema):
    c = TEMAS[tema]
    arte = ascii_txt.rstrip("\n").split("\n")
    cols_arte = max(len(l) for l in arte)

    ancho_ficha = 62
    ficha = construir_ficha(perfil, stats, ancho_ficha)
    cols_ficha = max(sum(len(t) for t, _ in l) for l in ficha if l)

    cols = cols_arte + SEPARACION_CAR + cols_ficha
    filas = max(len(arte), len(ficha))
    ancho = round(cols * ANCHO_CAR + MARGEN * 2)
    alto = round(filas * ALTO_LINEA + MARGEN * 2 + 6)
    largo_linea = cols * ANCHO_CAR

    out = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'font-family="ConsolasNormalizada,Consolas,\'DejaVu Sans Mono\',monospace" '
        f'width="{ancho}px" height="{alto}px" font-size="{FUENTE_PX}px">',
        "<style>",
        "@font-face {",
        "  src: local('Consolas');",
        "  font-family: 'ConsolasNormalizada';",
        "  font-display: swap;",
        "  size-adjust: 109%;",
        "}",
        f".key {{fill: {c['clave']};}}",
        f".value {{fill: {c['valor']};}}",
        f".add {{fill: {c['suma']};}}",
        f".del {{fill: {c['resta']};}}",
        f".cc {{fill: {c['tenue']};}}",
        "text, tspan {white-space: pre;}",
        "</style>",
        f'<rect width="{ancho}px" height="{alto}px" fill="{c["fondo"]}" rx="15"/>',
        f'<text x="{MARGEN}" y="{MARGEN + FUENTE_PX}" fill="{c["texto"]}">',
    ]

    # Cada fila combina retrato y ficha en una sola linea: asi la grilla la
    # sostienen los propios caracteres y no las coordenadas, que dependerian
    # de la fuente que tenga quien mira. textLength fija ademas el ancho total,
    # de modo que el panel se ve igual con cualquier monoespaciada de respaldo.
    y = MARGEN + FUENTE_PX
    for i in range(filas):
        izq = arte[i] if i < len(arte) else ""
        partes = [(izq.ljust(cols_arte + SEPARACION_CAR), "ascii")]
        if i < len(ficha) and ficha[i]:
            partes += ficha[i]
        usado = sum(len(t) for t, _ in partes)
        partes.append((" " * max(0, cols - usado), "cc"))
        trozos = "".join(
            f'<tspan class="{cl}">{esc(t)}</tspan>' if cl != "ascii" else esc(t)
            for t, cl in partes
        )
        out.append(
            f'<tspan x="{MARGEN}" y="{y + i * ALTO_LINEA}" '
            f'textLength="{largo_linea:.1f}" lengthAdjust="spacing">{trozos}</tspan>'
        )
    out += ["</text>", "</svg>"]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ascii", default="assets/retrato.txt")
    p.add_argument("--perfil", default="perfil.json")
    p.add_argument("--stats", default="assets/stats.json")
    a = p.parse_args()

    arte = open(a.ascii).read()
    perfil = json.load(open(a.perfil))
    stats = json.load(open(a.stats))
    for tema in TEMAS:
        with open(f"{tema}_mode.svg", "w") as fh:
            fh.write(render(arte, perfil, stats, tema))
        print(f"{tema}_mode.svg")
