# Jurisdiction policies consume physical GIS evidence

The software has two separately runnable layers:

1. `drainage_core` measures surfaces and boundaries, prepares/routes terrain,
   represents buildings/curbs/inlets/connections, preserves evidence and unknowns,
   validates references, and exports maps and physical measurements. It imports
   no Philadelphia providers, credit rules or billing code.
2. `stormwater.jurisdictions` applies a named jurisdiction's eligibility and
   billing rules to a frozen GIS case/result. Only **`philadelphia-pwd`** is
   implemented. Running the GIS engine elsewhere does not imply support for that
   location's credits, tariffs or public-data discovery.

The GIS layer is a physical screening model, not a construction-design, pipe
hydraulics or professional-certification package. A mapped system footprint,
topographic depression or delineated collection catchment does not establish an
eligible practice, treatment capacity or approved credit.

## Apply Philadelphia rules separately

Generate a general GIS project first, then run:

```sh
.venv/bin/python -m stormwater.policy_cli \
  --jurisdiction philadelphia-pwd \
  --case /path/to/gis/case.json \
  --gis /path/to/gis/analysis.json \
  --policy /path/to/philly-policy.json \
  --output /path/to/credits.json
```

For an existing Philadelphia workbench case, use its `gis-analysis.json` for the
`--gis` argument. Its combined `analysis.json` is a policy result and is not a
reusable GIS artifact. Newly saved Philadelphia cases retain both.

The command performs no acquisition, terrain preparation, surface classification
or drainage rerun. It checks the input-case hash and any analysis-content digest,
then applies only the explicit jurisdiction. It refuses to overwrite the frozen
case, GIS artifact or policy input. Output records the GIS input hash, deterministic
GIS analysis hash, exact artifact hash, jurisdiction/rule versions and policy-input
hash. Changing baseline/evidence/benefit inputs produces a separate policy result
while preserving the same physical GIS evidence.

The `./credits` launcher is equivalent to `.venv/bin/python -m
stormwater.policy_cli`; `./credits --help` lists the required artifact and policy
arguments. A working example using the saved Whitaker GIS artifact is:

```sh
./credits --jurisdiction philadelphia-pwd \
  --case data/cases/pwd-98627-usgs-1m/case.json \
  --gis data/cases/pwd-98627-usgs-1m/gis-analysis.json \
  --output data/policy/whitaker-pwd.json
```

This reuses the existing case's baseline/benefits. Its output reproduces the
standard public $3,138.21/month baseline while retaining blocked area/credit
scenarios and missing evidence. It does not establish an actual bill, eligible
managed area or new savings. Saving a legacy workbench case regenerates its
separate `gis-analysis.json`; do not substitute the combined `analysis.json`.

The exact launcher command above was executed on November 15, 2026. It wrote
`data/policy/whitaker-pwd.json`, reproduced the **$3,138.21/month** public baseline,
and retained blocked appeal-only and combined scenarios. Before/after SHA-256
checks confirmed that the case, GIS artifact, frozen native DEM window, window
provenance record and exact USGS metadata bytes were unchanged. The machine-readable
verification is `data/policy/whitaker-policy-verification.json`. This was a
policy-only execution; the adapter/CLI tests also explicitly fail if GIS analysis
is called while applying a policy. All 13 policy-boundary tests passed after the
real-case execution.

A minimal policy file can contain only a public or verified billing baseline:

```json
{
  "jurisdiction": "philadelphia-pwd",
  "baseline": {
    "ga_sqft": 10000,
    "ia_sqft": 8000,
    "existing_ga_credit_sqft": 0,
    "existing_ia_credit_sqft": 0,
    "existing_iar_sqft": 0,
    "npdes_fraction": 0,
    "property_type": "NonRes",
    "accounts": [{"allocation": 1, "discount_factor": 1}],
    "bill_date": "2026-11-15",
    "actual_bill_verified": false
  },
  "benefits": []
}
```

These figures are a synthetic format example, not a property assessment. Unknown
credits, discounts and account allocations must not be replaced with zero or one
merely to make the model run. Missing baseline fields block billing. PWD is an
explicit policy choice; the adapter does not infer jurisdiction from coordinates.

Benefits use the existing schema: `id`, `category`, `geometry`, `basis` and
`evidence`. Their geometry is projected **in the GIS case's CRS**, not necessarily
longitude/latitude. Categories are `canopy`, `roof_disconnection`,
`pavement_disconnection`, `open_space` and `management`. Basis is `documented` or
`modeled`. For example, a canopy benefit's prerequisites include confirmed physical
area, ground-level impervious overlap, parcel allocation and current account
status. Supplying booleans is an evidence assertion, not automatic verification.

The adapter recomputes a benefit polygon's area in the case's area-accounting CRS
and intersects it with the previously measured applicable geometry. Areas outside
physical IA/pervious/canopy-ground overlap, scalar-only hypotheses and unsupported
overlaps do not silently earn savings. Source observations and GIS measurements
are never modified by eligibility decisions.

`--policy` is optional when the original case already contains `baseline` and
`benefits`. Separate policy inputs may override those two fields and optionally
supply an explicitly verified `tariff`; they cannot change physical inputs. If a
parcel, terrain, surface or correction changes, regenerate the GIS artifact.

## Python interface

```python
from stormwater.jurisdictions import get_profile

result = get_profile("philadelphia-pwd").apply(
    case,
    gis_result,
    policy_inputs={"baseline": baseline, "benefits": benefits},
)
```

The return value is policy enrichment only: `screens`, `billing`,
`surface_assumption_scenarios`, policy warnings and provenance hashes. It does not
return copied physical measurements or routing as if they were policy outputs.
Passing a changed case with an old artifact, a modified digest-bearing artifact,
or a combined jurisdiction result raises an error before calculating savings.

## Add another jurisdiction

Implement another opt-in module exposing an `apply(case, gis_result,
policy_inputs=None)` operation and register its explicit profile ID. Reuse
physical measurements, geometry/evidence and validation from the core; implement
that jurisdiction's rules, prerequisites, units, tariff versions, overlap
sequencing and billing independently. Add known-answer policy fixtures and tests
that prove its calculations do not mutate or rerun the GIS layer. Public-data
providers are separate adapters and must record their source/CRS/date/quality
evidence. Do not add local tariffs or automatic municipal assumptions to the core.

Philadelphia's current evidence and billing limitations remain documented in
[RULES.md](RULES.md). Separating modules does not resolve missing independent
validation, site connections, grading, actual bills or unsupported combinations.
