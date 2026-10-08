"""Typical Ip/In by rated kW band (WEG guia §4.5.1 — design values for estimation).

Values are nominal design ratios before applying η·cos φ correction for
apparent-power based estimates. See service for the combined formula.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IpInBand:
    kw_max: float
    ip_in_base: float


# Ascending kw_max; last band catches all higher powers.
IP_IN_BANDS: tuple[IpInBand, ...] = (
    IpInBand(kw_max=1.5, ip_in_base=6.0),
    IpInBand(kw_max=4.0, ip_in_base=6.5),
    IpInBand(kw_max=7.5, ip_in_base=7.0),
    IpInBand(kw_max=15.0, ip_in_base=7.5),
    IpInBand(kw_max=75.0, ip_in_base=8.0),
    IpInBand(kw_max=99999.0, ip_in_base=7.0),
)


def lookup_ip_in_base(potencia_kw: float) -> float:
    for band in IP_IN_BANDS:
        if potencia_kw <= band.kw_max:
            return band.ip_in_base
    return IP_IN_BANDS[-1].ip_in_base


def ip_in_ratio(*, potencia_kw: float) -> float:
    """Estimate Ip/In from the kW band table (guia §4.5.1)."""
    return lookup_ip_in_base(potencia_kw)
