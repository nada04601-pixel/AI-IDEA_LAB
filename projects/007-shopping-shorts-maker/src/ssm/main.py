"""`ssm` 명령 (CLI 엔트리포인트).

Claude Code가 이 명령들을 도구처럼 호출한다 (기획서 2.1 A안). 사람도 그대로 쓸 수 있다.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
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


def _is_terminal() -> bool:
    """사람이 직접 입력하는 창인지 (Claude Code·스크립트에서는 묻지 않고 기본값)."""
    return sys.stdin.isatty()


def _ask_choice(label: str, choices: list[str], default: str) -> str:
    return typer.prompt(f"{label} ({'/'.join(choices)})", default=default,
                        type=click.Choice(choices, case_sensitive=False))


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
    interactive = _is_terminal() and not yes
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
        if _looks_cut(source):
            console.print("[yellow][주의][/] 링크에 접근 토큰(xsec_token)이 없습니다 — 공유 링크의 '&' 뒤가 잘렸을 수 있습니다.\n"
                          "  PowerShell에서 ssm.bat을 쓰면 '&' 뒤가 잘립니다 → `.venv\\Scripts\\ssm.exe new \"링크\"`를 쓰세요.")
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
        console.print("  다음 단계: `ssm run`으로 수집·분석 → `ssm script --preset N`으로 대본 요청서 → 대본 작성 → `ssm run`")
    else:
        console.print("  다음 단계: `ssm collect` (같은 상품 영상 수집·필터) → `ssm analyze` → `ssm script --preset N`")


def _looks_cut(url: str) -> bool:
    """샤오홍슈·rednote 글 링크인데 접근 토큰이 없으면 (짧은 링크 xhslink 제외) — 열 때 보안 오류가 난다."""
    from ssm.downloader import platform_of

    return platform_of(url) == "xiaohongshu" and "xhslink.com" not in url and "xsec_token=" not in url


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
    for col in ("단계", "이름", "상태"):
        table.add_column(col)
    statuses = ws.statuses()
    for name in ORDER:
        table.add_row(name, STAGES[name].title, STATUS_LABEL[statuses[name]])
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
    """보관된 결과물 버전 목록 (만들 때마다 직전 결과를 자동 보관)."""
    ws = open_ws(project_id)
    versions = ws.versions()
    if not versions:
        console.print("보관된 버전이 없습니다.")
        return
    table = Table()
    for col in ("버전", "보관 시각", "메모", "영상"):
        table.add_column(col)
    for v in versions:
        info = ws.version_info(v)
        has_video = (ws.path / "versions" / f"v{v}" / "final_output.mp4").is_file()
        table.add_row(f"v{v}", info.get("created_at", "").replace("T", " "), info.get("note", ""), "있음" if has_video else "")
    console.print(table)
    console.print("되돌리기: `ssm rollback 번호` (지금 상태도 버전으로 남는다)")


@app.command("rollback")
def rollback_cmd(version: int = typer.Argument(..., help="되돌릴 버전 번호 (예: 2)"),
                 project_id: Optional[str] = typer.Option(None, "--project", "-p")) -> None:
    """결과물을 이전 버전으로 되돌린다 (지금 상태도 새 버전으로 남긴다)."""
    ws = open_ws(project_id)
    try:
        kept = ws.rollback(version)
    except WorkspaceError as e:
        fail(str(e))
    console.print(f"v{version}으로 되돌렸습니다." + (f" 되돌리기 전 상태는 v{kept}에 있습니다." if kept else ""))


# ---- 제작 단계 ---------------------------------------------------------------------


PRODUCTION = ("script", "tts", "edit", "meta")  # 결과물을 바꾸는 단계


def _keep_version(ws: Workspace, stages: list[str]) -> None:
    """실행이 성공한 뒤 결과를 버전으로 보관한다 (입력과 결과물이 서로 맞는 상태만 남는다)."""
    if any(s in PRODUCTION for s in stages) and (n := ws.snapshot(f"{' → '.join(stages)} 실행 후")):
        console.print(f"[dim]이 결과를 v{n}로 보관했습니다 (`ssm versions`, `ssm rollback 번호`).[/]")


def _run_stage(stage: str, ws: Workspace, **options) -> None:
    """구현된 단계를 실행한다. 사용자에게 보여줄 오류는 한국어 메시지로 바꿔 종료한다."""
    from ssm.analyzer import AnalyzeError, run_analyze
    from ssm.collector import CollectError, run_collect
    from ssm.media import MediaError
    from ssm.metadata_gen import MetaError, run_meta
    from ssm.scripter import ScriptError, run_script_check
    from ssm.tts_engine import TTSError, run_tts
    from ssm.video_editor import EditError, run_edit

    console.print(f"[bold]▶ {STAGES[stage].title}[/] ({stage})")

    def log(message: str) -> None:  # 단계 로그는 그대로 찍는다 (영상 제목의 [话题] 같은 대괄호를 서식으로 읽지 않게)
        console.print(message, markup=False)

    try:
        if stage == "collect":
            run_collect(ws, log=log)
        elif stage == "analyze":
            run_analyze(ws, log=log)
        elif stage == "script":
            run_script_check(ws, log=log)
        elif stage == "tts":
            run_tts(ws, log=log)
        elif stage == "edit":
            out = run_edit(ws, preview=options.get("preview", False), log=log)
            console.print(f"[green]완성:[/] {out}")
        elif stage == "meta":
            run_meta(ws, log=log)
            console.print(f"[green]썸네일·캡션:[/] {ws.path}")
    except (CollectError, AnalyzeError, ScriptError, TTSError, EditError, MetaError, MediaError, WorkspaceError) as e:
        fail(str(e))


@app.command("collect")
def collect_cmd(project_id: Optional[str] = ProjectArg,
                keyword: Optional[str] = typer.Option(None, "--keyword", "-k", help="같은 상품 검색어 (중국어 권장)"),
                url: list[str] = typer.Option([], "--url", help="직접 지정할 후보 링크 (여러 번 지정 가능, 기존 목록에 추가)"),
                max_videos: Optional[int] = typer.Option(None, "--max", help="채택할 영상 수 (기본 5)")) -> None:
    """기준 영상과 같은 상품 영상을 모으고 국내 콘텐츠를 걸러 raw_videos/에 넣는다. 옵션은 프로젝트 설정으로 저장된다."""
    ws = open_ws(project_id)
    try:
        if keyword is not None:
            ws.set_override("collector.keyword", keyword)
        if url:
            ws.set_override("collector.urls", [*ws.config().collector.urls, *url])
        if max_videos is not None:
            ws.set_override("collector.max_videos", max_videos)
    except ValidationError as e:
        fail("설정 값이 올바르지 않습니다 — " + validation_message(e))
    _run_stage("collect", ws)


@app.command("presets")
def presets_cmd() -> None:
    """대본 프리셋 목록 (사용자에게 보여주고 고르게 한다)."""
    from ssm.config import load_config
    from ssm.scripter import ScriptError, load_presets

    try:
        presets = load_presets(load_config())
    except ScriptError as e:
        fail(str(e))
    table = Table()
    for col in ("번호", "프리셋", "설명", "훅 예시"):
        table.add_column(col)
    for p in presets:
        table.add_row(str(p.number), f"{p.name}\n({p.id})", f"{p.description}\n어울리는 상품: {p.fits}",
                      p.hook_patterns[0] if p.hook_patterns else "")
    console.print(table)


@app.command("script")
def script_cmd(project_id: Optional[str] = ProjectArg,
               preset: Optional[str] = typer.Option(None, "--preset", help="프리셋 번호(1~4) 또는 이름 — `ssm presets`"),
               reference: Optional[str] = typer.Option(None, "--reference",
                                                       help="화법을 따라 할 영상 링크·파일 또는 대본 .txt ('none'이면 해제)"),
               check: bool = typer.Option(False, "--check", help="Claude가 쓴 script.json을 검사하고 통과하면 완료로 기록")) -> None:
    """(A안) 대본 작성 요청서(script_prompt.md)를 만든다. 대본은 Claude가 그 요청서대로 script.json에 쓴다."""
    from ssm.media import MediaError
    from ssm.scripter import ScriptError, find_preset, load_presets, prepare_request

    ws = open_ws(project_id)
    if check:
        _run_stage("script", ws)
        return
    try:
        if preset is not None:
            found = find_preset(load_presets(ws.config()), preset)
            if found is None:
                fail(f"프리셋 '{preset}'이 없습니다 → `ssm presets`로 목록을 보세요.")
            ws.set_override("script.preset", found.id)
        if reference is not None:
            ws.set_override("script.reference", None if reference.lower() == "none" else reference)
        prepare_request(ws, log=lambda m: console.print(m, markup=False))
    except (ScriptError, MediaError, WorkspaceError) as e:
        fail(str(e))
    except ValidationError as e:
        fail("설정 값이 올바르지 않습니다 — " + validation_message(e))
    console.print("다음: Claude가 요청서대로 script.json을 쓰고 → `ssm script --check` → `ssm run`")


@app.command("meta")
def meta_cmd(project_id: Optional[str] = ProjectArg,
             style: Optional[str] = typer.Option(None, "--style", help="따라 할 썸네일 이미지 ('none'이면 해제)")) -> None:
    """썸네일 3안(thumbnail_1~3.png)과 플랫폼별 캡션(caption.txt)을 만든다. 문구는 meta.json (Claude 작성)."""
    from ssm.metadata_gen import MetaError, save_style

    ws = open_ws(project_id)
    if style is not None:
        try:
            result = save_style(ws, None if style.lower() == "none" else style)
        except MetaError as e:
            fail(str(e))
        if result:
            console.print(f"썸네일 스타일: 강조색 {result.top_color} · 요약색 {result.bottom_color} · 팔레트 "
                          f"{', '.join(result.palette[:4])} → thumbnail_style.json", markup=False)
            for note in result.notes:
                console.print(f"[참고] {note}", markup=False)
    _run_stage("meta", ws)
    _keep_version(ws, ["meta"])


@app.command("cuts")
def cuts_cmd(number: Optional[int] = typer.Argument(None, help="이 번호 컷 대신 쓸 수 있는 장면도 보여준다"),
             project_id: Optional[str] = typer.Option(None, "--project", "-p", help="프로젝트 ID (생략하면 최근 프로젝트)")) -> None:
    """마지막으로 렌더링한 영상의 컷 목록 (번호·시간·구간·자막·장면)."""
    from ssm.cutplan import replacement_candidates

    ws = open_ws(project_id)
    timeline, analysis = _load_timeline(ws)
    overrides = {round(o.position, 2) for o in _load_overrides(ws).cuts}
    sentences = _sentences(ws)
    table = Table()
    for col in ("번호", "시간", "구간", "그때 자막", "장면", "원본"):
        table.add_column(col)
    for i, c in enumerate(timeline.cuts, start=1):
        mark = " (교체)" if round(c.position, 2) in overrides else ""
        table.add_row(str(i), f"{c.position:.1f}~{c.position + c.length:.1f}초", c.section or "",
                      _text_at(sentences, c.position), f"{c.shot_id}{mark}", c.source.split("/")[-1])
    console.print(table, markup=False)
    if number is not None:
        if not 1 <= number <= len(timeline.cuts):
            fail(f"컷 번호는 1~{len(timeline.cuts)}입니다.")
        options = replacement_candidates(timeline, analysis, number - 1)
        console.print(f"{number}번 컷 대신 쓸 수 있는 장면 (점수 순): " +
                      (", ".join(f"{s.id}({s.duration:.1f}초, 점수 {s.score:.2f})" for _, s in options[:8]) or "없음"),
                      markup=False)


@app.command("cut")
def cut_cmd(number: int = typer.Argument(..., help="바꿀 컷 번호 (`ssm cuts`로 확인)"),
            shot: Optional[str] = typer.Option(None, "--shot", help="대신 쓸 장면 ID (생략하면 점수가 가장 높은 다른 장면)"),
            reset: bool = typer.Option(False, "--reset", help="이 컷의 교체를 취소하고 원래 장면으로"),
            project_id: Optional[str] = typer.Option(None, "--project", "-p")) -> None:
    """컷 하나만 다른 장면으로 바꾼다 (overrides.json). 다음 `ssm run`에서 편집 단계만 다시 실행된다."""
    from ssm.cutplan import POSITION_TOLERANCE, PlanError, check_replacement, replacement_candidates
    from ssm.schemas import CutOverride

    ws = open_ws(project_id)
    timeline, analysis = _load_timeline(ws)
    if not 1 <= number <= len(timeline.cuts):
        fail(f"컷 번호는 1~{len(timeline.cuts)}입니다 (`ssm cuts`).")
    cut = timeline.cuts[number - 1]
    overrides = _load_overrides(ws)
    existing = next((o for o in overrides.cuts if abs(o.position - cut.position) <= POSITION_TOLERANCE), None)
    if reset:
        if existing is None:
            fail(f"{number}번 컷은 바꾼 적이 없습니다.")
        overrides.cuts.remove(existing)
        message = f"{number}번 컷을 원래 장면({existing.was})으로 되돌립니다."
    else:
        try:
            if shot is None:
                options = replacement_candidates(timeline, analysis, number - 1)
                if not options:
                    raise PlanError("바꿔 넣을 수 있는 장면이 없습니다 (모두 쓰는 중이거나 짧음) → 같은 상품 영상을 `ssm add`로 추가하세요.")
                shot = options[0][1].id
            else:
                check_replacement(timeline, analysis, number - 1, shot)
        except PlanError as e:
            fail(str(e))
        if existing:
            existing.shot = shot
        else:
            overrides.cuts.append(CutOverride(position=cut.position, was=cut.shot_id, shot=shot))
        message = f"{number}번 컷 ({cut.position:.1f}초~): {cut.shot_id} → {shot}"
    (ws.path / "overrides.json").write_text(overrides.model_dump_json(indent=2), encoding="utf-8")
    console.print(message + " · `ssm run`으로 다시 렌더링합니다 (편집 단계만).", markup=False)


def _load_timeline(ws: Workspace):
    from ssm.schemas import Analysis, Timeline

    files = [ws.path / "timeline.json", ws.path / "analysis.json"]
    if not all(f.is_file() for f in files):
        fail("아직 렌더링한 영상이 없습니다 → 먼저 `ssm run`")
    return (Timeline.model_validate_json(files[0].read_text(encoding="utf-8")),
            Analysis.model_validate_json(files[1].read_text(encoding="utf-8")))


def _load_overrides(ws: Workspace):
    from ssm.video_editor import EditError, load_overrides

    try:
        return load_overrides(ws)
    except EditError as e:
        fail(str(e))


def _sentences(ws: Workspace) -> list[tuple[float, str]]:
    from ssm.schemas import WordTimings

    path = ws.path / "word_timings.json"
    if not path.is_file():
        return []
    timings = WordTimings.model_validate_json(path.read_text(encoding="utf-8"))
    return [(s.words[0].start if s.words else s.start, s.text) for s in timings.sentences]


def _text_at(sentences: list[tuple[float, str]], t: float) -> str:
    text = sentences[0][1] if sentences else ""  # 첫 문장 앞 짧은 무음 구간도 첫 문장으로
    for start, sentence in sentences:
        if start <= t + 0.05:
            text = sentence
    return text if len(text) <= 18 else text[:17] + "…"


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
    ws = open_ws(project_id)
    _run_stage("tts", ws)
    _keep_version(ws, ["tts"])


@app.command("edit")
def edit_cmd(project_id: Optional[str] = ProjectArg,
             preview: bool = typer.Option(False, "--preview", help="540x960으로 빠르게 미리보기 (preview.mp4)")) -> None:
    """원본 영상에 음성·한국어 자막·광고 표시를 얹어 final_output.mp4를 만든다."""
    ws = open_ws(project_id)
    _run_stage("edit", ws, preview=preview)
    if not preview:
        _keep_version(ws, ["edit"])


@app.command("run")
def run_cmd(project_id: Optional[str] = ProjectArg) -> None:
    """남은 단계를 순서대로 실행한다 (state.json 기준). 결과가 바뀐 단계만 이어서 실행된다."""
    ws = open_ws(project_id)
    todo = ws.pending_stages()
    if not todo:
        console.print("모든 단계가 완료되어 있습니다.")
        return
    console.print(f"실행할 단계: {' → '.join(todo)}")
    executed = []
    for stage in ORDER:  # 앞 단계를 돌린 뒤 상태를 다시 보므로, 앞 단계 결과가 그대로면 뒤 단계는 건너뛴다
        if ws.status(stage) != "done":
            _run_stage(stage, ws)  # 실패하면 여기서 끝난다 (그 결과는 보관하지 않는다)
            executed.append(stage)
    _keep_version(ws, executed)


@app.callback(invoke_without_command=True)
def main(version: bool = typer.Option(False, "--version", help="버전 출력")) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()
