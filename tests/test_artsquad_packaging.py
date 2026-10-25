import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from build_artsquad_site import checked_file, check_distribution_scope, check_terminal_run_status, clean_text, component_display_order, copy_obj_bundle


class PackagingHelpersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.target = self.root / 'public'
        self.source.mkdir()

    def tearDown(self): self.temp.cleanup()

    def bundle(self, texture='camera_1.jpg'):
        obj = self.source / 'projected.obj'
        obj.write_text('mtllib projected.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        (self.source / 'projected.mtl').write_text('newmtl camera_1\nmap_Kd ' + texture + '\n')
        (self.source / texture).write_bytes(b'fixture-photo')
        return obj

    def test_clean_text_removes_metadata_markup_and_decodes_entities(self):
        self.assertEqual(clean_text('<a href="https://example.org">A &amp; B</a>'), 'A & B')
        self.assertEqual(clean_text(None), '')
        self.assertEqual(clean_text(42), '42')

    def test_clean_text_collapses_whitespace(self):
        self.assertEqual(clean_text('  A\n\t B&nbsp; C  '), 'A B C')

    def test_real_surface_precedes_multi_label_sparse_component(self):
        sparse = {'id': '4', 'mesh': None, 'metadata_core_candidates': ['mcgraw-hall', 'white'],
                  'stats': {'mesh_faces': 0, 'registered_cameras': 30}}
        fragment = {'id': '1', 'mesh': {'url': 'measured.obj'}, 'metadata_core_candidates': ['goldwin-smith'],
                    'stats': {'mesh_faces': 26433, 'registered_cameras': 5}}
        self.assertEqual(sorted([sparse, fragment], key=component_display_order), [fragment, sparse])

    def test_collection_labels_do_not_change_component_display_order(self):
        a = {'id': '1', 'mesh': None, 'stats': {'mesh_faces': 0, 'registered_cameras': 3}}
        b = {**a, 'metadata_core_candidates': ['morrill', 'mcgraw-hall', 'white']}
        self.assertEqual(component_display_order(a), component_display_order(b))

    def test_research_only_snapshot_cannot_enter_public_package(self):
        for snapshot in ({'scope': 'private-research-only'}, {'public_redistribution_permitted': False},
                         {'images': [{'filename': 'research.jpg', 'public_redistribution_permitted': False}]}):
            with self.subTest(snapshot=snapshot), self.assertRaisesRegex(ValueError, 'Research-only source rights'):
                check_distribution_scope(snapshot, self.target)

    def test_private_preview_requires_dedicated_contained_directory(self):
        private = self.root / 'artifacts/local_previews'
        for path in (self.target, private, private / '../../dist'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'dedicated subdirectory'):
                check_distribution_scope({}, path, True, private)
        self.assertEqual(check_distribution_scope({'scope': 'private-research-only'}, private / 'run-1', True, private), 'private-research-only')

    def test_private_preview_rejects_symlink_escape(self):
        private = self.root / 'artifacts/local_previews'; private.mkdir(parents=True)
        (private / 'escape').symlink_to(self.target)
        with self.assertRaises(ValueError): check_distribution_scope({}, private / 'escape', True, private)

    def test_incomplete_or_failed_run_cannot_replace_working_preview(self):
        for status in ('running', 'matching_pending', 'interrupted', 'error', None):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'terminal SfM'):
                check_terminal_run_status({'status': status})
        for run in (None, {'status': 'sfm_complete'}, {'status': 'no_model'}):
            check_terminal_run_status(run)

    def test_checked_file_accepts_existing_local_basename(self):
        path = self.source / 'asset.jpg'; path.write_bytes(b'asset')
        self.assertEqual(checked_file(self.source, 'asset.jpg'), path.resolve())

    def test_checked_file_rejects_empty_missing_and_paths(self):
        for name in ('', 'missing.jpg', '../secret.txt', '/etc/passwd', 'nested/file.jpg'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError): checked_file(self.source, name)

    def test_checked_file_rejects_escaping_symlink(self):
        secret = self.root / 'secret.txt'; secret.write_text('private')
        (self.source / 'photo.jpg').symlink_to(secret)
        with self.assertRaises(ValueError): checked_file(self.source, 'photo.jpg')

    def test_explicit_dependency_closure_excludes_unrelated_files(self):
        obj = self.bundle()
        (self.source / 'credentials.json').write_text('private fixture')
        (self.source / 'unrelated.jpg').write_bytes(b'not a dependency')
        (self.source / 'originals').mkdir()
        (self.source / 'originals' / 'unrelated-original.jpg').write_bytes(b'private fixture')
        result = copy_obj_bundle(obj, self.target)
        self.assertEqual(result, ('projected.obj', 'projected.mtl'))
        self.assertEqual({p.name for p in self.target.iterdir()}, {'projected.obj', 'projected.mtl', 'camera_1.jpg'})
        self.assertEqual((self.target / 'camera_1.jpg').read_bytes(), b'fixture-photo')

    def test_shared_texture_dependency_copied_once(self):
        obj = self.bundle()
        with (self.source / 'projected.mtl').open('a') as handle:
            handle.write('newmtl camera_2\nmap_Kd camera_1.jpg\n')
        copy_obj_bundle(obj, self.target)
        self.assertEqual(len(list(self.target.iterdir())), 3)

    def test_missing_obj_rejected(self):
        with self.assertRaises(ValueError): copy_obj_bundle(self.source / 'missing.obj', self.target)

    def test_missing_material_library_rejected(self):
        obj = self.bundle()
        (self.source / 'projected.mtl').unlink()
        with self.assertRaises(ValueError): copy_obj_bundle(obj, self.target)

    def test_missing_texture_rejected_before_copy(self):
        obj = self.bundle()
        (self.source / 'camera_1.jpg').unlink()
        with self.assertRaises(ValueError): copy_obj_bundle(obj, self.target)
        self.assertFalse(self.target.exists())

    def test_material_library_traversal_rejected(self):
        obj = self.bundle()
        obj.write_text('mtllib ../private.mtl\n')
        (self.root / 'private.mtl').write_text('newmtl secret\n')
        with self.assertRaises(ValueError): copy_obj_bundle(obj, self.target)

    def test_texture_dependency_traversal_rejected(self):
        obj = self.bundle()
        (self.source / 'projected.mtl').write_text('newmtl a\nmap_Kd ../private.jpg\n')
        (self.root / 'private.jpg').write_bytes(b'private')
        with self.assertRaises(ValueError): copy_obj_bundle(obj, self.target)

    def test_texture_dependency_escaping_symlink_rejected(self):
        obj = self.bundle()
        (self.source / 'camera_1.jpg').unlink()
        secret = self.root / 'private.jpg'; secret.write_bytes(b'private')
        (self.source / 'camera_1.jpg').symlink_to(secret)
        with self.assertRaises(ValueError): copy_obj_bundle(obj, self.target)

    def test_obj_requires_one_explicit_material_library(self):
        obj = self.bundle()
        for declaration in ('v 0 0 0\n', 'mtllib projected.mtl\nmtllib another.mtl\n'):
            obj.write_text(declaration)
            with self.subTest(declaration=declaration):
                with self.assertRaises(ValueError): copy_obj_bundle(obj, self.target)


if __name__ == '__main__': unittest.main()
