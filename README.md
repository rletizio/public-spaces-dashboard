# Public Spaces of Boston, Cambridge & Somerville

Interactive D3 / SvelteKit dashboards on public space in the Boston area (CS171 visualization project).

**Live site:** https://rletizio.github.io/public-spaces-dashboard/

| Page | Path | Content |
|---|---|---|
| Landing | `/` | Index of dashboards |
| Dashboard 1 | `/dashboard-1/` | Map of public spaces (pan, jump, select an area) linked to a dot plot of the people living within 500 m of each space |

## Run locally

```bash
npm ci
npm run dev        # http://localhost:5173
npm run build      # static site in ./build
```

## Data

The app reads only the small, processed files in `static/data/` (`spaces.geojson`, `boundaries.geojson`,
`water.geojson`, `spaces.csv`; see `static/data/README.md` for the fields). They are produced by
`scripts/preprocess_spaces.py` from MassGIS (open space, census blocks, town boundaries, hydrography)
and the Boston, Cambridge and Somerville open-space layers. The raw source files are large and are not in this
repository; the script needs them in `prompt/data/` and Python with `geopandas`.

Rules used to build the dataset: usable public spaces only (cemeteries, conservation land, school grounds,
water supply and flood control land are excluded); MassGIS is the primary source, completed with municipal
data; people within 500 m are 2020 census block populations weighted by the share of each block inside a
500 m buffer of the space (straight-line distance).

## Adding another dashboard

Create `src/routes/<name>/+page.svelte` (and a `+page.js` if it loads data with `asset('/data/...')`), then
list it in `src/routes/+page.svelte`. GitHub Pages serves everything from the same repository at
`/<name>/`.

## Deployment

Every push to `main` runs `.github/workflows/deploy.yml`, which builds the static site with
`BASE_PATH=/public-spaces-dashboard` and publishes it to GitHub Pages.

Basemap © OpenStreetMap contributors.
