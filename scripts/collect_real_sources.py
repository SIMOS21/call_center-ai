"""Download ABCD official public research data; optionally crawl eBay Help conservatively.

No fabricated FAQ is created. We refuse a forbidden crawl (robots.txt) and do not
bypass bot defenses. Always check source terms and permission before collecting eBay.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

ROOT = Path("data")
ABCD_REVISION = os.getenv("ABCD_REVISION", "6b8700ce67c6b37b062dd7a60abc76d7ef832a97")
ABCD_BASE = f"https://raw.githubusercontent.com/asappresearch/abcd/{ABCD_REVISION}/data/"
EBAY_SEEDS = [
    "https://www.ebay.com/help/buying",
    "https://www.ebay.com/help/returns-refunds",
    "https://www.ebay.com/help/buying/paying-items",
    "https://www.ebay.com/help/buying/shipping-delivery",
    "https://www.ebay.com/help/buying/returns-refunds/return-item-refund?id=4041",
]
UA = "CommerceOpsAcademicRAG/0.1 (educational project; obeys robots.txt)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})


def get(url, timeout=30):
    r = SESSION.get(url, timeout=timeout)
    r.raise_for_status()
    if len(r.content) > 100_000_000:
        raise ValueError("Source too large")
    return r


def save_record(text, title, source, source_type) -> Path:
    if len(text.strip()) < 120:
        raise ValueError("Document too short")
    output = ROOT / "knowledge"
    output.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(source.encode()).hexdigest()[:16]
    file = output / f"{source_type}_{sha}.json"
    file.write_text(json.dumps({"title": title, "source": source, "source_type": source_type,
                                "text": text, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                "sha256": hashlib.sha256(text.encode()).hexdigest()},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return file


def download_abcd() -> None:
    folder = ROOT / "raw" / "abcd"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("guidelines.json", "kb.json", "ontology.json", "abcd_v1.1.json.gz"):
        url = ABCD_BASE + name
        response = get(url, timeout=120)
        (folder / name).write_bytes(response.content)
        print("downloaded", name, len(response.content))
    guidelines = json.loads((folder / "guidelines.json").read_text(encoding="utf-8"))
    count = 0
    for flow_name, group in guidelines.items():
        for sub_name, payload in group.get("subflows", {}).items():
            chunks = [f"Action-based Conversations Dataset / {flow_name} / {sub_name}"]
            chunks.extend(payload.get("instructions", []))
            for step in payload.get("actions", []):
                chunks.extend([f"Action: {step.get('button', '')}", step.get("text", "")])
                chunks.extend(map(str, step.get("subtext", [])))
            save_record("\n".join(map(str, chunks)), f"ABCD: {flow_name} / {sub_name}",
                        "https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json"
                        + f"#flow={flow_name}&subflow={sub_name}", "abcd")
            count += 1
    print("ABCD real guidelines indexed as", count, "documents; dialogs downloaded for evaluation only")


def crawl_ebay(max_pages: int, pause: float = 1.5):
    if os.getenv("ALLOW_EBAY_COLLECTION", "false").lower() != "true":
        raise RuntimeError("eBay collection blocked: set ALLOW_EBAY_COLLECTION=true after reviewing rights.")
    rp = RobotFileParser()
    rp.set_url("https://www.ebay.com/robots.txt")
    rp.read()
    seen, queue, saved = set(), list(EBAY_SEEDS), 0
    while queue and saved < max_pages:
        url = queue.pop(0)
        url = urldefrag(url)[0]
        if url in seen:
            continue
        seen.add(url)
        parsed = urlparse(url)
        if parsed.hostname != "www.ebay.com" or not parsed.path.startswith("/help/"):
            continue
        if not rp.can_fetch(UA, url):
            print("robots disallow:", url)
            continue
        try:
            response = get(url)
            if "html" not in response.headers.get("content-type", "").lower():
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            title = (soup.find("h1") or soup.title)
            title = title.get_text(" ", strip=True) if title else url
            main = soup.find("main") or soup.find("article")
            if not main:
                print("skip no article content:", url)
                continue
            for node in main.select("script,style,nav,footer,header,aside"):
                node.decompose()
            text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
            if len(text) >= 500:
                save_record(text, title, url, "ebay")
                saved += 1
                print(saved, title[:60])
            for link in soup.select('a[href*="/help/"]'):
                candidate = urljoin(url, link.get("href", ""))
                if candidate not in seen and candidate not in queue:
                    queue.append(candidate)
        except (requests.RequestException, ValueError) as e:
            print("skip failed page", url, type(e).__name__)
        time.sleep(pause)
    print("Total real eBay pages imported:", saved)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--abcd", action="store_true")
    parser.add_argument("--ebay", action="store_true")
    parser.add_argument("--max-pages", type=int, default=150)
    args = parser.parse_args()
    if not args.abcd and not args.ebay:
        parser.error("Choose --abcd or --ebay")
    if args.abcd:
        download_abcd()
    if args.ebay:
        crawl_ebay(args.max_pages)
