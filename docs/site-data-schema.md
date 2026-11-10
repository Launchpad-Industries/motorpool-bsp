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
  "units": [ /* Unit */ ]
}
```

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
