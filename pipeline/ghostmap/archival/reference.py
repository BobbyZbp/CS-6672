"""The anchored modern reference: model in local metres plus lidar ground and footprints."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

LIDAR = ROOT / 'data/lidar/NY_FingerLakes_1_2020'
FOOTPRINTS = ROOT / 'data/footprints/buildings-utm18n.json'


class Reference:
    """Anchored model (local metres = UTM 18N minus origin) with measured ground."""

    def __init__(self, anchor_report):
        import pycolmap
        from ghostmap.anchor.align import raster_lookup
        from ghostmap.anchor.lidar import fill_nearest
        self.report_path = Path(anchor_report)
        self.report = json.loads(self.report_path.read_text())
        if not self.report.get('metric_frame_usable'): raise ValueError('Anchored frame is not usable for metric work')
        self.model = pycolmap.Reconstruction(self.report['anchored_model'])
        self.origin = np.asarray(self.report['local_frame']['origin_utm18n'])
        rasters = np.load(LIDAR / 'quad-rasters-utm18n.npz')
        self.box, self.cell = tuple(rasters['box']), float(rasters['cell'])
        self.ground_raster = rasters['ground']; self.surface_raster = fill_nearest(rasters['surface'])
        self._lookup = raster_lookup
        self.buildings = json.loads(FOOTPRINTS.read_text())['buildings']
        self.run_path = self.report_path.parents[2]
        # Occluders: measured roof heights inside building footprints, ground
        # elsewhere (tree canopy is not an occluder for photographs).
        from ghostmap.anchor.align import InsideMask
        mask = InsideMask([b['ring'] for b in self.buildings], self.box, self.cell).mask
        self.building_raster = np.where(mask, self.surface_raster, self.ground_raster)

    def ground(self, xy_local):
        return self._lookup(self.ground_raster, self.box, self.cell, np.asarray(xy_local) + self.origin[:2])

    def surface(self, xy_local):
        return self._lookup(self.surface_raster, self.box, self.cell, np.asarray(xy_local) + self.origin[:2])

    def buildings_surface(self, xy_local):
        return self._lookup(self.building_raster, self.box, self.cell, np.asarray(xy_local) + self.origin[:2])

    def footprint_local(self, name):
        from ghostmap.anchor.footprints import named
        b = named(self.buildings, name)
        return None if b is None else np.asarray(b['ring']) - self.origin[:2]

    def points(self, min_track=2):
        ids, xyz = [], []
        for pid, p in self.model.points3D.items():
            if len(p.track.elements) >= min_track: ids.append(pid); xyz.append(p.xyz)
        return np.asarray(ids), np.asarray(xyz)

    def observations(self, image, min_other_views=2):
        """2D-3D pairs of a registered image, keeping points seen by other cameras."""
        p2, p3, ids = [], [], []
        for point2D in image.points2D:
            if not point2D.has_point3D(): continue
            p = self.model.points3D[point2D.point3D_id]
            if len(p.track.elements) - 1 < min_other_views: continue
            p2.append(point2D.xy); p3.append(p.xyz); ids.append(point2D.point3D_id)
        return np.asarray(p2), np.asarray(p3), np.asarray(ids)
