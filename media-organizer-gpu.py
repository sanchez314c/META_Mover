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
# Script Name: media-organizer-gpu.py                                             #
# 
# Author: sanchez314c@speedheathens.com                                          #
#                                              
# Date Created: 2025-01-24                                                       #
#
# Last Modified: 2025-01-24                                                      #
#
# Version: 1.1.0                                                                 #
#
# Description: Advanced media organizer with GPU acceleration and deep metadata   #
#              recovery. Features Metal framework optimization for macOS,         #
#              sophisticated file organization, and enhanced metadata extraction  #
#              capabilities for corrupted or minimal metadata situations.         #
#
# Usage: python media-organizer-gpu.py                                           #
#        Select source and destination folders through GUI dialogs               #
#
# Dependencies: PIL, OpenCV, numpy, MoviePy (optional), Metal (macOS), exiftool  #
#                                                                                  #
# GitHub: https://github.com/your-repo/metamover                                 #
#                                                                                  #
# Notes: Requires ExifTool and GPU acceleration support. Metal framework for     #
#        macOS GPU optimization. Includes deep metadata recovery for files with  #
#        minimal or corrupted metadata.                                           #
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
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any, Set

# Third-party imports
try:
    from PIL import Image
    import numpy as np
    import cv2
    from tkinter import Tk, filedialog, messagebox
    from tqdm import tqdm
    
    # Optional imports
    try:
        import moviepy.editor as mp
        MOVIEPY_AVAILABLE = True
    except ImportError:
        print("MoviePy not available. Video processing features will be limited.")
        MOVIEPY_AVAILABLE = False
    
    # Check for GPU acceleration
    GPU_ACCELERATION = False
    try:
        # Only try to import Metal on macOS
        if sys.platform == 'darwin':
            from Metal import *
            from MetalKit import *
            from MetalPerformanceShaders import *
            GPU_ACCELERATION = True
            print("Metal GPU acceleration enabled.")
    except ImportError:
        print("Metal framework not available. Using CPU processing only.")
        GPU_ACCELERATION = False
except ImportError as e:
    missing_module = str(e).split("'")[1]
    print(f"Required module {missing_module} is missing. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", missing_module])
    print(f"Installed {missing_module}. Please restart the script.")
    sys.exit(1)

# Global variables
processed_files: Set[str] = set()
error_files: List[Tuple[str, str]] = []

# Define media types and their extensions
MEDIA_TYPES = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif', 
              '.raw', '.dng', '.cr2', '.nef', '.arw'],
    'video': ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'],
    'audio': ['.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.aiff', '.alac']
}


class MetalOptimizer:
    """Metal framework optimization for macOS GPU acceleration."""
    
    def __init__(self, metal_device):
        """Initialize Metal optimizer with the given device."""
        self.device = metal_device
        self.heaps = []
        self.command_queues = []
        self.shared_event_listener = None
        self.initialize_metal_environment()

    def initialize_metal_environment(self):
        """Set up Metal environment for processing."""
        if not self.device:
            return
            
        self.initialize_heaps()
        self.create_command_queues()
        self.setup_event_listener()
        self.initialize_pipeline_states()

    def initialize_heaps(self):
        """Initialize memory heaps for Metal processing."""
        if not self.device:
            return
            
        try:
            main_heap_descriptor = mtl.MTLHeapDescriptor.alloc().init()
            main_heap_descriptor.size = 512 * 1024 * 1024  # 512MB heap
            main_heap_descriptor.storageMode = mtl.MTLStorageModePrivate
            self.heaps.append(self.device.newHeapWithDescriptor(main_heap_descriptor))

            texture_heap_descriptor = mtl.MTLHeapDescriptor.alloc().init()
            texture_heap_descriptor.size = 256 * 1024 * 1024  # 256MB heap
            texture_heap_descriptor.storageMode = mtl.MTLStorageModePrivate
            texture_heap_descriptor.type = mtl.MTLHeapTypeTexture
            self.heaps.append(self.device.newHeapWithDescriptor(texture_heap_descriptor))
        except Exception as e:
            print(f"Metal heap initialization failed: {e}")

    def create_command_queues(self):
        """Create Metal command queues for processing."""
        if not self.device:
            return
            
        try:
            main_queue = self.device.newCommandQueue()
            main_queue.setExecutionEnabled(True)
            self.command_queues.append(main_queue)

            background_queue = self.device.newCommandQueue()
            background_queue.setExecutionEnabled(True)
            self.command_queues.append(background_queue)
        except Exception as e:
            print(f"Metal command queue creation failed: {e}")

    def setup_event_listener(self):
        """Set up event listener for Metal events."""
        if not self.device:
            return
            
        try:
            self.shared_event_listener = self.device.newSharedEventListener()
            self.shared_event_listener.setEventHandler(self.handle_gpu_event)
        except Exception as e:
            print(f"Metal event listener setup failed: {e}")

    def initialize_pipeline_states(self):
        """Initialize Metal pipeline states."""
        if not self.device:
            return
            
        try:
            self.render_pipeline_state = self.create_render_pipeline_state()
            self.compute_pipeline_state = self.create_compute_pipeline_state()
        except Exception as e:
            print(f"Metal pipeline state initialization failed: {e}")

    def create_render_pipeline_state(self):
        """Create render pipeline state for Metal."""
        if not self.device:
            return None
            
        try:
            descriptor = mtl.MTLRenderPipelineDescriptor.alloc().init()
            descriptor.sampleCount = 1
            descriptor.colorAttachments[0].pixelFormat = mtl.MTLPixelFormatBGRA8Unorm
            return self.device.newRenderPipelineStateWithDescriptor(descriptor)
        except Exception as e:
            print(f"Metal render pipeline creation failed: {e}")
            return None

    def create_compute_pipeline_state(self):
        """Create compute pipeline state for Metal."""
        if not self.device:
            return None
            
        try:
            descriptor = mtl.MTLComputePipelineDescriptor.alloc().init()
            return self.device.newComputePipelineStateWithDescriptor(descriptor)
        except Exception as e:
            print(f"Metal compute pipeline creation failed: {e}")
            return None

    def handle_gpu_event(self, event):
        """Handle Metal GPU events."""
        if not self.device:
            return
            
        try:
            if event.type == mtl.MTLEventTypeMemoryPressure:
                self.optimize_memory_usage()
        except Exception as e:
            print(f"Metal GPU event handling failed: {e}")

    def optimize_memory_usage(self):
        """Optimize Metal memory usage."""
        if not self.device:
            return
            
        try:
            for heap in self.heaps:
                heap.purgeableState = mtl.MTLPurgeableStateEmpty
            self.device.newHeapGarbageCollectorWithDescriptor(None)
        except Exception as e:
            print(f"Metal memory optimization failed: {e}")


class GPUAccelerator:
    """GPU acceleration for image and video processing."""
    
    def __init__(self):
        """Initialize GPU accelerator."""
        self.device = None
        self.context = None
        self.queue = None
        self.metal_optimizer = None
        self.metal_device = None
        self.initialize_gpu()

    def initialize_gpu(self):
        """Initialize GPU acceleration if available."""
        if not GPU_ACCELERATION:
            return
            
        try:
            self.metal_device = mtl.MTLCreateSystemDefaultDevice()
            if self.metal_device:
                self.metal_optimizer = MetalOptimizer(self.metal_device)
                print(f"GPU Initialized: {self.metal_device.name} with Metal optimizations")
        except Exception as e:
            print(f"GPU initialization failed: {e}. Falling back to CPU.")
            self.metal_device = None

    def process_image_gpu(self, image_data):
        """
        Process image using GPU acceleration.
        
        Args:
            image_data: Image data as numpy array
            
        Returns:
            Processed image data
        """
        if not self.metal_device or not GPU_ACCELERATION:
            return image_data

        try:
            texture_descriptor = mtl.MTLTextureDescriptor.texture2DDescriptor(
                pixelFormat=mtl.MTLPixelFormatBGRA8Unorm,
                width=image_data.shape[1],
                height=image_data.shape[0],
                mipmapped=False
            )
            texture_descriptor.usage = (mtl.MTLTextureUsageShaderRead | 
                                       mtl.MTLTextureUsageShaderWrite | 
                                       mtl.MTLTextureUsageRenderTarget)
            texture_descriptor.storageMode = mtl.MTLStorageModePrivate

            texture = self.metal_optimizer.heaps[1].newTextureWithDescriptor(texture_descriptor)
            output_texture = self.metal_optimizer.heaps[1].newTextureWithDescriptor(texture_descriptor)

            command_buffer = self.metal_optimizer.command_queues[0].commandBuffer()
            
            kernel = mps.MPSImageGaussianBlur.alloc().initWithDevice(self.metal_device)
            kernel.encode(commandBuffer=command_buffer,
                         sourceTexture=texture,
                         destinationTexture=output_texture)

            command_buffer.commit()
            command_buffer.waitUntilCompleted()

            return np.array(output_texture)
        except Exception as e:
            print(f"GPU processing failed: {e}. Using CPU fallback.")
            return image_data

    def process_video_gpu(self, video_data):
        """
        Process video using GPU acceleration.
        
        Args:
            video_data: Video data
            
        Returns:
            Processed video data
        """
        if not self.metal_device or not GPU_ACCELERATION:
            return video_data

        try:
            command_buffer = self.metal_optimizer.command_queues[1].commandBuffer()
            video_processing_descriptor = mtl.MTLComputePipelineDescriptor.alloc().init()
            video_processing_state = self.metal_device.newComputePipelineStateWithDescriptor(
                video_processing_descriptor
            )

            encoder = command_buffer.computeCommandEncoder()
            encoder.setComputePipelineState(video_processing_state)
            encoder.dispatchThreadgroups(video_data.shape, threadsPerThreadgroup=(16, 16, 1))
            encoder.endEncoding()

            command_buffer.commit()
            command_buffer.waitUntilCompleted()

            return video_data
        except Exception as e:
            print(f"Video GPU processing failed: {e}. Using CPU fallback.")
            return video_data


class DeepMetadataRecovery:
    """Deep metadata recovery for files with minimal or corrupted metadata."""
    
    def __init__(self, gpu_accelerator=None):
        """Initialize deep metadata recovery with optional GPU acceleration."""
        self.gpu = gpu_accelerator
        self.known_patterns = self.load_known_patterns()
        self.temporal_patterns = self.initialize_temporal_patterns()

    def load_known_patterns(self):
        """Load known binary patterns for metadata recovery."""
        return {
            'exif': [b'Exif\x00\x00', b'MM\x00*', b'II*\x00'],
            'xmp': [b'<?xpacket', b'<x:xmpmeta'],
            'icc': [b'acsp'],
            'maker_notes': {
                'canon': [b'CANON'],
                'nikon': [b'Nikon'],
                'sony': [b'SONY'],
                'apple': [b'Apple']
            }
        }

    def initialize_temporal_patterns(self):
        """Initialize temporal patterns for date extraction."""
        return {
            'date_patterns': [
                r'\d{4}[:-]\d{2}[:-]\d{2}',
                r'\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}',
                r'\d{8}_\d{6}'
            ],
            'subsecond_patterns': [
                r'\.\d{1,6}',
                r'_\d{6}',
                r'subsec\d{6}'
            ]
        }

    def deep_scan(self, file_path):
        """
        Perform deep metadata scan on a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Recovered metadata
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            metadata_layers = {
                'exif': self.recover_exif(file_path),
                'xmp': self.recover_xmp(file_data),
                'filesystem': self.get_filesystem_metadata(file_path),
                'binary': self.scan_binary_patterns(file_data),
                'maker_notes': self.extract_maker_notes(file_data)
            }

            if self.gpu and self.is_image_file(file_path):
                try:
                    img = cv2.imread(file_path)
                    if img is not None:
                        metadata_layers['image_analysis'] = self.gpu.process_image_gpu(img)
                except Exception as e:
                    print(f"Image analysis failed: {e}")

            return self.merge_metadata_layers(metadata_layers)
        except Exception as e:
            print(f"Deep scan error: {e}")
            return {}

    def recover_exif(self, file_path):
        """
        Recover EXIF metadata using exiftool.
        
        Args:
            file_path: Path to the file
            
        Returns:
            EXIF metadata
        """
        try:
            result = subprocess.run(
                ['exiftool', '-json', '-all', file_path],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)[0] if result.stdout else {}
        except Exception:
            return {}

    def recover_xmp(self, file_data):
        """
        Recover XMP metadata from binary data.
        
        Args:
            file_data: Binary file data
            
        Returns:
            XMP metadata
        """
        try:
            xmp_start = file_data.find(b'<?xpacket')
            if xmp_start != -1:
                xmp_end = file_data.find(b'</x:xmpmeta>', xmp_start)
                if xmp_end != -1:
                    return file_data[xmp_start:xmp_end + 12]
        except Exception:
            pass
        return b''

    def get_filesystem_metadata(self, file_path):
        """
        Get metadata from the filesystem.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Filesystem metadata
        """
        try:
            stats = os.stat(file_path)
            return {
                'created': datetime.fromtimestamp(stats.st_ctime),
                'modified': datetime.fromtimestamp(stats.st_mtime),
                'accessed': datetime.fromtimestamp(stats.st_atime)
            }
        except Exception:
            return {}

    def scan_binary_patterns(self, file_data):
        """
        Scan binary data for known metadata patterns.
        
        Args:
            file_data: Binary file data
            
        Returns:
            Detected patterns
        """
        patterns = {}
        for pattern_type, pattern_list in self.known_patterns.items():
            if isinstance(pattern_list, list):
                for pattern in pattern_list:
                    if pattern in file_data:
                        patterns[pattern_type] = True
                        break
        return patterns

    def extract_maker_notes(self, file_data):
        """
        Extract camera maker notes from binary data.
        
        Args:
            file_data: Binary file data
            
        Returns:
            Maker notes
        """
        maker_notes = {}
        for maker, patterns in self.known_patterns['maker_notes'].items():
            for pattern in patterns:
                if pattern in file_data:
                    start_idx = file_data.index(pattern)
                    maker_notes[maker] = file_data[start_idx:start_idx+1024]
        return maker_notes

    def is_image_file(self, file_path):
        """
        Check if a file is an image.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if image file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in MEDIA_TYPES['image']

    def merge_metadata_layers(self, layers):
        """
        Merge metadata layers into a single metadata object.
        
        Args:
            layers: Metadata layers
            
        Returns:
            Merged metadata
        """
        merged = {}
        for layer_name, layer_data in layers.items():
            if layer_data:
                merged[layer_name] = layer_data
        return merged


class MetadataProcessor:
    """Process and organize files based on metadata."""
    
    def __init__(self, gpu_accelerator=None):
        """Initialize metadata processor with optional GPU acceleration."""
        self.gpu = gpu_accelerator
        self.metadata_recovery = DeepMetadataRecovery(gpu_accelerator)
        self.processed_files = set()
        self.error_files = []

    def process_file(self, file_path, destination_root):
        """
        Process a single file.
        
        Args:
            file_path: Path to the file
            destination_root: Destination root directory
        """
        try:
            if file_path in self.processed_files:
                return
            
            metadata = self.metadata_recovery.deep_scan(file_path)
            
            media_type = self.get_media_type(file_path)
            if media_type in ['image', 'video'] and self.gpu:
                try:
                    if media_type == 'image':
                        img = cv2.imread(file_path)
                        if img is not None:
                            self.gpu.process_image_gpu(img)
                    elif media_type == 'video' and MOVIEPY_AVAILABLE:
                        clip = mp.VideoFileClip(file_path)
                        if clip is not None:
                            self.gpu.process_video_gpu(np.array(clip.get_frame(0)))
                            clip.close()
                except Exception as e:
                    print(f"GPU processing failed for {file_path}: {e}")
            
            creation_date = self.extract_creation_date(metadata)
            subseconds = self.extract_subseconds(metadata)
            
            new_filename = self.generate_filename(creation_date, subseconds, file_path)
            target_path = self.get_target_path(destination_root, media_type, 
                                             creation_date, new_filename)
            
            self.move_and_update_file(file_path, target_path, metadata)
            
            self.processed_files.add(file_path)
            
        except Exception as e:
            self.error_files.append((file_path, str(e)))
            print(f"Error processing {file_path}: {e}")

    def get_media_type(self, file_path):
        """
        Determine the media type of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Media type
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        for media_type, extensions in MEDIA_TYPES.items():
            if ext in extensions:
                return media_type
        return 'unknown'

    def extract_creation_date(self, metadata):
        """
        Extract creation date from metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Creation date
        """
        date_fields = ['DateTimeOriginal', 'CreateDate', 'FileModifyDate']
        for field in date_fields:
            if field in metadata.get('exif', {}):
                try:
                    return datetime.strptime(metadata['exif'][field], '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    continue
        
        # Fallback to filesystem metadata
        if 'filesystem' in metadata:
            return metadata['filesystem'].get('created', datetime.now())
        
        return datetime.now()

    def extract_subseconds(self, metadata):
        """
        Extract subseconds from metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Subseconds string
        """
        subsec_fields = ['SubSecTimeOriginal', 'SubSecTimeDigitized', 'SubSecTime']
        for field in subsec_fields:
            if field in metadata.get('exif', {}):
                return metadata['exif'][field]
        return None

    def generate_filename(self, creation_date, subseconds, original_path):
        """
        Generate a new filename based on metadata.
        
        Args:
            creation_date: Creation date
            subseconds: Subseconds string
            original_path: Original file path
            
        Returns:
            New filename
        """
        base = creation_date.strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(original_path)[1]
        if subseconds:
            return f"{base}_{subseconds}{ext}"
        return f"{base}{ext}"

    def get_target_path(self, destination_root, media_type, creation_date, filename):
        """
        Get target path for a file.
        
        Args:
            destination_root: Destination root directory
            media_type: Media type
            creation_date: Creation date
            filename: New filename
            
        Returns:
            Target path
        """
        year = str(creation_date.year)
        month = creation_date.strftime('%m')
        media_folder = {'image': 'Photos', 'video': 'Videos', 'audio': 'Audio'}.get(media_type, 'Other')
        
        target_dir = os.path.join(destination_root, media_folder, year, month)
        os.makedirs(target_dir, exist_ok=True)
        
        target_path = os.path.join(target_dir, filename)
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"
            
        return target_path

    def move_and_update_file(self, source_path, target_path, metadata):
        """
        Move and update a file.
        
        Args:
            source_path: Source file path
            target_path: Target file path
            metadata: Metadata dictionary
        """
        try:
            # Create target directory if it doesn't exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Move the file
            shutil.move(source_path, target_path)
            
            # Update metadata at new location
            if metadata:
                try:
                    self.update_metadata(target_path, metadata)
                except Exception as e:
                    print(f"Metadata update failed for {target_path}: {e}")
            
        except Exception as e:
            print(f"Move operation failed for {source_path}: {e}")
            raise

    def update_metadata(self, file_path, metadata):
        """
        Update file metadata.
        
        Args:
            file_path: File path
            metadata: Metadata dictionary
        """
        try:
            cmd = ['exiftool', '-overwrite_original']
            
            # Add metadata fields to command
            for key, value in metadata.get('exif', {}).items():
                if value:
                    cmd.extend([f'-{key}={value}'])
            
            cmd.append(file_path)
            
            # Execute exiftool command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Metadata update warning for {file_path}: {result.stderr}")
                
        except Exception as e:
            print(f"Metadata update error for {file_path}: {e}")


def choose_directory(title):
    """
    Show directory chooser dialog.
    
    Args:
        title: Dialog title
        
    Returns:
        Selected directory path
    """
    root = Tk()
    root.withdraw()  # Hide the main window
    directory = filedialog.askdirectory(title=title)
    root.destroy()
    return directory


def cleanup_empty_directories(path):
    """
    Remove empty directories after processing.
    
    Args:
        path: Root path to clean
    """
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):  # Check if directory is empty
                        os.rmdir(dir_path)
                        print(f"Removed empty directory: {dir_path}")
                except Exception as e:
                    print(f"Error removing directory {dir_path}: {e}")
    except Exception as e:
        print(f"Error during cleanup: {e}")


def main():
    """Main execution function."""
    try:
        print("GPU-Accelerated Media Organizer")
        print("------------------------------")
        
        # Check if exiftool is installed
        try:
            subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            print("Error: ExifTool is not installed or not in the PATH.")
            print("Please install ExifTool: https://exiftool.org/")
            
            # Show error message
            root = Tk()
            root.withdraw()
            messagebox.showerror("Error", "ExifTool is not installed or not in the PATH.\n"
                                "Please install ExifTool: https://exiftool.org/")
            root.destroy()
            return
        
        # Initialize GPU accelerator
        print("\nInitializing hardware acceleration...")
        gpu_accelerator = GPUAccelerator() if GPU_ACCELERATION else None
        
        # Initialize processor
        print("Initializing metadata processor...")
        processor = MetadataProcessor(gpu_accelerator)
        
        # Get directories
        print("\nSelect directories:")
        source_dir = choose_directory("Select Source Directory")
        if not source_dir:
            print("Source directory selection cancelled")
            return
        
        dest_dir = choose_directory("Select Destination Directory")
        if not dest_dir:
            print("Destination directory selection cancelled")
            return
        
        print(f"\nSource: {source_dir}")
        print(f"Destination: {dest_dir}")
        
        # Collect all files
        print("\nCollecting files...")
        files = []
        for root, _, filenames in os.walk(source_dir):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                if processor.get_media_type(file_path) != 'unknown':
                    files.append(file_path)
        
        if not files:
            print("No supported files found in source directory")
            
            # Show warning message
            root = Tk()
            root.withdraw()
            messagebox.showwarning("No Files Found", "No supported media files found in the source directory.")
            root.destroy()
            return
        
        print(f"Found {len(files)} files")
        
        # Process files using multiprocessing
        print("\nProcessing files...")
        num_cores = cpu_count()
        print(f"Using {num_cores} CPU cores")
        
        start_time = time.time()
        
        with Pool(num_cores) as pool:
            with tqdm(total=len(files), unit="files") as pbar:
                def update_progress(*args):
                    pbar.update()
                
                for file_path in files:
                    pool.apply_async(
                        processor.process_file, 
                        args=(file_path, dest_dir),
                        callback=update_progress
                    )
                pool.close()
                pool.join()
        
        elapsed_time = time.time() - start_time
        
        # Cleanup empty directories
        print("\nCleaning up empty directories...")
        cleanup_empty_directories(source_dir)
        
        # Final report
        print("\nProcessing Complete!")
        print(f"Time elapsed: {elapsed_time:.1f} seconds")
        print(f"Successfully processed: {len(processor.processed_files)} files")
        print(f"Errors encountered: {len(processor.error_files)} files")
        
        if processor.error_files:
            print("\nError Summary:")
            for file_path, error in processor.error_files:
                print(f"{os.path.basename(file_path)}: {error}")
        
        # Show completion message
        root = Tk()
        root.withdraw()
        messagebox.showinfo("Processing Complete", 
                           f"Processed {len(processor.processed_files)} files\n"
                           f"Errors: {len(processor.error_files)} files\n"
                           f"Time: {elapsed_time:.1f} seconds")
        root.destroy()
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        
        # Show error message
        root = Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        root.destroy()


if __name__ == "__main__":
    main()