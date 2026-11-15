"""The line-based three-way merge of a proposal (plan M6 decision 8): base, the
proposed text and the page's current text. Clean merges give the text; overlapping
changes give conflict regions, never a silent choice."""

from app.modules.proposals.merge import merge3


def test_untouched_current_takes_the_proposal() -> None:
    result = merge3("a\nb\nc", "a\nB\nc", "a\nb\nc")
    assert result.clean and result.text == "a\nB\nc"


def test_changes_in_different_places_merge() -> None:
    base = "title\n\none\ntwo\nthree\nfour\n"
    proposed = "title\n\nONE\ntwo\nthree\nfour\n"
    current = "title\n\none\ntwo\nthree\nFOUR\nfive\n"
    result = merge3(base, proposed, current)
    assert result.clean
    assert result.text == "title\n\nONE\ntwo\nthree\nFOUR\nfive\n"
    assert [s.kind for s in result.segments] == ["clean"]


def test_the_same_change_on_both_sides_is_no_conflict() -> None:
    result = merge3("a\nb\nc", "a\nX\nc", "a\nX\nc")
    assert result.clean and result.text == "a\nX\nc"


def test_overlapping_changes_are_a_conflict() -> None:
    result = merge3("a\nb\nc\nd", "a\nproposed\nc\nd", "a\ncurrent\nc\nD")
    assert not result.clean
    assert result.text is None
    kinds = [s.kind for s in result.segments]
    assert kinds == ["clean", "conflict", "clean"]
    conflict = result.segments[1]
    assert conflict.base == ["b"]
    assert conflict.proposed == ["proposed"]
    assert conflict.current == ["current"]
    assert result.segments[0].lines == ["a"]
    assert result.segments[2].lines == ["c", "D"]
    assert len(result.conflicts) == 1


def test_a_deletion_against_an_edit_is_a_conflict() -> None:
    result = merge3("a\nb\nc", "a\nc", "a\nbb\nc")
    assert not result.clean
    (conflict,) = result.conflicts
    assert (conflict.base, conflict.proposed, conflict.current) == (["b"], [], ["bb"])


def test_both_appending_at_the_end_conflicts() -> None:
    result = merge3("a", "a\nx", "a\ny")
    assert not result.clean
    (conflict,) = result.conflicts
    assert (conflict.proposed, conflict.current) == (["x"], ["y"])


def test_trailing_newlines_and_empty_texts_round_trip() -> None:
    assert merge3("", "new\n", "").text == "new\n"
    assert merge3("a\n", "a\n", "a\nb\n").text == "a\nb\n"
    assert merge3("a", "a\n", "a").text == "a\n"
    assert merge3("x\n", "", "x\n").text == ""


def test_insertions_next_to_each_other_in_different_spots() -> None:
    base = "1\n2\n3\n4\n5\n6"
    proposed = "0\n1\n2\n3\n4\n5\n6"
    current = "1\n2\n3\n4\n5\n6\n7"
    assert merge3(base, proposed, current).text == "0\n1\n2\n3\n4\n5\n6\n7"
