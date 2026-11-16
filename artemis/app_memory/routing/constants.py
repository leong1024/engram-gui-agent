from collections.abc import Mapping

from artemis.app_memory.models import ObservationStatus

OBSERVATION_WEIGHT: Mapping[ObservationStatus, float] = {
    ObservationStatus.CONFIRMED: 1.0,
    ObservationStatus.DISCOUNTED: 0.25,
    ObservationStatus.PROVISIONAL: 0.5,
    ObservationStatus.DROPPED: 0.0,
}
PRIOR_SUCCESSES = 1.0
PRIOR_TRIALS = 2.0
HOP_COST = 0.1
OPAQUE_COST = 0.3
MAX_HOPS = 15
HIDE_AFTER_UNKNOWN_TURNS = 2
