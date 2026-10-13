"""Indicadores del ranking: clasificación de clubes y regiones, figuras, competitividad, zonas y búsquedas."""
from __future__ import annotations

import datetime as dt
import functools
from dataclasses import dataclass, field

import pandas as pd

from . import ubicaciones
from .datos import GRUPOS, GRUPOS_MENORES, SEXOS, SLUG_SIN_CLUB, sin_tildes

ORDEN_GRUPOS = sorted(GRUPOS.values(), key=lambda g: g[1])  # (etiqueta, orden, slug), de Sub 13 a Absoluta

SIN_RIVALES = "Sin rivales"  # categoría con un solo deportista: no hay a quién sacarle ventaja


def nivel_competencia(ventaja: float) -> str:
    """Qué tan pareja está la pelea por el 1.º lugar (ventaja del 1.º sobre el 2.º)."""
    if ventaja < 0.10:
        return "Muy reñida"
    if ventaja < 0.30:
        return "Disputada"
    return "Dominada"


def _memo(fn):
    """Guarda el resultado por versión de los datos: no cambia hasta la próxima actualización."""
    @functools.wraps(fn)
    def envoltura(self, *args):
        clave = (fn.__name__, args)
        if clave in self._cache:
            return self._cache[clave]
        resultado = fn(self, *args)
        inexistente = resultado is None or (isinstance(resultado, tuple) and resultado[0] is None)
        if not inexistente:  # no guarda direcciones que no existen
            self._cache[clave] = resultado
        return resultado
    return envoltura


# Cuántas categorías encabeza un club o una región (oro), en cuántas va 2.º o 3.º y cuántos deportistas
# tiene entre los 8 primeros. Se usa en las tablas de clubes y de regiones.
MEDALLAS = {
    "oro": ("pos", lambda s: int((s == 1).sum())),
    "plata": ("pos", lambda s: int((s == 2).sum())),
    "bronce": ("pos", lambda s: int((s == 3).sum())),
    "top8": ("pos", lambda s: int((s <= 8).sum())),
}


def _tabla_clubes(df: pd.DataFrame) -> pd.DataFrame:
    """Clubes ordenados por puntos totales: la suma del puntaje de todos sus deportistas."""
    t = (
        df.groupby("club_slug")
        .agg(club_nombre=("club_nombre", "first"), region=("region", "first"), zona=("zona", "first"), **MEDALLAS,
             deportistas=("dep_slug", "nunique"),
             puntos=("total", "sum"),
             mejor_pos=("pos", "min"))
        .reset_index()
    )
    t["podios"] = t.oro + t.plata + t.bronce
    t = t.sort_values(["puntos", "oro", "plata", "bronce"], ascending=False, kind="stable").reset_index(drop=True)
    t["lugar"] = t.index + 1
    return t


def _tabla_regiones(df: pd.DataFrame) -> pd.DataFrame:
    """Regiones ordenadas por puntos totales. Cada deportista cuenta para la región de su club."""
    d = df[df.region != ""]
    t = (
        d.groupby("region")
        .agg(puntos=("total", "sum"), deportistas=("dep_slug", "nunique"), clubes=("club_slug", "nunique"), **MEDALLAS)
        .reset_index()
    )
    intl = d[d.intl > 0].groupby("region").dep_slug.nunique()
    t["intl"] = t.region.map(intl).fillna(0).astype(int)
    t["podios"] = t.oro + t.plata + t.bronce
    t["por_deportista"] = t.puntos / t.deportistas
    t["zona"] = t.region.map(ubicaciones.ZONA_DE_REGION)
    t["slug"] = t.region.map(ubicaciones.SLUG_REGION)
    t["orden_geo"] = t.region.map(ubicaciones.REGIONES.index)
    t = t.sort_values(["puntos", "oro"], ascending=False, kind="stable").reset_index(drop=True)
    t["lugar"] = t.index + 1
    return t


def _resumen_categorias(df: pd.DataFrame, col_pos: str = "pos") -> pd.DataFrame:
    """Una fila por categoría: inscritos, líder y ventaja del 1.º sobre el 2.º según la columna de lugar."""
    cats = (
        df.groupby("cat_id", sort=False)
        .agg(grupo=("grupo", "first"), grupo_slug=("grupo_slug", "first"), orden_grupo=("orden_grupo", "first"),
             sexo=("sexo", "first"), sexo_txt=("sexo_txt", "first"), peso=("peso", "first"),
             kg=("kg", "first"), cat_slug=("cat_slug", "first"), categoria=("categoria", "first"),
             inscritos=("dep_slug", "size"), activos=("n_torneos", lambda s: int((s > 0).sum())))
        .reset_index()
    )
    primero = df[df[col_pos] == 1].set_index("cat_id")
    segundo = df[df[col_pos] == 2].set_index("cat_id")
    cats["lider"] = cats.cat_id.map(primero.deportista)
    cats["lider_slug"] = cats.cat_id.map(primero.dep_slug)
    cats["lider_club"] = cats.cat_id.map(primero.club_nombre)
    cats["lider_club_slug"] = cats.cat_id.map(primero.club_slug)
    cats["p1"] = cats.cat_id.map(primero.total).fillna(0)
    cats["p2"] = cats.cat_id.map(segundo.total).fillna(0)
    cats["ventaja"] = ((cats.p1 - cats.p2) / cats.p1.where(cats.p1 > 0)).fillna(0)
    cats["competencia"] = cats.ventaja.map(nivel_competencia)
    cats.loc[cats.inscritos < 2, "competencia"] = SIN_RIVALES
    return cats


@dataclass
class Ranking:
    """Todos los indicadores que muestra el sitio, calculados a partir de una versión de las planillas.

    df tiene una fila por deportista y categoría (ver datos.cargar_directorio). Las tablas de clubes,
    regiones y categorías se arman al crearlo; el resto se calcula cuando una página lo pide y queda
    guardado (_memo) hasta la próxima actualización de los datos.
    """
    df: pd.DataFrame
    anio: int
    fecha_datos: dt.date
    cats: pd.DataFrame = field(init=False)
    clubes: pd.DataFrame = field(init=False)
    regiones_t: pd.DataFrame = field(init=False, repr=False)
    fichas: dict = field(init=False, repr=False)
    menores: frozenset = field(init=False, repr=False)
    _cache: dict = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self):
        self.cats = _resumen_categorias(self.df)
        # Quien aparece en alguna edad de menores (aunque también compita en Sub 21 o Absoluta)
        self.menores = frozenset(self.df.loc[self.df.grupo_slug.isin(GRUPOS_MENORES), "dep_slug"])
        self.fichas = ubicaciones.cargar()
        clubes = _tabla_clubes(self.df[self.df.con_club])
        clave = self.df[self.df.con_club].drop_duplicates("club_slug").set_index("club_slug").club
        clubes["ciudad"] = clubes.club_slug.map(lambda s: self.fichas.get(clave[s], {}).get("ciudad", ""))
        clubes["comuna"] = clubes.club_slug.map(lambda s: self.fichas.get(clave[s], {}).get("comuna", ""))
        self.clubes = clubes

        regiones = _tabla_regiones(self.df[self.df.con_club])
        mejor = clubes[clubes.region != ""].drop_duplicates("region").set_index("region")  # clubes ya viene ordenado
        regiones["mejor_club"] = regiones.region.map(mejor.club_nombre)
        regiones["mejor_club_slug"] = regiones.region.map(mejor.club_slug)
        regiones["mejor_club_puntos"] = regiones.region.map(mejor.puntos)
        self.regiones_t = regiones

    def precalcular(self):
        """Calcula la portada al cargar los datos, para que ninguna visita espere."""
        for f in (self.resumen, self.mapa_podios, self.mejores_por_grupo, self.figuras,
                  self.pelea_primer_lugar, self.multi_edad, self.participacion, self.grupos, self.lista_clubes,
                  self.regiones, self.regiones_geo, self.mapa_regiones, self.resumen_regiones):
            f()
        return self

    # ------------------------------------------------------------------
    # Resumen del país
    # ------------------------------------------------------------------
    @_memo
    def resumen(self) -> dict:
        """Cifras generales del país (portada y "Cómo funciona")."""
        df, con = self.df, self.df[self.df.con_club]
        return {
            "deportistas": df.dep_slug.nunique(),
            "registros": len(df),
            "clubes": con.club_slug.nunique(),
            "categorias": len(self.cats),
            "activos": int(df[df.torneos > 0].dep_slug.nunique()),
            "intl": int(df[df.intl > 0].dep_slug.nunique()),
            "sin_club": int(df[~df.con_club].dep_slug.nunique()),
            "variantes_club": int(df.club_original.nunique() - df.club.nunique()),
            "clubes_sin_region": int((self.clubes.region == "").sum()),
        }

    @_memo
    def mapa_podios(self, n=12) -> dict:
        """Podios (1.º a 3.º) de los n clubes con más puntos, en cada grupo de edad."""
        con = self.df[self.df.con_club & (self.df.pos <= 3)]
        top = self.clubes.head(n)
        tabla = con.groupby(["club_slug", "grupo"]).size().unstack(fill_value=0)
        tabla = tabla.reindex(index=top.club_slug, columns=[g[0] for g in ORDEN_GRUPOS], fill_value=0)
        filas = [{"club": c.club_nombre, "slug": c.club_slug, "valores": [int(v) for v in tabla.loc[c.club_slug]]}
                 for c in top.itertuples()]
        return {"grupos": ORDEN_GRUPOS, "filas": filas, "max": max(int(tabla.values.max()), 1)}

    @_memo
    def mejores_por_grupo(self, n=3) -> list[dict]:
        """Los n clubes con más puntos en cada grupo de edad."""
        con = self.df[self.df.con_club]
        out = []
        for etiqueta, _, gslug in ORDEN_GRUPOS:
            t = _tabla_clubes(con[con.grupo == etiqueta]).head(n)
            out.append({"grupo": etiqueta, "slug": gslug, "clubes": t.to_dict("records")})
        return out

    @_memo
    def figuras(self, n=10) -> dict:
        """Los n deportistas con más puntos: en total, ganados este año y en el ranking internacional.
        Cada uno aparece una vez, con su mejor categoría."""
        df = self.df

        def unico(d, col):
            return d.sort_values(col, ascending=False, kind="stable").drop_duplicates("dep_slug").head(n)

        return {
            "total": unico(df, "total").to_dict("records"),
            "temporada": unico(df, "torneos").to_dict("records"),
            "intl": unico(df[df.intl > 0], "intl").to_dict("records"),
        }

    @_memo
    def pelea_primer_lugar(self, n=6) -> dict:
        """Las categorías donde el 1.º le saca más ventaja al 2.º, y las más parejas (con 3 deportistas o más)."""
        c = self.cats[(self.cats.inscritos >= 3) & (self.cats.p1 > 0)]
        return {
            "dominadas": c.sort_values("ventaja", ascending=False).head(n).to_dict("records"),
            "renidas": c.sort_values("ventaja").head(n).to_dict("records"),
        }

    @_memo
    def multi_edad(self) -> list[dict]:
        """Deportistas en el podio de más de un grupo de edad."""
        podio = self.df[self.df.pos <= 3]
        out = []
        for _, podios in podio.groupby("dep_slug"):
            if podios.grupo.nunique() < 2:
                continue
            g = podios.sort_values("orden_grupo")
            out.append({"deportista": g.deportista.iloc[0], "slug": g.dep_slug.iloc[0],
                        "club": g.club_nombre.iloc[0], "club_slug": g.club_slug.iloc[0],
                        "lugares": g[["pos", "grupo", "peso", "grupo_slug", "cat_slug"]].to_dict("records"),
                        "oros": int((g.pos == 1).sum()), "puntos": float(g.total.sum())})
        out.sort(key=lambda x: (-x["oros"], -len(x["lugares"]), -x["puntos"]))
        return out

    @_memo
    def participacion(self) -> list[dict]:
        """Cuántas mujeres y cuántos hombres hay en el ranking de cada grupo de edad."""
        t = self.df.drop_duplicates(["dep_slug", "grupo"]).groupby(["grupo", "sexo"]).size().unstack(fill_value=0)
        return [{"grupo": e, "slug": s, "F": int(t.loc[e].get("F", 0)), "M": int(t.loc[e].get("M", 0))}
                for e, _, s in ORDEN_GRUPOS if e in t.index]

    # ------------------------------------------------------------------
    # Zonas: el lugar se recalcula entre los deportistas de clubes de la zona.
    # ------------------------------------------------------------------
    @_memo
    def _df_zona(self, zona: str) -> pd.DataFrame:
        """Deportistas de clubes de la zona, con su lugar entre ellos (pos_zona)."""
        d = self.df[self.df.zona == zona].copy()
        d["pos_zona"] = d.groupby("cat_id").cumcount() + 1  # df ya viene ordenado por puntaje
        return d

    @_memo
    def _cats_zona(self, zona: str) -> pd.DataFrame:
        """Resumen de cada categoría con los deportistas de la zona (incluye categorías sin deportistas de la zona)."""
        z = _resumen_categorias(self._df_zona(zona), "pos_zona").set_index("cat_id")
        base = self.cats[["cat_id", "grupo", "grupo_slug", "orden_grupo", "sexo", "sexo_txt", "peso", "kg",
                          "cat_slug", "categoria"]].set_index("cat_id")
        datos = ["inscritos", "activos", "lider", "lider_slug", "lider_club", "lider_club_slug", "p1", "p2",
                 "ventaja", "competencia"]
        c = base.join(z[datos]).reset_index()
        c["inscritos"] = c.inscritos.fillna(0).astype(int)
        c["activos"] = c.activos.fillna(0).astype(int)
        c[["p1", "p2", "ventaja"]] = c[["p1", "p2", "ventaja"]].fillna(0)
        c["competencia"] = c.competencia.where(c.inscritos > 0, "")
        c[["lider", "lider_slug", "lider_club", "lider_club_slug"]] = (
            c[["lider", "lider_slug", "lider_club", "lider_club_slug"]].astype(object).where(c.inscritos > 0, None))
        return c

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------
    @_memo
    def grupos(self) -> list[tuple]:
        """Grupos de edad que traen las planillas, en orden: (etiqueta, orden, slug)."""
        return [g for g in ORDEN_GRUPOS if g[0] in set(self.cats.grupo)]

    @_memo
    def categorias_de(self, grupo_slug: str, zona: str = "") -> dict[str, list[dict]]:
        """Categorías de peso de un grupo de edad, separadas en Mujeres y Hombres."""
        cats = self._cats_zona(zona) if zona else self.cats
        c = cats[cats.grupo_slug == grupo_slug].sort_values(["sexo", "kg"])
        return {SEXOS[s]: c[c.sexo == s].to_dict("records") for s in ("F", "M") if (c.sexo == s).any()}

    @_memo
    def categoria(self, grupo_slug: str, cat_slug: str, zona: str = ""):
        """(resumen de la categoría, sus deportistas en orden). Con zona, solo los de clubes de esa zona.
        (None, []) si la categoría no existe."""
        cid = f"{grupo_slug}/{cat_slug}"
        cats = self._cats_zona(zona) if zona else self.cats
        fila = cats[cats.cat_id == cid]
        if fila.empty:
            return None, []
        if zona:
            filas = self._df_zona(zona)
            filas = filas[filas.cat_id == cid].sort_values("pos_zona")
        else:
            filas = self.df[self.df.cat_id == cid].sort_values("pos")
        return fila.iloc[0].to_dict(), filas.to_dict("records")

    # ------------------------------------------------------------------
    # Clubes
    # ------------------------------------------------------------------
    @_memo
    def lista_clubes(self, zona: str = "") -> list[dict]:
        """Clubes ordenados por puntos totales (del país o de una zona)."""
        t = self.clubes[self.clubes.zona == zona] if zona else self.clubes
        filas = t.to_dict("records")
        for i, f in enumerate(filas, 1):
            f["puesto"] = i  # puesto dentro de la lista mostrada (nacional o de la zona)
        return filas

    @_memo
    def clubes_en(self, grupo_slug: str, cat_slug: str = "", zona: str = "") -> list[dict]:
        """Clubes ordenados por los puntos que suman sus deportistas en un grupo de edad o en una categoría."""
        d = self.df[self.df.con_club & (self.df.grupo_slug == grupo_slug)]
        if cat_slug:
            d = d[d.cat_slug == cat_slug]
        if zona:
            d = d[d.zona == zona]
        if d.empty:
            return []
        t = _tabla_clubes(d)
        mejores = d.loc[d.groupby("club_slug").pos.idxmin()].set_index("club_slug")
        t["mejor"] = t.club_slug.map(mejores.deportista)
        t["mejor_slug"] = t.club_slug.map(mejores.dep_slug)
        t["mejor_peso"] = t.club_slug.map(mejores.sexo_txt + " " + mejores.peso)
        filas = t.to_dict("records")
        for i, f in enumerate(filas, 1):
            f["puesto"] = i
        return filas

    @_memo
    def club(self, club_slug: str):
        """Ficha de un club: ubicación, medallas, presencia por edad y todos sus deportistas (None si no existe)."""
        filas = self.df[self.df.club_slug == club_slug]
        if filas.empty:
            return None
        med = self.clubes[self.clubes.club_slug == club_slug]
        info = med.iloc[0].to_dict() if not med.empty else {
            "club_slug": club_slug, "club_nombre": filas.club_nombre.iloc[0], "lugar": None, "region": "", "zona": "",
            "oro": 0, "plata": 0, "bronce": 0, "podios": 0, "top8": int((filas.pos <= 8).sum()),
            "deportistas": filas.dep_slug.nunique(), "puntos": float(filas.total.sum())}
        info["sin_club"] = club_slug == SLUG_SIN_CLUB
        ficha = self.fichas.get(filas.club.iloc[0], {})
        info.update({k: ficha.get(k, "") for k in ("ciudad", "comuna", "nombre_registro", "fuente", "confianza", "nota")})
        info["zona_nombre"] = ubicaciones.NOMBRE_ZONA.get(info.get("zona") or "", "")
        info["variantes"] = sorted(set(filas.club_original) - {filas.club.iloc[0]})
        filas = filas.merge(self.cats[["cat_id", "inscritos"]], on="cat_id")
        por_grupo, presencia = [], []
        for etiqueta, _, gslug in ORDEN_GRUPOS:
            g = filas[filas.grupo == etiqueta].sort_values(["pos", "total"], ascending=[True, False])
            presencia.append({"grupo": etiqueta, "slug": gslug, "deportistas": g.dep_slug.nunique(),
                              "podios": int((g.pos <= 3).sum())})
            if not g.empty:
                por_grupo.append({"grupo": etiqueta, "slug": gslug, "filas": g.to_dict("records")})
        info["numeros_uno"] = filas[filas.pos == 1].sort_values("orden_grupo").to_dict("records")
        info["por_grupo"] = por_grupo
        info["presencia"] = presencia
        return info

    # ------------------------------------------------------------------
    # Regiones (cada deportista cuenta para la región de su club)
    # ------------------------------------------------------------------
    @_memo
    def regiones(self, zona: str = "") -> list[dict]:
        """Regiones ordenadas por puntos totales (del país o de una zona)."""
        t = self.regiones_t[self.regiones_t.zona == zona] if zona else self.regiones_t
        filas = t.to_dict("records")
        for i, f in enumerate(filas, 1):
            f["puesto"] = i  # puesto dentro de la lista mostrada (nacional o de la zona)
        return filas

    @_memo
    def regiones_geo(self, zona: str = "") -> list[dict]:
        """Regiones de norte a sur, agrupadas por zona."""
        filas = sorted(self.regiones(zona), key=lambda f: f["orden_geo"])
        grupos = [{"zona": z, "nombre": nombre, "filas": [f for f in filas if f["zona"] == z]}
                  for z, nombre in ubicaciones.ZONAS]
        return [g for g in grupos if g["filas"]]

    @_memo
    def resumen_regiones(self, zona: str = "") -> dict:
        """Cifras destacadas de la sección Regiones: la que más suma, el mejor promedio, la zona más fuerte."""
        filas = self.regiones(zona)
        if not filas:
            return {}
        zonas = self.regiones_t.groupby("zona").puntos.sum().sort_values(ascending=False)
        return {
            "n": len(filas),
            "top": filas[0],
            "mejor_promedio": max(filas, key=lambda f: f["por_deportista"]),
            "mas_clubes": max(filas, key=lambda f: f["clubes"]),
            "zona_top": {"zona": zonas.index[0], "nombre": ubicaciones.NOMBRE_ZONA[zonas.index[0]],
                         "puntos": float(zonas.iloc[0])},
            "zonas": [{"zona": z, "nombre": ubicaciones.NOMBRE_ZONA[z], "puntos": float(p)} for z, p in zonas.items()],
        }

    @_memo
    def mapa_regiones(self, zona: str = "") -> dict:
        """Podios (1.º a 3.º) de cada región en cada grupo de edad, de norte a sur."""
        filas = sorted(self.regiones(zona), key=lambda f: f["orden_geo"])
        con = self.df[self.df.con_club & (self.df.pos <= 3) & (self.df.region != "")]
        tabla = con.groupby(["region", "grupo"]).size().unstack(fill_value=0)
        tabla = tabla.reindex(index=[f["region"] for f in filas], columns=[g[0] for g in ORDEN_GRUPOS], fill_value=0)
        return {"grupos": ORDEN_GRUPOS, "max": max(int(tabla.values.max()) if len(tabla) else 0, 1),
                "filas": [{"region": f["region"], "slug": f["slug"], "valores": [int(v) for v in tabla.loc[f["region"]]]}
                          for f in filas]}

    @_memo
    def _regiones_por_grupo(self) -> dict:
        """Tabla de regiones de cada grupo de edad (para el puesto de una región en cada edad)."""
        con = self.df[self.df.con_club]
        return {etiqueta: _tabla_regiones(con[con.grupo == etiqueta]) for etiqueta, _, _ in ORDEN_GRUPOS}

    @_memo
    def region(self, slug: str):
        """Ficha de una región: puesto en el país y en su zona, puesto por edad, figuras y clubes (None si no existe)."""
        nombre = ubicaciones.REGION_DE_SLUG.get(slug)
        fila = self.regiones_t[self.regiones_t.region == nombre] if nombre else self.regiones_t.iloc[0:0]
        if fila.empty:
            return None
        info = fila.iloc[0].to_dict()
        info["nombre_largo"] = ubicaciones.nombre_largo(nombre)
        info["zona_nombre"] = ubicaciones.NOMBRE_ZONA[info["zona"]]
        de_zona = self.regiones(info["zona"])
        info["puesto_zona"] = next(f["puesto"] for f in de_zona if f["region"] == nombre)
        info["n_zona"] = len(de_zona)
        info["n_regiones"] = len(self.regiones_t)

        clubes = self.clubes[self.clubes.region == nombre].to_dict("records")
        for i, c in enumerate(clubes, 1):
            c["puesto"] = i
        info["clubes_lista"] = clubes

        d = self.df[self.df.con_club & (self.df.region == nombre)]
        info["numeros_uno"] = d[d.pos == 1].sort_values(["orden_grupo", "sexo", "kg"]).to_dict("records")
        info["figuras"] = (d.sort_values("total", ascending=False, kind="stable")
                           .drop_duplicates("dep_slug").head(10).to_dict("records"))
        por_edad = []
        for etiqueta, _, gslug in ORDEN_GRUPOS:
            tg = self._regiones_por_grupo()[etiqueta]
            f = tg[tg.region == nombre]
            x = f.iloc[0] if not f.empty else None
            por_edad.append({"grupo": etiqueta, "slug": gslug, "n": len(tg),
                             "puesto": int(x.lugar) if x is not None else None,
                             "puntos": float(x.puntos) if x is not None else 0.0,
                             "deportistas": int(x.deportistas) if x is not None else 0,
                             "podios": int(x.podios) if x is not None else 0})
        info["por_edad"] = por_edad
        return info

    # ------------------------------------------------------------------
    # Deportistas y búsqueda
    # ------------------------------------------------------------------
    @_memo
    def deportista(self, dep_slug: str):
        """Ficha de un deportista: sus categorías, mejores lugares y las fichas con su mismo nombre (None si no existe)."""
        filas = self.df[self.df.dep_slug == dep_slug]
        if filas.empty:
            return None
        mismo_nombre = self.df[(self.df.dep_nombre_slug == filas.dep_nombre_slug.iloc[0]) & (self.df.dep_slug != dep_slug)]
        homonimos = mismo_nombre.drop_duplicates("dep_slug")[["dep_slug", "deportista", "club_nombre"]].to_dict("records")
        filas = filas.merge(self.cats[["cat_id", "inscritos", "p1"]], on="cat_id").sort_values("orden_grupo")
        # La planilla oficial a veces anota dos veces a la misma persona en una categoría
        filas["repetida"] = filas.cat_id.duplicated(keep=False)
        clubes = filas.drop_duplicates("club_slug")[["club_nombre", "club_slug", "region"]].to_dict("records")
        return {
            "nombre": filas.deportista.iloc[0], "sexo_txt": filas.sexo_txt.iloc[0], "clubes": clubes,
            "mejor_pos": int(filas.pos.min()), "max_total": float(filas.total.max()),
            "max_intl": float(filas.intl.max()), "n_intl": int(filas.n_intl.max()),
            "n_torneos": int(filas.n_torneos.max()), "filas": filas.to_dict("records"), "homonimos": homonimos,
        }

    def ficha_vigente(self, slug: str):
        """Para enlaces viejos: la dirección de una ficha cambia cuando aparece (o deja de haber) alguien
        con el mismo nombre en otro club. Entrega ("ficha", slug), ("buscar", nombre) o None."""
        d = self.df
        mismo_nombre = d[d.dep_nombre_slug == slug]
        if not mismo_nombre.empty:  # ahora hay una ficha por club: la búsqueda las muestra todas
            return "buscar", mismo_nombre.deportista.iloc[0]
        unicas = d[d.dep_slug == d.dep_nombre_slug]
        antes = unicas[unicas.dep_slug + "-" + unicas.club_slug == slug]
        return ("ficha", antes.dep_slug.iloc[0]) if not antes.empty else None

    def buscar(self, q: str, limite=60) -> dict:
        """Clubes y deportistas cuyo nombre (o club) contiene todas las palabras buscadas, sin importar
        tildes ni mayúsculas. Cada deportista aparece una vez, con su mejor categoría."""
        terms = sin_tildes(q.lower()).split()
        if not terms or len("".join(terms)) < 2:
            return {"clubes": [], "deportistas": [], "total": 0}
        clubes = self.clubes[self.clubes.club_nombre.map(lambda c: all(t in sin_tildes(c.lower()) for t in terms))]
        texto = (self.df.deportista + " " + self.df.club_nombre).map(lambda s: sin_tildes(s.lower()))
        hits = self.df[texto.map(lambda s: all(t in s for t in terms))]
        mejores = hits.sort_values(["pos", "total"], ascending=[True, False]).drop_duplicates("dep_slug")
        return {"clubes": clubes.head(20).to_dict("records"),
                "deportistas": mejores.head(limite).to_dict("records"),
                "total": len(mejores)}
