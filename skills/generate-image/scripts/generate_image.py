#!/usr/bin/env python3
"""Generate an image with a responses endpoint and image_generation tool."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.xairouter.com/v1"
DEFAULT_RESPONSE_MODEL = "gpt-5.5"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_OUTPUT_DIR = "data/generated"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_STREAM = True
DEFAULT_TIMEOUT_SECONDS = 600
UNSUPPORTED_PREVIOUS_RESPONSE_ID_MESSAGE = (
    "previous_response_id is not supported by this image-generation API path. "
    "Generate a new text-only variant, or switch to an existing-image editing workflow "
    "when exact image continuation is required."
)
SKILL_ROOT = Path(__file__).resolve().parents[1]


def infer_host_root(skill_root: Path = SKILL_ROOT) -> Path:
    skills_dir = skill_root.parent
    if skills_dir.name == "skills":
        inferred_root = skills_dir.parent.expanduser().resolve()
        if inferred_root.name in {".codex", ".claude"}:
            return inferred_root

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser().resolve()

    return (Path.home() / ".codex").resolve()


def resolve_default_config_path(skill_root: Path = SKILL_ROOT) -> Path:
    config_override = os.environ.get("GENERATE_IMAGE_CONFIG")
    if config_override:
        return Path(config_override).expanduser().resolve()

    home_override = os.environ.get("GENERATE_IMAGE_HOME")
    if home_override:
        return (Path(home_override).expanduser() / "config.json").resolve()

    return (infer_host_root(skill_root) / "generate-image" / "config.json").resolve()


DEFAULT_HOST_ROOT = infer_host_root()
DEFAULT_SKILL_ROOT_TEMPLATE = "<host-root>/skills/generate-image"
DEFAULT_CONFIG_PATH_TEMPLATE = (
    "$GENERATE_IMAGE_CONFIG or $GENERATE_IMAGE_HOME/config.json "
    "or <host-root>/generate-image/config.json"
)
DEFAULT_CONFIG_PATH = str(resolve_default_config_path())
CONFIG_KEYS = {
    "api_key",
    "base_url",
    "response_model",
    "image_model",
    "model",
    "output_dir",
    "quality",
    "background",
    "output_format",
    "output_compression",
    "partial_images",
    "tool_choice",
    "stream",
    "timeout_seconds",
}


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser()

    try:
        config = load_config_file(config_path)
        warn_if_config_file_is_too_open(config_path)

        prompt = read_prompt(args)
        if not prompt:
            print_error("Prompt is empty. Pass --prompt or --prompt-file.")
            return 2
        if args.previous_response_id:
            print_error(UNSUPPORTED_PREVIOUS_RESPONSE_ID_MESSAGE)
            return 2

        api_key = config_value(args, config, "api_key", "")
        if not api_key:
            print_error(
                "Provider API key is empty. Configure api_key in config.json "
                f"(default resolution: {DEFAULT_CONFIG_PATH_TEMPLATE} -> {DEFAULT_CONFIG_PATH}), "
                "or pass --api-key."
            )
            return 2

        base_url = config_value(args, config, "base_url", DEFAULT_BASE_URL).rstrip("/")
        response_model = config_value(args, config, "response_model", DEFAULT_RESPONSE_MODEL)
        image_model = config_value(
            args,
            config,
            "image_model",
            DEFAULT_IMAGE_MODEL,
            config_aliases=("image_model", "model"),
        )
        output_dir = config_value(args, config, "output_dir", DEFAULT_OUTPUT_DIR)
        output_format = config_value(args, config, "output_format", DEFAULT_OUTPUT_FORMAT)
        stream = config_bool_value(args, config, "stream", DEFAULT_STREAM)
        timeout_seconds = config_int_value(args, config, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        body = build_request_body(
            args,
            config,
            response_model=response_model,
            image_model=image_model,
            prompt=prompt,
            stream=stream,
        )

        if args.dry_run:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "config": str(config_path.resolve()),
                        "base_url": base_url,
                        "endpoint": f"{base_url}/responses",
                        "response_model": response_model,
                        "image_model": image_model,
                        "stream": stream,
                        "output_dir": str(resolve_output_dir(output_dir)),
                        "request_body": body,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        partial_saved_to: list[str] = []

        def on_partial_image(partial: dict[str, Any]) -> None:
            partial_saved_to.append(
                save_partial_image_with_progress(
                    partial,
                    output_dir,
                    image_model,
                    output_format=output_format,
                )
            )

        response_payload = post_responses_api(
            base_url,
            api_key,
            body,
            timeout_seconds=timeout_seconds,
            on_partial_image=on_partial_image if stream else None,
            capture_stream_events=args.raw_json,
        )
        response_json = response_payload.get("response_json")
        image = response_payload.get("image")
        if image is None:
            print_error("No image payload found in the response.", {"response": response_json})
            return 1

        saved_to = save_image(
            image["image_base64"],
            output_dir,
            image_model,
            output_format=output_format,
        )
        if not partial_saved_to:
            for partial in image.get("partial_images", []):
                partial_index = partial.get("index")
                partial_saved_to.append(
                    str(
                        save_image(
                            partial["image_base64"],
                            output_dir,
                            image_model,
                            output_format=output_format,
                            stem_suffix=f"partial-{partial_index}",
                        )
                    )
                )
        output = {
            "saved_to": str(saved_to),
            "markdown": f"![Generated image]({saved_to})",
            "response_id": image.get("response_id") or (response_json or {}).get("id"),
            "image_call_id": image.get("image_call_id"),
            "revised_prompt": image.get("revised_prompt"),
            "action": image.get("action"),
            "response_model": response_model,
            "image_model": image_model,
            "stream": stream,
        }
        if partial_saved_to:
            output["partial_saved_to"] = partial_saved_to
        if args.raw_json:
            output["raw_response"] = response_json
            if response_payload.get("stream_events"):
                output["raw_stream_events"] = response_payload["stream_events"]

        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (HTTPError, URLError) as exc:
        print_error(format_url_error(exc))
        return 1
    except Exception as exc:
        print_error(str(exc))
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an image from a text prompt.")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Text prompt to generate from.")
    prompt_group.add_argument("--prompt-file", help="File containing the prompt.")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=(
            "Path to config.json. "
            f"Default resolves from {DEFAULT_CONFIG_PATH_TEMPLATE}."
        ),
    )
    parser.add_argument("--api-key", help="Provider API key. Prefer config.json for repeated use.")
    parser.add_argument("--base-url", help="Base URL for the responses endpoint.")
    parser.add_argument("--response-model", help="Main responses model used for orchestration.")
    parser.add_argument("--image-model", "--model", dest="image_model", help="Image generation model name.")
    parser.add_argument("--output-dir", help="Directory for PNG output.")
    parser.add_argument(
        "--previous-response-id",
        help="Unsupported on the current image-generation API path; accepted only to return a clear error.",
    )
    parser.add_argument("--size", help="Optional image size passed to the image_generation tool.")
    parser.add_argument("--quality", help="Optional image quality passed to the image_generation tool.")
    parser.add_argument("--background", help="Optional background mode passed to the image_generation tool.")
    parser.add_argument("--output-format", choices=("png", "jpeg", "webp"), help="Image output format.")
    parser.add_argument("--output-compression", type=int, help="Compression level for jpeg/webp output.")
    parser.add_argument("--partial-images", type=int, help="Number of streamed preview images to request.")
    parser.add_argument(
        "--tool-choice",
        choices=("auto", "image_generation"),
        help="Force the image generation tool or leave tool routing automatic.",
    )
    parser.add_argument("--timeout-seconds", type=int, help="Network timeout in seconds.")
    parser.add_argument(
        "--stream",
        dest="stream",
        action="store_true",
        help="Use streaming responses events. Enabled by default.",
    )
    parser.add_argument(
        "--no-stream",
        dest="stream",
        action="store_false",
        help="Disable streaming and wait for the complete response payload.",
    )
    parser.set_defaults(stream=None)
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request config without calling the API.")
    parser.add_argument("--raw-json", action="store_true", help="Include the raw API JSON in output.")
    return parser.parse_args()


def load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is not valid JSON: {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")

    unknown_keys = sorted(set(data) - CONFIG_KEYS)
    if unknown_keys:
        print(
            json.dumps(
                {
                    "warning": (
                        "Ignoring unknown config.json field(s): "
                        + ", ".join(unknown_keys)
                    )
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )

    return data


def warn_if_config_file_is_too_open(path: Path) -> None:
    if not path.exists():
        return

    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        print(
            json.dumps(
                {
                    "warning": (
                        f"Config file {path} is readable by group/others. "
                        f"Consider: chmod 600 {path}"
                    )
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )


def config_value(
    args: argparse.Namespace,
    config: dict[str, Any],
    key: str,
    default: str,
    *,
    config_aliases: tuple[str, ...] | None = None,
) -> str:
    cli_value = getattr(args, key.replace("-", "_"), None)
    if isinstance(cli_value, str) and cli_value:
        return cli_value

    candidate_keys = config_aliases or (key,)
    for candidate_key in candidate_keys:
        config_value_raw = config.get(candidate_key)
        if isinstance(config_value_raw, str) and config_value_raw:
            return config_value_raw

    return default


def config_int_value(
    args: argparse.Namespace,
    config: dict[str, Any],
    key: str,
    default: int | None,
) -> int | None:
    cli_value = getattr(args, key.replace("-", "_"), None)
    if isinstance(cli_value, int):
        return cli_value

    config_value_raw = config.get(key)
    if isinstance(config_value_raw, int):
        return config_value_raw
    if isinstance(config_value_raw, str) and config_value_raw:
        return int(config_value_raw)

    return default


def config_bool_value(
    args: argparse.Namespace,
    config: dict[str, Any],
    key: str,
    default: bool,
) -> bool:
    cli_value = getattr(args, key.replace("-", "_"), None)
    if isinstance(cli_value, bool):
        return cli_value

    config_value_raw = config.get(key)
    if isinstance(config_value_raw, bool):
        return config_value_raw
    if isinstance(config_value_raw, str):
        normalized = config_value_raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

    return default


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt.strip()

    return Path(args.prompt_file).expanduser().read_text(encoding="utf-8").strip()


def build_request_body(
    args: argparse.Namespace,
    config: dict[str, Any],
    *,
    response_model: str,
    image_model: str,
    prompt: str,
    stream: bool,
) -> dict[str, Any]:
    output_format = config_value(args, config, "output_format", DEFAULT_OUTPUT_FORMAT)
    tool: dict[str, Any] = {
        "type": "image_generation",
        "model": image_model,
        "output_format": output_format,
    }
    if args.size:
        tool["size"] = args.size

    for field in ("quality", "background"):
        value = config_value(args, config, field, "")
        if value:
            tool[field] = value

    output_compression = config_int_value(args, config, "output_compression", None)
    if output_compression is not None:
        tool["output_compression"] = output_compression

    partial_images = config_int_value(args, config, "partial_images", None)
    if partial_images is not None:
        if not stream:
            raise ValueError("partial_images requires streaming. Remove --no-stream or unset partial_images.")
        tool["partial_images"] = partial_images

    body: dict[str, Any] = {
        "model": response_model,
        "input": prompt,
        "tools": [tool],
        "stream": stream,
    }

    tool_choice = config_value(args, config, "tool_choice", "auto")
    normalized_tool_choice = normalize_tool_choice(tool_choice)
    if normalized_tool_choice is not None:
        body["tool_choice"] = normalized_tool_choice

    return body


def normalize_tool_choice(tool_choice: str) -> dict[str, str] | None:
    if tool_choice == "image_generation":
        return {"type": "image_generation"}
    return None


def post_responses_api(
    base_url: str,
    api_key: str,
    body: dict[str, Any],
    *,
    timeout_seconds: int,
    on_partial_image: Callable[[dict[str, Any]], Any] | None = None,
    capture_stream_events: bool = False,
) -> dict[str, Any]:
    request = Request(
        f"{base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        if body.get("stream"):
            image = consume_stream_events(
                iter_sse_events(response),
                on_partial_image=on_partial_image,
                capture_events=capture_stream_events,
            )
            return {
                "response_json": image.get("response_json"),
                "image": image if image.get("image_base64") else None,
                "stream_events": image.get("stream_events"),
            }

        response_json = json.loads(response.read().decode("utf-8"))
        return {
            "response_json": response_json,
            "image": extract_image_result(response_json),
        }


def extract_image_result(response_json: dict[str, Any]) -> dict[str, Any] | None:
    output = response_json.get("output")
    if not isinstance(output, list):
        return None

    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "image_generation_call":
            continue

        result = item.get("result")
        if not isinstance(result, str) or not result:
            continue

        return {
            "image_base64": result,
            "image_call_id": item.get("id"),
            "revised_prompt": item.get("revised_prompt"),
            "action": item.get("action"),
            "partial_images": [],
            "response_id": response_json.get("id"),
        }

    return None


def iter_sse_events(lines: Iterable[bytes]) -> Iterator[dict[str, Any]]:
    event_name = "message"
    data_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            event = finalize_sse_event(event_name, data_lines)
            if event is not None:
                yield event
            event_name = "message"
            data_lines = []
            continue

        if line.startswith("event:"):
            event_name = line.partition(":")[2].strip() or "message"
            continue

        if line.startswith("data:"):
            data_lines.append(line.partition(":")[2].strip())

    event = finalize_sse_event(event_name, data_lines)
    if event is not None:
        yield event


def finalize_sse_event(event_name: str, data_lines: list[str]) -> dict[str, Any] | None:
    if not data_lines:
        return None

    payload = "\n".join(data_lines)
    if payload == "[DONE]":
        return None

    return {
        "event": event_name,
        "data": json.loads(payload),
    }


def consume_stream_events(
    events: Iterable[dict[str, Any]],
    *,
    on_partial_image: Callable[[dict[str, Any]], Any] | None = None,
    capture_events: bool = False,
) -> dict[str, Any]:
    partial_images: list[dict[str, Any]] = []
    final_image: dict[str, Any] | None = None
    response_json: dict[str, Any] | None = None
    response_id: str | None = None
    stream_events: list[dict[str, Any]] | None = [] if capture_events else None

    for event in events:
        if stream_events is not None:
            stream_events.append(event)

        data = event.get("data")
        if not isinstance(data, dict):
            continue

        event_type = data.get("type")
        if isinstance(data.get("response_id"), str) and not response_id:
            response_id = data["response_id"]

        if event_type == "response.image_generation_call.partial_image":
            partial_image_b64 = data.get("partial_image_b64")
            if isinstance(partial_image_b64, str) and partial_image_b64:
                partial = {
                    "index": data.get("partial_image_index"),
                    "image_base64": partial_image_b64,
                }
                partial_images.append(partial)
                if on_partial_image is not None:
                    on_partial_image(partial)
            continue

        if event_type == "response.output_item.done":
            image = extract_image_from_output_item(data.get("item"))
            if image is not None:
                final_image = image
            continue

        if event_type == "response.completed":
            response = data.get("response")
            if isinstance(response, dict):
                response_json = response
                if isinstance(response.get("id"), str) and not response_id:
                    response_id = response.get("id")
                if final_image is None:
                    final_image = extract_image_result(response)
            continue

        if event_type == "response.failed":
            raise ValueError(f"Responses streaming request failed: {json.dumps(data, ensure_ascii=False)}")

    if final_image is None:
        result = {
            "partial_images": partial_images,
            "response_json": response_json,
            "response_id": response_id,
        }
        if stream_events is not None:
            result["stream_events"] = stream_events
        return result

    final_image["partial_images"] = partial_images
    final_image["response_json"] = response_json
    final_image["response_id"] = final_image.get("response_id") or response_id
    if stream_events is not None:
        final_image["stream_events"] = stream_events
    return final_image


def extract_stream_image_result(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return consume_stream_events(events)


def save_partial_image_with_progress(
    partial: dict[str, Any],
    output_dir: str,
    image_model: str,
    *,
    output_format: str,
) -> str:
    partial_index = partial.get("index")
    suffix = partial_index if partial_index is not None else "unknown"
    saved_to = save_image(
        partial["image_base64"],
        output_dir,
        image_model,
        output_format=output_format,
        stem_suffix=f"partial-{suffix}",
    )
    print(
        json.dumps(
            {
                "event": "partial_image",
                "partial_index": partial_index,
                "saved_to": str(saved_to),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return str(saved_to)


def extract_image_from_output_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    if item.get("type") != "image_generation_call":
        return None

    result = item.get("result")
    if not isinstance(result, str) or not result:
        return None

    return {
        "image_base64": result,
        "image_call_id": item.get("id"),
        "revised_prompt": item.get("revised_prompt"),
        "action": item.get("action"),
        "partial_images": [],
    }


def save_image(
    image_base64: str,
    output_dir: str,
    model: str,
    *,
    output_format: str,
    stem_suffix: str | None = None,
    base_dir: Path | None = None,
) -> Path:
    directory = resolve_output_dir(output_dir, base_dir=base_dir)
    directory.mkdir(parents=True, exist_ok=True)

    stem_source = model if not stem_suffix else f"{model}-{stem_suffix}"
    stem = sanitize_file_stem(stem_source)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    extension = extension_for_output_format(output_format)
    candidate = directory / f"{stem}-{timestamp}.{extension}"
    suffix = 1
    while candidate.exists():
        candidate = directory / f"{stem}-{timestamp}-{suffix}.{extension}"
        suffix += 1

    candidate.write_bytes(base64.b64decode(image_base64))
    return candidate


def resolve_output_dir(output_dir: str, *, base_dir: Path | None = None) -> Path:
    directory = Path(output_dir).expanduser()
    if not directory.is_absolute():
        directory = (base_dir or Path.cwd()) / directory
    return directory.resolve()


def sanitize_file_stem(value: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return stem or "generated-image"


def extension_for_output_format(output_format: str) -> str:
    if output_format == "jpeg":
        return "jpeg"
    if output_format == "webp":
        return "webp"
    return "png"


def format_url_error(exc: HTTPError | URLError) -> str:
    if isinstance(exc, HTTPError):
        detail = exc.read().decode("utf-8", errors="replace")
        return f"Responses request failed with HTTP {exc.code}: {detail}"
    return f"Responses request failed: {exc.reason}"


def print_error(message: str, extra: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"error": message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
