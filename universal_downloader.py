#!/usr/bin/env python3
"""
Universal Video Downloader - Support Multiple Platforms
YouTube, Facebook, Instagram, TikTok, Twitter, dll
"""

import os
import sys
import argparse
import subprocess
from urllib.parse import urlparse


def detect_platform(url):
    """Deteksi platform dari URL"""
    url_lower = url.lower()
    
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'facebook'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    elif 'vimeo.com' in url_lower:
        return 'vimeo'
    elif 'dailymotion.com' in url_lower:
        return 'dailymotion'
    elif 'twitch.tv' in url_lower:
        return 'twitch'
    elif 'github.com' in url_lower or 'githubusercontent.com' in url_lower:
        return 'github'
    else:
        return 'direct'


def download_video(url, output_path):
    """Download video dari URL apapun"""
    
    platform = detect_platform(url)
    print(f"[*] Platform: {platform}")
    print(f"[*] URL: {url}")
    print(f"[*] Output: {output_path}")
    
    # Format output
    output_template = output_path.replace('.mp4', '.%(ext)s')
    
    # Coba yt-dlp (support 1000+ situs)
    cmd = [
        'yt-dlp',
        '--no-warnings',
        '--no-check-certificates',
        '-f', 'best[ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--no-playlist',
        url
    ]
    
    print("[*] Trying yt-dlp...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            # Cari file yang di-download
            import glob
            files = glob.glob(output_path.replace('.mp4', '.*'))
            
            if files:
                actual_file = files[0]
                if actual_file != output_path:
                    os.rename(actual_file, output_path)
                
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"[+] Downloaded: {size_mb:.1f} MB")
                return True
        else:
            print(f"[!] yt-dlp error: {result.stderr[:200]}")
    except Exception as e:
        print(f"[!] yt-dlp exception: {e}")
    
    # Fallback: wget/curl untuk direct download
    print("[*] Trying wget...")
    
    cmd = ['wget', '--timeout=300', '--tries=3', url, '-O', output_path]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"[+] Downloaded: {size_mb:.1f} MB")
            return True
    except Exception as e:
        print(f"[!] wget error: {e}")
    
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True, help='Video URL')
    parser.add_argument('--output', default='input/video.mp4')
    args = parser.parse_args()
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    success = download_video(args.url, args.output)
    
    if success:
        print(f"[+] SUCCESS: {args.output}")
        sys.exit(0)
    else:
        print(f"[!] FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
