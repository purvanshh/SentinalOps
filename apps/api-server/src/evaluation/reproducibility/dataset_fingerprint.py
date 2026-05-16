"""Dataset fingerprinting — detects mutation, contamination, and benchmark drift."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass
class FingerprintRecord:
    checksum: str
    item_count: int
    schema_hash: str
    label_distribution: dict[str, int]
    sample_checksums: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checksum": self.checksum,
            "item_count": self.item_count,
            "schema_hash": self.schema_hash,
            "label_distribution": self.label_distribution,
            "sample_checksums": self.sample_checksums,
        }


class DatasetFingerprint:
    """Compute and compare dataset fingerprints to detect contamination or drift.

    The fingerprint is order-independent (sorted serialization) so that
    cosmetic row reordering does not falsely flag drift.
    """

    SAMPLE_SIZE = 10

    def compute(self, dataset: Sequence[dict[str, Any]], label_field: str = "label") -> FingerprintRecord:
        sorted_items = sorted(
            [json.dumps(item, sort_keys=True, default=str) for item in dataset]
        )
        full_blob = "\n".join(sorted_items)
        checksum = self._sha(full_blob)

        label_dist: dict[str, int] = {}
        for item in dataset:
            lbl = str(item.get(label_field, "__missing__"))
            label_dist[lbl] = label_dist.get(lbl, 0) + 1

        keys = sorted({k for item in dataset for k in item.keys()})
        schema_hash = self._sha(",".join(keys))

        samples = sorted_items[: self.SAMPLE_SIZE]
        sample_checksums = [self._sha(s)[:8] for s in samples]

        return FingerprintRecord(
            checksum=checksum,
            item_count=len(dataset),
            schema_hash=schema_hash,
            label_distribution=label_dist,
            sample_checksums=sample_checksums,
        )

    def compute_from_file(self, path: Path, label_field: str = "label") -> FingerprintRecord:
        raw = json.loads(path.read_text())
        dataset = raw if isinstance(raw, list) else raw.get("incidents", raw.get("items", []))
        return self.compute(dataset, label_field=label_field)

    def compare(self, a: FingerprintRecord, b: FingerprintRecord) -> dict[str, Any]:
        mutations: list[str] = []
        if a.checksum != b.checksum:
            mutations.append("full_dataset_mutated")
        if a.item_count != b.item_count:
            mutations.append(f"item_count_changed:{a.item_count}->{b.item_count}")
        if a.schema_hash != b.schema_hash:
            mutations.append("schema_changed")
        if a.label_distribution != b.label_distribution:
            mutations.append("label_distribution_changed")
        return {
            "clean": len(mutations) == 0,
            "mutations": mutations,
            "fingerprint_a": a.to_dict(),
            "fingerprint_b": b.to_dict(),
        }

    def detect_label_leakage(
        self,
        predictions: list[dict[str, Any]],
        golden: list[dict[str, Any]],
        id_field: str = "incident_id",
        prediction_field: str = "prediction",
        label_field: str = "label",
    ) -> dict[str, Any]:
        """Detect if predictions suspiciously match golden labels with perfect accuracy."""
        golden_map = {str(g[id_field]): g[label_field] for g in golden if id_field in g and label_field in g}
        perfect_matches = 0
        checked = 0
        for pred in predictions:
            pid = str(pred.get(id_field, ""))
            if pid in golden_map:
                checked += 1
                if pred.get(prediction_field) == golden_map[pid]:
                    perfect_matches += 1

        match_rate = perfect_matches / checked if checked else 0.0
        # A match rate >0.99 on a large set is suspicious — flag for review.
        suspicious = checked >= 20 and match_rate > 0.99
        return {
            "checked": checked,
            "perfect_matches": perfect_matches,
            "match_rate": round(match_rate, 4),
            "suspicious_leakage": suspicious,
        }

    def _sha(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]
