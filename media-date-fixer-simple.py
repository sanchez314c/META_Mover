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
# Script Name: media-date-fixer-simple.py                                         #
# 
# Author: sanchez314c@speedheathens.com                                          #
#                                              
# Date Created: 2025-01-24                                                       #
#
# Last Modified: 2025-01-24                                                      #
#
# Version: 1.1.0                                                                 #
#
# Description: Simple metadata date correction tool for image files. Fixes       #
#              incorrect dates (like 1970) in EXIF metadata by updating them     #
#              with correct creation dates from other metadata fields. Features  #
#              GUI directory selection and batch processing capabilities.        #
#
# Usage: python media-date-fixer-simple.py                                       #
#        Select source and destination folders through GUI dialogs               #
#
# Dependencies: PIL (Pillow), piexif, tkinter, tqdm                              #
#                                                                                  #
# GitHub: https://github.com/your-repo/metamover                                 #
#                                                                                  #
# Notes: Lightweight alternative to the comprehensive media-date-fixer.py.       #
#        Only processes JPEG images. Uses multi-threading for performance.       #
#                                                                                  #
####################################################################################

import os
import sys
import subprocess
import threading
import time
from datetime import datetime
from multiprocessing import Pool, cpu_count
from typing import List, Dict, Tuple, Optional, Union, Any

# Third-party imports
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

# Define supported file extensions
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg']

# Global variables for tracking progress
total_files = 0
processed_files = 0
updated_files = 0
error_files = 0
progress_lock = threading.Lock()

def update_progress() -> None:
    """Update the progress counters in a thread-safe way"""
    global processed_files
    with progress_lock:
        processed_files += 1

def process_image(file_info: Tuple[str, str]) -> Tuple[bool, str]:
    """
    Process an image file to fix incorrect dates in metadata.
    
    Args:
        file_info: Tuple of (filepath, destination_dir)
        
    Returns:
        Tuple of (success, message)
    """
    filepath, destination_dir = file_info
    
    try:
        # Create the target filename and directories
        target_path = os.path.join(destination_dir, os.path.basename(filepath))
        
        # Open and process the image
        img = Image.open(filepath)
        if 'exif' not in img.info:
            # Copy file without changes if no EXIF data
            img.save(target_path)
            update_progress()
            return (False, f"No EXIF data in {os.path.basename(filepath)}")
        
        exif_dict = piexif.load(img.info['exif'])
        updated = False
        date_fields = [piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized]

        # Retrieve the creation date from Exif data if available
        create_date = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeOriginal, None)

        if create_date:
            create_date = create_date.decode('utf-8')

            # Check and update all relevant tags
            for ifd in exif_dict:
                for tag in exif_dict[ifd]:
                    if isinstance(exif_dict[ifd][tag], bytes):
                        try:
                            data = exif_dict[ifd][tag].decode('utf-8')
                            if '1970' in data:
                                # Check if the tag is a date field to ensure correct format
                                if tag in date_fields:
                                    exif_dict[ifd][tag] = create_date.encode('utf-8')
                                    updated = True
                        except UnicodeDecodeError:
                            # Skip binary data that can't be decoded as UTF-8
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
            # No creation date found, just copy the file
            img.save(target_path)
            img.close()
            update_progress()
            return (False, f"No creation date found in {os.path.basename(filepath)}")

    except Exception as e:
        update_progress()
        return (False, f"Failed to process {os.path.basename(filepath)}: {e}")

def get_files_to_process(directory: str) -> List[str]:
    """
    Get all supported files in the directory.
    
    Args:
        directory: Directory to scan
        
    Returns:
        List of file paths
    """
    files = []
    for filename in os.listdir(directory):
        if any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                files.append(filepath)
    
    return files

def update_metadata(source_dir: str, destination_dir: str) -> Dict[str, int]:
    """
    Process all image files in the source directory and save to destination.
    
    Args:
        source_dir: Source directory
        destination_dir: Destination directory
        
    Returns:
        Dictionary with statistics
    """
    global total_files, processed_files, updated_files, error_files
    
    # Reset counters
    processed_files = 0
    updated_files = 0
    error_files = 0
    
    # Get all files to process
    files_to_process = get_files_to_process(source_dir)
    total_files = len(files_to_process)
    
    if total_files == 0:
        return {
            'total': 0,
            'updated': 0,
            'errors': 0
        }
    
    # Create a progress bar
    print(f"Processing {total_files} files...")
    
    # Create a list of file information for the processing function
    file_info_list = [(filepath, destination_dir) for filepath in files_to_process]
    
    # Process files in parallel
    num_cores = cpu_count()
    results = []
    
    with Pool(num_cores) as pool:
        for result in tqdm(pool.imap_unordered(process_image, file_info_list), 
                          total=total_files, unit="files"):
            results.append(result)
    
    # Collect results
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
    """Show a directory chooser dialog and return the selected path."""
    root = Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title=title)
    root.destroy()
    return directory

def main() -> None:
    """Main function to run the script."""
    print("Simple Metadata Date Fix Tool")
    print("----------------------------")
    
    # Select source directory
    source_dir = choose_directory('Select a Source Folder with Images')
    if not source_dir:
        print("No source directory selected, exiting...")
        return
    
    # Select destination directory
    destination_dir = choose_directory('Select a Destination Folder for Processed Files')
    if not destination_dir:
        print("No destination directory selected, exiting...")
        return
    
    # Create destination directory if it doesn't exist
    os.makedirs(destination_dir, exist_ok=True)
    
    # Update metadata
    start_time = time.time()
    stats = update_metadata(source_dir, destination_dir)
    elapsed_time = time.time() - start_time
    
    # Show results
    if stats['total'] > 0:
        print("\nProcessing complete!")
        print(f"Processed {stats['total']} files in {elapsed_time:.1f} seconds")
        print(f"Updated {stats['updated']} files")
        if stats['errors'] > 0:
            print(f"Encountered {stats['errors']} errors")
        
        # Show completion message
        root = Tk()
        root.withdraw()
        messagebox.showinfo("Processing Complete", 
                           f"Processed {stats['total']} files\nUpdated {stats['updated']} files\nErrors: {stats['errors']}")
        root.destroy()
    else:
        print("No supported files found in the source directory.")
        
        # Show error message
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
        
        # Show error message
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        root.destroy()