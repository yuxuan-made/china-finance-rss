import unittest
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import server


class FeedGenerationTests(unittest.TestCase):
    def test_generate_rss_includes_atom_self_link_when_feed_url_given(self):
        xml = server.generate_rss(
            "Example",
            "https://example.com",
            "Example feed",
            [],
            feed_url="https://feeds.example.com/example.xml",
        )

        root = ET.fromstring(xml)
        atom_link = root.find("./channel/{http://www.w3.org/2005/Atom}link")

        self.assertIsNotNone(atom_link)
        self.assertEqual(atom_link.attrib["href"], "https://feeds.example.com/example.xml")
        self.assertEqual(atom_link.attrib["rel"], "self")
        self.assertEqual(atom_link.attrib["type"], "application/rss+xml")

    def test_generate_error_rss_returns_valid_feed_with_diagnostic_item(self):
        xml = server.generate_error_rss(
            "CLS Telegraph",
            "https://www.cls.cn/telegraph",
            "CLS feed",
            RuntimeError("HTTP 404 from upstream"),
            feed_url="https://feeds.example.com/cls/telegraph",
        )

        root = ET.fromstring(xml)
        item = root.find("./channel/item")

        self.assertIsNotNone(item)
        self.assertIn("temporarily unavailable", item.findtext("title"))
        self.assertIn("HTTP 404 from upstream", item.findtext("description"))
        self.assertEqual(item.find("guid").attrib["isPermaLink"], "false")

    def test_generate_opml_lists_all_builtin_feeds_with_absolute_urls(self):
        xml = server.generate_opml("https://feeds.example.com")
        root = ET.fromstring(xml)
        urls = {
            outline.attrib["xmlUrl"]
            for outline in root.findall("./body/outline/outline")
        }

        self.assertIn("https://feeds.example.com/cls/telegraph", urls)
        self.assertIn("https://feeds.example.com/eastmoney/kuaixun", urls)
        self.assertIn("https://feeds.example.com/ths/kuaixun", urls)
        self.assertIn("https://feeds.example.com/jin10/flash", urls)
        self.assertIn("https://feeds.example.com/wallstreetcn/live", urls)
        self.assertIn("https://feeds.example.com/xueqiu/user/1247347556", urls)


class TimeParsingTests(unittest.TestCase):
    def test_parse_china_datetime_to_rfc822_treats_source_time_as_utc_plus_8(self):
        dt = parsedate_to_datetime(
            server.parse_china_datetime_to_rfc822("2026-06-12 16:00:00")
        )

        self.assertEqual(dt.hour, 8)
        self.assertEqual(dt.utcoffset().total_seconds(), 0)


class SourceParserTests(unittest.TestCase):
    def test_cls_sign_params_matches_frontend_sha1_then_md5_signature(self):
        params = {
            "refresh_type": 1,
            "rn": 20,
            "last_time": 0,
            "os": "web",
            "sv": "8.7.9",
            "app": "CailianpressWeb",
        }

        self.assertEqual(
            server.cls_sign_params(params),
            "e11ef7d616d8f9a2f056e6df1aefc4d4",
        )

    def test_parse_cls_items_maps_roll_data(self):
        payload = {
            "data": {
                "roll_data": [{
                    "id": 123,
                    "ctime": 1781278243,
                    "brief": "LME期铜收涨216美元",
                    "content": "财联社6月13日电，LME期铜收涨216美元。",
                }]
            }
        }

        items = server.parse_cls_items(payload)

        self.assertEqual(items[0]["title"], "LME期铜收涨216美元")
        self.assertEqual(items[0]["description"], "财联社6月13日电，LME期铜收涨216美元。")
        self.assertEqual(items[0]["link"], "https://www.cls.cn/telegraph/123")
        self.assertEqual(items[0]["guid"], "cls_123")

    def test_extract_jin10_public_app_id_from_frontend_bundle(self):
        bundle = 'headers:{"x-app-id":"public-web-app-id","x-version":t,handleError:!0}'

        self.assertEqual(server.extract_jin10_public_app_id(bundle), "public-web-app-id")

    def test_parse_jin10_items_maps_nested_flash_data(self):
        payload = {
            "data": [{
                "id": "20260612233021430800",
                "time": "2026-06-12 23:30:21",
                "data": {
                    "title": "CME补上周末交易",
                    "content": "周末定价权大重估<font class=\"important-text\"></font>",
                    "source_link": "",
                },
            }]
        }

        items = server.parse_jin10_items(payload)

        self.assertEqual(items[0]["title"], "CME补上周末交易")
        self.assertEqual(items[0]["description"], "周末定价权大重估")
        self.assertEqual(items[0]["link"], "https://flash.jin10.com/detail/20260612233021430800")
        self.assertEqual(items[0]["guid"], "jin10_20260612233021430800")

    def test_parse_wallstreetcn_items_prefers_plain_text_content(self):
        payload = {
            "data": {
                "items": [{
                    "id": 3118981,
                    "title": "意大利银行板块收涨超3%",
                    "content": "<p>德国DAX 30指数初步收涨1.66%。</p>",
                    "content_text": "德国DAX 30指数初步收涨1.66%。",
                    "display_time": 1781278243,
                    "uri": "https://wallstreetcn.com/livenews/3118981",
                }]
            }
        }

        items = server.parse_wallstreetcn_items(payload)

        self.assertEqual(items[0]["title"], "意大利银行板块收涨超3%")
        self.assertEqual(items[0]["description"], "德国DAX 30指数初步收涨1.66%。")
        self.assertEqual(items[0]["link"], "https://wallstreetcn.com/livenews/3118981")
        self.assertEqual(items[0]["guid"], "wallstreetcn_3118981")


if __name__ == "__main__":
    unittest.main()
