from html.parser import HTMLParser


class _AnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def extract_hrefs(html: str) -> list[str]:
    parser = _AnchorExtractor()
    parser.feed(html)
    return parser.hrefs
