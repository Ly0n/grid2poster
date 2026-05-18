# grid2poster — gh-pages gallery

This is an **orphan branch** that hosts the public poster gallery for
[grid2poster](https://github.com/Ly0n/grid2poster). It has no shared history
with `main`, so cloning `main` does not pull these images.

Once GitHub Pages is enabled on this branch, the gallery is served at:

    https://<your-user>.github.io/grid2poster/

## Layout

```
.
├── index.html          # gallery page (vanilla HTML/CSS/JS, no build step)
├── style.css
├── app.js
├── build_manifest.py   # regenerates posters/manifest.json from the files
├── posters/
│   ├── manifest.json   # consumed by app.js
│   └── *.png, *.svg    # the posters themselves
└── .nojekyll           # disable Jekyll processing on GitHub Pages
```

## Updating the gallery

1. Generate a new poster on `main`:
   ```bash
   python create_grid_poster.py --country Spain --theme paper_grid
   ```
2. Switch to this branch (use a worktree to avoid disturbing `main`):
   ```bash
   git worktree add ../grid2poster-ghpages gh-pages
   ```
3. Copy the new poster file(s) into `posters/` here, regenerate the manifest,
   commit, and push:
   ```bash
   cp ../grid2poster/posters/spain_grid_*.png posters/
   python build_manifest.py
   git add posters/ && git commit -m "Add Spain (paper_grid)"
   git push origin gh-pages
   ```

## Filename convention

Posters follow `{region}_grid_{theme}_{YYYYMMDD}_{HHMMSS}.{ext}`. The manifest
builder splits on the first `_grid_` to separate region from theme — both can
contain underscores.

## Enabling GitHub Pages

In the repo settings on GitHub:

- **Settings → Pages → Source**: *Deploy from a branch*
- **Branch**: `gh-pages` · folder `/ (root)` · Save

Posters are CC BY 4.0; map data © OpenStreetMap contributors.
