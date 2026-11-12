"""Re-export of the canonical L0 ``NetworkStatus`` enum from hb-data-type-primitives.

Sharing the same class keeps enum identity shared with the parent once it is wired.
"""

from data_type_primitives import NetworkStatus

__all__ = ["NetworkStatus"]
