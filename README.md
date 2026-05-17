<h1 align="center">Grid2Poster</h1>

<p align="center">
  Generate print-ready posters of electrical grid infrastructure from OpenStreetMap data.<br/>
  Transmission lines for a country or continent are downloaded and rendered with GeoPandas, OSMnx, and Matplotlib. The project is heavily inspired and reused styling from <a href="https://github.com/originalankur/maptoposter">maptoposter</a>.
</p>

<p align="center">
  <img src="./posters/india_grid_neon_cyberpunk_20260512_143421.png" alt="India transmission grid - paper_grid theme" width="380"/>
  <img src="./posters/africa_grid_paper_grid_20260512_144322.png" alt="Africa transmission grid - paper_grid theme" width="380"/>
</p>

<p align="center"> Grid2Poster supports countries, states, provinces and continents, as well as predefined regions.</p>

## Data

Grid2Poster uses OpenStreetMap features tagged as:

- `power=line`
- `power=minor_line` when enabled
- `power=cable` when enabled

Feature completeness depends on OpenStreetMap coverage in the selected country or region.

### Contributing to the data

Coverage and quality in your country can be improved by mapping transmission infrastructure directly in OpenStreetMap. [MapYourGrid](https://mapyourgrid.org) is a community initiative that coordinates this work. It provides tutorials, country-level completeness/quality statistics and mapping tools for tracing power lines, generators and substations from imagery.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

By default every run writes both a PNG and an SVG:

```bash
python create_grid_poster.py --country Portugal
```

For large countries, reduce the Overpass query tile size:

```bash
python create_grid_poster.py --country Vietnam --tile-size-km 150
```


```

Include additional distribution grids if available:

```bash
python create_grid_poster.py --country Germany --include-minor-lines

List available themes:

```bash
python create_grid_poster.py --list-themes
```

Use a local GeoJSON file as the boundary instead of geocoding (handy for custom regions or sub-national areas):

```bash
python create_grid_poster.py --country "Middle East and North Africa" --boundary-geojson ./regions/mena.geojson  
```

All polygonal features in the file are dissolved into a single boundary. The `--country` value is still used for the poster title and output filename.

Render an entire continent. Continent boundaries come from the Natural Earth admin-0 dataset (downloaded and cached on first use) because Nominatim does not resolve continent names. Accepted values are `Africa`, `Antarctica`, `Asia`, `Europe`, `North America`, `Oceania`, and `South America`. The aggregate name `global` combines every inhabited continent.

```bash
python create_grid_poster.py --country Africa --tile-size-km 500
```

Continent-scale runs hit the Overpass API hundreds of times and can take several hours. A larger `--tile-size-km` cuts the number of queries; pick a value that still stays under the Overpass per-query size limit.


## Options

| Option | Default | Description |
| --- | --- | --- |
| `--country` | - | Country or region name resolvable by Nominatim, a continent name (`Africa`, `Antarctica`, `Asia`, `Europe`, `North America`, `Oceania`, `South America`), or the aggregate `global` (all inhabited continents plus Australia, Papua New Guinea, and New Zealand, clipped at Alaska's northernmost latitude and New Zealand's easternmost main-island longitude). When paired with `--boundary-geojson`, the value is used only as the poster title. |
| `--boundary-geojson` | - | Path to a local GeoJSON file with polygonal boundary features. Overrides the Nominatim/Natural Earth lookup. Useful for custom regions, sub-national areas, or offline workflows. |
| `--display-country` | value of `--country` | Text to print on the poster. Useful when the geocoder name differs from the desired title. |
| `--subtitle` | `ELECTRICAL TRANSMISSION GRID` (or `ELECTRICAL GRID` with `--include-minor-lines`) | Override the subtitle printed under the country/region name. |
| `--padding` | `0.10` | Fractional padding around the boundary bounds. Lower values zoom in (`0` = tight fit, `-0.05` = crop slightly into the bounds); higher values pull the view out. |
| `--theme` | `paper_grid` | Theme ID from the `themes/` directory. |
| `--list-themes` | - | List available themes and exit. |
| `--include-minor-lines` | off | Also fetch `power=minor_line` features. |
| `--include-cables` / `--no-include-cables` | on | Fetch `power=cable` features (underground/submarine). On by default; pass `--no-include-cables` to skip. |
| `--include-outlying` | off | Keep overseas territories and other polygons far from the main landmass. By default the geocoded boundary is filtered to the mainland (and nearby islands), so posters for countries like the Netherlands or France do not include Aruba, Curaçao, French Guiana, etc. |
| `--paper-size` | - | Named preset, portrait orientation. Overrides `--width`/`--height`. Choices: `a5`, `a4`, `a3`, `a2`, `a1`, `a0`, `letter`, `legal`, `tabloid`. Combine with `--landscape` to flip. |
| `--width` | `297.0` | Poster width in millimeters (default: A3 short side). |
| `--height` | `420.0` | Poster height in millimeters (default: A3 long side). |
| `--landscape` | off | Render in landscape (horizontal) orientation. Swaps width and height if width < height. |
| `--dpi` | `300` | Raster output DPI (applies to PNG output). |
| `--title-size` | auto | Title font size in points. Auto-scaled from poster size by default; set to override. |
| `--tile-size-km` | `200` | Overpass query tile size in kilometers. Use smaller values for very large countries or busy servers. |
| `--format` | `png svg` | Output format(s): any combination of `png`, `svg`, `pdf`. Multiple values are written in one run. |
| `--output` | auto-generated in `posters/` | Output file path. When set, only a single file is written and its format is inferred from the extension. |
| `--crs` | `EPSG:3857` | Projection used for rendering. EPSG:3857 (Pseudo-Mercator) works well for country posters. |
| `--hide-metadata` | off | Do not print segment counts on the poster. |
| `--export-geojson` | off | Also save all transmission lines as a single GeoJSON in WGS84 (EPSG:4326). Pass a path to override the default location in `posters/`. |
| `--verbose-osmnx` | off | Print OSMnx request logs. |

## Output

Generated posters are written to the `posters/` directory by default. Intermediate OSM responses and processed geometries are cached in `cache/` to avoid repeated downloads.


## Gallery

| Poster | Country | Theme |
| --- | --- | --- |
| ![`china_grid_paper_grid_20260512_173256.png`](posters/china_grid_paper_grid_20260512_173256.png) | China | `paper_grid` |
| ![`south_america_grid_japanese_ink_20260514_141831.png`](posters/south_america_grid_japanese_ink_20260514_141831.png) | South America | `japanese_ink` |
| ![`india_grid_japanese_ink_20260512_134242.png`](posters/india_grid_japanese_ink_20260512_134242.png) | India | `japanese_ink` |
| ![`pakistan_grid_electric_midnight_20260512_152527.png`](posters/pakistan_grid_electric_midnight_20260512_152527.png) | Pakistan | `electric_midnight` |
| ![`vietnam_grid_midnight_blue_20260512_153543.png`](posters/vietnam_grid_midnight_blue_20260512_153543.png) | Vietnam | `midnight_blue` |
| ![`california_grid_warm_beige_20260512_155549.png`](posters/california_grid_warm_beige_20260512_155549.png) | California | `warm_beige` |
| ![`mexico_grid_forest_20260512_160112.png`](posters/mexico_grid_forest_20260512_160112.png) | Mexico | `forest` |
| ![`italy_grid_autumn_20260512_162023.png`](posters/italy_grid_autumn_20260512_162023.png) | Italy | `autumn` |
| ![`zambia_grid_sunset_20260512_162627.png`](posters/zambia_grid_sunset_20260512_162627.png) | Zambia | `sunset` |
| ![`marocco_grid_autumn_20260512_165630.png`](posters/marocco_grid_autumn_20260512_165630.png) | Morocco | `autumn` |
| ![`latin_america_grid_emerald_20260516_215030.png`](posters/latin_america_grid_emerald_20260516_215030.png) | Latin America | `emerald` |

### Predefined regions

The `regions/` directory ships with multi-country boundaries that map to common power-system groupings. Pass any of them via `--boundary-geojson` and set `--country` to the title you want printed on the poster:

```bash
python create_grid_poster.py --country "Continental Europe" --boundary-geojson ./regions/continental_europe.geojson --tile-size-km 300
```

| File | Coverage |
| --- | --- |
| `regions/continental_europe.geojson` | Continental Europe Synchronous Area - 31 countries: Albania, Austria, Belgium, Bosnia and Herzegovina, Bulgaria, Croatia, Czech Republic, Estonia, France, Germany, Greece, Hungary, Italy, Kosovo, Latvia, Lithuania, Luxembourg, Moldova, Montenegro, Netherlands, North Macedonia, Poland, Portugal, Romania, Serbia, Slovakia, Slovenia, Spain, Switzerland, Turkey, Ukraine. Includes Moldova and Ukraine (synchronized with CE in March 2022) and the Baltic states (Estonia, Latvia, Lithuania, synchronized in February 2025); excludes the Nordic, GB, Ireland, and Cyprus synchronous areas. |
| `regions/iberia.geojson` | Spain and Portugal. |
| `regions/latin_america.geojson` | Latin America and the Caribbean - 48 entries from Mexico south through Argentina and Chile, plus the Caribbean islands and overseas territories (e.g. Puerto Rico, French Guiana, Guadeloupe). |
| `regions/mediterranean.geojson` | 22 countries bordering the Mediterranean: Albania, Algeria, Bosnia and Herzegovina, Croatia, Cyprus, Egypt, France, Greece, Israel, Italy, Lebanon, Libya, Malta, Monaco, Montenegro, Morocco, Palestine, Slovenia, Spain, Syria, Tunisia, Turkey. |
| `regions/mena.geojson` | Middle East and North Africa - 18 countries: Algeria, Bahrain, Egypt, Iraq, Israel, Jordan, Kuwait, Lebanon, Libya, Morocco, Oman, Palestine, Qatar, Saudi Arabia, Syria, Tunisia, United Arab Emirates, Yemen. |
| `regions/southeast_asia.geojson` | Brunei, Cambodia, Indonesia, Laos, Malaysia, Myanmar, Philippines, Singapore, Thailand, Timor-Leste, Vietnam. |
| `regions/uk_no_shetland.geojson` | United Kingdom with the Shetland Islands trimmed off for tighter framing. |
| `regions/us_canada_mainland.geojson` | Continental United States and Canadian mainland south of 60°N - excludes Alaska, the Canadian Arctic, Hawaii and offshore islands. |
| `regions/wapp.geojson` | West African Power Pool members - Benin, Burkina Faso, Côte d'Ivoire, Gambia, Ghana, Guinea, Guinea-Bissau, Liberia, Mali, Niger, Nigeria, Senegal, Sierra Leone, Togo. |

For ad-hoc areas (a single state, a metro region, a custom polygon), supply your own GeoJSON via `--boundary-geojson`. All polygonal features in the file are dissolved into one boundary.

## Attribution

Map data © OpenStreetMap contributors.

