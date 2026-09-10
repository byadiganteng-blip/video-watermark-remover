#!/usr/bin/env python3
"""
Advanced Video Watermark Remover
- Auto-detect multiple watermarks
- Text & image watermark support
- Multiple removal methods
"""

import cv2
import numpy as np
import os
import sys
import glob
from datetime import datetime
import argparse

class WatermarkRemover:
    def __init__(self, video_path, output_path=None):
        self.video_path = video_path
        self.output_path = output_path or video_path.rsplit('.', 1)[0] + "_no_wm.mp4"
        self.cap = cv2.VideoCapture(video_path)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.cap.release()
        
    def detect_all_watermarks(self, sample_count=50):
        """Detect ALL watermarks (text + image) dengan akurasi tinggi"""
        
        print(f"[*] Analyzing {sample_count} frames untuk deteksi...")
        
        cap = cv2.VideoCapture(self.video_path)
        total = self.total_frames
        step = max(1, total // sample_count)
        
        frames = []
        for i in range(0, total, step):
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
        watermarks = []
        
        # ============================================
        # METODE 1: TEMPORAL VARIANCE (Static Area)
        # ============================================
        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        stacked = np.stack(gray_frames, axis=0)
        variance = np.var(stacked, axis=0)
        
        # Watermark = area yang static (variance rendah)
        static_mask = (variance < 30).astype(np.uint8) * 255
        
        # ============================================
        # METODE 2: EDGE STABILITY
        # ============================================
        edge_frames = []
        for f in frames:
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_frames.append(edges)
        
        edge_stack = np.stack(edge_frames, axis=0)
        edge_variance = np.var(edge_stack, axis=0)
        stable_edges = (edge_variance < 100).astype(np.uint8) * 255
        
        # ============================================
        # METODE 3: BRIGHTNESS (Text watermark biasanya putih)
        # ============================================
        bright_frames = []
        for f in frames:
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            _, bright = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            bright_frames.append(bright)
        
        bright_stack = np.stack(bright_frames, axis=0)
        bright_stable = (np.mean(bright_stack, axis=0) > 200).astype(np.uint8) * 255
        
        # ============================================
        # KOMBINASI: Static + Edge + Bright
        # ============================================
        combined = cv2.bitwise_or(static_mask, stable_edges)
        combined = cv2.bitwise_or(combined, bright_stable)
        
        # ============================================
        # DETEKSI SEMUA REGION (bukan hanya 4 sudut!)
        # ============================================
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours berdasarkan ukuran
        min_area = 100
        max_area = w * h * 0.15  # Maks 15% dari frame
        
        detected = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                x, y, cw, ch = cv2.boundingRect(cnt)
                
                # Filter: aspect ratio wajar untuk watermark
                aspect = cw / ch if ch > 0 else 0
                if 0.1 < aspect < 20:
                    detected.append({
                        'bbox': (x, y, x + cw, y + ch),
                        'area': area,
                        'score': area
                    })
        
        # Jika tidak ada yang terdeteksi via contours, fallback ke corner analysis
        if not detected:
            print("[*] Fallback ke corner analysis...")
            detected = self._corner_analysis(frames, static_mask, bright_stable)
        
        # Sort berdasarkan score
        detected.sort(key=lambda x: x['score'], reverse=True)
        
        # Gabungkan bbox yang overlap
        merged = self._merge_overlapping(detected)
        
        print(f"[+] Terdeteksi {len(merged)} area watermark")
        
        return merged
    
    def _corner_analysis(self, frames, static_mask, bright_mask):
        """Analisis 4 sudut jika contour detection gagal"""
        h, w = frames[0].shape[:2]
        corner_size = min(w, h) // 4
        
        regions = {
            'top-left': (0, 0, corner_size, corner_size),
            'top-right': (w - corner_size, 0, w, corner_size),
            'bottom-left': (0, h - corner_size, corner_size, h),
            'bottom-right': (w - corner_size, h - corner_size, w, h),
            'top-center': (w//3, 0, 2*w//3, corner_size),
            'bottom-center': (w//3, h - corner_size, 2*w//3, h),
        }
        
        detected = []
        for name, (x1, y1, x2, y2) in regions.items():
            region_static = static_mask[y1:y2, x1:x2]
            region_bright = bright_mask[y1:y2, x1:x2]
            
            static_count = cv2.countNonZero(region_static)
            bright_count = cv2.countNonZero(region_bright)
            
            # Threshold: harus ada cukup pixel static DAN bright
            if static_count > 100 or bright_count > 500:
                # Refine bbox berdasarkan bright pixels
                ys, xs = np.where(region_bright > 0)
                if len(xs) > 0:
                    rx1 = x1 + max(0, xs.min() - 20)
                    ry1 = y1 + max(0, ys.min() - 20)
                    rx2 = x1 + min(x2 - x1, xs.max() + 20)
                    ry2 = y1 + min(y2 - y1, ys.max() + 20)
                    
                    detected.append({
                        'bbox': (rx1, ry1, rx2, ry2),
                        'area': (rx2 - rx1) * (ry2 - ry1),
                        'score': static_count + bright_count * 2
                    })
        
        return detected
    
    def _merge_overlapping(self, detections, overlap_threshold=0.3):
        """Gabungkan bbox yang overlap"""
        if not detections:
            return []
        
        merged = []
        used = [False] * len(detections)
        
        for i, det in enumerate(detections):
            if used[i]:
                continue
            
            x1, y1, x2, y2 = det['bbox']
            
            for j in range(i + 1, len(detections)):
                if used[j]:
                    continue
                
                x3, y3, x4, y4 = detections[j]['bbox']
                
                # Cek overlap
                ox1 = max(x1, x3)
                oy1 = max(y1, y3)
                ox2 = min(x2, x4)
                oy2 = min(y2, y4)
                
                if ox1 < ox2 and oy1 < oy2:
                    overlap_area = (ox2 - ox1) * (oy2 - oy1)
                    min_area = min(det['area'], detections[j]['area'])
                    
                    if overlap_area / min_area > overlap_threshold:
                        # Merge bbox
                        x1 = min(x1, x3)
                        y1 = min(y1, y3)
                        x2 = max(x2, x4)
                        y2 = max(y2, y4)
                        used[j] = True
            
            merged.append({
                'bbox': (x1, y1, x2, y2),
                'area': (x2 - x1) * (y2 - y1)
            })
            used[i] = True
        
        return merged
    
    def remove_watermark(self, watermarks, method='inpaint', expand=15):
        """Hapus watermark dengan metode terpilih"""
        
        if not watermarks:
            print("[!] Tidak ada watermark untuk dihapus")
            return False
        
        print(f"[*] Menghapus {len(watermarks)} watermark(s)...")
        print(f"[*] Metode: {method}")
        
        # Buat mask untuk SEMUA watermark
        mask = np.zeros((self.height, self.width), dtype=np.uint8)
        
        for wm in watermarks:
            x1, y1, x2, y2 = wm['bbox']
            # Expand area sedikit
            x1 = max(0, x1 - expand)
            y1 = max(0, y1 - expand)
            x2 = min(self.width, x2 + expand)
            y2 = min(self.height, y2 + expand)
            mask[y1:y2, x1:x2] = 255
            print(f"    Watermark: ({x1}, {y1}) - ({x2}, {y2})")
        
        # Dilate mask untuk coverage lebih baik
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # Proses video
        cap = cv2.VideoCapture(self.video_path)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_path, fourcc, self.fps, 
                              (self.width, self.height))
        
        frame_count = 0
        start_time = datetime.now()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if method == 'inpaint':
                result = cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)
            elif method == 'inpaint_ns':
                result = cv2.inpaint(frame, mask, 5, cv2.INPAINT_NS)
            elif method == 'blur':
                result = cv2.GaussianBlur(frame, (99, 99), 0)
                result = np.where(mask[:, :, np.newaxis] > 0, result, frame)
            elif method == 'median':
                result = cv2.medianBlur(frame, 51)
                result = np.where(mask[:, :, np.newaxis] > 0, result, frame)
            else:
                result = frame
            
            out.write(result)
            frame_count += 1
            
            if frame_count % 500 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = frame_count / self.total_frames * 100
                eta = (elapsed / frame_count) * (self.total_frames - frame_count)
                print(f"    [{frame_count}/{self.total_frames}] {progress:.1f}% - ETA: {eta:.0f}s")
        
        cap.release()
        out.release()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"[+] Selesai! {frame_count} frames dalam {elapsed:.1f}s")
        
        return os.path.exists(self.output_path)
    
    def preview_detection(self, watermarks, preview_path='preview.jpg'):
        """Buat preview deteksi"""
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return None
        
        for wm in watermarks:
            x1, y1, x2, y2 = wm['bbox']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, "WATERMARK", (x1, max(20, y1 - 10)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imwrite(preview_path, frame)
        return preview_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input video path')
    parser.add_argument('--output', help='Output video path')
    parser.add_argument('--method', default='inpaint', 
                       choices=['inpaint', 'inpaint_ns', 'blur', 'median'])
    parser.add_argument('--samples', type=int, default=50)
    args = parser.parse_args()
    
    print("=" * 60)
    print("  ADVANCED VIDEO WATERMARK REMOVER")
    print("=" * 60)
    
    remover = WatermarkRemover(args.input, args.output)
    
    print(f"\n[*] Video: {args.input}")
    print(f"    Resolution: {remover.width}x{remover.height}")
    print(f"    FPS: {remover.fps:.2f}")
    print(f"    Frames: {remover.total_frames}")
    
    # Detect ALL watermarks
    watermarks = remover.detect_all_watermarks(args.samples)
    
    if not watermarks:
        print("[!] Tidak ada watermark terdeteksi!")
        return
    
    print(f"\n[+] Watermarks detected:")
    for i, wm in enumerate(watermarks, 1):
        print(f"    [{i}] BBox: {wm['bbox']} (area: {wm['area']:.0f})")
    
    # Preview
    preview = remover.preview_detection(watermarks)
    if preview:
        print(f"[+] Preview: {preview}")
    
    # Remove
    success = remover.remove_watermark(watermarks, method=args.method)
    
    if success:
        size_mb = os.path.getsize(remover.output_path) / (1024 * 1024)
        print(f"\n[+] Output: {remover.output_path} ({size_mb:.1f} MB)")
    else:
        print("[!] Gagal menghapus watermark")


if __name__ == '__main__':
    main()
