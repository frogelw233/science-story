"""Store untrusted public source text; this module never executes source content.

The HTML reader is deliberately a conservative extractor, not a full browser.
The host must inspect the original page and captions when extraction is incomplete.
PDFs are supplementary evidence: extract them with the host's PDF capability and
pass the resulting text explicitly instead of treating PDF bytes as article text.
"""

from __future__ import annotations

import codecs
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5
_TEXT_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}
_HTML_TYPES = {"text/html", "application/xhtml+xml"}
_METADATA_KEYS = {"title", "publisher", "published_date", "url"}


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_global and not address.is_multicast and not address.is_reserved


class _VisibleHTML(HTMLParser):
    """Keep paragraph/caption boundaries while discarding obvious page chrome."""

    _HIDDEN = {"script", "style", "noscript", "template", "nav", "footer", "form", "svg", "canvas", "iframe"}
    _BLOCK = {"p", "div", "section", "article", "main", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "figure", "figcaption", "blockquote", "tr"}
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.hidden: list[str] = []
        self.in_head = False
        self.in_title = False
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if self.hidden:
            if tag not in self._VOID:
                self.hidden.append(tag)
            return
        if tag in self._HIDDEN or "hidden" in attributes or attributes.get("aria-hidden", "").lower() == "true":
            if tag not in self._VOID:
                self.hidden.append(tag)
            return
        if tag == "head":
            self.in_head = True
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            value = attributes.get("content", "").strip()
            if key in {"article:published_time", "date", "datepublished", "dc.date", "dcterms.date", "citation_publication_date"} and value:
                self.metadata.setdefault("published_date", value)
            if key in {"og:site_name", "citation_publisher"} and value:
                self.metadata.setdefault("publisher", value)
            if key == "og:title" and value:
                self.metadata.setdefault("title", value)
        if tag == "time" and attributes.get("datetime"):
            self.metadata.setdefault("published_date", attributes["datetime"])
        if not self.in_head and tag in self._BLOCK:
            self.parts.append("\n\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in self.hidden:
                index = len(self.hidden) - 1 - self.hidden[::-1].index(tag)
                self.hidden = self.hidden[:index]
            return
        if tag == "title":
            self.in_title = False
        if tag == "head":
            self.in_head = False
        if not self.in_head and tag in self._BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_title:
            self.title_parts.append(data)
        if not self.in_head and not self.in_title:
            self.parts.append(data)

    def result(self):
        # HTML formatting whitespace is not a paragraph boundary.
        raw = "".join(self.parts)
        paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", raw)]
        title = re.sub(r"\s+", " ", "".join(self.title_parts)).strip()
        if title:
            self.metadata.setdefault("title", title)
        return "\n\n".join(part for part in paragraphs if part), self.metadata


def _validated_url(url: str):
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a nonempty string.")
    if any(ord(character) <= 32 or ord(character) == 127 for character in url):
        raise ValueError("URL cannot contain whitespace or control characters.")
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only public HTTP or HTTPS URLs are supported.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Credentials in URLs are prohibited.")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Invalid URL port.")
        hostname = parsed.hostname.rstrip(".")
        if hostname.lower() == "localhost" or hostname.lower().endswith((".localhost", ".local", ".internal")):
            raise ValueError("Local and private network URLs are prohibited.")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            hostname.encode("idna")
        else:
            if not _is_public_address(str(address)):
                raise ValueError("Local and private network URLs are prohibited.")
    except (UnicodeError, TypeError) as error:
        raise ValueError("Invalid public URL.") from error
    return parsed


def _connect_public(hostname: str, port: int):
    """Resolve once, reject any nonpublic answer, then connect to a vetted IP."""
    try:
        candidates = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not candidates:
            raise ValueError("The source hostname has no addresses.")
        for family, _, _, _, address in candidates:
            if family not in {socket.AF_INET, socket.AF_INET6} or not _is_public_address(address[0]):
                raise ValueError("The source hostname resolves to a nonpublic address.")
        last_error = None
        for family, kind, protocol, _, address in candidates:
            connection = socket.socket(family, kind, protocol)
            connection.settimeout(TIMEOUT_SECONDS)
            try:
                connection.connect(address)
                return connection
            except OSError as error:
                connection.close()
                last_error = error
        raise ValueError("Could not connect to the public source.") from last_error
    except OSError as error:
        raise ValueError("Could not resolve or connect to the public source.") from error


def _request_url(url: str):
    parsed = _validated_url(url)
    hostname = parsed.hostname.encode("idna").decode("ascii")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    connection = http.client.HTTPConnection(hostname, port, timeout=TIMEOUT_SECONDS)
    raw_socket = None
    try:
        raw_socket = _connect_public(hostname, port)
        if parsed.scheme.lower() == "https":
            connection.sock = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=hostname)
        else:
            connection.sock = raw_socket
        path = quote(urlunsplit(("", "", parsed.path or "/", parsed.query, "")), safe="/%?=&:;+,$@!~*'()[]")
        connection.request("GET", path, headers={"User-Agent": "ScienceStory/0.1 (public-source reader)", "Accept": "text/html,text/plain,text/markdown,application/xhtml+xml", "Accept-Encoding": "identity"})
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        if response.status in {301, 302, 303, 307, 308}:
            return response.status, headers, b""
        if response.status != 200:
            raise ValueError(f"Public source returned HTTP {response.status}.")
        if headers.get("content-encoding", "identity").lower() not in {"identity", ""}:
            raise ValueError("Compressed responses are not supported; use host-extracted text.")
        if headers.get("content-length"):
            try:
                if int(headers["content-length"]) > MAX_BYTES:
                    raise ValueError("Source exceeds the 5 MiB input limit.")
            except ValueError as error:
                raise ValueError("Invalid or excessive source Content-Length.") from error
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Source exceeds the 5 MiB input limit.")
        return response.status, headers, body
    except (OSError, http.client.HTTPException, UnicodeError) as error:
        raise ValueError(f"Public source retrieval failed ({type(error).__name__}); use available host tools and pass extracted text explicitly.") from error
    finally:
        connection.close()
        if raw_socket is not None:
            raw_socket.close()


def _fetch_public_url(url: str):
    current = url
    for redirects in range(MAX_REDIRECTS + 1):
        _validated_url(current)
        status, headers, body = _request_url(current)
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location:
                raise ValueError("Public source redirect has no Location header.")
            current = urljoin(current, location)
            _validated_url(current)
            continue
        media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media_type == "application/pdf" or body.startswith(b"%PDF-"):
            raise ValueError("PDF is supplementary evidence. Extract its text with the host PDF tools and provide text/file input.")
        if media_type not in _TEXT_TYPES | _HTML_TYPES:
            raise ValueError("Source is not a supported HTML, plain text, or Markdown response.")
        match = re.search(r"charset\s*=\s*[\"']?([^;\s\"']+)", headers.get("content-type", ""), re.I)
        encoding = match.group(1) if match else "utf-8-sig"
        try:
            codecs.lookup(encoding)
            decoded = body.decode(encoding, errors="strict")
        except (LookupError, UnicodeError) as error:
            raise ValueError("Source text encoding is unsupported or invalid; provide UTF-8 text extracted by the host.") from error
        if "\x00" in decoded:
            raise ValueError("Source contains binary NUL bytes.")
        metadata = {}
        if media_type in _HTML_TYPES:
            parser = _VisibleHTML()
            parser.feed(decoded)
            parser.close()
            decoded, metadata = parser.result()
        return decoded, metadata, current, {"method": "html_parser" if media_type in _HTML_TYPES else "http_text", "media_type": media_type, "response_bytes": len(body), "redirects": redirects}
    raise ValueError(f"Public source exceeded the {MAX_REDIRECTS}-redirect limit.")


def ingest(run_dir: Path, *, url=None, text=None, file=None, metadata=None) -> dict:
    """Save exactly one input as input.txt and input.json, returning its record.

    Metadata accepts title, publisher, published_date and url. A metadata URL on
    pasted/file text records provenance only; it does not claim a network fetch.
    Missing metadata stays null and must be completed by the host from evidence.
    """
    if sum(value is not None for value in (url, text, file)) != 1:
        raise ValueError("Provide exactly one of url, text, or file.")
    if not isinstance(run_dir, (str, Path)):
        raise ValueError("run_dir must be a filesystem path.")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("metadata must be a dictionary.")
    metadata = dict(metadata or {})
    if set(metadata) - _METADATA_KEYS or any(value is not None and not isinstance(value, str) for value in metadata.values()):
        raise ValueError("metadata accepts only string title, publisher, published_date and url fields.")
    if metadata.get("url"):
        _validated_url(metadata["url"])
    extracted = {}
    final_url = None
    if url is not None:
        if metadata.get("url") and metadata["url"] != url:
            raise ValueError("metadata.url cannot contradict the requested URL.")
        content, extracted, final_url, extraction = _fetch_public_url(url)
        kind = "url"
    elif text is not None:
        if not isinstance(text, str):
            raise ValueError("text must be a Unicode string.")
        content = text
        kind = "text"
        extraction = {"method": "provided_text", "network_fetched_by_script": False}
    else:
        if not isinstance(file, (str, Path)):
            raise ValueError("file must be a filesystem path.")
        source_path = Path(file)
        if source_path.suffix.lower() not in {".txt", ".md"}:
            raise ValueError("Local input must be a UTF-8 .txt or .md file.")
        try:
            if source_path.stat().st_size > MAX_BYTES:
                raise ValueError("Source exceeds the 5 MiB input limit.")
            with source_path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Source exceeds the 5 MiB input limit.")
            content = raw.decode("utf-8-sig", errors="strict")
        except (OSError, UnicodeError) as error:
            raise ValueError("Could not read local input as UTF-8 text.") from error
        kind = "file"
        extraction = {"method": "utf8_file", "filename": source_path.name, "network_fetched_by_script": False}
    if not content.strip():
        raise ValueError("Input contains no readable text.")
    try:
        encoded = content.encode("utf-8")
    except UnicodeError as error:
        raise ValueError("Input is not valid Unicode text.") from error
    if len(encoded) > MAX_BYTES:
        raise ValueError("Source exceeds the 5 MiB input limit.")
    if "\x00" in content:
        raise ValueError("Input contains binary NUL bytes.")
    record = {
        "schema_version": "0.1",
        "input_kind": kind,
        "title": metadata.get("title") or extracted.get("title"),
        "publisher": metadata.get("publisher") or extracted.get("publisher"),
        "published_date": metadata.get("published_date") or extracted.get("published_date"),
        "original_url": url or metadata.get("url"),
        "url": final_url or metadata.get("url"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "text_path": "input.txt",
        "untrusted": True,
        "needs_host_full_read": extraction["method"] == "html_parser",
        "content_sha256": hashlib.sha256(encoded).hexdigest(),
        "extraction": extraction,
    }
    destination = Path(run_dir)
    try:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "input.txt").write_bytes(encoded)
        (destination / "input.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        raise ValueError("Could not save the input files to run_dir.") from error
    return record
