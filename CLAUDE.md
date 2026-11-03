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
| **App / website** (Motor Pool) | Claude Code in this folder | `bsp/app.py`, `bsp/web/`, `bsp/cards.py`, `bsp/art.py`, `bsp/approvals.py`, `bsp/signing.py`, `README.md` |

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
pip install -r requirements.txt
python -m playwright install chromium     # PDF engine, once
python -m bsp.setup_data                  # MegaMek data + sprites + caches
python -m bsp.app                         # Motor Pool on http://127.0.0.1:8640
python -m pytest tests
```

`official.tsv` (the private export of Catalyst's official cards) sits in this
folder and is git-ignored; never commit it or print its contents into public
files. The app picks it up automatically when Settings leaves the path blank.

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
  Emplacement, or listed under `generic:` in card_links.yaml) are listed as
  official-only entries (ids start with "g"): no calculated card, tweak or
  Differences until the model covers them.
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
  Will still needs to run `python -m bsp.signing init --name Launchpad` and
  `sign-existing`, then commit `data/trusted_keys.yaml` and `data/approvals.yaml`.
- Tweak → live re-cost → optional cost override → approve, recording changes.
- "Send tweaks for approval": mailto to the Settings address
  (williamtbecker@gmail.com for now; Will wants a dedicated address before
  wider distribution) with a readable summary + `MOTORPOOL:` import code;
  "Import proposals" reads it back.
- Working title **Motor Pool** (may change once infantry/battle armor arrive).

- **Tester build** (`python tools/build.py` → `dist/MotorPool-vX.Y.Z.zip`):
  PyInstaller one-folder exe, waitress on a free 127.0.0.1 port, console
  window = quit switch. Distribution mode (`bsp/dist.py`; frozen or
  `MOTORPOOL_DIST=1`) reads only the bundled snapshot, inlines local fonts,
  prints PDFs with the installed Edge, locks the data paths in Settings and
  never writes into the bundle. The zip includes the private official cards,
  so it's shared privately only: no public GitHub Release. Dev mode
  (`python -m bsp.app`) is unchanged.

## App to-do / ideas

- Bundle the fonts (Oswald, Barlow, Barlow Condensed — OFL) so PDFs look
  right offline.
- A double-click `Motor Pool.bat` launcher (git pull + start).
- Tester build: include infantry/BA/emplacement data once the app shows them;
  a dedicated feedback email address; maybe a calculated-only public build.
- Infantry, battle armor and emplacement cards once the model supports them.

## Licensing

Code GPL v3 or later (keep the header comment on new files). MegaMek data
and sprites are CC BY-NC-SA 4.0, downloaded at run time, never committed.
BattleTech is a Topps trademark; cards are unofficial fan content.
