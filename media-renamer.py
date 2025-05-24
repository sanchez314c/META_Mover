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
# Script Name: media-renamer.py                                                   #
# 
# Author: sanchez314c@speedheathens.com                                          #
#                                              
# Date Created: 2025-01-24                                                       #
#
# Last Modified: 2025-01-24                                                      #
#
# Version: 1.1.0                                                                 #
#
# Description: Intelligent media file renaming tool based on metadata. Renames   #
#              files using creation dates and metadata information with          #
#              subsecond precision for avoiding collisions. Supports multiple    #
#              media formats including photos, videos, and audio files.          #
#
# Usage: python media-renamer.py                                                 #
#        Select source and destination folders through GUI dialogs               #
#
# Dependencies: exiftool (external), tkinter, tqdm                               #
#                                                                                  #
# GitHub: https://github.com/your-repo/metamover                                 #
#                                                                                  #
# Notes: Requires ExifTool to be installed separately. Particularly useful for   #
#        organizing photos exported from Apple Photos and other applications.    #
#                                                                                  #
####################################################################################

import os
import sys
import re
import json
import shutil
import subprocess
import time
import threading
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any, Set

# Third-party imports
try:
    from tkinter import Tk, filedialog, messagebox
    from tqdm import tqdm
except ImportError as e:
    missing_module = str(e).split("'")[1]
    print(f"Required module {missing_module} is missing. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", missing_module])
    print(f"Installed {missing_module}. Please restart the script.")
    sys.exit(1)

# Define media types and their extensions
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.heic', '.heif', 
                        '.raw', '.cr2', '.nef', '.arw', '.mp4', '.mov', '.mp3', '.wav']

# Global variables
processed_files = 0
total_files = 0
error_files = []
progress_lock = threading.Lock()


def update_progress() -> None:
    """Update the progress counters in a thread-safe way"""
    global processed_files
    with progress_lock:
        processed_files += 1


def check_exiftool() -> bool:
    """
    Check if exiftool is installed and available.
    
    Returns:
        True if exiftool is available, False otherwise
    """
    try:
        result = subprocess.run(['exiftool', '-ver'], 
                              capture_output=True, text=True, check=True)
        print(f"ExifTool version {result.stdout.strip()} found")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def extract_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a file using exiftool.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Metadata dictionary
    """
    try:
        result = subprocess.run(['exiftool', '-json', '-a', '-u', '-g1', file_path], 
                              capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)[0]
        return metadata
    except subprocess.CalledProcessError as e:
        print(f"Error extracting metadata from {file_path}: {e}")
        return {}
    except json.JSONDecodeError:
        print(f"Error parsing metadata from {file_path}")
        return {}


def extract_date_from_metadata(metadata: Dict[str, Any], file_path: str) -> Optional[datetime]:
    """
    Extract date from various metadata fields.
    
    Args:
        metadata: Metadata dictionary
        file_path: Path to the file for fallback
        
    Returns:
        Date as datetime object or None if not found
    """
    # Look in EXIF data
    date_fields = ['DateTimeOriginal', 'CreateDate', 'DateTimeCreated', 
                  'FileModifyDate', 'ModifyDate']
    
    for field in date_fields:
        if field in metadata:
            try:
                # Remove timezone if present (e.g., "+00:00")
                date_str = re.sub(r'[+-]\d{2}:\d{2}$', '', metadata[field])
                # Normalize format
                date_str = date_str.replace(':', ':', 2)  # Keep first two colons
                date_str = date_str.replace(':', '-', 2)  # Replace first two colons with hyphens
                # Parse with various formats
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H-%M-%S', '%Y:%m:%d %H:%M:%S'):
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
            except Exception:
                continue
    
    # If no date found in metadata, use file modification time
    try:
        return datetime.fromtimestamp(os.path.getmtime(file_path))
    except Exception:
        return None


def extract_subseconds(metadata: Dict[str, Any]) -> str:
    """
    Extract subsecond information from metadata.
    
    Args:
        metadata: Metadata dictionary
        
    Returns:
        Subsecond string or empty string if not found
    """
    subsec_fields = ['SubSecTimeOriginal', 'SubSecTime', 'SubSecTimeDigitized']
    
    for field in subsec_fields:
        if field in metadata and metadata[field]:
            return metadata[field].zfill(6)[:6]
    
    return ''


def generate_new_filename(file_path: str, metadata: Dict[str, Any]) -> str:
    """
    Generate a new filename based on metadata.
    
    Args:
        file_path: Original file path
        metadata: Metadata dictionary
        
    Returns:
        New filename
    """
    # Extract date and subseconds
    date = extract_date_from_metadata(metadata, file_path)
    subsec = extract_subseconds(metadata)
    
    # Get original extension
    _, ext = os.path.splitext(file_path)
    
    # Generate new filename
    if date:
        base = date.strftime('%Y-%m-%d_%H-%M-%S')
        if subsec:
            return f"{base}_{subsec}{ext}"
        else:
            return f"{base}{ext}"
    else:
        # If date extraction failed, keep original filename
        return os.path.basename(file_path)


def rename_file(args: Tuple[str, str]) -> Tuple[bool, str]:
    """
    Rename a file based on its metadata.
    
    Args:
        args: Tuple of (file_path, destination_dir)
        
    Returns:
        Tuple of (success, message)
    """
    file_path, destination_dir = args
    
    try:
        # Extract metadata
        metadata = extract_metadata(file_path)
        if not metadata:
            update_progress()
            return (False, f"Failed to extract metadata from {os.path.basename(file_path)}")
        
        # Generate new filename
        new_filename = generate_new_filename(file_path, metadata)
        
        # Create the target path
        target_path = os.path.join(destination_dir, new_filename)
        
        # Check for filename collision
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"
        
        # Copy the file to the new location
        shutil.copy2(file_path, target_path)
        
        update_progress()
        return (True, f"Renamed {os.path.basename(file_path)} -> {os.path.basename(target_path)}")
    
    except Exception as e:
        update_progress()
        return (False, f"Error processing {os.path.basename(file_path)}: {e}")


def choose_directory(title: str) -> str:
    """
    Show directory chooser dialog.
    
    Args:
        title: Dialog title
        
    Returns:
        Selected directory path
    """
    root = Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title=title)
    root.destroy()
    return directory


def get_files_to_process(source_dir: str) -> List[str]:
    """
    Get all supported files from the source directory.
    
    Args:
        source_dir: Source directory
        
    Returns:
        List of file paths
    """
    files = []
    for root, _, filenames in os.walk(source_dir):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                file_path = os.path.join(root, filename)
                files.append(file_path)
    return files


def process_files(source_dir: str, destination_dir: str) -> Dict[str, int]:
    """
    Process all files in the source directory.
    
    Args:
        source_dir: Source directory
        destination_dir: Destination directory
        
    Returns:
        Statistics dictionary
    """
    global total_files, processed_files, error_files
    
    # Reset counters
    processed_files = 0
    error_files = []
    
    # Get all files to process
    files = get_files_to_process(source_dir)
    total_files = len(files)
    
    if total_files == 0:
        return {'total': 0, 'success': 0, 'errors': 0}
    
    # Create list of arguments for the rename_file function
    args_list = [(file_path, destination_dir) for file_path in files]
    
    # Process files in parallel
    num_cores = cpu_count()
    results = []
    
    print(f"Processing {total_files} files using {num_cores} CPU cores...")
    
    with Pool(num_cores) as pool:
        for result in tqdm(pool.imap_unordered(rename_file, args_list), 
                         total=total_files, unit="files"):
            results.append(result)
    
    # Collect results
    success_count = 0
    for success, message in results:
        if success:
            success_count += 1
        else:
            error_files.append(message)
        print(message)
    
    return {
        'total': total_files,
        'success': success_count,
        'errors': len(error_files)
    }


def main() -> None:
    """Main function"""
    print("Media Renamer")
    print("-------------")
    
    # Check for exiftool
    if not check_exiftool():
        print("Error: ExifTool is not installed or not in the PATH.")
        print("Please install ExifTool: https://exiftool.org/")
        
        # Show error message
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", "ExifTool is not installed or not in the PATH.\n"
                           "Please install ExifTool: https://exiftool.org/")
        root.destroy()
        return
    
    # Select source directory
    source_dir = choose_directory("Select Source Directory")
    if not source_dir:
        print("No source directory selected, exiting...")
        return
    
    # Select destination directory
    destination_dir = choose_directory("Select Destination Directory")
    if not destination_dir:
        print("No destination directory selected, exiting...")
        return
    
    # Create destination directory if it doesn't exist
    os.makedirs(destination_dir, exist_ok=True)
    
    # Process files
    start_time = time.time()
    stats = process_files(source_dir, destination_dir)
    elapsed_time = time.time() - start_time
    
    # Show results
    print("\nProcessing complete!")
    print(f"Processed {stats['total']} files in {elapsed_time:.1f} seconds")
    print(f"Successfully renamed: {stats['success']} files")
    if stats['errors'] > 0:
        print(f"Errors: {stats['errors']} files")
    
    # Show completion message
    root = Tk()
    root.withdraw()
    messagebox.showinfo("Processing Complete", 
                       f"Processed {stats['total']} files\n"
                       f"Successfully renamed: {stats['success']} files\n"
                       f"Errors: {stats['errors']} files")
    root.destroy()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        
        # Show error message
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        root.destroy()