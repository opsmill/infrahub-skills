"""Every docs.infrahub.app link the skills cite must still resolve.

The skills point agents at docs.infrahub.app for the points they do not
cover themselves, and `workflow-information-priority.md` sends them to the
`llms.txt` index when a skill is silent. Both are references to a surface
this repository does not own: the docs site is restructured independently,
and a moved page turns a citation into a 404 with nothing here noticing.
Three links had already died that way (`backup/guides/...` and
`topics/menu/`), cited from 21 files between them.

This is reference drift rather than model behaviour, so it is asserted
against the live site instead of through an eval: it fails on what has
drifted, and again the next time upstream moves. Two directions:

- every docs URL written under `skills/` resolves, after redirects;
- every `## <section>` heading the information-priority rule tells agents
  to look for in `llms.txt` exists there.

The module skips when docs.infrahub.app cannot be reached at all, so an
offline run does not report a network outage as drift.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
RULE = SKILLS / "infrahub-common" / "rules" / "workflow-information-priority.md"
DOCS = "https://docs.infrahub.app"
INDEX = f"{DOCS}/llms.txt"
TIMEOUT_SECONDS = 20

# A URL ends at whitespace, a closing bracket, a quote, or a backtick; a
# trailing full stop or comma is sentence punctuation, not part of the path.
_URL = re.compile(r"https://docs\.infrahub\.app/[^\s)\]>\"'`]*")
_SECTION = re.compile(r"`(## [a-z0-9-]+)`")


class _FollowPermanentRedirect(urllib.request.HTTPRedirectHandler):
    """Follow HTTP 308 on every supported Python, not only 3.11 and later.

    docs.infrahub.app answers a path without its trailing slash (and some
    with one) with a 308. `urllib` learned to follow 308 in Python 3.11; on
    3.10 it raises `HTTPError(308)`, which would report a live page as
    dead. A 308 is a 307 that is also permanent, so it is followed the same
    way.
    """

    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Treat 308 as 307, which every supported `urllib` redirects."""
        if code == 308:
            code = 307
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_FollowPermanentRedirect)


def _fetch(url: str) -> tuple[int, str]:
    """GET a URL, following redirects, and return its status and body.

    Args:
        url: The absolute URL to fetch.

    Returns:
        The final HTTP status code and the decoded response body (empty on
        an HTTP error).
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "infrahub-skills-tests"}
    )
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""


def _cited_urls() -> list[str]:
    """Collect every distinct docs URL written under `skills/`.

    Returns:
        Sorted URLs with anchors and trailing punctuation removed. The bare
        site root and `...` placeholders are dropped, since neither names a
        page.
    """
    urls: set[str] = set()
    for path in SKILLS.rglob("*"):
        if path.suffix not in {".md", ".py", ".yaml", ".yml"} or not path.is_file():
            continue
        for match in _URL.findall(path.read_text(encoding="utf-8")):
            url = match.split("#", 1)[0].rstrip(".,;:")
            if url.rstrip("/") == DOCS or "..." in url:
                continue
            urls.add(url)
    return sorted(urls)


@pytest.fixture(scope="module")
def index_text() -> str:
    """Fetch `llms.txt` once, skipping the module when the site is unreachable."""
    try:
        status, body = _fetch(INDEX)
    except (urllib.error.URLError, TimeoutError) as error:
        pytest.skip(f"{DOCS} unreachable: {error}")
    assert status == 200, f"{INDEX} returned {status}"
    return body


def test_skills_cite_docs_urls() -> None:
    """Guard the scan itself: an empty URL list would pass vacuously."""
    assert len(_cited_urls()) > 10


def test_every_cited_docs_url_resolves(index_text: str) -> None:
    """A cited page that 404s sends the agent to a dead end it trusts."""
    del index_text  # requested only so an unreachable site skips this test
    urls = _cited_urls()
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = dict(
            zip(urls, pool.map(lambda url: _fetch(url)[0], urls), strict=True)
        )
    dead = {url: status for url, status in statuses.items() if status != 200}
    assert not dead, f"docs.infrahub.app links that no longer resolve: {dead}"


def test_rule_sections_exist_in_index(index_text: str) -> None:
    """The headings the rule tells agents to search for must be in llms.txt."""
    named = _SECTION.findall(RULE.read_text(encoding="utf-8"))
    assert named, "rule names no `## <section>` headings; the scan is broken"
    headings = set(index_text.splitlines())
    missing = [section for section in named if section not in headings]
    assert not missing, (
        f"sections named in {RULE.name} but absent from llms.txt: {missing}"
    )
