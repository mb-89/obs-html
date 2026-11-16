"""Timeline figures in the reader: rows in their order, the drill-down, the filter, the anchor and
a phone's width (timeline-figure.js; artifact-ui.md, Timeline figures; obs input-model, Timeline
figures). The pure model's every rule is test/timeline.test.js; these check what the page draws.

Reader: whoever changes how a timeline figure is drawn, opened, filtered or anchored.

The artifact is built through the core once per run from the vault ``_vault`` writes: a chapter
whose figure has 2 lanes, records on 30 days across a year end, an anchored Today band, 3 planned
days, 2 end bands and one release marker, then a block after the figure; and a chapter whose
figure's query selects nothing.
"""
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from conftest import built_once
from obs_html import cli

pytestmark = pytest.mark.browser
PLAN, EMPTY = "plan", "empty"
FIGURE = """```figure
version: 1
kind: timeline
caption: Work by team
alt: Work by day and team
content:
  records: {{where: [{{field: kind, equals: {kind}}}]}}
  date: when
  lane: team
  today: 2026-01-08
  lanes: [Build, Review]
  band: state
  bands:
    - {{value: doing, label: Today, at: today}}
    - {{value: next, label: Next, at: end}}
    - {{value: later, label: Later, at: end}}
  anchor: today
  label: short
  text: summary
  flags: flags
  marker: release
```
"""
PAST = [(date(2025, 12, 10) + timedelta(days=index)).isoformat() for index in range(30)]
PLANNED = ["2026-01-12", "2026-01-20", "2026-02-03"]
ROWS = [*PAST[:22], "2026", *PAST[22:], "band:doing", *PLANNED, "band:next", "band:later"]
"""The rows top to bottom, a year divider by its year: 22 December days, then 8 January days."""


def _vault(root: Path) -> None:
    (root / "work").mkdir(parents=True)
    # The reader's filter selects records, not chapters, so the chapter stays as it filters.
    (root / "manifest.md").write_text(
        "---\ntitle: Timelines\nobsHtml: {query: {scope: records, where: [{field: kind, equals: work-item}]}}\n---\n"
        "- [[plan]]\n- [[empty]]\n", encoding="utf-8")
    (root / "plan.md").write_text(
        "# Plan\n\nThe plan of two teams; see [[#^closing|the closing words]].\n\n" + FIGURE.format(kind="work-item")
        + "\n## After\n\n" + "A paragraph after the figure. " * 8 + "^closing\n", encoding="utf-8")
    (root / "empty.md").write_text("# Empty\n\n" + FIGURE.format(kind="nothing"), encoding="utf-8")
    records = [(day, "Build" if index % 2 else "Review", "") for index, day in enumerate(PAST)]
    records += [(day, "Build", "") for day in PLANNED] + [("", "Review", "doing"), ("", "Build", "next"),
                                                          ("", "Review", "later")]
    for index, (day, team, state) in enumerate(records):
        fields = f"when: {day}\n" if day else f"state: {state}\n"
        flags = "flags: [{label: review, tone: warning}]\n" if index == 0 else ""
        (root / "work" / f"item-{index:02d}.md").write_text(
            f"---\nkind: work-item\n{fields}team: {team}\nshort: Item {index}\nsummary: What item {index} did.\n"
            f"{flags}---\n# Item {index}\n", encoding="utf-8")
    (root / "work" / "release.md").write_text(
        "---\nkind: work-item\nwhen: 2026-01-05\nteam: Build\nshort: Release one\nrelease: true\n"
        "obs: {document: false}\n---\n# Release one\n", encoding="utf-8")


@pytest.fixture(scope="module")
def timeline(tmp_path_factory) -> Path:
    def build(folder: Path) -> None:
        _vault(folder / "vault")
        subprocess.run([sys.executable, "-m", "obs.document", "--source", str(folder / "vault" / "manifest.md"),
                        "--document", str(folder / "timeline.json")], check=True)
        assert cli.main([str(folder / "timeline.json"), str(folder / "timeline.html")]) == 0

    return built_once(tmp_path_factory, "timeline-figure", build) / "timeline.html"


def _open(browser, artifact: Path, chapter: str, width: int = 1200, height: int = 900):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate(f"obsArtifact.activateChapter('{chapter}')")
    page.wait_for_selector(f"[data-active-chapter] [data-figure-kind='timeline'] {'.timeline' if chapter == PLAN else '.timeline-empty'}")
    return page, errors


ROW_KEYS = """() => [...document.querySelectorAll('[data-active-chapter] .timeline > *')].slice(1)
    .map(node => node.classList.contains('timeline-year') ? node.textContent : node.dataset.timelineRow)"""
ANCHOR = """() => {
    const scroller = document.querySelector('[data-chapter-scroll]').getBoundingClientRect();
    const row = document.querySelector('[data-active-chapter] [data-timeline-anchor]').getBoundingClientRect();
    return {top: row.top, bottom: row.bottom, viewTop: scroller.top, viewBottom: scroller.bottom,
            scrolled: document.querySelector('[data-chapter-scroll]').scrollTop};
}"""


def test_the_rows_stand_in_their_order_with_one_year_divider_and_planned_days_hollow(reader_browser, timeline) -> None:
    page, errors = _open(reader_browser, timeline, PLAN)

    assert page.evaluate(ROW_KEYS) == ROWS
    assert page.locator("[data-active-chapter] .timeline-year").count() == 1
    shown = page.evaluate("""() => {
        const row = key => document.querySelector(`[data-timeline-row="${key}"]`);
        const cells = key => [...row(key).querySelectorAll('.timeline-cell')].map(cell => cell.className.split('--')[1]);
        return {lanes: [...document.querySelectorAll('.timeline-lane-name')].map(node => node.textContent),
                past: cells('2026-01-05'), planned: cells('2026-01-12'), band: cells('band:doing'),
                italic: getComputedStyle(row('2026-01-12').querySelector('.timeline-when')).fontStyle,
                marker: row('2026-01-05').querySelector('.timeline-cell').querySelector('.timeline-marker')?.textContent,
                count: row('2026-01-05').querySelector('.timeline-cell').querySelector('.timeline-count')?.textContent,
                anchor: document.querySelector('[data-timeline-anchor]').dataset.timelineRow,
                height: Math.min(...[...document.querySelectorAll('.timeline-summary')].map(node => node.getBoundingClientRect().height)),
                styled: document.querySelectorAll('[data-active-chapter] .timeline-figure [style]').length};
    }""")
    assert shown.pop("height") >= 2.4 * 16 - 0.5, "each row is at least 2.4rem tall"
    assert shown == {"lanes": ["Build", "Review"], "past": ["past", "past"], "planned": ["planned", "none"],
                     "band": ["none", "band"], "italic": "italic", "marker": "Release one", "count": None,
                     "anchor": "band:doing", "styled": 0}
    assert errors == []


def test_the_today_row_is_in_view_when_the_chapter_opens_and_a_block_link_wins(reader_browser, timeline) -> None:
    page, errors = _open(reader_browser, timeline, PLAN, 1200, 700)
    page.wait_for_function("document.querySelector('[data-chapter-scroll]').scrollTop > 0")

    opened = page.evaluate(ANCHOR)
    assert opened["viewTop"] <= opened["top"] and opened["bottom"] <= opened["viewBottom"], opened
    middle = (opened["viewTop"] + opened["viewBottom"]) / 2
    assert abs((opened["top"] + opened["bottom"]) / 2 - middle) < 2, f"the anchor row is centred: {opened}"

    page.evaluate("document.querySelector('[data-chapter-scroll]').scrollTop = 0")
    page.locator("[data-active-chapter] a.internal-link", has_text="the closing words").click()
    page.wait_for_function("document.querySelector('[data-chapter-scroll]').scrollTop > 0")
    page.evaluate("() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))")
    landed = page.evaluate("""() => {
        const scroller = document.querySelector('[data-chapter-scroll]').getBoundingClientRect();
        const block = document.getElementById('plan--block-closing').getBoundingClientRect();
        return {top: block.top, viewTop: scroller.top, viewBottom: scroller.bottom};
    }""")
    assert landed["viewTop"] - 1 <= landed["top"] <= landed["viewBottom"], landed
    assert errors == []


def test_opening_a_row_lists_its_items_per_lane_and_an_item_shows_its_text_and_note_link(reader_browser, timeline) -> None:
    page, errors = _open(reader_browser, timeline, PLAN)

    page.locator('[data-timeline-row="2025-12-10"] > summary').click()
    page.locator('[data-timeline-row="2026-01-05"] > summary').click()
    page.locator('[data-timeline-row="2025-12-10"] .timeline-item > summary').click()
    shown = page.evaluate("""() => {
        const list = key => [...document.querySelector(`[data-timeline-row="${key}"] .timeline-list`).children]
            .map(node => node.matches('ul') ? [...node.querySelectorAll('summary')].map(item => item.textContent) : node.textContent);
        const item = document.querySelector('[data-timeline-row="2025-12-10"] .timeline-item');
        return {first: list('2025-12-10'), release: list('2026-01-05'), open: item.open,
                text: item.querySelector('.timeline-text').textContent,
                link: [item.querySelector('a.internal-link').textContent, item.querySelector('a.internal-link').getAttribute('href')],
                flag: getComputedStyle(item.querySelector('.timeline-flag--warning')).color,
                warning: getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim()};
    }""")
    assert shown["first"] == ["Review", ["Item 0 review"]]
    assert shown["release"] == ["Build", "Release one", "Review", ["Item 26"]], "a lane's markers, then its items"
    assert shown["open"] and shown["text"] == "What item 0 did."
    assert shown["link"][0] == "Open Item 0" and shown["link"][1].startswith("#")
    # The note is outside the reading order, so it opens in the floating window, as any such link does.
    with page.expect_popup() as opened:
        page.locator('[data-timeline-row="2025-12-10"] .timeline-item a.internal-link').click()
    window = opened.value
    window.wait_for_selector(".guided-card-title:has-text('Item 0')")
    window.close()
    assert errors == []


def test_a_global_filter_that_removes_a_lanes_records_drops_them_from_the_counts_and_the_lists(reader_browser, timeline) -> None:
    page, errors = _open(reader_browser, timeline, PLAN)
    page.locator('[data-timeline-row="2025-12-10"] > summary').click()
    counts = """() => [...document.querySelectorAll('[data-active-chapter] .timeline-row')].map(row =>
        [...row.querySelectorAll('.timeline-cell')].map(cell => Number(cell.querySelector('.timeline-count')?.textContent || 0)))
        .reduce((sums, row) => sums.map((sum, index) => sum + row[index]), [0, 0])"""
    assert page.evaluate(counts) == [19, 17]

    page.evaluate("obsArtifact.setFilter(obsQuery.compile('team:Build'))")
    page.wait_for_function("!document.querySelector('[data-timeline-row=\"band:doing\"] .timeline-count')")

    assert page.evaluate(counts) == [19, 0]
    assert page.evaluate("[...document.querySelectorAll('.timeline-lane-name')].map(node => node.textContent)") == ["Build", "Review"]
    assert page.locator('[data-timeline-row="2025-12-10"]').count() == 0, "a day left without records has no row"
    assert page.locator(".timeline-list-lane", has_text="Review").count() == 0
    page.evaluate("obsArtifact.setFilter(obsQuery.compile(''))")
    page.wait_for_selector('[data-timeline-row="2025-12-10"][open]')  # The reader's opened row stays open.
    assert errors == []


def test_print_shows_the_rows_the_reader_opened_from_the_unfiltered_records(reader_browser, timeline) -> None:
    page, errors = _open(reader_browser, timeline, PLAN)
    page.locator('[data-timeline-row="2025-12-10"] > summary').click()
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('team:Build'))")
    page.wait_for_function("!document.querySelector('[data-timeline-row=\"2025-12-10\"]')")

    printed = page.evaluate("""async () => {
        let shown;
        window.print = () => {
            dispatchEvent(new Event('beforeprint'));
            const copy = document.querySelector('.print-book [data-figure-kind="timeline"]');
            shown = {rows: copy.querySelectorAll('.timeline-row').length,
                     open: [...copy.querySelectorAll('.timeline-row')].filter(row => row.open).map(row => row.dataset.timelineRow)};
        };
        await obsPages.exportPDF();
        dispatchEvent(new Event('afterprint'));
        await new Promise(requestAnimationFrame);
        return shown;
    }""")

    assert printed == {"rows": len(ROWS) - 1, "open": ["2025-12-10"]}
    assert page.locator('[data-active-chapter] [data-timeline-row="2025-12-10"]').count() == 0, "the reader's view is kept"
    assert errors == []


def test_an_empty_selection_shows_one_sentence_and_no_grid(reader_browser, timeline) -> None:
    page, errors = _open(reader_browser, timeline, EMPTY)

    figure = page.locator("[data-active-chapter] [data-figure-kind='timeline']")
    assert figure.locator(".timeline-figure").inner_text() == "No records to show."
    assert figure.locator(".timeline, .timeline-row, .timeline-lanes").count() == 0
    assert figure.locator("figcaption").inner_text().endswith("Work by team")
    assert errors == []


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_at_390_by_844_nothing_scrolls_sideways_with_every_row_open(phone_browser, timeline, appearance) -> None:
    page, errors = _open(phone_browser, timeline, PLAN, 390, 844)
    page.evaluate("""value => {
        const select = document.querySelector('[data-theme-select]');
        select.value = value;
        select.dispatchEvent(new Event('change'));
    }""", appearance)
    page.evaluate("document.querySelectorAll('.timeline-row, .timeline-item').forEach(node => { node.open = true; })")

    widths = page.evaluate("""() => ({scroll: document.scrollingElement.scrollWidth, client: document.scrollingElement.clientWidth,
        chapter: [document.querySelector('[data-chapter-scroll]').scrollWidth, document.querySelector('[data-chapter-scroll]').clientWidth],
        theme: document.documentElement.dataset.theme,
        sideways: [...document.querySelectorAll('[data-active-chapter] *')].filter(node => node.scrollWidth > node.clientWidth + 1
            && ['auto', 'scroll'].includes(getComputedStyle(node).overflowX)).map(node => node.className)})""")
    print(f"390x844 {appearance}: scrollWidth {widths['scroll']}, clientWidth {widths['client']}; "
          f"chapter scrollWidth {widths['chapter'][0]}, clientWidth {widths['chapter'][1]}")
    assert widths["theme"] == appearance
    assert widths["scroll"] <= widths["client"] and widths["chapter"][0] <= widths["chapter"][1], widths
    assert widths["sideways"] == []
    assert errors == []
