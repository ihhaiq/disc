import re
from html.parser import HTMLParser


class HTMLToTelegramParser(HTMLParser):
    SUPPORTED_TAGS = frozenset(
        {"b", "strong", "i", "em", "code", "pre", "u", "s", "a", "tg-emoji"}
    )

    def __init__(self):
        super().__init__()
        self.text = ""
        self.open_tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.SUPPORTED_TAGS:
            return
        self.open_tags.append(tag)
        if tag in ("b", "strong"):
            self.text += "<b>"
        elif tag in ("i", "em"):
            self.text += "<i>"
        elif tag in ("code", "pre", "u", "s"):
            self.text += f"<{tag}>"
        elif tag == "a":
            href = dict(attrs).get("href", "#")
            self.text += f'<a href="{href}">'
        elif tag == "tg-emoji":
            emoji_id = dict(attrs).get("emoji-id") or ""
            emoji_id = emoji_id if emoji_id.isdigit() else ""
            self.text += f'<tg-emoji emoji-id="{emoji_id}">'

    def handle_endtag(self, tag):
        if tag not in self.SUPPORTED_TAGS:
            return
        equivalent_tags = (
            tag,
            "strong" if tag == "b" else tag,
            "em" if tag == "i" else tag,
        )
        if self.open_tags and self.open_tags[-1] in equivalent_tags:
            self.open_tags.pop()
        if tag in ("b", "strong"):
            self.text += "</b>"
        elif tag in ("i", "em"):
            self.text += "</i>"
        elif tag in ("code", "pre", "u", "s", "a", "tg-emoji"):
            self.text += f"</{tag}>"

    def handle_data(self, data):
        self.text += data


def clean_html(html_text: str) -> str:
    for tag in (r"h[1-6]", "p", "div", "footer", "span", "section", "article", "main"):
        html_text = re.sub(rf"</?{tag}[^>]*>", "", html_text)
    html_text = re.sub(r"\n\s*\n+", "\n\n", html_text)

    parser = HTMLToTelegramParser()
    try:
        parser.feed(html_text)
        return parser.text.strip()
    except Exception:
        return re.sub(r"<[^>]+>", "", html_text).strip()


def process_text_markup(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"<<(.+?)>>", r"<u>\1</u>", text)
    return clean_html(text)
