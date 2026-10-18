#!/usr/bin/env python3
"""tools/snapshot/mmdc_snapshot.py のテスト。ネットワークは使わない。

    python3 -m unittest tools/snapshot/test_mmdc_snapshot.py
"""

import json
import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mmdc_snapshot as m  # noqa: E402

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US" xmlns="http://www.w3.org/2005/Atom">
  <title>更新情報</title>
  <entry>
    <id>tag:mmdc.tiger-star.net,2005:History/27280</id>
    <published>2026-10-08T22:06:15+09:00</published>
    <updated>2026-10-08T22:06:15+09:00</updated>
    <link rel="alternate" type="text/html" href="http://mmdc.tiger-star.net/credits/new/15805"/>
    <title>Wanted登録</title>
    <content type="text">Wanted登録 2.シュガーポットb (角砂糖・金属蓋).pmx</content>
  </entry>
  <entry>
    <id>tag:mmdc.tiger-star.net,2005:History/27100</id>
    <published>2026-09-20T15:00:49+09:00</published>
    <updated>2026-09-20T15:00:49+09:00</updated>
    <link rel="alternate" type="text/html" href="http://mmdc.tiger-star.net/credits/9650/edit"/>
    <title>クレジット更新</title>
    <content type="text">クレジット更新 スイスポ(ZC33S)</content>
  </entry>
</feed>
"""

HOME = (
    '<h2>貢献度ランキング</h2><div class="row"><div class="col-sm-4"><div class="row"><div class="col-sm-4">'
    ' <img src ="/images/rank1.png" class="img-rounded" width="70" alt="rank1"> </div><div class="col-sm-8">'
    ' <img src="https://furyutei.work/gadget/twicon/mar_ky_2010/bigger" class="img-rounded">'
    ' <p><a href="https://twitter.com/mar_ky_2010" target="_blank">まーき (*・◇・*)</p><p>2,000pt</p></div></div></div>'
    '<div class="col-sm-4"><div class="row"><div class="col-sm-4"> <img src ="/images/rank2.png" class="img-rounded" width="70" alt="rank2"> </div>'
    '<div class="col-sm-8"> <img src="https://furyutei.work/gadget/twicon/mikosu3/bigger" class="img-rounded">'
    ' <p><a href="https://twitter.com/mikosu3" target="_blank">みこす</p><p>867pt</p></div></div></div></div>'
    '<h1>統計</h1><div><table class="table table-responsive table-hover"><tr><td>Wantend</td><td class="text-right">6,143件</td><td class="text-right"></td></tr>'
    '<tr><td>クレジット情報</td><td class="text-right">9,659件</td><td class="text-right"></td></tr>'
    '<tr><td>作者情報</td><td class="text-right">1,209件</td><td class="text-right"></td></tr></table></div>'
)

AUTHORS_INDEX = (
    '<table><tbody>'
    '<tr class="author" id="author_12"><td><a href="/authors/12/edit">ビームマンP</a></td><td>ビームマンP</td><td>'
    '<a target="_blank" href="http://www.nicovideo.jp/user/421727"><img src="/assets/icons/nico.jpg" /></a>'
    '<a target="_blank" href="https://twitter.com/BeamManP"><img src="/assets/icons/twitter.jpg" /></a>'
    '<a target="_blank" href="http://www43.atwiki.jp/beamman/"><span class="glyphicon glyphicon-home"></span></a>'
    '<a href="mailto:beam@example.com"><span class="glyphicon glyphicon-envelope"></span></a>'
    '</td><td></td></tr>'
    '<tr class="author" id="author_13"><td><a href="/authors/13/edit">あいうえおかきくけこさしすせそたち...</a></td><td>そぼろ</td><td>'
    '<a target="_blank" href="https://www.pixiv.net/member.php?id=99"><img src="/assets/icons/pixiv.jpg" /></a>'
    '</td><td><a data-confirm="削除してよろしいですか?" rel="nofollow" data-method="delete" href="/authors/13">削除</a></td></tr>'
    '</tbody></table>'
)

CREDITS_INDEX = (
    '<table><tbody>'
    '<tr class="credit" id="credit_9700"><td><a href="/credits/9700/edit">PowerShader改変_Y</a></td>'
    '<td>ビームマンP<br />そぼろ<br /></td><td><a href="http://www.nicovideo.jp/watch/sm123">sm123</a></td>'
    '<td>PowerSh...</td><td>PowerSh...</td></tr>'
    '<tr class="credit" id="credit_9701"><td><a href="/credits/9701/edit">短い名前</a></td>'
    '<td>針金P<br /></td><td></td><td>空色町1.52</td><td>sorairo1.x</td></tr>'
    '</tbody></table>'
)

CREDIT_EDIT = (
    '<form class="form-horizontal" id="edit_credit_9700" action="/credits/9700" method="post">'
    '<input type="hidden" name="_method" value="patch" /><input type="hidden" name="authenticity_token" value="tok" />'
    '<input value="15805" type="hidden" name="credit[wanted_id]" id="credit_wanted_id" />'
    '<div class="panel-body"><div class="col-sm-2"><strong>フォルダ名</strong></div><div class="col-sm-10">PowerShader_v1.0 &amp; ex</div>'
    '<div class="col-sm-2"><strong>ファイル名</strong></div><div class="col-sm-10">PowerShader改変_Y.fx</div></div>'
    '<input class="form-control" maxlength="100" placeholder="x" type="text" value="PowerShader改変_Y" name="credit[name]" id="credit_name" />'
    '<input type="text" name="author_names[]" id="author_names_" value="ビームマンP" class="form-control" />'
    '<input type="text" name="author_names[]" id="author_names_" value="そぼろ" class="form-control" />'
    '<input class="form-control" type="text" value="sm123" name="credit[distribution]" id="credit_distribution" />'
    '<input class="form-control" type="text" value="" name="credit[url]" id="credit_url" />'
    '<textarea class="form-control" rows="5" name="credit[description]" id="credit_description">\n改変品 &lt;注意&gt;</textarea>'
    '<input type="submit" name="commit" value="Update Credit" />'
    '</form>'
)

AUTHOR_EDIT = (
    '<form id="edit_author_13" action="/authors/13" method="post">'
    '<input class="form-control" type="text" value="あいうえおかきくけこさしすせそたちつてとな" name="author[name]" />'
    '<input class="form-control" type="text" value="そぼろ" name="author[disp_name]" />'
    '<input class="form-control" type="text" value="" name="author[url]" />'
    '<input class="form-control" type="text" value="424150" name="author[nico]" />'
    '<input class="form-control" type="text" value="sovoro_mmd" name="author[twitter]" />'
    '<input class="form-control" type="text" value="" name="author[pixiv]" />'
    '<input class="form-control" type="text" value="" name="author[email]" />'
    '</form>'
)


class ParserTest(unittest.TestCase):
    def test_histories_atom(self):
        rows = m.parse_histories_atom(ATOM)
        self.assertEqual(rows[0], {
            "id": 27280, "created_at": "2026-10-08T13:06:15Z", "item": "Wanted",
            "item_name": "2.シュガーポットb (角砂糖・金属蓋).pmx", "is_create": True, "link": "/credits/new/15805",
        })
        self.assertEqual(rows[1]["item"], "クレジット")
        self.assertFalse(rows[1]["is_create"])
        self.assertEqual(rows[1]["link"], "/credits/9650/edit")

    def test_home(self):
        ranks, stats = m.parse_home(HOME)
        self.assertEqual(ranks[0], {"rank": 1, "screen_name": "mar_ky_2010", "name": "まーき (*・◇・*)", "point": 2000})
        self.assertEqual(ranks[1]["point"], 867)
        self.assertEqual(stats, {"wanted": 6143, "credit": 9659, "author": 1209})

    def test_normalize_info_drops_url(self):
        row = m.normalize_info({"id": 1, "date": "2016-03-04", "title": "t", "note": None, "lock_version": 0, "url": "x"})
        self.assertNotIn("url", row)
        self.assertEqual(row["title"], "t")

    def test_truncate_roundtrip(self):
        long = "あいうえおかきくけこさしすせそたちつてとな"
        self.assertEqual(m.rails_truncate(long, 20), "あいうえおかきくけこさしすせそたち...")
        self.assertTrue(m.is_truncated(m.rails_truncate(long, 20), 20))
        self.assertEqual(m.rails_truncate("短い", 20), "短い")
        self.assertFalse(m.is_truncated("短い", 20))

    def test_authors_index(self):
        rows = m.parse_authors_index(AUTHORS_INDEX)
        self.assertEqual(len(rows), 2)
        a = rows[0]
        self.assertEqual((a["id"], a["name"], a["disp_name"]), (12, "ビームマンP", "ビームマンP"))
        self.assertEqual((a["nico"], a["twitter"], a["url"], a["email"], a["pixiv"]),
                         ("421727", "BeamManP", "http://www43.atwiki.jp/beamman/", "beam@example.com", None))
        self.assertFalse(a["_truncated"])
        b = rows[1]
        self.assertEqual(b["pixiv"], "99")
        self.assertTrue(b["_truncated"])

    def test_credits_index(self):
        rows = m.parse_credits_index(CREDITS_INDEX)
        c = rows[0]
        self.assertEqual(c["id"], 9700)
        self.assertEqual(c["author_names"], ["ビームマンP", "そぼろ"])
        self.assertEqual(c["distribution"], "sm123")
        self.assertTrue(c["_truncated"])
        d = rows[1]
        self.assertEqual(d["distribution"], "")
        self.assertEqual((d["wanted_folder_name"], d["wanted_file_name"]), ("空色町1.52", "sorairo1.x"))
        self.assertFalse(d["_truncated"])

    def test_credit_edit(self):
        d = m.parse_credit_edit(CREDIT_EDIT)
        self.assertEqual(d["name"], "PowerShader改変_Y")
        self.assertEqual(d["author_names"], ["ビームマンP", "そぼろ"])
        self.assertEqual(d["wanted_id"], 15805)
        self.assertEqual(d["wanted_folder_name"], "PowerShader_v1.0 & ex")
        self.assertEqual(d["wanted_file_name"], "PowerShader改変_Y.fx")
        self.assertEqual(d["description"], "改変品 <注意>")
        self.assertIsNone(d["url"])

    def test_author_edit(self):
        d = m.parse_author_edit(AUTHOR_EDIT)
        self.assertEqual(d["name"], "あいうえおかきくけこさしすせそたちつてとな")
        self.assertEqual(d["nico"], "424150")
        self.assertIsNone(d["url"])

    def test_row_changed_since_detail(self):
        old = {"name": "あいうえおかきくけこさしすせそたちつてとな", "disp_name": "そぼろ", "_detail": True}
        fresh = m.parse_authors_index(AUTHORS_INDEX)[1]
        self.assertFalse(m.row_changed_since_detail("authors", old, fresh))
        self.assertTrue(m.row_changed_since_detail("authors", dict(old, disp_name="別名"), fresh))


class FakeResponse:
    def __init__(self, body, url):
        self.body = body
        self.url = url
        self.headers = {}

    def read(self):
        return self.body

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ClientTest(unittest.TestCase):
    def test_sequential_delay_and_retry(self):
        sleeps = []
        calls = []

        def fake_urlopen(req, timeout=0):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 503, "busy", {"Retry-After": "7"}, None)
            return FakeResponse(b"ok", req.full_url)

        c = m.ThrottledClient(base_url="https://example.test", delay=3, sleep=sleeps.append, log=lambda s: None)
        with unittest.mock.patch.object(m.urllib.request, "urlopen", fake_urlopen):
            self.assertEqual(c.get("/a"), b"ok")
            self.assertEqual(c.get("/b"), b"ok")
        self.assertEqual(calls, ["https://example.test/a", "https://example.test/a", "https://example.test/b"])
        self.assertEqual(sleeps[0], 7.0)  # Retry-After を尊重
        self.assertTrue(all(s > 0 for s in sleeps))
        self.assertEqual(c.request_count, 3)

    def test_redirect_to_top_means_login_required(self):
        def fake_urlopen(req, timeout=0):
            return FakeResponse(b"<html>", "https://example.test/")

        c = m.ThrottledClient(base_url="https://example.test", delay=1, sleep=lambda s: None)
        with unittest.mock.patch.object(m.urllib.request, "urlopen", fake_urlopen):
            with self.assertRaises(m.LoginRequired):
                c.get("/authors?page=1")

    def test_cookie_is_sent_only_when_given(self):
        seen = []

        def fake_urlopen(req, timeout=0):
            seen.append(req.headers.get("Cookie"))
            return FakeResponse(b"x", req.full_url)

        with unittest.mock.patch.object(m.urllib.request, "urlopen", fake_urlopen):
            m.ThrottledClient(base_url="https://example.test", delay=1, sleep=lambda s: None).get("/")
            m.ThrottledClient(base_url="https://example.test", delay=1, cookie="uid=1; auto_login_token=2",
                              sleep=lambda s: None).get("/")
        self.assertEqual(seen, [None, "uid=1; auto_login_token=2"])


class LoaderTest(unittest.TestCase):
    def test_jsonl_roundtrip_and_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.write_jsonl("infos", [{"id": 2, "title": "b"}, {"id": 1, "title": "a", "date": "2016-03-04"}], tmp)
            lines = Path(tmp, "infos.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], '{"date": "2016-03-04", "id": 1, "title": "a"}')  # id 昇順・キーソート
            m.write_jsonl("histories", m.parse_histories_atom(ATOM), tmp)
            m.write_jsonl("ranks", [dict(r, id=r["rank"]) for r in m.parse_home(HOME)[0]], tmp)
            m.write_jsonl("authors", m.parse_authors_index(AUTHORS_INDEX), tmp)
            m.write_jsonl("credits", m.parse_credits_index(CREDITS_INDEX), tmp)
            m.write_meta({"stats": {"wanted": 1}}, tmp)

            con = sqlite3.connect(":memory:")
            counts = m.load_into_connection(con, tmp)
            self.assertEqual(counts["infos"], 2)
            self.assertEqual(counts["credit_author_names"], 3)
            self.assertEqual(con.execute("SELECT item_name FROM histories WHERE id=27280").fetchone()[0],
                             "2.シュガーポットb (角砂糖・金属蓋).pmx")
            self.assertEqual(con.execute("SELECT point FROM ranks WHERE rank=2").fetchone()[0], 867)
            # 作者名から author_id を引ける
            self.assertEqual(con.execute(
                "SELECT author_id FROM credit_author_names WHERE credit_id=9700 AND position=0").fetchone()[0], 12)
            # 補完していない切り詰め行には truncated=1 が立つ
            self.assertEqual(con.execute("SELECT truncated FROM credits WHERE id=9700").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT truncated FROM credits WHERE id=9701").fetchone()[0], 0)
            self.assertEqual(json.loads(con.execute(
                "SELECT value FROM snapshot_meta WHERE key='stats'").fetchone()[0]), {"wanted": 1})


if __name__ == "__main__":
    unittest.main()
