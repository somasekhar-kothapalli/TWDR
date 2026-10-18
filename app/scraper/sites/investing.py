"""Investing.com economic-calendar scraper. The table is JS-rendered and the
site blocks plain HTTP, so it needs a real browser via scraper.browser.

Rows match tradingeconomics.py's exactly (see scraper.utils.calendar):
`release_date` (DD-MM-YYYY), IST `time`, float million-barrel values.
"""
from datetime import datetime

from ..utils.base import CalendarScraper
from ..utils.calendar import format_date, gmt_to_ist, to_mb_suffixed
from ..utils.cli import run_cli


INVESTING_BASE = "https://in.investing.com/economic-calendar/"
OCCURRENCE_TABLE_SELECTOR = 'table[data-test="occurrence-table"]'
MAX_SHOW_MORE_CLICKS = 120  # 10 rows each: about 23 years of weekly releases
SHOW_MORE_JS = r"""async ([sel, stop, maxClicks]) => {
  const rows = () => document.querySelectorAll(sel + ' tbody tr');
  const control = () => [...document.querySelectorAll('div')].find(d => d.children.length === 0 && d.textContent.trim() === 'Show More');
  const oldest = () => {  // the last row's date 'DD-MM-YYYY' as a number YYYYMMDD
    const r = rows(); const cell = r.length ? r[r.length - 1].querySelector('td') : null;
    const m = cell ? cell.textContent.trim().match(/^(\d\d)-(\d\d)-(\d{4})$/) : null;
    return m ? Number(m[3] + m[2] + m[1]) : null;
  };
  let prev = rows().length, stale = 0;
  for (let i = 0; i < maxClicks; i++) {
    const c = control(); const d = oldest();
    if (!c || (d !== null && d <= stop)) break;
    c.click();
    await new Promise(r => setTimeout(r, 700));
    const n = rows().length;
    if (n === prev) { if (++stale >= 4) break; } else { stale = 0; prev = n; }
  }
  return rows().length;
}"""


class InvestingCalendarScraper(CalendarScraper):
    """Investing.com economic-calendar occurrence tables.

        with InvestingCalendarScraper() as scraper:
            row = scraper.fetch_release("eia-crude-oil-inventories-75", "23-09-2026")

    Response shape is defined in scraper.utils.base. investing.com rate-limits
    hard, so page loads are spaced page_gap_s (default 10s) apart.
    """

    base_url = INVESTING_BASE
    wait_selector = OCCURRENCE_TABLE_SELECTOR
    page_gap_s = 10
    session_gap_s = 60  # pause between separate browser sessions (it 403/429s back-to-back ones)
    show_more_until = None  # a date: click "Show More" (10 older releases per click) until the oldest row is on or before it

    def after_load(self, page):
        """Expand the history table when `show_more_until` is set. The control under the table is a plain <div> reading
        "Show More" (not a <button>: the page's only <button> of that name expands the description); a JS click on it
        works in headless Chromium, a Playwright locator click did nothing. It stops at the date, when the control is
        gone, or after 4 clicks that add no row."""
        if self.show_more_until is None:
            return
        stop = int(self.show_more_until.strftime("%Y%m%d"))
        page.evaluate(SHOW_MORE_JS, [OCCURRENCE_TABLE_SELECTOR, stop, MAX_SHOW_MORE_CLICKS])

    def parse_rows(self, soup):
        table = soup.find("table", {"data-test": "occurrence-table"})
        tbody = table.find("tbody") if table is not None else None
        rows = [parse_row(r) for r in tbody.find_all("tr")] if tbody is not None else []
        return [r for r in rows if r is not None]

    def parse_stats(self, soup, rows):
        return parse_stats(soup)


def parse_row(row):
    """One <tr> from the occurrence table -> a dict, or None if the row
    doesn't have the expected cells (e.g. a header/spacer row).
    """
    cells = row.find_all("td")
    if len(cells) < 5:
        return None

    date_str = cells[0].get_text(strip=True)
    try:
        release_date = datetime.strptime(date_str, "%d-%m-%Y").date()
    except ValueError:
        release_date = None

    return {
        "release_date": format_date(release_date),
        "time": gmt_to_ist(cells[1].get_text(strip=True)),
        "actual": to_mb_suffixed(cells[2].get_text(strip=True)),
        "consensus": to_mb_suffixed(cells[3].get_text(strip=True)),
        "previous": to_mb_suffixed(cells[4].get_text(strip=True)),
    }


def _label_value(soup, label_text):
    """Find a '<span>label</span> ... <span dir="ltr">value</span>' pair
    by the label's exact text. The page's "Latest Release" summary widget
    has no stable id/data-test attribute (Tailwind utility classes only,
    verified live 2026-09-17), so matching by label text is the resilient
    hook - not the class names, which can change on any redeploy. Returns
    None if the label or a following value span isn't present.
    """
    label = soup.find("span", string=lambda s: bool(s) and s.strip() == label_text)
    if label is None:
        return None
    value_span = label.find_next("span", attrs={"dir": "ltr"})
    return value_span.get_text(strip=True) if value_span else None


def parse_stats(soup):
    """The "Latest Release" summary widget above the occurrence table:
    Actual/Forecast/Previous for the most recent report (investing.com's
    "Forecast" is our `consensus`). Returns
    {actual_mb, consensus_mb, previous_mb}, all None if the widget isn't
    present on this page.
    """
    return {
        "actual_mb": to_mb_suffixed(_label_value(soup, "Actual") or ""),
        "consensus_mb": to_mb_suffixed(_label_value(soup, "Forecast") or ""),
        "previous_mb": to_mb_suffixed(_label_value(soup, "Previous") or ""),
    }


if __name__ == "__main__":
    run_cli(InvestingCalendarScraper, "eia-crude-oil-inventories-75")
