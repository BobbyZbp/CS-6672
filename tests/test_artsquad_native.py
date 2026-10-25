"""Native API regression; temporary test images never become scene assets."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from run_artsquad_sfm import sha256, stage_images


@unittest.skipUnless(importlib.util.find_spec('pycolmap'), 'pycolmap not installed')
class NativeImageNamingTests(unittest.TestCase):
    def test_colmap_keeps_staged_image_names_inside_run(self):
        import pycolmap
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); original = root / 'original.jpg'
            Image.new('RGB', (96, 64), '#305040').save(original)
            staged = root / 'run/images'
            stage_images([{'filename': 'camera.jpg', 'working_path': str(original),
                           'sha256_working': sha256(original)}], staged)
            database = root / 'test.db'
            with pycolmap.Database.open(database): pass
            pycolmap.import_images(database, staged, pycolmap.CameraMode.PER_IMAGE,
                                   image_names=['camera.jpg'], options={'camera_model': 'SIMPLE_RADIAL'})
            with pycolmap.Database.open(database) as db:
                self.assertEqual([i.name for i in db.read_all_images()], ['camera.jpg'])
            self.assertFalse((staged / 'camera.jpg').is_symlink())


if __name__ == '__main__': unittest.main()
