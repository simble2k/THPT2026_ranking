import unittest

from scraper.scraper import ExamScraper


class TestScraperLogic(unittest.TestCase):
    def setUp(self):
        self.scraper = ExamScraper("http://test.com/{sbd}")
        self.sample_html = """
        <table class="e-table">
            <tr><td>Toán</td><td>8.5</td></tr>
            <tr><td>Ngữ văn</td><td>7.25</td></tr>
            <tr><td>Ngoại ngữ</td><td>9.0</td></tr>
            <tr><td>Vật lý</td><td>6.75</td></tr>
        </table>
        """

    def test_parse_html(self):
        result = self.scraper.parse_html("01000001", self.sample_html)
        self.assertIsNotNone(result)
        self.assertEqual(result["math"], 8.5)
        self.assertEqual(result["literature"], 7.25)
        self.assertEqual(result["foreign_language"], 9.0)
        self.assertEqual(result["physics"], 6.75)
        self.assertEqual(result["candidate_id"], "01000001")
        self.assertEqual(result["province_code"], "01")

    def test_fallback_parse(self):
        # Messy HTML with Vietnamese subject names
        messy_html = "Some random text Toán: 8.5 và Ngữ văn: 7.25 sau đó Lịch sử 9.0"
        result = self.scraper._fallback_parse("01000001", messy_html)
        self.assertIsNotNone(result)
        self.assertEqual(result["math"], 8.5)
        self.assertEqual(result["literature"], 7.25)
        self.assertEqual(result["history"], 9.0)

    def test_parse_html_new_subjects(self):
        new_html = """
        <table class="e-table">
            <tr><td>Toán</td><td>4.35</td></tr>
            <tr><td>Giáo dục kinh tế và pháp luật</td><td>6.75</td></tr>
        </table>
        """
        result = self.scraper.parse_html("01000001", new_html)
        self.assertIsNotNone(result)
        self.assertEqual(result["math"], 4.35)
        self.assertEqual(result["civic_education"], 6.75)

    def test_invalid_scores(self):
        invalid_html = """
        <table class="e-table">
            <tr><td>Toán</td><td>11.0</td></tr>
            <tr><td>Ngữ văn</td><td>-1.0</td></tr>
            <tr><td>Ngoại ngữ</td><td>abc</td></tr>
        </table>
        """
        result = self.scraper.parse_html("01000001", invalid_html)
        # Should be None if no valid scores found, but here we might get empty results
        # Actually our code returns parsed if found_any
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
