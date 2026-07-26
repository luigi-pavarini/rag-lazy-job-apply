"""Response parsing is defensive: fenced JSON, prose wrappers, and bad JSON."""

import pytest

from lazyapply.llm import parse_suggestions, LLMError


def test_plain_json():
    raw = '{"fields":[{"id":1,"label":"Email","action":"fill_value","value":"a@b.com","why":"","confidence":0.9}]}'
    out = parse_suggestions(raw)
    assert len(out) == 1
    assert out[0].id == 1 and out[0].action == "fill_value" and out[0].value == "a@b.com"


def test_code_fenced_json():
    raw = "Here you go:\n```json\n{\"fields\":[{\"id\":2,\"action\":\"generate\",\"value\":\"hi\"}]}\n```\nDone."
    out = parse_suggestions(raw)
    assert out[0].id == 2 and out[0].value == "hi"


def test_unknown_action_falls_back_to_skip():
    raw = '{"fields":[{"id":3,"action":"delete_everything","value":""}]}'
    out = parse_suggestions(raw)
    assert out[0].action == "skip"


def test_bad_confidence_is_zero():
    raw = '{"fields":[{"id":4,"action":"skip","confidence":"high"}]}'
    assert parse_suggestions(raw)[0].confidence == 0.0


def test_concatenated_objects_no_wrapper():
    # The exact shape qwen2.5:3b produced live: separate objects, no "fields" key.
    raw = (
        '{"id":1,"label":"Search","action":"skip","value":"","confidence":0.9}\n'
        '{"id":2,"label":"Why us?","action":"generate","value":"I like it","confidence":0.8}'
    )
    out = parse_suggestions(raw)
    assert [s.id for s in out] == [1, 2]
    assert out[1].value == "I like it"


def test_bare_array():
    raw = '[{"id":1,"action":"fill_value","value":"a@b.com"}]'
    assert parse_suggestions(raw)[0].value == "a@b.com"


def test_duplicate_ids_keep_first():
    raw = '{"fields":[{"id":1,"value":"first"},{"id":1,"value":"second"}]}'
    out = parse_suggestions(raw)
    assert len(out) == 1 and out[0].value == "first"


def test_no_json_raises():
    with pytest.raises(LLMError):
        parse_suggestions("I could not do that.")


def test_missing_fields_list_raises():
    with pytest.raises(LLMError):
        parse_suggestions('{"result": "ok"}')


def test_entry_without_id_raises():
    with pytest.raises(LLMError):
        parse_suggestions('{"fields":[{"action":"skip"}]}')
