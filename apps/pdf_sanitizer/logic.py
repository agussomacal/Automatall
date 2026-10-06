#!/usr/bin/env python3
"""Business logic for PDF Sanitizer - Pure functions, no GTK dependencies"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional


def validate_input_path(file_path: str) -> Tuple[bool, str]:
    """
    Validate the input PDF file path.

    Args:
        file_path: Path to the PDF file

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return (False, "No file selected")

    if not os.path.exists(file_path):
        return (False, f"File does not exist: {file_path}")

    if not os.path.isfile(file_path):
        return (False, f"Not a file: {file_path}")

    if not file_path.lower().endswith('.pdf'):
        return (False, "Not a PDF file (.pdf required)")

    # Check if readable
    if not os.access(file_path, os.R_OK):
        return (False, "File is not readable")

    return (True, "")


def validate_output_path(output_path: str) -> Tuple[bool, str]:
    """
    Validate the output file path.

    Args:
        output_path: Desired output path

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not output_path:
        return (False, "No output path specified")

    if not output_path.lower().endswith('.pdf'):
        return (False, "Output must be a .pdf file")

    # Check if output directory exists
    output_dir = os.path.dirname(output_path) or "."
    if not os.path.isdir(output_dir):
        return (False, f"Output directory does not exist: {output_dir}")

    return (True, "")


def generate_default_output_name(input_path: str, suffix: str = "_sanitized") -> str:
    """
    Generate default output filename from input.

    Args:
        input_path: Path to input PDF
        suffix: Suffix to add before .pdf extension

    Returns:
        Suggested output path
    """
    if not input_path:
        return ""

    input_dir = os.path.dirname(input_path) or "."
    base_name = os.path.basename(input_path)
    name_without_ext = os.path.splitext(base_name)[0]

    output_name = f"{name_without_ext}{suffix}.pdf"
    output_path = os.path.join(input_dir, output_name)

    return output_path


def check_pdftoppm_available() -> Tuple[bool, str]:
    """
    Check if pdftoppm (Poppler) is installed and available.

    Returns:
        Tuple of (available, error_message)
    """
    import subprocess

    try:
        result = subprocess.run(
            ['pdftoppm', '-h'],
            capture_output=True,
            timeout=5
        )
        # pdftoppm exits with 1 on -h but still outputs version
        if result.returncode in [0, 1]:
            stdout = result.stdout.decode('utf-8', errors='ignore')
            stderr = result.stderr.decode('utf-8', errors='ignore')
            version_line = (stdout + stderr).split('\n')[0]
            return (True, f"pdftoppm found ({version_line})")
        else:
            return (False, "pdftoppm returned unexpected error")
    except FileNotFoundError:
        return (False, "pdftoppm not found (install: sudo apt install poppler-utils)")
    except subprocess.TimeoutExpired:
        return (False, "pdftoppm command timed out")
    except Exception as e:
        return (False, f"Error checking pdftoppm: {e}")


def check_convert_available() -> Tuple[bool, str]:
    """
    Check if ImageMagick convert is available.

    Returns:
        Tuple of (available, error_message)
    """
    import subprocess

    try:
        result = subprocess.run(
            ['convert', '-version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.decode('utf-8').split('\n')[0]
            return (True, f"ImageMagick found ({version})")
        else:
            return (False, "ImageMagick returned error")
    except FileNotFoundError:
        return (False, "convert not found (install: sudo apt install imagemagick)")
    except subprocess.TimeoutExpired:
        return (False, "convert command timed out")
    except Exception as e:
        return (False, f"Error checking ImageMagick: {e}")


def check_tools_available() -> Tuple[bool, str]:
    """
    Check if both required tools are available.

    Returns:
        Tuple of (both_available, combined_message)
    """
    pdftoppm_ok, pdftoppm_msg = check_pdftoppm_available()
    convert_ok, convert_msg = check_convert_available()

    if not pdftoppm_ok and not convert_ok:
        return (False, f"Both tools missing:\n{pdftoppm_msg}\n{convert_msg}")
    elif not pdftoppm_ok:
        return (False, pdftoppm_msg)
    elif not convert_ok:
        return (False, convert_msg)
    else:
        return (True, f"{pdftoppm_msg} + {convert_msg}")


def sanitize_pdf(
        input_path: str,
        output_path: str,
        dpi: int = 150,
        keep_temp_files: bool = False
) -> Tuple[bool, str]:
    """
    Sanitize PDF by converting to PNG images and back.

    Process:
    1. PDF → PNG images (one per page) using pdftoppm
    2. PNG images → PDF using ImageMagick convert

    This removes hidden text, annotations, metadata while preserving visual content.

    Args:
        input_path: Path to input PDF
        output_path: Path for sanitized output PDF
        dpi: Resolution for PNG conversion (higher = better quality)
        keep_temp_files: Whether to keep intermediate PNG files

    Returns:
        Tuple of (success, error_message)
    """
    import subprocess
    import glob

    # Validate inputs
    is_valid, error = validate_input_path(input_path)
    if not is_valid:
        return (False, f"Input validation failed: {error}")

    is_valid, error = validate_output_path(output_path)
    if not is_valid:
        return (False, f"Output validation failed: {error}")

    # Create temp directory for PNG files
    temp_dir = tempfile.mkdtemp(prefix="pdf_sanitizer_")

    try:
        # Step 1: Convert PDF to PNG images using pdftoppm
        # Output will be: temp_dir/{basename}-1.png, {basename}-2.png, etc.
        basename = os.path.join(temp_dir, "page")

        pdftoppm_cmd = [
            'pdftoppm',
            '-png',
            '-r', str(dpi),
            input_path,
            basename
        ]

        result = subprocess.run(
            pdftoppm_cmd,
            capture_output=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            return (False, f"pdftoppm failed: {stderr[:200]}")

        # Find generated PNG files
        png_pattern = os.path.join(temp_dir, "page-*.png")
        png_files = sorted(glob.glob(png_pattern))

        if not png_files:
            return (False, "No PNG files were generated")

        # Step 2: Convert PNG images back to PDF using ImageMagick
        convert_cmd = [
                          'convert'
                      ] + png_files + [
                          output_path
                      ]

        result = subprocess.run(
            convert_cmd,
            capture_output=True,
            timeout=300
        )

        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            return (False, f"ImageMagick convert failed: {stderr[:200]}")

        # Verify output was created
        if not os.path.exists(output_path):
            return (False, "Sanitization succeeded but output file not created")

        # Optionally keep temp files for debugging
        if not keep_temp_files:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return (True, "")

    except FileNotFoundError as e:
        return (False, f"Required tool not found: {e}")
    except subprocess.TimeoutExpired:
        return (False, "Processing timed out (file may be too large or complex)")
    except PermissionError as e:
        return (False, f"Permission denied: {e}")
    except Exception as e:
        return (False, f"Unexpected error: {str(e)}")

    finally:
        # Always cleanup temp directory unless explicitly requested
        if not keep_temp_files:
            shutil.rmtree(temp_dir, ignore_errors=True)


def get_quality_options() -> dict:
    """
    Get available DPI quality options.

    Returns:
        Dict mapping name to DPI value
    """
    return {
        'Low (72 DPI)': 72,
        'Medium (150 DPI)': 150,
        'High (300 DPI)': 300,
        'Very High (600 DPI)': 600
    }


def get_file_size_bytes(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def format_file_size(size_bytes: int) -> str:
    """Format file size for display."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def calculate_size_change(original: int, converted: int) -> Tuple[float, str]:
    """
    Calculate size change percentage and description.

    Args:
        original: Original file size
        converted: Converted file size

    Returns:
        Tuple of (percentage_change, description)
    """
    if original == 0:
        return (0.0, "No change")

    change = ((converted - original) / original) * 100

    if change > 0:
        return (change, f"Increased by {change:.1f}%")
    elif change < 0:
        return (change, f"Reduced by {-change:.1f}%")
    else:
        return (0.0, "Same size")


def estimate_processing_time(dpi: int, page_count: int) -> str:
    """
    Estimate processing time based on DPI and pages.

    Args:
        dpi: Resolution
        page_count: Number of pages in PDF

    Returns:
        Estimated time string
    """
    # Rough estimation: 150 DPI takes ~2 seconds per page
    base_seconds = page_count * (dpi / 150) * 2
    if base_seconds < 10:
        return f"< 10 seconds"
    elif base_seconds < 60:
        return f"~{int(base_seconds)} seconds"
    else:
        minutes = base_seconds / 60
        return f"~{minutes:.1f} minutes"