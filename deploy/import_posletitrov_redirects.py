"""Compile the two WordPress exports into a static, reviewed nginx map.

No database, network calls or WordPress runtime are needed by this importer.
Unsupported conditions/conflicts fail closed instead of silently losing rules.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit


@dataclass(frozen=True)
class Redirect:
    path: str
    target: str
    source_id: str


class WordPressRedirectImporter:
    """Validate exports and resolve the known tag-to-article/tag conflict."""

    SOURCE_HOSTS = {"posletitrov.ru", "www.posletitrov.ru"}
    MAX_BYTES = 20_000_000
    MAX_ROWS = 50_000

    def __init__(self) -> None:
        self.redirects: dict[str, Redirect] = {}
        self.pagination: dict[str, str] = {}
        self.conflicts: list[dict] = []
        self.source_hashes: dict[str, str] = {}
        self.exact_count = 0
        self.duplicates = 0
        self.repaired_rules: list[str] = []

    def read(self, path: Path) -> list[dict]:
        if path.stat().st_size > self.MAX_BYTES:
            raise ValueError("Export exceeds the offline import size limit")
        raw = path.read_bytes()
        rows = json.loads(raw)
        if not isinstance(rows, list) or len(rows) > self.MAX_ROWS:
            raise ValueError("Expected a bounded list of redirects")
        self.source_hashes[path.name] = hashlib.sha256(raw).hexdigest()
        return rows

    @staticmethod
    def validate_flags(row: dict, kind: str) -> None:
        redirect, meta = row["redirect"], row["metas"]
        if redirect["status"] != "1" or redirect["type"] != kind:
            raise ValueError(f"Unsupported redirect status/type: {redirect['id']}")
        required = {"redirect_code": "301", "ignore_parameters": "1",
                    "ignore_case": "1", "ignore_trailing_slashes": "1",
                    "pass_on_parameters": "", "inclusion_exclusion_rules": "",
                    "redirection_http_headers": ""}
        if any(meta.get(key) != value for key, value in required.items()):
            raise ValueError(f"Unsupported redirect options: {redirect['id']}")
        if any(value.get("enabled") != "0" for key, value in meta.items()
               if key.startswith("rules_group")):
            raise ValueError(f"Conditional redirect cannot become public: {redirect['id']}")

    @staticmethod
    def target_url(value: str) -> str:
        # WP exports HTML entities in tag names (e.g. O&#039;Brien).
        value = html.unescape(value)
        if re.search(r"[\x00-\x1f\x7f]", unquote(value)):
            raise ValueError("Control characters in target URL")
        url = urlsplit(value)
        if url.scheme != "https" or url.netloc != "tambur.pub" or url.fragment:
            raise ValueError(f"Unexpected target URL: {value}")
        if not url.path.startswith(("/b/post/", "/tags/", "/comuns/")):
            raise ValueError(f"Unexpected destination path: {url.path}")
        if re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise ValueError("Malformed URL escaping")
        # Keep existing percent escapes; encode Cyrillic, spaces and punctuation.
        return urlunsplit(("https", "tambur.pub", quote(url.path, safe="/%-._~"),
                           quote(url.query, safe="=&%-._~"), ""))

    def source_path(self, value: str) -> str:
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or url.netloc not in self.SOURCE_HOSTS:
            raise ValueError("Unexpected source host")
        if url.query or url.fragment:
            raise ValueError("Query-specific source needs a separate request_uri map")
        path = unquote(url.path, errors="strict").lower().rstrip("/") or "/"
        if not re.fullmatch(r"/[\w/.-]*", path) or any(p in {".", ".."} for p in path.split("/")):
            raise ValueError(f"Unsupported source path: {path}")
        return path

    def add_exact(self, row: dict) -> None:
        self.validate_flags(row, "redirection")
        entry = row["redirect"]
        path = self.source_path(entry["from"])
        if urlsplit(entry["from"]).path != entry["match"]:
            raise ValueError("Source and match disagree")
        incoming = Redirect(path, self.target_url(entry["to"]), entry["id"])
        self.exact_count += 1
        previous = self.redirects.get(path)
        if previous is None:
            self.redirects[path] = incoming
        elif previous.target == incoming.target:
            self.duplicates += 1
        else:
            # This is the only observed conflict: a tag formerly pointed to one
            # article and now has its own tag page. Live WP checks confirm tags.
            pair = (previous, incoming)
            tags = [r for r in pair if r.target.startswith("https://tambur.pub/tags/")]
            articles = [r for r in pair if r.target.startswith("https://tambur.pub/b/post/")]
            if not path.startswith("/tag/") or len(tags) != 1 or len(articles) != 1:
                raise ValueError(f"Unresolved redirect conflict: {path}")
            self.redirects[path] = tags[0]
            self.conflicts.append({"path": path, "selected": tags[0].target,
                                   "discarded": articles[0].target})

    def add_pagination(self, row: dict) -> None:
        self.validate_flags(row, "redirection_rule")
        meta, entry = row["metas"], row["redirect"]
        criteria = meta["criterias"]
        if len(criteria) != 1 or criteria[0]["criteria"] not in {"regex-match", "end-with"}:
            raise ValueError("Unsupported pagination condition")
        expression = criteria[0]["value"]
        for prefix in ("https://posletitrov.ru", "http://posletitrov.ru"):
            if expression.startswith(prefix):
                expression = expression[len(prefix):]
                break
        match = re.fullmatch(r"(/[a-z/-]*)/page/\[0-9\]\+/", expression)
        if expression == "/page/[0-9]+/":
            prefix = ""
        elif match:
            prefix = match[1]
        else:
            raise ValueError(f"Unsupported pagination regex: {expression}")
        if criteria[0]["criteria"] == "end-with":
            if expression != "/articles/tv-series/page/[0-9]+/":
                raise ValueError("Only the known TV archive literal-regex typo may be repaired")
            self.repaired_rules.append(entry["id"])
        target = self.target_url(entry["to"])
        if meta["action"] != {"name": "a-specific-url", "value": entry["to"]}:
            raise ValueError("Rule action disagrees with its destination")
        if prefix in self.pagination and self.pagination[prefix] != target:
            raise ValueError("Conflicting pagination rules")
        self.pagination[prefix] = target

    def import_files(self, specific: Path, rules: Path) -> None:
        for row in self.read(specific):
            self.add_exact(row)
        for row in self.read(rules):
            self.add_pagination(row)

    def report(self) -> dict:
        return {"source_sha256": self.source_hashes, "exported_rows": self.exact_count,
                "unique_paths": len(self.redirects), "same_target_duplicates": self.duplicates,
                "pagination_rules": len(self.pagination), "repaired_rule_ids": self.repaired_rules,
                "resolved_tag_conflicts": self.conflicts}


class NginxRedirectRenderer:
    """Compile exact hashes plus bounded, anchored archive/Unicode regexes."""

    @staticmethod
    def token(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def render(self, imported: WordPressRedirectImporter) -> str:
        lines = ["# Generated by deploy/import_posletitrov_redirects.py; do not hand-edit.",
                 f"# {len(imported.redirects)} unique paths; {len(imported.pagination)} pagination rules."]
        for name, digest in sorted(imported.source_hashes.items()):
            lines.append(f"# SHA256 {name}: {digest}")
        lines += ["map $uri $posletitrov_redirect {", '  default "";']
        for path, row in sorted(imported.redirects.items()):
            for variant in ([path] if path == "/" else [path, path + "/"]):
                lines.append(f"  {self.token(variant)} {self.token(row.target)};")
        # nginx hash strings ignore ASCII case; UTF regexes additionally handle
        # the 19 Cyrillic source paths, including percent-encoded requests ($uri).
        for path, row in sorted(imported.redirects.items()):
            if not path.isascii():
                pattern = "~*(*UTF)(*UCP)^" + re.escape(path) + "/?$"
                lines.append(f"  {self.token(pattern)} {self.token(row.target)};")
        for prefix, target in sorted(imported.pagination.items()):
            pattern = "~*^" + prefix + "/page/[0-9]+/?$"
            lines.append(f"  {self.token(pattern)} {self.token(target)};")
        lines += ["}", ""]
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("specific", type=Path)
    parser.add_argument("rules", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    imported = WordPressRedirectImporter()
    imported.import_files(args.specific, args.rules)
    args.output.write_text(NginxRedirectRenderer().render(imported), encoding="utf-8")
    args.report.write_text(json.dumps(imported.report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(imported.redirects)} paths and {len(imported.pagination)} archive rules")


if __name__ == "__main__":
    main()
