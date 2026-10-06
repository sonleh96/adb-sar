"""Exercise the detection-preparation CLI on small, explicit FIRMS/GeoJSON fixtures.

Checks units and UTC dates/times, satellite preservation, overlap duplicates,
boundary ambiguity, unassigned locations, invalid source records and atomic output.
Run with: python -m replication.validate_fire_detections
"""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DetectionCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "firms.csv"
        self.gadm = self.root / "gadm.json"
        self.out = self.root / "output"
        features = []
        for gid, west, east in (("MMR.1_1", 95, 96), ("MMR.2_1", 96, 97)):
            features.append({"type": "Feature", "properties": {"GID_1": gid, "GID_0": "MMR"},
                             "geometry": {"type": "Polygon", "coordinates": [
                                 [[west, 20], [east, 20], [east, 21], [west, 21], [west, 20]]]}})
        self.gadm.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        self.rows = [self.row(), self.row(satellite="A", acq_time="0145", frp="0"),
                     self.row(acq_date="2022-12-31", acq_time="2359"),
                     self.row(acq_date="2023-01-01")]

    @staticmethod
    def row(**changes):
        return {"latitude": "20.5", "longitude": "95.5", "brightness": "321.8", "scan": "1.1",
                "track": "1.2", "acq_date": "2017-01-01", "acq_time": "51", "satellite": "T",
                "instrument": "MODIS", "confidence": "0", "version": "6.1", "bright_t31": "289.6",
                "frp": "14", "daynight": "N", "type": "2", **changes}

    def run_cli(self, *options, success=True):
        with self.source.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.rows[0].keys())
            writer.writeheader()
            writer.writerows(self.rows)
        result = subprocess.run([sys.executable, "-m", "replication.prepare_fire_detections",
                                 "--inputs", str(self.source), "--gadm", str(self.gadm),
                                 "--countries", "MMR", "--output-dir", str(self.out), *options],
                                cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 2, result.stdout + result.stderr)
        if not success:
            self.assertFalse(self.out.exists())
            self.assertEqual(list(self.root.glob(".fire-detections-*")), [])
        return result

    def read_rows(self, name="FRP_son.csv"):
        with (self.out / name).open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_measures_dates_satellites_and_lookup(self):
        self.run_cli("--write-dta")
        rows = self.read_rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual([(r["satellite"], r["acq_time"], r["year"], r["mon"]) for r in rows],
                         [("Terra", "0051", "2017", "1"), ("Aqua", "0145", "2017", "1"),
                          ("Terra", "2359", "2022", "12")])
        self.assertEqual([(float(r["frp"]), float(r["brightness"]), float(r["T31"])) for r in rows],
                         [(14.0, 321.8, 289.6), (0.0, 321.8, 289.6), (14.0, 321.8, 289.6)])
        self.assertEqual(self.read_rows("lon-lat-adm1.csv"),
                         [{"lon": "95.5", "lat": "20.5", "gid_1": "MMR.1_1", "country": "MYM"}])
        import pandas as pd
        frame = pd.read_stata(self.out / "FRP_son.dta")
        self.assertEqual(frame["acq_time"].tolist(), ["0051", "0145", "2359"])
        manifest = json.loads((self.out / "fire_manifest.json").read_text())
        self.assertEqual(manifest["counts"]["outside_dates"], 1)
        self.assertEqual(len(manifest["inputs"][0]["sha256"]), 64)

    def test_duplicates_error_then_explicit_drop(self):
        self.rows.append(self.rows[0].copy())
        result = self.run_cli(success=False)
        self.assertIn("Duplicate detection", result.stderr)
        self.run_cli("--duplicates", "drop-exact")
        self.assertEqual(len(self.read_rows()), 3)
        self.assertEqual(json.loads((self.out / "fire_manifest.json").read_text())["counts"]["exact_duplicates"], 1)

    def test_boundary_error_then_deterministic_assignment(self):
        self.rows = [self.row(longitude="96")]
        result = self.run_cli(success=False)
        self.assertIn("overlaps multiple", result.stderr)
        self.run_cli("--boundaries", "first", "--myanmar-code", "MMR")
        self.assertEqual(self.read_rows()[0]["gid_1"], "MMR.1_1")
        self.assertEqual(self.read_rows()[0]["country"], "MMR")

    def test_unassigned_error_then_keep(self):
        self.rows.append(self.row(longitude="99"))
        result = self.run_cli(success=False)
        self.assertIn("outside selected", result.stderr)
        self.run_cli("--unassigned", "keep")
        self.assertEqual(len(self.read_rows()), 4)
        self.assertEqual(self.read_rows()[-1]["gid_1"], "")
        self.assertEqual(len(self.read_rows("lon-lat-adm1.csv")), 2)

    def test_explicit_geometry_repair(self):
        data = json.loads(self.gadm.read_text())
        data["features"][0]["geometry"]["coordinates"] = [
            [[95, 20], [96, 21], [95, 21], [96, 20], [95, 20]]]
        data["features"] = data["features"][:1]
        self.gadm.write_text(json.dumps(data))
        self.rows = [self.row(latitude="20.1")]
        result = self.run_cli(success=False)
        self.assertIn("invalid or non-polygon", result.stderr)
        self.run_cli("--repair-invalid-geometries")
        self.assertEqual(self.read_rows()[0]["gid_1"], "MMR.1_1")
        manifest = json.loads((self.out / "fire_manifest.json").read_text())
        self.assertEqual(manifest["repaired_geometry_ids"], ["MMR.1_1"])

    def test_invalid_source_records(self):
        for changes, expected in [({"latitude": "nan"}, "Invalid latitude"),
                                  ({"acq_time": "2460"}, "Invalid UTC"),
                                  ({"instrument": "VIIRS"}, "Only MODIS"),
                                  ({"version": "6.1NRT"}, "Use standard MODIS")]:
            with self.subTest(changes=changes):
                self.rows = [self.row(**changes)]
                result = self.run_cli(success=False)
                self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
