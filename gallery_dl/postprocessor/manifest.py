# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Write a markdown file listing the files of a post in post order"""

from .common import PostProcessor
from .. import formatter
from urllib.parse import quote
import os


class ManifestPP(PostProcessor):

    FIELDS = {
        "author" : "{username|author[name]|user[name]|uploader|artist|author}",
        "date"   : "{post_date|date|published|created_at}",
        "url"    : "{post_url|page_url|tweet_url|permalink}",
        "caption": "{description|caption|content|text|title}",
    }
    FILENAME = "{post_shortcode|post_id|id|filename}.manifest.md"

    def __init__(self, job, options):
        PostProcessor.__init__(self, job)

        fields = {**self.FIELDS, **(options.get("fields") or {})}
        self.fields = {
            name: formatter.parse(fmt, "").format_map
            for name, fmt in fields.items()
        }
        self.filename_fmt = formatter.parse(
            options.get("filename") or self.FILENAME).format_map
        self.encoding = options.get("encoding", "utf-8")
        self.source_url = job.extractor.url

        self.entries = []
        self.meta = self.filename = None

        job.register_hooks({
            "post"      : self.run_post,
            "after"     : self.run_file,
            "skip"      : self.run_file,
            "error"     : self.run_error,
            "post-after": self.run_post_after,
        }, options)

    def run_post(self, _):
        self.entries.clear()
        self.meta = self.filename = None

    def run_file(self, pathfmt):
        self._add(pathfmt, False)

    def run_error(self, pathfmt):
        self._add(pathfmt, True)

    def run_post_after(self, pathfmt):
        if not self.entries:
            return

        path = os.path.join(pathfmt.realdirectory, self.filename)
        try:
            with open(path, "w", encoding=self.encoding) as fp:
                fp.write(self._render())
        except FileNotFoundError:
            os.makedirs(pathfmt.realdirectory, exist_ok=True)
            with open(path, "w", encoding=self.encoding) as fp:
                fp.write(self._render())
        self.log.debug("Wrote '%s'", path)
        self.entries.clear()

    def _add(self, pathfmt, failed):
        kwdict = pathfmt.kwdict

        if self.meta is None:
            self.meta = {
                name: fmt(kwdict)
                for name, fmt in self.fields.items()
            }
            self.filename = pathfmt.clean_path(pathfmt.clean_segment(
                self.filename_fmt(kwdict)))

        self.entries.append((
            kwdict.get("num"),
            pathfmt.filename or pathfmt.build_filename(kwdict),
            failed,
        ))

    def _sorted_entries(self):
        """Return entries ordered by 'num', or as received without it"""
        entries = self.entries
        if all(isinstance(entry[0], int) for entry in entries):
            return sorted(entries, key=lambda entry: entry[0])
        return [(idx, entry[1], entry[2])
                for idx, entry in enumerate(entries, 1)]

    def _render(self):
        meta = self.meta

        lines = [
            f"# {self.filename.partition('.')[0]}",
            "",
            f"- Author: {_oneline(meta.get('author'))}",
            f"- Date: {_oneline(meta.get('date'))}",
            f"- Source: {_oneline(meta.get('url')) or self.source_url}",
            "",
        ]

        if caption := meta.get("caption"):
            # blockquote so a caption cannot add its own headings or lists
            lines.append("## Caption")
            lines.append("")
            lines.extend(f"> {line}".rstrip()
                         for line in caption.splitlines())
            lines.append("")

        lines.append("## Files")
        lines.append("")
        for num, name, failed in self._sorted_entries():
            if failed:
                lines.append(f"{num}. {name} (failed)")
            else:
                lines.append(f"{num}. [{name}]({quote(name)})")
        lines.append("")

        return "\n".join(lines)


def _oneline(value):
    return " ".join(value.split()) if value else ""


__postprocessor__ = ManifestPP
