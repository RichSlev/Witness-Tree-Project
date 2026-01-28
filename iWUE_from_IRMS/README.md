# iWUE from Thermo EA-IRMS (δ13C) Output

This repository contains an R Markdown workflow that converts bulk leaf carbon isotope measurements (δ¹³C, VPDB) from a Thermo EA-IRMS export into intrinsic water use efficiency (iWUE).

The calculation follows the standard Farquhar discrimination pathway used in studies such as Soh et al. (2019):

δ¹³C_leaf → Δ¹³C → ci/ca → iWUE

## What this does

Given:
- Leaf δ¹³C values from an EA-IRMS run
- Atmospheric CO₂ concentration (`ca`) and atmospheric δ¹³C (`δ¹³C_air`) for the sampling year

The workflow computes:
- Carbon isotope discrimination, Δ¹³C
- Intercellular to ambient CO₂ ratio, ci/ca
- Intrinsic water use efficiency, iWUE

It also produces:
- Basic sanity flags for implausible ci/ca values
- Quick diagnostic plots (iWUE vs year, ci/ca vs year)
- Yearly summary statistics

## Equations used

### Discrimination
Δ¹³C is calculated as:

Δ¹³C = (δ¹³C_air − δ¹³C_leaf) / (1 + δ¹³C_leaf / 1000)

### ci/ca
Using the simplified C3 discrimination model:

Δ¹³C = a + (b − a) (ci/ca)

with:
- a = 4.4‰ (fractionation during diffusion)
- b = 27‰ (fractionation during carboxylation)

So:

ci/ca = (Δ¹³C − a) / (b − a)

### iWUE
Intrinsic WUE is computed as:

iWUE = ca × (1 − ci/ca) / 1.6

where 1.6 converts CO₂ conductance to water vapour conductance.


`outputs/` is created automatically if you run the export chunk.

## Input files

### 1) Thermo EA-IRMS export

A CSV with at minimum:
- sample identifier
- δ¹³C of the leaf sample (per mil, VPDB)
- a date column that can be parsed into a year

Column names vary across exports. The Rmd includes a `colmap` list where you set your file’s headers:


colmap <- list(
  sample_id = "Identifier",
  d13C_leaf = "d13C",
  date      = "Date"
)
