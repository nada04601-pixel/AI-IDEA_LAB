"""프로젝트 작업 폴더(workspace/{project_id}/)와 단계별 상태(state.json) 관리.

단계가 끝나면 그 단계의 '입력 해시'를 기록해 둔다. 입력 해시는
  - 그 단계가 쓰는 설정 구역(config 일부)
  - 앞 단계 산출물의 현재 내용
으로 계산하므로, 설정을 바꾸거나 앞 단계 파일(예: script.json)을 고치면 영향을 받는 단계만 다시 실행 대상이 된다.
"""

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from ssm.config import AppConfig, load_config, raw_config, set_dotted
from ssm.schemas import ProjectFile, Source


@dataclass(frozen=True)
class Stage:
    name: str
    title: str
    upstream: tuple[str, ...]
    config_keys: tuple[str, ...]
    outputs: tuple[str, ...]  # 프로젝트 폴더 기준 파일·폴더 이름 (glob 패턴 가능)
    milestone: str
    inputs: tuple[str, ...] = ()  # 앞 단계 산출물 외에 직접 읽는 파일 (예: 로컬로 넣은 raw_videos)


STAGES: dict[str, Stage] = {
    s.name: s
    for s in [
        Stage("collect", "원본 수집·필터", (), ("collector",), ("raw_videos", "candidates.json", "selected.json"), "M3"),
        # 자막 가리는 방식(foreign_sub_removal)은 edit에서 적용하므로 분석 결과와 무관하다
        Stage("analyze", "영상 분석", ("collect",), (), ("analysis.json",), "M2", inputs=("raw_videos",)),
        Stage("script", "대본", ("analyze",), ("project", "script"), ("script.json",), "M4"),
        Stage("tts", "음성·자막 타이밍", ("script",), ("tts", "audio"), ("tts.mp3", "word_timings.json"), "M1"),
        # 자막 화면 나누기는 자막 설정(한 줄 글자 수)에 따라 달라지므로 subtitles.srt는 edit에서 만든다
        Stage("edit", "편집·렌더링", ("tts", "analyze"),
              ("project", "video", "subtitle", "foreign_sub_removal", "ad_disclosure", "audio"),
              ("timeline.json", "subtitles.srt", "final_output.mp4"), "M1"),
        Stage("meta", "썸네일·캡션", ("script", "analyze"), ("thumbnail", "ad_disclosure"),
              ("thumbnail*.png", "caption.txt"), "M5"),
    ]
}
ORDER = list(STAGES)

# 버전으로 보관할 결과물 (원본 영상·분석 결과처럼 크고 다시 만들 필요 없는 것은 제외)
VERSIONED = ("project.yaml", "state.json", "script.json", "tts.mp3", "word_timings.json", "subtitles.srt",
             "timeline.json", "final_output.mp4", "thumbnail*.png", "caption.txt")

BIG_FILE = 16 * 1024 * 1024  # 이보다 큰 파일은 내용 대신 크기·수정 시각으로 변화를 판단한다 (속도)


class WorkspaceError(Exception):
    """사용자에게 그대로 보여줄 수 있는 작업 폴더 오류."""


def workspace_root(cfg: AppConfig | None = None) -> Path:
    cfg = cfg or load_config()
    root = cfg.path(cfg.workspace_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def slugify(text: str, limit: int = 30) -> str:
    text = text.strip()
    if text.startswith(("http://", "https://")):  # URL은 '사이트-영상ID'만 남긴다
        url = urlparse(text)
        labels = url.hostname.split(".") if url.hostname else ["url"]
        site = labels[-2] if len(labels) >= 2 else labels[0]  # v.douyin.com → douyin
        last = [p for p in url.path.split("/") if p]
        text = f"{site}-{last[-1]}" if last else site
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-").lower()
    return slug[:limit].strip("-") or "project"


def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    if stat.st_size > BIG_FILE:
        return f"size:{stat.st_size}:mtime:{stat.st_mtime_ns}"
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Workspace:
    def __init__(self, path: Path):
        self.path = path
        self.id = path.name

    # ---- 생성·열기 ----------------------------------------------------------

    @classmethod
    def create(cls, source: Source, overrides: dict | None = None, root: Path | None = None,
               now: datetime | None = None) -> "Workspace":
        root = root or workspace_root()
        now = now or datetime.now()
        label = source.value or (Path(source.files[0]).stem if source.files else "project")
        base = f"{now:%Y%m%d-%H%M}-{slugify(label)}"
        path, n = root / base, 2
        while path.exists():
            path, n = root / f"{base}-{n}", n + 1
        path.mkdir(parents=True)
        for sub in ("raw_videos", "logs", "versions"):
            (path / sub).mkdir()
        ws = cls(path)
        ws._write_project(ProjectFile(id=path.name, created_at=now, source=source, overrides=overrides or {}))
        ws.config()  # 잘못된 설정이면 여기서 바로 알린다
        return ws

    @classmethod
    def open(cls, project_id: str | None, root: Path | None = None) -> "Workspace":
        """project_id가 없으면 가장 최근 프로젝트를 연다."""
        root = root or workspace_root()
        if project_id:
            path = root / project_id
            if not (path / "project.yaml").is_file():
                raise WorkspaceError(f"프로젝트 '{project_id}'를 찾을 수 없습니다. `ssm list`로 목록을 확인하세요.")
            return cls(path)
        projects = list_projects(root)
        if not projects:
            raise WorkspaceError("프로젝트가 없습니다. `ssm new`로 먼저 만드세요.")
        return projects[-1]

    # ---- project.yaml / 설정 --------------------------------------------------

    @property
    def project_file(self) -> Path:
        return self.path / "project.yaml"

    def project(self) -> ProjectFile:
        data = yaml.safe_load(self.project_file.read_text(encoding="utf-8")) or {}
        return ProjectFile.model_validate(data)

    def _write_project(self, project: ProjectFile) -> None:
        text = yaml.safe_dump(project.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        self.project_file.write_text(text, encoding="utf-8")

    def config(self) -> AppConfig:
        """전역 설정에 이 프로젝트의 overrides를 덮어쓴 최종 설정."""
        return load_config(self.project().overrides)

    def set_override(self, dotted_key: str, value) -> AppConfig:
        """프로젝트 설정 하나를 바꾼다. 결과가 올바르지 않으면 저장하지 않고 오류를 낸다."""
        project = self.project()
        overrides = set_dotted(project.overrides, dotted_key, value)
        if dotted_key.split(".")[0] not in raw_config():
            raise WorkspaceError(f"'{dotted_key}'는 없는 설정입니다.")
        cfg = load_config(overrides)  # 검증 (실패하면 ValidationError)
        self._write_project(project.model_copy(update={"overrides": overrides}))
        return cfg

    # ---- 단계 상태 -----------------------------------------------------------

    @property
    def state_file(self) -> Path:
        return self.path / "state.json"

    def _state(self) -> dict:
        if not self.state_file.is_file():
            return {}
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def _save_state(self, state: dict) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def _paths(self, patterns: tuple[str, ...]) -> list[Path] | None:
        files: list[Path] = []
        for pattern in patterns:
            matches = sorted(self.path.glob(pattern))
            if not matches:
                return None
            for m in matches:
                files.extend(sorted(p for p in m.rglob("*") if p.is_file()) if m.is_dir() else [m])
        return files

    def output_paths(self, stage: str) -> list[Path] | None:
        """단계 산출물 파일 목록. 하나라도 없으면 None."""
        return self._paths(STAGES[stage].outputs)

    def output_hash(self, stage: str) -> str | None:
        return self._files_hash(self.output_paths(stage))

    def _files_hash(self, files: list[Path] | None) -> str | None:
        if files is None:
            return None
        h = hashlib.sha256()
        for f in files:
            h.update(f.relative_to(self.path).as_posix().encode())
            h.update(_file_fingerprint(f).encode())
        return h.hexdigest()

    def input_hash(self, stage: str, cfg: AppConfig | None = None) -> str:
        cfg = cfg or self.config()
        dumped = cfg.model_dump(mode="json")
        payload = {
            "config": {k: dumped[k] for k in STAGES[stage].config_keys},
            "upstream": {u: self.output_hash(u) for u in STAGES[stage].upstream},
        }
        if STAGES[stage].inputs:
            payload["inputs"] = self._files_hash(self._paths(STAGES[stage].inputs))
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def status(self, stage: str, cfg: AppConfig | None = None) -> str:
        """done(완료) | stale(입력이 바뀌어 다시 실행 필요) | pending(아직 안 함)"""
        record = self._state().get(stage)
        if not record or self.output_paths(stage) is None:
            return "pending"
        return "done" if record["input_hash"] == self.input_hash(stage, cfg) else "stale"

    def statuses(self) -> dict[str, str]:
        cfg = self.config()
        return {name: self.status(name, cfg) for name in ORDER}

    def mark_done(self, stage: str) -> None:
        if self.output_paths(stage) is None:
            raise WorkspaceError(f"'{STAGES[stage].title}' 단계의 결과 파일이 없어 완료로 기록할 수 없습니다.")
        state = self._state()
        state[stage] = {
            "input_hash": self.input_hash(stage),
            "output_hash": self.output_hash(stage),
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_state(state)

    def pending_stages(self) -> list[str]:
        """다시 실행해야 하는 단계 (실행 순서대로). 앞 단계가 다시 돌면 그 아래도 포함한다.

        한 번도 돌지 않은 앞 단계(예: 로컬 영상·직접 쓴 대본으로 건너뛴 수집·분석)는 아래 단계를 끌어들이지 않는다.
        """
        statuses, state = self.statuses(), self._state()
        todo: list[str] = []
        rerun: set[str] = set()  # 이전 결과가 있는데 다시 돌아서 결과가 바뀔 단계
        for name in ORDER:
            cascaded = any(u in rerun for u in STAGES[name].upstream)
            if statuses[name] != "done" or cascaded:
                todo.append(name)
            if cascaded or statuses[name] == "stale" or (statuses[name] == "pending" and name in state):
                rerun.add(name)
        return todo

    # ---- 버전 ---------------------------------------------------------------

    def versions(self) -> list[int]:
        found = [int(p.name[1:]) for p in (self.path / "versions").glob("v*") if p.name[1:].isdigit()]
        return sorted(found)

    def snapshot(self) -> int:
        """현재 결과물을 versions/v{n}/에 보관하고 n을 돌려준다."""
        n = (self.versions() or [0])[-1] + 1
        dest = self.path / "versions" / f"v{n}"
        dest.mkdir(parents=True)
        for pattern in VERSIONED:
            for f in self.path.glob(pattern):
                if f.is_file():
                    shutil.copy2(f, dest / f.name)
        return n

    def rollback(self, n: int) -> None:
        """v{n} 결과물로 되돌린다. 되돌리기 전 상태도 새 버전으로 남긴다."""
        src = self.path / "versions" / f"v{n}"
        if not src.is_dir():
            raise WorkspaceError(f"버전 v{n}이 없습니다. 있는 버전: {self.versions() or '없음'}")
        self.snapshot()
        for pattern in VERSIONED:  # v{n} 이후에 새로 생긴 결과물은 지운다
            for f in self.path.glob(pattern):
                if f.is_file() and not (src / f.name).exists():
                    f.unlink()
        for f in src.iterdir():
            shutil.copy2(f, self.path / f.name)


def list_projects(root: Path | None = None) -> list[Workspace]:
    """만든 순서(이름 순)대로 정렬한 프로젝트 목록."""
    root = root or workspace_root()
    return [Workspace(p) for p in sorted(root.iterdir()) if (p / "project.yaml").is_file()]


def import_local_videos(ws: Workspace, files: list[Path]) -> list[Path]:
    """직접 받아둔 영상 파일을 raw_videos/01.mp4, 02.mp4 … 로 복사한다."""
    copied = []
    dest_dir = ws.path / "raw_videos"
    start = len(list(dest_dir.glob("*"))) + 1
    for i, src in enumerate(files, start=start):
        if not src.is_file():
            raise WorkspaceError(f"파일을 찾을 수 없습니다: {src}")
        dest = dest_dir / f"{i:02d}{src.suffix.lower() or '.mp4'}"
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied
