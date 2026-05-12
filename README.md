# GridToPoster

Generate print-ready posters of electrical grid infrastructure from OpenStreetMap data.

The script downloads country-level power infrastructure, including transmission lines, substations, and power plants, then renders a static poster using GeoPandas, OSMnx, and Matplotlib.

## Data

GridToPoster uses OpenStreetMap features tagged as:

- `power=line`
- `power=minor_line` when enabled
- `power=cable` when enabled
- `power=substation`
- `power=plant`

Feature completeness depends on OpenStreetMap coverage in the selected country or region.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install osmnx geopandas matplotlib numpy pandas shapely tqdm
```

## Usage

```bash
python create_grid_poster.py --country Germany
```

For large countries, reduce the Overpass query tile size:

```bash
python create_grid_poster.py --country France --tile-size-km 150
```

Export as SVG or PDF for vector workflows:

```bash
python create_grid_poster.py --country Spain --format svg
python create_grid_poster.py --country Poland --format pdf
```

Include additional infrastructure layers:

```bash
python create_grid_poster.py --country Germany --include-minor-lines --include-cables
```

List available themes:

```bash
python create_grid_poster.py --list-themes
```

## Output

Generated posters are written to the `posters/` directory by default. Intermediate OSM responses and processed geometries are cached in `cache/` to avoid repeated downloads.

## Gallery

| Poster | Country | Theme |
| --- | --- | --- |
| [`india_grid_blackout_20260512_100511.png`](posters/india_grid_blackout_20260512_100511.png) | India | `blackout` |
| [`india_grid_paper_grid_20260512_105701.png`](posters/india_grid_paper_grid_20260512_105701.png) | India | `paper_grid` |
| [`kenya_grid_electric_midnight_20260512_091015.png`](posters/kenya_grid_electric_midnight_20260512_091015.png) | Kenya | `electric_midnight` |
| [`kenya_grid_paper_grid_20260512_091554.png`](posters/kenya_grid_paper_grid_20260512_091554.png) | Kenya | `paper_grid` |
| [`pakistan_grid_paper_grid_20260512_092409.png`](posters/pakistan_grid_paper_grid_20260512_092409.png) | Pakistan | `paper_grid` |

## Notes

The script uses the public Overpass API through OSMnx. Large requests may fail or be rate-limited. Use smaller `--tile-size-km` values for large countries or when the Overpass server is busy.

The map is intended for visualisation and print design. It should not be used as an authoritative grid model.

## Attribution

Map data © OpenStreetMap contributors.

