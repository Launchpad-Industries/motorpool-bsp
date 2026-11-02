# BSP Card Generator — Motor Pool

A local tool for making BattleTech **Battlefield Support asset cards** for
units that don't have official cards, using each unit's full Total Warfare
statistics as the starting point.

It reads unit data from [MegaMek](https://megamek.org/), derives an asset
spec (MP, TMM, range, Skill, damage, Destroy Check, Threshold, specials and
BSP cost), records where every spec came from, and prints cards eight to a
page.

> **Status:** early development. The rules for turning a unit into an asset
> spec are still being worked out against the official cards.

## How specs are labelled

Every asset carries a provenance label, which also prints on the card:

| Label | Meaning |
|---|---|
| **Official** | As printed by Catalyst Game Labs. Never overwritten. |
| **Approved** | Calculated (and possibly tweaked), then approved by a named person. Approvals signed with a trusted key print as "Source: Approved-*name*"; others print as "Source: Unverified-*name*". The approved values are kept; if a later rule change disagrees, the unit is flagged as drifted. |
| **Calculated** | Calculated by this tool and not yet reviewed. |

For official units the app can show the printed values, the calculated
values, or the differences between them, since printed cards occasionally
contain mistakes.

Specs use MegaMek's `.bfs` asset format, extended with provenance fields.

## Getting started

Needs Python 3.11+ and git.

```
pip install -r requirements.txt
python -m playwright install chromium          # once: the engine behind "Make PDF"
python -m bsp.setup_data                      # fetch MegaMek data + unit sprites, build caches
python -m bsp.app                             # start Motor Pool; opens in your browser
```

## Motor Pool (the app)

`python -m bsp.app` starts a small server on this computer only
(http://127.0.0.1:8640) and opens it in your browser.

- **Search** every vehicle and VTOL in MegaMek's data (filters for movement,
  source and tech base). Units with an official card show it; the rest show
  the approved or calculated card. "≠" marks official cards where the
  calculation differs; "drift" marks approvals the rules have since moved away from.
- **Force list** on the left: add assets with **+**, pick Regular or Veteran,
  Official or Calculated (where both exist) and quantity. BSP and BV-equivalent
  totals update as you go.
- **Make PDF**: an optional summary page, then cards 2 × 4 per US Letter
  page, ready to cut. "Print view" opens the same pages in the browser instead.
- **Card detail**: Official / Approved / Calculated / Differences views, a
  Regular / Veteran toggle, **Tweak…** (edit any stat; the cost re-calculates
  live; tick "Override cost" to set it by hand) and **Approve**.
- **Send tweaks for approval**: collects tweaks into a pre-filled email to the
  address in Settings (with a `MOTORPOOL:` import code). **Import proposals**
  reads that code back so the approver can review, adjust and approve.

Settings (name, approval email, data folders, your images folder) live in
`~/.motorpool/settings.json` and in the app's Settings dialog. Card images
come from your images folder first (one file per chassis, e.g.
`drillson.jpg`, `scimitar.png`; `drillson-streak.png` overrides one variant),
then MegaMek's top-down unit sprites.

### Google Sheet pull and push (offline, from the command line)

Motor Pool runs only from local files and never contacts your Google Sheet.
Moving data to or from the Sheet is a separate command you run when you
want, through a small Apps Script in the Sheet. Setup, once:

1. In the Sheet: **Extensions → Apps Script**. Replace the editor's contents
   with `bsp/sheet_sync.gs`, change `SECRET` to a long phrase of your own, and
   save.
2. **Deploy → New deployment →** type **Web app**, Execute as **Me**, Who has
   access **Anyone**. Authorise it, then copy the web app URL (ends `/exec`).
   The secret is what keeps others out; the Sheet itself stays private.
3. Run `python -m bsp.sheet setup` and give it the URL, the secret and the
   official cards tab name. They're saved in `~/.motorpool/sheet.json`, apart
   from the app's settings. That tab needs the columns `name variant type
   costR costV skill mp mtype tmm range dmg check thr specials` (the same
   layout as `official.tsv`); pull refuses a tab without them.

```
python -m bsp.sheet tabs    # check the link: lists the Sheet's tabs
python -m bsp.sheet pull    # official cards tab -> official.tsv (old one kept as official.tsv.bak)
python -m bsp.sheet push    # every calculated vehicle -> new tab "Calculated <date>"
```

Restart Motor Pool after a pull to load the new cards. Push never
overwrites: it always makes a new tab (adding " (2)" if the name is taken).
Approved cards go up with their approved values and label. If you edit
`SECRET` or the script later, use **Deploy → Manage deployments → Edit → New
version** so the URL stays the same.

### Signed approvals (owner setup, once)

Only approvals signed with a trusted key show as verified, so a copy of the
app on someone else's computer can't produce "Approved-Launchpad".

```
python -m bsp.signing init --name Launchpad   # creates ~/.motorpool/signing_key (keep private)
python -m bsp.signing sign-existing           # sign earlier approvals made as Launchpad
git add data/trusted_keys.yaml data/approvals.yaml && git commit -m "Trust Launchpad's key"
```

Approvals made on a machine without the key are saved in
`~/.motorpool/approvals.yaml` under that person's name, unverified.

## Command-line tools

```
python -m bsp.generate --mm-data mm-data/data/mekfiles --out specs
python -m pytest tests
```

`generate` writes one `.bfs` spec per combat vehicle plus `specs/index.csv`.
Add `--name Behemoth` to generate only matching units.

`python -m bsp.listing --mm-data mm-data/data/mekfiles --out asset-specs.csv --official cards.tsv`
writes one spreadsheet row per asset (chassis and variant split, range in three
columns, damage as `5dx4`, with a Source column). The official TSV is optional
and stays on your machine.

To approve calculated specs:

```
python -m bsp.approvals --mm-data mm-data/data/mekfiles --by Launchpad "Peregrine Attack VTOL"
```

## Layout

| Path | Contents |
|---|---|
| `bsp/megamek.py` | Reads MegaMek `.blk` unit files |
| `bsp/weapons.py` | Weapon stats from MegaMek's weapon definitions |
| `bsp/match.py` | Links asset cards to MegaMek units |
| `bsp/derive.py` | First-pass spec: MP, TMM, range, damage, IF, Check, Threshold |
| `bsp/cost.py` | BSP cost from a spec's card stats |
| `bsp/bv.py` | Total Warfare vehicle BV (TechManual pp. 307-308), for reference |
| `bsp/bfs.py` | Reads and writes `.bfs` specs with provenance fields |
| `bsp/generate.py` | Command line: MegaMek units to `.bfs` specs |
| `bsp/listing.py` | Spreadsheet list: official rows, calculated rows where they differ |
| `bsp/report.py` | Official vs calculated comparison page (private use) |
| `bsp/approvals.py` | Records approvals (who, when, approved values, tweaks) and flags drift |
| `bsp/signing.py` | Ed25519 signing keys; verifies approvals against `data/trusted_keys.yaml` |
| `bsp/cards.py` | Printable cards and the summary page (HTML) |
| `bsp/art.py` | Card images: your images folder, then MegaMek sprites |
| `bsp/app.py`, `bsp/web/` | Motor Pool, the local browser app |
| `bsp/sheet.py`, `bsp/sheet_sync.gs` | Command-line pull/push with the Google Sheet (Apps Script link; not used by the app) |
| `data/card_links.yaml` | Manual card-to-unit links |
| `data/approvals.yaml` | Approved calculated specs, e.g. "Autogenerated-Approved by Launchpad" |

The reasoning behind every rule and cost is in [docs/cost-rationale.md](docs/cost-rationale.md).

All tunable constants are in `RULES` (`derive.py`) and `COST_RULES`
(`cost.py`).

## Data and licensing

**Code:** GNU General Public License v3 or later. See [LICENSE](LICENSE).

**Unit data and sprites:** downloaded at run time from
[MegaMek Data](https://github.com/MegaMek/mm-data), (C) The MegaMek Team,
licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
It is not stored in this repository. Asset specs and cards this tool
generates are derived from that data, so if you share them they fall under
the same license: credit MegaMek, non-commercial use only, share alike.

**Official asset specs** are not stored here either. They are read at run
time from the owner's own spreadsheet.

## Unofficial fan content

This is an unofficial, non-commercial fan project. It is not affiliated
with, endorsed by, or sponsored by The Topps Company, Inc., Catalyst Game
Labs, or InMediaRes Productions, LLC.

BattleTech, MechWarrior, BattleMech, 'Mech and related names are registered
trademarks and/or trademarks of The Topps Company, Inc. Catalyst Game Labs
and the Catalyst Game Labs logo are trademarks of InMediaRes Productions,
LLC. Cards produced by this tool are not official cards.
