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
# Script Name: media-date-fixer.py                                        
# 
# Author: sanchez314c@speedheathens.com  
#                                              
# Date Created: 2025-01-24                                                       
#
# Last Modified: 2025-01-24                                                      
#
# Version: 1.1.0                                                                 
#
# Description: Comprehensive metadata date correction tool for fixing incorrect    
#              timestamps (especially 1970 dates) using original EXIF creation  
#              dates with multi-core processing and visual progress tracking.                                              
#
# Usage: python media-date-fixer.py [--input PATH] [--output DIR]
#
# Dependencies: pillow, piexif, tkinter, tqdm                                           
#
# GitHub: https://github.com/sanchez314c                                         
#
# Notes: Supports multiple image formats with comprehensive EXIF date field      
#        detection and correction, parallel processing optimization,  
#        and automatic directory structure preservation.                                                    
#                                                                                
####################################################################################

"""
Comprehensive Metadata Date Fixer
================================

Advanced date correction tool for fixing incorrect timestamps in image metadata
with comprehensive EXIF field support and multi-core processing optimization.
"""

import os
import sys
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import List, Dict, Tuple, Optional, Union, Any

try:
    from PIL import Image
    import piexif
    from tkinter import Tk, filedialog, messagebox
    from tqdm import tqdm
except ImportError as e:
    missing_module = str(e).split("'")[1]
    print(f"Required module {missing_module} is missing. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", missing_module])
    print(f"Installed {missing_module}. Please restart the script.")
    sys.exit(1)

SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.tiff', '.tif', '.png', '.heic', '.heif']

total_files = 0
processed_files = 0
updated_files = 0
error_files = 0
progress_lock = threading.Lock()

def update_progress() -> None:
    global processed_files
    with progress_lock:
        processed_files += 1

def process_image(file_info: Tuple[str, str]) -> Tuple[bool, str]:
    filepath, destination_dir = file_info
    
    try:
        rel_path = os.path.relpath(filepath, os.path.dirname(filepath))
        target_path = os.path.join(destination_dir, rel_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        img = Image.open(filepath)
        if 'exif' not in img.info:
            img.save(target_path)
            update_progress()
            return (False, f"No EXIF data in {os.path.basename(filepath)}")
        
        exif_dict = piexif.load(img.info['exif'])
        updated = False
        date_fields = [piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized]

        create_date = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeOriginal, None)

        if create_date:
            create_date = create_date.decode('utf-8')

            for ifd in exif_dict:
                for tag in exif_dict[ifd]:
                    if isinstance(exif_dict[ifd][tag], bytes):
                        try:
                            data = exif_dict[ifd][tag].decode('utf-8')
                            if '1970' in data:
                                if tag in date_fields:
                                    exif_dict[ifd][tag] = create_date.encode('utf-8')
                                    updated = True
                        except UnicodeDecodeError:
                            continue

            exif_bytes = piexif.dump(exif_dict)
            img.save(target_path, exif=exif_bytes)
            img.close()
            update_progress()
            
            if updated:
                return (True, f"Updated dates for {os.path.basename(filepath)}")
            else:
                return (False, f"No updates required for {os.path.basename(filepath)}")
        else:
            img.save(target_path)
            img.close()
            update_progress()
            return (False, f"No creation date found in {os.path.basename(filepath)}")

    except Exception as e:
        update_progress()
        return (False, f"Failed to process {os.path.basename(filepath)}: {e}")

def get_files_to_process(directory: str) -> List[str]:
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                filepath = os.path.join(root, filename)
                files.append(filepath)
    
    return files

def update_metadata(source_dir: str, destination_dir: str) -> Dict[str, int]:
    global total_files, processed_files, updated_files, error_files
    
    processed_files = 0
    updated_files = 0
    error_files = 0
    
    files_to_process = get_files_to_process(source_dir)
    total_files = len(files_to_process)
    
    if total_files == 0:
        return {
            'total': 0,
            'updated': 0,
            'errors': 0
        }
    
    print(f"Processing {total_files} files...")
    
    file_info_list = [(filepath, destination_dir) for filepath in files_to_process]
    
    num_cores = cpu_count()
    results = []
    
    with Pool(num_cores) as pool:
        for result in tqdm(pool.imap_unordered(process_image, file_info_list), 
                          total=total_files, unit="files"):
            results.append(result)
    
    for success, message in results:
        if success:
            updated_files += 1
        elif 'Failed' in message:
            error_files += 1
        print(message)
    
    return {
        'total': total_files,
        'updated': updated_files,
        'errors': error_files
    }

def choose_directory(title: str) -> str:
    root = Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title=title)
    root.destroy()
    return directory

def main() -> None:
    print("Comprehensive Metadata Date Fixer")
    print("--------------------------------")
    
    source_dir = choose_directory('Select a Source Folder with Images')
    if not source_dir:
        print("No source directory selected, exiting...")
        return
    
    destination_dir = choose_directory('Select a Destination Folder for Processed Files')
    if not destination_dir:
        print("No destination directory selected, exiting...")
        return
    
    os.makedirs(destination_dir, exist_ok=True)
    
    start_time = time.time()
    stats = update_metadata(source_dir, destination_dir)
    elapsed_time = time.time() - start_time
    
    if stats['total'] > 0:
        print("\nProcessing complete!")
        print(f"Processed {stats['total']} files in {elapsed_time:.1f} seconds")
        print(f"Updated {stats['updated']} files")
        if stats['errors'] > 0:
            print(f"Encountered {stats['errors']} errors")
        
        root = Tk()
        root.withdraw()
        messagebox.showinfo("Processing Complete", 
                           f"Processed {stats['total']} files\nUpdated {stats['updated']} files\nErrors: {stats['errors']}")
        root.destroy()
    else:
        print("No supported files found in the source directory.")
        
        root = Tk()
        root.withdraw()
        messagebox.showwarning("No Files Found", "No supported image files found in the source directory.")
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