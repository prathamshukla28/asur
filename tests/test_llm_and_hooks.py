"""Optional LLM drafting (fake provider, no network) + feature-based hook scoring."""

from __future__ import annotations

import io
import json

import pytest

from asur.core.workspace import Workspace
from asur.llm import (
    LLMError,
    draft_or_fallback,
    parse_json_payload,
    provider_from_spec,
)
from asur.llm.adapters.anthropic import AnthropicProvider
from asur.llm.adapters.ollama import OllamaProvider
from asur.script.audience import build_audience
from asur.script.hooks import (
    _DIM_FORMULAS,
    SCORE_DIMS,
    build_hooks,
    hook_features,
    score_from_features,
)
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.script_builder import SECTION_ORDER, build_script
from asur.script.strategy import build_strategy
from asur.tools.verify_repro import verify_reproducible

IDEA = "why most people waste money on AI tools"
TAKEAWAY = "list every AI subscription you pay for and cancel the ones that use the same model"


class FakeProvider:
    """Returns canned replies keyed by a word in the prompt; records calls."""

    def __init__(self, replies: dict[str, str], label: str = "llm:fake/test") -> None:
        self.replies = replies
        self._label = label
        self.calls: list[str] = []

    @property
    def label(self) -> str:
        return self._label

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1500) -> str:
        self.calls.append(prompt)
        for key, reply in self.replies.items():
            if key in prompt:
                return reply
        raise LLMError("no canned reply")


GOOD = {
    '"supporting_points"': json.dumps({
        "angles": [{"angle": a, "summary": f"{a} take", "why": "it helps"}
                   for a in ("audit", "overlap", "free-tier")],
        "supporting_points": ["Many tools resell the same model.", "Annual plans hide churn."],
        "risks": ["Prices change often."],
        "counterarguments": [{"objection": "I need them all", "response": "Check overlap first"}],
    }),
    '"pains"': json.dumps({"pains": ["Too many bills", "Unclear value"],
                           "desires": ["Spend less", "Keep the best tool"],
                           "objections": ["Switching is hard", "Is this an ad?"]}),
    '"hooks"': "Sure! ```json\n" + json.dumps({"hooks": [
        {"hook": "You might be paying three times for the same AI model.", "category": "cost"},
        {"hook": "Which of your AI subscriptions are secretly identical?", "category": "question"},
    ]}) + "\n```",
    '"sections"': json.dumps({"sections": {
        name: {"spoken_words": f"Drafted {name} line about overlapping AI plans.",
               "onscreen_text": name.title()}
        for name in SECTION_ORDER[1:]
    }}),
}


def _chain(generator=None, takeaway=TAKEAWAY):
    idea = build_idea(IDEA, "p", takeaway=takeaway)
    research = build_research(idea, "p", generator=generator)
    audience = build_audience(idea, research, "p", generator=generator)
    strategy = build_strategy(idea, audience, "p")
    hooks = build_hooks(strategy, "p", generator=generator)
    script = build_script(strategy, hooks, "p", generator=generator)
    return {"idea": idea, "research": research, "audience": audience,
            "strategy": strategy, "hooks": hooks, "script": script}


# -- provider selection ------------------------------------------------------


def test_default_is_templates(monkeypatch):
    monkeypatch.delenv("ASUR_LLM", raising=False)
    assert provider_from_spec(None) is None
    assert provider_from_spec("none") is None


def test_spec_builds_providers_lazily(monkeypatch):
    monkeypatch.setenv("ASUR_OLLAMA_URL", "http://127.0.0.1:9")
    ollama = provider_from_spec("ollama:qwen2.5")
    assert isinstance(ollama, OllamaProvider) and ollama.label == "llm:ollama/qwen2.5"
    anth = provider_from_spec("anthropic")
    assert isinstance(anth, AnthropicProvider)
    assert anth.label == "llm:anthropic/claude-sonnet-5-5"
    with pytest.raises(ValueError):
        provider_from_spec("gpt-everything")


def test_parse_json_payload_handles_fences_and_prose():
    assert parse_json_payload('{"a": 1}') == {"a": 1}
    assert parse_json_payload('here:\n```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json_payload('ok [1, 2] done') == [1, 2]
    with pytest.raises(ValueError):
        parse_json_payload("no json here")


def test_draft_or_fallback_records_failure_reason():
    bad = FakeProvider({"x": "not json"})
    value, prov = draft_or_fallback(bad, prompt="x", system="", validate=dict,
                                    fallback=lambda: {"t": 1})
    assert value == {"t": 1}
    assert prov["generator"] == "template"
    assert prov["llm_fallback"]["provider"] == "llm:fake/test"


# -- stages with a fake LLM ----------------------------------------------------


def test_stages_record_llm_provenance_and_tag_claims_hypothesis():
    chain = _chain(FakeProvider(GOOD))
    assert chain["research"].body["generator"] == "llm:fake/test"
    assert {a["angle"] for a in chain["research"].body["angles"]} == {"audit", "overlap", "free-tier"}
    assert all(c["evidence_class"] == "HYPOTHESIS"
               for c in chain["research"].body["supporting_points"])
    assert chain["audience"].body["generator"] == "llm:fake/test"
    assert chain["hooks"].body["generator"] == "template+llm:fake/test"
    llm_hooks = [h for h in chain["hooks"].body["hooks"]
                 if h["metadata"]["generator"] == "llm:fake/test"]
    assert len(llm_hooks) == 2
    assert chain["script"].body["generator"] == "llm:fake/test"
    hook_line = chain["script"].body["sections"]["hook"]["spoken_words"]
    selected = next(h for h in chain["hooks"].body["hooks"]
                    if h["hook_id"] == chain["hooks"].body["selected_hook_id"])
    assert hook_line == selected["metadata"]["hook"]


def test_template_path_records_template_provenance():
    chain = _chain(None)
    for kind in ("idea", "research", "audience", "strategy", "hooks", "script"):
        assert chain[kind].body["generator"] == "template", kind


def test_invalid_llm_output_falls_back_to_templates():
    broken = FakeProvider({'"supporting_points"': '{"angles": []}', '"pains"': "[]",
                           '"hooks"': '{"hooks": "nope"}', '"sections"': '{"sections": {}}'})
    chain = _chain(broken)
    template = _chain(None)
    for kind in ("research", "audience", "script"):
        assert chain[kind].body["generator"] == "template"
        assert "llm_fallback" in chain[kind].body
    assert chain["research"].body["angles"] == template["research"].body["angles"]
    assert chain["hooks"].body["generator"] == "template"


def test_verify_repro_skips_llm_drafted_stages(tmp_path):
    ws = Workspace(tmp_path, "p").ensure()
    for art in _chain(FakeProvider(GOOD)).values():
        ws.save_artifact(art)
    report = verify_reproducible(ws)
    by_kind = {s["kind"]: s for s in report["stages"]}
    assert by_kind["research"]["match"] is None
    assert "llm:fake/test" in by_kind["research"]["note"]
    assert by_kind["idea"]["match"] is True
    assert by_kind["strategy"]["match"] is True


def test_ollama_adapter_parses_response(monkeypatch):
    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["payload"] = json.loads(request.data)
        return _Resp(json.dumps({"response": '{"ok": true}'}).encode())

    import asur.llm.adapters.ollama as mod

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    out = OllamaProvider("llama3.1", base_url="http://localhost:11434").complete("hi", system="s")
    assert out == '{"ok": true}'
    assert seen["url"] == "http://localhost:11434/api/generate"
    assert seen["payload"]["stream"] is False and seen["payload"]["model"] == "llama3.1"


def test_ollama_adapter_wraps_connection_errors(monkeypatch):
    import asur.llm.adapters.ollama as mod

    def refuse(request, timeout):
        raise mod.urllib.error.URLError("connection refused")

    monkeypatch.setattr(mod.urllib.request, "urlopen", refuse)
    with pytest.raises(LLMError):
        OllamaProvider("x").complete("hi")


def test_anthropic_adapter_uses_messages_api_with_injected_client():
    class _Block:
        text = '{"ok": 1}'

    class _Messages:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return type("M", (), {"content": [_Block()]})()

    client = type("C", (), {"messages": _Messages()})()
    provider = AnthropicProvider(client=client)
    assert provider.complete("hello", system="sys", max_tokens=50) == '{"ok": 1}'
    assert client.messages.kwargs["model"] == "claude-sonnet-5-5"
    assert client.messages.kwargs["messages"] == [{"role": "user", "content": "hello"}]


# -- hook feature model ----------------------------------------------------------


def _feat(text, **kw):
    base = dict(subject="AI tools", language="en", language_target="en",
                emotion="curiosity", strategy_emotion="curiosity", novelty_vs_prior=1.0)
    base.update(kw)
    return hook_features(text, **base)


def test_formula_rows_sum_to_one_so_scores_span_0_100():
    for dim in SCORE_DIMS:
        bias, weights = _DIM_FORMULAS[dim]
        assert abs(bias + sum(weights.values()) - 1.0) < 1e-9, dim


def test_features_measure_the_text():
    f = _feat("Why are you paying twice for AI tools?")
    assert f["second_person"] == 1.0 and f["question"] == 1.0 and f["curiosity"] >= 0.5
    assert f["subject"] == 1.0
    vague = _feat("This thing and that stuff, everything")
    assert vague["concrete"] < 0.5 and vague["subject"] == 0.0


def test_unverifiable_claims_lower_credibility():
    honest = score_from_features(_feat("Check which AI tools share one model."))
    stat = score_from_features(_feat("Nine out of ten people overpay for AI tools."))
    story = score_from_features(_feat("I tested every AI tools plan for a year."))
    assert stat["credibility"] < honest["credibility"]
    assert story["authenticity"] < honest["authenticity"]


def test_scores_depend_only_on_features_not_on_hashes():
    # Identical features -> identical scores, whatever the text hash.
    a = _feat("Why do AI tools cost so much?")
    b = _feat("Why do AI tools cost so much?  ")
    assert a == b and score_from_features(a) == score_from_features(b)


def test_hook_ranking_is_stable_and_explained():
    one = _chain(None)["hooks"].body
    two = _chain(None)["hooks"].body
    assert [h["hook_id"] for h in one["hooks"]] == [h["hook_id"] for h in two["hooks"]]
    for h in one["hooks"]:
        assert score_from_features(h["features"]) == h["scores"]
    keys = [(-h["aggregate"], len(h["metadata"]["hook"].split()), h["candidate_order"])
            for h in one["hooks"]]
    assert keys == sorted(keys)
    assert "weights" in one["scoring_model"]
