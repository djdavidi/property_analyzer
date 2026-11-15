# Validation results

Independent real-site validation remains incomplete. Synthetic tests check deterministic behavior and workflow only; they do not count as measured real-site accuracy.

Machine-readable assessment: `data/validation/benchmarks.json`.

| Validation layer | Real cases with metrics | Real holdouts | Status |
| --- | ---: | ---: | --- |
| IA | 0 | 0 | incomplete |
| DRAINAGE | 0 | 0 | incomplete |

## Metrics

IA and catchments are compared separately. Reports retain signed area error, absolute percentage error, boundary IoU, precision/recall, false positive and false negative area, and native-unit boundary Hausdorff distance. Equal total area alone does not establish agreement. Reference provenance, CRS and stable site vintage must be supplied explicitly.

Binary IA errors do not validate roof/pavement multiclass classification. Critical routing disagreements and processing/resolution sensitivity require additional independent review. No numerical release threshold is set.

## Executed cases

- `synthetic-demo`: synthetic fixture; excluded from empirical summary; IA incomplete; drainage incomplete; analysis 0.014501 seconds; logged manual review unknown minutes.
- `pwd-98627`: real evidence case; IA incomplete; drainage incomplete; analysis 0.008096 seconds; logged manual review 0 minutes.
- `pwd-98627-usgs-1m`: real evidence case; IA incomplete; drainage incomplete; analysis 3.769226 seconds; logged manual review 0 minutes.

## Outstanding

- IA: No independently referenced real-site ia result is available.
- IA: Several stable completed sites spanning the planned site types have not been evaluated.
- IA: No independently referenced real-site holdout has been evaluated.
- IA: Resolution and processing sensitivity remain incomplete.
- DRAINAGE: No independently referenced real-site drainage result is available.
- DRAINAGE: Several stable completed sites spanning the planned site types have not been evaluated.
- DRAINAGE: No independently referenced real-site holdout has been evaluated.
- DRAINAGE: Resolution and processing sensitivity remain incomplete.
- DRAINAGE: Critical routing disagreements have not been independently reviewed.
- Confirm independent IA labels and accepted drainage boundaries for stable completed sites, including proposed Whitaker, before recommending acceptance thresholds.
- Check soil, inlet/roof/pipe connections, shared allocations, current-condition evidence and actual bills before treating modeled benefit screens as a property-specific savings claim.
