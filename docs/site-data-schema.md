# Motor Pool public site — data export schema (v1)

The public site is a static viewer. It reads exactly one file, `site/data/units.json`,
written by the local workbench. Nothing on the site talks to Google Sheets, MegaMek,
or a server.

```
Local workbench (python -m bsp.app)          Public site (GitHub Pages)
  MegaMek data, Sheets, approvals   ──export──▶  site/data/units.json  ──▶  index.html + app.js
```

## Official values

Official specs may be stored in the repo and published on the site (decision changed
2026-11-09). The exporter **includes official values by default**: a unit with an official
card is exported with its printed values and `provenance: "official"`, matching Motor Pool's
rule that printing uses the official card whenever one exists. A `--no-official` flag
falls back to calculated values with `hasOfficialCard: true`, in case that's ever needed.

## Top level

```json
{
  "schemaVersion": 1,
  "generatedOn": "2026-11-09T22:00:00-05:00",
  "generator": "bsp-card-generator 0.x (git abc1234)",
  "disclaimer": "Unofficial fan-made content. BattleTech is a registered trademark of ...",
  "credits": ["Unit data: MegaMek mm-data (CC BY-NC-SA 4.0)", "..."],
  "units": [ /* Unit */ ],
  "strikes": [ /* Strike */ ]
}
```

`strikes` may be missing from older files; treat that as an empty list.

## Unit

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable slug, e.g. `"scorpion-lrm"`. Used in URLs and saved force lists, so never change it once published. |
| `name` | string | Display name as on the card, e.g. `"Scorpion Light Tank (LRM)"`. |
| `type` | string | `Vehicle`, `VTOL`, `WiGE`, `Infantry`, `Battle Armor`, `Emplacement`, `Artillery`, `Support Vehicle`. |
| `motive` | string? | `Tracked`, `Wheeled`, `Hover`, `VTOL`, … |
| `tonnage` | number? | |
| `techBase` | string? | `IS`, `Clan`, `Mixed`. |
| `introYear` | number? | |
| `mulId` | number? | Master Unit List id (links out to MUL). |
| `provenance` | string | `official` \| `approved` \| `calculated`. |
| `approvedBy` | string? | Approver name, e.g. `"Launchpad"`. Only for `approved`. |
| `approvedOn` | string? | ISO date. |
| `verified` | bool? | Approval signature checked against a trusted key. Unverified approvals show as `Unverified-<name>`. |
| `hasOfficialCard` | bool? | True when an official card exists but its values are not published. |
| `spec` | Spec | The card values. |
| `cost` | `{ "regular": number, "veteran": number \| null }` | `veteran: null` = no Veteran version (artillery). |
| `art` | `{ "src": string, "credit": string }?` | Path relative to `site/`, e.g. `"img/units/scorpion.png"`. |
| `cards` | `{ "regular": string, "veteran": string \| null }` | Pre-drawn card pages relative to `site/`, e.g. `"cards/scorpion-light-tank-lrm.html"` and `"…-vet.html"`; `veteran: null` when there's no Veteran version. See "Card pages" below. |
| `notes` | string? | Short note shown on the detail panel, not on the card. |

## Spec

| Field | Type | Example |
|---|---|---|
| `move` | string | `"10h"`, `"5t"`, `"8v"`. Printed as-is. |
| `tmm` | number | `4` |
| `skill` | `{ "regular": number, "veteran": number \| null }` | `{ "regular": 6, "veteran": 5 }` |
| `range` | `[number, number, number]` | `[5, 10, 15]` |
| `damage` | string | `"6dx3"`, `"4x3"` (exact card notation) |
| `indirect` | number? | IF value; omit or `0` for none. |
| `check` | number | Destroy Check |
| `threshold` | number | |
| `specials` | string[] | `["ECM", "TAG", "IF1"]` — keywords only, as on the card. |

## Strike

Strike cards (air strikes, bombing, air cover, artillery, smoke, minefields) from
`bsp-options.tsv`. They have no Veteran grade and no provenance: they're always the
Core Rulebook options. Kept in their own list (decided 2026-11-09) because they share
none of a unit's stats.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `strike-` + name slug, e.g. `"strike-light-air-strike"`, so it never clashes with a unit id. Never change once published. |
| `name` | string | As on the card; minefields end in "Minefield", e.g. `"Light Density Minefield"`. |
| `category` | string | `Air`, `Artillery`, `Minefield`. |
| `support` | string? | Card subtitle, e.g. `"Offensive Aerospace Support"`. |
| `chip` | string | `STRIKE`, `MINEFIELD` or `NOT AN ATTACK`. |
| `cost` | number | BSP. Counts toward the force total. |
| `per` | string? | `"per hex"` when the cost is per hex (minefields). |
| `tn` | number? | Target number (printed as `5+`). |
| `groups` | string? | Damage groups of 5: `"3"`, or by distance from the target `"5/3/1"`; `"none"` for smoke. |
| `attackType` | string? | `AE`, `DE`, `N/A`, `Smoke`. |
| `scatter` | string? | e.g. `"1D6"`. |
| `radius` | number? | Hexes around the target. |
| `needs` | string? | e.g. `"TAG"`. |
| `cancels` | `[{ "strike": string, "tn": number }]`? | Air cover: the roll needed to cancel each strike. |
| `effect` | string | Rules summary, in our own words. |
| `rulesRef` | string? | e.g. `"Core Rulebook p. 154"`. |
| `writeOn` | string? | `target` (target hex, turn and Used boxes) or `hex` (hex box and a groups-left track); omitted = just a Used box. |
| `diagrams` | `[{ "src": string, "caption": string }]` | SVG files relative to `site/`, e.g. `"img/strikes/long-tom-1.svg"`; each sets its own printed width. |
| `notes` | string? | Detail panel only, never printed. |
| `source` | string | `"BattleTech Core Rulebook"` (card footer). |
| `card` | string | Pre-drawn card page relative to `site/`, e.g. `"cards/strike-long-tom.html"`. |

## Card pages

So the site's cards look exactly like Motor Pool's (decided 2026-11-10), the exporter
draws every card with Motor Pool's own card code (`bsp/cards.py` `card_html`, strike
cards `bsp/strikes.py`) and saves each as a small page in `site/cards/`: Motor Pool's
preview page (`card_frame`, which scales the card to fit its frame) with the shared
styles in `site/cards/card.css`. Images point at `../img/units/…`. The site shows a page
in an `<iframe>` (3.5 : 2.5) and prints by taking each page's `.one` contents into
Motor Pool's print layout (`.page` > `.sheet` > `.cell`, styled by `card.css`).
The Spec values above stay in `units.json` for search, filters and totals.

## Exporter (to build in Claude Code)

Prompt to use in the local code folder:

> Official specs are now allowed in the repo: move the official card specs from the private
> TSV into a tracked data file (e.g. `data/official_cards.yaml` or `.bfs` files) and update the
> README note that said they're never stored.
> Then add `bsp/export_site.py` (`python -m bsp.export_site [--no-official] [--out site/data/units.json]`).
> It should build the same unit list Motor Pool shows (official + approved + calculated, using
> derive.py / cost.py / approvals.py), and write JSON matching `docs/site-data-schema.md`.
> Default: official units use their printed values; `--no-official` falls back to calculated
> with `hasOfficialCard: true`.
> Copy any art the owner has rights to into `site/img/units/` (MegaMek sprites with credit; never MekBay images).
> Sort units by name. Add a test that the output validates against the schema field list.
