"""
DICOM → NIfTI 一键转换脚本
双击运行即可，会自动安装所需依赖库
"""

# ══════════════════════════════════════════════════════
#  第一步：自动检测并安装依赖（无需手动 pip install）
# ══════════════════════════════════════════════════════
import sys
import subprocess

REQUIRED = ["dicom2nifti", "pydicom"]

def install_if_missing(packages):
    import importlib
    pkg_map = {"dicom2nifti": "dicom2nifti", "pydicom": "pydicom"}
    missing = []
    for pkg in packages:
        try:
            importlib.import_module(pkg_map.get(pkg, pkg))
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"检测到缺少依赖库：{missing}")
        print("正在自动安装，请稍候...\n")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        print("✅ 依赖安装完成，开始转换...\n")
    else:
        print("✅ 依赖检测通过，开始转换...\n")

install_if_missing(REQUIRED)

# ══════════════════════════════════════════════════════
#  第二步：正式转换逻辑（依赖已就绪后才导入）
# ══════════════════════════════════════════════════════
import os
import csv
import gzip
import shutil
import pathlib
import logging
import tempfile
import datetime

import dicom2nifti
import dicom2nifti.settings as d2n_settings


# ── 路径配置（已根据截图写死，无需修改）─────────────────────────
CSV_PATH   = r"D:\Slicer_External_Data\DICOM\metadata\metadata.csv"
OUTPUT_DIR = r"D:\Slicer_External_Data\NIFTI_Output"
OVERWRITE  = False   # True = 重新转换已存在的文件


# ── 日志配置 ──────────────────────────────────────────────────────
def setup_logger(output_dir: pathlib.Path) -> logging.Logger:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"转换日志_{ts}.txt"
    logger = logging.getLogger("convert")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s",
                            datefmt="%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


# ── 读取任务 ──────────────────────────────────────────────────────
def load_tasks(csv_path: pathlib.Path) -> list:
    if not csv_path.exists():
        print(f"\n❌ 找不到 CSV 文件：{csv_path}")
        print("   请确认 metadata.csv 在：")
        print("   D:\\Slicer_External_Data\\DICOM\\metadata\\")
        input("\n按回车键退出...")
        sys.exit(1)

    tasks = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid      = row.get("PatientID", "").strip()
            raw_path = row.get("S5cmdManifestPath", "").strip()
            size     = row.get("FileSize", "0").strip()
            if pid and raw_path:
                tasks.append({
                    "patient_id": pid,
                    "dicom_path": pathlib.Path(raw_path),
                    "size_bytes": int(size) if size.isdigit() else 0,
                })

    tasks.sort(key=lambda x: x["patient_id"])
    return tasks


# ── 单序列转换 ────────────────────────────────────────────────────
def convert_one(dicom_dir: pathlib.Path,
                output_dir: pathlib.Path,
                patient_id: str,
                logger: logging.Logger) -> tuple:
    final = output_dir / f"{patient_id}.nii.gz"

    if not dicom_dir.exists():
        return False, f"路径不存在: {dicom_dir}"

    try:
        n_files = sum(1 for f in dicom_dir.iterdir() if f.is_file())
    except PermissionError as e:
        return False, f"权限不足: {e}"

    if n_files == 0:
        return False, "文件夹为空"

    with tempfile.TemporaryDirectory(prefix="d2n_") as tmp:
        tmp_path = pathlib.Path(tmp)
        try:
            dicom2nifti.convert_directory(
                str(dicom_dir), str(tmp_path),
                compression=True, reorient=True
            )
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

        nii_gz = list(tmp_path.glob("*.nii.gz"))

        if not nii_gz:
            nii = list(tmp_path.glob("*.nii"))
            if not nii:
                return False, "未找到输出文件"
            logger.debug("  .nii → gzip 压缩中...")
            gz = tmp_path / (nii[0].stem + ".nii.gz")
            with open(nii[0], "rb") as fi, gzip.open(gz, "wb") as fo:
                shutil.copyfileobj(fi, fo)
            nii_gz = [gz]

        if len(nii_gz) > 1:
            nii_gz.sort(key=lambda f: f.stat().st_size, reverse=True)

        shutil.move(str(nii_gz[0]), str(final))

    return True, ""


# ── 主程序 ────────────────────────────────────────────────────────
def main():
    output_dir = pathlib.Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(output_dir)

    d2n_settings.disable_validate_slice_increment()

    logger.info("=" * 62)
    logger.info("  DICOM → NIfTI 批量转换  |  StageII-Colorectal-CT")
    logger.info("=" * 62)
    logger.info(f"  CSV   : {CSV_PATH}")
    logger.info(f"  输出  : {OUTPUT_DIR}")
    logger.info("=" * 62)

    tasks = load_tasks(pathlib.Path(CSV_PATH))
    total = len(tasks)
    logger.info(f"读取到 {total} 个 case\n")

    # 预检
    done, miss, todo = [], [], []
    for t in tasks:
        out = output_dir / f"{t['patient_id']}.nii.gz"
        if out.exists() and not OVERWRITE:
            done.append(t)
        elif not t["dicom_path"].exists():
            miss.append(t)
        else:
            todo.append(t)

    logger.info(f"预检 → 已完成: {len(done)}  待转换: {len(todo)}  路径缺失: {len(miss)}")
    if miss:
        for t in miss:
            logger.warning(f"  ⚠️  {t['patient_id']}")
    if not todo:
        logger.info("\n✅ 全部已转换，无需重复处理。")
        input("\n按回车键退出...")
        return

    logger.info("")

    # 转换主循环
    report_rows = []
    success, fail = 0, 0
    start = datetime.datetime.now()

    for idx, t in enumerate(todo, 1):
        pid     = t["patient_id"]
        size_mb = t["size_bytes"] / 1024 ** 2
        elapsed = (datetime.datetime.now() - start).total_seconds()
        eta_s   = (elapsed / idx * (len(todo) - idx)) if idx > 1 else 0
        eta_str = f"{int(eta_s//60)}分{int(eta_s%60):02d}秒剩余" if eta_s else "计算中..."

        logger.info(f"[{idx:>3}/{len(todo)}]  {pid}  ({size_mb:.1f}MB)  {eta_str}")

        ok, err = convert_one(t["dicom_path"], output_dir, pid, logger)

        if ok:
            out_mb = (output_dir / f"{pid}.nii.gz").stat().st_size / 1024 ** 2
            logger.info(f"         ✅  {pid}.nii.gz  ({out_mb:.1f}MB)")
            success += 1
        else:
            logger.error(f"         ❌  {err}")
            fail += 1

        report_rows.append({
            "PatientID": pid,
            "状态":      "成功" if ok else "失败",
            "原始MB":    f"{size_mb:.1f}",
            "输出MB":    f"{(output_dir/f'{pid}.nii.gz').stat().st_size/1024**2:.1f}" if ok else "",
            "错误信息":  "" if ok else err,
        })

    # 写报告
    report_path = output_dir / "转换报告.csv"
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["PatientID","状态","原始MB","输出MB","错误信息"])
        w.writeheader()
        w.writerows(report_rows)

    # 汇总
    elapsed_total = (datetime.datetime.now() - start).total_seconds()
    total_gb = sum(
        (output_dir / f"{t['patient_id']}.nii.gz").stat().st_size
        for t in todo
        if (output_dir / f"{t['patient_id']}.nii.gz").exists()
    ) / 1024 ** 3

    logger.info(f"\n{'='*62}")
    logger.info(f"  转换完成！")
    logger.info(f"  ✅ 成功 : {success + len(done)}/{total}（含已跳过 {len(done)} 个）")
    logger.info(f"  ❌ 失败 : {fail} 个")
    logger.info(f"  💾 输出 : {total_gb:.2f} GB")
    logger.info(f"  ⏱  耗时 : {int(elapsed_total//60)}分{int(elapsed_total%60):02d}秒")
    logger.info(f"  📄 报告 : {report_path}")
    logger.info(f"{'='*62}")

    input("\n全部完成，按回车键退出...")


if __name__ == "__main__":
    main()
