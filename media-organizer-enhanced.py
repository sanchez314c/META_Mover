#!/usr/bin/env python3

####################################################################################
#                                                                                  #
#    ██████╗ ███████╗████████╗   ███████╗██╗    ██╗██╗███████╗████████╗██╗   ██╗   #
#   ██╔════╝ ██╔════╝╚══██╔══╝   ██╔════╝██║    ██║██║██╔════╝╚══██╔══╝╚██╗ ██╔╝   #
#   ██║  ███╗█████╗     ██║      ███████╗██║ █╗ ██║██║█████╗     ██║    ╚████╔╝    #
#   ██║   ██║██╔══╝     ██║      ╚════██║██║███╗██║██║██╔══╝     ██║     ╚██╔╝     #
#   ╚██████╗ ███████╗   ██║      ███████║╚███╔███╔╝██║██╗        ██║      ██║      #
#    ╚═════╝ ╚══════╝   ╚═╝      ╚══════╝ ╚══╝╚══╝ ╚═╝╚═╝        ╚═╝      ╚═╝      #
#                                                                                  #
####################################################################################
#
# Script Name: media-organizer-enhanced.py                                        
# 
# Author: sanchez314c@speedheathens.com  
#                                              
# Date Created: 2025-01-24                                                       
#
# Last Modified: 2025-01-24                                                      
#
# Version: 1.7.0                                                                 
#
# Description: Comprehensive media organizer with advanced metadata handling,    
#              multi-format support, and intelligent file organization. Features 
#              final sweep processing, subsecond precision, and MPO conversion.                                              
#
# Usage: python media-organizer-enhanced.py [--input PATH] [--output DIR]
#
# Dependencies: exiftool, mutagen, moviepy, imagemagick, tqdm, tkinter                                           
#
# GitHub: https://github.com/sanchez314c                                         
#
# Notes: Supports comprehensive media formats with advanced metadata extraction,      
#        year-based organization, subsecond filename formatting, and intelligent  
#        error recovery with final sweep capability.                                                    
#                                                                                
####################################################################################

"""
Enhanced Media Organizer
=======================

Comprehensive media organizer with advanced metadata handling, multi-format support,
and intelligent file organization. Features final sweep processing for maximum coverage.
"""

import os
import sys
import re
import json
import shutil
import subprocess
import time
import threading
import multiprocessing
import tempfile
import signal
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count, Manager
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any, Set
import importlib.util
import atexit

# Global variables
WORKER_PROCESS = False
MOVIEPY_AVAILABLE = False
IMAGEMAGICK_AVAILABLE = False
EXIT_FLAG = False

def ensure_package(package_name):
    if importlib.util.find_spec(package_name) is None:
        print(f"{package_name} not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"Installed {package_name}.")
        return True
    return False

if not WORKER_PROCESS:
    required_packages = ['tqdm', 'mutagen']
    for package in required_packages:
        ensure_package(package)
    
    try:
        ensure_package('moviepy')
        import moviepy
        MOVIEPY_AVAILABLE = True
        print("MoviePy available and loaded successfully.")
    except Exception as e:
        print(f"Warning: MoviePy not available: {e}")
        MOVIEPY_AVAILABLE = False
        
    try:
        result = subprocess.run(['convert', '-version'], 
                             capture_output=True, text=True)
        if result.returncode == 0 and 'ImageMagick' in result.stdout:
            IMAGEMAGICK_AVAILABLE = True
            print("ImageMagick available and loaded successfully.")
        else:
            IMAGEMAGICK_AVAILABLE = False
            print("Warning: ImageMagick not found. MPO conversion will be limited.")
    except FileNotFoundError:
        IMAGEMAGICK_AVAILABLE = False
        print("Warning: ImageMagick not found. MPO conversion will be limited.")

from tqdm import tqdm
import mutagen
from mutagen.id3 import ID3

try:
    from tkinter import Tk, filedialog, messagebox
except ImportError:
    print("Warning: tkinter not available. Please install tkinter for your platform.")
    sys.exit(1)

processed_files = 0
total_files = 0
error_files = []
progress_lock = threading.Lock()
temp_files = []

MEDIA_TYPES = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif', 
              '.raw', '.dng', '.cr2', '.nef', '.arw', '.ptx', '.svg', '.pdf', '.mpo'],
    'video': ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'],
    'audio': ['.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.aiff', '.alac', '.caf', '.amr', '.wmf'],
    'document': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf'],
    'art': ['.psd', '.ai', '.indd', '.cdr', '.dwg', '.eps']
}

def signal_handler(sig, frame):
    global EXIT_FLAG
    print("\nReceived interrupt signal. Initiating graceful shutdown...")
    EXIT_FLAG = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def cleanup_temp_files():
    global temp_files
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass

atexit.register(cleanup_temp_files)

def update_progress() -> None:
    global processed_files
    with progress_lock:
        processed_files += 1

def find_exiftool() -> Optional[str]:
    try:
        result = subprocess.run(['exiftool', '-ver'], 
                             capture_output=True, text=True, check=True)
        return 'exiftool'
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    common_locations = [
        '/usr/local/bin/exiftool',
        '/usr/bin/exiftool',
        '/opt/homebrew/bin/exiftool',
        '/opt/local/bin/exiftool',
        os.path.expanduser('~/bin/exiftool'),
        os.path.expanduser('~/.local/bin/exiftool'),
        '/Applications/ExifTool/exiftool'
    ]
    
    for location in common_locations:
        if os.path.isfile(location) and os.access(location, os.X_OK):
            try:
                result = subprocess.run([location, '-ver'], 
                                     capture_output=True, text=True, check=True)
                return location
            except subprocess.SubprocessError:
                continue
    
    return None

def get_fallback_date(file_path: str) -> datetime:
    return datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)

def remove_empty_directories(path: str) -> None:
    if not os.path.isdir(path):
        return
        
    for root, dirs, files in os.walk(path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if os.path.isdir(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"Removed empty directory: {dir_path}")
            except Exception as e:
                print(f"Error removing directory {dir_path}: {e}")

def choose_directory(title: str) -> str:
    root = Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title=title)
    root.destroy()
    return directory

def get_media_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    
    for media_type, extensions in MEDIA_TYPES.items():
        if ext in extensions:
            return media_type
    
    return "unknown"

def convert_mpo_to_jpeg(file_path: str) -> Optional[str]:
    global temp_files
    
    try:
        fd, temp_jpeg_path = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)
        temp_files.append(temp_jpeg_path)
        
        cmd = ['convert', file_path + '[0]', temp_jpeg_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        return temp_jpeg_path
    except subprocess.CalledProcessError as e:
        if not WORKER_PROCESS:
            print(f"Error converting MPO to JPEG: {e}")
            if e.stderr:
                print(f"  ImageMagick error: {e.stderr}")
        return None
    except Exception as e:
        if not WORKER_PROCESS:
            print(f"Unexpected error converting MPO to JPEG: {e}")
        return None

def extract_metadata(file_path: str, exiftool_path: str) -> Dict[str, Any]:
    try:
        result = subprocess.run([exiftool_path, '-json', '-a', '-u', '-g1', '-api', 'LargeFileSupport=1', file_path], 
                             capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)[0]
        metadata['SourceFile'] = file_path
        
        return metadata
    except subprocess.CalledProcessError as e:
        if not WORKER_PROCESS:
            print(f"Warning: ExifTool error for {file_path}: {e}")
        return {'SourceFile': file_path}
    except json.JSONDecodeError:
        if not WORKER_PROCESS:
            print(f"Warning: Failed to parse metadata from {file_path}")
        return {'SourceFile': file_path}
    except Exception as e:
        if not WORKER_PROCESS:
            print(f"Warning: Unexpected error extracting metadata from {file_path}: {e}")
        return {'SourceFile': file_path}

def extract_audio_metadata(file_path: str) -> Dict[str, Any]:
    try:
        audio = mutagen.File(file_path)
        if not audio:
            return {}
            
        metadata = {}
        
        if hasattr(audio, 'tags') and isinstance(audio.tags, ID3):
            for key, value in audio.items():
                metadata[key] = str(value)
        elif hasattr(audio, 'tags') and audio.tags:
            for key, value in audio.tags.items():
                metadata[key] = str(value)
                
        if hasattr(audio, 'info'):
            metadata['bitrate'] = getattr(audio.info, 'bitrate', 0)
            metadata['sample_rate'] = getattr(audio.info, 'sample_rate', 0)
            metadata['channels'] = getattr(audio.info, 'channels', 0)
            metadata['length'] = getattr(audio.info, 'length', 0)
            
        return metadata
    except Exception as e:
        if not WORKER_PROCESS:
            print(f"Warning: Failed to extract audio metadata from {file_path}: {e}")
        return {}

def extract_date_from_metadata(metadata: Dict[str, Any], file_path: str) -> datetime:
    filename = os.path.basename(file_path)
    
    filename_patterns = [
        (r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})', 
         lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 
                            int(m.group(4)), int(m.group(5)), int(m.group(6)))),
        (r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', 
         lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 
                            int(m.group(4)), int(m.group(5)), int(m.group(6)))),
    ]
    
    for pattern, parser in filename_patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                return parser(match)
            except (ValueError, IndexError):
                pass
    
    date_fields = ['DateTimeOriginal', 'CreateDate', 'DateTimeCreated', 
                  'MediaCreateDate', 'TrackCreateDate', 'FileModifyDate']
    
    date_formats = [
        '%Y:%m:%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y:%m:%d %H-%M-%S',
        '%Y-%m-%d %H-%M-%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y:%m:%d'
    ]
    
    exif_sections = ['ExifIFD', 'IFD0', 'XMP-xmp', 'Composite', '']
    
    for section in exif_sections:
        section_data = metadata.get(section, {}) if section else metadata
        
        if not isinstance(section_data, dict):
            continue
            
        for field in date_fields:
            if field in section_data:
                date_str = str(section_data[field])
                date_str = re.sub(r'[-+]\d{2}:\d{2}$', '', date_str)
                
                for fmt in date_formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
    
    if 'TDRC' in metadata:
        try:
            date_str = str(metadata['TDRC'])
            for fmt in ['%Y', '%Y-%m-%d', '%Y-%m']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
    
    filename_date_patterns = [
        (r'(\d{4})(\d{2})(\d{2})', 
         lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r'(\d{2})(\d{2})(\d{2})', 
         lambda m: datetime(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    ]
    
    for pattern, parser in filename_date_patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                date_only = parser(match)
                time_match = re.search(r'(\d{2})[-_]?(\d{2})[-_]?(\d{2})', filename)
                if time_match:
                    return datetime(date_only.year, date_only.month, date_only.day,
                                   int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3)))
                else:
                    return date_only
            except (ValueError, IndexError):
                pass
    
    return get_fallback_date(file_path)

def extract_subseconds_enhanced(metadata: Dict[str, Any]) -> Tuple[str, bool]:
    needs_cleaning = False
    suspicious_patterns = ['9642', '9643', '9644', '9645', '0964']
    
    if 'ExifIFD' in metadata and isinstance(metadata['ExifIFD'], dict):
        exif_ifd = metadata['ExifIFD']
        subsec_fields = ['SubSecTimeOriginal', 'SubSecTime', 'SubSecTimeDigitized']
        for field in subsec_fields:
            if field in exif_ifd and exif_ifd[field]:
                subsec = str(exif_ifd[field]).strip()
                
                if not subsec:
                    continue
                    
                if any(pattern in subsec for pattern in suspicious_patterns):
                    needs_cleaning = True
                    continue
                
                if subsec.startswith('0') and not all(c == '0' for c in subsec):
                    subsec = subsec.lstrip('0')
                    if subsec and subsec.isdigit():
                        return subsec.zfill(6)[:6], False
                    
                if subsec.isdigit():
                    if int(subsec) > 0:
                        return subsec.zfill(6)[:6], False
    
    subsec_fields = ['SubSecTimeOriginal', 'SubSecTime', 'SubSecTimeDigitized']
    for field in subsec_fields:
        if field in metadata and metadata[field]:
            subsec = str(metadata[field]).strip()
            
            if not subsec:
                continue
                
            if any(pattern in subsec for pattern in suspicious_patterns):
                needs_cleaning = True
                continue
            
            if subsec.startswith('0') and not all(c == '0' for c in subsec):
                subsec = subsec.lstrip('0')
                if subsec and subsec.isdigit():
                    return subsec.zfill(6)[:6], False
                
            if subsec.isdigit():
                if int(subsec) > 0:
                    return subsec.zfill(6)[:6], False
    
    return '', needs_cleaning

def clean_subsecond_metadata(file_path: str, exiftool_path: str) -> bool:
    try:
        cmd = [exiftool_path, '-overwrite_original']
        subsec_fields = ['SubSecTimeOriginal', 'SubSecTimeDigitized', 'SubSecTime']
        for field in subsec_fields:
            cmd.extend([f'-{field}='])
        cmd.append(file_path)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        if not WORKER_PROCESS:
            print(f"Error cleaning subsecond metadata for {file_path}: {e}")
        return False

def generate_filename_with_ss(date: datetime, subseconds: str, original_extension: str) -> str:
    date_str = date.strftime('%Y-%m-%d_%H-%M-%S')
    
    if (subseconds and 
        subseconds.isdigit() and 
        int(subseconds) > 0):
        
        suspicious_patterns = ['9642', '9643', '9644', '9645', '0964', '964']
        if not any(pattern in subseconds for pattern in suspicious_patterns):
            return f"{date_str}-ss{subseconds}{original_extension}"
    
    return f"{date_str}{original_extension}"

def resolve_collision(target_path: str) -> str:
    base, extension = os.path.splitext(target_path)
    counter = 2
    
    if "-ss" in base.lower():
        ss_part = base.split("-ss")[1]
        base = base.replace(f"-ss{ss_part}", "")
        while os.path.exists(f"{base}_{counter}-ss{ss_part}{extension}"):
            counter += 1
        return f"{base}_{counter}-ss{ss_part}{extension}"
    else:
        while os.path.exists(f"{base}_{counter}{extension}"):
            counter += 1
        return f"{base}_{counter}{extension}"

def determine_target_directory(destination_root: str, media_type: str, date: datetime, file_size: int = 0, is_error: bool = False) -> str:
    year = date.strftime('%Y')
    
    media_folder_map = {
        'image': 'Photos',
        'video': 'Videos',
        'audio': 'Audio', 
        'document': 'Documents',
        'art': 'Art',
        'unknown': 'Other'
    }
    
    media_folder = media_folder_map.get(media_type, 'Other')
    
    if is_error:
        if file_size > 0 and file_size <= 200 * 1024:
            return os.path.join(destination_root, 'Error', 'small_files', media_folder, year)
        else:
            return os.path.join(destination_root, 'Error', media_folder, year)
    
    elif file_size > 0 and file_size <= 200 * 1024:
        return os.path.join(destination_root, 'small_files', media_folder, year)
    else:
        return os.path.join(destination_root, media_folder, year)

def update_metadata_date(file_path: str, date: datetime, 
                       subseconds: Optional[str], exiftool_path: str) -> bool:
    try:
        formatted_date = date.strftime('%Y:%m:%d %H:%M:%S')
        cmd = [exiftool_path, '-overwrite_original']
        date_fields = ['FileModifyDate']
        for field in date_fields:
            cmd.extend([f'-{field}={formatted_date}'])
        
        if subseconds:
            subsec_fields = ['SubSecTimeOriginal', 'SubSecTimeDigitized', 'SubSecTime']
            for field in subsec_fields:
                cmd.extend([f'-{field}={subseconds}'])
        
        cmd.append(file_path)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        if not WORKER_PROCESS:
            print(f"Error updating metadata for {file_path}: {e}")
        return False

def process_file(args: Tuple[str, str, str, bool]) -> Tuple[bool, str]:
    file_path, destination_root, exiftool_path, is_error_sweep = args
    converted_file = None
    original_ext = os.path.splitext(file_path)[1].lower()
    is_mpo = original_ext == '.mpo'
    
    if EXIT_FLAG:
        update_progress()
        return (False, f"Processing interrupted: {os.path.basename(file_path)}")
    
    try:
        media_type = get_media_type(file_path)
        if media_type == 'unknown' and not is_error_sweep:
            update_progress()
            return (False, f"Unsupported file type: {os.path.basename(file_path)}")
        
        if is_mpo and IMAGEMAGICK_AVAILABLE:
            jpeg_path = convert_mpo_to_jpeg(file_path)
            if jpeg_path:
                converted_file = jpeg_path
                metadata = extract_metadata(jpeg_path, exiftool_path)
                original_metadata = extract_metadata(file_path, exiftool_path)
                for key, value in original_metadata.items():
                    if key not in metadata or not metadata[key]:
                        metadata[key] = value
                metadata['SourceFile'] = file_path
            else:
                metadata = extract_metadata(file_path, exiftool_path)
        else:
            metadata = extract_metadata(file_path, exiftool_path)
        
        if media_type == 'audio':
            audio_metadata = extract_audio_metadata(file_path)
            metadata.update(audio_metadata)
        
        date = extract_date_from_metadata(metadata, file_path)
        subseconds, needs_cleaning = extract_subseconds_enhanced(metadata)
        
        if is_mpo and IMAGEMAGICK_AVAILABLE:
            new_extension = '.jpg'
        else:
            new_extension = os.path.splitext(file_path)[1]
        
        new_filename = generate_filename_with_ss(date, subseconds, new_extension)
        
        try:
            if converted_file:
                file_size = os.path.getsize(converted_file)
            else:
                file_size = os.path.getsize(file_path)
        except Exception:
            file_size = 0
        
        target_directory = determine_target_directory(
            destination_root, media_type, date, file_size, is_error_sweep)
        os.makedirs(target_directory, exist_ok=True)
        
        target_path = os.path.join(target_directory, new_filename)
        
        if os.path.exists(target_path):
            target_path = resolve_collision(target_path)
        
        if converted_file:
            shutil.copy2(converted_file, target_path)
        else:
            shutil.copy2(file_path, target_path)
        
        if needs_cleaning:
            clean_subsecond_metadata(target_path, exiftool_path)
        else:
            update_metadata_date(target_path, date, subseconds, exiftool_path)
        
        if not is_error_sweep:
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not remove original file {file_path}: {e}")
        
        update_progress()
        
        prefix = "Error sweep - " if is_error_sweep else ""
        if is_mpo and IMAGEMAGICK_AVAILABLE:
            return (True, f"{prefix}Processed and converted: {os.path.basename(file_path)} (MPO→JPG) -> {os.path.relpath(target_path, destination_root)}")
        else:
            message = f"{prefix}Processed: {os.path.basename(file_path)} -> {os.path.relpath(target_path, destination_root)}"
            if needs_cleaning:
                message += " (cleaned erroneous subseconds)"
            return (True, message)
    
    except Exception as e:
        update_progress()
        error_files.append(file_path)
        return (False, f"Error processing {os.path.basename(file_path)}: {e}")
    finally:
        if converted_file and os.path.exists(converted_file):
            try:
                os.remove(converted_file)
            except Exception:
                pass

def get_files_to_process(source_dir: str, file_list: List[str] = None, include_unknown: bool = False) -> List[str]:
    result_list = [] if file_list is None else file_list
    
    def scan_directory(current_dir):
        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    try:
                        if entry.name.startswith('.'):
                            continue
                            
                        if entry.is_file():
                            media_type = get_media_type(entry.path)
                            if include_unknown or media_type != 'unknown':
                                result_list.append(entry.path)
                        elif entry.is_dir():
                            scan_directory(entry.path)
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not access {entry.path}: {e}")
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not scan directory {current_dir}: {e}")
    
    scan_directory(source_dir)
    
    if file_list is None:
        return result_list
    return None

def batch_files(files, num_batches):
    if not files:
        return []
        
    avg_batch_size = len(files) // num_batches
    remainder = len(files) % num_batches
    
    if avg_batch_size == 0:
        return [files] if files else []
    
    batches = []
    start = 0
    
    for i in range(num_batches):
        batch_size = avg_batch_size + (1 if i < remainder else 0)
        end = start + batch_size
        batches.append(files[start:end])
        start = end
        
    return batches

def worker_init():
    global WORKER_PROCESS
    WORKER_PROCESS = True

def process_batch(batch_args):
    batch_files, destination_root, exiftool_path, batch_index, shared_counter, is_error_sweep = batch_args
    
    global WORKER_PROCESS
    WORKER_PROCESS = True
    
    results = []
    for file_path in batch_files:
        if EXIT_FLAG:
            break
            
        try:
            result = process_file((file_path, destination_root, exiftool_path, is_error_sweep))
            results.append(result)
            
            try:
                if hasattr(shared_counter, 'get_lock'):
                    with shared_counter.get_lock():
                        shared_counter.value += 1
                else:
                    shared_counter.value += 1
            except Exception:
                shared_counter.value += 1
                
        except Exception as e:
            results.append((False, f"Error in batch {batch_index+1}: {str(e)}"))
            try:
                if hasattr(shared_counter, 'get_lock'):
                    with shared_counter.get_lock():
                        shared_counter.value += 1
                else:
                    shared_counter.value += 1
            except Exception:
                shared_counter.value += 1
    
    return results

def optimize_core_usage():
    total_cores = cpu_count()
    physical_cores = total_cores
    
    try:
        if sys.platform == 'darwin':
            output = subprocess.check_output(["sysctl", "-n", "hw.physicalcpu"]).decode('utf-8').strip()
            physical_cores = int(output)
    except:
        pass
    
    if physical_cores > 8:
        num_workers = physical_cores - 1
    else:
        num_workers = physical_cores
    
    try:
        if sys.platform == 'darwin':
            output = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode('utf-8').strip()
            total_memory_bytes = int(output)
            total_memory_gb = total_memory_bytes / (1024**3)
        elif sys.platform == 'linux':
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        total_memory_kb = int(line.split()[1])
                        total_memory_gb = total_memory_kb / (1024**2)
                        break
        elif sys.platform == 'win32':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            memoryStatus = MEMORYSTATUSEX()
            memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
            total_memory_gb = memoryStatus.ullTotalPhys / (1024**3)
        else:
            total_memory_gb = 8
    except:
        total_memory_gb = 8
    
    if total_memory_gb >= 32:
        files_per_worker = 50
    elif total_memory_gb >= 16:
        files_per_worker = 30
    else:
        files_per_worker = 15
    
    if num_workers >= 12:
        batch_size = num_workers * 8
    elif num_workers >= 8:
        batch_size = num_workers * 6
    elif num_workers >= 4:
        batch_size = num_workers * 4
    else:
        batch_size = num_workers * 3
    
    print(f"System has {physical_cores} physical cores out of {total_cores} logical cores")
    print(f"Detected approximately {total_memory_gb:.1f} GB of RAM")
    print(f"Using {num_workers} worker processes with {files_per_worker} files per worker")
    print(f"Batch size: {batch_size}")
    
    return (num_workers, files_per_worker, batch_size)

def perform_final_sweep(source_dir, destination_dir, exiftool_path, num_workers, batch_size):
    global total_files, processed_files, error_files, EXIT_FLAG
    
    processed_files = 0
    total_files = 0
    error_files = []
    
    print("\n========== STARTING FINAL SWEEP ==========")
    print("Scanning for remaining files in source directory...")
    
    sweep_files = get_files_to_process(source_dir, include_unknown=True)
    
    total_files = len(sweep_files)
    
    if total_files == 0:
        print("No remaining files found in the source directory. Final sweep not needed.")
        return (0, 0, 0)
    
    print(f"Found {total_files} remaining files to process in final sweep.")
    print(f"These files will be organized in the 'Error' directory.")
    
    start_time = time.time()
    success_count = 0
    
    try:
        with Manager() as manager:
            shared_processed_count = manager.Value('i', 0)
            shared_error_files = manager.list()
            
            batches = batch_files(sweep_files, min(batch_size, total_files))
            
            batch_args = [(batch, destination_dir, exiftool_path, i, shared_processed_count, True) 
                         for i, batch in enumerate(batches)]
            
            def update_progress_display():
                while shared_processed_count.value < total_files and not EXIT_FLAG:
                    current = shared_processed_count.value
                    percent = (current / total_files) * 100 if total_files > 0 else 0
                    elapsed = time.time() - start_time
                    files_per_sec = current / elapsed if elapsed > 0 else 0
                    
                    if files_per_sec > 0:
                        remaining_files = total_files - current
                        eta_seconds = remaining_files / files_per_sec
                        eta_str = f"{int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m {int(eta_seconds % 60)}s"
                    else:
                        eta_str = "calculating..."
                    
                    sys.stdout.write("\r" + " " * 80)
                    sys.stdout.write(f"\rFinal Sweep Progress: {current}/{total_files} ({percent:.1f}%) - {files_per_sec:.1f} files/sec - ETA: {eta_str}")
                    sys.stdout.flush()
                    
                    time.sleep(1)
                
                if not EXIT_FLAG:
                    sys.stdout.write("\r" + " " * 80)
                    sys.stdout.write(f"\rProcessed: {total_files}/{total_files} (100.0%) - Final Sweep Complete!\n")
                    sys.stdout.flush()
            
            progress_thread = threading.Thread(target=update_progress_display)
            progress_thread.daemon = True
            progress_thread.start()
            
            with Pool(processes=num_workers, initializer=worker_init) as pool:
                batch_results = []
                
                for batch_result in pool.imap_unordered(process_batch, batch_args):
                    if EXIT_FLAG:
                        pool.terminate()
                        break
                        
                    success_count += sum(1 for success, _ in batch_result if success)
                    
                    for success, message in batch_result:
                        if not success and "Unsupported file type" not in message:
                            shared_error_files.append(message)
                    
                    batch_results.append(batch_result)
            
            if progress_thread.is_alive():
                progress_thread.join(timeout=1)
            
            error_files = list(shared_error_files)
    
    except KeyboardInterrupt:
        EXIT_FLAG = True
        print("\nFinal sweep interrupted by user.")
    except Exception as e:
        print(f"\nError during final sweep: {e}")
    
    elapsed_time = time.time() - start_time
    
    return (success_count, total_files, elapsed_time)

def main() -> None:
    global total_files, processed_files, error_files, EXIT_FLAG
    
    EXIT_FLAG = False
    total_files = 0
    processed_files = 0
    error_files = []
    
    print("Enhanced Media Organizer - Final Sweep Edition")
    print("----------------------------------------------------------")
    
    exiftool_path = find_exiftool()
    if not exiftool_path:
        print("Error: ExifTool is not installed or not found.")
        print("Please install ExifTool: https://exiftool.org/")
        
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", "ExifTool is not installed or not found.\n"
                           "Please install ExifTool: https://exiftool.org/")
        root.destroy()
        return
    
    print(f"Using ExifTool: {exiftool_path}")
    
    source_dir = choose_directory("Select Source Directory")
    if not source_dir:
        print("No source directory selected, exiting...")
        return
    
    destination_dir = choose_directory("Select Destination Directory")
    if not destination_dir:
        print("No destination directory selected, exiting...")
        return
    
    print("Scanning for files...")
    
    scanning_progress = ["|", "/", "-", "\\"]
    scanning_idx = 0
    files_found = 0
    last_update_time = time.time()
    
    def update_scanning_progress():
        nonlocal scanning_idx, files_found, last_update_time
        current_time = time.time()
        
        if current_time - last_update_time >= 0.5:
            sys.stdout.write(f"\rScanning... {scanning_progress[scanning_idx]} Found {files_found} files so far")
            sys.stdout.flush()
            scanning_idx = (scanning_idx + 1) % len(scanning_progress)
            last_update_time = current_time
    
    class ProgressList(list):
        def append(self, item):
            nonlocal files_found
            super().append(item)
            files_found += 1
            update_scanning_progress()
    
    files = ProgressList()
    
    scanning_in_progress = [True]
    
    def spinner_thread():
        while len(files) == 0 or scanning_in_progress[0]:
            update_scanning_progress()
            time.sleep(0.1)
    
    spinner = threading.Thread(target=spinner_thread)
    spinner.daemon = True
    spinner.start()
    
    try:
        get_files_to_process(source_dir, files)
    finally:
        scanning_in_progress[0] = False
        
    sys.stdout.write(f"\rScanned {len(files)} files in total.{' ' * 30}\n")
    sys.stdout.flush()
    
    total_files = len(files)
    
    if total_files == 0:
        print("No supported files found in the source directory.")
        print("Proceeding to final sweep to check for any other files.")
        initial_success_count = 0
        initial_elapsed_time = 0
    else:
        num_workers, files_per_worker, batch_size = optimize_core_usage()
        
        print(f"Found {total_files} files in source directory.")
        print(f"Processing with {num_workers} worker processes and batch size of {batch_size}")
        
        start_time = time.time()
        initial_success_count = 0
        
        try:
            with Manager() as manager:
                shared_processed_count = manager.Value('i', 0)
                shared_error_files = manager.list()
                
                batches = batch_files(files, min(batch_size, total_files))
                
                batch_args = [(batch, destination_dir, exiftool_path, i, shared_processed_count, False) 
                             for i, batch in enumerate(batches)]
                
                def update_progress_display():
                    while shared_processed_count.value < total_files and not EXIT_FLAG:
                        current = shared_processed_count.value
                        percent = (current / total_files) * 100 if total_files > 0 else 0
                        elapsed = time.time() - start_time
                        files_per_sec = current / elapsed if elapsed > 0 else 0
                        
                        if files_per_sec > 0:
                            remaining_files = total_files - current
                            eta_seconds = remaining_files / files_per_sec
                            eta_str = f"{int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m {int(eta_seconds % 60)}s"
                        else:
                            eta_str = "calculating..."
                        
                        sys.stdout.write("\r" + " " * 80)
                        sys.stdout.write(f"\rProgress: {current}/{total_files} ({percent:.1f}%) - {files_per_sec:.1f} files/sec - ETA: {eta_str}")
                        sys.stdout.flush()
                        
                        time.sleep(1)
                    
                    if not EXIT_FLAG:
                        sys.stdout.write("\r" + " " * 80)
                        sys.stdout.write(f"\rProcessed: {total_files}/{total_files} (100.0%) - Initial Processing Complete!\n")
                        sys.stdout.flush()
                
                progress_thread = threading.Thread(target=update_progress_display)
                progress_thread.daemon = True
                progress_thread.start()
                
                with Pool(processes=num_workers, initializer=worker_init) as pool:
                    batch_results = []
                    
                    for batch_result in pool.imap_unordered(process_batch, batch_args):
                        if EXIT_FLAG:
                            pool.terminate()
                            break
                            
                        initial_success_count += sum(1 for success, _ in batch_result if success)
                        
                        for success, message in batch_result:
                            if not success and "Unsupported file type" not in message:
                                shared_error_files.append(message)
                        
                        batch_results.append(batch_result)
                
                if progress_thread.is_alive():
                    progress_thread.join(timeout=1)
                
                error_files = list(shared_error_files)
        
        except KeyboardInterrupt:
            EXIT_FLAG = True
            print("\nProcessing interrupted by user.")
        except Exception as e:
            print(f"\nError during processing: {e}")
        
        initial_elapsed_time = time.time() - start_time
        
        print("\nCleaning up empty directories...")
        remove_empty_directories(source_dir)
    
    if not EXIT_FLAG:
        num_workers, files_per_worker, batch_size = optimize_core_usage()
        
        final_success_count, final_total, final_elapsed_time = perform_final_sweep(
            source_dir, destination_dir, exiftool_path, num_workers, batch_size)
            
        if final_total > 0:
            print("\nFinal cleanup of empty directories...")
            remove_empty_directories(source_dir)
            
        total_processed = initial_success_count + final_success_count
        total_elapsed = initial_elapsed_time + final_elapsed_time
        total_found = total_files + final_total
        
        print("\n========== PROCESSING SUMMARY ==========")
        print(f"Initial processing: {initial_success_count} of {total_files} files in {initial_elapsed_time:.1f} seconds")
        if final_total > 0:
            print(f"Final sweep: {final_success_count} of {final_total} files in {final_elapsed_time:.1f} seconds")
        else:
            print("Final sweep: Not needed (no remaining files found)")
            
        print(f"\nTotal processed: {total_processed} of {total_found} files")
        print(f"Total time: {total_elapsed:.1f} seconds")
        files_per_second = total_processed / total_elapsed if total_elapsed > 0 else 0
        print(f"Overall speed: {files_per_second:.1f} files/second")
        
        if error_files:
            print(f"Errors encountered: {len(error_files)} files")
            print("Some example errors:")
            for error_msg in error_files[:5]:
                print(f"  - {error_msg}")
            if len(error_files) > 5:
                print(f"  - ... and {len(error_files) - 5} more")
        
        root = Tk()
        root.withdraw()
        if error_files:
            messagebox.showinfo("Processing Complete", 
                             f"Total processed: {total_processed} of {total_found} files\n"
                             f"Time taken: {total_elapsed:.1f} seconds\n"
                             f"Speed: {files_per_second:.1f} files/second\n"
                             f"Errors: {len(error_files)} files\n"
                             f"Files processed in final sweep: {final_success_count}")
        else:
            messagebox.showinfo("Processing Complete", 
                             f"All {total_processed} files processed successfully!\n"
                             f"Time taken: {total_elapsed:.1f} seconds\n"
                             f"Speed: {files_per_second:.1f} files/second\n"
                             f"Files in final sweep: {final_success_count}")
        root.destroy()
    else:
        print("\nProcessing was interrupted. Partial results:")
        print(f"Processed {initial_success_count} of {total_files} files")
        
        root = Tk()
        root.withdraw()
        messagebox.showwarning("Processing Interrupted", 
                          f"Processing was interrupted.\n"
                          f"Partially processed {initial_success_count} of {total_files} files.\n"
                          f"You can run the program again to process remaining files.")
        root.destroy()
    
    print("Cleaning up resources, please wait...")
    cleanup_temp_files()
    
    if EXIT_FLAG:
        print("Forcing exit due to user interruption...")
        os._exit(0)
    
    print("Process completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    
    try:
        if sys.platform == 'darwin':
            current_method = multiprocessing.get_start_method(allow_none=True)
            if current_method != 'spawn':
                multiprocessing.set_start_method('spawn')
        
        if sys.platform == 'darwin' and sys.version_info >= (3, 9):
            os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    except Exception as e:
        print(f"Warning: Could not set multiprocessing start method: {e}")
        print("Processing will continue, but performance may be affected.")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        EXIT_FLAG = True
        os._exit(0)
    except BrokenPipeError:
        print("\nBroken pipe error detected. This is often harmless.")
        print("The script has completed processing, but had trouble displaying progress.")
        os._exit(0)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        root.destroy()
        
        os._exit(1)