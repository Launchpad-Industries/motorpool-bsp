# Why things cost what they do

How the generator turns a MegaMek unit into an asset spec and a BSP cost,
and the reasoning behind each number. Values live in `RULES`
(`bsp/derive.py`) and `COST_RULES` (`bsp/cost.py`); this document explains
them. Update it whenever a rule changes.

Sources: TechManual Battle Value rules (pp. 302–318), the BattleTech core
rulebook's Battlefield Support chapter, MegaMek's equipment data, and the
official asset cards (used to fit and check values; not stored here).

## Ground rules

- **Asset cost is not Total Warfare BV ÷ 20.** Whole-unit BV is a poor
  predictor of card cost. Comparing the BV of individual components (one
  weapon, one launcher, one armor type) is fine.
- **Price the card, not the unit.** Cost comes from the card's own stats:
  damage, range, speed, Check, TMM and specials.
- **Official cards win ties, but not blindly.** Values are fitted to the
  official cards. Where a card looks like an early outlier, the rule follows
  the newer cards and the outlier is recorded below.

## The cost formula

```
Regular = round( base + (offense + defense) / 20 + flat specials )
Veteran = round( unrounded Regular x 1.15 )
```

| Part | Value | Why |
|---|---|---|
| Base | 8.0 points | Every asset has a floor; cheap units cost ~10–13 regardless of stats. Fitted. |
| Offense | 9.6 × speed factor(card MP) × damage × (long range ÷ 9)^0.6 × specials × 1.1^(6 − Skill) | BV-style: damage × range × speed, as in TechManual weapon BV. Scale and range exponent fitted on 110 official vehicles. |
| Defense | 0.6 × Check value × (1 + TMM ÷ 10) | TMM uses the TechManual defensive factor. Check value: Check 7 = 75, +75 per step above, ×2/3 per step below (Will's rule; the forum scale fits equally well). |
| Veteran | × 1.15 on the unrounded cost | Fits 126 of 127 official cards, Clan Skill 5 and 4 included. |

Constants are fitted, then rounded to one decimal place, as the TechManual
does (Veteran ×1.15 and ECM3 3.5 stay as they are: both are exact rules).
Accuracy on 117 official vehicles priced from their printed stats: 2.36
points average error, 83 within 2 points (2.30 before rounding).

## Card stats

| Stat | Rule | Why |
|---|---|---|
| MP | MegaMek cruise MP | Matches the cards except the Fox (confirmed real). |
| TMM | Standard TW movement table on card MP; +1 VTOL, +1 WiGE, +1 vehicle stealth | 107/118 official vehicles. |
| Skill | 6; 5 for Clan front-line designs; −1 with a targeting computer; 8 for artillery | 114/116. Clan versions of Inner Sphere designs stay at 6, as on the cards. |
| Range | Long range of the weapon type with the most BV (the unit's "character" weapon), as a standard bracket | 93/110 official ranges (the alternative, maximising damage × range, gets 87 and picks the Bulldog (Plasma)'s Streaks over its plasma rifle). |
| Damage | Average damage of weapons reaching the bracket's medium range; cluster weapons ×0.75 | Grouping is mostly judgment on the cards: total within 15% on 67/115. |
| Threshold | 8 at 75+ tons, else 5 | 117/118 (Von Luckner at 75 t is 8). |
| Check | Armor BV = (armor × 2.5 + structure × 1.5) × armor mod × motive mod, then cutoffs | 111/118. Motive: hover/WiGE 0.55, VTOL 0.7, wheeled 0.8, tracked 0.9. Hover is lower than the TechManual's 0.7 because hover cards are consistently less durable. Cutoffs: 6 ≥ 80, 7 ≥ 128, 8 ≥ 199, 9 ≥ 353, 10 ≥ 395, 11 ≥ 559, 12 ≥ 754. |

Armor modifiers for Check:

| Armor | Mod | Why |
|---|---|---|
| Hardened | ×2.0 | TacOps/MegaMek value; fits the cards. |
| Ferro-lamellor | ×1.4 | Removes 1 point per 5 (or fraction) of each hit: about +25% against 5-point groups, more against small hits. 1.4 is the least that keeps both Eurus cards at Check 11. No keyword, no extra cost. |
| Reactive, reflective, ballistic-reinforced | ×1.0 for Check | Their effect is the keyword (half damage from some weapon types). Putting ×1.5 into Check pushed two official cards a Check level too high. |

## Specials

| Special | When the generator adds it | Cost | Why |
|---|---|---|---|
| AI | Anti-infantry weapons give at least half of the main attack. Anti-infantry = MegaMek burst-fire weapons (machine guns, flamers, small/micro/ER small/X-pulse small pulse lasers, AP Gauss) plus all plasma weapons. Standard and ER small lasers don't count. | Offense ×1.05 (set by hand) | Matches the Hover APCs. Tracked APC and Coolant Trucks are known exceptions. The fitted value (×0.44) was meaningless: only 4 cards. |
| AMS | Anti-missile system fitted | Defense ×1.15 | Works like a special armor against missiles only (−4 on the cluster roll), so it is worth more on tougher units. TechManual counts AMS as defensive equipment (32 BV + ammo). The official AMS cards value it at under a point; ×1.15 is the most they support. |
| APC X | Troop space: under 4 t = APC1; each full 4 t = 2 points (a battle armor squad) | 1.1 points × X × durability; durability = √(defensive BV ÷ defensive BV at Check 7, TMM 0) | Carrying troops isn't firepower, so it isn't an offense multiplier. Tougher and faster carriers get troops where they need to go and keep them alive (Will), so the defensive BV equivalent (Check, TMM, special armor) scales it. Square root so a Check 11 carrier pays about twice a Check 7 one, not five times. APC2 costs about 1.5 at Check 5, 2.4 at Check 7, 4.2 at Check 9, 5.4 at Check 11. 1.1 fitted on the 7 official APC cards (all Check 5–7, so they can't test the scaling). Derivation matches all 6 official APC vehicles; Savior (3 t, APC2) is an exception. Replaced a fitted ×1.13 offense multiplier. |
| Arrow X | One per Arrow IV launcher | 38 points each | Scaled from the Long Tom by one-shot Strike cost (Arrow IV Strike 16 vs Long Tom 24). The Pilum fits; the early Arrow IV Carrier card (58) is a known outlier, likely due for an update. |
| Artillery (type) X | One per artillery piece | Long Tom 57, Sniper 38, Thumper 29 | Long Tom from the two Mobile Long Tom cards; others scaled by Strike cost (24 / 16 / 12). Artillery gets Skill 8 and no Veteran cost (the rules forbid Skill upgrades). |
| Arrow and artillery units keep other weapons | Regular attack from the remaining weapons | Priced normally, on top | The rules allow either attack each turn; Will would include them. Official cards omit them. |
| BRA, RCA, RFA | From MegaMek armor type | Defense ×1.5 | TacOps/MegaMek armor BV multiplier. Matches the Savannah (Reflective) +1 point. |
| Commander | C3 Master or C3 Boosted Master (not C3i or slaves), or 5+ tons of communications equipment | +15 points flat | Matches Catalyst: the Skulker/Skulker C3M and Mobile HQ/Browning comparisons all imply 15–17. Will thinks it's worth less in play but chose to match the cards. |
| Crit-Seeker | Small-cluster weapons in the main attack land at least 14 average damage. Counts SRMs, Streak SRMs and MMLs at their average damage, and every LB-X at its average pellet hits on the Cluster Hits Table (1 point each: LB 5-X 3.2, 10-X 6.3, 20-X 12.7). | Offense ×1.1 | +1 on the Determining Critical Hits roll raises average crits per roll from 0.61 to 0.94 (+55%). Crits are only part of an attack's killing power (rough guess 15–25%), so about +8–14% on offense. The 21 official Crit-Seeker vehicles fit best at ×1.10 (average error 2.44 vs 2.57 at the old fitted 1.05). When it applies: weapons whose TW damage lands in 1–2 point clusters. 116/118 official vehicles, no false positives. Three LB 5-X average 9.5 hits, which is why the Pike (LB-X) just misses, as Will predicted. MRMs (5-point groups) don't count. Misses: Behemoth and SturmFeur (SRM) (SRMs outside the main attack). |
| ECM X | Guardian, Clan or Angel ECM = ECM6; Watchdog = ECM3 | ECM6 +7 points flat; ECM3 +3.5 | From the Savannah (Interdictor) and Browning cards, which have no attack. Flat so unarmed units pay for it. About 2.5× the TechManual's 61 BV: a 6-hex bubble covers the whole force, and the rules limit how many ECM assets you can buy. |
| IF X | Round(average LRM/MML hits ÷ 5); none under 5 hits. MMLs count in LRM mode (1 point per hit) | Counted as X × 5 damage at 7/14/21, ×0.8; the larger of IF or direct fire | 23/30. |
| No Turret | Vehicle has no turret | Offense ×0.9 | A real disadvantage in play; Will puts it at a 10–20% discount on offense. Fitted 12% off on 25 cards, rounded to one decimal. |
| PRB | Active probe fitted | +1 point flat | A sensor, so its value doesn't scale with firepower (Will). TechManual probe BV is 10–25 (½–1¼ points); without a probe adjustment the 8 PRB cards price about 1 point low. Replaced a fitted ×1.08 offense multiplier. |
| TAG | TAG fitted | +2 points flat | Support for guided weapons, not firepower, so flat. TW BV is 0 (the benefit is counted in the guided weapons). The 8 TAG cards fit best at 2.5–3 points, but only slightly better than 2 (average error 2.0–2.1 vs 2.2); Will thought 2 was already a bit high, so 2. Replaced a fitted ×1.05 offense multiplier. |
| TC | Targeting computer | Through Skill (one step better) | |

| MML | Dual mode: SRM mode (2 points per hit, 3/6/9) for the direct attack and Crit-Seeker; LRM mode for IF | — | Will: an MML can fire either, so it can give both Crit-Seeker and IF. Fixed Crit-Seeker on the Pegasus (Upgrade) and Striker (Stealth). |

## Known exceptions

Official cards the rules don't reproduce, kept as printed:

- Hawk Moth II: Check 4 (armor suggests 7), confirmed by Will.
- Fox Armored Car: 11 MP (MegaMek 14), confirmed.
- Arrow IV Carrier: cost 58 (rules give 86), early card.
- Tracked APC, Coolant Trucks: no AI despite all-anti-infantry weapons.
- Savior Repair Vehicle: APC2 with 3 t of troop space.
- Check misses: Pandion, SRM Carrier (C3), Coolant Truck 135-K, Tokugawa (MRM),
  Demolisher (standard and Gauss).
