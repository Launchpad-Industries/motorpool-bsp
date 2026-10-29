# BSP Card Generator

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
| **Approved** | Calculated or hand-tuned, then approved by a named person. History is kept. |
| **Auto** | Calculated by this tool and not yet reviewed. |

For official units the app can show the printed values, the calculated
values, or the differences between them, since printed cards occasionally
contain mistakes.

Specs use MegaMek's `.bfs` asset format, extended with provenance fields.

## Getting started

Needs Python 3.11+ and git.

```
pip install pyyaml numpy scipy pytest
python -m bsp.setup_data                      # fetch MegaMek data, build caches
python -m bsp.generate --mm-data mm-data/data/mekfiles --out specs
python -m pytest tests
```

`generate` writes one `.bfs` spec per combat vehicle plus `specs/index.csv`.
Add `--name Behemoth` to generate only matching units.

`python -m bsp.listing --mm-data mm-data/data/mekfiles --out asset-specs.csv --official cards.tsv`
writes one spreadsheet row per asset (chassis and variant split, range in three
columns, damage as `5dx4`, with a Source column). The official TSV is optional
and stays on your machine.

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
| `data/card_links.yaml` | Manual card-to-unit links |

The reasoning behind every rule and cost is in [docs/cost-rationale.md](docs/cost-rationale.md).

All tunable constants are in `RULES` (`derive.py`) and `COST_RULES`
(`cost.py`).

## Data and licensing

**Code:** GNU General Public License v3 or later. See [LICENSE](LICENSE).

**Unit data:** downloaded at run time from
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
