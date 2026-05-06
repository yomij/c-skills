import json
import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path
from typing import Union
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "generate_image.py"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
DEFAULT_HOST_ROOT = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
DEFAULT_CONFIG_PATH = DEFAULT_HOST_ROOT / "generate-image" / "config.json"
DEFAULT_CONFIG_TEMPLATE = (
    "$GENERATE_IMAGE_CONFIG or $GENERATE_IMAGE_HOME/config.json "
    "or <host-root>/generate-image/config.json"
)
SKILL_ROOT_TEMPLATE = "<host-root>/skills/generate-image"
SCRIPT_PATH_TEMPLATE = "<installed-skill-root>/scripts/generate_image.py"
GENERATE_IMAGE_ENV_KEYS = ("GENERATE_IMAGE_CONFIG", "GENERATE_IMAGE_HOME")


class GenerateImageScriptTests(unittest.TestCase):
    def run_command(
        self,
        args,
        *,
        cwd: Union[str, Path],
        env=None,
        check: bool = True,
    ):
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            cwd=cwd,
            capture_output=True,
            env=self.isolated_script_env(env),
            text=True,
            check=check,
        )

    def isolated_script_env(self, env=None):
        process_env = dict(os.environ)
        for key in (
            "API_KEY",
            "api_key",
            "BASE_URL",
            "base_url",
            "MODEL",
            "model",
            *GENERATE_IMAGE_ENV_KEYS,
        ):
            process_env.pop(key, None)
        if env:
            process_env.update(env)
        return process_env

    def run_dry_run(self) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(
                [
                    "--prompt",
                    "test prompt",
                    "--api-key",
                    "dummy",
                    "--config",
                    str(Path(tmpdir) / "missing-config.json"),
                    "--dry-run",
                ],
                cwd=tmpdir,
            )
        return json.loads(result.stdout)

    def load_script_module(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in GENERATE_IMAGE_ENV_KEYS:
                os.environ.pop(key, None)

            spec = importlib.util.spec_from_file_location("generate_image", SCRIPT_PATH)
            assert spec is not None
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
        return module

    def test_default_responses_model_is_mainline_model(self) -> None:
        payload = self.run_dry_run()
        self.assertEqual(payload["mode"], "generate")
        self.assertEqual(payload["response_model"], "gpt-5.5")
        self.assertEqual(payload["image_model"], "gpt-image-2")
        self.assertEqual(payload["request_body"]["model"], "gpt-5.5")
        self.assertEqual(payload["request_body"]["tools"][0]["model"], "gpt-image-2")

    def test_request_body_matches_a_py_without_forced_tool_choice(self) -> None:
        payload = self.run_dry_run()
        self.assertEqual(payload["request_body"]["input"], "test prompt")
        self.assertEqual(
            payload["request_body"]["tools"],
            [{"type": "image_generation", "model": "gpt-image-2", "output_format": "png"}],
        )
        self.assertTrue(payload["request_body"]["stream"])
        self.assertNotIn("tool_choice", payload["request_body"])

    def test_default_config_path_uses_generate_image_overrides_or_host_root(self) -> None:
        module = self.load_script_module()
        self.assertEqual(module.DEFAULT_CONFIG_PATH_TEMPLATE, DEFAULT_CONFIG_TEMPLATE)
        self.assertEqual(module.DEFAULT_CONFIG_PATH, str(DEFAULT_CONFIG_PATH))

    def test_run_command_isolates_generate_image_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            external_config = str(Path(tmpdir) / "external-config.json")
            external_home = str(Path(tmpdir) / "external-home")
            with mock.patch.dict(
                os.environ,
                {"GENERATE_IMAGE_CONFIG": external_config, "GENERATE_IMAGE_HOME": external_home},
            ):
                result = self.run_command(
                    ["--prompt", "test prompt", "--api-key", "dummy", "--dry-run"],
                    cwd=tmpdir,
                )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["config"], str(DEFAULT_CONFIG_PATH.resolve()))

    def test_load_script_module_isolates_generate_image_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            external_config = str(Path(tmpdir) / "external-config.json")
            external_home = str(Path(tmpdir) / "external-home")
            with mock.patch.dict(
                os.environ,
                {"GENERATE_IMAGE_CONFIG": external_config, "GENERATE_IMAGE_HOME": external_home},
            ):
                module = self.load_script_module()

        self.assertEqual(module.DEFAULT_CONFIG_PATH, str(DEFAULT_CONFIG_PATH))

    def test_default_config_honors_codex_home_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            codex_home = Path(tmpdir) / "codex-home"
            codex_home.mkdir()
            result = self.run_command(
                [
                    "--prompt",
                    "test prompt",
                    "--api-key",
                    "dummy",
                    "--dry-run",
                ],
                cwd=tmpdir,
                env={"CODEX_HOME": str(codex_home)},
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["config"], str((codex_home / "generate-image" / "config.json").resolve()))

    def test_default_config_path_mentions_generate_image_home_override(self) -> None:
        module = self.load_script_module()
        self.assertIn("GENERATE_IMAGE_HOME", module.DEFAULT_CONFIG_PATH_TEMPLATE)

    def test_generate_image_config_environment_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config = Path(tmpdir) / "custom-config.json"
            result = self.run_command(
                [
                    "--prompt",
                    "test prompt",
                    "--api-key",
                    "dummy",
                    "--dry-run",
                ],
                cwd=tmpdir,
                env={"GENERATE_IMAGE_CONFIG": str(custom_config)},
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["config"], str(custom_config.resolve()))

    def test_generate_image_home_environment_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_home = Path(tmpdir) / "generate-image-home"
            result = self.run_command(
                [
                    "--prompt",
                    "test prompt",
                    "--api-key",
                    "dummy",
                    "--dry-run",
                ],
                cwd=tmpdir,
                env={"GENERATE_IMAGE_HOME": str(custom_home)},
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["config"], str((custom_home / "config.json").resolve()))

    def test_default_config_honors_claude_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_root = Path(tmpdir) / ".claude"
            skill_root = claude_root / "skills" / "generate-image"
            scripts_dir = skill_root / "scripts"
            scripts_dir.mkdir(parents=True)
            script_copy = scripts_dir / "generate_image.py"
            script_copy.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(script_copy),
                    "--prompt",
                    "test prompt",
                    "--api-key",
                    "dummy",
                    "--dry-run",
                ],
                cwd=tmpdir,
                capture_output=True,
                env=self.isolated_script_env(),
                text=True,
                check=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["config"], str((claude_root / "generate-image" / "config.json").resolve()))

    def test_tests_resolve_paths_relative_to_this_file(self) -> None:
        content = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn(str(SKILL_ROOT), content)

    def test_skill_directory_has_no_provider_brand_wording(self) -> None:
        forbidden = ("Open" + "AI", "open" + "ai", "OPEN" + "AI")
        forbidden_phrases = ("Responses" + " API",)
        for path in SKILL_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".md", ".py", ".yaml", ".json"}:
                continue
            content = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, content, msg=f"{token} found in {path}")
            for phrase in forbidden_phrases:
                self.assertNotIn(phrase, content, msg=f"{phrase} found in {path}")

    def test_response_format_matches_script_json_output(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertNotIn("optimized_prompt=", content)
        self.assertIn("revised_prompt", content)

    def test_default_config_is_not_read_from_current_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            Path(workspace_dir, "config.json").write_text(
                json.dumps({"api_key": "from-workspace-config"}),
                encoding="utf-8",
            )

            result = self.run_command(
                ["--prompt", "test prompt", "--api-key", "dummy", "--dry-run"],
                cwd=workspace_dir,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["config"], str(DEFAULT_CONFIG_PATH.resolve()))
        self.assertNotEqual(payload["config"], str((workspace_dir / "config.json").resolve()))

    def test_config_json_values_drive_dry_run_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "api_key": "from-config",
                        "base_url": "https://example.test/v1/",
                        "response_model": "configured-response-model",
                        "image_model": "configured-image-model",
                        "output_dir": "images",
                        "quality": "high",
                        "background": "opaque",
                        "output_format": "webp",
                        "output_compression": 55,
                        "partial_images": 2,
                        "tool_choice": "image_generation",
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_command(
                [
                    "--prompt",
                    "poster concept",
                    "--config",
                    str(config_path),
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["endpoint"], "https://example.test/v1/responses")
        self.assertEqual(payload["response_model"], "configured-response-model")
        self.assertEqual(payload["image_model"], "configured-image-model")
        self.assertEqual(payload["output_dir"], str((Path(tmpdir) / "images").resolve()))
        self.assertTrue(payload["request_body"]["stream"])
        self.assertEqual(payload["request_body"]["tool_choice"], {"type": "image_generation"})
        self.assertNotIn("size", payload["request_body"]["tools"][0])
        self.assertEqual(payload["request_body"]["tools"][0]["quality"], "high")
        self.assertEqual(payload["request_body"]["tools"][0]["background"], "opaque")
        self.assertEqual(payload["request_body"]["tools"][0]["output_format"], "webp")
        self.assertEqual(payload["request_body"]["tools"][0]["output_compression"], 55)
        self.assertEqual(payload["request_body"]["tools"][0]["partial_images"], 2)

    def test_legacy_model_config_key_maps_to_image_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "api_key": "from-config",
                        "model": "legacy-image-model",
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_command(
                [
                    "--prompt",
                    "poster concept",
                    "--config",
                    str(config_path),
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["image_model"], "legacy-image-model")
        self.assertEqual(payload["request_body"]["tools"][0]["model"], "legacy-image-model")

    def test_config_size_is_ignored_because_size_is_per_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "api_key": "from-config",
                        "size": "1024x1024",
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_command(
                [
                    "--prompt",
                    "poster concept",
                    "--config",
                    str(config_path),
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        self.assertNotIn("size", payload["request_body"]["tools"][0])
        self.assertIn("Ignoring unknown config.json field(s): size", result.stderr)

    def test_cli_size_is_passed_for_the_current_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(
                [
                    "--prompt",
                    "wide website hero",
                    "--api-key",
                    "dummy",
                    "--size",
                    "1536x1024",
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["request_body"]["tools"][0]["size"], "1536x1024")

    def test_edit_mode_dry_run_uses_images_edits_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.png"
            mask = Path(tmpdir) / "mask.png"
            source.write_bytes(b"source")
            mask.write_bytes(b"mask")
            result = self.run_command(
                [
                    "--prompt",
                    "make it brighter",
                    "--api-key",
                    "dummy",
                    "--image",
                    "source.png",
                    "--mask",
                    str(mask),
                    "--size",
                    "1024x1024",
                    "--quality",
                    "high",
                    "--output-format",
                    "webp",
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "edit")
        self.assertEqual(payload["endpoint"], "https://api.xairouter.com/v1/images/edits")
        self.assertEqual(payload["image_model"], "gpt-image-2")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["image_inputs"], [str(source.resolve())])
        self.assertEqual(payload["mask"], str(mask.resolve()))
        self.assertNotIn("request_body", payload)
        self.assertEqual(
            payload["multipart"]["fields"],
            {
                "model": "gpt-image-2",
                "prompt": "make it brighter",
                "response_format": "b64_json",
                "output_format": "webp",
                "size": "1024x1024",
                "quality": "high",
            },
        )
        self.assertEqual(payload["multipart"]["files"][0]["field"], "image")
        self.assertEqual(payload["multipart"]["files"][0]["content_type"], "image/png")
        self.assertEqual(payload["multipart"]["files"][1]["field"], "mask")

    def test_edit_mode_multiple_images_use_reference_array_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first.png"
            second = Path(tmpdir) / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            result = self.run_command(
                [
                    "--prompt",
                    "combine references",
                    "--api-key",
                    "dummy",
                    "--image",
                    str(first),
                    "--image",
                    str(second),
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        files = payload["multipart"]["files"]
        self.assertEqual([file_part["field"] for file_part in files], ["image[]", "image[]"])
        self.assertEqual([file_part["path"] for file_part in files], [str(first.resolve()), str(second.resolve())])
        self.assertEqual(files[1]["content_type"], "image/jpeg")

    def test_multipart_encoder_includes_edit_fields_and_file_bytes(self) -> None:
        module = self.load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.png"
            source.write_bytes(b"source-bytes")
            files = [module.build_multipart_file("image", source)]
            body, content_type = module.encode_multipart_form_data(
                {
                    "model": "gpt-image-2",
                    "prompt": "make it brighter",
                },
                files,
            )

        self.assertIn("multipart/form-data; boundary=----generate-image-", content_type)
        self.assertIn(b'name="model"\r\n\r\ngpt-image-2', body)
        self.assertIn(b'name="prompt"\r\n\r\nmake it brighter', body)
        self.assertIn(b'name="image"; filename="source.png"', body)
        self.assertIn(b"Content-Type: image/png", body)
        self.assertIn(b"source-bytes", body)

    def test_mask_requires_image_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(
                [
                    "--prompt",
                    "edit masked area",
                    "--api-key",
                    "dummy",
                    "--mask",
                    "mask.png",
                    "--dry-run",
                ],
                cwd=tmpdir,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--mask requires at least one --image", result.stderr)

    def test_partial_images_are_not_supported_in_edit_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(
                [
                    "--prompt",
                    "edit this image",
                    "--api-key",
                    "dummy",
                    "--image",
                    "source.png",
                    "--partial-images",
                    "2",
                    "--dry-run",
                ],
                cwd=tmpdir,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--partial-images is only supported for text generation mode", result.stderr)

    def test_images_edit_response_extracts_b64_and_saves_requested_format(self) -> None:
        module = self.load_script_module()
        image = module.extract_images_api_result(
            {
                "data": [
                    {
                        "b64_json": "aGVsbG8=",
                        "revised_prompt": "brighter result",
                    }
                ]
            }
        )

        self.assertEqual(image["image_base64"], "aGVsbG8=")
        self.assertEqual(image["revised_prompt"], "brighter result")
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_to = module.save_image(
                image["image_base64"],
                "generated",
                "gpt-image-2",
                output_format="jpeg",
                base_dir=Path(tmpdir),
            )
            saved_bytes = saved_to.read_bytes()

        self.assertEqual(saved_to.suffix, ".jpeg")
        self.assertEqual(saved_bytes, b"hello")

    def test_tool_choice_can_force_image_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(
                [
                    "--prompt",
                    "draw a launch poster",
                    "--api-key",
                    "dummy",
                    "--tool-choice",
                    "image_generation",
                    "--dry-run",
                ],
                cwd=tmpdir,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["request_body"]["tool_choice"], {"type": "image_generation"})

    def test_partial_images_require_streaming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(
                [
                    "--prompt",
                    "draw a launch poster",
                    "--api-key",
                    "dummy",
                    "--partial-images",
                    "2",
                    "--no-stream",
                ],
                cwd=tmpdir,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("partial_images requires streaming", result.stderr)

    def test_dotenv_and_environment_are_not_used_for_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, ".env").write_text("API_KEY=from-dotenv\n", encoding="utf-8")
            result = self.run_command(
                [
                    "--prompt",
                    "test prompt",
                    "--config",
                    str(Path(tmpdir) / "missing-config.json"),
                    "--dry-run",
                ],
                cwd=tmpdir,
                env={"API_KEY": "from-environment"},
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Configure api_key in config.json", result.stderr)

    def test_env_file_argument_is_not_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_command(["--help"], cwd=tmpdir)

        self.assertNotIn("--env-file", result.stdout)
        self.assertIn("GENERATE_IMAGE_CONFIG", result.stdout)
        self.assertIn("GENERATE_IMAGE_HOME/config.json", result.stdout)
        self.assertIn("generate-image/config.json", result.stdout)
        self.assertIn("--response-model", result.stdout)
        self.assertIn("--image-model", result.stdout)
        self.assertIn("--image", result.stdout)
        self.assertIn("--mask", result.stdout)
        self.assertIn("--tool-choice", result.stdout)
        self.assertIn("--partial-images", result.stdout)
        self.assertIn("--no-stream", result.stdout)

    def test_skill_instructions_make_config_location_explicit(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("GENERATE_IMAGE_CONFIG", content)
        self.assertIn("GENERATE_IMAGE_HOME", content)
        self.assertIn("<host-root>/generate-image/config.json", content)
        self.assertNotIn("../../generate-image/config.json", content)
        self.assertNotIn("/Users/yomi/.codex/generate-image/config.json", content)
        self.assertNotIn("~/.codex/generate-image/config.json", content)

    def test_skill_instructions_use_host_aware_skill_paths(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn(SKILL_ROOT_TEMPLATE, content)
        self.assertIn(SCRIPT_PATH_TEMPLATE, content)
        self.assertIn("$HOME/.claude/skills/generate-image", content)

    def test_skill_instructions_make_size_per_request(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("Do not store `size` in `config.json`", content)
        self.assertIn("choose it per request", content)
        self.assertNotIn('"size":', content)

    def test_skill_instructions_warn_that_image_generation_can_take_longer(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("Image generation can take a while", content)
        self.assertIn("do not kill the process too early", content)

    def test_skill_instructions_cover_streaming_tool_model_and_text_rendering(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("gpt-5.5", content)
        self.assertIn("gpt-image-2", content)
        self.assertIn("stream", content)
        self.assertIn("partial_images", content)
        self.assertIn("tool_choice", content)
        self.assertIn("transparent background", content)
        self.assertIn("let the image model render it directly in the image by default", content)
        self.assertNotIn("render text outside the generated image", content)

    def test_skill_instructions_cover_art_direction_prompting(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("Prompt Engineering Directives", content)
        self.assertIn("Prompt Blueprint", content)
        self.assertIn("Visualize Abstract Intent", content)
        self.assertIn("Medium and Camera Cohesion", content)
        self.assertIn("Multi-Subject Spatial Control", content)
        self.assertIn("Negative Constraints", content)
        self.assertIn("extra digits, bad hands", content)
        self.assertIn("--negative-prompt", content)

    def test_skill_instructions_absorb_imagegen_asset_workflow(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("Asset Workflow Discipline", content)
        self.assertIn("project-bound", content)
        self.assertIn("final saved path", content)
        self.assertIn("Prompt Spec Scaffold", content)
        self.assertIn("Use case:", content)
        self.assertIn("Asset type:", content)
        self.assertIn("chroma-key", content)
        self.assertIn("remove_chroma_key.py", content)

    def test_stream_parser_collects_partial_and_final_images(self) -> None:
        module = self.load_script_module()
        events = list(
            module.iter_sse_events(
                [
                    b"event: response.image_generation_call.partial_image\n",
                    b'data: {"type":"response.image_generation_call.partial_image","partial_image_index":0,"partial_image_b64":"cDE="}\n',
                    b"\n",
                    b"event: response.output_item.done\n",
                    b'data: {"type":"response.output_item.done","item":{"type":"image_generation_call","id":"img_123","result":"ZmluYWw=","revised_prompt":"refined prompt","action":"generate"}}\n',
                    b"\n",
                    b"data: [DONE]\n",
                    b"\n",
                ]
            )
        )

        self.assertEqual(events[0]["event"], "response.image_generation_call.partial_image")
        self.assertEqual(events[0]["data"]["partial_image_index"], 0)
        self.assertEqual(events[1]["event"], "response.output_item.done")

        parsed = module.extract_stream_image_result(events)
        self.assertEqual(parsed["image_base64"], "ZmluYWw=")
        self.assertEqual(parsed["image_call_id"], "img_123")
        self.assertEqual(parsed["revised_prompt"], "refined prompt")
        self.assertEqual(parsed["action"], "generate")
        self.assertEqual(parsed["partial_images"][0]["image_base64"], "cDE=")
        self.assertEqual(parsed["partial_images"][0]["index"], 0)

    def test_save_image_returns_absolute_path(self) -> None:
        module = self.load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_to = module.save_image(
                "aGVsbG8=",
                "generated",
                "gpt-image-2",
                output_format="png",
                base_dir=Path(tmpdir),
            )
            saved_bytes = saved_to.read_bytes()

        self.assertTrue(saved_to.is_absolute())
        self.assertTrue(saved_to.name.startswith("gpt-image-2-"))
        self.assertEqual(saved_bytes, b"hello")

    def test_save_image_uses_requested_output_format_extension(self) -> None:
        module = self.load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_to = module.save_image(
                "aGVsbG8=",
                "generated",
                "gpt-image-2",
                output_format="webp",
                base_dir=Path(tmpdir),
            )

        self.assertEqual(saved_to.suffix, ".webp")


if __name__ == "__main__":
    unittest.main()
