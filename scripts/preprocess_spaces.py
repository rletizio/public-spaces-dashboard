"""Build the cleaned public-space dataset for the dashboard.

Run from the project root:  python scripts/preprocess_spaces.py

Inputs  (prompt/data):  MassGIS open space (primary), Boston / Cambridge / Somerville
                        municipal layers (cross-check + gap-fill), MassGIS census blocks,
                        town boundaries, hydrography.
Outputs (static/data):  spaces.geojson, boundaries.geojson, water.geojson (WGS84),
                        spaces.csv, and review/ csv files listing what was excluded/added.
All geometry work is done in EPSG:26986 (MA State Plane, meters).
"""
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "prompt" / "data"
OUT = ROOT / "static" / "data"
REVIEW = OUT / "review"
OUT.mkdir(parents=True, exist_ok=True)
REVIEW.mkdir(parents=True, exist_ok=True)

M = 26986
TOWNS = {35: "Boston", 49: "Cambridge", 274: "Somerville"}
ACCESS_RADIUS_M = 500
MIN_AREA_M2 = 50
CLUSTER_GAP_M = 30  # same-name polygons closer than this are one space

CATS = {
    "plaza": "Square, Plaza & Mall",
    "park": "Park",
    "play": "Playground & Athletic Field",
    "garden": "Community Garden",
    "parkway": "Parkway, Reservation & Waterfront",
}

# ---------------------------------------------------------------- rules
RX_CEMETERY = re.compile(r"cemeter|cemetary|burying|burial|memorial gardens", re.I)
RX_CONSERV = re.compile(r"\bCR\b|conservation restriction|\bWMA\b|wildlife management", re.I)
RX_INFRA = re.compile(r"\bdam\b|water treatment|surface water|reservoir", re.I)
RX_SCHOOL = re.compile(r"school|academy|college|universit|campus|\bMIT\b|library|housing|golf", re.I)
RX_PLAZA = re.compile(r"\b(squares?|sq|plazas?|mall|common|circle|triangle|place|courtyard|green)\b", re.I)
RX_PLAY = re.compile(r"playground|play area|play lot|tot lot|\bfields?\b|ballfield|athletic|rink|\bcourts?\b|skate|stadium|pool", re.I)
RX_PARKWAY = re.compile(r"parkway|reservation|beach|harborwalk|esplanade|greenway|riverwalk|riverway|\bpier\b|waterfront|shore|wharf|corridor|\bpath\b|trail|boulevard|riverfront", re.I)
RX_GARDEN = re.compile(r"community garden", re.I)

OS_TYPE_EXCLUDE = {"Cemetery", "Conservation Area", "Youth Camp", "Flood Control Area",
                   "Elementary School Playground"}
PURPOSE_EXCLUDE = {"C", "W", "F"}  # conservation, water supply, flood control
BOSTON_TYPE_EXCLUDE = {"Cemeteries & Burying Grounds", "Urban Wilds", "Open Land", "Other Open Land"}
BOSTON_TYPE_MAP = {
    "Malls, Squares & Plazas": "plaza", "Malls, Square & Plazas": "plaza",
    "Malls, Squares, & Plazas": "plaza",
    "Parks, Playgrounds & Athletic Fields": None,  # park vs playground decided by name
    "Parkways, Reservations & Beaches": "parkway",
    "Community Gardens": "garden",
}
# Cambridge basemap FCODE meanings, inferred from the names of the polygons that carry them.
CAM_FCODE_INCLUDE = {1, 6, 13, 14, 15, 21, 22, 28, 41, 42, 43}


def name_excluded(name):
    if not isinstance(name, str):
        return None
    for tag, rx in (("cemetery", RX_CEMETERY), ("conservation", RX_CONSERV),
                    ("infrastructure/water", RX_INFRA), ("school/institution", RX_SCHOOL)):
        if rx.search(name):
            return tag
    return None


def category_from_name(name, purpose=None):
    n = name if isinstance(name, str) else ""
    if RX_GARDEN.search(n) or (purpose == "A" and "garden" in n.lower()):
        return "garden"
    if RX_PLAZA.search(n):
        return "plaza"
    if RX_PLAY.search(n):
        return "play"
    if RX_PARKWAY.search(n):
        return "parkway"
    return "park"


RX_FEE_CITY = re.compile(r"^(city|town) of|boston planning|boston redevelopment|boston housing|boston public|boston parks", re.I)
RX_FEE_STATE = re.compile(r"^DCR|commonwealth of massachusetts|massachusetts bay transit|MBTA|department of transportation|"
                          r"massachusetts highway|massport|water resources authority|^massachusetts department|"
                          r"division of capital|state of massachusetts", re.I)
NONPROFIT = "Nonprofit / institutional"
RX_FEE_NONPROFIT = re.compile(r"universit|college|institute of technology|church|archdiocese|congregation|synagogue|"
                              r"temple|association|trust|natural areas network|audubon|foundation|society|"
                              r"hospital|museum|fund|school|academy|inc", re.I)
RX_FEE_FED = re.compile(r"national park service|united states|army corps|federal|USA", re.I)


def owner_class_massgis(fee, t):
    """Classify by the fee-owner name (most specific), falling back to the one-letter OWNER_TYPE."""
    f = fee if isinstance(fee, str) else ""
    if RX_FEE_CITY.search(f):
        return "City"
    if RX_FEE_STATE.search(f):
        return "State"
    if RX_FEE_FED.search(f):
        return "Other public"
    if t in ("N", "L", "B") or RX_FEE_NONPROFIT.search(f):
        return NONPROFIT
    return {"M": "City", "S": "State", "F": "Other public"}.get(t, "Private")


def owner_class_boston(o):
    o = (o or "").lower()
    if o.startswith("city") or o in ("bra", "boston water & sewer commission"):
        return "City"
    if o in ("private",):
        return "Private"
    if o in ("commonwealth of massachusetts", "massdot", "massport", "mbta"):
        return "State"
    return "Other public"


def owner_class_cambridge(o):
    return {"City": "City", "Cambridge": "City", "School Dep": "City", "State": "State",
            "Private": "Private", "POPS": "Private", "Easement": "Private"}.get(o, "Other public")


def norm_name(n):
    if not isinstance(n, str):
        return None
    n = re.sub(r"[^a-z0-9 ]", " ", n.lower())
    n = re.sub(r"\bsq\b", "square", n)
    return re.sub(r"\s+", " ", n).strip() or None


# ---------------------------------------------------------------- load
print("loading ...")
mg = gpd.read_file(DATA / "MassGIS - Open Spaces.geojson", where="TOWN_ID IN (35,49,274)",
                   engine="pyogrio").set_crs(M, allow_override=True)
mg["city"] = mg.TOWN_ID.map(TOWNS)
bos = gpd.read_file(DATA / "Boston - Open Spaces.geojson").set_crs(4326).to_crs(M)
cam = gpd.read_file(DATA / "Cambridge - Recreational Open Spaces.geojson").set_crs(2249, allow_override=True).to_crs(M)
pla = gpd.read_file(DATA / "Cambridge - Plazas.geojson").set_crs(2249, allow_override=True).to_crs(M)
# Somerville's qmd says EPSG:26986 but the coordinates are in feet (EPSG:2249).
som = gpd.read_file(DATA / "Somerville - Open Spaces.geojson").set_crs(2249, allow_override=True).to_crs(M)
for g in (mg, bos, cam, pla, som):
    g["geometry"] = g.geometry.make_valid()

# ---------------------------------------------------------------- Boston attributes for MassGIS polys
ob = mg[mg.city == "Boston"][["POLY_ID", "TOWN_ID", "geometry"]].copy()
ob["_mid"] = ob.index
inter = gpd.overlay(ob[["_mid", "geometry"]],
                    bos[["OS_ID", "TypeLong", "OWNERSHIP", "YearAcquir", "geometry"]],
                    how="intersection", keep_geom_type=True)
inter["a"] = inter.area
best = inter.sort_values("a").groupby("_mid").tail(1).set_index("_mid")
best["frac"] = best.a / mg.loc[best.index].area
best = best[best.frac > 0.5]
mg["b_type"] = best.TypeLong.reindex(mg.index)
mg["b_year"] = best.YearAcquir.reindex(mg.index)
mg["b_owner"] = best.OWNERSHIP.reindex(mg.index)
oc = mg[mg.city == "Cambridge"][["geometry"]].copy()
oc["_mid"] = oc.index
ic = gpd.overlay(oc, cam[["OWNER", "geometry"]], how="intersection", keep_geom_type=True)
ic["a"] = ic.area
bc = ic.sort_values("a").groupby("_mid").tail(1).set_index("_mid")
bc = bc[bc.a / mg.loc[bc.index].area > 0.5]
mg["c_owner"] = bc.OWNER.reindex(mg.index)
mg["muni_owner"] = mg.b_owner.map(lambda o: owner_class_boston(o) if isinstance(o, str) else None)
cm = mg.c_owner.map(lambda o: owner_class_cambridge(o) if isinstance(o, str) else None)
mg["muni_owner"] = mg.muni_owner.fillna(cm)

# ---------------------------------------------------------------- classify MassGIS polygons
rows = []
for i, r in mg.iterrows():
    reason = None
    if r.OS_TYPE in OS_TYPE_EXCLUDE:
        reason = f"OS_TYPE={r.OS_TYPE}"
    elif r.PRIM_PURP in PURPOSE_EXCLUDE:
        reason = f"purpose={r.PRIM_PURP}"
    elif r.PUB_ACCESS == "N":
        reason = "no public access"
    elif isinstance(r.b_type, str) and r.b_type in BOSTON_TYPE_EXCLUDE:
        reason = f"Boston type={r.b_type}"
    else:
        reason = name_excluded(r.SITE_NAME)
    cat = None
    if reason is None:
        if r.b_type in BOSTON_TYPE_MAP and BOSTON_TYPE_MAP[r.b_type]:
            cat = BOSTON_TYPE_MAP[r.b_type]
        elif r.b_type == "Parks, Playgrounds & Athletic Fields":
            cat = "play" if RX_PLAY.search(str(r.SITE_NAME)) else "park"
        else:
            cat = category_from_name(r.SITE_NAME, r.PRIM_PURP)
    rows.append((reason, cat))
mg["excl"] = [x[0] for x in rows]
mg["cat"] = [x[1] for x in rows]

all_mg_union = mg.geometry.union_all()
cand = []
m_ok = mg[mg.excl.isna()]
cand.append(gpd.GeoDataFrame({
    "name": m_ok.SITE_NAME, "city": m_ok.city, "cat": m_ok.cat,
    "owner": [owner_class_massgis(f, t) for f, t in zip(m_ok.FEE_OWNER, m_ok.OWNER_TYPE)],
    "owner_raw": m_ok.FEE_OWNER, "owner_muni": m_ok.muni_owner,
    "access": m_ok.PUB_ACCESS, "year": m_ok.b_year.where(m_ok.b_year > 0),
    "source": "MassGIS", "geometry": m_ok.geometry}, crs=M))


# ---------------------------------------------------------------- municipal gap-fill
def uncovered(g, union, thr=0.5):
    cov = g.geometry.intersection(union).area / g.geometry.area.replace(0, np.nan)
    return cov.fillna(1) < thr


gap_log = []
# Boston
b = bos[uncovered(bos, all_mg_union)].copy()
for _, r in b.iterrows():
    reason = None
    if r.TypeLong in BOSTON_TYPE_EXCLUDE:
        reason = f"Boston type={r.TypeLong}"
    else:
        reason = name_excluded(r.SITE_NAME)
    t = r.TypeLong
    cat = BOSTON_TYPE_MAP.get(t) or ("play" if RX_PLAY.search(str(r.SITE_NAME)) else "park")
    gap_log.append(dict(source="Boston", name=r.SITE_NAME, detail=t, acres=r.ACRES, excluded=reason))
    if reason is None:
        cand.append(gpd.GeoDataFrame({
            "name": [r.SITE_NAME], "city": ["Boston"], "cat": [cat],
            "owner": [owner_class_boston(r.OWNERSHIP)], "owner_raw": [r.OWNERSHIP],
            "access": ["Y"], "year": [r.YearAcquir if r.YearAcquir and r.YearAcquir > 0 else np.nan],
            "source": ["Boston (gap-fill)"], "geometry": [r.geometry]}, crs=M))
# Cambridge open space
covered = all_mg_union
c = cam[uncovered(cam, covered)].copy()
for _, r in c.iterrows():
    reason = None
    if r.FCODE not in CAM_FCODE_INCLUDE:
        reason = f"FCODE={r.FCODE}"
    else:
        reason = name_excluded(r.NAME)
    gap_log.append(dict(source="Cambridge", name=r.NAME, detail=f"FCODE {r.FCODE} / {r.OWNER}",
                        acres=r.Acres, excluded=reason))
    if reason is None:
        f = r.FCODE
        cat = ("garden" if f == 13 else "plaza" if f in (6, 14, 42) else
               "parkway" if f == 22 else "play" if f in (15, 28) else category_from_name(r.NAME))
        if f in (41, 43, 21, 1) and cat == "parkway" and not RX_PARKWAY.search(str(r.NAME)):
            cat = "park"
        cand.append(gpd.GeoDataFrame({
            "name": [r.NAME], "city": ["Cambridge"], "cat": [cat],
            "owner": [owner_class_cambridge(r.OWNER)], "owner_raw": [r.OWNER],
            "access": ["L" if r.OWNER in ("Private",) else "Y"], "year": [np.nan],
            "source": ["Cambridge (gap-fill)"], "geometry": [r.geometry]}, crs=M))
covered = gpd.GeoSeries([all_mg_union, cam.geometry.union_all()], crs=M).union_all()
# Cambridge basemap plazas (only unnamed plaza footprints not in any other layer)
p = pla[(pla.TYPE == "PLAZA") & uncovered(pla, covered)].copy()
for _, r in p.iterrows():
    reason = "too small" if r.geometry.area < 100 else None
    gap_log.append(dict(source="Cambridge plazas", name=None, detail="basemap PLAZA",
                        acres=r.geometry.area / 4046.86, excluded=reason))
    if reason is None:
        cand.append(gpd.GeoDataFrame({
            "name": [None], "city": ["Cambridge"], "cat": ["plaza"], "owner": ["Unknown"],
            "owner_raw": [None], "access": ["X"], "year": [np.nan],
            "source": ["Cambridge basemap plaza"], "geometry": [r.geometry]}, crs=M))
# Somerville
s = som[uncovered(som, all_mg_union)].copy()
for _, r in s.iterrows():
    reason = name_excluded(r.Name)
    gap_log.append(dict(source="Somerville", name=r.Name, detail="", acres=r.SHAPE_Area / 4046.86,
                        excluded=reason))
    if reason is None:
        cand.append(gpd.GeoDataFrame({
            "name": [r.Name], "city": ["Somerville"], "cat": [category_from_name(r.Name)],
            "owner": ["City"], "owner_raw": ["assumed"], "access": ["Y"], "year": [np.nan],
            "source": ["Somerville (gap-fill)"], "geometry": [r.geometry]}, crs=M))

cand = pd.concat(cand, ignore_index=True)
cand = gpd.GeoDataFrame(cand, geometry="geometry", crs=M)
cand = cand[~cand.geometry.is_empty & (cand.geometry.area >= MIN_AREA_M2)].reset_index(drop=True)
print("candidate polygons:", len(cand))

# ---------------------------------------------------------------- cluster polygons into spaces
cand["nn"] = cand.name.map(norm_name)
cand["cluster"] = -1
next_id = 0
for (city, nn), grp in cand[cand.nn.notna()].groupby(["city", "nn"]):
    comp = gpd.GeoSeries(grp.geometry.buffer(CLUSTER_GAP_M / 2).values, crs=M).union_all()
    parts = list(comp.geoms) if hasattr(comp, "geoms") else [comp]
    for idx, geom in zip(grp.index, grp.geometry):
        for k, part in enumerate(parts):
            if part.intersects(geom):
                cand.loc[idx, "cluster"] = next_id + k
                break
    next_id += len(parts)
un = cand.cluster == -1
cand.loc[un, "cluster"] = range(next_id, next_id + un.sum())

spaces = []
for cid, grp in cand.groupby("cluster"):
    geom = grp.geometry.union_all()
    area = grp.geometry.area
    lead = grp.loc[area.idxmax()]
    w = grp.groupby("owner").apply(lambda d: d.geometry.area.sum()).idxmax()
    acc = "Y" if (grp.access == "Y").any() else ("L" if (grp.access == "L").any() else "X")
    yrs = grp.year.dropna()
    muni = grp.owner_muni.dropna()
    if len(muni) == 0:
        check = "municipal only" if grp.source.str.contains("gap-fill|basemap").all() else "no municipal match"
        muni_cls = None
    else:
        muni_cls = muni.mode().iloc[0]
        check = "agree" if (muni_cls == w or (muni_cls == "Private" and w == NONPROFIT)) else "differs"
    spaces.append(dict(
        owner_name=lead["owner_raw"], owner_municipal=muni_cls, owner_check=check,
        name=lead["name"] if isinstance(lead["name"], str) else "Unnamed " + CATS[lead["cat"]].split(",")[0].lower(),
        city=lead.city, category=CATS[lead["cat"]], owner=w, access=acc,
        year=int(yrs.min()) if len(yrs) else None,
        source=", ".join(sorted(set(grp.source))), n_parts=len(grp), geometry=geom))
sp = gpd.GeoDataFrame(spaces, geometry="geometry", crs=M)
sp["area_m2"] = sp.geometry.area.round(1)
sp["area_acres"] = (sp.area_m2 / 4046.8564).round(3)
# a name like "... Common" or "... Green" can be a large park, not a plaza: outside Boston
# (where the city layer gives the type) treat large name-derived plazas as parks.
big_plaza = (sp.category == CATS["plaza"]) & (sp.area_acres > 3) & (sp.city != "Boston")
sp.loc[big_plaza, "category"] = CATS["park"]
sp["private_owned"] = sp.owner.isin(["Private", NONPROFIT])
sp = sp.sort_values("area_m2", ascending=False).reset_index(drop=True)
sp["id"] = ["S%04d" % i for i in range(len(sp))]
sp["rank_all"] = sp.area_m2.rank(ascending=False, method="min").astype(int)

# ---------------------------------------------------------------- people within 500 m (areal weighting)
print("census access ...")
blk = gpd.read_file(DATA / "MassGIS - Census Blocks.geojson", engine="pyogrio").set_crs(M, allow_override=True)
blk = blk[["GEOID20", "POP20", "HOUSING20", "geometry"]].copy()
blk["geometry"] = blk.geometry.make_valid()
blk["barea"] = blk.geometry.area
sindex = blk.sindex
pops, houses = [], []
for geom in sp.geometry:
    buf = geom.buffer(ACCESS_RADIUS_M, resolution=8)
    ix = sindex.query(buf, predicate="intersects")
    sub = blk.iloc[ix]
    frac = sub.geometry.intersection(buf).area / sub.barea
    pops.append(float((sub.POP20 * frac).sum()))
    houses.append(float((sub.HOUSING20 * frac).sum()))
sp["pop_500m"] = np.round(pops).astype(int)
sp["housing_500m"] = np.round(houses).astype(int)

# ---------------------------------------------------------------- write
print("writing ...")
out = sp.copy()
out["geometry"] = out.geometry.simplify(1.5, preserve_topology=True)
cent = out.geometry.representative_point().to_crs(4326)
out["lon"], out["lat"] = cent.x.round(5), cent.y.round(5)
cols = ["id", "name", "city", "category", "owner", "owner_name", "owner_municipal", "owner_check", "private_owned", "access", "year", "area_m2",
        "area_acres", "rank_all", "pop_500m", "housing_500m", "n_parts", "source", "lon", "lat"]
out_w = out.to_crs(4326)[cols + ["geometry"]]
out_w.to_file(OUT / "spaces.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
pd.DataFrame(out_w.drop(columns="geometry")).to_csv(OUT / "spaces.csv", index=False)

towns = gpd.read_file(DATA / "MassGIS - Town Survey.geojson", engine="pyogrio").set_crs(M, allow_override=True)
t3 = towns[towns.TOWN_ID.isin(TOWNS)].dissolve(by="TOWN_ID", as_index=False)
t3["city"] = t3.TOWN_ID.map(TOWNS)
t3["geometry"] = t3.geometry.simplify(5)
t3[["city", "geometry"]].to_crs(4326).to_file(OUT / "boundaries.geojson", driver="GeoJSON")

bounds = t3.total_bounds
win = box(bounds[0] - 1500, bounds[1] - 1500, bounds[2] + 1500, bounds[3] + 1500)
hy = gpd.read_file(DATA / "MassGIS - Hydrography.geojson", bbox=tuple(win.bounds), engine="pyogrio").set_crs(M, allow_override=True)
hy = hy[hy.geometry.area > 2000].copy()  # drop tiny ponds/streams for the basemap
hy["geometry"] = hy.geometry.make_valid().intersection(win).simplify(5)
hy = hy[~hy.geometry.is_empty]
hy[["geometry"]].dissolve().to_crs(4326).to_file(OUT / "water.geojson", driver="GeoJSON")

# review files
rev = mg.drop(columns="geometry")[["city", "SITE_NAME", "OWNER_TYPE", "PRIM_PURP", "PUB_ACCESS", "OS_TYPE",
                                   "b_type", "GIS_ACRES", "excl", "cat"]]
rev.to_csv(REVIEW / "massgis_classification.csv", index=False)
pd.DataFrame(gap_log).to_csv(REVIEW / "municipal_gapfill.csv", index=False)

# ---------------------------------------------------------------- summary
print("\n=== spaces:", len(sp))
print(sp.groupby("city").agg(n=("id", "size"), acres=("area_acres", "sum")).round(0))
print(pd.crosstab(sp.category, sp.city))
print(pd.crosstab(sp.owner, sp.city))
print(pd.crosstab(sp.owner_check, sp.city))
print(sp.source.value_counts())
print("with year:", sp.year.notna().sum(), sp.groupby("city").year.apply(lambda s: s.notna().sum()).to_dict())
print(sp.pop_500m.describe().round(0))
print("MassGIS excluded:", mg.excl.notna().sum(), mg.excl.dropna().str.split("=").str[0].value_counts().to_dict())
