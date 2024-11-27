import os, subprocess, time, sys, tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_utils import load_key
from core.step1_ytdlp import find_video_files
from rich import print as rprint
import cv2
import numpy as np
import platform

SRC_FONT_SIZE = 16
TRANS_FONT_SIZE = 18
FONT_NAME = 'Arial'
TRANS_FONT_NAME = 'Arial'

# Linux need to install google noto fonts: apt-get install fonts-noto
if platform.system() == 'Linux':
    FONT_NAME = 'NotoSansCJK-Regular'
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'

SRC_FONT_COLOR = '&HFFFFFF'
SRC_OUTLINE_COLOR = '&H000000'
SRC_OUTLINE_WIDTH = 1
SRC_SHADOW_COLOR = '&H80000000'
TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1 
TRANS_BACK_COLOR = '&H33000000'

OUTPUT_DIR = "output"
OUTPUT_VIDEO = f"{OUTPUT_DIR}/output_sub.mp4"
SRC_SRT = f"{OUTPUT_DIR}/src.srt"
TRANS_SRT = f"{OUTPUT_DIR}/trans.srt"

def check_gpu_available():
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        return 'h264_nvenc' in result.stdout
    except:
        return False

def check_ffmpeg_filters():
    """检查 FFmpeg 支持的过滤器"""
    try:
        result = subprocess.run(['ffmpeg', '-filters'], capture_output=True, text=True)
        print("\nAvailable FFmpeg filters:")
        print(result.stdout)
        
        # 特别检查字幕相关的过滤器
        subtitle_filters = [line for line in result.stdout.split('\n') 
                          if 'sub' in line.lower() or 'ass' in line.lower()]
        print("\nSubtitle related filters:")
        for filter in subtitle_filters:
            print(filter)
            
        return result.stdout
    except Exception as e:
        print(f"Error checking FFmpeg filters: {e}")
        return None

def parse_srt(srt_file):
    """解析 SRT 文件，返回带时间戳的字幕列表"""
    subtitles = []
    with open(srt_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        if '-->' in lines[i]:
            # 解析时间戳
            time_parts = lines[i].strip().split(' --> ')
            start = time_parts[0].replace(',', '.')
            end = time_parts[1].replace(',', '.')
            
            # 获取文本
            text = []
            i += 1
            while i < len(lines) and lines[i].strip():
                text.append(lines[i].strip())
                i += 1
            
            subtitles.append({
                'start': start,
                'end': end,
                'text': ' '.join(text)
            })
        i += 1
    return subtitles

def escape_text(text):
    """转义 FFmpeg drawtext 文本"""
    return text.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

def format_time(time_str):
    """将 SRT 时间格式转换为秒"""
    h, m, s = time_str.replace(",", ".").split(":")
    return float(h) * 3600 + float(m) * 60 + float(s)

def merge_subtitles_to_video():
    """将字幕合并到视频中"""
    video_file = find_video_files()
    output_file = 'output/output_sub.mp4'
    
    if os.path.exists(output_file):
        print(f"[yellow]⚠️ {output_file} already exists, skipping merge step.[/yellow]")
        return
        
    print("🎬 Start merging subtitles to video...")
    
    # 检查是否有 NVIDIA GPU
    has_nvidia = check_gpu_available()
    
    # 构建 FFmpeg 命令
    resolution = load_key("resolution")
    if resolution == "0x0":
        return
        
    w, h = map(int, resolution.split('x'))
    
    # 解析字幕文件
    src_subs = parse_srt(SRC_SRT)
    trans_subs = parse_srt(TRANS_SRT)
    
    # 构建过滤器表达式
    filter_parts = [
        f'scale={w}:{h}:force_original_aspect_ratio=decrease',
        f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2'
    ]
    
    # 为每个字幕添加一个 drawtext 过滤器
    for sub in src_subs:
        filter_parts.append(
            f'drawtext=fontfile=/Windows/Fonts/arial.ttf:'
            f'text=\'{escape_text(sub["text"])}\':'
            f'fontsize={SRC_FONT_SIZE}:'
            f'fontcolor=white:'
            f'box=1:boxcolor=black@0.5:boxborderw=5:'
            f'x=(w-text_w)/2:y=h-text_h-100:'
            f'enable=between(t\\,{format_time(sub["start"])}\\,{format_time(sub["end"])})'
        )
    
    for sub in trans_subs:
        filter_parts.append(
            f'drawtext=fontfile=/Windows/Fonts/arial.ttf:'
            f'text=\'{sub["text"]}\':'
            f'fontsize={TRANS_FONT_SIZE}:'
            f'fontcolor=yellow:'
            f'box=1:boxcolor=black@0.5:boxborderw=5:'
            f'x=(w-text_w)/2:y=h-text_h-10:'
            f'enable=between(t\\,{sub["start"]}\\,{sub["end"]})'
        )
    
    filter_complex = ','.join(filter_parts)
    
    try:
        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_file,
            '-vf', filter_complex,
            '-c:v', 'h264_nvenc' if has_nvidia else 'libx264',
            '-preset', 'medium',
            '-c:a', 'copy',
            output_file
        ], check=True)
    except subprocess.CalledProcessError:
        print("❌ FFmpeg execution error")
        raise
    finally:
        # 清理临时文件
        try:
            os.remove(temp_src)
            os.remove(temp_trans)
        except:
            pass

if __name__ == "__main__":
    merge_subtitles_to_video()