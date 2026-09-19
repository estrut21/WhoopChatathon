"""Citation enforcement: the coach may only say numbers it was given.

How this works
--------------
Every tool call registers the numbers it returned into a **fact ledger**, along with
where each came from. After the model generates a reply, every number in that reply is
matched against the ledger. Anything that does not match is a *violation* and is
surfaced — struck through in the UI, or blocked entirely in strict mode.

What this catches and what it does not
--------------------------------------
It catches the dominant failure mode: a model inventing a plausible-looking statistic
("your recovery drops 18% after late workouts") that no analysis produced. It does not
catch a fluent but wrong *qualitative* claim ("your sleep is getting worse") that
contains no numbers, and it cannot catch a number that happens to collide with a real
one. It is a strong filter, not a proof of correctness, and calling it a proof would be
the same overclaiming the project exists to oppose.

Rounding and arithmetic are tolerated within limits, because refusing them would make
the coach unreadable — a model should be able to say "about 18%" for 18.2, and to
subtract two ledger values. Both relaxations are explicit and logged rather than silent.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from itertools import combinations

log = logging.getLogger(__name__)

#: Numbers so common they carry no risk of being a fabricated statistic: small counts,
#: round figures, plausible years, and the conventional confidence levels. Without the
#: last group every mention of "95% CI" is flagged, which trains a reader to ignore the
#: warnings — the worst possible outcome for a checker.
BENIGN = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 24, 30, 50, 60, 100, 1000,
    90, 95, 99,  # confidence levels
    2023, 2024, 2025, 2026,
}

#: Matches integers, decimals and scientific notation, with or without thousands
#: separators. The alternation matters: a naive `\d{1,3}(?:,\d{3})*` looks like it
#: handles both but silently fails to match *any* bare integer longer than three digits
#: — the trailing `(?![\w])` rejects the partial match and the whole number is skipped.
#: That made every large figure, such as a 99428-day sample size, invisible to the
#: checker and therefore unverifiable in exactly the cases where it mattered most.
NUMBER_RE = re.compile(
    r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w])"
)


@dataclass
class Fact:
    """One number the coach is permitted to use, and where it came from."""

    value: float
    label: str
    source: str
    """Which tool call produced it, e.g. 'get_finding(A1_strain_to_hrv).coef'."""

    def __hash__(self) -> int:
        return hash((round(self.value, 6), self.source))


@dataclass
class Violation:
    value: float
    context: str
    reason: str

    def __str__(self) -> str:
        return f"{self.value:g} — {self.reason} (…{self.context}…)"


@dataclass
class GroundingReport:
    verified: list[tuple[float, Fact]] = field(default_factory=list)
    derived: list[tuple[float, str]] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    benign_skipped: int = 0
    allow_derived: bool = False

    collision_rate: float = 0.0
    """Measured probability that a random plausible number would pass this ledger.

    Reported rather than hidden: a checker's credibility depends on knowing how often
    it can be fooled, and a large ledger is easier to fool than a small one."""

    ledger_size: int = 0

    @property
    def is_grounded(self) -> bool:
        return not self.violations

    @property
    def n_checked(self) -> int:
        return len(self.verified) + len(self.derived) + len(self.violations)

    @property
    def confidence_note(self) -> str:
        if self.ledger_size == 0:
            return ""
        return (
            f"Checker strength: a random plausible number would pass this "
            f"{self.ledger_size}-fact ledger {self.collision_rate:.1%} of the time."
        )

    def summary(self) -> str:
        if self.n_checked == 0:
            base = "No numeric claims to verify."
        elif self.is_grounded:
            derived_note = f", {len(self.derived)} derived" if self.derived else ""
            base = (
                f"All {self.n_checked} numeric claim(s) traced to retrieved data "
                f"({len(self.verified)} direct{derived_note})."
            )
        else:
            base = (
                f"{len(self.violations)} of {self.n_checked} numeric claim(s) could NOT "
                f"be traced to any retrieved data."
            )
        note = self.confidence_note
        return f"{base} {note}".strip()


class FactLedger:
    """Accumulates every number the model was actually shown."""

    def __init__(self) -> None:
        self._facts: list[Fact] = []

    def __len__(self) -> int:
        return len(self._facts)

    @property
    def facts(self) -> list[Fact]:
        return list(self._facts)

    def add(self, value: object, label: str, source: str) -> None:
        try:
            v = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        if not math.isfinite(v):
            return
        self._facts.append(Fact(value=v, label=label, source=source))

    def add_mapping(self, data: object, source: str, prefix: str = "") -> None:
        """Walk a nested tool result and register every number it contains."""
        if isinstance(data, dict):
            for k, v in data.items():
                self.add_mapping(v, source, f"{prefix}.{k}" if prefix else str(k))
        elif isinstance(data, (list, tuple)):
            for i, v in enumerate(data):
                self.add_mapping(v, source, f"{prefix}[{i}]")
        elif isinstance(data, bool):
            return
        elif isinstance(data, (int, float)):
            self.add(data, prefix, source)

    def match(
        self,
        value: float,
        *,
        tolerance: float | None = None,
        rel_tol: float = 0.02,
        percent_context: bool = False,
    ) -> Fact | None:
        """Find a ledger fact this number plausibly is, allowing for rounding.

        Matching is *sign-insensitive*, because "a fall of 0.053 ms" is the natural way
        to state a coefficient of -0.053 and rejecting that would make the coach
        unreadable. It costs a factor of two in match surface, which is accounted for
        in `collision_rate`.

        `percent_context` (the number carries a % sign) additionally permits a stored
        proportion of 0.182 to license "18.2%". That rescaling is deliberately *not*
        unconditional — applying it to every number triples the match surface.

        There is no absolute-tolerance floor. One is tempting, to let a reported 0 match
        a stored 0, but any floor means every number below it matches any zero-valued
        fact — and ledgers are full of structural zeros like `hr_zone_5_min`. Zero is in
        `BENIGN` and never reaches here anyway.
        """
        for fact in self._facts:
            candidates = [fact.value]
            if percent_context:
                candidates += [fact.value * 100, fact.value / 100]
            for candidate in candidates:
                if candidate == 0:
                    continue
                tol = tolerance if tolerance is not None else abs(candidate) * rel_tol
                for signed in (candidate, -candidate):
                    if abs(value - signed) <= tol:
                        return fact
        return None

    def match_derived(self, value: float, *, rel_tol: float = 0.01) -> str | None:
        """Permit one-step arithmetic, but only between *comparable* ledger values.

        Unrestricted pairwise arithmetic is worse than useless. With a few hundred
        ledger entries, five operations over every pair spans O(N^2) candidate values
        densely enough that almost any number is "derivable" — in testing, a fabricated
        23.7 matched as `-1.737 / -0.0728`, two quantities with no shared meaning. That
        turns the checker into a rubber stamp.

        So derivation is restricted to pairs that share a field name (two `.coef`
        values, two `.hrv` values), and to differences and ratios, which are the only
        operations a coach has a legitimate reason to perform. Even then it is off by
        default — see `verify`.
        """
        by_field: dict[str, list[Fact]] = {}
        for f in self._facts:
            if not math.isfinite(f.value):
                continue
            field_name = f.label.rsplit(".", 1)[-1].split("[")[0]
            by_field.setdefault(field_name, []).append(f)

        for field_name, facts in by_field.items():
            if len(facts) < 2:
                continue
            values = sorted({f.value for f in facts})
            for a, b in combinations(values, 2):
                for op, label in (
                    (a - b, f"{a:g} - {b:g} (both '{field_name}')"),
                    (b - a, f"{b:g} - {a:g} (both '{field_name}')"),
                    (a / b if b else None, f"{a:g} / {b:g} (both '{field_name}')"),
                    (b / a if a else None, f"{b:g} / {a:g} (both '{field_name}')"),
                ):
                    if op is None or not math.isfinite(op):
                        continue
                    if abs(value - op) <= max(0.005, abs(op) * rel_tol):
                        return label
        return None

    def collision_rate(
        self, *, n_probes: int = 1000, seed: int = 0, allow_derived: bool = False
    ) -> float:
        """Empirically measure how often a *fabricated* number would pass verification.

        This is the detector's false-negative rate, and publishing it is the difference
        between a guardrail and a claim of one.

        Probe construction is the whole game. Sampling uniformly across the ledger's
        full range is meaningless — ledgers span p-values near 1e-150 and row counts
        near 1e5, and a uniform draw over that lands nowhere near anything. Instead each
        probe is drawn *within the decade of a randomly chosen real fact*, which is the
        hard case: a fabricated statistic looks like a plausible one, stated at a
        plausible scale.

        The rate scales with ledger size — more retrieved facts means more ways for a
        wrong number to land near a right one. That is a real property of this approach,
        not a defect to hide, and it is the reason tools return curated fields rather
        than entire dataframes.
        """
        import random

        rng = random.Random(seed)
        reals = [f.value for f in self._facts if math.isfinite(f.value) and f.value != 0]
        if not reals:
            return 0.0

        hits = 0
        for _ in range(n_probes):
            anchor = abs(rng.choice(reals))
            decade = math.floor(math.log10(anchor))
            probe = rng.uniform(10**decade, 10 ** (decade + 1))
            # Probe as a coach would write it - three significant figures - so the
            # tolerance applied matches the one a real claim would receive.
            literal = f"{probe:.3g}"
            tol = rounding_tolerance(literal)
            if self.match(float(literal), tolerance=tol) is not None or allow_derived and self.match_derived(float(literal)) is not None:
                hits += 1
        return hits / n_probes


def rounding_tolerance(literal: str) -> float:
    """Half a unit in the last place of a number *as it was written*.

    A flat relative tolerance is wrong in both directions at once. At 2% it rejects
    "1.9e-06" as a rendering of 1.9464e-06 (legitimate rounding to two significant
    figures, 2.4% away), while accepting "23.7" as a match for anything within 0.47 —
    far too generous for a number stated to three figures.

    Deriving the tolerance from the written precision fixes both: a model that rounds
    is believed, and a model that states more digits is held to them.
    """
    s = literal.replace(",", "").strip().lstrip("+-")
    exponent = 0
    if "e" in s.lower():
        s, _, exp_part = s.lower().partition("e")
        exponent = int(exp_part)

    decimals = len(s.split(".")[1]) if "." in s else 0
    return 0.5 * (10 ** (-decimals + exponent))


@dataclass
class NumberMention:
    value: float
    literal: str
    context: str
    is_percent: bool
    tolerance: float


def extract_numbers(text: str) -> list[NumberMention]:
    """Pull every number out of generated text, with its written precision.

    The literal spelling matters as much as the value: it determines how much rounding
    slack the claim is entitled to.
    """
    out: list[NumberMention] = []
    for m in NUMBER_RE.finditer(text):
        literal = m.group()
        try:
            value = float(literal.replace(",", ""))
        except ValueError:  # pragma: no cover
            continue
        trailing = text[m.end() : m.end() + 2]
        start, end = max(0, m.start() - 40), min(len(text), m.end() + 40)
        out.append(
            NumberMention(
                value=value,
                literal=literal,
                context=text[start:end].replace("\n", " "),
                is_percent=trailing.lstrip().startswith("%"),
                tolerance=rounding_tolerance(literal),
            )
        )
    return out


def verify(
    text: str,
    ledger: FactLedger,
    *,
    allow_derived: bool = False,
    measure_collision_rate: bool = True,
) -> GroundingReport:
    """Check every number in `text` against the ledger.

    `allow_derived` is off by default. Arithmetic between retrieved values sounds
    harmless and is the single biggest hole in this kind of checker — see
    `FactLedger.match_derived`. A coach that must quote the numbers it was actually
    given, rather than combining them, is both safer and easier to audit.
    """
    report = GroundingReport(allow_derived=allow_derived)

    for mention in extract_numbers(text):
        value = mention.value
        if value in BENIGN or (float(value).is_integer() and abs(value) in BENIGN):
            report.benign_skipped += 1
            continue

        fact = ledger.match(
            value, tolerance=mention.tolerance, percent_context=mention.is_percent
        )
        if fact is not None:
            report.verified.append((value, fact))
            continue

        if allow_derived:
            derived = ledger.match_derived(value)
            if derived is not None:
                report.derived.append((value, derived))
                continue

        report.violations.append(
            Violation(
                value=value,
                context=mention.context,
                reason=(
                    f"no retrieved datapoint within +/-{mention.tolerance:g} "
                    f"(the precision '{mention.literal}' was stated to)"
                ),
            )
        )

    if measure_collision_rate and len(ledger):
        report.collision_rate = ledger.collision_rate(allow_derived=allow_derived)
        report.ledger_size = len(ledger)

    return report


def annotate(text: str, report: GroundingReport) -> str:
    """Mark unverifiable numbers inline so a reader can see exactly what failed."""
    if report.is_grounded:
        return text
    flagged = {v.value for v in report.violations}
    out: list[str] = []
    last = 0
    for m in NUMBER_RE.finditer(text):
        try:
            value = float(m.group().replace(",", ""))
        except ValueError:  # pragma: no cover
            continue
        if value in flagged:
            out.append(text[last : m.start()])
            out.append(f"[UNVERIFIED: {m.group()}]")
            last = m.end()
    out.append(text[last:])
    return "".join(out)


REFUSAL_TEMPLATE = (
    "I don't have that in your data.\n\n"
    "{detail}\n\n"
    "What I can tell you is drawn only from the pre-registered analyses and the rows "
    "actually retrieved for you. If you want this question answered properly, it needs "
    "to be added to the hypothesis family in `causal/hypotheses.py` and re-run — which "
    "also widens the multiple-comparison correction for everything else, on purpose."
)


SYSTEM_PROMPT = """\
You are a physiological-data analyst working over a WHOOP-style daily panel. You are \
deliberately built to be the opposite of a confident wellness chatbot.

ABSOLUTE RULES

1. Every number you state must come from a tool result in this conversation. You may \
round, and you may do simple arithmetic between retrieved numbers if you show what you \
combined. You may not estimate, recall, extrapolate, or infer a number from general \
knowledge. There is an automated checker on your output; unverifiable numbers are \
flagged to the user and destroy the point of this system.

2. If the data needed to answer does not exist, say so plainly and stop. "I don't have \
that" is a correct and valued answer here. Never substitute a plausible-sounding \
alternative for a missing measurement.

3. Respect the verdict attached to every finding. They are not interchangeable:
   - supported: detectable and large enough to act on.
   - detectable_but_trivial: real, but too small to change behaviour. Say both halves. \
Never present one of these as actionable.
   - negligible: affirmatively ruled out as a practical influence. This is a positive \
result, not an absence of information — report it as a finding.
   - inconclusive: the data cannot settle it. Say so, and give the minimum detectable \
effect. Never round this down to "no effect".
   - direction_reversed: flag it as anomalous; do not build advice on it.

4. All of this is observational. No exposure was randomised. Use associational language \
- "is followed by", "accompanies", "is associated with" - not "causes" or "makes".

5. Literature explains mechanism only. A paper never licenses a numeric claim about \
this athlete. When you cite, include the PMID, and state the study's limitation if the \
tool gave you one. Several papers in the corpus report null or contradictory results; \
represent them accurately rather than as support.

6. Do not diagnose, and do not give medical advice. If something looks like an illness \
signal, describe the measurement and recommend a clinician.

STYLE

Lead with the answer. Give the number, the interval, and the verdict together - an \
estimate without its uncertainty is misinformation here. Be concise. Do not pad with \
encouragement, and do not soften a null result into false optimism.\
"""
