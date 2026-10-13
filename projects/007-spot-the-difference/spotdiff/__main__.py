"""명령줄 실행: python -m spotdiff

예)
  python -m spotdiff                         # 코드로 그린 그림 3문제 (쉬움→어려움)
  python -m spotdiff --puzzles 2 --seed 7    # 다른 그림으로 2문제
  python -m spotdiff --image my1.png --image my2.png   # 내 그림으로 문제 만들기
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from .photo import load_image, make_puzzle_from_image
from .scene import make_puzzle
from .video import VideoConfig, answer_image, render_video


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="spotdiff", description="틀린그림 찾기 쇼츠 MP4 만들기")
    ap.add_argument("--out", default="out", help="결과 폴더 (기본: out)")
    ap.add_argument("--puzzles", type=int, default=3, help="문제 수 (기본 3, --image를 쓰면 무시)")
    ap.add_argument("--seed", type=int, default=None, help="같은 값이면 같은 그림이 나온다 (기본: 무작위)")
    ap.add_argument("--time", type=float, default=8.0, help="문제당 제한 시간(초), 기본 8")
    ap.add_argument("--level", type=int, choices=[0, 1, 2], default=None,
                    help="난이도 고정 (0 쉬움 3곳, 1 보통 4곳, 2 어려움 5곳). 기본: 문제마다 점점 어렵게")
    ap.add_argument("--image", action="append", default=[], help="내 그림 파일 (여러 번 지정 가능, 문제 하나씩)")
    ap.add_argument("--font", default=None, help="한글 글꼴 .ttf/.ttc 경로 (기본: 자동 탐색)")
    ap.add_argument("--no-video", action="store_true", help="MP4 없이 그림과 정답만 만든다")
    args = ap.parse_args(argv)

    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    count = len(args.image) or args.puzzles
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    puzzles, meta = [], []
    for i in range(count):
        level = args.level if args.level is not None else min(i, 2)
        if args.image:
            p = make_puzzle_from_image(load_image(args.image[i]), seed + i, level)
            source = args.image[i]
        else:
            p = make_puzzle(seed + i, level)
            source = "scene"
        n = i + 1
        p.image_a.save(out / f"puzzle{n}_a.png")
        p.image_b.save(out / f"puzzle{n}_b.png")
        answer_image(p).save(out / f"puzzle{n}_answer.png")
        puzzles.append(p)
        meta.append({"puzzle": n, "source": source, "seed": seed + i, "level": level,
                     "differences": [d.to_dict() for d in p.differences]})
        print(f"문제 {n}: 틀린 곳 {len(p.differences)}개 ({', '.join(d.type + ':' + d.kind for d in p.differences)})")

    (out / "puzzles.json").write_text(json.dumps({"seed": seed, "time_sec": args.time, "puzzles": meta},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    if args.no_video:
        print(f"완료: {out.resolve()}")
        return 0

    t = time.time()
    mp4 = render_video(puzzles, out / "shorts.mp4", VideoConfig(time_sec=args.time, font=args.font))
    print(f"완료: {mp4.resolve()} ({time.time() - t:.0f}초 걸림, seed={seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
