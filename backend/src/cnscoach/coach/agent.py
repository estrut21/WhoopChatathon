"""The coach: an Anthropic tool-use loop wrapped in citation enforcement.

The loop itself is ordinary. What matters is what surrounds it:

* the model starts with **no data in context** — it must call tools to learn anything,
  so there is nothing for it to half-remember;
* every tool result is registered in a `FactLedger`;
* the final reply is verified against that ledger before the user sees it.

In `strict` mode an ungrounded reply is replaced by a refusal. In default mode it is
shown with the offending numbers marked, which is more useful during a demo because the
failure is visible rather than hidden.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from cnscoach.causal.engine import Finding
from cnscoach.coach import guardrails as G
from cnscoach.coach.tools import TOOL_SCHEMAS, ToolExecutor
from cnscoach.config import settings
from cnscoach.evidence import EvidenceStore

log = logging.getLogger(__name__)


@dataclass
class CoachReply:
    text: str
    grounding: G.GroundingReport
    tool_calls: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    blocked: bool = False
    stop_reason: str = ""
    n_turns: int = 0

    @property
    def is_grounded(self) -> bool:
        return self.grounding.is_grounded

    def render(self) -> str:
        parts = [self.text, "", "---", self.grounding.summary()]
        if self.tool_calls:
            names = ", ".join(sorted({c["name"] for c in self.tool_calls}))
            parts.append(f"Data retrieved via: {names}")
        if self.citations:
            parts.append("Citations: " + "; ".join(self.citations))
        if not self.is_grounded:
            parts.append("")
            parts.append("UNVERIFIED CLAIMS:")
            parts.extend(f"  - {v}" for v in self.grounding.violations)
        return "\n".join(parts)


class Coach:
    """Answers questions about one panel, using only what it can retrieve."""

    MAX_TURNS = 8

    def __init__(
        self,
        features,
        findings: list[Finding],
        *,
        api_key: str | None = None,
        model: str | None = None,
        strict: bool = False,
        evidence: EvidenceStore | None = None,
    ) -> None:
        self.features = features
        self.findings = findings
        self.model = model or settings.model
        self.strict = strict
        self.evidence = evidence or EvidenceStore()
        self._api_key = api_key or settings.anthropic_api_key

        self._client = None
        if self._api_key:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self._api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def ask(self, question: str, athlete_id: str | None = None) -> CoachReply:
        if self._client is None:
            raise RuntimeError(
                "No Anthropic API key. Set CNSCOACH_ANTHROPIC_API_KEY in .env, or use "
                "dry_run() to exercise the tool layer and guardrails without a model."
            )

        ledger = G.FactLedger()
        executor = ToolExecutor(self.features, self.findings, ledger, self.evidence)

        preamble = (
            f"The athlete under discussion is '{athlete_id}'. "
            if athlete_id
            else "No specific athlete selected; ask which one if the question needs it. "
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": preamble + question}]

        tool_calls: list[dict] = []
        citations: list[str] = []
        final_text = ""
        stop_reason = ""

        for turn in range(self.MAX_TURNS):
            response = self._client.messages.create(
                model=self.model,
                max_tokens=settings.max_tokens,
                system=G.SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            stop_reason = response.stop_reason or ""

            text_parts = [b.text for b in response.content if b.type == "text"]
            uses = [b for b in response.content if b.type == "tool_use"]

            if not uses:
                final_text = "\n".join(text_parts).strip()
                break

            messages.append({"role": "assistant", "content": response.content})

            results = []
            for use in uses:
                args = dict(use.input)  # type: ignore[arg-type]
                result = executor.run(use.name, args)
                tool_calls.append({"name": use.name, "args": args})

                if use.name == "search_literature":
                    citations.extend(
                        f"{r['citation']} {r['doi_url']}".strip()
                        for r in result.get("results", [])
                    )

                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": use.id,
                        "content": _as_text(result),
                    }
                )
            messages.append({"role": "user", "content": results})
        else:  # pragma: no cover - only on a pathological loop
            final_text = "Stopped after the maximum number of tool-use turns."
            stop_reason = "max_turns"

        report = G.verify(final_text, ledger)
        blocked = False

        if self.strict and not report.is_grounded:
            blocked = True
            offending = "; ".join(f"{v.value:g}" for v in report.violations)
            final_text = G.REFUSAL_TEMPLATE.format(
                detail=(
                    f"I generated {len(report.violations)} number(s) I cannot trace back to "
                    f"any retrieved datapoint ({offending}), so I have withheld the answer "
                    f"rather than show you something I cannot source."
                )
            )
        elif not report.is_grounded:
            final_text = G.annotate(final_text, report)

        return CoachReply(
            text=final_text,
            grounding=report,
            tool_calls=tool_calls,
            citations=list(dict.fromkeys(citations)),
            blocked=blocked,
            stop_reason=stop_reason,
            n_turns=len(tool_calls),
        )

    # -- offline paths -------------------------------------------------------------

    def dry_run(self, tool_name: str, args: dict) -> dict:
        """Execute one tool directly. Lets the data layer be tested without a model."""
        ledger = G.FactLedger()
        executor = ToolExecutor(self.features, self.findings, ledger, self.evidence)
        result = executor.run(tool_name, args)
        return {"result": result, "facts_registered": len(ledger)}

    def check_text(self, text: str, tool_calls: list[tuple[str, dict]]) -> G.GroundingReport:
        """Verify arbitrary text against the facts a given set of tool calls would yield.

        Used by the test suite to confirm that a fabricated statistic is caught even
        when every other number in the sentence is real.
        """
        ledger = G.FactLedger()
        executor = ToolExecutor(self.features, self.findings, ledger, self.evidence)
        for name, args in tool_calls:
            executor.run(name, args)
        return G.verify(text, ledger)


def _as_text(result: dict) -> str:
    import json

    return json.dumps(result, indent=2, default=str)
