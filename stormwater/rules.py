"""Versioned PWD technical screens. A passing screen is never PWD approval.

Rates, factors and thresholds are read from ``config/rules-pwd-2026-09.json``
(manual September 2026; tariff effective 2026-09-01). The code holds no second
copy of those numbers.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_EVEN, InvalidOperation
from pathlib import Path
import json
import math

RULE_VERSION = 'pwd-2026-09-screen-v1'
MANUAL_URL = 'https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf'
TARIFF_URL = 'https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf'
RULE_CONFIG_PATH = Path(__file__).resolve().parents[1]/'config'/'rules-pwd-2026-09.json'
_CONFIG_CACHE = {}


def _config(path=None):
    target = Path(path) if path is not None else RULE_CONFIG_PATH
    key = str(target)
    stamp = target.stat().st_mtime_ns
    cached = _CONFIG_CACHE.get(key)
    if cached is None or cached[0] != stamp:
        with open(target, encoding='utf-8') as handle:
            cached = (stamp, json.load(handle))
        _CONFIG_CACHE[key] = cached
    return cached[1]


def load_rule_config(path=None):
    """Return the versioned PWD rule configuration (a fresh copy on each call)."""
    return json.loads(json.dumps(_config(path)))


def factor(name, path=None):
    """A configured rule factor as Decimal (never float)."""
    return Decimal(str(_config(path)[name]))


def number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be numeric')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be numeric') from None
    if not math.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def curve_number_decimal(curve_number):
    """Exact Decimal CN; floats use their shortest repr, never binary expansion."""
    number(curve_number, 'curve_number')
    try:
        cn = curve_number if isinstance(curve_number, Decimal) else Decimal(str(curve_number))
    except (InvalidOperation, ValueError):
        raise ValueError('curve_number must be numeric') from None
    if not Decimal(0) <= cn <= Decimal(100):
        raise ValueError('curve_number must be between 0 and 100')
    return cn


def open_space_factor(curve_number, npdes=False):
    """Manual Table A-2 credit factor for an average open-space CN.

    Manual 4.3.3.1: "A percent reduction is applied for each whole number below a
    CN of 75"; Table A-2 lists whole CNs (>=75 -> 0; 55 and <55 -> 80%, or 87%
    with NPDES). A fractional average earns only the whole steps it reaches:
    steps = floor(75 - CN) = 75 - ceil(CN). The CN is handled in Decimal and
    stabilized to 1e-9 so binary area noise (61.000000000000014) cannot remove a
    step; Appendix A steps 3-5 define the average as sum(area x CN) / sum(area).
    """
    cn = curve_number_decimal(curve_number).quantize(Decimal('.000000001'), rounding=ROUND_HALF_EVEN)
    config = _config()
    threshold = int(config['open_space_cn_threshold'])
    whole = int(cn.to_integral_value(rounding=ROUND_CEILING))
    steps = max(0, min(int(config['open_space_cn_max_steps']), threshold - whole))
    step = factor('open_space_cn_step_npdes_factor' if npdes else 'open_space_cn_step_factor')
    return float(Decimal(steps) * step)


def screen(category, area_sqft, evidence=None):
    """Return missing and failed prerequisites separately; unknown is not false.

    Numeric units are explicit in field names. Evidence may contain assumed values
    only if the caller labels the resulting benefit basis='modeled'.
    """
    evidence = evidence or {}
    area = number(area_sqft, 'area_sqft')
    if area < 0:
        raise ValueError('area_sqft cannot be negative')
    aliases = {'tree_canopy':'canopy', 'downspout':'roof_disconnection',
               'roof':'roof_disconnection','pavement':'pavement_disconnection',
               'open-space':'open_space','managed':'management'}
    category = aliases.get(category, category)
    missing, failed = [], []
    def required(name):
        if evidence.get(name) is None:
            missing.append(name); return False
        if evidence[name] is not True:
            failed.append(name); return False
        return True
    def numeric(name, predicate):
        if evidence.get(name) is None:
            missing.append(name); return None
        value = number(evidence[name], name)
        if not predicate(value): failed.append(name)
        return value
    for name in ['physical_area_confirmed','parcel_allocation_confirmed','account_current']:
        required(name)
    iar, ga, ia = 0., 0., 0.
    if category == 'canopy':
        required('ground_impervious_overlap_confirmed')
        iar = float(Decimal(str(area)) * factor('canopy_ground_ia_overlap_iar_factor'))
    elif category in ('roof_disconnection','pavement_disconnection'):
        required('receiving_area_pervious')
        required('receiving_dimensions_sufficient')
        required('routing_confirmed')
        numeric('receiving_slope_percent', lambda x: 0 < x <= 5)
        soil = evidence.get('soil_group')
        if soil is None: missing.append('soil_group')
        elif str(soil).upper() not in ['A','B','C','UB']: failed.append('soil_group')
        if category == 'roof_disconnection':
            numeric('area_per_downspout_sqft',lambda x: 0 < x <= 500)
            numeric('ground_impervious_clearance_ft',lambda x: x >= 15)
            required('continuous_flow_path')
            required('no_dcia_in_flow_path')
            required('unique_flow_path_per_downspout')
        else:
            numeric('impervious_flow_path_ft',lambda x: 0 <= x <= 75)
            numeric('contributing_slope_percent',lambda x: 0 <= x <= 5)
            required('vegetated_receiving_area')
            if evidence.get('sheet_flow') is None: missing.append('sheet_flow')
            elif evidence['sheet_flow'] is not True:
                numeric('area_per_discharge_point_sqft',lambda x: 0 < x <= 1000)
                required('erosion_control')
        iar = area
    elif category == 'open_space':
        required('cover_confirmed'); required('soil_confirmed')
        required('runoff_characteristics_confirmed'); required('non_impervious_confirmed')
        if evidence.get('curve_number') is None: missing.append('curve_number')
        else: ga = float(Decimal(str(area)) * Decimal(str(open_space_factor(evidence['curve_number'], evidence.get('npdes') is True))))
    elif category == 'management':
        for name in ['routing_confirmed','approved_record_drawings','current_condition_confirmed',
                     'maintenance_documented','professional_reviewed']:
            required(name)
        numeric('treatment_depth_inches',lambda x: x >= (1.0 if evidence.get('old_standard_renewal_verified') is True else 1.5))
        ga = ia = float(Decimal(str(area)) * factor('non_surface_management_npdes_factor' if evidence.get('npdes') is True else 'non_surface_management_factor'))
    else:
        raise ValueError(f'Unsupported credit category: {category}')
    status = 'requirements_failed' if failed else 'missing_evidence' if missing else 'screen_pass'
    return {'rule_version':RULE_VERSION,'category':category,'area_sqft':area,
            'status':status,'missing':missing,'failed':failed,
            'potential_iar_sqft':iar,'potential_ga_credit_sqft':ga,
            'potential_ia_credit_sqft':ia,
            'iar_sqft':iar if status=='screen_pass' else None,
            'ga_credit_sqft':ga if status=='screen_pass' else None,
            'ia_credit_sqft':ia if status=='screen_pass' else None,
            'decision':'Technical screening only; PWD approval is not established.',
            'source':MANUAL_URL}
