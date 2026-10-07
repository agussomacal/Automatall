#!/usr/bin/env python3
"""Core logic for PDF Concatenator"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


class PDFConcatenatorLogic:
    """Handles PDF merging operations"""

    def __init__(self):
        self.supported_extensions = ['.pdf']

    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate if a file is a valid PDF.
        Returns (is_valid, error_message)
        """
        path = Path(file_path)

        if not path.exists():
            return False, f"File not found: {file_path}"

        if not path.is_file():
            return False, f"Not a file: {file_path}"

        if path.suffix.lower() not in self.supported_extensions:
            return False, f"Unsupported format: {path.suffix}. Only PDFs are supported."

        # Check if file is readable
        try:
            with open(path, 'rb') as f:
                header = f.read(4)
                if b'%PDF' not in header:
                    return False, f"Invalid PDF header in: {file_path}"
        except PermissionError:
            return False, f"Permission denied: {file_path}"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

        return True, ""

    def concat_pdfs(self, input_files: List[str], output_path: str) -> Tuple[bool, str]:
        """
        Concatenate multiple PDF files into one using Ghostscript.

        Args:
            input_files: List of absolute paths to PDF files in order
            output_path: Absolute path for the output PDF

        Returns:
            (success, message_or_error)
        """
        if len(input_files) < 1:
            return False, "No input files provided"

        if not output_path:
            return False, "Output path not specified"

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                return False, f"Cannot create output directory: {str(e)}"

        # Validate all input files first
        for i, f_path in enumerate(input_files):
            is_valid, error = self.validate_file(f_path)
            if not is_valid:
                return False, f"Invalid file at position {i + 1}: {error}"

        # Build Ghostscript command
        # -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=output.pdf input1.pdf input2.pdf ...
        cmd = [
                  'gs',
                  '-dBATCH',
                  '-dNOPAUSE',
                  '-q',
                  '-sDEVICE=pdfwrite',
                  f'-sOutputFile={output_path}'
              ] + input_files

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown Ghostscript error"
                return False, f"Ghostscript failed: {error_msg}"

            # Verify output was created
            if not os.path.exists(output_path):
                return False, "Ghostscript completed but output file was not created"

            return True, f"Successfully merged {len(input_files)} files into {os.path.basename(output_path)}"

        except FileNotFoundError:
            return False, "Ghostscript (gs) not found. Please install it."
        except subprocess.TimeoutExpired:
            return False, "Operation timed out. The files might be too large."
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def get_temp_output_path(self, prefix="merged_", suffix=".pdf") -> str:
        """Generate a temporary output path"""
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)
        return path