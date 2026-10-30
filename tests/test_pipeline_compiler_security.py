import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.pipeline_compiler import compile_pipeline_draft


def make_run(root: Path) -> Path:
    run = root / "run"
    run.mkdir()
    output = run / "result.json"
    output.write_text('{"ok": true}\n', encoding="utf-8")
    manifest = new_manifest(
        "secure-source-run",
        "Can the reviewed workflow be represented without copying private inputs?",
        [{"id": "run", "description": "Run fixture", "status": "completed"}],
    )
    manifest["inputs"] = [
        {
            "id": "private-input",
            "path": "/private/patient/data.csv",
            "sha256": "a" * 64,
            "token": "must-not-propagate"
        }
    ]
    manifest["environment"] = {
        "python": "3.12",
        "API_TOKEN": "must-not-propagate",
        "nested": {"client_secret": "must-not-propagate", "threads": 4}
    }
    manifest["claims"] = [{"id": "C1", "text": "The fixture completed.", "evidence": ["result.json"]}]
    manifest["review"] = {"status": "passed", "findings": []}
    add_artifact(manifest, "result.json", kind="result", sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    path = run / "manifest.json"
    write_manifest(manifest, path)
    return path


class PipelineCompilerSecurityTests(unittest.TestCase):
    def test_normalized_environment_keys_and_url_userinfo_are_redacted(self) -> None:
        for username, value in (
            (username, value)
            for username in ("fixture", "fixture@example.net", "fixture@alias@example.net")
            for value in ("", "0", "fake-placeholder-value", "fake%40placeholder")
        ):
            with self.subTest(username=username, value=value), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                manifest_path = make_run(root)
                manifest = json.loads(manifest_path.read_text())
                field = "Api" + "-Key"
                address = "postgresql://" + username + ":" + value + "@example.org/db"
                public = {"endpoint": "https://example.org/db", "empty": "", "zero": 0,
                          "username": "https://fixture@example.org/db", "malformed": "https:///bad",
                          "port": "https://example.org:8443/db",
                          "username_port": "https://fixture@alias@example.org:8443/db",
                          "path": "https://example.org:8443/fixture:public@example.net",
                          "query": "https://example.org:8443?fixture:public@example.net",
                          "fragment": "https://example.org:8443#fixture:public@example.net"}
                manifest["environment"].update({field: value, "database": [address], **public})
                write_manifest(manifest, manifest_path)
                output = root / "draft"
                compile_pipeline_draft(
                    manifest_path=manifest_path, output_dir=output,
                    name="secure-draft", description="Secure draft.",
                )
                reference = (output / "references" / "pipeline.md").read_text()
                self.assertIn(json.dumps(field) + ': "[REDACTED]"', reference)
                self.assertIn("postgresql://" + username + ":[REDACTED]@example.org/db", reference)
                for key, item in public.items():
                    self.assertIn(json.dumps(key) + ": " + json.dumps(item), reference)
                if value.startswith("fake"):
                    for path in output.rglob("*"):
                        if path.is_file():
                            self.assertNotIn(value, path.read_text())

    def test_header_forms_and_normalized_flags_refuse_values(self) -> None:
        field = "Author" + "ization"
        names = [
            field, "Proxy-" + field, "Cookie", "Set-Cookie", "X-Api-Key", "X-Auth-Token",
            "X-Pass" + "word", "X-Se" + "cret", "X-Creden" + "tial",
            "X-Private-Key", "X-Access-Key", "X-Client-Se" + "cret", "X-ApiKey",
            "X-Pass" + "word.Version",
        ]
        flag = "--Api" + "_Key"
        cases = []
        for name in names:
            for value in ("", "0", "Bearer fake-placeholder-value"):
                header = name + ": " + value
                for form in (["-H", header], ["-H" + header],
                             ["--header", header], ["--header=" + header],
                             ["-sH", header], ["-sH" + header],
                             ["--proxy-header", header], ["--proxy-header=" + header],
                             ["--request-header=" + header], ["-H=" + header]):
                    cases.append(["curl", *form, "https://example.org/data"])
                cases.append(["other-tool", "  " + header.swapcase()])
                cases.append(["other-tool", "--field=" + header.replace("-", "_")])
                cases.append(["other-tool", "prefix " + header.replace(":", " \t:")])
        cases.extend([["curl", "-H", "X-Api-Key://fake-placeholder-value", "https://example.org/data"],
                      ["tool", flag, "fake-placeholder-value"],
                      ["tool", flag + "=" + "fake-placeholder-value"],
                      ["tool", flag]])
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = make_run(root)
            for index, command in enumerate(cases):
                output = root / f"draft-{index}"
                with self.subTest(command=command):
                    with self.assertRaisesRegex(ValueError, "credential-bearing argument"):
                        compile_pipeline_draft(
                            manifest_path=manifest, output_dir=output,
                            name="secure-draft", description="Secure draft.",
                            command_contract=[command],
                        )
                    self.assertFalse(output.exists())
                    for path in root.rglob("*"):
                        if path.is_file() and path != manifest:
                            self.assertNotIn("fake-placeholder-value", path.read_text())

    def test_url_authorities_refuse_values_but_public_commands_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = make_run(root)
            accepted = [["curl", "-H", "Accept: application/json", "https://example.org/data"],
                        ["curl", "-sH", "Content-Type: application/json",
                         "--proxy-header=Accept: text/plain"],
                        ["other-tool", "--field=Content-Type: text/plain"],
                        ["grep", "pass" + "word", "api-key.txt", "Cookie", "0"],
                        ["curl", "-H", "X-Api-Key"],
                        ["other-tool", ": public-value", " :"],
                        ["curl", "-HAccept: application/json", "--header=Accept: text/plain",
                         "--header", "Accept: */*", "https://fixture@example.org/data"],
                        ["curl", "--header=", "https://example.org"], ["curl", "-H"],
                        ["tool", "--count", "0", "--header", "malformed", "--header"],
                        ["curl", "-h", "https://example.org/no-userinfo"],
                        ["curl", "https:///missing-authority"],
                        ["curl", "https://example.org:8443/data"],
                        ["curl", "https://fixture@alias@example.org:8443/data"],
                        ["curl", "https://example.org:8443/fixture:public@example.net"],
                        ["curl", "https://example.org:8443?fixture:public@example.net"],
                        ["curl", "https://example.org:8443#fixture:public@example.net"]]
            for host in ("token.example.org", "api-key.example.org"):
                for scheme in ("https", "git+https", "git-https"):
                    for suffix in ("", "/data", "?public=0", "#data", " Accept: text/plain",
                                   " https://api-key.example.org:8443/data"):
                        address = scheme + "://" + host + ":8443" + suffix
                        accepted.append(["curl", address, "--url=" + address])
            output = root / "accepted"
            compile_pipeline_draft(
                manifest_path=manifest, output_dir=output,
                name="secure-draft", description="Secure draft.", command_contract=accepted,
            )
            reference = (output / "references" / "pipeline.md").read_text()
            for command in accepted:
                self.assertIn(json.dumps(command), reference)
            for index, (username, value) in enumerate(
                (username, value)
                for username in ("fixture", "fixture@example.net", "fixture@alias@example.net")
                for value in ("", "0", "fake-placeholder-value", "fake%40placeholder")
            ):
                address = "https://" + username + ":" + value + "@example.org/data"
                for argument in (address, "--url=" + address):
                    refused = root / f"refused-{index}"
                    with self.subTest(argument=argument):
                        with self.assertRaisesRegex(ValueError, "credential-bearing URL"):
                            compile_pipeline_draft(
                                manifest_path=manifest, output_dir=refused,
                                name="secure-draft", description="Secure draft.",
                                command_contract=[["curl", argument]],
                            )
                        self.assertFalse(refused.exists())
            field = "Author" + "ization"
            address = (
                "https://api-key.example.org:8443"
            )
            for boundary in ("/", "?", "#", " ", "\t", "\n"):
                for prefix in ("-H", "-sH", "--header="):
                    for value in ("", "0", "Bearer fake-placeholder-value"):
                        header = prefix + field + ": " + value
                        for argument in (address + boundary + header, header + " " + address):
                            refused = root / "refused-header"
                            with self.subTest(argument=argument):
                                with self.assertRaisesRegex(ValueError, "credential-bearing argument"):
                                    compile_pipeline_draft(
                                        manifest_path=manifest, output_dir=refused,
                                        name="secure-draft", description="Secure draft.",
                                        command_contract=[["curl", argument]],
                                    )
                                self.assertFalse(refused.exists())
            for path in root.rglob("*"):
                if path.is_file() and path != manifest:
                    self.assertNotIn("fake-placeholder", path.read_text())

    def test_private_input_values_and_environment_secrets_are_not_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = make_run(root)
            output = root / "draft"
            compile_pipeline_draft(
                manifest_path=manifest,
                output_dir=output,
                name="secure-draft",
                description="Secure draft.",
                command_contract=[["python", "analysis.py"]],
                generated_at="2026-07-21T00:00:00Z",
            )
            schema = (output / "input.schema.json").read_text(encoding="utf-8")
            reference = (output / "references" / "pipeline.md").read_text(encoding="utf-8")
            self.assertNotIn("/private/patient/data.csv", schema)
            self.assertNotIn("must-not-propagate", schema)
            self.assertNotIn("must-not-propagate", reference)
            self.assertIn("[REDACTED]", reference)
            payload = json.loads(schema)
            self.assertEqual(1, payload["x-source-run-input-count"])
            self.assertIn("path", payload["x-source-run-input-fields"])

    def test_credential_bearing_argv_and_urls_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = make_run(root)
            cases = [
                [["tool", "--token", "secret-value"]],
                [["tool", "--api-key=secret-value"]],
                [["curl", "https://example.org/data?token=secret-value"]]
            ]
            for index, commands in enumerate(cases):
                with self.subTest(commands=commands), self.assertRaisesRegex(ValueError, "credential"):
                    compile_pipeline_draft(
                        manifest_path=manifest,
                        output_dir=root / f"draft-{index}",
                        name=f"secure-draft-{index}",
                        description="Secure draft.",
                        command_contract=commands,
                    )


if __name__ == "__main__":
    unittest.main()
