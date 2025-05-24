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
# Script Name: media-tags-report.py                                               #
# 
# Author: sanchez314c@speedheathens.com                                          #
#                                              
# Date Created: 2025-01-24                                                       #
#
# Last Modified: 2025-01-24                                                      #
#
# Version: 1.1.0                                                                 #
#
# Description: Comprehensive metadata tag reporting tool for media collections.   #
#              Scans directories and generates detailed reports of all metadata   #
#              tags found across various media formats. Supports both text and   #
#              CSV export formats for analysis and documentation purposes.        #
#
# Usage: python media-tags-report.py                                             #
#        Select source directory and output file through GUI dialogs             #
#
# Dependencies: exiftool (external), tkinter, tqdm                               #
#                                                                                  #
# GitHub: https://github.com/your-repo/metamover                                 #
#                                                                                  #
# Notes: Requires ExifTool for comprehensive metadata extraction. Generates      #
#        organized reports by tag categories with export options for analysis.   #
#                                                                                  #
####################################################################################

import os
import sys
import json
import subprocess
import time
import threading
import csv
from datetime import datetime
from multiprocessing import Pool, cpu_count, Manager
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any, Set

# Third-party imports
try:
    from tkinter import Tk, filedialog, messagebox, StringVar
    from tkinter.ttk import Progressbar
    from tqdm import tqdm
except ImportError as e:
    missing_module = str(e).split("'")[1]
    print(f"Required module {missing_module} is missing. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", missing_module])
    print(f"Installed {missing_module}. Please restart the script.")
    sys.exit(1)

# Global variables
processed_files = 0
total_files = 0
progress_lock = threading.Lock()

# Define media types and their extensions
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.heic', '.heif', 
                        '.raw', '.cr2', '.nef', '.arw', '.mp4', '.mov', '.mp3', '.wav']


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


def extract_tags(file_path: str, unique_tags: Dict[str, Set[str]]) -> Tuple[bool, str]:
    """
    Extract metadata tags from a file and update the unique tags dictionary.
    
    Args:
        file_path: Path to the file
        unique_tags: Dictionary of unique tags
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Run exiftool to extract all metadata
        result = subprocess.run(['exiftool', '-json', '-a', '-u', '-g1', file_path], 
                              capture_output=True, text=True, check=True)
        
        # Parse the JSON output
        data = json.loads(result.stdout)
        if not data:
            update_progress()
            return (False, f"No metadata found in {os.path.basename(file_path)}")
        
        # Extract all tag names and add to the unique tags set
        metadata = data[0]
        for group, tags in metadata.items():
            if group == 'SourceFile':
                continue
                
            if isinstance(tags, dict):
                for tag_name in tags.keys():
                    with progress_lock:
                        if group not in unique_tags:
                            unique_tags[group] = set()
                        unique_tags[group].add(tag_name)
        
        update_progress()
        return (True, f"Processed {os.path.basename(file_path)}")
    
    except subprocess.CalledProcessError as e:
        update_progress()
        return (False, f"Error processing {os.path.basename(file_path)}: {e}")
    except json.JSONDecodeError:
        update_progress()
        return (False, f"Error parsing metadata from {os.path.basename(file_path)}")
    except Exception as e:
        update_progress()
        return (False, f"Unexpected error processing {os.path.basename(file_path)}: {e}")


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


def choose_output_file(title: str, default_filename: str) -> str:
    """
    Show file save dialog.
    
    Args:
        title: Dialog title
        default_filename: Default filename
        
    Returns:
        Selected file path
    """
    root = Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        title=title,
        initialfile=default_filename,
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
    )
    root.destroy()
    return file_path


def find_files(directory: str) -> List[str]:
    """
    Find all supported files in the directory and its subdirectories.
    
    Args:
        directory: Directory to scan
        
    Returns:
        List of file paths
    """
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                files.append(os.path.join(root, filename))
    return files


def generate_text_report(tags: Dict[str, Set[str]], output_file: str) -> None:
    """
    Generate a text report of metadata tags.
    
    Args:
        tags: Dictionary of metadata tags
        output_file: Output file path
    """
    with open(output_file, 'w') as f:
        f.write("Comprehensive Metadata Tags Report\n")
        f.write("=================================\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Summary statistics
        total_groups = len(tags)
        total_tags = sum(len(tag_set) for tag_set in tags.values())
        f.write(f"Summary:\n")
        f.write(f"- Total metadata groups: {total_groups}\n")
        f.write(f"- Total unique tags: {total_tags}\n\n")
        
        # Tags by group
        f.write("Metadata Groups and Tags:\n")
        f.write("========================\n\n")
        
        for group in sorted(tags.keys()):
            tag_set = tags[group]
            f.write(f"[{group}] ({len(tag_set)} tags)\n")
            f.write("-" * (len(group) + 20) + "\n")
            for tag in sorted(tag_set):
                f.write(f"  {tag}\n")
            f.write("\n")


def generate_csv_report(tags: Dict[str, Set[str]], output_file: str) -> None:
    """
    Generate a CSV report of metadata tags.
    
    Args:
        tags: Dictionary of metadata tags
        output_file: Output file path
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Group', 'Tag', 'Group_Tag_Count', 'Total_Groups', 'Total_Tags'])
        
        total_groups = len(tags)
        total_tags = sum(len(tag_set) for tag_set in tags.values())
        
        for group in sorted(tags.keys()):
            tag_set = tags[group]
            for tag in sorted(tag_set):
                writer.writerow([group, tag, len(tag_set), total_groups, total_tags])


def generate_report(tags: Dict[str, Set[str]], output_file: str) -> None:
    """
    Generate a report in the appropriate format based on file extension.
    
    Args:
        tags: Dictionary of metadata tags
        output_file: Output file path
    """
    if output_file.lower().endswith('.csv'):
        generate_csv_report(tags, output_file)
    else:
        generate_text_report(tags, output_file)


def main() -> None:
    """Main function"""
    global total_files, processed_files
    
    print("Comprehensive Metadata Tags Reporter")
    print("----------------------------------")
    
    # Check if exiftool is available
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
    source_dir = choose_directory("Select Directory with Media Files")
    if not source_dir:
        print("No directory selected, exiting...")
        return
    
    # Find all supported files
    print("Scanning for media files...")
    files = find_files(source_dir)
    total_files = len(files)
    
    if total_files == 0:
        print("No supported media files found in the selected directory.")
        
        # Show warning message
        root = Tk()
        root.withdraw()
        messagebox.showwarning("No Files Found", "No supported media files found in the selected directory.")
        root.destroy()
        return
    
    print(f"Found {total_files} media files.")
    
    # Select output file
    default_filename = f"metadata_tags_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    output_file = choose_output_file("Save Report As", default_filename)
    if not output_file:
        print("No output file selected, exiting...")
        return
    
    # Process files in parallel
    print("Extracting metadata tags...")
    
    # Create shared dictionary for tags
    manager = Manager()
    unique_tags = manager.dict()
    
    # Process files
    start_time = time.time()
    errors = []
    
    with Pool(cpu_count()) as pool:
        args = [(file_path, unique_tags) for file_path in files]
        
        for result in tqdm(pool.starmap(extract_tags, args), total=total_files, unit="files"):
            success, message = result
            if not success:
                errors.append(message)
    
    # Convert manager dict to regular dict with sets
    tags_dict = {group: set(tags) for group, tags in unique_tags.items()}
    
    # Generate report
    print("Generating report...")
    generate_report(tags_dict, output_file)
    
    # Show results
    elapsed_time = time.time() - start_time
    print("\nReport generation complete!")
    print(f"Processed {total_files} files in {elapsed_time:.2f} seconds")
    print(f"Found {len(tags_dict)} metadata groups with {sum(len(tags) for tags in tags_dict.values())} unique tags")
    print(f"Report saved to: {output_file}")
    
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            print(f"- {error}")
        if len(errors) > 5:
            print(f"- ...and {len(errors) - 5} more")
    
    # Show completion message
    root = Tk()
    root.withdraw()
    messagebox.showinfo("Report Generation Complete", 
                      f"Processed {total_files} files\n"
                      f"Found {sum(len(tags) for tags in tags_dict.values())} unique metadata tags\n"
                      f"Report saved to:\n{output_file}")
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