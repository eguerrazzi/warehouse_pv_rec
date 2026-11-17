"""wpvrec: warehouse + rooftop PV + Renewable Energy Community.

Bi-objective LP (F1: PV self-consumed, F2: lost productivity) for shifting the
internal work of an automated warehouse into the PV hours, with an ex-post
evaluation of REC membership. See ``docs/spec/specification_v1.md``.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("wpvrec")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0"
