# CLAUDE.md — BSP Card Generator / Motor Pool

Context for Claude Code sessions in this repository. Owner: Will
(Discord handle **Launchpad**, the name his approvals carry).

## What this is

A tool that turns MegaMek Total Warfare unit data into BattleTech
**Battlefield Support (BSP) asset cards**, plus **Motor Pool**, a local
browser app to search units, build a force, preview cards, tweak and approve
calculated cards, and print a PDF (8 cards per US Letter page).

Work is split between two places:

| Area | Where it's worked on | Files |
|---|---|---|
| **Translation model** (how TW stats become BSP stats and cost) | Will's claude.ai project chat "Battletech BSP Generator" | `bsp/derive.py` (`RULES`), `bsp/cost.py` (`COST_RULES`), `bsp/weapons.py`, `docs/cost-rationale.md`, `data/card_links.yaml` |
| **App / website** (Motor Pool) | Claude Code in this folder | `bsp/app.py`, `bsp/web/`, `bsp/cards.py`, `bsp/strikes.py`, `bsp/art.py`, `bsp/approvals.py`, `bsp/signing.py`, `README.md` |

Don't change the model files from an app session without asking Will: rule
changes are decided with him one at a time and recorded, with reasons, in
`docs/cost-rationale.md`. If the app needs something from the model, add a
small, clearly named function rather than changing rules. Always `git pull`
before starting; both places push to `origin main`.

## Working with Will

- **Ask questions one at a time, numbered** (Question 1, 2, …), and offer
  options with a recommendation when that helps. He prefers to be asked
  before big changes, and is happy for small, obvious fixes to just be done.
- Keep explanations plain; he's comfortable with git basics and Python via
  an Anaconda Prompt on Windows (Surface Pro, display scaling ~150%).
- Commit as `William Becker <williamtbecker@gmail.com>` and push to
  `origin main` when a change is done and tested.

## Running things (Windows, Anaconda Prompt, from this folder)

```
conda activate bsp                        # Will's environment for this project
pip install -r requirements.txt
python -m playwright install chromium     # PDF engine, once
python -m bsp.setup_data                  # MegaMek data + sprites + caches
python -m bsp.app                         # Motor Pool on http://127.0.0.1:8640
python -m pytest tests
```

Make PDF uses Playwright in dev mode and falls back to the installed Microsoft
Edge if Playwright is missing or fails (the tester build always uses Edge).

`official.tsv` (the export of the official cards from Will's Sheet, which
stays the master copy) sits in this folder and is committed to git, as is
`bsp-options.tsv`; after a pull, commit them to share the new values. Distributing
the card stats in builds is fine: they're game statistics, shared the way
MegaMek, MekBay and other fan tools do. Never include Catalyst artwork, logos
or rules text. The app picks it up automatically when Settings leaves the path
blank.

## Motor Pool design decisions (agreed with Will)

- MekBay-style layout: force list left, search/results middle, card detail
  right. Clicking a result or a force entry opens its card preview.
- Cards: 3.5" × 2.5" landscape, 2 × 4 per page with cut lines; Alpha-Strike-
  printout feel **without Catalyst logos or art**. Regular on the left,
  Veteran in parentheses on the right, emphasis on the grade in play, a
  REGULAR/VETERAN chip; degradation pips from the full Check down to 2;
  footer "Source: Official Catalyst BSP" (solid) / "Approved-<name>" (grey) /
  "Unverified-<name>" (dotted) / "Calculated" (dashed).
- Generic official cards (official.tsv rows of type Infantry, Battle Armor,
  Emplacement, or listed under `generic:` in card_links.yaml, unless linked to
  a unit there) are listed as official-only entries (ids start with "g"): no
  calculated card, tweak or Differences until the model covers them.
- Battle armor (model: `derive_battle_armor`): listed as ordinary units.
  Only squads in `data/battle_armor_squads.yaml` (`bsp/squads.py`), built by
  `tools/battle_armor_list.py`: Will chose squads MegaMek's force generator gives
  to a faction, at standard sizes (Clan 5, Inner Sphere 4 and 6; a design available
  only at another size keeps it). Refreshed MegaMek data doesn't change the list
  until that script is rerun. The four official BA cards are linked to one suit each in
  card_links.yaml, so those suits show the official card by default.
- Strike cards (`bsp/strikes.py`, ids start with "s"): air, artillery and
  minefield options from `bsp-options.tsv` (from the Sheet's "BSP Options"
  tab). Minefield titles get "Minefield" added in the app. Same frame as unit cards, no Veteran grade: the chip says STRIKE /
  MINEFIELD / NOT AN ATTACK, the side shows a radius, scatter, line or single
  hex diagram, and the card has write-on boxes. Footer "Source: BattleTech Core
  Rulebook". Own section in search and the force list; printed after the units;
  BSP counts toward the force total. Effect text must stay in our own words.
- Official card always used when one exists; Official/Calculated switch per
  force entry; Differences view in the detail panel.
- Optional summary page: asset, type, grade, skill, BSP cost, BV equivalent
  (BSP × 20), tons, source, totals.
- Art: Will's images folder (one file per chassis, e.g. `drillson.jpg`,
  variant override `drillson-streak.png`), then MegaMek top-down sprites
  (CC BY-NC-SA, credited), else none. Don't use MekBay/MUL fluff art
  (unclear licensing).
- Google Sheet: **not part of the app**. Motor Pool reads only local files
  and has no Sheet buttons, settings or routes. `python -m bsp.sheet
  pull|push` (`bsp/sheet.py`, own config in `~/.motorpool/sheet.json`, via
  the Apps Script `bsp/sheet_sync.gs`) runs separately: pull writes the
  official tab to `official.tsv`, push sends all calculated vehicles to a new
  tab. The Sheet stays master for official cards.
- Approvals are **signed** (Ed25519, `bsp/signing.py`): Will's private key
  stays in `~/.motorpool`; trusted public keys in `data/trusted_keys.yaml`.
  Others' approvals are saved locally under their own name, unverified.
- Tweak → live re-cost → optional cost override → approve, recording changes.
- "Send tweaks for approval": mailto to the Settings address
  (default motorpool.support@gmail.com, the project's support and feedback
  address since 2026-11-10; saved settings with the old default move to it) with a readable summary + `MOTORPOOL:` import code;
  "Import proposals" in Settings reads it back.
- **About** button beside Settings shows `bsp/web/about.html`: a plain-language
  description of the model and costing, in our own words, plus credits and
  notices. When a rule changes, in either place, update it and its "Last updated"
  date. `tests/test_about.py` checks the worked example against the cost formula.
  No GitHub link while the repository is private.
- Working title **Motor Pool** (may change once infantry/battle armor arrive).
  Tagline: "Unofficial fan-made BattleTech force builder for battlefield support".

- **Tester build** (`python tools/build.py` → `dist/MotorPool-vX.Y.Z.zip`):
  PyInstaller one-folder exe, waitress on a free 127.0.0.1 port, console
  window = quit switch. Distribution mode (`bsp/dist.py`; frozen or
  `MOTORPOOL_DIST=1`) reads only the bundled snapshot, inlines local fonts,
  prints PDFs with the installed Edge, locks the data paths in Settings and
  never writes into the bundle. The zip includes the official card stats
  (fine to distribute; no Catalyst art or logos). No GitHub Release workflow
  yet. Dev mode
  (`python -m bsp.app`) is unchanged.

- **Public site export**: `python -m bsp.export_site [--no-official]` writes
  `site/data/units.json` (schema: `docs/site-data-schema.md`) from the same
  catalog Motor Pool shows, official values by default, and copies the MegaMek
  sprites it uses into `site/img/units/` (never the owner's images folder).
  Strike cards go in their own `strikes` list (Will, 2026-11-09), with their
  hex diagrams as SVG files in `site/img/strikes/`; the site prints them after
  the units. Every card is **pre-drawn** by Motor Pool's own card code into
  `site/cards/` (one page per card and grade, styles in `cards/card.css`), so
  the site's cards match the app's exactly (Will, 2026-11-10). The site's own
  JS only shows and prints those pages; don't draw cards in JS. Will is still
  considering making a JavaScript card renderer the master later.
- **The website is Motor Pool's own page** (`bsp/web/`) in **website mode**
  (Will, 2026-11-10): the exporter copies `bsp/web/` into `site/` with
  `window.MOTORPOOL_STATIC` set; `app.js` then reads `site/data/motorpool.json`
  and `data/unit/<id>.json` instead of `/api/...`, shows the pre-drawn cards,
  prints via a new tab (summary page + cards), and hides elements marked
  `server-only` (tweak, approve, settings except theme, proposals). Edit
  `bsp/web/`, never the copies in `site/`; any new server-only control needs
  the `server-only` class, and any new `/api/` read needs a static answer in
  `staticApi()` plus exported data.

## App to-do / ideas

- Bundle the fonts (Oswald, Barlow, Barlow Condensed — OFL) so PDFs look
  right offline.
- A double-click `Motor Pool.bat` launcher (git pull + start).
- Tester build: include infantry/emplacement data once the app shows them;
  maybe a calculated-only public build.
- Infantry and emplacement cards once the model supports them.

## Licensing

Code GPL v3 or later (keep the header comment on new files). MegaMek data
and sprites are CC BY-NC-SA 4.0, downloaded at run time, never committed,
except the sprites the public site uses (`site/img/units/`, credited; Will
agreed 2026-11-09).
BattleTech is a Topps trademark; cards are unofficial fan content.
