<h1 align="center">Grid2Poster</h1>

<p align="center">
  Generate print-ready posters of electrical grid infrastructure from OpenStreetMap data.<br/>
  Transmission lines for a country or continent are downloaded and rendered with GeoPandas, OSMnx, and Matplotlib. The project is heavily inspired and reused styling from <a href="https://github.com/originalankur/maptoposter">maptoposter</a>.
</p>

<p align="center">
  <img src="./posters/india_grid_neon_cyberpunk_20260512_143421.png" alt="India transmission grid — paper_grid theme" width="380"/>
  <img src="./posters/africa_grid_paper_grid_20260512_144322.png" alt="Africa transmission grid — paper_grid theme" width="380"/>
</p>

<p align="center"><em> Grid2Poster supports countries, states, provinces and continents, as well as optional administrative boundaries. </em></p>

## Data

Grid2Poster uses OpenStreetMap features tagged as:

- `power=line`
- `power=minor_line` when enabled
- `power=cable` when enabled

Feature completeness depends on OpenStreetMap coverage in the selected country or region.

### Contributing to the data

Coverage and quality in your country can be improved by mapping transmission infrastructure directly in OpenStreetMap. [MapYourGrid](https://mapyourgrid.org) is a community initiative that coordinates this work — it provides tutorials, country-level completeness/quality statistics and mapping tools for tracing power lines, generators and substations from imagery.

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

Render an entire continent. Continent boundaries come from the Natural Earth admin-0 dataset (downloaded and cached on first use) because Nominatim does not resolve continent names. Accepted values are `Africa`, `Antarctica`, `Asia`, `Europe`, `North America`, `Oceania`, and `South America`:

```bash
python create_grid_poster.py --country Africa --tile-size-km 500
```

Continent-scale runs hit the Overpass API hundreds of times and can take several hours. A larger `--tile-size-km` cuts the number of queries; pick a value that still stays under the Overpass per-query size limit.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--country` | — | Country or region name resolvable by Nominatim, or a continent name (`Africa`, `Antarctica`, `Asia`, `Europe`, `North America`, `Oceania`, `South America`). |
| `--display-country` | value of `--country` | Text to print on the poster. Useful when the geocoder name differs from the desired title. |
| `--theme` | `electric_midnight` | Theme ID from the `themes/` directory. |
| `--list-themes` | — | List available themes and exit. |
| `--include-minor-lines` | off | Also fetch `power=minor_line` features. |
| `--include-cables` | off | Also fetch `power=cable` features. |
| `--width` | `12.0` | Poster width in inches. |
| `--height` | `16.0` | Poster height in inches. |
| `--dpi` | `300` | Raster output DPI (applies to PNG output). |
| `--tile-size-km` | `200` | Overpass query tile size in kilometers. Use smaller values for very large countries or busy servers. |
| `--format`, `-f` | `png` | Output format: `png`, `svg`, or `pdf`. |
| `--output`, `-o` | auto-generated in `posters/` | Output file path. |
| `--crs` | `EPSG:3857` | Projection used for rendering. EPSG:3857 (Pseudo-Mercator) works well for country posters. |
| `--hide-metadata` | off | Do not print segment counts on the poster. |
| `--verbose-osmnx` | off | Print OSMnx request logs. |

## Output

Generated posters are written to the `posters/` directory by default. Intermediate OSM responses and processed geometries are cached in `cache/` to avoid repeated downloads.

## Gallery

| Poster | Country | Theme |
| --- | --- | --- |
| ![`india_grid_blackout_20260512_100511.png`](posters/india_grid_blackout_20260512_100511.png) | India | `blackout` |
| ![`india_grid_paper_grid_20260512_105701.png`](posters/india_grid_paper_grid_20260512_125057.png) | India | `paper_grid` |
| ![`kenya_grid_electric_midnight_20260512_091015.png`](posters/kenya_grid_electric_midnight_20260512_091015.png) | Kenya | `electric_midnight` |
| ![`kenya_grid_paper_grid_20260512_091554.png`](posters/kenya_grid_paper_grid_20260512_091554.png) | Kenya | `paper_grid` |
| ![`pakistan_grid_paper_grid_20260512_092409.png`](posters/pakistan_grid_paper_grid_20260512_092409.png) | Pakistan | `paper_grid` |

## Notes

The script uses the public Overpass API through OSMnx. Large requests may fail or be rate-limited. Use smaller `--tile-size-km` values for large countries or when the Overpass server is busy.

The map is intended for visualisation and print design. It should not be used as an authoritative grid model.

## Attribution

Map data © OpenStreetMap contributors.

