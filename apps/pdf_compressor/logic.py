#!/usr/bin/env python3
"""Business logic for PDF Compressor - Pure functions, no GTK dependencies"""

import os
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


def validate_output_path(output_path: str, input_path: str) -> Tuple[bool, str]:
    """
    Validate the output file path.

    Args:
        output_path: Desired output path
        input_path: Input file path (for directory validation)

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

    # Warn if overwriting
    if os.path.exists(output_path) and output_path != input_path:
        return (False, f"Output file already exists: {output_path}")

    return (True, "")


def generate_default_output_name(input_path: str) -> str:
    """
    Generate default output filename from input.

    Args:
        input_path: Path to input PDF

    Returns:
        Suggested output path with '_compressed' suffix
    """
    if not input_path:
        return ""

    # Get base name without extension
    input_dir = os.path.dirname(input_path) or "."
    base_name = os.path.basename(input_path)
    name_without_ext = os.path.splitext(base_name)[0]

    # Add _compressed suffix and .pdf extension
    output_name = f"{name_without_ext}_compressed.pdf"
    output_path = os.path.join(input_dir, output_name)

    return output_path


def check_ghostscript_available() -> Tuple[bool, str]:
    """
    Check if Ghostscript is installed and available.

    Returns:
        Tuple of (available, error_message)
    """
    import subprocess

    try:
        result = subprocess.run(
            ['gs', '--version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.decode('utf-8').strip()
            return (True, f"Ghostscript found (v{version})")
        else:
            return (False, "Ghostscript returned error code")
    except FileNotFoundError:
        return (False, "Ghostscript not found (install with: sudo apt install ghostscript)")
    except subprocess.TimeoutExpired:
        return (False, "Ghostscript command timed out")
    except Exception as e:
        return (False, f"Error checking Ghostscript: {e}")


def compress_pdf(
        input_path: str,
        output_path: str,
        preset: str = "/ebook"
) -> Tuple[bool, str]:
    """
    Compress a PDF using Ghostscript.

    Args:
        input_path: Path to input PDF
        output_path: Path for output compressed PDF
        preset: Compression preset
                (/screen, /ebook, /printer, /prepress, /default)

    Returns:
        Tuple of (success, error_message)
    """
    import subprocess

    # Validate inputs first
    is_valid, error = validate_input_path(input_path)
    if not is_valid:
        return (False, f"Input validation failed: {error}")

    is_valid, error = validate_output_path(output_path, input_path)
    if not is_valid and not os.path.exists(output_path):
        # Allow if overwriting existing
        if not os.path.exists(output_path):
            return (False, f"Output validation failed: {error}")

    # Build Ghostscript command
    cmd = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dCompatibilityLevel=1.4',
        f'-dPDFSETTINGS={preset}',
        '-dNOPAUSE',
        '-dQUIET',
        '-dBATCH',
        f'-sOutputFile={output_path}',
        input_path
    ]

    try:
        # Run compression
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300  # 5 minute timeout for large files
        )

        if result.returncode == 0:
            # Verify output was created
            if os.path.exists(output_path):
                return (True, "")
            else:
                return (False, "Ghostscript succeeded but output file not created")
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            return (False, f"Ghostscript error: {stderr[:200]}")

    except FileNotFoundError:
        return (False, "Ghostscript not found")
    except subprocess.TimeoutExpired:
        return (False, "Compression timed out (file may be too large)")
    except PermissionError:
        return (False, "Permission denied - check file permissions")
    except Exception as e:
        return (False, f"Unexpected error: {str(e)}")


def get_preset_description(preset: str) -> str:
    """
    Get human-readable description for compression preset.

    Args:
        preset: Ghostscript preset string

    Returns:
        Description string
    """
    presets = {
        '/screen': 'Low quality, smallest size (~72 dpi)',
        '/ebook': 'Medium quality, medium size (~150 dpi)',
        '/printer': 'High quality, larger size (~300 dpi)',
        '/prepress': 'Best quality, largest size (color preserved)',
        '/default': 'Default settings'
    }
    return presets.get(preset, 'Custom settings')


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


def calculate_compression_ratio(original: int, compressed: int) -> float:
    """Calculate compression ratio as percentage reduction."""
    if original == 0:
        return 0.0
    reduction = ((original - compressed) / original) * 100
    return max(0.0, reduction)  # Don't return negative