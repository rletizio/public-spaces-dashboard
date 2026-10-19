"""Build the 500 m grid file for Dashboard 3 (SK_06).

Run from the project root:  python scripts/preprocess_grid.py

Inputs  (prompt/data):  Grid500m_Polygons.geojson  (500 m cells, EPSG:26986, with public-space / green / water areas)
                        Spaces_green.geojson       (the spaces with area_green_m2 / area_green_pct)
                        MassGIS - Census Blocks.geojson (2020 population, Boston / Cambridge / Somerville blocks only)
Output  (static/data):  grid.geojson  (WGS84; only cells that touch Boston, Cambridge or Somerville)
Each cell keeps its area figures plus the spaces that fall in it (largest first), so the page can list
"what spaces are here".  Geometry work is done in EPSG:26986 (meters).
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "prompt" / "data"
OUT = ROOT / "static" / "data"
M = 26986
MAX_SPACES = 8  # spaces listed per cell
MIN_SPACE_M2 = 25  # ignore slivers of a space that only clips a cell corner

grid = gpd.read_file(DATA / "Grid500m_Polygons.geojson").set_crs(M, allow_override=True)
grid = grid[grid.overlap_area_m2.fillna(0) > 0].copy()
spaces = gpd.read_file(DATA / "Spaces_green.geojson").to_crs(M)
spaces["geometry"] = spaces.geometry.make_valid()

# ---- spaces inside each cell
inter = gpd.overlay(grid[["id", "geometry"]].rename(columns={"id": "cell"}),
                    spaces[["id", "name", "category", "owner", "area_green_pct", "geometry"]],
                    how="intersection", keep_geom_type=True)
inter["a"] = inter.geometry.area
inter = inter[inter.a >= MIN_SPACE_M2].sort_values("a", ascending=False)
by_cell = {}
for cell, grp in inter.groupby("cell"):
    by_cell[cell] = dict(
        n=len(grp),
        spaces=[dict(id=r.id, name=r["name"], category=r.category, owner=r.owner,
                     area_m2=round(r.a), green_pct=None if pd.isna(r.area_green_pct) else round(float(r.area_green_pct)))
                for _, r in grp.head(MAX_SPACES).iterrows()])

# ---- residents per cell: 2020 census blocks of the three cities, split by the share of each block inside the cell
blk = gpd.read_file(DATA / "MassGIS - Census Blocks.geojson", engine="pyogrio").set_crs(M, allow_override=True)
blk = blk[blk.TOWN_ID.isin([35, 49, 274]) & (blk.POP20 > 0)][["POP20", "HOUSING20", "geometry"]].copy()
blk["geometry"] = blk.geometry.make_valid()
blk["barea"] = blk.geometry.area
bi = gpd.overlay(grid[["id", "geometry"]].rename(columns={"id": "cell"}), blk, how="intersection", keep_geom_type=True)
bi["f"] = bi.geometry.area / bi.barea
bi["pop"] = bi.POP20 * bi.f
bi["hou"] = bi.HOUSING20 * bi.f
pop_cell = bi.groupby("cell")["pop"].sum()
hou_cell = bi.groupby("cell")["hou"].sum()
print("population allocated to cells:", int(pop_cell.sum()), "of", int(blk.POP20.sum()))

# ---- tidy attributes (clamp rounding artefacts: shares can drift just past 100 %)
def num(v, nd=0):
    return None if pd.isna(v) else round(float(v), nd)

grid["pop"] = grid.id.map(pop_cell).fillna(0)
grid["hou"] = grid.id.map(hou_cell).fillna(0)
grid["pub_clamped"] = grid.apply(lambda r: 0.0 if pd.isna(r.publicspace_area_m2) else min(r.publicspace_area_m2, r.overlap_area_m2), axis=1)
# the cell plus its 8 neighbours (about 1.5 km square): people can reach a park next door
key = {(r.row_index, r.col_index): (r["pop"], r.pub_clamped) for _, r in grid.iterrows()}
nb = {}
for (ri, ci) in key:
    pops = pubs = 0.0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (ri + dr, ci + dc) in key:
                pops += key[(ri + dr, ci + dc)][0]
                pubs += key[(ri + dr, ci + dc)][1]
    nb[(ri, ci)] = (pops, pubs)

rows = []
for _, r in grid.iterrows():
    area = r.overlap_area_m2
    pub = 0.0 if pd.isna(r.publicspace_area_m2) else min(r.publicspace_area_m2, area)
    pub_green_pct = None if pd.isna(r.publicspace_green_pct) else min(float(r.publicspace_green_pct), 100.0)
    green_pct = None if pd.isna(r.overlap_green_pct) else min(float(r.overlap_green_pct), 100.0)
    water = 0.0 if pd.isna(r.overlap_water_m2) else min(r.overlap_water_m2, area)
    c = by_cell.get(r.id, dict(n=0, spaces=[]))
    rows.append(dict(
        id=int(r.id), row=int(r.row_index), col=int(r.col_index), city=r.city,
        pop=num(r["pop"]), housing=num(r["hou"]),
        pop_nb=num(nb[(r.row_index, r.col_index)][0]), pub_nb_m2=num(nb[(r.row_index, r.col_index)][1]),
        area_m2=num(area), pub_m2=num(pub), pub_share=num(100 * pub / area, 1),
        pub_green_pct=None if pub == 0 else num(pub_green_pct, 1),
        green_pct=num(green_pct, 1), water_pct=num(100 * water / area, 1),
        n_spaces=c["n"], spaces=c["spaces"]))
out = gpd.GeoDataFrame(rows, geometry=grid.geometry.values, crs=M).to_crs(4326)
out["geometry"] = out.geometry.simplify(0.00001)
# list-valued column: write through json so the GeoJSON keeps real arrays
import json
feats = []
for _, r in out.iterrows():
    props = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.drop("geometry").items()}
    feats.append(dict(type="Feature", properties=props,
                      geometry=json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]))
with open(OUT / "grid.geojson", "w", encoding="utf-8") as f:
    json.dump(dict(type="FeatureCollection", features=feats), f, separators=(",", ":"))

print("cells:", len(out), "| with public space:", int((out.pub_m2 > 0).sum()),
      "| with green data:", int(out.pub_green_pct.notna().sum()))
print("public area in file (m2):", int(out.pub_m2.sum()), "| listed spaces' area in cells (m2):", int(inter.a.sum()))
print(out.groupby("city").agg(cells=("id", "size"), pub_m2=("pub_m2", "sum")).round(0))
