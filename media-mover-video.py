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
# Script Name: media-mover-video.py                                        
# 
# Author: sanchez314c@speedheathens.com  
#                                              
# Date Created: 2025-01-24                                                       
#
# Last Modified: 2025-01-24                                                      
#
# Version: 1.0.0                                                                 
#
# Description: Video-focused metadata management tool with intelligent date    
#              extraction from multiple sources and comprehensive video format  
#              support with multi-threaded processing optimization.                                              
#
# Usage: python media-mover-video.py [--input PATH] [--output DIR]
#
# Dependencies: exiftool, tkinter, multiprocessing                                           
#
# GitHub: https://github.com/sanchez314c                                         
#
# Notes: Specialized for video formats (MP4, MPG, MPEG, 3GP, AVI, MOV, M4V),      
#        intelligent filename pattern detection, year-based organization,  
#        and comprehensive metadata updating with collision handling.                                                    
#                                                                                
####################################################################################

"""
Video Metadata Mover and Organizer
=================================

Specialized video metadata management tool with intelligent multi-source date detection
and comprehensive video format support with optimized processing.
"""

import os
import re
import subprocess
import shutil
import logging
import json
from datetime import datetime
from multiprocessing import Pool, cpu_count
from tkinter import filedialog, Tk, messagebox
from typing import Optional, Dict, List

SUPPORTED_EXTENSIONS = ['.mp4', '.mpg', '.mpeg', '.3gp', '.avi', '.mov', '.m4v']
FILENAME_DATE_PATTERN = re.compile(r'(\d{4})[-_](\d{2})[-_](\d{2})[_\s]*(\d{2})[-_](\d{2})[-_](\d{2})')
DATE_CUTOFF = datetime(1989, 12, 31)
NUM_THREADS = max(1, cpu_count() - 1)

def setup_logging(log_file: str = 'video_metadata_mover.log') -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def choose_directory(title: str) -> str:
    root = Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title=title)
    if not directory:
        logging.warning(f"No directory selected for: {title}")
    return directory

def extract_metadata_with_exiftool(file_path: str) -> Dict:
    try:
        cmd = ['exiftool', '-json', '-extractEmbedded', '-dateFormat', '%Y:%m:%d %H:%M:%S', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)[0] if result.stdout else {}
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logging.error(f"Metadata extraction failed for {file_path}: {e}")
        return {}

def extract_date_from_filename(file_name: str) -> Optional[datetime]:
    match = FILENAME_DATE_PATTERN.search(file_name)
    try:
        return datetime(*map(int, match.groups())) if match else None
    except (ValueError, AttributeError):
        return None

def get_oldest_date(tags: Dict, filename_date: Optional[datetime]) -> Optional[datetime]:
    dates = [filename_date] if filename_date else []
    
    date_fields = [
        'CreateDate', 'DateTimeOriginal', 'ModifyDate',
        'MediaCreateDate', 'TrackCreateDate', 'FileModifyDate'
    ]

    for field in date_fields:
        if field in tags:
            try:
                date_str = str(tags[field])
                date = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                if date > DATE_CUTOFF:
                    dates.append(date)
            except (ValueError, TypeError):
                continue

    return min(dates) if dates else None

def get_subseconds(tags: Dict) -> str:
    subsec_pattern = re.compile(r'(\d{1,6})')
    subsec_fields = ['SubSecTime', 'SubSecTimeOriginal', 'SubSecTimeDigitized']
    
    for field in subsec_fields:
        if field in tags:
            match = subsec_pattern.search(str(tags[field]))
            if match:
                return match.group(1).zfill(6)
    return ''

def update_metadata(file_path: str) -> None:
    try:
        if extract_date_from_filename(os.path.basename(file_path)):
            title = os.path.splitext(os.path.basename(file_path))[0]
            subprocess.run(['exiftool', f'-XMP:Title={title}', '-overwrite_original', file_path], check=True)

        subprocess.run([
            'exiftool',
            '-v3',
            '-progress',
            '-wm', 'wcg',
            '-AllDates<Filename',
            '-FileModifyDate<Filename',
            '-DateTimeOriginal<Filename',
            '-Time:all<DateTimeOriginal',
            '-TrackCreateDate<DateTimeOriginal',
            '-MediaCreateDate<DateTimeOriginal',
            '-overwrite_original',
            file_path
        ], check=True)

    except subprocess.SubprocessError as e:
        logging.error(f"Metadata update failed for {file_path}: {e}")
        raise

def move_and_rename_file(args: tuple) -> None:
    file_path, destination_root, exceptions_dir = args
    
    try:
        logging.info(f"Processing: {file_path}")
        
        tags = extract_metadata_with_exiftool(file_path)
        filename_date = extract_date_from_filename(os.path.basename(file_path))
        oldest_date = get_oldest_date(tags, filename_date)
        subsec_str = get_subseconds(tags)

        if oldest_date:
            year_folder = os.path.join(destination_root, str(oldest_date.year))
            os.makedirs(year_folder, exist_ok=True)

            base_name = oldest_date.strftime("%Y-%m-%d_%H-%M-%S")
            extension = os.path.splitext(file_path)[1].lower()
            new_name = f"{base_name}{('-' + subsec_str) if subsec_str else ''}{extension}"
            new_path = os.path.join(year_folder, new_name)

            counter = 1
            while os.path.exists(new_path):
                new_name = f"{base_name}-{counter}{extension}"
                new_path = os.path.join(year_folder, new_name)
                counter += 1

            shutil.move(file_path, new_path)
            logging.info(f"Moved to: {new_path}")
            update_metadata(new_path)
        else:
            move_to_exceptions(file_path, exceptions_dir)

    except Exception as e:
        logging.error(f"Processing failed for {file_path}: {e}")
        move_to_exceptions(file_path, exceptions_dir)

def move_to_exceptions(file_path: str, exceptions_dir: str) -> None:
    try:
        os.makedirs(exceptions_dir, exist_ok=True)
        dest_path = os.path.join(exceptions_dir, os.path.basename(file_path))
        shutil.move(file_path, dest_path)
        logging.warning(f"Moved to exceptions: {dest_path}")
    except Exception as e:
        logging.error(f"Failed to move to exceptions: {file_path}: {e}")

def main() -> None:
    try:
        setup_logging()
        
        source_dir = choose_directory("Select Source Directory")
        destination_dir = choose_directory("Select Destination Directory")
        exceptions_dir = choose_directory("Select Exceptions Directory")

        if not all([source_dir, destination_dir, exceptions_dir]):
            logging.error("Directory selection cancelled")
            return

        file_paths = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in SUPPORTED_EXTENSIONS:
                    file_paths.append(os.path.join(root, file))

        if not file_paths:
            messagebox.showwarning("No Files", "No supported video files found.")
            return

        with Pool(NUM_THREADS) as pool:
            args = [(path, destination_dir, exceptions_dir) for path in file_paths]
            pool.map(move_and_rename_file, args)

        messagebox.showinfo("Complete", "Video file processing completed successfully!")

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()