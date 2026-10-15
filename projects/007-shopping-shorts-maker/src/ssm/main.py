"""`ssm` 명령 (CLI 엔트리포인트).

Claude Code가 이 명령들을 도구처럼 호출한다 (기획서 2.1 A안). 사람도 그대로 쓸 수 있다.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from ssm import __version__, doctor, fonts
from ssm.config import ADS, DURATIONS, FPS_CHOICES
from ssm.schemas import Source
from ssm.workspace import (ORDER, STAGES, Workspace, WorkspaceError, import_local_videos, list_projects,
                           workspace_root)

if hasattr(sys.stdout, "reconfigure"):  # Windows 콘솔에서 한글이 깨지지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="쇼핑 쇼츠 메이커 — 해외 숏폼 링크로 한국어 쇼핑 쇼츠를 만든다.", no_args_is_help=True,
                  add_completion=False, rich_markup_mode=None)
console = Console(highlight=False)

STATUS_LABEL = {"done": "[green]완료[/]", "stale": "[yellow]다시 실행 필요[/]", "pending": "[dim]대기[/]"}
CHECK_LABEL = {"ok": "[green]통과[/]", "warn": "[yellow]주의[/]", "fail": "[red]실패[/]"}
ProjectArg = typer.Argument(None, help="프로젝트 ID (생략하면 가장 최근 프로젝트)")


def fail(message: str, code: int = 1) -> None:
    console.print(f"[red][오류][/] {message}")
    raise typer.Exit(code)


def open_ws(project_id: Optional[str]) -> Workspace:
    try:
        return Workspace.open(project_id)
    except WorkspaceError as e:
        fail(str(e))


def validation_message(e: ValidationError) -> str:
    first = e.errors()[0]
    where = ".".join(str(x) for x in first["loc"])
    return f"{where}: {first['msg']}" if where else first["msg"]


# ---- 설치·점검 -----------------------------------------------------------------


@app.command("doctor")
def doctor_cmd(as_json: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력")) -> None:
    """설치 상태를 점검한다. 실패 항목이 있으면 종료 코드 1."""
    checks = doctor.run_checks()
    failed = [c for c in checks if c.status == "fail"]
    if as_json:
        print(json.dumps([c.__dict__ for c in checks], ensure_ascii=False, indent=2))
        raise typer.Exit(1 if failed else 0)

    table = Table(title=f"ssm doctor (v{__version__})", show_lines=False)
    for col in ("구분", "항목", "결과", "내용"):
        table.add_column(col)
    for c in checks:
        table.add_row(c.group, c.name, CHECK_LABEL[c.status], c.detail)
    console.print(table)
    for c in checks:
        if c.status != "ok" and c.fix:
            console.print(f" - {c.name}: {c.fix}")
    warns = sum(c.status == "warn" for c in checks)
    if failed:
        console.print(f"\n[red]실패 {len(failed)}개[/], 주의 {warns}개 — 위 안내대로 고친 뒤 다시 실행하세요.")
        raise typer.Exit(1)
    console.print(f"\n[green]모든 필수 항목 통과[/] (주의 {warns}개는 다음 단계에서 필요할 때 준비하면 됩니다)")


@app.command("fonts")
def fonts_cmd(force: bool = typer.Option(False, "--force", help="이미 있어도 다시 받기")) -> None:
    """자막·썸네일용 무료 폰트(OFL)를 내려받는다."""
    console.print(f"폰트 폴더: {fonts.fonts_dir()}")
    failed = fonts.install_fonts(force=force, log=console.print)
    if failed:
        fail(f"폰트 {len(failed)}개를 받지 못했습니다. 인터넷 연결을 확인하고 `ssm fonts`를 다시 실행하세요.")


# ---- 프로젝트 ---------------------------------------------------------------------


def _ask_choice(label: str, choices: list[str], default: str) -> str:
    return typer.prompt(f"{label} ({'/'.join(choices)})", default=default,
                        type=typer.Choice(choices, case_sensitive=False))


@app.command("new")
def new_cmd(
    source: Optional[str] = typer.Argument(None, help="원본 영상 URL 또는 검색 키워드"),
    local: list[Path] = typer.Option([], "--local", help="직접 받아둔 영상 파일 (여러 번 지정 가능)"),
    duration: Optional[int] = typer.Option(None, "--duration", help="영상 길이(초): 15/30/45/60"),
    fps: Optional[int] = typer.Option(None, "--fps", help="30 또는 60"),
    ad: Optional[str] = typer.Option(None, "--ad", help="광고 표시: coupang/aliexpress/custom"),
    ad_text: Optional[str] = typer.Option(None, "--ad-text", help="--ad custom일 때 넣을 문구"),
    yes: bool = typer.Option(False, "--yes", "-y", help="빠진 옵션을 묻지 않고 기본값 사용"),
) -> None:
    """새 프로젝트를 만든다."""
    if not source and not local:
        fail("URL·키워드 또는 --local 파일 중 하나는 필요합니다.")
    interactive = sys.stdin.isatty() and not yes
    if interactive:
        if duration is None:
            duration = int(_ask_choice("영상 길이(초)", [str(d) for d in DURATIONS], "30"))
        if fps is None:
            fps = int(_ask_choice("fps", [str(f) for f in FPS_CHOICES], "30"))
        if ad is None:
            ad = _ask_choice("광고 표시 (later=렌더링 전에 선택)", [*ADS, "later"], "coupang")
        if ad == "custom" and not ad_text:
            ad_text = typer.prompt("광고 문구 직접 입력")

    overrides: dict = {}
    if duration is not None:
        overrides.setdefault("project", {})["duration_sec"] = duration
    if fps is not None:
        overrides.setdefault("video", {})["fps"] = fps
    if ad and ad != "later":
        overrides["ad_disclosure"] = {"profile": ad, **({"custom_text": ad_text} if ad_text else {})}

    if local:
        src = Source(type="local", value=source, files=[str(p.resolve()) for p in local])
    elif source.startswith(("http://", "https://")):
        src = Source(type="url", value=source)
    else:
        src = Source(type="keyword", value=source)

    try:
        ws = Workspace.create(src, overrides)
    except ValidationError as e:
        fail("설정 값이 올바르지 않습니다 — " + validation_message(e))
    if local:
        try:
            copied = import_local_videos(ws, list(local))
        except WorkspaceError as e:
            fail(str(e))
        console.print(f"영상 {len(copied)}개를 raw_videos/에 복사했습니다.")

    cfg = ws.config()
    console.print(f"[green]프로젝트를 만들었습니다:[/] {ws.id}")
    console.print(f"  폴더: {ws.path}")
    console.print(f"  길이 {cfg.project.duration_sec}초 · {cfg.video.fps}fps · 광고 표시: "
                  f"{cfg.ad_disclosure.profile or '아직 선택 안 함 (렌더링 전에 필요)'}")
    if local:
        console.print(f"  다음 단계: 대본을 {ws.path / 'script.json'}에 저장한 뒤 `ssm run` (analyze → tts → edit)")
    else:
        console.print("  다음 단계: 수집·분석 기능은 아직 개발 중입니다 (M2~M3). "
                      "직접 받은 영상이 있으면 `ssm new --local 영상.mp4`로 만들 수 있습니다.")


@app.command("list")
def list_cmd() -> None:
    """프로젝트 목록."""
    projects = list_projects()
    if not projects:
        console.print(f"프로젝트가 없습니다. ({workspace_root()})")
        return
    table = Table()
    for col in ("ID", "원본", "남은 단계"):
        table.add_column(col)
    for ws in projects:
        src = ws.project().source
        label = src.value or f"로컬 파일 {len(src.files)}개"
        table.add_row(ws.id, label, ", ".join(ws.pending_stages()) or "없음")
    console.print(table)


@app.command("status")
def status_cmd(project_id: Optional[str] = ProjectArg) -> None:
    """단계별 진행 상황과 프로젝트 설정."""
    ws = open_ws(project_id)
    cfg = ws.config()
    console.print(f"[bold]{ws.id}[/]  ({ws.path})")
    console.print(f"길이 {cfg.project.duration_sec}초 · {cfg.video.fps}fps · 광고 표시: "
                  f"{cfg.ad_disclosure.profile or '[yellow]선택 안 함[/]'}")
    table = Table()
    for col in ("단계", "이름", "상태", "구현"):
        table.add_column(col)
    statuses = ws.statuses()
    for name in ORDER:
        stage = STAGES[name]
        table.add_row(name, stage.title, STATUS_LABEL[statuses[name]],
                      "구현됨" if name in IMPLEMENTED else f"{stage.milestone} 예정")
    console.print(table)
    versions = ws.versions()
    if versions:
        console.print(f"보관된 버전: {', '.join(f'v{v}' for v in versions)}")


@app.command("set")
def set_cmd(
    key: str = typer.Argument(..., help="설정 키 (예: subtitle.size)"),
    value: str = typer.Argument(..., help="값 (예: 90, true, null, \"문구\")"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="프로젝트 ID (생략하면 최근 프로젝트)"),
) -> None:
    """이 프로젝트에만 적용할 설정을 바꾼다. 영향을 받는 단계만 '다시 실행 필요'가 된다."""
    ws = open_ws(project_id)
    parsed = yaml.safe_load(value)
    try:
        ws.set_override(key, parsed)
    except ValidationError as e:
        fail("설정 값이 올바르지 않습니다 — " + validation_message(e))
    except WorkspaceError as e:
        fail(str(e))
    todo = ws.pending_stages()
    console.print(f"{key} = {parsed!r} 저장. 다시 실행할 단계: {', '.join(todo) or '없음'}")


@app.command("versions")
def versions_cmd(project_id: Optional[str] = ProjectArg) -> None:
    """보관된 결과물 버전 목록."""
    ws = open_ws(project_id)
    versions = ws.versions()
    console.print(", ".join(f"v{v}" for v in versions) if versions else "보관된 버전이 없습니다.")


@app.command("rollback")
def rollback_cmd(version: int = typer.Argument(..., help="되돌릴 버전 번호 (예: 2)"),
                 project_id: Optional[str] = typer.Option(None, "--project", "-p")) -> None:
    """결과물을 이전 버전으로 되돌린다 (지금 상태도 새 버전으로 남긴다)."""
    ws = open_ws(project_id)
    try:
        ws.rollback(version)
    except WorkspaceError as e:
        fail(str(e))
    console.print(f"v{version}으로 되돌렸습니다. 되돌리기 전 상태는 v{ws.versions()[-1]}에 있습니다.")


# ---- 제작 단계 ---------------------------------------------------------------------


def _run_stage(stage: str, ws: Workspace, **options) -> None:
    """구현된 단계를 실행한다. 사용자에게 보여줄 오류는 한국어 메시지로 바꿔 종료한다."""
    from ssm.analyzer import AnalyzeError, run_analyze
    from ssm.media import MediaError
    from ssm.tts_engine import TTSError, run_tts
    from ssm.video_editor import EditError, run_edit

    console.print(f"[bold]▶ {STAGES[stage].title}[/] ({stage})")
    try:
        if stage == "analyze":
            run_analyze(ws, log=console.print)
        elif stage == "tts":
            run_tts(ws, log=console.print)
        elif stage == "edit":
            out = run_edit(ws, preview=options.get("preview", False), log=console.print)
            console.print(f"[green]완성:[/] {out}")
    except (AnalyzeError, TTSError, EditError, MediaError, WorkspaceError) as e:
        fail(str(e))


IMPLEMENTED = ("analyze", "tts", "edit")


def _not_ready(stage: str) -> None:
    s = STAGES[stage]
    fail(f"'{s.title}'({stage}) 단계는 아직 구현되지 않았습니다 ({s.milestone}에서 구현 예정).", code=2)


def _stage_command(stage: str) -> None:
    def command(project_id: Optional[str] = ProjectArg) -> None:
        open_ws(project_id)
        _not_ready(stage)

    command.__doc__ = f"{STAGES[stage].title} ({STAGES[stage].milestone}에서 구현 예정)"
    app.command(stage)(command)


for _stage in ORDER:
    if _stage not in IMPLEMENTED:
        _stage_command(_stage)


@app.command("analyze")
def analyze_cmd(project_id: Optional[str] = ProjectArg) -> None:
    """원본 영상의 샷·하이라이트 점수·고정 글자(자막) 영역을 분석해 analysis.json을 만든다."""
    _run_stage("analyze", open_ws(project_id))


@app.command("add")
def add_cmd(files: list[Path] = typer.Argument(..., help="추가할 영상 파일들"),
            project_id: Optional[str] = typer.Option(None, "--project", "-p", help="프로젝트 ID (생략하면 최근 프로젝트)")) -> None:
    """같은 상품 영상을 프로젝트에 추가한다 (raw_videos/). 추가하면 analyze부터 다시 실행된다."""
    ws = open_ws(project_id)
    try:
        copied = import_local_videos(ws, files)
    except WorkspaceError as e:
        fail(str(e))
    console.print(f"영상 {len(copied)}개를 추가했습니다: {', '.join(p.name for p in copied)}. 다음: `ssm run`")


@app.command("tts")
def tts_cmd(project_id: Optional[str] = ProjectArg) -> None:
    """script.json을 읽어 음성(tts.mp3)과 단어별 시간(word_timings.json)을 만든다."""
    _run_stage("tts", open_ws(project_id))


@app.command("edit")
def edit_cmd(project_id: Optional[str] = ProjectArg,
             preview: bool = typer.Option(False, "--preview", help="540x960으로 빠르게 미리보기 (preview.mp4)")) -> None:
    """원본 영상에 음성·한국어 자막·광고 표시를 얹어 final_output.mp4를 만든다."""
    _run_stage("edit", open_ws(project_id), preview=preview)


@app.command("run")
def run_cmd(project_id: Optional[str] = ProjectArg) -> None:
    """남은 단계를 순서대로 실행한다 (state.json 기준). 아직 개발 전인 단계는 건너뛴다."""
    ws = open_ws(project_id)
    todo = ws.pending_stages()
    if not todo:
        console.print("모든 단계가 완료되어 있습니다.")
        return
    if not any(s in IMPLEMENTED for s in todo):
        console.print(f"구현된 단계({', '.join(IMPLEMENTED)})는 모두 최신입니다. "
                      f"남은 단계 {', '.join(todo)}는 아직 개발 전입니다.")
        return
    console.print(f"실행할 단계: {' → '.join(todo)}")
    for stage in ORDER:  # 앞 단계를 돌린 뒤 상태를 다시 보므로, 결과가 바뀐 단계만 이어서 실행된다
        if stage not in IMPLEMENTED:
            if stage in todo:
                console.print(f"[dim]- {stage}: 아직 개발 전 단계라 건너뜁니다 ({STAGES[stage].milestone} 예정)[/]")
        elif ws.status(stage) != "done":
            _run_stage(stage, ws)


@app.callback(invoke_without_command=True)
def main(version: bool = typer.Option(False, "--version", help="버전 출력")) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()
