#!/usr/bin/env python3
"""
Split Video 5 menit + Remove Watermark + Preserve Audio
"""

import cv2
import numpy as np
import os
import sys
import argparse
import time
import subprocess
import tempfile
import glob
import shutil
from datetime import datetime


def get_video_duration(video_path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error',
             '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             video_path],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except:
        return 0


def has_audio(video_path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error',
             '-select_streams', 'a:0',
             '-show_entries', 'stream=codec_type',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             video_path],
            capture_output=True, text=True, timeout=10
        )
        return 'audio' in result.stdout.lower()
    except:
        return False


def split_video(input_path, output_dir, part_duration=300):
    os.makedirs(output_dir, exist_ok=True)

    total_duration = get_video_duration(input_path)

    if total_duration == 0:
        print("[!] Cannot get video duration")
        return []

    num_parts = int(np.ceil(total_duration / part_duration))

    print(f"[*] Total duration: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    print(f"[*] Part duration: {part_duration}s ({part_duration/60:.1f} min)")
    print(f"[*] Will split into {num_parts} parts")

    input_name = os.path.splitext(os.path.basename(input_path))[0]
    input_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in input_name)

    parts = []

    for i in range(num_parts):
        start_time = i * part_duration
        part_num = i + 1

        output_path = os.path.join(output_dir, f"part_{part_num:03d}.mp4")

        print(f"\n  Part {part_num}/{num_parts}: start={start_time}s")

        cmd = [
            'ffmpeg',
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(part_duration),
            '-c', 'copy',
            '-map', '0',
            '-avoid_negative_ts', 'make_zero',
            output_path,
            '-y',
            '-loglevel', 'error'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            parts.append(output_path)
            print(f"    OK: {size_mb:.1f} MB")
        else:
            print(f"    FAILED: {result.stderr[:200]}")

    return parts


def detect_watermark(video_path, sample_count=20):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames < 2:
        cap.release()
        return []

    step = max(1, total_frames // sample_count)

    frames = []
    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
        if len(frames) >= sample_count:
            break
    cap.release()

    if len(frames) < 2:
        return []

    h, w = frames[0].shape[:2]

    gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    stacked = np.stack(gray_frames, axis=0)
    variance = np.var(stacked, axis=0)

    static_mask = (variance < 50).astype(np.uint8) * 255

    kernel = np.ones((15, 15), np.uint8)
    static_mask = cv2.dilate(static_mask, kernel, iterations=2)

    contours, _ = cv2.findContours(static_mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    watermarks = []
    min_area = 200
    max_area = w * h * 0.2

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, cw, ch = cv2.boundingRect(cnt)
            watermarks.append({
                'bbox': (x, y, x + cw, y + ch),
                'area': area
            })

    if not watermarks:
        corner_size = min(w, h) // 4
        corners = [
            (0, 0, corner_size, corner_size),
            (w - corner_size, 0, w, corner_size),
            (0, h - corner_size, corner_size, h),
            (w - corner_size, h - corner_size, w, h)
        ]

        for (x1, y1, x2, y2) in corners:
            region = static_mask[y1:y2, x1:x2]
            count = cv2.countNonZero(region)
            if count > 500:
                watermarks.append({
                    'bbox': (x1, y1, x2, y2),
                    'area': count
                })

    return watermarks


def remove_watermark_from_part(part_path, output_path, watermarks, method='blur'):
    cap = cv2.VideoCapture(part_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    temp_video = tempfile.mktemp(suffix='_noaudio.mp4')

    mask = np.zeros((height, width), dtype=np.uint8)
    for wm in watermarks:
        x1, y1, x2, y2 = wm['bbox']
        mask[y1:y2, x1:x2] = 255

    kernel = np.ones((10, 10), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    cap = cv2.VideoCapture(part_path)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if method == 'blur':
            for wm in watermarks:
                x1, y1, x2, y2 = wm['bbox']
                roi = frame[y1:y2, x1:x2]
                if roi.size > 0:
                    blurred = cv2.GaussianBlur(roi, (25, 25), 0)
                    frame[y1:y2, x1:x2] = blurred
            result = frame
        elif method == 'inpaint_fast':
            result = cv2.inpaint(frame, mask, 2, cv2.INPAINT_TELEA)
        elif method == 'median':
            for wm in watermarks:
                x1, y1, x2, y2 = wm['bbox']
                roi = frame[y1:y2, x1:x2]
                if roi.size > 0:
                    median = cv2.medianBlur(roi, 21)
                    frame[y1:y2, x1:x2] = median
            result = frame
        else:
            result = cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)

        out.write(result)
        frame_count += 1

        if frame_count % 500 == 0:
            elapsed = time.time() - start_time
            progress = frame_count / total_frames * 100
            eta = (elapsed / frame_count) * (total_frames - frame_count) if frame_count > 0 else 0
            print(f"      [{frame_count}/{total_frames}] {progress:.1f}% - ETA: {eta:.0f}s")

    cap.release()
    out.release()

    if has_audio(part_path):
        print(f"    [*] Merging audio...")

        cmd = [
            'ffmpeg',
            '-i', temp_video,
            '-i', part_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-map', '0:v:0',
            '-map', '1:a:0?',
            '-shortest',
            '-movflags', '+faststart',
            output_path,
            '-y',
            '-loglevel', 'error'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if os.path.exists(temp_video):
            os.remove(temp_video)

        if result.returncode != 0:
            print(f"    [!] Audio merge failed, using video only")
            if os.path.exists(temp_video):
                shutil.move(temp_video, output_path)
    else:
        shutil.move(temp_video, output_path)

    return os.path.exists(output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output-dir', default='output')
    parser.add_argument('--part-duration', type=int, default=300)
    parser.add_argument('--method', default='blur')
    parser.add_argument('--samples', type=int, default=20)
    args = parser.parse_args()

    print("=" * 70)
    print("  SPLIT + REMOVE WATERMARK")
    print("=" * 70)

    os.makedirs(args.output_dir, exist_ok=True)

    print("\n[STEP 1] Splitting video...")
    split_dir = tempfile.mkdtemp(prefix='split_')
    parts = split_video(args.input, split_dir, args.part_duration)

    if not parts:
        print("[!] No parts created")
        return

    print(f"\n[+] Created {len(parts)} parts")

    print("\n[STEP 2] Detecting watermark...")
    watermarks = detect_watermark(parts[0], args.samples)

    if not watermarks:
        print("[!] No watermark detected, copying parts")
        for i, part in enumerate(parts):
            output_path = os.path.join(args.output_dir, os.path.basename(part))
            shutil.copy(part, output_path)
        return

    print(f"[+] Detected {len(watermarks)} watermark(s):")
    for i, wm in enumerate(watermarks, 1):
        print(f"    [{i}] {wm['bbox']}")

    print("\n[STEP 3] Removing watermark from each part...")

    input_name = os.path.splitext(os.path.basename(args.input))[0]
    input_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in input_name)

    for i, part in enumerate(parts, 1):
        print(f"\n  Processing part {i}/{len(parts)}: {os.path.basename(part)}")

        output_path = os.path.join(args.output_dir, f"{input_name}_part{i:03d}_no_wm.mp4")

        success = remove_watermark_from_part(
            part, output_path, watermarks, method=args.method
        )

        if success:
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"    OK: {output_path} ({size_mb:.1f} MB)")

    shutil.rmtree(split_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    print("  COMPLETE!")
    print("=" * 70)


if __name__ == '__main__':
    main()
