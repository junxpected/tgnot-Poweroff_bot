from __future__ import annotations

import unittest

from services.address_lookup import AddressLookup


class AddressLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lookup = AddressLookup()
        self.lookup.city_rows = [
            {"text": "м.Рівне, вул. Київська, 1-20", "podcherga": "2,1", "norm_text": "рівне київська 1-20"},
            {"text": "м.Рівне, вул. Шевченка, 7", "podcherga": "1,2", "norm_text": "рівне шевченка 7"},
        ]
        self.lookup.region_rows = [
            {"text": "с. Шкарів, Томахів, Симонів", "podcherga": "3,1", "norm_text": "шкарів томахів симонів"}
        ]

    def test_find_in_house_range(self) -> None:
        result, err = self.lookup.find_queue("Рівне Київська", "12")
        self.assertIsNone(err)
        self.assertEqual(result, ("2", "1", "city"))

    def test_find_without_house_number_uses_village_row(self) -> None:
        result, err = self.lookup.find_queue("Томахів", "")
        self.assertIsNone(err)
        self.assertEqual(result, ("3", "1", "region"))

    def test_not_found(self) -> None:
        result, err = self.lookup.find_queue("Невідома", "1")
        self.assertIsNone(result)
        self.assertEqual(err, "NOT_FOUND")

    def test_parse_podcherga_accepts_dot_separator(self) -> None:
        queue, sub = self.lookup._parse_podcherga("2.1")
        self.assertEqual(queue, "2")
        self.assertEqual(sub, "1")


if __name__ == "__main__":
    unittest.main()
