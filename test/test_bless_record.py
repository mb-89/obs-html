"""The answered and the outdated record of a chapter that asks for a bless (bless_record.py).

Reader: whoever changes how obs-html shows an answer obs-document --answers put into the Document.
test/test_bless_browser.py shows the answered record in the artifact; this module the outdated one.
"""
from obs_html.bless_record import record_html
from test_features import with_bless

VERDICT = {"chapter": "one", "version": "1" * 64, "verdict": "decline", "comment": "Not <yet>."}


def _chapter(key: str) -> dict:
    chapter = with_bless()["chapters"][0]
    chapter["bless"][key] = VERDICT
    return chapter


def test_an_answer_shows_read_only_and_an_outdated_one_says_the_chapter_asks_again() -> None:
    answered, outdated = record_html(_chapter("answer")), record_html(_chapter("outdated"))

    assert 'data-bless-record="answer"' in answered and "Declined" in answered and "Not &lt;yet&gt;." in answered
    assert 'data-bless-record="outdated"' in outdated and "the chapter changed after it was answered" in outdated
    assert record_html(with_bless()["chapters"][0]) == ""


def test_the_record_names_the_picked_option_by_the_short_name_the_document_carries() -> None:
    chapter = _chapter("answer")
    chapter["bless"]["answer"] = {**VERDICT, "verdict": "pick", "pick": {"option": "B"}}
    matrix = {"criteria": [{"key": "cost", "weight": 1, "better": "lower"}],
              "candidates": [{"key": "a", "label": "One"}, {"key": "b", "label": "Two", "short": "Two"},
                             {"key": "c", "label": "Three"}]}
    figure = {"type": "figures", "attrs": {"kind": "pugh"},
              "children": [{"type": "pugh", "attrs": {"matrix": matrix, "shortNames": ["One", "Second", None]},
                            "children": []}]}
    chapter["content"].append(figure)
    picked_c = {**chapter, "bless": {**chapter["bless"], "answer": {**VERDICT, "verdict": "pick", "pick": {"option": "C"}}}}

    # The core resolved the names (obs input-model, Pugh decision figures); the record keeps no rule of its own.
    assert "Picked B · Second" in record_html(chapter)
    assert "Picked C<" in record_html(picked_c)


def test_the_record_names_none_of_the_above() -> None:
    chapter = _chapter("answer")
    chapter["bless"]["answer"] = {**VERDICT, "verdict": "pick", "pick": {"figure": "choice", "option": "none"}}

    assert '<span data-bless-record-verdict>None of the above</span>' in record_html(chapter)


def test_a_comment_with_no_verdict_shows_and_says_the_chapter_asks_still() -> None:
    """obs input-model, Answers: an entry of chapter, version and comment alone answers nothing."""
    chapter = with_bless()["chapters"][0]
    chapter["bless"]["comment"] = {"chapter": "one", "version": "1" * 64, "comment": "Only <a> thought."}

    shown = record_html(chapter)
    assert 'data-bless-record="comment"' in shown and "the chapter asks still" in shown
    assert "Only &lt;a&gt; thought." in shown and "Verdict" not in shown


def test_the_record_names_the_readers_vetoes_lifted_vetoes_and_datum() -> None:
    """artifact-ui.md, The reader's vetoes and datum: the engine's changes beyond weights and marks
    are part of the record, each option by its letter and short name."""
    chapter = _chapter("answer")
    matrix = {"criteria": [{"key": "cost", "weight": 1, "better": "lower"}],
              "candidates": [{"key": "a", "label": "One"}, {"key": "b", "label": "Two"}, {"key": "c", "label": "Three"}]}
    chapter["content"].append({"type": "figures", "attrs": {"kind": "pugh"}, "children": [
        {"type": "pugh", "attrs": {"matrix": matrix, "shortNames": ["One", "Two", None]}, "children": []}]})
    chapter["bless"]["answer"] = {**VERDICT, "figures": {"choice": {
        "vetoes": ["A"], "lifts": {"C": ["given", "gate1"]}, "datum": "B", "winner": "C"}}}
    record = record_html(chapter)

    assert "<li>A · One vetoed</li>" in record
    assert "<li>Veto of C lifted: the fence&#x27;s verdict that it does not fit</li>" in record
    assert "<li>Veto of C lifted: gate 2</li>" in record
    assert "<li>Datum: B · Two</li>" in record and "<li>Winner with these changes: C</li>" in record
