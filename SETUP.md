# Setup

## 1. Push this repo

The repository name **must** be exactly `sevbanarkn` for GitHub to render
`README.md` on the profile page.

```bash
gh repo create sevbanarkn --public --source . --remote origin --push
```

Or manually: create a public repo named `sevbanarkn` on github.com, then

```bash
git remote add origin https://github.com/sevbanarkn/sevbanarkn.git
git push -u origin main
```

## 2. Add a photo (optional)

Drop a portrait at `assets/avatar.jpg` and push. Until then the avatar panel
renders a placeholder. Square-ish images around 800 px work best.

## 3. Let Actions run

The workflow runs on every push to `main`, daily at 03:17 UTC, and on demand
from the Actions tab. It regenerates `svg/` and commits the result back.

If the first run fails to push, enable
**Settings → Actions → General → Workflow permissions → Read and write**.

## Editing the card

`config.json` holds everything shown on the neofetch panel — rows, title,
ASCII width, whether to strip the photo background, and `"snake"` for the
heatmap animation. No Python edits needed.

## Running locally

Python is not installed on this machine, so the SVGs are only ever built in
CI. To preview locally, install Python 3.11+ and:

```bash
pip install -r requirements.txt
pip install -r requirements-photo.txt   # only if you added a photo
python scripts/build.py
```

Open the files in `svg/` in a browser — animations do not play in most
editors' SVG preview panes.

## Known limitations

- **The heatmap scrapes HTML.** `scripts/contrib_graph.py` reads
  `github.com/users/sevbanarkn/contributions`, which needs no token but breaks
  whenever GitHub reworks that markup. Failures fall back to an empty grid
  instead of breaking the build — if the graph goes blank, that parser is the
  place to look. The GraphQL API with a read-only token is the stable
  alternative.
- **Image caching.** GitHub proxies README images through camo, so a freshly
  committed SVG can take a few minutes to appear.
- **Colour scheme.** An `<img>`-embedded SVG follows the *operating system*
  theme, not the theme selected in GitHub's settings. The panels therefore
  commit to a dark terminal look that reads correctly on both.
- **The snake loops forever**, the other two panels play once per page load.
  Set `"snake": false` in `config.json` to swap the heatmap back to a
  play-once fill-in wave.
