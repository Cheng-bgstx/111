#!/usr/bin/env python3
"""
从 fallAndGetUp2_subject2.json 截取「第一次站起」的片段，生成 getUp_once.json。
用法: python3 trim_getup_once.py
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MOTIONS_DIR = os.path.join(PROJECT_ROOT, "public", "examples", "checkpoints", "g1", "motions")
SRC_FILE = os.path.join(MOTIONS_DIR, "fallAndGetUp2_subject2.json")
OUT_FILE = os.path.join(MOTIONS_DIR, "getUp_once.json")

ROOT_Z_STANDING = 0.74
ROOT_Z_LOW = 0.55
STANDING_FRAMES = 40


def main():
    with open(SRC_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    joint_pos = data["joint_pos"]
    root_pos = data["root_pos"]
    root_quat = data["root_quat"]
    n = len(joint_pos)
    assert len(root_pos) == n and len(root_quat) == n

    def z_at(i):
        row = root_pos[i]
        return row[2] if isinstance(row, (list, tuple)) else row

    start_idx = 0
    for i in range(n):
        if z_at(i) < ROOT_Z_LOW:
            start_idx = i
            break

    end_idx = n
    count = 0
    for i in range(start_idx, n):
        if z_at(i) >= ROOT_Z_STANDING:
            count += 1
            if count >= STANDING_FRAMES:
                end_idx = i + 1
                break
        else:
            count = 0

    min_frames = 80
    end_idx = max(end_idx, min_frames)
    end_idx = min(end_idx, n)

    start_idx = min(start_idx, end_idx - 1)
    out = {
        "joint_pos": joint_pos[start_idx:end_idx],
        "root_pos": root_pos[start_idx:end_idx],
        "root_quat": root_quat[start_idx:end_idx],
    }
    num_frames = len(out["joint_pos"])
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(f"Written {num_frames} frames (indices {start_idx}-{end_idx}) to {OUT_FILE}")


if __name__ == "__main__":
    main()
