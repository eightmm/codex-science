"""Regression coverage for byte-bound artifact views and selectors."""

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science import artifact_runtime as runtime
from codex_science.advanced_sidecars import validate_advanced_sidecars


# Literal output from 00f4dc83cb320405df9c4fb0cafee92d981b713d; tests never invoke Git.
BASE_SELECTION_FIXTURES = json.loads(r'''
[
  {
    "name": "small.csv",
    "bytes_hex": "613b623b630a313b323b330a343b353b360a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "small.csv",
      "artifact_sha256": "715914c0413e39ff50a4d19575ed35bab95f500724700afeaf7217882a3d0b6d",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 18,
      "viewer": "table",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 8,
        "max_records": 100
      },
      "preview": {
        "format": "delimited-text",
        "encoding": "utf-8",
        "delimiter": ",",
        "columns": [
          "a;b;c"
        ],
        "rows_preview": [
          [
            "1;"
          ]
        ]
      },
      "warnings": [
        "The table preview is bounded and is not a complete row count."
      ],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "52b4e5a209593e52651aed86a86c6ec334005272ab9041cd4bbf684903309c1e"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "small.csv",
      "artifact_sha256": "715914c0413e39ff50a4d19575ed35bab95f500724700afeaf7217882a3d0b6d",
      "viewer": "table",
      "selector_type": "column",
      "selector": {
        "column": "a;b;c"
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-df03e0a4f5ec5bd8c506",
      "fingerprint": "df03e0a4f5ec5bd8c506242cf6deb17ba847b46fd54abccbb04bbbf489aaf166"
    }
  },
  {
    "name": "bom.csv",
    "bytes_hex": "efbbbf6e616d652c76616c75650a616c7068612c370a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "bom.csv",
      "artifact_sha256": "33df0f8edd53ad30a006c23192d060d7269a2c07af7d2d7b55bb050996a8397a",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 22,
      "viewer": "table",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "format": "delimited-text",
        "encoding": "utf-8",
        "delimiter": ",",
        "columns": [
          "\ufeffname",
          "value"
        ],
        "rows_preview": [
          [
            "alpha",
            "7"
          ]
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "830f1605c92c9b248d7b46ed19eb1fa8de1cad47d4d1d1a17f16f45d823ed5de"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "bom.csv",
      "artifact_sha256": "33df0f8edd53ad30a006c23192d060d7269a2c07af7d2d7b55bb050996a8397a",
      "viewer": "table",
      "selector_type": "column",
      "selector": {
        "column": "\ufeffname"
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-76e6ea822b3c1ff28b6d",
      "fingerprint": "76e6ea822b3c1ff28b6d2b8cd4dee0434f3a6fbec5aae12b81dab047a6d95883"
    }
  },
  {
    "name": "separator.json",
    "bytes_hex": "7b2261223a2278e280a879227d",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "separator.json",
      "artifact_sha256": "2c9928872c171a83588f85ff4b91c37a37c7961d16cb8ac1b2dede324a9ec80b",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 13,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-8",
        "line_count_in_prefix": 2,
        "lines_preview": [
          {
            "line": 1,
            "text": "{\"a\":\"x"
          },
          {
            "line": 2,
            "text": "y\"}"
          }
        ],
        "json_type": "dict",
        "top_level_keys": [
          "a"
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "65bf532639681fef410d0f1735f391f72b21d2814deb096fd7ecdba8273898b9"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "separator.json",
      "artifact_sha256": "2c9928872c171a83588f85ff4b91c37a37c7961d16cb8ac1b2dede324a9ec80b",
      "viewer": "text",
      "selector_type": "line",
      "selector": {
        "line": 2
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-bc7eb95d7997e3c318e4",
      "fingerprint": "bc7eb95d7997e3c318e428acef6817957567b568931615a74214d821141aee20"
    }
  },
  {
    "name": "locus.bed",
    "bytes_hex": "636872310931300931310a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "locus.bed",
      "artifact_sha256": "20ab665a6aeab8a0c788ccf4f3181c8d805ebb0fdf2652ccb36e4cda1c002fb8",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 11,
      "viewer": "genome-track",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "format": "bed",
        "encoding": "utf-8",
        "headers_preview": [],
        "records_preview": [
          {
            "line": 1,
            "chrom": "chr1",
            "start": "10",
            "end": "11",
            "fields": []
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "a3672bf05036d1b6f543238e9f21472f3f41c1449c1c476d10efbfb88c4e644d"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "locus.bed",
      "artifact_sha256": "20ab665a6aeab8a0c788ccf4f3181c8d805ebb0fdf2652ccb36e4cda1c002fb8",
      "viewer": "genome-track",
      "selector_type": "locus",
      "selector": {
        "chrom": "chr1",
        "start": 10
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-17f637d47882ea6dbe16",
      "fingerprint": "17f637d47882ea6dbe16a4b6890137d09b24ea2f613cb831b87e98ed0cea78ea"
    }
  },
  {
    "name": "labels.csv",
    "bytes_hex": "6e616d652c76616c75650a616c7068612c370a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "labels.csv",
      "artifact_sha256": "da884892f29ef1d4709d1ca23a8cceb2a2ba03ec99c1f49f058ab0c4172d075d",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 19,
      "viewer": "table",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "format": "delimited-text",
        "encoding": "utf-8",
        "delimiter": ",",
        "columns": [
          "name",
          "value"
        ],
        "rows_preview": [
          [
            "alpha",
            "7"
          ]
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "881cecc1955b1486304cfeaafa55b82b10559da0d597fe18de163b1b378d0603"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "labels.csv",
      "artifact_sha256": "da884892f29ef1d4709d1ca23a8cceb2a2ba03ec99c1f49f058ab0c4172d075d",
      "viewer": "table",
      "selector_type": "row",
      "selector": {
        "row": "alpha"
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-aef65d01b3428097c9ff",
      "fingerprint": "aef65d01b3428097c9ff2bc548733f44e98d98ed3ba9df8682daaf3c44996932"
    }
  },
  {
    "name": "bytes.bin",
    "bytes_hex": "616263",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "bytes.bin",
      "artifact_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 3,
      "viewer": "binary",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "header_hex": "616263",
        "header_ascii": "abc"
      },
      "warnings": [
        "Binary preview is metadata only."
      ],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "04a17212b670fe08a6d168e887414e7da431a45f8ddd68809892575724f0ae74"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "bytes.bin",
      "artifact_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "viewer": "binary",
      "selector_type": "byte-range",
      "selector": {
        "offset": 0,
        "length": 3
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-bb1e4ee5efe597b052d8",
      "fingerprint": "bb1e4ee5efe597b052d8b49c371b085c5136098daa2bebf78966338df5e05786"
    }
  },
  {
    "name": "pointer.json",
    "bytes_hex": "7b2261223a317d",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "pointer.json",
      "artifact_sha256": "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 7,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-8",
        "line_count_in_prefix": 1,
        "lines_preview": [
          {
            "line": 1,
            "text": "{\"a\":1}"
          }
        ],
        "json_type": "dict",
        "top_level_keys": [
          "a"
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "2a6b3d6a24d64ee1dd455a13a771ce2d7d5ba2653988fcee6b90360992e4c2dd"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "pointer.json",
      "artifact_sha256": "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862",
      "viewer": "text",
      "selector_type": "json-pointer",
      "selector": {
        "path": "/a"
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-e77c5d4558eb96395874",
      "fingerprint": "e77c5d4558eb96395874895b39ca5b5c90b8ce506a81e76bf6b12bbc60bf80cd"
    }
  },
  {
    "name": "legacy.yaml",
    "bytes_hex": "6d6f64656c3a0a20206c723a20302e310a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "legacy.yaml",
      "artifact_sha256": "43e07ed4a1b571a83d554d34988dca6d971f92e3acb214d62541a9e48923ab99",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 17,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-8",
        "line_count_in_prefix": 2,
        "lines_preview": [
          {
            "line": 1,
            "text": "model:"
          },
          {
            "line": 2,
            "text": "  lr: 0.1"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "e2e520d54f5391695a8578412b5fef0093f75e42fb9cd00f6069a9601f8f9feb"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "legacy.yaml",
      "artifact_sha256": "43e07ed4a1b571a83d554d34988dca6d971f92e3acb214d62541a9e48923ab99",
      "viewer": "text",
      "selector_type": "json-pointer",
      "selector": {
        "pointer": "/model/lr"
      },
      "selected_by": "reviewer",
      "reason": "Base producer compatibility.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-5f944b27c0ca49656bd3",
      "fingerprint": "5f944b27c0ca49656bd37cb673bba73e2c9ca5d2882e601d50f558b3c0245f01"
    }
  }
]
''')


class ArtifactRuntimeValidityTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.descriptors = {}

    def describe(self, name, content, **bounds):
        path = self.root / name
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        descriptor = runtime.describe_runtime(path, **bounds).to_dict()
        self.descriptors[descriptor["artifact_path"]] = descriptor
        return descriptor

    def select(self, descriptor, kind, selector):
        return runtime.build_selection(
            descriptor, selector_type=kind, selector=selector,
            selected_by="reviewer", reason="Inspect selected bytes.",
        )

    def resign(self, record, id_key, prefix):
        record = dict(record)
        record.pop("fingerprint", None)
        record.pop(id_key, None)
        fingerprint = runtime._fingerprint(record)
        return {**record, "fingerprint": fingerprint, id_key: prefix + fingerprint[:20]}

    def sidecars(self, *records, media_type=None):
        manifest = {"artifacts": []}
        verified = {}
        for name, kind, payload in records:
            path = self.root / name
            path.write_text(json.dumps(payload))
            verified[name] = path
            manifest["artifacts"].append({
                "path": name, "kind": kind,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
        targets = {payload["artifact_path"] for _, kind, payload in records if kind == "artifact-selection"}
        for relative in targets:
            descriptor = self.descriptors.get(relative)
            if descriptor is not None:
                name = relative + ".runtime.json"
                path = self.root / name
                path.write_text(json.dumps(descriptor))
                verified[name] = path
                manifest["artifacts"].append({
                    "path": name, "kind": "artifact-runtime-descriptor",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
            data = self.root / relative
            if data.exists():
                verified[relative] = data
                manifest["artifacts"].append({
                    "path": relative, "kind": "metrics",
                    "sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
                    **({"media_type": media_type} if media_type is not None else {}),
                })
        return validate_advanced_sidecars(manifest, self.root, verified)

    def assert_stored_active(self, selection, *, media_type=None):
        result = self.sidecars(("selection.json", "artifact-selection", selection), media_type=media_type)
        self.assertEqual("active", result["artifact_selections"][0]["status"])

    def test_bom_json_pointers_resolve_without_changing_encoding_or_text(self):
        descriptor = self.describe("bom.json", b"\xef\xbb\xbf" + b'{"a":1}')
        self.assertEqual("utf-8", descriptor["preview"]["encoding"])
        self.assertTrue(descriptor["preview"]["lines_preview"][0]["text"].startswith("\ufeff"))
        self.assertEqual("dict", descriptor["preview"]["json_type"])
        legacy = json.loads(json.dumps(descriptor))
        legacy["preview"]["json_type"] = "invalid"
        legacy["preview"].pop("top_level_keys")
        legacy.pop("fingerprint")
        legacy["fingerprint"] = runtime._fingerprint(legacy)
        for context in (descriptor, legacy):
            for pointer in ("", "/a"):
                with self.subTest(pointer=pointer, legacy=context is legacy):
                    selection = self.select(context, "json-pointer", {"pointer": pointer})
                    self.descriptors["bom.json"] = context
                    result = self.sidecars(("selection.json", "artifact-selection", selection))
                    self.assertEqual("active", result["artifact_selections"][0]["status"])

    def test_base_produced_selections_remain_valid_as_stored_sidecars(self):
        for fixture in BASE_SELECTION_FIXTURES:
            with self.subTest(name=fixture["name"]):
                path = self.root / fixture["name"]
                path.write_bytes(bytes.fromhex(fixture["bytes_hex"]))
                descriptor = fixture["descriptor"]
                selection = fixture["selection"]
                runtime.validate_runtime_descriptor(descriptor)
                runtime.validate_selection(selection)
                self.descriptors[fixture["name"]] = descriptor
                result = self.sidecars(("selection.json", "artifact-selection", selection))
                self.assertEqual("active", result["artifact_selections"][0]["status"])
                self.descriptors.clear()
                result = self.sidecars(("selection.json", "artifact-selection", selection))
                self.assertEqual("active", result["artifact_selections"][0]["status"])

    def test_replacement_between_hash_and_preview_is_refused(self):
        descriptor = self.describe("data.csv", "a,b\nold,1\n")
        read_head = runtime._read_head

        def replace_then_read(path, bound):
            path.write_text("a,b\nnew,2\n")
            return read_head(path, bound)

        with patch.object(runtime, "_read_head", side_effect=replace_then_read):
            with self.assertRaisesRegex(ValueError, "changed|match"):
                runtime.describe_runtime(
                    self.root / "data.csv", artifact_sha256=descriptor["artifact_sha256"],
                )
        directory = self.root / "directory"
        directory.mkdir()
        child = directory / "data.txt"
        child.write_text("original")
        preview_directory = runtime._directory_preview

        def replace_directory_then_read(path, bound, media):
            child.write_text("changed")
            return preview_directory(path, bound, media)

        with patch.object(runtime, "_directory_preview", side_effect=replace_directory_then_read):
            with self.assertRaisesRegex(ValueError, "changed"):
                runtime.describe_runtime(directory)

    def test_proposal_must_retain_selection_artifact_identity(self):
        descriptor = self.describe("data.csv", "a,b\nx,1\n")
        selection = self.select(descriptor, "cell", {"row": 1, "column": "b"})
        proposal = runtime.build_transform_proposal(
            selection, operation="inspect", parameters={}, reason="Review bytes.",
            affected_steps=["review"], expected_outputs=[], proposed_by="reviewer",
        )
        runtime.validate_transform_proposal(proposal, selection)
        for field, value in (("artifact_path", "other.csv"), ("artifact_sha256", "0" * 64)):
            with self.subTest(field=field):
                forged = self.resign({**proposal, field: value}, "proposal_id", "transform-")
                with self.assertRaisesRegex(ValueError, "artifact|selection"):
                    runtime.validate_transform_proposal(forged, selection)
                with self.assertRaisesRegex(ValueError, "artifact|selection"):
                    self.sidecars(
                        ("selection.json", "artifact-selection", selection),
                        ("proposal.json", "transform-proposal", forged),
                    )

    def test_table_regions_refuse_missing_reversed_and_malformed_coordinates(self):
        descriptor = self.describe("data.csv", "a,b\nx,1\ny,2\n")
        for kind, selector in (
            ("row", {"row": 999}), ("row", {"row": -1}),
            ("column", {"column": "missing"}), ("column", {"column": 999}),
            ("cell", {"row": 1, "column": "missing"}),
            ("range", {"row_start": 2, "row_end": 1}),
            ("range", {"start": 2, "end": 1}),
            ("range", {"row_start": 0, "row_end": 999}),
        ):
            with self.subTest(kind=kind, selector=selector), self.assertRaises(ValueError):
                self.select(descriptor, kind, selector)
        for kind, selector in (
            ("row", {"row": "bad"}), ("row", {"row": True}),
            ("row", {"unknown": 1}), ("cell", {"row": 1}),
            ("range", {"row_start": 1}), ("range", {"unknown": 1}),
        ):
            with self.subTest(unverified=selector):
                selection = self.select(descriptor, kind, selector)
                runtime.validate_selection(selection)
                self.sidecars(("selection.json", "artifact-selection", selection))
        for row in (0, 1, 2):
            self.select(descriptor, "cell", {"row": row, "column": "b"})
        self.select(descriptor, "range", {"row_start": 1, "row_end": 1})
        for content in ("", "a,b\n"):
            empty = self.describe("empty.csv", content)
            with self.assertRaises(ValueError):
                self.select(empty, "row", {"row": 0})
        ragged = self.describe("ragged.csv", "a,b\nx\n")
        with self.assertRaises(ValueError):
            self.select(ragged, "cell", {"row": 1, "column": "b"})
        bounded = self.describe("bounded.csv", "a,b\nx,1\ny,2\n", max_records=1)
        self.select(bounded, "row", {"row": 1})
        self.select(bounded, "row", {"row": 999})

    def test_json_pointer_resolves_escapes_arrays_and_root(self):
        descriptor = self.describe("data.json", '{"a/b":{"~key":[null,7]}}\n')
        for pointer in ("/missing/7", "/a~1b/~0key/2", "/a~1b/~0key/-1", "a", "/a~2b", "/a~1b/~0key/01", "/a~1b/~0key/0/x"):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                self.select(descriptor, "json-pointer", {"pointer": pointer})
        for pointer in ("", "/a~1b/~0key/0", "/a~1b/~0key/1"):
            self.select(descriptor, "json-pointer", {"pointer": pointer})
        for content, bounds in (("", {}), ("{bad", {})):
            incomplete = self.describe("incomplete.json", content, **bounds)
            with self.assertRaises(ValueError):
                self.select(incomplete, "json-pointer", {"pointer": "/a"})
        bounded = self.describe("bounded.json", '{\n"a":1\n}', max_records=1)
        for pointer in ("/a", "/missing"):
            selection = self.select(bounded, "json-pointer", {"pointer": pointer})
            self.sidecars(("selection.json", "artifact-selection", selection))
        for suffix, content in (
            ("yaml", "model:\n  lr: 0.1\n"), ("yml", "model:\n  lr: 0.1\n"),
            ("toml", "[model]\nlr = 0.1\n"), ("jsonl", '{"a":1}\n{"a":2}\n'),
            ("yaml", "model:\n" + "  lr: 0.1\n" * 101),
        ):
            with self.subTest(suffix=suffix, lines=len(content.splitlines())):
                opaque = self.describe("other." + suffix, content)
                for pointer in ("/model/lr", "/missing", "opaque locator"):
                    selection = self.select(opaque, "json-pointer", {"pointer": pointer})
                    self.sidecars(("selection.json", "artifact-selection", selection))
        invalid = self.describe("invalid.json", '{\n"broken":\n', max_records=1)
        selection = self.select(invalid, "json-pointer", {"pointer": "/broken"})
        self.assertFalse(runtime._validate_selection_region(selection, invalid))
        invalid = self.describe("invalid.json", '{\n"broken":\n', max_records=2)
        with self.assertRaisesRegex(ValueError, "JSON pointer does not resolve"):
            self.select(invalid, "json-pointer", {"pointer": "/broken"})
        for separator in ("\u2028", "\u0085"):
            for indent in (None, 2):
                with self.subTest(separator=separator, indent=indent):
                    content = json.dumps({"a": "x" + separator + "y"}, ensure_ascii=False, indent=indent)
                    descriptor = self.describe("data.json", content)
                    # Exercise the same descriptor-only interface used by CLI select.
                    selection = self.select(json.loads(json.dumps(descriptor)), "json-pointer", {"pointer": "/a"})
                    self.sidecars(("selection.json", "artifact-selection", selection))
                    with patch.object(runtime, "MAX_RUNTIME_BYTES", len(content.encode())):
                        self.sidecars(("selection.json", "artifact-selection", selection))
                    with self.assertRaises(ValueError):
                        self.select(descriptor, "json-pointer", {"pointer": "/missing"})
        for suffix, media in (("geojson", "application/geo+json"), ("dat", "application/json"), ("geojson", "APPLICATION/GEO+JSON")):
            for separator in ("\u2028", "\u0085"):
                with self.subTest(suffix=suffix, media=media, separator=separator):
                    content = json.dumps({"a": "x" + separator + "y"}, ensure_ascii=False)
                    descriptor = self.describe("data." + suffix, content, media_type=media)
                    self.assertEqual("dict", descriptor["preview"]["json_type"])
                    selection = self.select(json.loads(json.dumps(descriptor)), "json-pointer", {"pointer": "/a"})
                    self.sidecars(("selection.json", "artifact-selection", selection))
                    with self.assertRaises(ValueError):
                        self.select(descriptor, "json-pointer", {"pointer": "/missing"})
        zero = self.describe("data.json", "0")
        selection = self.select(zero, "json-pointer", {"pointer": ""})
        self.sidecars(("selection.json", "artifact-selection", selection))
        for content in ("", "{bad", '{"a":"x\ny"}'):
            with self.subTest(content=content):
                invalid = self.describe("data.json", content)
                forged = self.resign({**selection, "artifact_sha256": invalid["artifact_sha256"]}, "selection_id", "selection-")
                self.assert_stored_active(forged)

    def test_table_selections_beyond_record_bound_are_accepted_without_resolution(self):
        semicolon = "a;b;c\n1;2;3\n4;5;6\n"
        for bound in (8, len(semicolon)):
            with self.subTest(semicolon_bound=bound):
                view = self.describe("small.csv", semicolon, max_bytes=bound)
                for kind, selector in (
                    ("column", {"column": "b"}), ("cell", {"row": 1, "column": "b"}),
                    ("range", {"column_start": "b", "column_end": "c"}),
                ):
                    selection = self.select(view, kind, selector)
                    self.sidecars(("selection.json", "artifact-selection", selection))
                    if bound < len(semicolon):
                        self.assertFalse(runtime._validate_selection_region(selection, view))
                if bound == len(semicolon):
                    self.assertEqual(["a", "b", "c"], view["preview"]["columns"])
                    with self.assertRaises(ValueError):
                        self.select(view, "column", {"column": "missing"})
                else:
                    self.assertEqual(["a;b;c"], view["preview"]["columns"])
                    for kind, selector in (("column", {"column": "missing"}), ("column", {"column": 999}),
                                           ("row", {"row": 999}), ("cell", {"row": 999, "column": 999})):
                        self.select(view, kind, selector)
        content = "name,value\n" + "alpha,7\n" * (runtime.MAX_RUNTIME_RECORDS + 1)
        descriptor = self.describe("data.csv", content, max_records=100)
        for kind, selector in (
            ("row", {"row": 500}), ("cell", {"row": 500, "column": "value"}),
            ("range", {"row_start": 500, "row_end": runtime.MAX_RUNTIME_RECORDS + 1}),
        ):
            with self.subTest(kind=kind):
                selection = self.select(descriptor, kind, selector)
                self.sidecars(("selection.json", "artifact-selection", selection))
        selection = self.select(descriptor, "row", {"row": runtime.MAX_RUNTIME_RECORDS + 1})
        self.sidecars(("selection.json", "artifact-selection", selection))
        for kind, selector in (
            ("row", {"row": -1}),
            ("range", {"row_start": 501, "row_end": 500}),
        ):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                self.select(descriptor, kind, selector)
        for kind, selector in (("cell", {"row": 500, "column": "missing"}),
                               ("column", {"column": "missing"}), ("column", {"column": 999})):
            selection = self.select(descriptor, kind, selector)
            self.assertFalse(runtime._validate_selection_region(selection, descriptor))
            self.sidecars(("selection.json", "artifact-selection", selection))
        for row in (True, "500"):
            selection = self.select(descriptor, "row", {"row": row})
            self.sidecars(("selection.json", "artifact-selection", selection))
        small = self.describe("small.csv", "name,value\nalpha,7\n", max_records=1)
        with self.assertRaises(ValueError):
            self.select(small, "row", {"row": 2})
        header = "name,value,third\n"
        content = header + "x,1,2\n"
        for bound in (1, 5, len(header) - 1):
            with self.subTest(bound=bound):
                partial = self.describe("data.csv", content, max_bytes=bound)
                for kind, selector in (("column", {"column": "third"}), ("cell", {"row": 1, "column": "third"})):
                    selection = self.select(partial, kind, selector)
                    with patch.object(runtime, "MAX_RUNTIME_BYTES", bound):
                        self.sidecars(("selection.json", "artifact-selection", selection))
                self.select(partial, "column", {"column": 3})
                with self.assertRaises(ValueError):
                    self.select(partial, "column", {"column": -1})
                for column in (None, True):
                    selection = self.select(partial, "column", {"column": column})
                    self.sidecars(("selection.json", "artifact-selection", selection))
        for bound in (len(header), len(content)):
            with self.subTest(bound=bound):
                view = self.describe("data.csv", content, max_bytes=bound)
                self.select(view, "column", {"column": "third"})
                if bound == len(content):
                    with self.assertRaises(ValueError):
                        self.select(view, "column", {"column": "missing"})
                else:
                    self.select(view, "column", {"column": "missing"})
        quoted = self.describe("quoted.csv", '"multi\nline",third\nx,1\n', max_bytes=7)
        self.select(quoted, "column", {"column": "third"})
        quoted_header = '"multi\nline",third\n'
        quoted = self.describe("quoted.csv", quoted_header + "x,1\n", max_bytes=len(quoted_header))
        self.select(quoted, "column", {"column": "missing"})
        empty = self.describe("empty.csv", "")
        for column in (0, "third"):
            with self.subTest(column=column), self.assertRaises(ValueError):
                self.select(empty, "column", {"column": column})

    def test_text_selections_beyond_byte_prefix_are_accepted_without_resolution(self):
        descriptor = self.describe("data.txt", "entry\n" * 9000, max_bytes=64, max_records=2)
        for kind, selector in (("line", {"line": 9000}), ("line-range", {"start": 8999, "end": 9000})):
            with self.subTest(kind=kind):
                selection = self.select(descriptor, kind, selector)
                with patch.object(runtime, "MAX_RUNTIME_BYTES", 64):
                    self.sidecars(("selection.json", "artifact-selection", selection))
        selection = self.select(descriptor, "line", {"line": "9000"})
        self.sidecars(("selection.json", "artifact-selection", selection))
        for selector in ({"line": 0}, {"line": -1}):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                self.select(descriptor, "line", selector)
        small = self.describe("small.txt", "a\nb\n", max_bytes=4, max_records=1)
        self.select(small, "line", {"line": 2})
        for kind, selector in (("line", {"line": 3}), ("line-range", {"start": 2, "end": 999})):
            selection = self.select(small, kind, selector)
            self.assertFalse(runtime._validate_selection_region(selection, small))
        full = self.describe("small.txt", "a\nb\n", max_bytes=4, max_records=2)
        self.select(full, "line", {"line": 2})
        with self.assertRaises(ValueError):
            self.select(full, "line", {"line": 3})
        with self.assertRaises(ValueError):
            self.select(full, "line-range", {"start": 2, "end": 3})
        for media in ("application/geo+json", "APPLICATION/GEO+JSON", "application/json"):
            with self.subTest(media=media):
                content = json.dumps({"a": "x\u2028y\u0085z"}, ensure_ascii=False)
                partial = self.describe("data.geojson", content, media_type=media, max_bytes=5)
                selection = self.select(partial, "line", {"line": 2})
                with patch.object(runtime, "MAX_RUNTIME_BYTES", 5):
                    self.sidecars(("selection.json", "artifact-selection", selection), media_type=media)
                self.sidecars(("selection.json", "artifact-selection", selection), media_type=media)
                complete = self.describe("data.geojson", content, media_type=media)
                self.assert_stored_active(selection, media_type=media)
                self.assertEqual(1, complete["preview"]["line_count_in_prefix"])
                with self.assertRaises(ValueError):
                    self.select(complete, "line", {"line": 2})

    def test_json_pointer_beyond_byte_bound_is_accepted_without_resolution(self):
        content = json.dumps({"results": [7], "padding": "x" * (5 * 1024 * 1024)})
        descriptor = self.describe("data.json", content)
        selection = self.select(descriptor, "json-pointer", {"pointer": "/results/0"})
        self.sidecars(("selection.json", "artifact-selection", selection))
        with patch.object(runtime, "MAX_RUNTIME_BYTES", 64):
            self.sidecars(("selection.json", "artifact-selection", selection))
        for pointer in ("results/0", "/results/~2"):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                self.select(descriptor, "json-pointer", {"pointer": pointer})
        small = self.describe("small.json", '{"results":[7]}')
        self.select(small, "json-pointer", {"pointer": "/results/0"})
        with self.assertRaises(ValueError):
            self.select(small, "json-pointer", {"pointer": "/results/1"})

    def test_stored_regions_stay_active_and_refreshed_bytes_stay_stale(self):
        descriptor = self.describe("data.csv", "a,b\nx,1\n")
        selection = self.select(descriptor, "row", {"row": 1})
        forged = self.resign({**selection, "selector": {"row": 999}}, "selection_id", "selection-")
        self.assert_stored_active(forged)
        (self.root / "data.csv").write_text("")
        result = self.sidecars(("selection.json", "artifact-selection", selection))
        self.assertEqual("stale-anchor", result["artifact_selections"][0]["status"])
        for name, content, kind, valid, invalid in (
            ("data.json", '{"a":[1]}', "json-pointer", {"pointer": "/a/0"}, {"pointer": "/missing/7"}),
            ("data.bin", b"abc", "byte-range", {"start": 0, "end": 3}, {"start": 0, "end": 4}),
        ):
            with self.subTest(name=name):
                descriptor = self.describe(name, content)
                selection = self.select(descriptor, kind, valid)
                self.sidecars(("selection.json", "artifact-selection", selection))
                forged = self.resign({**selection, "selector": invalid}, "selection_id", "selection-")
                self.assert_stored_active(forged)
        field_limit = csv.field_size_limit()
        content = "name,value\nfirst,1\nsecond," + "x" * max(140000, field_limit + 1) + "\n"
        descriptor = self.describe("data.csv", content, max_bytes=64, max_records=1)
        for kind, selector in (
            ("cell", {"row": 1, "column": "value"}), ("row", {"row": 0}),
            ("column", {"column": "value"}), ("range", {"row_start": 1, "row_end": 1}),
        ):
            with self.subTest(kind=kind, selector=selector):
                selection = self.select(descriptor, kind, selector)
                result = self.sidecars(("selection.json", "artifact-selection", selection))
                self.assertEqual("active", result["artifact_selections"][0]["status"])
        for row in (2, 3):
            with self.subTest(unverified_row=row):
                selection = self.select(descriptor, "cell", {"row": row, "column": "value"})
                result = self.sidecars(("selection.json", "artifact-selection", selection))
                self.assertEqual("active", result["artifact_selections"][0]["status"])
        forged = self.resign({**selection, "selector": {"row": 2, "column": "missing"}},
                             "selection_id", "selection-")
        self.assert_stored_active(forged)
        # Creation still reports a reader error when its requested preview cannot be built.
        with self.assertRaisesRegex(ValueError, "CSV.*field"):
            runtime.describe_runtime(self.root / "data.csv")
        content = "name,value\nfirst,1\nsecond," + "x" * field_limit + "\n"
        descriptor = self.describe("data.csv", content, max_bytes=64, max_records=1)
        selection = self.select(descriptor, "cell", {"row": 2, "column": "value"})
        self.sidecars(("selection.json", "artifact-selection", selection))
        forged = self.resign({**selection, "selector": {"row": 3, "column": "value"}}, "selection_id", "selection-")
        self.assert_stored_active(forged)
        self.assertEqual(field_limit, csv.field_size_limit())
        descriptor = self.describe("data.csv", "x" * (field_limit + 1) + ",value\nx,1\n", max_bytes=64)
        selection = self.select(descriptor, "cell", {"row": 1, "column": "value"})
        result = self.sidecars(("selection.json", "artifact-selection", selection))
        self.assertEqual("active", result["artifact_selections"][0]["status"])
        self.assertEqual(field_limit, csv.field_size_limit())

        def malformed_records():
            yield ["name", "value"]
            raise csv.Error("malformed CSV record")

        with patch.object(runtime.csv, "reader", return_value=malformed_records()):
            with self.assertRaisesRegex(ValueError, "CSV.*malformed"):
                runtime._table_preview(self.root / "data.csv", 64, 1)
        self.descriptors.clear()
        with patch.object(runtime, "_table_preview", side_effect=AssertionError("unexpected unverified parse")):
            self.assert_stored_active(selection)

    def test_line_and_byte_coordinate_edges_and_reversed_validation(self):
        text = self.describe("data.txt", "first\nsecond\n")
        binary = self.describe("data.bin", b"abc")
        table = self.describe("data.csv", "name,value\nfirst,1\n")
        trajectory = self.describe("data.xyz", "1\nframe\nH 0 0 0\n")
        genome = self.describe("data.bed", "chr1\t0\t1\n")
        valid_cases = (
            (text, "line", ({"line": 2}, {"line": "1"}, {"unknown": 1}, {"line": 1, "row_start": 9, "row_end": -1})),
            (text, "line-range", (
                {"start": 1, "end": 1}, {"start": 1, "end": 2}, {"line_start": 1, "line_end": 2},
                {"row_start": 999, "row_end": 999}, {"row_start": 9, "row_end": -1},
                {"column_start": 0, "column_end": 0}, {"start": 1, "end": 1, "row_start": 0, "row_end": 0},
                {"start": 1, "end": 1, "line_start": 1}, {"unknown": 1},
                {"start": 1, "end": 1, "start_line": 1, "end_line": 1},
            )),
            (table, "range", (
                {"row_start": 0, "row_end": 1}, {"line_start": 999, "line_end": 999},
                {"line_start": 9, "line_end": -1}, {"row_start": 1, "row_end": 1, "column_start": 0},
                {"row_start": 1}, {"start_row": 0, "end_row": 1, "start_column": 0, "end_column": 1},
            )),
            (table, "row", ({"row": 1}, {"row": 1, "start": 0, "end": 0})),
            (table, "column", ({"column": "value"}, {"column": "value", "line_start": 0, "line_end": 0}, {"column": True})),
            (table, "cell", (
                {"row": 1, "column": "value"}, {"row": 1, "column": "value", "row_start": 0, "row_end": 0},
                {"row": 1, "column": None},
            )),
            (binary, "byte-range", (
                {"start": 0, "end": 3}, {"start": 0, "end": 0}, {"start": "0", "end": 1}, {"start": 0},
                {"start": 0, "end": 0, "row_start": 0, "row_end": 0},
            )),
            (trajectory, "frame-range", (
                {"start": 0, "end": 0}, {"start": "0", "end": 1},
                {"row_start": 999, "row_end": 999}, {"start": 0}, {"unknown": 1}, {"start": True, "end": 1},
            )),
            (trajectory, "frame", ({"frame": 0}, {"frame": "0"}, {"frame": 0, "line_start": 0, "line_end": 0})),
            (genome, "interval", ({"chrom": "chr1", "start": 0, "end": 1}, {"start": 0})),
            (genome, "locus", ({"chrom": "chr1", "pos": 1}, {"row_start": 0, "row_end": 0})),
        )
        for view, kind, selectors in valid_cases:
            for selector in selectors:
                with self.subTest(kind=kind, unverified_or_valid=selector):
                    selection = self.select(view, kind, selector)
                    runtime.validate_selection(selection)
                    self.sidecars(("selection.json", "artifact-selection", selection))
                    self.assertEqual(selector, selection["selector"])
        invalid_cases = (
            (text, "line", ({"line": 0}, {"line": 3})),
            (text, "line-range", ({"start": 0, "end": 0}, {"start": 2, "end": 1})),
            (binary, "byte-range", ({"start": 0, "end": 4}, {"start": 2, "end": 1})),
            (trajectory, "frame-range", ({"start": 1, "end": -1}, {"start": 2, "end": 1})),
            (trajectory, "frame", ({"frame": -1},)),
            (genome, "interval", ({"start": 1, "end": -1}, {"start": 2, "end": 1})),
            (genome, "locus", ({"start": 1, "end": -1},)),
        )
        for view, kind, selectors in invalid_cases:
            for selector in selectors:
                with self.subTest(kind=kind, invalid=selector), self.assertRaises(ValueError):
                    self.select(view, kind, selector)
                valid = self.select(view, kind, {"legacy": True})
                forged = self.resign({**valid, "selector": selector}, "selection_id", "selection-")
                runtime.validate_selection(forged)
                self.assertEqual("stale-anchor", runtime.stale_selection(forged, {})["status"])
                self.assert_stored_active(forged)
        empty = self.describe("empty.bin", b"")
        with self.assertRaises(ValueError):
            self.select(empty, "byte-range", {"start": 0, "end": 0})

    def test_opaque_selector_shapes_remain_unverified_without_rewriting(self):
        for name, content in (("data.csv", "name,value\nx,1\n"), ("data.txt", "one\n"),
                              ("data.bin", b"abc"), ("data.bed", "chr1\t10\t11\n"),
                              ("data.xyz", "1\nframe\nH 0 0 0\n")):
            view = self.describe(name, content)
            for kind in runtime.VIEWER_SELECTIONS[view["viewer"]]:
                for selector in ({"legacy": {"start": -1}}, {"row": {"label": "alpha"}},
                                 {"row": []}, {"column": 1.5}, {"pointer": None}, {"json_pointer": {"path": "/a"}}):
                    with self.subTest(kind=kind, selector=selector):
                        selection = self.select(view, kind, selector)
                        runtime.validate_selection(selection)
                        self.sidecars(("selection.json", "artifact-selection", selection))
                        self.assertEqual(selector, selection["selector"])

    def test_csv_full_dialect_preserves_quoted_delimiters_and_newlines(self):
        for content, expected in (
            ("name,value\n'alpha,beta',7\n", [["alpha,beta", "7"]]),
            ('name,value\nA, "x,y"\n', [["A", "x,y"]]),
            ('name,value\n"alpha,beta","x\ny"\n', [["alpha,beta", "x\ny"]]),
        ):
            with self.subTest(content=content):
                descriptor = self.describe("data.csv", content)
                self.assertEqual(expected, descriptor["preview"]["rows_preview"])
        bounded = self.describe("data.csv", "a,b\n1,2\n3,4\n", max_records=1)
        self.assertTrue(bounded["warnings"])
        content = 'a,b\n' + 'x,1\n' * 2047 + '"foo""\nbar",2\n'
        descriptor = self.describe("data.csv", content, max_records=2049)
        self.assertEqual(2048, len(descriptor["preview"]["rows_preview"]))
        self.assertEqual(['foo"\nbar', "2"], descriptor["preview"]["rows_preview"][-1])
        self.select(descriptor, "row", {"row": 2048})
        with self.assertRaises(ValueError):
            self.select(descriptor, "row", {"row": 2049})
        content = '"name\nextra",value\n\'alpha\',7\n\'alpha\',7\n'
        descriptor = self.describe("data.csv", content)
        self.assertEqual(["name\nextra", "value"], descriptor["preview"]["columns"])
        self.assertEqual([["'alpha'", "7"], ["'alpha'", "7"]], descriptor["preview"]["rows_preview"])
        self.assertEqual([], descriptor["warnings"])
        column = self.select(descriptor, "column", {"column": "value"})
        self.sidecars(("selection.json", "artifact-selection", column))
        selection = self.select(descriptor, "row", {"row": 2})
        self.sidecars(("selection.json", "artifact-selection", selection))
        with self.assertRaises(ValueError):
            self.select(descriptor, "row", {"row": 3})
        forged = self.resign({**selection, "selector": {"row": 3}}, "selection_id", "selection-")
        self.assert_stored_active(forged)
        standard = list(csv.reader("name,value\n'alpha,beta',7\n".splitlines()))
        self.assertEqual((2, 3), (len(standard[0]), len(standard[1])))
        for content, expected in (
            ("name,value\nx, 7\n", [["x", " 7"]]),
            ("name,value\n'alpha,beta',7", [["alpha,beta", "7"]]),
            ("name,value\n'a,b',7,extra\n", [["'a", "b'", "7", "extra"]]),
            ('name,value\n"odd"suffix,7\n\'alpha,beta\',7\n', [['"odd"suffix', "7"], ["alpha,beta", "7"]]),
        ):
            with self.subTest(content=content):
                descriptor = self.describe("data.csv", content)
                self.assertEqual(expected, descriptor["preview"]["rows_preview"])
        content = '"name\nextra",value\n\'alpha\',7\n\'alpha\',7\n'
        bound = len('"name\nextra",value\n\'alpha\',')
        partial = self.describe("data.csv", content, max_bytes=bound)
        self.assertEqual(["name\nextra", "value"], partial["preview"]["columns"])
        self.assertEqual("'alpha'", partial["preview"]["rows_preview"][0][0])
        self.assertTrue(partial["warnings"])

    def test_unicode_boms_are_decoded_before_csv_and_graph_parsing(self):
        for encoding in ("utf-8-sig", "utf-16", "utf-32", "utf-16-be", "utf-32-be"):
            with self.subTest(encoding=encoding):
                marker = {"utf-16-be": b"\xfe\xff", "utf-32-be": b"\x00\x00\xfe\xff"}.get(encoding, b"")
                descriptor = self.describe("data.csv", marker + "name,value\nalpha,7\n".encode(encoding))
                first_column = "\ufeffname" if encoding == "utf-8-sig" else "name"
                self.assertEqual([first_column, "value"], descriptor["preview"]["columns"])
                self.assertEqual([["alpha", "7"]], descriptor["preview"]["rows_preview"])
                graph = self.describe("data.cyjs", marker + '{"nodes":[{}],"edges":[]}'.encode(encoding))
                self.assertEqual(1, graph["preview"]["node_count"])
        with self.assertRaises(ValueError):
            self.describe("broken.csv", b"\xff\xfe{")
        for encoding in ("utf-16", "utf-32"):
            with self.subTest(encoding=encoding):
                partial = self.describe("partial.csv", ("name,value\n" + "alpha,7\n" * 10).encode(encoding), max_bytes=65)
                self.assertEqual(["name", "value"], partial["preview"]["columns"])
                self.assertTrue(partial["warnings"])
                empty = self.describe("empty.csv", "".encode(encoding))
                self.assertEqual([], empty["preview"]["columns"])
                graph_data = ('{"nodes":[{}],"edges":[]}' + " " * 100).encode(encoding)
                graph = self.describe("partial.cyjs", graph_data, max_bytes=65 if encoding == "utf-16" else 129)
                self.assertEqual(1, graph["preview"]["node_count"])
        surrogate = ("a" * 31 + "\U0001f600tail").encode("utf-16")
        partial = self.describe("surrogate.txt", surrogate, max_bytes=66)
        self.assertEqual("a" * 31, partial["preview"]["lines_preview"][0]["text"])
        self.assertTrue(partial["warnings"])
        for malformed in (
            b"\xff\xfe\x00\xd8\x00\x00" + b"a\x00" * 40,
            b"\xff\xfe\x00\x00\x00\x00\x11\x00" + b"a\x00\x00\x00" * 40,
        ):
            with self.subTest(malformed=malformed[:8]), self.assertRaises(ValueError):
                self.describe("malformed.txt", malformed, max_bytes=65)
        with self.assertRaises(ValueError):
            self.describe("incomplete.txt", surrogate[:66])
        for encoding in ("utf-8", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                data = "name,value\nx,\u00e9\n".encode(encoding)
                bound = data.index("\u00e9".encode("utf-8")) + 1
                partial = self.describe("data.csv", data, max_bytes=bound)
                first_column = "\ufeffname" if encoding == "utf-8-sig" else "name"
                self.assertEqual([first_column, "value"], partial["preview"]["columns"])
                self.assertNotEqual("latin-1", partial["preview"]["encoding"])
                selection = self.select(partial, "column", {"column": first_column})
                with patch.object(runtime, "MAX_RUNTIME_BYTES", bound):
                    self.sidecars(("selection.json", "artifact-selection", selection))
                full = self.describe("data.csv", data, max_bytes=len(data))
                self.assertEqual([["x", "\u00e9"]], full["preview"]["rows_preview"])
        invalid = self.describe("invalid.txt", b"\xff" + b"a" * 20, max_bytes=5)
        self.assertEqual("latin-1", invalid["preview"]["encoding"])
        for bound in (1, 2, 3):
            with self.subTest(bound=bound):
                partial = self.describe("data.csv", "name,value\nx,1\n".encode("utf-8-sig"), max_bytes=bound)
                self.assertEqual(["\ufeff"] if bound == 3 else [], partial["preview"]["columns"])
                self.select(partial, "column", {"column": "name"})

    def test_gff_and_gtf_use_annotation_coordinates_while_bed_stays_unchanged(self):
        for suffix in ("gff", "gff3", "gtf"):
            with self.subTest(suffix=suffix):
                descriptor = self.describe("data." + suffix, "chr1\tsource\tgene\t11\t21\t.\t+\t.\tID=x\n")
                record = descriptor["preview"]["records_preview"][0]
                self.assertEqual(("chr1", "11", "21"), (record["chrom"], record["start"], record["end"]))
        bed = self.describe("data.bed", "chr1\t10\t21\tgene\n")
        self.assertEqual("10", bed["preview"]["records_preview"][0]["start"])
        malformed = self.describe("bad.gff", "chr1\tsource\tgene\n")
        self.assertNotIn("start", malformed["preview"]["records_preview"][0])

    def test_cytoscape_object_and_grouped_list_counts(self):
        node = {"data": {"id": "a"}}
        edge = {"data": {"source": "a", "target": "a"}}
        for elements in (
            {"nodes": [node], "edges": [edge]},
            [{**node, "group": "nodes"}, {**edge, "group": "edges"}],
        ):
            with self.subTest(elements=elements):
                descriptor = self.describe("data.cyjs", json.dumps({"elements": elements}))
                self.assertEqual((1, 1), (descriptor["preview"]["node_count"], descriptor["preview"]["edge_count"]))
        empty = self.describe("empty.cyjs", '{"elements":[]}')
        self.assertEqual(0, empty["preview"]["node_count"])
        malformed = self.describe("bad.cyjs", '{"elements":[{"group":"unknown"}]}')
        self.assertTrue(malformed["warnings"])
        for elements in ({"unsupported": []}, "unsupported", {"nodes": {}, "edges": []}):
            with self.subTest(elements=elements):
                malformed = self.describe("bad.cyjs", json.dumps({"elements": elements}))
                self.assertTrue(malformed["warnings"])

    def test_pdb_insertion_codes_count_distinct_residues_without_new_fields(self):
        line = "ATOM      1  N   GLY A 145      11.104  13.207   9.101  1.00 20.00           N  \n"
        inserted = line[:26] + "A" + line[27:]
        descriptor = self.describe("data.pdb", line + inserted + inserted)
        self.assertEqual(2, descriptor["preview"]["residues_seen"])
        self.assertEqual("145", descriptor["preview"]["atoms_preview"][1]["resseq"])
        self.assertNotIn("insertion_code", descriptor["preview"]["atoms_preview"][1])

    def test_cli_select_refuses_unresolved_region_without_output(self):
        descriptor = self.describe("data.csv", "a,b\nx,1\n")
        json_descriptor = self.describe("data.json", '{"a":1}')
        contexts = [("unresolved row", descriptor, "row", {"row": 999})]
        mutations = [(descriptor, "bounds", {}, "row", {"row": 1})]
        mutations.extend((json_descriptor, field, 42, "json-pointer", {"pointer": "/a"}) for field in (
            "media_type", "artifact_path", "artifact_sha256", "artifact_kind", "artifact_type", "viewer",
            "generated_at", "evidence_boundary",
        ))
        mutations.append((json_descriptor, "schema_version", True, "json-pointer", {"pointer": "/a"}))
        for original, field, value, kind, selector in mutations:
            malformed = {**original, field: value}
            malformed.pop("fingerprint")
            malformed["fingerprint"] = runtime._fingerprint(malformed)
            if field in {"media_type", "artifact_path"}:
                runtime.validate_runtime_descriptor(malformed)
            contexts.append((field, malformed, kind, selector))
        descriptor_path = self.root / "view.json"
        output = self.root / "selection.json"
        source_bytes = {name: (self.root / name).read_bytes() for name in ("data.csv", "data.json")}
        for label, context, kind, selector in contexts:
            with self.subTest(field=label):
                stored = json.dumps(context).encode()
                descriptor_path.write_bytes(stored)
                result = subprocess.run([
                    sys.executable, "scripts/render_artifact_runtime.py", "select", str(descriptor_path),
                    "--selector-type", kind, "--selector", json.dumps(selector),
                    "--selected-by", "reviewer", "--reason", "Inspect.", "--output", str(output),
                ], capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")))
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                if label != "unresolved row":
                    self.assertIn("selection descriptor", result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(stored, descriptor_path.read_bytes())
                for name, content in source_bytes.items():
                    self.assertEqual(content, (self.root / name).read_bytes())

    def test_creation_refuses_missing_or_wrongly_typed_descriptor_region_facts(self):
        cases = (
            ("data.csv", "a,b\nx,1\n", "row", {"row": 1}, ("bounds", "max_bytes"), (None, "64", False, 0, -1)),
            ("data.csv", "a,b\nx,1\n", "column", {"column": "b"}, ("preview", "columns"), (None, "a,b", {}, [1])),
            ("data.csv", "a,b\nx,1\n", "row", {"row": 1}, ("preview", "rows_preview"), (None, "x,1", {}, ["x"], [[1]])),
            ("data.txt", "one\n", "line", {"line": 1}, ("preview", "line_count_in_prefix"), (None, "1", False, -1)),
            ("data.json", '{"a":1}', "json-pointer", {"pointer": "/a"}, ("preview", "lines_preview"),
             (None, "text", {}, [None], [{}], [{"text": 1}])),
            ("data.bin", b"abc", "byte-range", {"start": 0, "end": 3}, ("size_bytes",), (None, "3", False, -1, [])),
            ("data.csv", "a,b\nx,1\n", "row", {"row": 1}, ("preview", "format"), (None, 42, [], {})),
        )
        for name, content, kind, selector, fields, values in cases:
            descriptor = self.describe(name, content)
            for missing, value in [(True, None), *((False, item) for item in values)]:
                with self.subTest(fields=fields, missing=missing, value=value):
                    malformed = json.loads(json.dumps(descriptor))
                    parent = malformed
                    for field in fields[:-1]:
                        parent = parent[field]
                    if missing:
                        parent.pop(fields[-1])
                    else:
                        parent[fields[-1]] = value
                    malformed.pop("fingerprint")
                    malformed["fingerprint"] = runtime._fingerprint(malformed)
                    with self.assertRaises(ValueError):
                        self.select(malformed, kind, selector)
        for viewer, kinds in runtime.VIEWER_SELECTIONS.items():
            descriptor = self.describe("metadata.json", '{"a":1}')
            descriptor["viewer"] = viewer
            for field in ("artifact_path", "artifact_sha256", "artifact_kind", "artifact_type", "viewer",
                          "generated_at", "evidence_boundary", "media_type", "schema_version", "fingerprint"):
                for kind in kinds:
                    with self.subTest(viewer=viewer, kind=kind, field=field):
                        malformed = {**descriptor, field: 42}
                        if field != "fingerprint":
                            malformed.pop("fingerprint")
                            malformed["fingerprint"] = runtime._fingerprint(malformed)
                        with self.assertRaisesRegex(ValueError, "selection descriptor"):
                            self.select(malformed, kind, {"legacy": True})
        descriptor = self.describe("metadata.json", '{"a":1}')
        for field in ("artifact_path", "artifact_sha256", "artifact_kind", "artifact_type", "viewer",
                      "generated_at", "evidence_boundary", "schema_version", "fingerprint"):
            missing = dict(descriptor)
            missing.pop(field)
            if field != "fingerprint":
                missing.pop("fingerprint")
                missing["fingerprint"] = runtime._fingerprint(missing)
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.select(missing, "json-pointer", {"pointer": "/a"})
            for value in (None, False, [], {}, 1.0, "", 0):
                with self.subTest(field=field, value=value):
                    malformed = {**descriptor, field: value}
                    if field != "fingerprint":
                        malformed.pop("fingerprint")
                        malformed["fingerprint"] = runtime._fingerprint(malformed)
                    with self.assertRaises(ValueError):
                        self.select(malformed, "json-pointer", {"pointer": "/a"})
        for value in (42, False, [], {}):
            malformed = {**descriptor, "media_type": value}
            malformed.pop("fingerprint")
            malformed["fingerprint"] = runtime._fingerprint(malformed)
            with self.subTest(media_type=value), self.assertRaises(ValueError):
                self.select(malformed, "json-pointer", {"pointer": "/a"})
        for value in (42, None, [], {}):
            malformed = json.loads(json.dumps(descriptor))
            malformed["preview"]["json_type"] = value
            malformed.pop("fingerprint")
            malformed["fingerprint"] = runtime._fingerprint(malformed)
            with self.subTest(json_type=value), self.assertRaises(ValueError):
                self.select(malformed, "json-pointer", {"pointer": "/a"})
        for value in (None, "", "application/json"):
            valid = {**descriptor, "media_type": value}
            valid.pop("fingerprint")
            valid["fingerprint"] = runtime._fingerprint(valid)
            self.select(valid, "json-pointer", {"pointer": "/a"})
        for field, value in (("format", ""), ("format", "unknown")):
            table = self.describe("metadata.csv", "a,b\nx,1\n")
            table["preview"][field] = value
            table.pop("fingerprint")
            table["fingerprint"] = runtime._fingerprint(table)
            self.select(table, "row", {"legacy": True})
        for value in ("", "dict"):
            valid = json.loads(json.dumps(descriptor))
            valid["preview"]["json_type"] = value
            valid.pop("fingerprint")
            valid["fingerprint"] = runtime._fingerprint(valid)
            self.select(valid, "json-pointer", {"pointer": "/a"})
        missing_media_type = dict(descriptor)
        missing_media_type.pop("media_type")
        missing_media_type.pop("fingerprint")
        missing_media_type["fingerprint"] = runtime._fingerprint(missing_media_type)
        self.select(missing_media_type, "json-pointer", {"pointer": "/a"})
        for malformed in (None, [], 42, {**descriptor, "extra": object()}):
            with self.subTest(non_json_descriptor=type(malformed).__name__), self.assertRaisesRegex(ValueError, "selection descriptor"):
                self.select(malformed, "json-pointer", {"pointer": "/a"})
        for name, content in (("empty.csv", ""), ("empty.txt", ""), ("empty.bin", b"")):
            descriptor = self.describe(name, content, max_bytes=1)
            kind = next(iter(runtime.VIEWER_SELECTIONS[descriptor["viewer"]]))
            self.select(descriptor, kind, {"legacy": True})

    def test_stored_byte_range_beyond_file_size_validates_without_target_reinspection(self):
        descriptor = self.describe("bytes.bin", b"abc")
        seed = self.select(descriptor, "byte-range", {"start": 0, "end": 3})
        stored = self.resign({**seed, "selector": {"start": 0, "end": 4}}, "selection_id", "selection-")
        self.assert_stored_active(stored)
        with patch.object(runtime, "stream_sha256", side_effect=AssertionError("unexpected selection target hash")), \
             patch.object(runtime, "_table_preview", side_effect=AssertionError("unexpected selection target parse")), \
             patch.object(runtime, "_text_preview", side_effect=AssertionError("unexpected selection target parse")):
            result = self.sidecars(("selection.json", "artifact-selection", stored))
        self.assertEqual("active", result["artifact_selections"][0]["status"])
        self.assertEqual(stored, result["artifact_selections"][0])
        with self.assertRaises(ValueError):
            self.select(descriptor, "byte-range", stored["selector"])

    def test_stored_table_and_text_selections_do_not_reinspect_targets(self):
        for name, content, kind, selector in (
            ("data.csv", "a,b\nx,1\n", "column", {"column": "b"}),
            ("data.txt", "one\n", "line", {"line": 1}),
        ):
            with self.subTest(name=name):
                descriptor = self.describe(name, content)
                selection = self.select(descriptor, kind, selector)
                with patch.object(runtime, "stream_sha256", side_effect=AssertionError("unexpected selection target hash")), \
                     patch.object(runtime, "_table_preview", side_effect=AssertionError("unexpected selection target parse")), \
                     patch.object(runtime, "_text_preview", side_effect=AssertionError("unexpected selection target parse")), \
                     patch.object(runtime, "_validate_selection_region", side_effect=AssertionError("unexpected region check")):
                    self.assert_stored_active(selection)
