"""cns-coach: honest longitudinal inference over wearable data.

Three pieces, deliberately separable:

* ``cnscoach.causal``   — pre-registered hypotheses, within-athlete fixed effects,
  family-wise error control, and equivalence testing so that "no effect" is a result.
* ``cnscoach.cns``      — a transparent, swappable readiness score. Every component is
  named, weighted in the open and traceable to a citation.
* ``cnscoach.coach``    — an LLM that may only speak in claims the engine produced.
"""

__version__ = "0.1.0"
