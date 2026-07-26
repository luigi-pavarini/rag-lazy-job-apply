"""Deterministic identity matching from a facts.md fixture (dummy data only)."""

from lazyapply.identity import load_identity, match_value, deterministic_suggestions
from lazyapply.extract import parse_form_dict


FACTS = """# Facts
- Full name: Jane Ada Doe
- First name: Jane
- Last name (sobrenome): Ada
- Email (primary): jane@example.com
- Phone: +55 (11) 90000-0000
- LinkedIn: https://www.linkedin.com/in/jane-ada-doe
- GitHub: https://github.com/jane-doe
- City / State / Country: São Paulo, SP, Brazil
- Salary expectation (Brazil): R$1,000/month (BRL), negotiable
"""


def _facts(tmp_path):
    (tmp_path / "facts.md").write_text(FACTS)
    return load_identity(tmp_path)


def test_parse(tmp_path):
    f = _facts(tmp_path)
    assert f["email"] == "jane@example.com"
    assert f["linkedin"].endswith("jane-ada-doe")
    assert f["phone"] == "+55 (11) 90000-0000"  # no trailing newline
    assert "\n" not in f["phone"]


def test_matching(tmp_path):
    f = _facts(tmp_path)
    assert match_value("LinkedIn", f).endswith("jane-ada-doe")
    assert match_value("E-mail", f) == "jane@example.com"
    assert match_value("Nome", f) == "Jane"           # explicit first name
    assert match_value("Sobrenome", f) == "Ada"       # explicit last name
    assert match_value("Company name", f) is None     # not the person's name
    assert match_value("CPF", f) is None              # not in facts -> ask


def test_deterministic_suggestions(tmp_path):
    f = _facts(tmp_path)
    form = parse_form_dict({
        "fields": [
            {"id": 1, "tag": "input", "type": "email", "label": "E-mail",
             "required": True, "value": "", "options": [], "box": {}},
            {"id": 2, "tag": "input", "type": "url", "label": "LinkedIn",
             "required": True, "value": "", "options": [], "box": {}},
            {"id": 3, "tag": "textarea", "type": "textarea", "label": "Why us?",
             "required": True, "value": "", "options": [], "box": {}},
        ]
    })
    det = deterministic_suggestions(form, f)
    assert set(det) == {1, 2}                       # question (3) not matched
    assert det[1].value == "jane@example.com"
    assert det[2].action == "fill_value"
