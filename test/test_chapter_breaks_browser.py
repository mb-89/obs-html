"""Printed chapter boundaries preserve top-level navigation and group short subsections."""
import pytest

from artifacts import artifact_html
from browser.viewer import open_viewer
from documents import chapter, document, heading, node, paragraph, text


LONG_PARAGRAPHS = tuple(paragraph("A long chapter paragraph with enough text to occupy several lines. " * 8)
                        for _ in range(24))


def _short(identifier: str, title: str) -> dict:
    return chapter(identifier, title, heading(1, title), paragraph(f"Text of {title}."))


def _long(identifier: str, title: str) -> dict:
    return chapter(identifier, title, heading(1, title), *LONG_PARAGRAPHS)


def _print_groups(frame) -> list[dict[str, object]]:
    return frame.evaluate("""() => {
        window.dispatchEvent(new Event("beforeprint"));
        return [...document.querySelectorAll(".print-book .paper-sheet")].map((sheet) => ({
            chapter: sheet.dataset.pageChapter,
            headings: [...sheet.querySelectorAll("h1, h2, h3, h4, h5, h6, .paragraph-heading > .heading-name")]
                .map((heading) => heading.textContent.trim()),
            subchapters: [...sheet.querySelectorAll("[data-manifest-chapter]")]
                .map((chapter) => chapter.dataset.manifestChapter),
        }));
    }""")


def _open(tmp_path, reader_browser, source: dict):
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact_html(source), "light")
    assert errors == []
    return frame, errors


@pytest.mark.browser
def test_two_short_top_level_chapters_remain_separate_pages(tmp_path, reader_browser) -> None:
    frame, errors = _open(tmp_path, reader_browser, document(
        "Top-level chapters", _short("first", "First"), _short("second", "Second")))

    pages = [group for group in _print_groups(frame) if group["chapter"] in {"first", "second"}]

    assert [page["chapter"] for page in pages] == ["first", "second"]
    assert [page["headings"] for page in pages] == [["First"], ["Second"]]
    assert errors == []


@pytest.mark.browser
def test_short_appendix_parts_share_a_page(tmp_path, reader_browser) -> None:
    appendix = chapter(
        "appendix", "Appendix", heading(1, "Appendix"), paragraph("Appendix contents."),
        children=(
            _short("miscellaneous", "Miscellaneous"),
            _short("figures", "List of Figures"),
            _short("tables", "List of Tables"),
        ),
    )
    frame, errors = _open(tmp_path, reader_browser, document("Appendix", appendix))

    pages = [group for group in _print_groups(frame) if group["chapter"] == "appendix"]

    assert len(pages) == 1
    assert pages[0]["headings"] == ["Appendix", "Miscellaneous", "List of Figures", "List of Tables"]
    assert pages[0]["subchapters"] == ["miscellaneous", "figures", "tables"]
    assert errors == []


@pytest.mark.browser
def test_short_long_short_subchapters_stay_separate_from_the_long_one(tmp_path, reader_browser) -> None:
    parent = chapter(
        "parent", "Parent", heading(1, "Parent"),
        children=(
            _short("before", "Before"),
            _long("long", "Long"),
            _short("after", "After"),
        ),
    )
    frame, errors = _open(tmp_path, reader_browser, document("Nested chapters", parent))

    pages = [group for group in _print_groups(frame) if group["chapter"] == "parent"]
    before = [index for index, page in enumerate(pages) if "before" in page["subchapters"]]
    long = [index for index, page in enumerate(pages) if "long" in page["subchapters"]]
    after = [index for index, page in enumerate(pages) if "after" in page["subchapters"]]

    assert len(long) > 1
    assert before and after
    assert max(before) < min(long)
    assert max(long) < min(after)
    assert errors == []


@pytest.mark.browser
def test_leaf_chapter_titles_stay_headings_above_tables_and_body_headings(tmp_path, reader_browser) -> None:
    table = {**node("table"), "children": [
        {**node("table-row"), "children": [{**node("table-cell"), "children": [text("Value")]}]},
    ]}
    source = document("Leaves", chapter("parent", "Parent", children=(
        chapter("prose", "Prose", heading(1, "Prose"), paragraph("Introduction."), table),
        chapter("table", "Table", table),
        chapter("context", "Chapter", heading(1, "Chapter"), heading(2, "Context"), paragraph("Details.")),
        chapter("text", "Text", heading(1, "Text"), paragraph("Plain text.")),
    )), metadata={"obsHtml": {"numberedHeadings": True}})
    frame, errors = _open(tmp_path, reader_browser, source)
    evidence = frame.evaluate("""async () => {
        await obsArtifact.activateChapter("prose");
        await obsArtifact.whenChapterReady();
        return ["prose", "table", "context", "text"].map((id) => {
            const section = document.querySelector(`[data-chapter-body] #${id}`);
            const title = section.querySelector("h2");
            const body = section.querySelector(".paragraph-heading");
            return {title: title?.textContent.trim(), body: body?.textContent.trim() || null,
                table: Boolean(section.querySelector("table"))};
        });
    }""")
    assert evidence == [
        {"title": "1.1 Prose", "body": None, "table": True},
        {"title": "1.2 Table", "body": None, "table": True},
        {"title": "1.3 Chapter", "body": "ContextDetails.", "table": False},
        {"title": "1.4 Text", "body": None, "table": False},
    ]
    assert errors == []


@pytest.mark.browser
def test_nested_chapter_navigation_keeps_numbers_when_heading_names_are_hidden(tmp_path, reader_browser) -> None:
    source = document(
        "Nested",
        chapter("first", "First", heading(1, "First"), paragraph("First prose."), children=(
            chapter("first-child", "First child", heading(1, "First child"),
                    heading(2, "Details"), paragraph("Nested prose.")),
        )),
        chapter("second", "Second"),
        metadata={"obsHtml": {"numberedHeadings": True}},
    )
    frame, errors = _open(tmp_path, reader_browser, source)

    evidence = frame.evaluate("""async () => {
        await obsArtifact.activateChapter("first-child");
        await obsArtifact.whenChapterReady();
        const page = document.querySelector("[data-active-chapter]");
        const nested = document.querySelector('[data-chapter-body] #first-child');
        const number = nested.querySelector(".chapter-number");
        const toggle = document.querySelector("[data-heading-names-toggle]");
        toggle.checked = false;
        toggle.dispatchEvent(new Event("change"));
        window.dispatchEvent(new Event("beforeprint"));
        return {
            activePage: page.dataset.chapter,
            nestedExists: Boolean(nested),
            nestedNumber: number?.textContent.trim(),
            navigation: obsArtifact.navigationChapters().map(({slug, chapterNumber}) =>
                [slug, chapterNumber]),
            pages: obsArtifact.exportChapters().map(({slug}) => slug),
            contents: [...document.querySelectorAll(".print-book [data-contents-chapter]")].map((pageNumber) => {
                const link = pageNumber.closest("a");
                return [pageNumber.dataset.contentsChapter, link.querySelector(".chapter-number")?.textContent.trim(),
                    pageNumber.textContent.trim()];
            }),
            sidebarNumbers: [...document.querySelectorAll("[data-toc-link] .chapter-number")]
                .map((item) => item.textContent.trim()),
            nestedOutlineLinks: [...document.querySelectorAll('[data-toc-tree] a[href^="#first-child"]')]
                .map((link) => link.getAttribute("href")),
            headingNameHidden: getComputedStyle(nested.querySelector(".heading-name")).display === "none",
            numberVisible: getComputedStyle(number).display !== "none",
        };
    }""")

    assert evidence == {
        "activePage": "first",
        "nestedExists": True,
        "nestedNumber": "1.1",
        "navigation": [["first", "1"], ["first-child", "1.1"], ["second", "2"]],
        "pages": ["first", "second"],
        "contents": [["first", "1", "4"], ["first-child", "1.1", "4"], ["second", "2", "5"]],
        "sidebarNumbers": ["1", "1.1", "2"],
        "nestedOutlineLinks": ["#first-child"],
        "headingNameHidden": True,
        "numberVisible": True,
    }
    assert errors == []
