#!/usr/bin/env python3

####################################################################################
#                                                                                  #
#    ██████╗ ███████╗████████╗   ███████╗██╗    ██╗██╗███████╗████████╗██╗   ██╗   #
#   ██╔════╝ ██╔════╝╚══██╔══╝   ██╔════╝██║    ██║██║██╔════╝╚══██╔══╝╚██╗ ██╔╝   #
#   ██║  ███╗█████╗     ██║      ███████╗██║ █╗ ██║██║█████╗     ██║    ╚████╔╝    #
#   ██║   ██║██╔══╝     ██║      ╚════██║██║███╗██║██║██╔══╝     ██║     ╚██╔╝     #
#   ╚██████╔╝███████╗   ██║      ███████║╚███╔███╔╝██║██╗        ██║      ██║      #
#    ╚═════╝ ╚══════╝   ╚═╝      ╚══════╝ ╚══╝╚══╝ ╚═╝╚═╝        ╚═╝      ╚═╝      #
#                                                                                  #
####################################################################################
#
# Script Name: media-mover-basic.py                                        
# 
# Author: sanchez314c@speedheathens.com  
#                                              
# Date Created: 2025-01-24                                                       
#
# Last Modified: 2025-01-24                                                      
#
# Version: 1.1.0                                                                 
#
# Description: Basic media file mover with metadata extraction and organization    
#              by date and media type. Multi-threaded processing with automatic  
#              collision resolution and empty directory cleanup.                                              
#
# Usage: python media-mover-basic.py [--input PATH] [--output DIR]
#
# Dependencies: exiftool, moviepy, pillow, tqdm, tkinter                                           
#
# GitHub: https://github.com/sanchez314c                                         
#
# Notes: Supports comprehensive media formats with year/month organization,      
#        automatic extension correction, and collision resolution with  
#        subsecond precision support.                                                    
#                                                                                
####################################################################################

"""
Basic Media Mover
================

Basic media file organizer with metadata extraction and intelligent organization
by date and media type with multi-threaded processing capabilities.
"""

import os
import sys
import re
import json
import shutil
import subprocess
import time
import threading
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any, Set

try:
    from PIL import Image
    import moviepy.editor as mp
    from tkinter import Tk, filedialog, messagebox
    from tqdm import tqdm
except ImportError as e:
    missing_module = str(e).split("'")[1]
    print(f"Required module {missing_module} is missing. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", missing_module])
    print(f"Installed {missing_module}. Please restart the script.")
    sys.exit(1)

processed_filenames: Set[str] = set()
error_files: List[str] = []
progress_lock = threading.Lock()

MEDIA_TYPES = {
    'image': ['.mpo', '.dng', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', 
              '.ptx', '.raw', '.heic', '.heif', '.svg', '.pdf', '.ico', '.wmf'],
    'audio': ['.wmf', '.amr', '.caf', '.aiff', '.mp3', '.wav', '.aac', '.flac', '.alac', 
              '.ogg', '.m4a'],
    'video': ['.3gp', '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', 
              '.mpeg', '.webm'],
    'art': ['.cdr', '.ai', '.dwg', '.eps', '.indd', '.psd']
}

def get_fallback_date(file_path: str) -> datetime:
    return datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)

def remove_empty_directories(path: str) -> None:
    if os.path.isdir(path):
        for f in os.listdir(path):
            fullpath = os.path.join(path, f)
            if os.path.isdir(fullpath): 
                remove_empty_directories(fullpath)
        
        if not os.listdir(path):
            os.rmdir(path)
            print(f"Removed empty directory: {path}")

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

def check_and_correct_extension(file_path: str, media_type: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    
    if media_type == 'image':
        try:
            with Image.open(file_path) as img:
                correct_ext = f'.{img.format.lower()}'
                if correct_ext != ext:
                    new_file_path = os.path.splitext(file_path)[0] + correct_ext
                    os.rename(file_path, new_file_path)
                    return new_file_path
        except Exception:
            pass
    elif media_type == 'audio':
        if ext not in ['.mp3', '.wav', '.aac', '.flac', '.alac', '.ogg', '.m4a']:
            correct_ext = '.audio'
            new_file_path = os.path.splitext(file_path)[0] + correct_ext
            os.rename(file_path, new_file_path)
            return new_file_path
    elif media_type == 'video':
        try:
            clip = mp.VideoFileClip(file_path)
            correct_ext = f'.{clip.reader.fmt.lower()}'
            if correct_ext != ext:
                new_file_path = os.path.splitext(file_path)[0] + correct_ext
                os.rename(file_path, new_file_path)
                return new_file_path
            clip.close()
        except Exception:
            pass
            
    return file_path

def extract_metadata(file_path: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(['exiftool', '-json', file_path], 
                                capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)[0]
        return metadata
    except Exception as e:
        print(f"Warning: Failed to extract metadata from {file_path}: {e}")
        return {}

def extract_subseconds(metadata: Dict[str, Any]) -> str:
    for tag in ['SubSecTime', 'SubSecTimeOriginal', 'SubSecTimeDigitized']:
        if tag in metadata and metadata[tag] and metadata[tag] != '000':
            return metadata[tag]

    date_time_string = metadata.get('DateTimeOriginal') or metadata.get('CreateDate', '')
    datetime_match = re.search(r'\.(\d+)', date_time_string)
    embedded_subseconds = datetime_match.group(1) if datetime_match else None
    if embedded_subseconds:
        return embedded_subseconds

    xmp_title = metadata.get('Title', '')
    xmp_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})-(\d{6})-\d', xmp_title)
    xmp_subseconds = xmp_match.group(2) if xmp_match else None
    if xmp_subseconds:
        return xmp_subseconds

    return ''

def find_oldest_date(metadata: Dict[str, Any], file_path: str) -> datetime:
    date_formats = [
        '%Y-%m-%d %H:%M:%S%z',
        '%Y-%m-%d %H-%M-%S.%f',
        '%Y-%m-%d %H-%M-%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H-%M-%S',
        '%Y-%m-%d %H-%M-%S.%f',
    ]
    valid_dates = []

    def parse_date(date_str: str) -> Optional[datetime]:
        date_str = date_str.replace(':', '-', 2)
        for fmt in date_formats:
            try:
                date = datetime.strptime(date_str, fmt)
                return date.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    for key, value in metadata.items():
        potential_dates = re.findall(r'(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{2})?)', str(value))
        for date_str in potential_dates:
            date = parse_date(date_str.replace(':', '-', 2))
            if date:
                valid_dates.append(date)

    valid_dates.sort()

    if valid_dates:
        return valid_dates[0]
    else:
        return get_fallback_date(file_path)

def update_metadata(file_path: str, formatted_date: str, subseconds: Optional[str] = None) -> None:
    try:
        cmd = ['exiftool', '-overwrite_original']
        date_keys = ['FileModifyDate']
        for key in date_keys:
            cmd.extend([f'-{key}={formatted_date}'])
        
        if subseconds:
            subsec_keys = ['SubSecTimeOriginal', 'SubSecTimeDigitized']
            for key in subsec_keys:
                cmd.extend([f'-{key}={subseconds}'])
        else:
            cmd.extend(['-SubSecTimeOriginal=', '-SubSecTimeDigitized='])
        
        cmd.append(file_path)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Error updating metadata for {file_path}: {e}")
        print(f"ExifTool output: {e.stdout}")
        print(f"ExifTool error: {e.stderr}")

def generate_filename(oldest_date: datetime, subseconds: str, original_extension: str) -> str:
    date_str = oldest_date.strftime('%Y-%m-%d %H-%M-%S')
    if subseconds and subseconds != '000000':
        return f"{date_str}_ss{subseconds}{original_extension}"
    else:
        return f"{date_str}{original_extension}"

def resolve_collision(target_path: str) -> str:
    base, extension = os.path.splitext(target_path)
    counter = 2
    while os.path.exists(f"{base}_{counter}{extension}"):
        counter += 1
    return f"{base}_{counter}{extension}"

def move_and_rename_file(file_path: str, destination_root: str, 
                         metadata: Dict[str, Any], media_type: str) -> None:
    original_extension = os.path.splitext(file_path)[1]
    oldest_date = find_oldest_date(metadata, file_path)
    year_from_filename = oldest_date.strftime('%Y')
    month_from_filename = oldest_date.strftime('%m')
    subseconds = extract_subseconds(metadata)
    new_filename = generate_filename(oldest_date, subseconds, original_extension)

    friendly_media_type = {'art': 'Art', 'image': 'Photos', 'audio': 'Music', 
                           'video': 'Videos'}.get(media_type, "Unknown")
    target_directory = os.path.join(destination_root, friendly_media_type, 
                                    year_from_filename, month_from_filename)
    os.makedirs(target_directory, exist_ok=True)
    target_path = os.path.join(target_directory, new_filename)

    if os.path.exists(target_path):
        target_path = resolve_collision(target_path)

    shutil.move(file_path, target_path)

    formatted_date = new_filename.split('_')[0].replace('-', ':') + ":00"
    subseconds_from_name = re.search(r'_ss(\d+)', new_filename)
    subseconds_to_use = subseconds_from_name.group(1) if subseconds_from_name else None

    update_metadata(target_path, formatted_date, subseconds_to_use)

def process_file(args: Tuple[str, str]) -> Tuple[bool, str]:
    file_path, destination_root = args
    
    try:
        media_type = get_media_type(file_path)
        if media_type == 'unknown':
            return (False, f"Unsupported file type: {os.path.basename(file_path)}")
        
        metadata = extract_metadata(file_path)
        if not metadata:
            return (False, f"No metadata found: {os.path.basename(file_path)}")
        
        move_and_rename_file(file_path, destination_root, metadata, media_type)
        return (True, f"Processed: {os.path.basename(file_path)}")
    
    except Exception as e:
        error_files.append(file_path)
        return (False, f"Error processing {os.path.basename(file_path)}: {e}")

def main() -> None:
    global error_files
    error_files = []
    
    print("Basic Media Mover")
    print("----------------")
    
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Error: ExifTool is not installed or not in the PATH.")
        print("Please install ExifTool: https://exiftool.org/")
        
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", "ExifTool is not installed or not in the PATH.\n"
                            "Please install ExifTool: https://exiftool.org/")
        root.destroy()
        return
    
    source_directory = choose_directory("Select the Source Directory for processing")
    if not source_directory:
        print("No source directory selected, exiting...")
        return
    
    destination_directory = choose_directory("Select the Destination Directory for processed files")
    if not destination_directory:
        print("No destination directory selected, exiting...")
        return
    
    file_paths = []
    for root, _, files in os.walk(source_directory):
        for file in files:
            file_path = os.path.join(root, file)
            if get_media_type(file_path) != 'unknown':
                file_paths.append(file_path)
    
    if not file_paths:
        print("No supported files found in the source directory. Exiting.")
        
        root = Tk()
        root.withdraw()
        messagebox.showwarning("No Files Found", "No supported media files found in the source directory.")
        root.destroy()
        return
    
    print(f"Found {len(file_paths)} files in source directory.")
    num_cores = cpu_count()
    print(f"Using {num_cores} CPU cores for processing.")
    
    start_time = time.time()
    success_count = 0
    
    try:
        with Pool(num_cores) as pool:
            results = []
            for result in tqdm(pool.imap_unordered(process_file, 
                                                [(f, destination_directory) for f in file_paths]), 
                              total=len(file_paths), unit="files"):
                results.append(result)
                if result[0]:
                    success_count += 1
    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        elapsed_time = time.time() - start_time
        
        print("\nCleaning up empty directories...")
        remove_empty_directories(source_directory)
        
        print("\nProcessing complete!")
        print(f"Processed {len(file_paths)} files in {elapsed_time:.1f} seconds")
        print(f"Successfully processed: {success_count} files")
        
        if error_files:
            print(f"Errors encountered: {len(error_files)} files")
            print("See above for error details.")
        else:
            print("All files processed successfully.")
        
        root = Tk()
        root.withdraw()
        if error_files:
            messagebox.showinfo("Processing Complete", 
                               f"Processed {len(file_paths)} files\n"
                               f"Successfully processed: {success_count} files\n"
                               f"Errors: {len(error_files)} files")
        else:
            messagebox.showinfo("Processing Complete", 
                               f"All {len(file_paths)} files processed successfully!")
        root.destroy()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        root.destroy()