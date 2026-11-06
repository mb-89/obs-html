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
