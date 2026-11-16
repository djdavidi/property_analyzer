"""One ground-class interpretation table for every IA scenario (review A3, decision D3).

Jurisdiction-neutral. Dated semantic appearance classes never establish
construction or permeability; each named scenario below states how a class is
*treated* while that scenario is evaluated. The app path
(``model_integration.ai_surfaces`` / ``ia_bounds``), the per-system physical
estimates (``management_estimates``) and the saved-data pilot all read this table,
so the same pixels mean the same thing everywhere.

Decision D3:

* road appearance is impervious in a **labelled default** scenario
  (``road_impervious``), never in the measurement basis;
* developed-space appearance is **unknown** in every default; it becomes
  impervious only in the ``road_and_developed_impervious`` sensitivity;
* grass/shrub, bare soil and water are **pervious only in a labelled scenario**
  (``road_impervious_soft_pervious``);
* canopy conceals ground and is interpreted through crown context
  (``surface_estimates``), never as a surface class.

None of these scenarios may drive a headline figure on its own until class
agreement is measured against the 2018 lidar-assisted land cover (review G4).
"""

from copy import deepcopy

VERSION = "ground-class-interpretation-v1"
SOFT = ("grass_shrub", "bare_soil", "water")
SURFACE_CLASSES = ("roof", "road", "developed_space") + SOFT
CONCEALING = ("canopy",)

CLASS_TABLE = {
    "roof": {
        "measurement_basis": "impervious",
        "labelled_default": "impervious",
        "basis": "Roof outline is a modeled IA hypothesis (dated image)",
    },
    "road": {
        "measurement_basis": "unknown",
        "labelled_default": "impervious",
        "basis": "Road appearance is usually paved but permeability is not observed (D3 labelled default)",
    },
    "developed_space": {
        "measurement_basis": "unknown",
        "labelled_default": "unknown",
        "basis": "Developed space can be pavement, gravel, soil or structures",
    },
    "grass_shrub": {
        "measurement_basis": "unknown",
        "labelled_default": "unknown",
        "basis": "Vegetated appearance; pervious only in a labelled scenario",
    },
    "bare_soil": {
        "measurement_basis": "unknown",
        "labelled_default": "unknown",
        "basis": "Soil appearance; compaction/permeability unobserved; pervious only in a labelled scenario",
    },
    "water": {
        "measurement_basis": "unknown",
        "labelled_default": "unknown",
        "basis": "Water appearance; pervious only in a labelled scenario",
    },
    "canopy": {
        "measurement_basis": "concealed",
        "labelled_default": "concealed",
        "basis": "Crowns conceal ground; interpreted only by local crown context",
    },
}

SCENARIOS = {
    "identified_only": {
        "impervious": ("roof",),
        "pervious": (),
        "role": "measurement_basis",
        "label": "Observed IA plus modeled roof outlines only; every other appearance class unknown",
        "assumptions": [],
    },
    "road_impervious": {
        "impervious": ("roof", "road"),
        "pervious": (),
        "role": "labelled_default",
        "label": "D3 labelled default: road appearance assumed impervious; developed space and soft classes unknown",
        "assumptions": [
            "All road-appearance pixels are impermeable; this is unverified (D3 labelled default)"
        ],
    },
    "road_impervious_soft_pervious": {
        "impervious": ("roof", "road"),
        "pervious": SOFT,
        "role": "labelled_scenario",
        "label": "Labelled scenario: road impervious, grass/soil/water pervious, developed space unknown",
        "assumptions": [
            "All road-appearance pixels are impermeable; this is unverified",
            "Grass/shrub, bare-soil and water appearances are pervious; permeability is not observed",
        ],
    },
    "road_and_developed_impervious": {
        "impervious": ("roof", "road", "developed_space"),
        "pervious": (),
        "role": "sensitivity",
        "label": "Sensitivity: road and developed-space appearance assumed impervious",
        "assumptions": ["All road/developed-space pixels are impermeable; this is unverified"],
    },
}

# The app's modeled measurement never promotes ground appearance (A3 overcorrection
# is addressed by the labelled scenarios, not by changing the measurement basis).
MEASUREMENT_SCENARIO = "identified_only"
DEFAULT_SCENARIO = "road_impervious"
# Per-system physical area scenarios (drainage_core.management_estimates).
SYSTEM_SCENARIOS = (
    ("low", "identified_only"),
    ("base", "road_impervious"),
    ("high", "road_and_developed_impervious"),
)
# Extra labelled IA bound offered by the app path (model_integration.ia_bounds).
APP_LABELLED_BOUNDS = (("road_impervious", "road_impervious"),)


def classes(scenario, treatment):
    """Class names treated as ``impervious`` or ``pervious`` in a named scenario."""
    if treatment not in ("impervious", "pervious"):
        raise ValueError("treatment must be impervious or pervious")
    return SCENARIOS[scenario][treatment]


def describe(scenario):
    """A copy of the scenario definition for result lineage."""
    return {"id": scenario, "version": VERSION, **deepcopy(SCENARIOS[scenario])}


def table():
    return {
        "version": VERSION,
        "classes": deepcopy(CLASS_TABLE),
        "scenarios": deepcopy(SCENARIOS),
        "measurement_scenario": MEASUREMENT_SCENARIO,
        "default_scenario": DEFAULT_SCENARIO,
        "headline_rule": (
            "No single interpretation scenario drives a headline figure until class agreement "
            "is measured against the 2018 lidar-assisted land cover (G4)"
        ),
    }
