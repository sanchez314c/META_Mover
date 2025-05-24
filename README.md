# MetaMover

<p align="center">
  <img src="https://raw.githubusercontent.com/YourUsername/Github/main/.images/metamover-hero.png" alt="MetaMover Hero" width="600" />
</p>

**Professional Media Organization and Metadata Management Suite**

A comprehensive collection of Python tools for organizing, processing, and managing media files based on their metadata. MetaMover provides intelligent file organization, metadata correction, and comprehensive reporting capabilities for photographers, videographers, and digital asset managers.

## 🚀 Features

- **Intelligent Media Organization**: Automatically organize photos, videos, and audio files by date, type, and metadata
- **Advanced Metadata Processing**: Extract, analyze, and correct metadata across multiple formats
- **GPU Acceleration**: Hardware-accelerated processing with Metal framework support (macOS)
- **Comprehensive Reporting**: Generate detailed metadata reports for analysis and documentation
- **Multi-format Support**: Works with JPEG, PNG, TIFF, HEIC, RAW, MP4, MOV, MP3, WAV, and more
- **High Performance**: Multi-threaded processing utilizing all available CPU cores
- **User-friendly**: GUI interfaces for easy directory and file selection

## 📋 Requirements

- **Python 3.6+**
- **ExifTool** (must be installed separately)
- **Required Python packages** (see requirements.txt)

### Installing ExifTool

**macOS:**
```bash
brew install exiftool
```

**Windows:**
Download from [https://exiftool.org/](https://exiftool.org/) and add to PATH

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install libimage-exiftool-perl
```

## 🛠 Installation

1. Clone the repository:
```bash
git clone https://github.com/your-repo/metamover.git
cd metamover
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Ensure ExifTool is installed and accessible in your PATH

## 📚 Tools Overview

### Media Organizers

#### `media-organizer-enhanced.py`
**Main comprehensive media organizer**
- Organizes photos, videos, and audio files by date and type
- Creates structured directory hierarchies (Photos/Videos/Audio → Year → Month)
- Handles filename collisions with intelligent numbering
- Supports batch processing with progress tracking

#### `media-organizer-audio.py` 
**Audio-specific organizer with final sweep capability**
- Specialized for music and audio file organization
- Extracts audio metadata (artist, album, genre)
- Performs final sweep to catch missed files
- Handles various audio formats and encoding types

#### `media-organizer-gpu.py`
**GPU-accelerated advanced processor**
- Metal framework optimization for macOS GPU acceleration
- Deep metadata recovery for corrupted or minimal metadata
- Enhanced performance for large media collections
- Sophisticated binary pattern recognition

### Media Movers

#### `media-mover-basic.py`
**Basic media file mover with metadata extraction**
- Simple file moving with basic metadata preservation
- Lightweight alternative for basic organization needs
- Fast processing for simple directory restructuring

#### `media-mover-video.py`
**Video-focused mover with intelligent date detection**
- Specialized for video file processing
- Advanced date extraction from video metadata
- Handles various video formats and codecs
- Optimized for large video file collections

### Date Fixers

#### `media-date-fixer.py`
**Comprehensive date correction tool**
- Fixes incorrect dates in EXIF metadata
- Handles timezone conversions and date format standardization
- Batch processing with detailed logging
- Preserves original files with backup options

#### `media-date-fixer-simple.py`
**Simple date fixing utility for JPEG images**
- Lightweight tool for basic date corrections
- Focuses on common date issues (1970 timestamps)
- GUI-driven workflow for ease of use
- Fast processing for simple date fixes

### Utilities

#### `media-renamer.py`
**File renaming based on metadata**
- Renames files using creation dates and metadata
- Customizable filename patterns
- Subsecond precision for avoiding collisions
- Handles various media formats intelligently

### Reporting Tools

#### `media-tags-report.py`
**Comprehensive metadata tag reporting**
- Generates detailed reports of all metadata tags
- Supports both text and CSV export formats
- Analyzes metadata across entire collections
- Useful for understanding available metadata fields

#### `media-tags-report-unique.py`
**Unique metadata tags reporter**
- Discovers all unique metadata tags in a collection
- Groups tags by metadata format and type
- Searchable text output for documentation
- Helps identify inconsistencies and missing data

## 🎯 Quick Start

### Basic Media Organization
```bash
python media-organizer-enhanced.py
```
Select source and destination folders through the GUI, and the tool will organize your media files automatically.

### Fix Date Issues
```bash
python media-date-fixer.py
```
Correct problematic dates in your photo metadata.

### Generate Metadata Report
```bash
python media-tags-report.py
```
Create a comprehensive report of all metadata tags in your collection.

### GPU-Accelerated Processing (macOS)
```bash
python media-organizer-gpu.py
```
Leverage Metal framework for hardware-accelerated processing.

## 📖 Detailed Usage

### Media Organization Workflow

1. **Preparation**: Ensure all tools have proper permissions to read/write your media directories
2. **Selection**: Choose source directory containing your media files
3. **Destination**: Select or create destination directory for organized files
4. **Processing**: Let the tool automatically organize files by date and type
5. **Verification**: Review the organized structure and generated logs

### Date Correction Workflow

1. **Scan**: Use date fixer tools to identify files with incorrect dates
2. **Preview**: Review proposed changes before applying
3. **Backup**: Original files are preserved during the correction process
4. **Apply**: Execute date corrections with detailed logging

### Metadata Analysis Workflow

1. **Scan**: Use reporting tools to analyze metadata across your collection
2. **Export**: Generate reports in text or CSV format
3. **Analysis**: Review metadata patterns and identify issues
4. **Planning**: Use insights to plan organization and correction strategies

## ⚡ Performance Tips

- **Use SSD storage** for best performance with large collections
- **Close other applications** during processing to maximize available resources
- **Process in batches** for extremely large collections (>100,000 files)
- **Enable GPU acceleration** on supported systems for faster processing
- **Use appropriate tools** for your specific needs (don't use GPU tools for small collections)

## 🔧 Configuration

### Environment Variables
- `EXIFTOOL_PATH`: Custom path to ExifTool executable
- `METAMOVER_TEMP`: Custom temporary directory for processing

### Processing Options
Most tools support these common options through GUI:
- Source directory selection
- Destination directory selection
- Processing options and filters
- Output format preferences

## 🐛 Troubleshooting

### Common Issues

**ExifTool not found**
- Ensure ExifTool is installed and in your system PATH
- On Windows, restart your terminal after installation
- Check installation with: `exiftool -ver`

**Permission denied errors**
- Ensure read/write permissions for source and destination directories
- On macOS, grant Full Disk Access to Terminal in System Preferences
- Run with appropriate user permissions

**Memory issues with large collections**
- Process files in smaller batches
- Close other applications to free memory
- Consider using basic tools for very large collections

**GPU acceleration not working**
- Metal framework is only available on macOS
- Ensure you have a compatible GPU
- Fall back to CPU processing if GPU fails

### Getting Help

1. Check the error messages in the console output
2. Verify ExifTool installation and accessibility
3. Ensure sufficient disk space for processing
4. Check file permissions for source and destination directories

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
git clone https://github.com/your-repo/metamover.git
cd metamover
pip install -r requirements.txt
# Install development dependencies
pip install pytest black flake8
```

### Running Tests
```bash
pytest tests/
```

### Code Style
We use Black for code formatting:
```bash
black *.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **ExifTool** by Phil Harvey - The foundation for metadata processing
- **Python PIL/Pillow** - Image processing capabilities
- **OpenCV** - Computer vision and image analysis
- **MoviePy** - Video processing support
- **tqdm** - Progress bar functionality

## 📊 Project Stats

- **10 specialized tools** for different media processing needs
- **Support for 15+ file formats** including RAW, HEIC, and professional formats
- **Multi-core processing** for maximum performance
- **GPU acceleration** support for compatible systems
- **Comprehensive error handling** and logging
- **User-friendly GUI interfaces** for all tools

## 🔄 Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and feature additions.

---

**Made with ❤️ for photographers, videographers, and digital asset managers**

For support, issues, or feature requests, please visit our [GitHub Issues](https://github.com/your-repo/metamover/issues) page.