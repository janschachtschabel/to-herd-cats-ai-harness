"""The SKILL.md format (agentskills.io; plan M6 decision 11): YAML front matter with
`name` and `description`, then the instructions. Read strictly, written so that it
reads back the same."""

import pytest

from app.modules.skills.format import (
    MAX_CONTENT_CHARS,
    MAX_DESCRIPTION_CHARS,
    SkillFormatError,
    parse_skill_md,
    serialise_skill_md,
    valid_name,
)

GOOD = "---\nname: pdf-tools\ndescription: Work with PDF files.\n---\n# PDF\n\nSteps.\n"


def test_a_good_skill_md_is_read() -> None:
    parsed = parse_skill_md(GOOD)
    assert parsed.name == "pdf-tools"
    assert parsed.description == "Work with PDF files."
    assert parsed.content == "# PDF\n\nSteps.\n"
    assert parsed.ignored == []


def test_the_optional_fields_of_the_format_are_accepted_and_named_as_ignored() -> None:
    text = (
        "---\nname: a\ndescription: d\nlicense: MIT\ncompatibility: any\n"
        "metadata:\n  author: x\n  version: '1.0'\nallowed-tools: Read Grep\n---\nBody\n"
    )
    parsed = parse_skill_md(text)
    assert parsed.ignored == ["allowed-tools", "compatibility", "license", "metadata"]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("# no front matter\n", "frontmatter_invalid"),
        ("---\nname: a\ndescription: d\n", "frontmatter_invalid"),  # never closed
        ("---\n- a\n- b\n---\nBody\n", "frontmatter_invalid"),  # not a mapping
        ("---\nname: [a\n---\nBody\n", "frontmatter_invalid"),  # not YAML
        ("---\nname: a\ndescription: d\nextra: x\n---\nBody\n", "frontmatter_invalid"),
        ("---\nname: a\ndescription: d\nmetadata: x\n---\nBody\n", "frontmatter_invalid"),
        ("---\nname: a\ndescription: d\nmetadata:\n  k: [1]\n---\nB\n", "frontmatter_invalid"),
        ("---\nname: a\ndescription: d\nlicense: [x]\n---\nB\n", "frontmatter_invalid"),
        ("---\nname: a\ndescription: d\n---\n   \n", "content_invalid"),
        ("---\ndescription: d\n---\nBody\n", "name_invalid"),
        ("---\nname: 12\ndescription: d\n---\nBody\n", "name_invalid"),
        ("---\nname: Bad_Name\ndescription: d\n---\nBody\n", "name_invalid"),
        ("---\nname: a--b\ndescription: d\n---\nBody\n", "name_invalid"),
        ("---\nname: -a\ndescription: d\n---\nBody\n", "name_invalid"),
        ("---\nname: a\n---\nBody\n", "description_invalid"),
        ("---\nname: a\ndescription: '  '\n---\nBody\n", "description_invalid"),
        ("---\nname: a\ndescription: 2026-01-01\n---\nBody\n", "description_invalid"),
        ("---\nname: a\ndescription: !!python/object:os.system x\n---\nB\n", "frontmatter_invalid"),
        ("---\nname: &x a\ndescription: *x\n---\nBody\n", "frontmatter_invalid"),
    ],
)
def test_anything_else_is_refused_with_a_reason(text: str, reason: str) -> None:
    with pytest.raises(SkillFormatError) as caught:
        parse_skill_md(text)
    assert caught.value.reason == reason


def test_bounds() -> None:
    long_description = "x" * (MAX_DESCRIPTION_CHARS + 1)
    with pytest.raises(SkillFormatError) as caught:
        parse_skill_md(f"---\nname: a\ndescription: {long_description}\n---\nB\n")
    assert caught.value.reason == "description_invalid"
    body = "y" * (MAX_CONTENT_CHARS + 1)
    with pytest.raises(SkillFormatError) as caught:
        parse_skill_md(f"---\nname: a\ndescription: d\n---\n{body}")
    assert caught.value.reason == "content_invalid"
    huge = "---\nname: a\ndescription: d\n" + "# c\n" * 5000 + "---\nB\n"
    with pytest.raises(SkillFormatError) as caught:
        parse_skill_md(huge)
    assert caught.value.reason == "frontmatter_invalid"


def test_names() -> None:
    assert valid_name("a")
    assert valid_name("pdf-tools-2")
    assert valid_name("a" * 64)
    for bad in ("", "a" * 65, "A", "a_b", "a--b", "-a", "a-", "ä", "a b", "a\x00"):
        assert not valid_name(bad), bad


@pytest.mark.parametrize(
    "description",
    ["Plain.", "Colons: and # hashes", "'quotes' and \"double\"", "Zeilen\nUmbruch", "- dash"],
)
def test_written_skills_read_back_the_same(description: str) -> None:
    content = "---\nnot front matter\n---\nBody ü\n"
    text = serialise_skill_md("my-skill", description, content)
    parsed = parse_skill_md(text)
    assert (parsed.name, parsed.description, parsed.content) == ("my-skill", description, content)
