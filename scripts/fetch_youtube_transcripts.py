#!/usr/bin/env python3
"""Download YouTube transcripts and save them as markdown by author."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "research" / "youtube-transcripts"


@dataclass(frozen=True)
class VideoSource:
    author: str
    title: str
    url: str
    video_id: str

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.author.lower()).strip("-")


# High-signal SaaS growth videos from experts listed in research/sources.md
VIDEO_SOURCES: list[VideoSource] = [
    VideoSource(
        author="Adam Robinson",
        title="How Adam Robinson Scaled RB2B to $5M ARR in 13 Months",
        url="https://www.youtube.com/watch?v=TBKUsO2Vb5s",
        video_id="TBKUsO2Vb5s",
    ),
    VideoSource(
        author="Adam Robinson",
        title="How I Went from $0 to $5M ARR in 13 Months Using LinkedIn",
        url="https://www.youtube.com/watch?v=O65FssItemk",
        video_id="O65FssItemk",
    ),
    VideoSource(
        author="Sam Kuehnle",
        title="How to Implement a Demand Creation Strategy (Stacking Growth)",
        url="https://www.youtube.com/watch?v=vDRrGZJS6C4",
        video_id="vDRrGZJS6C4",
    ),
    VideoSource(
        author="Sam Kuehnle",
        title="How to Implement a Demand Creation Strategy (RevOps FM)",
        url="https://www.youtube.com/watch?v=F8CSGGeGVrc",
        video_id="F8CSGGeGVrc",
    ),
]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "transcript"


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def normalize_entry(entry: object) -> dict[str, float | str]:
    if isinstance(entry, dict):
        return {"start": float(entry["start"]), "text": str(entry["text"])}
    return {"start": float(entry.start), "text": str(entry.text)}


def fetch_transcript(video_id: str) -> list[dict[str, float | str]]:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    for language in ("en", "en-US", "en-GB"):
        try:
            transcript = transcript_list.find_transcript([language])
            return [normalize_entry(entry) for entry in transcript.fetch()]
        except NoTranscriptFound:
            continue

    transcript = transcript_list.find_generated_transcript(["en"])
    return [normalize_entry(entry) for entry in transcript.fetch()]


def transcript_to_markdown(source: VideoSource, entries: list[dict[str, float | str]]) -> str:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {source.title}",
        "",
        f"- **Author:** {source.author}",
        f"- **Source:** [{source.url}]({source.url})",
        f"- **Video ID:** `{source.video_id}`",
        f"- **Fetched:** {fetched_at}",
        "",
        "## Transcript",
        "",
    ]

    for entry in entries:
        timestamp = format_timestamp(entry["start"])
        text = entry["text"].replace("\n", " ").strip()
        lines.append(f"**[{timestamp}]** {text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def save_transcript(source: VideoSource, content: str) -> Path:
    author_dir = OUTPUT_DIR / source.slug
    author_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(source.title)}.md"
    output_path = author_dir / filename
    output_path.write_text(content, encoding="utf-8")
    return output_path


def download_all(sources: list[VideoSource]) -> int:
    failures: list[str] = []
    saved = 0

    for source in sources:
        try:
            entries = fetch_transcript(source.video_id)
            markdown = transcript_to_markdown(source, entries)
            output_path = save_transcript(source, markdown)
            print(f"Saved: {output_path.relative_to(REPO_ROOT)}")
            saved += 1
        except (TranscriptsDisabled, NoTranscriptFound) as exc:
            failures.append(f"{source.title} ({source.video_id}): no transcript — {exc}")
        except VideoUnavailable as exc:
            failures.append(f"{source.title} ({source.video_id}): video unavailable — {exc}")
        except Exception as exc:  # noqa: BLE001 - surface any API/network errors clearly
            failures.append(f"{source.title} ({source.video_id}): {exc}")

    if failures:
        print("\nFailures:", file=sys.stderr)
        for message in failures:
            print(f"  - {message}", file=sys.stderr)

    return saved


def main() -> int:
    saved = download_all(VIDEO_SOURCES)
    print(f"\nDownloaded {saved}/{len(VIDEO_SOURCES)} transcripts to {OUTPUT_DIR.relative_to(REPO_ROOT)}/")
    return 0 if saved == len(VIDEO_SOURCES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
