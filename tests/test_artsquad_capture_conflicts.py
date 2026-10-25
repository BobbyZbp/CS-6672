import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from prepare_artsquad import capture_evidence


class CaptureConflictTests(unittest.TestCase):
    def test_digitization_date_cannot_override_older_caption(self):
        evidence, error = capture_evidence({'title': 'Cornell University, Ithaca, New York 1996 (19951361)',
                                           'capture_date_asserted': 'Taken on 18 June 2005',
                                           'exif': {'date_time_original': '2005:06:18 10:56:08'}}, 2000)
        self.assertIsNone(evidence)
        self.assertIn('epoch conflict', error)

    def test_numeric_photo_id_is_not_a_capture_year(self):
        evidence, error = capture_evidence({'title': 'Cornell (19951361)', 'capture_date_asserted': '2005-06-18'}, 2000)
        self.assertIsNone(error)
        self.assertEqual(evidence['earliest'], '2005-06-18')

    def test_explicit_construction_year_is_not_photographic_year(self):
        evidence, error = capture_evidence({'title': 'Modern hall (built in 1890)', 'capture_date_asserted': '2020-05-01'}, 2000)
        self.assertIsNone(error)
        self.assertEqual(evidence['earliest'], '2020-05-01')

    def test_ambiguous_older_year_is_review_not_a_claim_of_true_capture(self):
        evidence, error = capture_evidence({'title': 'Hall 1930', 'capture_date_asserted': '2020-05-01'}, 2000)
        self.assertIsNone(evidence)
        self.assertIn('cannot resolve', error)


if __name__ == '__main__': unittest.main()
