import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
from acquire_artsquad import assess,license_allowed
from review_artsquad_inputs import review


CONFIG={'minimum_short_side':800,'capture_year_min':2000,
        'targets':[{'name':'White Hall'}]}


def image(date='2017-05-04',title='File:Cornell White Hall built 1868.jpg'):
    return {'title':title,'discovery':{'sources':['search:intitle:White Hall Cornell']},
            'imageinfo':[{'mime':'image/jpeg','width':4000,'height':3000,
                          'extmetadata':{'DateTimeOriginal':{'value':date},
                                         'LicenseShortName':{'value':'CC BY-SA 4.0'}}}]}


class AdmissionTests(unittest.TestCase):
    def test_capture_not_construction_year(self):
        self.assertTrue(assess(image(),CONFIG)[0])

    def test_upload_date_not_capture(self):
        row=image('');row['imageinfo'][0]['timestamp']='2025-01-01T00:00:00Z'
        self.assertFalse(assess(row,CONFIG)[0])

    def test_old_capture(self):self.assertFalse(assess(image('1905'),CONFIG)[0])

    def test_mixed_old_range(self):self.assertFalse(assess(image('1890–2017'),CONFIG)[0])

    def test_reproduced_postcard(self):
        self.assertFalse(assess(image(title='File:Cornell White Hall postcard.jpg'),CONFIG)[0])

    def test_irrelevant_fulltext_hit(self):
        self.assertFalse(assess(image(title='File:Portrait of Cornell alumnus.jpg'),CONFIG)[0])

    def test_category_scene_evidence(self):
        row=image(title='File:Campus spring.jpg')
        row['discovery']['sources']=['Category:White Hall (Cornell University)']
        self.assertTrue(assess(row,CONFIG)[0])

    def test_native_resolution(self):
        row=image();row['imageinfo'][0]['height']=400
        self.assertFalse(assess(row,CONFIG)[0])

    def test_license_policy(self):
        for value in ['CC BY 4.0','CC-BY-SA-3.0','CC0','Public domain']:
            self.assertTrue(license_allowed(value))
        for value in ['All rights reserved','Fair use','Unknown']:
            self.assertFalse(license_allowed(value))

    def test_plans_not_scene_cameras(self):
        self.assertEqual(review('File:Plan of Library.JPG','','unknown')[0],'reference-document')

    def test_interiors_separate(self):
        self.assertEqual(review('File:Rand Hall Interior.JPG','','unknown')[0],'interior')

    def test_spherical_camera_separate(self):
        self.assertEqual(review('File:Arts Quad.jpg','','equirectangular')[0],'panorama-camera-review')

    def test_structural_epoch_separate(self):
        self.assertEqual(review('File:Rand Hall 2018 renovation.jpg','','unknown')[0],'structural-epoch-review')

    def test_exterior_still_only_candidate(self):
        self.assertEqual(review('File:Cornell White Hall.jpg','','unknown')[0],'scene-candidate')


if __name__=='__main__':unittest.main()
