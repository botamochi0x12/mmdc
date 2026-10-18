#!/usr/bin/env python3
"""本番環境 (https://mmdc.tiger-star.net/) のデータを低負荷で写し取り、SQLite に入れる。

依存は Python 3 標準ライブラリのみ。Rails / MySQL を立てなくても動く。

使い方:

    # 公開データ (お知らせ・更新情報・ランキング・統計) だけを取り、DB を作る
    python3 tools/snapshot/mmdc_snapshot.py all

    # ログイン必須データ (Wanted / 作者 / クレジット) も取る。
    # ブラウザで自分の X アカウントでログインし、DevTools の Cookie から
    # `uid` と `auto_login_token` を写して渡す。
    MMDC_COOKIE='uid=...; auto_login_token=...' \\
      python3 tools/snapshot/mmdc_snapshot.py fetch --gated

    # 一覧で切り詰められた名前 (truncate) を編集画面から補完する (1 件 1 リクエスト)
    MMDC_COOKIE=... python3 tools/snapshot/mmdc_snapshot.py fetch --gated --detail

    # JSONL から SQLite を作り直す (ネットワークは使わない)
    python3 tools/snapshot/mmdc_snapshot.py load

負荷低減のためにしていること:

- 接続は常に 1 本。並列にしない
- リクエスト間に待ち時間を入れる (`--delay`、既定 3 秒)
- 429 / 5xx は Retry-After を尊重し、指数バックオフで数回だけ再試行する
- 本文は gzip で受ける
- 一覧の JSON が使える表 (Wanted) は HTML を描画させない
- 編集画面は `--detail` を付けたときだけ、しかも一覧で切り詰められた行だけ取る。
  取得済みの行は JSONL を見て飛ばす (中断しても続きから)
- Wayback Machine は authors / credits / wanteds を 1 度も保存していないので使えない

出力:

- `db/snapshot/<table>.jsonl` … 1 行 1 レコード。キーはソート済み。git で差分を読む
- `db/snapshot/mmdc.sqlite3` … JSONL から組み立てる DB。git には入れない
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

BASE_URL = "https://mmdc.tiger-star.net"
USER_AGENT = "mmdc-snapshot/1.0 (+https://github.com/botamochi0x12/mmdc)"
REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "db" / "snapshot"
DB_PATH = SNAPSHOT_DIR / "mmdc.sqlite3"

DEFAULT_DELAY = 3.0  # 秒。リクエストとリクエストの間に必ず空ける
MAX_RETRIES = 4
RETRY_STATUSES = {429, 502, 503, 504}
PER_PAGE = 30  # kaminari の default_per_page (config/initializers/kaminari_config.rb)

# 一覧画面の truncate() の幅。app/views/*/index.html.slim と揃える
AUTHOR_NAME_WIDTH = 20
CREDIT_NAME_WIDTH = 15
CREDIT_AUTHOR_WIDTH = 15
CREDIT_WANTED_WIDTH = 10

PUBLIC_TABLES = ("infos", "histories", "ranks")
GATED_TABLES = ("wanteds", "authors", "credits")


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class ThrottledClient:
    """1 本の接続で、間隔を空けながら取るクライアント。"""

    def __init__(self, base_url=BASE_URL, delay=DEFAULT_DELAY, cookie=None, sleep=time.sleep, log=None):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.cookie = cookie
        self._sleep = sleep
        self._log = log or (lambda msg: print(msg, file=sys.stderr))
        self._last_request_at = None
        self.request_count = 0

    def _wait(self):
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay:
            self._sleep(self.delay - elapsed)

    def get(self, path, accept="*/*"):
        url = self.base_url + path
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Encoding": "gzip",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        backoff = self.delay
        for attempt in range(MAX_RETRIES + 1):
            self._wait()
            self._last_request_at = time.monotonic()
            self.request_count += 1
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read()
                    if resp.headers.get("Content-Encoding", "") == "gzip":
                        body = gzip.decompress(body)
                    # ログイン必須ページは未ログインだとトップへ 302 する。
                    # urllib は追従するので、最終 URL で見抜く
                    final = resp.geturl()
                    if urllib.parse.urlparse(final).path.rstrip("/") != urllib.parse.urlparse(url).path.rstrip("/"):
                        raise LoginRequired(f"{path} はトップへリダイレクトされた (Cookie が無効か、ログインが要る)")
                    return body
            except urllib.error.HTTPError as e:
                if e.code in RETRY_STATUSES and attempt < MAX_RETRIES:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                    self._log(f"  HTTP {e.code} {path} → {wait:.0f}s 待って再試行 ({attempt + 1}/{MAX_RETRIES})")
                    self._sleep(wait)
                    backoff *= 2
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < MAX_RETRIES:
                    self._log(f"  {e} {path} → {backoff:.0f}s 待って再試行 ({attempt + 1}/{MAX_RETRIES})")
                    self._sleep(backoff)
                    backoff *= 2
                    continue
                raise
        raise RuntimeError("unreachable")

    def get_text(self, path, accept="text/html"):
        return self.get(path, accept=accept).decode("utf-8")

    def get_json(self, path):
        return json.loads(self.get(path, accept="application/json").decode("utf-8"))


class LoginRequired(RuntimeError):
    pass


# --------------------------------------------------------------------------
# 正規化の小道具
# --------------------------------------------------------------------------


def to_utc_iso(value):
    """'2026-10-08T22:06:15+09:00' → '2026-10-08T13:06:15Z'。Rails の datetime は UTC なので揃える。"""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_truncated(text, width):
    """Rails の String#truncate(width) で切られた値か。切られると全長 width で末尾が '...'。"""
    return text is not None and len(text) == width and text.endswith("...")


def parse_int_count(text):
    """'6,143件' → 6143。"""
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def strip_tags(html):
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


# --------------------------------------------------------------------------
# 公開データのパーサ
# --------------------------------------------------------------------------


def normalize_info(row):
    return {
        "id": row["id"],
        "date": row.get("date"),
        "title": row.get("title"),
        "note": row.get("note"),
        "lock_version": row.get("lock_version"),
    }


ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
HISTORY_TITLE_RE = re.compile(r"^(?P<item>.+?)(?P<verb>登録|更新)$")


def parse_histories_atom(xml_text):
    """home/index.atom → histories 行。id はエントリ id の末尾 (History/27280) から取る。"""
    root = ElementTree.fromstring(xml_text)
    rows = []
    for entry in root.findall("a:entry", ATOM_NS):
        entry_id = entry.findtext("a:id", default="", namespaces=ATOM_NS)
        m = re.search(r"History/(\d+)$", entry_id)
        if not m:
            continue
        title = entry.findtext("a:title", default="", namespaces=ATOM_NS)
        content = entry.findtext("a:content", default="", namespaces=ATOM_NS)
        tm = HISTORY_TITLE_RE.match(title)
        item = tm.group("item") if tm else title
        is_create = (tm.group("verb") == "登録") if tm else None
        item_name = content[len(title):].lstrip(" ") if content.startswith(title) else content
        link_el = entry.find("a:link", ATOM_NS)
        href = link_el.get("href") if link_el is not None else None
        link = urllib.parse.urlparse(href).path if href else None
        rows.append({
            "id": int(m.group(1)),
            "created_at": to_utc_iso(entry.findtext("a:published", namespaces=ATOM_NS)),
            "item": item,
            "item_name": item_name,
            "is_create": is_create,
            "link": link,
        })
    return rows


RANK_RE = re.compile(
    r'alt="rank(?P<rank>\d+)".*?twitter\.com/(?P<screen_name>[^"]+)"[^>]*>(?P<name>.*?)</p><p>(?P<point>[\d,]+)pt</p>',
    re.S,
)
STAT_RE = re.compile(r"<td>(?P<label>Wantend|クレジット情報|作者情報)</td><td class=\"text-right\">(?P<count>[\d,]+)件</td>")
STAT_KEYS = {"Wantend": "wanted", "クレジット情報": "credit", "作者情報": "author"}


def parse_home(html):
    """トップページ → (ranks 行, stats)。ranks は貢献度ランキング上位 3 件。"""
    ranks = []
    for m in RANK_RE.finditer(html):
        ranks.append({
            "rank": int(m.group("rank")),
            "screen_name": unescape(m.group("screen_name")),
            "name": strip_tags(m.group("name")),
            "point": parse_int_count(m.group("point")),
        })
    stats = {}
    for m in STAT_RE.finditer(html):
        stats[STAT_KEYS[m.group("label")]] = parse_int_count(m.group("count"))
    return ranks, stats


# --------------------------------------------------------------------------
# ログイン必須データのパーサ
# --------------------------------------------------------------------------


class TableRowsParser(HTMLParser):
    """`content_tag_for(:tr, ...)` が出す `<tr id="author_12">` を、セルごとの文字列とリンクに分解する。"""

    def __init__(self, row_id_prefix):
        super().__init__(convert_charrefs=True)
        self.prefix = row_id_prefix + "_"
        self.rows = []
        self._row = None
        self._cell = None
        self._link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and (attrs.get("id") or "").startswith(self.prefix):
            self._row = {"id": int(attrs["id"][len(self.prefix):]), "cells": []}
        elif self._row is not None and tag == "td":
            self._cell = {"text": "", "links": []}
        elif self._cell is not None and tag == "a":
            self._link = {"href": attrs.get("href"), "text": ""}
        elif self._cell is not None and tag == "br":
            self._cell["text"] += "\n"

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self._link["text"] = self._link["text"].strip()
            self._cell["links"].append(self._link)
            self._link = None
        elif tag == "td" and self._cell is not None:
            self._row["cells"].append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._link is not None:
            self._link["text"] += data
        if self._cell is not None:
            self._cell["text"] += data


def parse_table_rows(html, row_id_prefix):
    p = TableRowsParser(row_id_prefix)
    p.feed(html)
    return p.rows


def parse_authors_index(html):
    """authors 一覧 → authors 行。名前と表記名は truncate(20) されうるので `_truncated` に印を付ける。"""
    rows = []
    for tr in parse_table_rows(html, "author"):
        cells = tr["cells"]
        if len(cells) < 3:
            continue
        name = cells[0]["links"][0]["text"] if cells[0]["links"] else cells[0]["text"].strip()
        disp_name = cells[1]["text"].strip()
        row = {
            "id": tr["id"],
            "name": name,
            "disp_name": disp_name,
            "nico": None,
            "twitter": None,
            "pixiv": None,
            "url": None,
            "email": None,
            "_truncated": is_truncated(name, AUTHOR_NAME_WIDTH) or is_truncated(disp_name, AUTHOR_NAME_WIDTH),
        }
        for link in cells[2]["links"]:
            href = link["href"] or ""
            if href.startswith("http://www.nicovideo.jp/user/"):
                row["nico"] = href.rsplit("/", 1)[1]
            elif href.startswith("https://twitter.com/"):
                row["twitter"] = href.rsplit("/", 1)[1]
            elif href.startswith("https://www.pixiv.net/member.php?id="):
                row["pixiv"] = href.split("id=", 1)[1]
            elif href.startswith("mailto:"):
                row["email"] = href[len("mailto:"):]
            elif href:
                row["url"] = href
        rows.append(row)
    return rows


def parse_credits_index(html):
    """credits 一覧 → credits 行。name は truncate(15)、作者名は 15、Wanted のフォルダ/ファイル名は 10 で切られる。"""
    rows = []
    for tr in parse_table_rows(html, "credit"):
        cells = tr["cells"]
        if len(cells) < 5:
            continue
        name = cells[0]["links"][0]["text"] if cells[0]["links"] else cells[0]["text"].strip()
        author_names = [a.strip() for a in cells[1]["text"].split("\n") if a.strip()]
        distribution = cells[2]["text"].strip()
        folder_name = cells[3]["text"].strip()
        file_name = cells[4]["text"].strip()
        truncated = (
            is_truncated(name, CREDIT_NAME_WIDTH)
            or any(is_truncated(a, CREDIT_AUTHOR_WIDTH) for a in author_names)
            or is_truncated(folder_name, CREDIT_WANTED_WIDTH)
            or is_truncated(file_name, CREDIT_WANTED_WIDTH)
        )
        rows.append({
            "id": tr["id"],
            "name": name,
            "author_names": author_names,
            "distribution": distribution,
            "url": None,
            "description": None,
            "wanted_id": None,
            "wanted_folder_name": folder_name,
            "wanted_file_name": file_name,
            "_truncated": truncated,
            "_detail": False,
        })
    return rows


class FormParser(HTMLParser):
    """編集画面の input / textarea を name → value に集める。同名 (author_names[]) はリストにする。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = {}
        self._textarea = None

    def _put(self, name, value):
        if name.endswith("[]"):
            self.fields.setdefault(name, []).append(value)
        else:
            self.fields[name] = value

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") and attrs.get("type") != "submit":
            self._put(attrs["name"], attrs.get("value", ""))
        elif tag == "textarea" and attrs.get("name"):
            self._textarea = [attrs["name"], ""]

    def handle_endtag(self, tag):
        if tag == "textarea" and self._textarea is not None:
            name, text = self._textarea
            # Rails は textarea の先頭に改行を 1 つ入れる
            self._put(name, text[1:] if text.startswith("\n") else text)
            self._textarea = None

    def handle_data(self, data):
        if self._textarea is not None:
            self._textarea[1] += data


def parse_form(html):
    p = FormParser()
    p.feed(html)
    return p.fields


def parse_author_edit(html):
    f = parse_form(html)
    return {
        "name": f.get("author[name]"),
        "disp_name": f.get("author[disp_name]"),
        "url": f.get("author[url]") or None,
        "nico": f.get("author[nico]") or None,
        "twitter": f.get("author[twitter]") or None,
        "pixiv": f.get("author[pixiv]") or None,
        "email": f.get("author[email]") or None,
    }


WANTED_PANEL_RE = re.compile(r"<strong>(?P<label>フォルダ名|ファイル名)</strong></div><div class=\"col-sm-10\">(?P<value>.*?)</div>", re.S)


def parse_credit_edit(html):
    f = parse_form(html)
    panel = {m.group("label"): unescape(m.group("value")).strip() for m in WANTED_PANEL_RE.finditer(html)}
    wanted_id = f.get("credit[wanted_id]")
    return {
        "name": f.get("credit[name]"),
        "author_names": [a for a in f.get("author_names[]", []) if a],
        "distribution": f.get("credit[distribution]") or "",
        "url": f.get("credit[url]") or None,
        "description": f.get("credit[description]") or "",
        "wanted_id": int(wanted_id) if wanted_id and wanted_id.isdigit() else None,
        "wanted_folder_name": panel.get("フォルダ名"),
        "wanted_file_name": panel.get("ファイル名"),
    }


def normalize_wanted(row):
    return {
        "id": row["id"],
        "file_name": row.get("file_name"),
        "folder_name": row.get("folder_name"),
        "extension": row.get("extension"),
        "lock_version": row.get("lock_version"),
    }


# --------------------------------------------------------------------------
# JSONL の読み書き
# --------------------------------------------------------------------------


def jsonl_path(table, snapshot_dir=SNAPSHOT_DIR):
    return Path(snapshot_dir) / f"{table}.jsonl"


def write_jsonl(table, rows, snapshot_dir=SNAPSHOT_DIR):
    path = jsonl_path(table, snapshot_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r["id"])
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def read_jsonl(table, snapshot_dir=SNAPSHOT_DIR):
    path = jsonl_path(table, snapshot_dir)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_meta(meta, snapshot_dir=SNAPSHOT_DIR):
    path = Path(snapshot_dir) / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def read_meta(snapshot_dir=SNAPSHOT_DIR):
    path = Path(snapshot_dir) / "meta.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------


def fetch_public(client, snapshot_dir=SNAPSHOT_DIR, log=print):
    """公開エンドポイントだけ。合計 3 リクエスト。"""
    log("infos.json (お知らせ)")
    infos = [normalize_info(r) for r in client.get_json("/infos.json")]
    write_jsonl("infos", infos, snapshot_dir)

    log("home/index.atom (更新情報 直近 30 件)")
    histories = parse_histories_atom(client.get_text("/home/index.atom", accept="application/atom+xml"))
    # 直近 30 件しか出ないので、過去回の分と合算して積む (id で後勝ち)
    merged = {r["id"]: r for r in read_jsonl("histories", snapshot_dir)}
    merged.update({r["id"]: r for r in histories})
    write_jsonl("histories", merged.values(), snapshot_dir)

    log("/ (貢献度ランキング・統計)")
    ranks, stats = parse_home(client.get_text("/"))
    write_jsonl("ranks", [dict(r, id=r["rank"]) for r in ranks], snapshot_dir)
    return {"infos": len(infos), "histories": len(merged), "ranks": len(ranks), "stats": stats}


def fetch_paged(client, path_for_page, parse, log, label, limit_pages=None):
    rows = []
    page = 1
    while True:
        if limit_pages and page > limit_pages:
            break
        log(f"{label} page {page}")
        got = parse(client, path_for_page(page))
        rows.extend(got)
        if len(got) < PER_PAGE:
            break
        page += 1
    return rows


def fetch_gated(client, snapshot_dir=SNAPSHOT_DIR, detail=False, limit_pages=None, log=print):
    """ログイン必須の一覧。Wanted は JSON、作者とクレジットは HTML しか正しく返らない
    (credits/index.json.jbuilder は存在しない属性を extract して 500 になる)。"""
    counts = {}

    wanteds = fetch_paged(
        client,
        lambda p: f"/wanteds.json?page={p}",
        lambda c, path: [normalize_wanted(r) for r in c.get_json(path)],
        log, "wanteds.json", limit_pages,
    )
    write_jsonl("wanteds", wanteds, snapshot_dir)
    counts["wanteds"] = len(wanteds)

    authors = fetch_paged(
        client,
        lambda p: f"/authors?page={p}",
        lambda c, path: parse_authors_index(c.get_text(path)),
        log, "authors", limit_pages,
    )
    authors = merge_detail_rows("authors", authors, snapshot_dir)
    if detail:
        for row in authors:
            if row.get("_truncated") and not row.get("_detail"):
                log(f"authors/{row['id']}/edit")
                row.update(parse_author_edit(client.get_text(f"/authors/{row['id']}/edit")))
                row["_detail"] = True
                write_jsonl("authors", authors, snapshot_dir)  # 中断に備えて都度書く
    write_jsonl("authors", authors, snapshot_dir)
    counts["authors"] = len(authors)

    credits = fetch_paged(
        client,
        lambda p: f"/credits?page={p}",
        lambda c, path: parse_credits_index(c.get_text(path)),
        log, "credits", limit_pages,
    )
    credits = merge_detail_rows("credits", credits, snapshot_dir)
    if detail:
        for row in credits:
            if row.get("_truncated") and not row.get("_detail"):
                log(f"credits/{row['id']}/edit")
                row.update(parse_credit_edit(client.get_text(f"/credits/{row['id']}/edit")))
                row["_detail"] = True
                write_jsonl("credits", credits, snapshot_dir)
    write_jsonl("credits", credits, snapshot_dir)
    counts["credits"] = len(credits)
    return counts


def merge_detail_rows(table, fresh_rows, snapshot_dir):
    """前回 `--detail` で補完済みの行は、一覧の切り詰め値で上書きしない (再取得を避ける)。"""
    previous = {r["id"]: r for r in read_jsonl(table, snapshot_dir) if r.get("_detail")}
    merged = []
    for row in fresh_rows:
        old = previous.get(row["id"])
        if old and not row_changed_since_detail(table, old, row):
            merged.append(old)
        else:
            merged.append(row)
    return merged


def row_changed_since_detail(table, old, fresh):
    """一覧に出ている値 (切り詰め後) が、補完済みの値を同じ幅で切った結果と食い違えば更新されている。"""
    if table == "authors":
        return rails_truncate(old["name"], AUTHOR_NAME_WIDTH) != fresh["name"] or rails_truncate(
            old["disp_name"], AUTHOR_NAME_WIDTH
        ) != fresh["disp_name"]
    return (
        rails_truncate(old["name"], CREDIT_NAME_WIDTH) != fresh["name"]
        or [rails_truncate(a, CREDIT_AUTHOR_WIDTH) for a in old["author_names"]] != fresh["author_names"]
        or old["distribution"] != fresh["distribution"]
    )


def rails_truncate(text, width, omission="..."):
    if text is None:
        return None
    if len(text) <= width:
        return text
    return text[: width - len(omission)] + omission


# --------------------------------------------------------------------------
# load (JSONL → SQLite)
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE infos (
  id INTEGER PRIMARY KEY, date TEXT, title TEXT NOT NULL, note TEXT, lock_version INTEGER
);
CREATE TABLE histories (
  id INTEGER PRIMARY KEY, link TEXT, created_at TEXT NOT NULL, item TEXT, item_name TEXT, is_create INTEGER
);
CREATE TABLE ranks (
  rank INTEGER NOT NULL, screen_name TEXT NOT NULL, name TEXT, point INTEGER
);
CREATE TABLE wanteds (
  id INTEGER PRIMARY KEY, file_name TEXT NOT NULL, folder_name TEXT NOT NULL, extension TEXT NOT NULL, lock_version INTEGER
);
CREATE TABLE authors (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, disp_name TEXT, url TEXT, nico TEXT, twitter TEXT, pixiv TEXT, email TEXT,
  truncated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE credits (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, distribution TEXT, url TEXT, description TEXT, wanted_id INTEGER,
  wanted_folder_name TEXT, wanted_file_name TEXT, truncated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE credit_author_names (
  credit_id INTEGER NOT NULL, position INTEGER NOT NULL, author_name TEXT NOT NULL,
  author_id INTEGER, PRIMARY KEY (credit_id, position)
);
CREATE TABLE snapshot_meta (key TEXT PRIMARY KEY, value TEXT);
"""


def load_sqlite(db_path=DB_PATH, snapshot_dir=SNAPSHOT_DIR):
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        load_into_connection(con, snapshot_dir)
    finally:
        con.close()
    return db_path


def load_into_connection(con, snapshot_dir=SNAPSHOT_DIR):
    con.executescript(SCHEMA)
    counts = {}

    def insert(table, rows, columns):
        placeholders = ",".join("?" for _ in columns)
        con.executemany(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
            [[r.get(c) for c in columns] for r in rows],
        )
        counts[table] = len(rows)

    insert("infos", read_jsonl("infos", snapshot_dir), ["id", "date", "title", "note", "lock_version"])
    insert("histories", read_jsonl("histories", snapshot_dir), ["id", "link", "created_at", "item", "item_name", "is_create"])
    insert("ranks", read_jsonl("ranks", snapshot_dir), ["rank", "screen_name", "name", "point"])
    insert("wanteds", read_jsonl("wanteds", snapshot_dir), ["id", "file_name", "folder_name", "extension", "lock_version"])

    authors = read_jsonl("authors", snapshot_dir)
    insert("authors", [dict(a, truncated=int(bool(a.get("_truncated")) and not a.get("_detail"))) for a in authors],
           ["id", "name", "disp_name", "url", "nico", "twitter", "pixiv", "email", "truncated"])
    author_id_by_name = {a["name"]: a["id"] for a in authors}

    credits = read_jsonl("credits", snapshot_dir)
    insert("credits", [dict(c, truncated=int(bool(c.get("_truncated")) and not c.get("_detail"))) for c in credits],
           ["id", "name", "distribution", "url", "description", "wanted_id", "wanted_folder_name", "wanted_file_name", "truncated"])
    links = []
    for c in credits:
        for i, name in enumerate(c.get("author_names") or []):
            links.append({"credit_id": c["id"], "position": i, "author_name": name, "author_id": author_id_by_name.get(name)})
    insert("credit_author_names", links, ["credit_id", "position", "author_name", "author_id"])

    meta = read_meta(snapshot_dir)
    con.executemany("INSERT INTO snapshot_meta (key, value) VALUES (?, ?)",
                    [(k, json.dumps(v, ensure_ascii=False, sort_keys=True)) for k, v in meta.items()])
    con.commit()
    return counts


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="本番から取って db/snapshot/*.jsonl に書く")
    add_fetch_args(f)

    sub.add_parser("load", help="db/snapshot/*.jsonl から SQLite を作り直す")

    a = sub.add_parser("all", help="fetch してから load する")
    add_fetch_args(a)
    return p


def add_fetch_args(p):
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"リクエスト間隔 (秒)。既定 {DEFAULT_DELAY}")
    p.add_argument("--gated", action="store_true", help="ログイン必須の一覧 (wanteds / authors / credits) も取る。MMDC_COOKIE が要る")
    p.add_argument("--detail", action="store_true", help="--gated のとき、一覧で切り詰められた行だけ編集画面から補完する")
    p.add_argument("--limit-pages", type=int, default=None, help="各一覧で取るページ数の上限 (動作確認用)")
    p.add_argument("--base-url", default=BASE_URL)


def run_fetch(args):
    cookie = os.environ.get("MMDC_COOKIE")
    if args.gated and not cookie:
        print("--gated には環境変数 MMDC_COOKIE (uid=...; auto_login_token=...) が要ります。", file=sys.stderr)
        print("自分の X アカウントでブラウザからログインし、DevTools の Cookie から写してください。", file=sys.stderr)
        return 2
    if args.delay < 1.0:
        print("--delay は 1 秒以上にしてください (本番への負荷を抑えるため)。", file=sys.stderr)
        return 2
    client = ThrottledClient(base_url=args.base_url, delay=args.delay, cookie=cookie if args.gated else None)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = fetch_public(client)
    meta = read_meta()
    meta.update({
        "source": args.base_url,
        "public_fetched_at": started,
        "stats": result.pop("stats"),
    })
    if args.gated:
        try:
            result.update(fetch_gated(client, detail=args.detail, limit_pages=args.limit_pages))
        except LoginRequired as e:
            print(f"中断: {e}", file=sys.stderr)
            return 3
        meta["gated_fetched_at"] = started
        meta["gated_detail"] = bool(args.detail)
        meta["gated_limit_pages"] = args.limit_pages
    write_meta(meta)
    print(f"requests={client.request_count} rows={result}")
    return 0


def run_load():
    path = load_sqlite()
    con = sqlite3.connect(path)
    try:
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("infos", "histories", "ranks", "wanteds", "authors", "credits", "credit_author_names")}
    finally:
        con.close()
    print(f"{path}: {counts}")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return run_fetch(args)
    if args.command == "load":
        return run_load()
    rc = run_fetch(args)
    if rc:
        return rc
    return run_load()


if __name__ == "__main__":
    sys.exit(main())
