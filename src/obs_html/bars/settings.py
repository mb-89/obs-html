from obs_html.bars import BarDefinition


def render() -> str:
    return (
        '<label class="settings-appearance">Appearance'
        '<span class="settings-appearance-control"><span data-theme-icon></span>'
        '<select data-theme-select aria-label="Appearance">'
        '<option value="system">System</option>'
        '<option value="light">Light</option>'
        '<option value="dark">Dark</option>'
        '</select>'
        '</span></label>'
        '<div class="settings-page-export">'
        '<label class="settings-pages" data-hover-help="View the content on the same sheets used for PDF export.">'
        '<input type="checkbox" data-pages-toggle> Show as pages</label>'
        '<button type="button" data-export-pdf aria-describedby="pdf-destination-guidance" '
        'data-hover-help="Uses light colors and the global filter. '
        'Keep the HTML beside the PDF for links to omitted notes.">Export to PDF</button>'
        '<small id="pdf-destination-guidance" class="settings-pdf-guidance">'
        'Choose Save as PDF, not Microsoft Print to PDF.</small>'
        '</div>'
        '<div class="settings-source-exports" data-source-exports hidden>'
        '<button type="button" data-source-download '
        'data-hover-help="Save the embedded ZIP using your browser’s download location.">Download source ZIP</button>'
        '<button type="button" data-source-attach '
        'data-hover-help="Choose a PDF saved from this HTML; attach the ZIP locally and download a new PDF.">'
        'Attach source ZIP to PDF</button></div>'
        '<p data-export-status role="status" hidden></p>'
    )


BAR = BarDefinition(
    key="settings",
    label="Settings + exports",
    icon="settings",
    help="Appearance, pages, and PDF export",
    order=50,
    render=render,
)
