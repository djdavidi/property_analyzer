"""Opt-in jurisdiction policies layered over reusable GIS evidence.

The drainage_core package must never import this package. Import a profile only
when applying that jurisdiction's eligibility and billing rules.
"""

PROFILES = ("philadelphia-pwd",)


def get_profile(identifier):
    if identifier != "philadelphia-pwd":
        raise ValueError(f"Unknown jurisdiction profile: {identifier}")
    from . import philadelphia

    return philadelphia
