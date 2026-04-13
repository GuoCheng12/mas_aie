from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any, Optional

import click

from aie_mas.macro_harness.backend import (
    ValidationError,
    describe_macro_capability,
    execute_macro_payload,
    execute_macro_screen,
    inspect_shared_structure_context_file,
    list_macro_capabilities,
    load_shared_structure_context_file,
    validate_shared_structure_context_file,
)


def _emit(data: Any, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                click.echo(f"{key}:")
                click.echo(json.dumps(value, ensure_ascii=False, indent=2))
            else:
                click.echo(f"{key}: {value}")
        return
    click.echo(str(data))


def _error_payload(
    *,
    error_code: str,
    message: str,
    command_path: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "command_path": command_path,
        "details": details or {},
    }


def _emit_error(
    ctx: click.Context,
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    exit_code: int = 1,
) -> None:
    if bool(ctx.obj.get("json")):
        click.echo(
            json.dumps(
                _error_payload(
                    error_code=error_code,
                    message=message,
                    command_path=ctx.command_path,
                    details=details,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise click.exceptions.Exit(exit_code)
    raise click.ClickException(message)


def _invoke_nested(argv: list[str], *, json_output: bool) -> None:
    cli.main(
        args=(["--json"] if json_output else []) + argv,
        prog_name="aie-mas-macro",
        standalone_mode=False,
    )


@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool) -> None:
    """Formal Macro CLI harness for bounded structural screening."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group("capability")
def capability_group() -> None:
    """Inspect supported macro screening capabilities."""


@capability_group.command("list")
@click.pass_context
def capability_list(ctx: click.Context) -> None:
    _emit({"capabilities": list_macro_capabilities()}, bool(ctx.obj.get("json")))


@capability_group.command("show")
@click.argument("capability_name")
@click.pass_context
def capability_show(ctx: click.Context, capability_name: str) -> None:
    try:
        result = describe_macro_capability(capability_name)
    except ValueError as exc:
        _emit_error(
            ctx,
            error_code="invalid_capability",
            message=str(exc),
            details={"capability_name": capability_name},
        )
        return
    _emit(result, bool(ctx.obj.get("json")))


@cli.group("screen")
def screen_group() -> None:
    """Run bounded structural screening commands."""


@screen_group.command("run")
@click.argument("capability_name")
@click.option("--smiles", required=True, help="Target molecule SMILES.")
@click.option(
    "--shared-structure-context-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="JSON file containing a serialized SharedStructureContext.",
)
@click.option(
    "--requested-deliverable",
    multiple=True,
    help="Repeatable requested deliverable override.",
)
@click.option(
    "--observable-tag",
    multiple=True,
    help="Repeatable requested observable tag override.",
)
@click.option(
    "--binding-mode",
    type=click.Choice(["hard", "preferred", "none"]),
    default=None,
    help="Optional binding mode.",
)
@click.pass_context
def screen_run(
    ctx: click.Context,
    capability_name: str,
    smiles: str,
    shared_structure_context_file: Optional[Path],
    requested_deliverable: tuple[str, ...],
    observable_tag: tuple[str, ...],
    binding_mode: Optional[str],
) -> None:
    try:
        shared_structure_context = load_shared_structure_context_file(
            shared_structure_context_file
        )
        result = execute_macro_screen(
            capability_name=capability_name,
            smiles=smiles,
            shared_structure_context=shared_structure_context,
            requested_deliverables=list(requested_deliverable),
            requested_observable_tags=list(observable_tag),
            binding_mode=binding_mode,
        )
    except FileNotFoundError as exc:
        _emit_error(
            ctx,
            error_code="context_file_not_found",
            message=str(exc),
            details={"shared_structure_context_file": str(shared_structure_context_file)},
        )
        return
    except ValidationError as exc:
        _emit_error(
            ctx,
            error_code="invalid_shared_structure_context",
            message="SharedStructureContext JSON failed schema validation.",
            details={"validation_error": str(exc)},
        )
        return
    except ValueError as exc:
        _emit_error(
            ctx,
            error_code="invalid_input",
            message=str(exc),
            details={"capability_name": capability_name},
        )
        return
    _emit(result, bool(ctx.obj.get("json")))


@cli.group("context")
def context_group() -> None:
    """Inspect or validate shared structure context files."""


@context_group.command("inspect")
@click.argument("context_file", type=click.Path(path_type=Path, dir_okay=False))
@click.pass_context
def context_inspect(ctx: click.Context, context_file: Path) -> None:
    try:
        result = inspect_shared_structure_context_file(context_file)
    except FileNotFoundError as exc:
        _emit_error(
            ctx,
            error_code="context_file_not_found",
            message=str(exc),
            details={"context_file": str(context_file)},
        )
        return
    except ValidationError as exc:
        _emit_error(
            ctx,
            error_code="invalid_shared_structure_context",
            message="SharedStructureContext JSON failed schema validation.",
            details={"context_file": str(context_file), "validation_error": str(exc)},
        )
        return
    _emit(result, bool(ctx.obj.get("json")))


@context_group.command("validate")
@click.argument("context_file", type=click.Path(path_type=Path, dir_okay=False))
@click.pass_context
def context_validate(ctx: click.Context, context_file: Path) -> None:
    try:
        result = validate_shared_structure_context_file(context_file)
    except FileNotFoundError as exc:
        _emit_error(
            ctx,
            error_code="context_file_not_found",
            message=str(exc),
            details={"context_file": str(context_file)},
        )
        return
    except ValidationError as exc:
        _emit_error(
            ctx,
            error_code="invalid_shared_structure_context",
            message="SharedStructureContext JSON failed schema validation.",
            details={"context_file": str(context_file), "validation_error": str(exc)},
        )
        return
    _emit(result, bool(ctx.obj.get("json")))


@cli.command("repl")
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start an interactive REPL for bounded Macro commands."""
    json_output = bool(ctx.obj.get("json"))
    click.echo("AIE-MAS Macro REPL. Type `help`, `exit`, or a command.")
    while True:
        try:
            raw_line = click.prompt("aie-mas-macro", prompt_suffix="> ", default="", show_default=False)
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break
        line = raw_line.strip()
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        if line == "help":
            click.echo("Examples:")
            click.echo("  capability list")
            click.echo("  screen run screen_neutral_aromatic_structure --smiles c1ccccc1")
            continue
        try:
            _invoke_nested(shlex.split(line), json_output=json_output)
        except SystemExit as exc:
            if exc.code not in (0, None):
                click.echo(f"Command exited with status {exc.code}.", err=True)
        except Exception as exc:  # pragma: no cover - REPL guardrail
            click.echo(f"Error: {exc}", err=True)


@cli.command("execute-payload", hidden=True)
def execute_payload() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    result = execute_macro_payload(payload)
    click.echo(json.dumps(result, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in args
    try:
        cli.main(args=args, prog_name="aie-mas-macro", standalone_mode=False)
    except click.ClickException as exc:
        if json_output:
            click.echo(
                json.dumps(
                    _error_payload(
                        error_code="invalid_command_usage",
                        message=exc.format_message(),
                        command_path="aie-mas-macro",
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            raise SystemExit(exc.exit_code)
        exc.show()
        raise SystemExit(exc.exit_code)
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.exit_code)
    except Exception as exc:
        if json_output:
            click.echo(
                json.dumps(
                    _error_payload(
                        error_code="unexpected_error",
                        message=str(exc),
                        command_path="aie-mas-macro",
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            raise SystemExit(1)
        raise


if __name__ == "__main__":
    main()
