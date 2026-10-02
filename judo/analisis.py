"""Indicadores del ranking: medallero de clubes, figuras, competitividad y búsquedas."""
from __future__ import annotations

import datetime as dt
import functools
from dataclasses import dataclass, field

import pandas as pd

from .datos import GRUPOS, SEXOS, SLUG_SIN_CLUB, sin_tildes

ORDEN_GRUPOS = [v for v in sorted(GRUPOS.values(), key=lambda x: x[1])]  # (etiqueta, orden, slug)


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
        if resultado is not None and resultado != (None, []):  # no guarda direcciones inexistentes
            self._cache[clave] = resultado
        return resultado
    return envoltura


def _medallero(df: pd.DataFrame) -> pd.DataFrame:
    t = (
        df.groupby(["club_slug", "club_nombre"])
        .agg(oro=("pos", lambda s: int((s == 1).sum())),
             plata=("pos", lambda s: int((s == 2).sum())),
             bronce=("pos", lambda s: int((s == 3).sum())),
             top8=("pos", lambda s: int((s <= 8).sum())),
             deportistas=("dep_slug", "nunique"),
             puntos=("total", "sum"))
        .reset_index()
    )
    t["podios"] = t.oro + t.plata + t.bronce
    return t.sort_values(["oro", "plata", "bronce", "puntos"], ascending=False, kind="stable").reset_index(drop=True)


@dataclass
class Ranking:
    df: pd.DataFrame
    anio: int
    fecha_datos: dt.date
    cats: pd.DataFrame = field(init=False)
    clubes: pd.DataFrame = field(init=False)
    _cache: dict = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self):
        df = self.df
        cats = (
            df.groupby("cat_id", sort=False)
            .agg(grupo=("grupo", "first"), grupo_slug=("grupo_slug", "first"), orden_grupo=("orden_grupo", "first"),
                 sexo=("sexo", "first"), sexo_txt=("sexo_txt", "first"), peso=("peso", "first"),
                 kg=("kg", "first"), cat_slug=("cat_slug", "first"), categoria=("categoria", "first"),
                 inscritos=("dep_slug", "size"), activos=("n_torneos", lambda s: int((s > 0).sum())))
            .reset_index()
        )
        primero = df[df.pos == 1].set_index("cat_id")
        segundo = df[df.pos == 2].set_index("cat_id")
        cats["lider"] = cats.cat_id.map(primero.deportista)
        cats["lider_slug"] = cats.cat_id.map(primero.dep_slug)
        cats["lider_club"] = cats.cat_id.map(primero.club_nombre)
        cats["lider_club_slug"] = cats.cat_id.map(primero.club_slug)
        cats["p1"] = cats.cat_id.map(primero.total).fillna(0)
        cats["p2"] = cats.cat_id.map(segundo.total).fillna(0)
        cats["ventaja"] = ((cats.p1 - cats.p2) / cats.p1.where(cats.p1 > 0)).fillna(0)
        cats["competencia"] = cats.ventaja.map(nivel_competencia)
        self.cats = cats

        clubes = _medallero(df[df.con_club])
        clubes["lugar"] = clubes.index + 1
        self.clubes = clubes

    def precalcular(self):
        """Calcula la portada al cargar los datos, para que ninguna visita espere."""
        for f in (self.resumen, self.mapa_podios, self.mejores_por_grupo, self.figuras,
                  self.pelea_primer_lugar, self.multi_edad, self.participacion, self.grupos):
            f()
        return self

    # ------------------------------------------------------------------
    # Resumen del país
    # ------------------------------------------------------------------
    @_memo
    def resumen(self) -> dict:
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
        }

    @_memo
    def mapa_podios(self, n=12) -> dict:
        """Podios (1.º a 3.º) de los n mejores clubes en cada grupo de edad."""
        con = self.df[self.df.con_club & (self.df.pos <= 3)]
        top = self.clubes.head(n)
        tabla = con.groupby(["club_slug", "grupo"]).size().unstack(fill_value=0)
        tabla = tabla.reindex(index=top.club_slug, columns=[g[0] for g in ORDEN_GRUPOS], fill_value=0)
        filas = [{"club": c.club_nombre, "slug": c.club_slug, "valores": [int(v) for v in tabla.loc[c.club_slug]]}
                 for c in top.itertuples()]
        return {"grupos": ORDEN_GRUPOS, "filas": filas, "max": max(int(tabla.values.max()), 1)}

    @_memo
    def mejores_por_grupo(self, n=3) -> list[dict]:
        con = self.df[self.df.con_club]
        out = []
        for etiqueta, _, gslug in ORDEN_GRUPOS:
            t = _medallero(con[con.grupo == etiqueta]).head(n)
            out.append({"grupo": etiqueta, "slug": gslug, "clubes": t.to_dict("records")})
        return out

    @_memo
    def figuras(self, n=10) -> dict:
        df = self.df
        unico = lambda d, col: d.sort_values(col, ascending=False, kind="stable").drop_duplicates("dep_slug").head(n)
        return {
            "total": unico(df, "total").to_dict("records"),
            "temporada": unico(df, "torneos").to_dict("records"),
            "intl": unico(df[df.intl > 0], "intl").to_dict("records"),
        }

    @_memo
    def pelea_primer_lugar(self, n=6) -> dict:
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
        for _, g in podio.groupby("dep_slug"):
            if g.grupo.nunique() < 2:
                continue
            g = g.sort_values("orden_grupo")
            out.append({"deportista": g.deportista.iloc[0], "slug": g.dep_slug.iloc[0],
                        "club": g.club_nombre.iloc[0], "club_slug": g.club_slug.iloc[0],
                        "lugares": g[["pos", "grupo", "peso", "grupo_slug", "cat_slug"]].to_dict("records"),
                        "oros": int((g.pos == 1).sum()), "puntos": float(g.total.sum())})
        out.sort(key=lambda x: (-x["oros"], -len(x["lugares"]), -x["puntos"]))
        return out

    @_memo
    def participacion(self) -> list[dict]:
        t = self.df.drop_duplicates(["dep_slug", "grupo"]).groupby(["grupo", "sexo"]).size().unstack(fill_value=0)
        return [{"grupo": e, "slug": s, "F": int(t.loc[e].get("F", 0)), "M": int(t.loc[e].get("M", 0))}
                for e, _, s in ORDEN_GRUPOS if e in t.index]

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------
    @_memo
    def grupos(self) -> list[tuple]:
        return [g for g in ORDEN_GRUPOS if g[0] in set(self.cats.grupo)]

    @_memo
    def categorias_de(self, grupo_slug: str) -> dict[str, list[dict]]:
        c = self.cats[self.cats.grupo_slug == grupo_slug].sort_values(["sexo", "kg"])
        return {SEXOS[s]: c[c.sexo == s].to_dict("records") for s in ("F", "M") if (c.sexo == s).any()}

    @_memo
    def categoria(self, grupo_slug: str, cat_slug: str):
        cid = f"{grupo_slug}/{cat_slug}"
        fila = self.cats[self.cats.cat_id == cid]
        if fila.empty:
            return None, []
        return fila.iloc[0].to_dict(), self.df[self.df.cat_id == cid].sort_values("pos").to_dict("records")

    # ------------------------------------------------------------------
    # Clubes y deportistas
    # ------------------------------------------------------------------
    @_memo
    def club(self, club_slug: str):
        filas = self.df[self.df.club_slug == club_slug]
        if filas.empty:
            return None
        med = self.clubes[self.clubes.club_slug == club_slug]
        info = med.iloc[0].to_dict() if not med.empty else {
            "club_slug": club_slug, "club_nombre": filas.club_nombre.iloc[0], "lugar": None,
            "oro": 0, "plata": 0, "bronce": 0, "podios": 0, "top8": int((filas.pos <= 8).sum()),
            "deportistas": filas.dep_slug.nunique(), "puntos": float(filas.total.sum())}
        info["sin_club"] = club_slug == SLUG_SIN_CLUB
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

    @_memo
    def deportista(self, dep_slug: str):
        filas = self.df[self.df.dep_slug == dep_slug]
        if filas.empty:
            return None
        filas = filas.merge(self.cats[["cat_id", "inscritos", "p1"]], on="cat_id").sort_values("orden_grupo")
        clubes = filas.drop_duplicates("club_slug")[["club_nombre", "club_slug"]].to_dict("records")
        return {
            "nombre": filas.deportista.iloc[0], "sexo_txt": filas.sexo_txt.iloc[0], "clubes": clubes,
            "mejor_pos": int(filas.pos.min()), "max_total": float(filas.total.max()),
            "max_intl": float(filas.intl.max()), "n_intl": int(filas.n_intl.max()),
            "n_torneos": int(filas.n_torneos.max()), "filas": filas.to_dict("records"),
        }

    def buscar(self, q: str, limite=60) -> dict:
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
