"""Exercise the local nightlights CLI with small HDF5 and annual-mask fixtures."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
import unittest
import uuid


class NightlightsTests(unittest.TestCase):
    def setUp(self):
        import h5py
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        self.root = Path.cwd() / ".task_tmp" / f"nightlights-check-{uuid.uuid4().hex}"
        self.root.mkdir(parents=True)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        months = [(2016, 12)] + [(y, m) for y in (2017, 2018) for m in range(1, 13)]
        for year, month in months:
            doy = (date(year, month, 1) - date(year, 1, 1)).days + 1
            for tile, start in (("h27v07", 0), ("h28v07", 8)):
                raw = np.full((2, 8), 500.0)
                quality = np.zeros((2, 8), dtype="uint8")
                land = np.ones((2, 8), dtype="uint8")
                if start == 0:
                    raw[:] = 100 * ((year - 2017) * 12 + month + 1)
                    if year == 2017 and month == 1:
                        raw[0, 1] = 65535
                    if (year, month) == (2017, 10):
                        raw[0, 2], raw[0, 6] = 100, 300
                    if (year, month) == (2017, 11):
                        raw[0, 2], raw[0, 6] = 300, 100
                    if (year, month) == (2017, 12):
                        raw[0, 2] = raw[0, 6] = 65535
                    if year == 2018 and month in (1, 2, 3):
                        raw[0, 2] = {1: 65535, 2: 700, 3: 900}[month]
                    quality[0, 3] = 1
                    raw[0, 4] = 500 if month == 6 else 65535
                    raw[0, 5], raw[0, 7] = 10001, 65534
                    land[1, 1] = 151
                    land[1, 2] = 150
                    quality[1, 3] = 2
                    raw[1, 2:4] = 300
                    if (year, month) == (2017, 1):
                        raw[1, 4], raw[1, 5], raw[1, 6] = 65535, -10, np.nan
                    raw[1, 7] = 70000
                path = self.inputs / f"VNP46A3.A{year}{doy:03d}.{tile}.001.2023000000000.h5"
                with h5py.File(path, "w") as h5:
                    fields = h5.create_group("HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields")
                    fields["lon"] = np.arange(start, start + 8) + 0.5
                    fields["lat"] = [1.5, 0.5]
                    fields["AllAngle_Composite_Snow_Free"] = raw
                    fields["AllAngle_Composite_Snow_Free_Quality"] = quality
                    fields["Land_Water_Mask"] = land
        self.mask = self.root / "2017_mask.tif"
        # Zero is an actual unlit value, even when the source marks zero as nodata.
        with rasterio.open(self.mask, "w", driver="GTiff", width=8, height=1,
                           count=1, dtype="uint8", crs="EPSG:4326", nodata=0,
                           transform=from_origin(0, 2, 2, 2)) as dst:
            dst.write(np.array([[1, 1, 1, 1, 1, 0, 1, 1]], dtype="uint8"), 1)

    def tearDown(self):
        self.root.resolve().relative_to((Path.cwd() / ".task_tmp").resolve())
        shutil.rmtree(self.root)

    def run_cli(self, *extra, success=True):
        command = [sys.executable, "-m", "replication.prepare_nightlights",
                   "--input-dir", str(self.inputs), "--output-dir", str(self.root / "output"),
                   "--year", "2017", "--year", "2018", "--mask", f"2017={self.mask}",
                   "--reuse-mask", "2016=2017", "--reuse-mask", "2018=2017",
                   "--block-size", "3", *extra]
        result = subprocess.run(command, text=True, capture_output=True, cwd=Path(__file__).resolve().parent.parent)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse((self.root / "output").exists())
        return result

    def test_cleaning_interpolation_month_labels_mosaic_and_provenance(self):
        import numpy as np
        import rasterio

        result = json.loads(self.run_cli().stdout)
        self.assertEqual(result["rasters"], 24)
        output = self.root / "output"
        with rasterio.open(output / "VNM_bm_2017_01.tif") as src:
            january = src.read(1)
            self.assertEqual(src.shape, (2, 16))
            self.assertEqual(src.descriptions, ("b1",))
            self.assertEqual(src.dtypes, ("float32",))
            self.assertEqual(src.crs.to_epsg(), 4326)
            self.assertEqual(tuple(src.bounds), (0, 0, 16, 2))
        np.testing.assert_allclose(january[0, :8], [20, 20, 20, 0, 0, 1000.1, 20, 6553.4], rtol=1e-6)
        np.testing.assert_allclose(january[1, :8], [20, 0, 30, 30, 20, 0, 0, 0], rtol=1e-6)
        np.testing.assert_array_equal(january[:, 8:], [[50, 50, 0, 0, 50, 50, 50, 50]] * 2)
        with rasterio.open(output / "VNM_bm_2017_12.tif") as src:
            december = src.read(1)
        self.assertEqual(float(december[0, 0]), 130)
        self.assertEqual(float(december[0, 2]), 50)
        self.assertEqual(float(december[0, 6]), 0)
        with rasterio.open(output / "VNM_bm_2017_06.tif") as src:
            self.assertEqual(float(src.read(1)[0, 4]), 50)
        with rasterio.open(output / "VNM_bm_2018_01.tif") as src:
            january_next = src.read(1)
        self.assertEqual(float(january_next[0, 0]), 140)
        self.assertEqual(float(january_next[0, 2]), 50, "Use clean December, not its imputed value, as context")
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(len(manifest["inputs"]), 50)
        self.assertEqual([entry["source_year"] for entry in manifest["masks"]], [2017, 2017, 2017])
        self.assertIn("December", manifest["source_bugfix"])
        for entry in manifest["inputs"]:
            self.assertEqual(entry["sha256"], hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest())
        for entry in manifest["outputs"]:
            self.assertEqual(entry["sha256"], hashlib.sha256((output / entry["file"]).read_bytes()).hexdigest())

    def test_missing_previous_december_rejected_before_output(self):
        next(self.inputs.glob("VNP46A3.A2016336.h27v07.*")).unlink()
        result = self.run_cli(success=False)
        self.assertIn("preceding clean December", result.stderr)

    def test_mixed_nasa_collections_rejected(self):
        path = next(self.inputs.glob("*.h5"))
        path.rename(path.with_name(path.name.replace(".001.", ".002.")))
        result = self.run_cli(success=False)
        self.assertIn("Expected only NASA collection 001", result.stderr)

    def test_unprovided_mask_year_rejected(self):
        command = [sys.executable, "-m", "replication.prepare_nightlights", "--input-dir", str(self.inputs),
                   "--output-dir", str(self.root / "output"), "--year", "2017", "--mask", f"2017={self.mask}"]
        result = subprocess.run(command, text=True, capture_output=True, cwd=Path(__file__).resolve().parent.parent)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required for years [2016]", result.stderr)
        self.assertFalse((self.root / "output").exists())

    def test_incomplete_mask_coverage_rejected_without_partial_outputs(self):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        with rasterio.open(self.mask, "w", driver="GTiff", width=1, height=1,
                           count=1, dtype="uint8", crs="EPSG:4326",
                           transform=from_origin(0, 2, 1, 1)) as dst:
            dst.write(np.ones((1, 1), dtype="uint8"), 1)
        result = self.run_cli(success=False)
        self.assertIn("EOG mask does not cover all pixels", result.stderr)
        self.assertEqual(list(self.root.glob(".nightlights-*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
