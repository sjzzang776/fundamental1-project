"""AI Hub 노인 음성 데이터를 내 컴퓨터(한국 IP)에서 받아 Colab 학습용으로 줄여 담는 스크립트.

AI Hub는 해외 IP(Colab 포함)에서 다운로드를 막기 때문에, 다운로드와 정리는 내 컴퓨터에서 하고
결과(FLAC zip + manifest.csv)만 Google Drive에 올려 Colab에서 학습한다.

실행 (Docker, 저장소 루트에서):
  docker run --rm -it --env-file ../aihub.env -v "<데이터폴더>:/data" -v "$PWD/model/scripts:/scripts:ro" \
      aihub-prep python /scripts/prepare_aihub.py <명령> ...

명령
  download <이름> <datasetkey> <filekey...>   zip 받기 → /data/raw/<이름>/
  inspect  <이름>                             라벨 JSON 예시·정답 문장 칸·짝 맞춤 결과 보기
  build    <이름> --train-hours 60 --valid-n 1000
                                              음성을 골라 16kHz FLAC zip 으로 담기 → /data/upload/
"""

import argparse
import io
import json
import os
import random
import re
import subprocess
import sys
import tarfile
import zipfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import soundfile as sf

DATA = "/data"
AUDIO_EXTS = (".wav", ".pcm")
HANGUL = re.compile("[가-힣]")
TEXT_KEY_HINTS = ["stt", "전사", "transcript", "text", "발화", "script", "sentence", "문장"]
MAX_SECONDS = 30
SHARD_BYTES = 1_500_000_000  # FLAC zip 하나당 약 1.5GB


# ---------- 다운로드 ----------
def download(name, datasetkey, filekeys):
    key = os.environ.get("AIHUB_APIKEY", "")
    if not key or key == "여기에-입력":
        sys.exit("🔒 aihub.env 의 AIHUB_APIKEY 를 채워 주세요.")
    out = f"{DATA}/raw/{name}"
    os.makedirs(out, exist_ok=True)
    for fk in filekeys:
        done = f"{out}/.done_{fk}"
        if os.path.exists(done):
            print(f"✅ {fk}: 이미 받음")
            continue
        tar_path = f"{out}/download_{fk}.tar"
        print(f"⬇️ {name} filekey {fk} 받는 중...", flush=True)
        r = subprocess.run(
            ["curl", "-L", "-C", "-", "--fail-with-body", "-o", tar_path, "-H", f"apikey:{key}",
             "-w", "%{http_code}", "--progress-bar",
             f"https://api.aihub.or.kr/down/0.6/{datasetkey}.do?fileSn={fk}"],
            stdout=subprocess.PIPE, text=True,
        )
        if r.returncode != 0:
            msg = open(tar_path, "rb").read(500).decode("utf-8", "replace") if os.path.exists(tar_path) else ""
            sys.exit(f"❌ 다운로드 실패 (HTTP {r.stdout.strip()}): {msg}")
        with tarfile.open(tar_path) as t:
            t.extractall(out, filter="data")
        os.remove(tar_path)
        merge_parts(out)
        open(done, "w").close()
        print(f"✅ {fk}: 완료", flush=True)
    for z in sorted(zips(name)):
        print(f"  {os.path.getsize(z) / 1e9:6.2f}GB  {os.path.relpath(z, out)}")


def merge_parts(root):
    """AI Hub 는 큰 파일을 xxx.zip.part0, part1... 로 나눠 보낸다 → 하나로 합친다."""
    for d, _, files in os.walk(root):
        groups = {}
        for f in files:
            m = re.match(r"(.+)\.part(\d+)$", f)
            if m:
                groups.setdefault(m.group(1), []).append((int(m.group(2)), f))
        for target, parts in groups.items():
            with open(os.path.join(d, target), "wb") as w:
                for _, f in sorted(parts):
                    with open(os.path.join(d, f), "rb") as p:
                        while chunk := p.read(64 << 20):
                            w.write(chunk)
            for _, f in parts:
                os.remove(os.path.join(d, f))


# ---------- 라벨 읽기 ----------
def zips(name):
    out = []
    for d, _, files in os.walk(f"{DATA}/raw/{name}"):
        out += [os.path.join(d, f) for f in files if f.lower().endswith(".zip")]
    return out


def fix_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except Exception:
        return info.filename


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, path + (i,))
    else:
        yield path, obj


def get_path(obj, path):
    for p in path:
        obj = obj[p]
    return obj


def key_rank(path):
    names = [str(p).lower() for p in path if not isinstance(p, int)]
    last = names[-1] if names else ""
    for i, h in enumerate(TEXT_KEY_HINTS):
        if h in last:
            return i
    return len(TEXT_KEY_HINTS)


def detect_text_path(samples):
    counter = Counter()
    for obj in samples:
        for path, v in walk(obj):
            if isinstance(v, str) and HANGUL.search(v) and not v.lower().endswith(AUDIO_EXTS):
                counter[path] += 1
    ranked = sorted(counter, key=lambda p: (key_rank(p), -counter[p]))
    return (ranked[0] if ranked else None), ranked[:8]


def audio_name_in_json(obj):
    for _, v in walk(obj):
        if isinstance(v, str) and v.lower().endswith(AUDIO_EXTS):
            return stem(v)
    return None


def clean_text(t):
    """정답 문장 정리. 쓰지 않을 문장은 빈 문자열을 돌려준다.

    자유대화(노인남여) 표시: (FP:뭐) 군말, (SN:..)/(NO:..) 잡음 구간 → 말은 남김,
    (SP:..) 발음 불분명 → 받아 적기가 확실하지 않아 문장째 뺌.
    """
    if re.search(r"\(SP:", t):
        return ""
    t = re.sub(r"\((?:FP|SN|NO):([^()]*)\)", r" \1 ", t)
    t = re.sub(r"\(([^()]*)\)\s*/\s*\(([^()]*)\)", r"\1", t)  # (철자)/(발음) → 철자 쪽
    t = re.sub(r"(?<![A-Za-z])[A-Za-z]{1,2}/", " ", t)          # b/ n/ l/ o/ 잡음 표시
    t = re.sub(r"[\[{<][^\]}>]*[\]}>]", " ", t)                # [잡음] {웃음} <...>
    t = re.sub(r"[()*+/&#@~]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if re.search(r"[^가-힣A-Za-z0-9\s.,?!'\-]", t):  # 낱자모(ㅏ, ㄱ)·이상한 기호가 남은 문장
        return ""
    return t


def split_of(path):
    p = path.lower()
    return "valid" if "validation" in p else "train" if "training" in p else "unknown"


def read_labels(name):
    labels = []
    for zp in zips(name):
        if "라벨" not in os.path.basename(zp):
            continue
        with zipfile.ZipFile(zp) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(".json"):
                    try:
                        labels.append((split_of(zp), fix_name(info), json.loads(z.read(info).decode("utf-8-sig"))))
                    except Exception:
                        pass
    return labels


def index_audio(name):
    idx = {}
    for zp in zips(name):
        if "라벨" in os.path.basename(zp):
            continue
        with zipfile.ZipFile(zp) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(AUDIO_EXTS):
                    idx[stem(fix_name(info))] = (zp, info.filename, info.file_size)
    return idx


def matched_rows(name, text_path=None, verbose=True):
    labels = read_labels(name)
    if not labels:
        sys.exit("❌ 라벨 zip/JSON 을 찾지 못했습니다.")
    if text_path is None:
        sample = [o for _, _, o in random.Random(0).sample(labels, min(300, len(labels)))]
        text_path, cands = detect_text_path(sample)
        if verbose:
            print("정답 문장 칸 후보:", [" → ".join(map(str, c)) for c in cands])
    if verbose:
        print("✅ 사용할 칸:", " → ".join(map(str, text_path)))
    audio = index_audio(name)
    rows, no_audio, no_text = [], 0, 0
    bps = {}
    for split, jname, obj in labels:
        try:
            raw = get_path(obj, text_path)
        except (KeyError, IndexError, TypeError):
            no_text += 1
            continue
        a = audio.get(stem(jname)) or audio.get(audio_name_in_json(obj) or "")
        if a is None:
            no_audio += 1
            continue
        text = clean_text(str(raw))
        if not text:
            no_text += 1
            continue
        zp, member, size = a
        if zp not in bps:
            bps[zp] = bytes_per_sec(zp, member)
        rows.append({"dataset": name, "split": split_of(zp), "src_zip": zp, "src_member": member,
                     "seconds": round(size / bps[zp], 2), "raw_text": str(raw), "text": text})
    df = pd.DataFrame(rows)
    if verbose:
        print(f"라벨 {len(labels):,}개 · 음성 {len(audio):,}개 · 짝 맞춤 {len(df):,}개 "
              f"(음성 없음 {no_audio:,} = 받지 않은 묶음이면 정상, 문장 없음 {no_text:,})")
    return df, text_path


def bytes_per_sec(zp, member):
    if member.lower().endswith(".pcm"):
        return 16000 * 2
    with zipfile.ZipFile(zp) as z:
        info = sf.info(io.BytesIO(z.read(member)))
    return info.samplerate * info.channels * 2


# ---------- 명령 ----------
def inspect(name):
    labels = read_labels(name)
    print(f"[{name}] 라벨 JSON {len(labels):,}개")
    for split in ["train", "valid"]:
        ex = next((x for x in labels if x[0] == split), None)
        if ex:
            print(f"\n▼ 라벨 예시 ({split}) {ex[1]}")
            print(json.dumps(ex[2], ensure_ascii=False, indent=1)[:2000])
    df, _ = matched_rows(name)
    if df.empty:
        return
    print("\n음성 형식:", end=" ")
    zp, member = df.iloc[0][["src_zip", "src_member"]]
    with zipfile.ZipFile(zp) as z:
        info = sf.info(io.BytesIO(z.read(member)))
    print(f"{info.samplerate}Hz, {info.channels}채널, {info.subtype}")
    print("\n=== 시간 ===")
    print(df.groupby("split")["seconds"].agg(["count", "mean", "max"]).assign(
        hours=df.groupby("split")["seconds"].sum() / 3600).round(2))
    print(f"\n{MAX_SECONDS}초 넘는 음성: {(df.seconds > MAX_SECONDS).sum():,}개")
    print("\n=== 정리 전 → 후 예시 ===")
    for _, r in df.sample(min(15, len(df)), random_state=0).iterrows():
        print(f"[{r.split}] {r.raw_text}\n     → {r.text}")


_zcache = {}


def to_flac(args):
    zp, member = args
    if zp not in _zcache:  # 큰 zip 은 여는 데 오래 걸려서 작업 프로세스마다 한 번만 연다
        _zcache[zp] = zipfile.ZipFile(zp)
    data = _zcache[zp].read(member)
    if member.lower().endswith(".pcm"):
        audio, sr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768, 16000
    else:
        audio, sr = sf.read(io.BytesIO(data), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
    if sr != 16000:
        import soxr
        audio = soxr.resample(audio, sr, 16000)
    buf = io.BytesIO()
    sf.write(buf, audio, 16000, format="FLAC", subtype="PCM_16")
    return buf.getvalue()


def build(name, train_hours, valid_n, seed, run, splits=("train", "valid")):
    df, _ = matched_rows(name)
    df = df[(df.seconds > 0.3) & (df.seconds <= MAX_SECONDS)]
    train = df[df.split == "train"].sample(frac=1, random_state=seed)
    train = train[train.seconds.cumsum() <= train_hours * 3600]
    valid = df[df.split == "valid"].sample(min(valid_n, (df.split == "valid").sum()), random_state=seed)
    picked = pd.concat([p for s, p in [("train", train), ("valid", valid)] if s in splits], ignore_index=True)
    if picked.empty:
        sys.exit(f"❌ {name} {splits}: 고를 음성이 없습니다 (아직 다운로드 중인지 확인)")
    print(f"고른 음성: 학습 {len(train):,}개 ({train.seconds.sum() / 3600:.1f}시간) · 검증 {len(valid):,}개")

    out_dir = f"{DATA}/upload/{run}"
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for split, part in picked.groupby("split"):
        shard, shard_bytes, zf = 0, 0, None
        jobs = list(zip(part.src_zip, part.src_member))
        with ProcessPoolExecutor(max(1, os.cpu_count() - 1)) as ex:
            for i, (flac, (_, r)) in enumerate(zip(ex.map(to_flac, jobs, chunksize=32), part.iterrows())):
                if zf is None or shard_bytes > SHARD_BYTES:
                    if zf:
                        zf.close()
                    shard += 1
                    shard_name = f"{name}_{split}_{shard:02d}.zip"
                    zf = zipfile.ZipFile(f"{out_dir}/{shard_name}", "w", zipfile.ZIP_STORED)
                    shard_bytes = 0
                member = f"{name}/{split}/{i:07d}.flac"
                zf.writestr(member, flac)
                shard_bytes += len(flac)
                rows.append({"dataset": name, "split": split, "zip": shard_name, "member": member,
                             "seconds": r.seconds, "text": r.text})
                if (i + 1) % 5000 == 0:
                    print(f"  {split}: {i + 1:,}/{len(part):,}", flush=True)
        if zf:
            zf.close()

    manifest = f"{out_dir}/manifest.csv"
    new = pd.DataFrame(rows)
    if os.path.exists(manifest):  # 이번에 정리한 (데이터셋, 학습/검증) 줄만 바꾼다
        old = pd.read_csv(manifest)
        keep = ~((old.dataset == name) & old.split.isin(list(splits)))
        new = pd.concat([old[keep], new], ignore_index=True)
    new.to_csv(manifest, index=False)
    total = sum(os.path.getsize(f"{out_dir}/{f}") for f in os.listdir(out_dir))
    print(f"✅ {out_dir} 에 저장 (폴더 전체 {total / 1e9:.2f}GB)")
    print(new.groupby(["dataset", "split"])["seconds"].agg(["count", "sum"]).assign(
        hours=lambda d: (d["sum"] / 3600).round(1)).drop(columns="sum"))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download")
    d.add_argument("name")
    d.add_argument("datasetkey")
    d.add_argument("filekeys", nargs="+")
    i = sub.add_parser("inspect")
    i.add_argument("name")
    b = sub.add_parser("build")
    b.add_argument("name")
    b.add_argument("--train-hours", type=float, required=True)
    b.add_argument("--valid-n", type=int, default=1000)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--run", default="whisper-small-elderly-v1")
    b.add_argument("--split", choices=["train", "valid", "all"], default="all",
                   help="학습용만/검증용만 정리 (다운로드가 덜 끝났을 때)")
    a = ap.parse_args()
    if a.cmd == "download":
        download(a.name, a.datasetkey, a.filekeys)
    elif a.cmd == "inspect":
        inspect(a.name)
    else:
        build(a.name, a.train_hours, a.valid_n, a.seed, a.run,
              ("train", "valid") if a.split == "all" else (a.split,))


if __name__ == "__main__":
    main()
