"""Data loader for IPC, CPC, and FI classification files."""

import re
from pathlib import Path
from typing import List, Dict, Generator
from loguru import logger

try:
    from ..models.patent_class import PatentClassification, ClassificationType
except ImportError:
    from models.patent_class import PatentClassification, ClassificationType


class ClassificationDataLoader:
    """Loads and parses patent classification data from text files."""

    def __init__(self, data_path: Path):
        """
        Initialize the data loader.

        Args:
            data_path: Path to the data_20250812 directory
        """
        self.data_path = Path(data_path)
        if not self.data_path.exists():
            raise ValueError(f"Data path does not exist: {self.data_path}")

    def _parse_code_hierarchy(self, code: str) -> tuple[str, int]:
        """
        Extract parent code and determine hierarchy level.

        Args:
            code: Classification code (e.g., "A01B1/00")

        Returns:
            Tuple of (parent_code, hierarchy_level)
        """
        # Remove trailing backslash if present
        code = code.rstrip("\\").strip()

        # Determine parent based on code structure
        # A -> no parent
        # A01B -> parent is A
        # A01B1/00 -> parent is A01B
        # A01B1/02 -> parent is A01B1/00
        if len(code) == 1:  # Section level (A, B, C...)
            return None, 1
        elif len(code) <= 4:  # Class level (A01, A01B)
            return code[0], 2
        elif "/" not in code:  # Subclass without slash
            return code[:4], 3
        else:
            # Has slash - could be group or subgroup
            main_part, sub_part = code.split("/")
            if sub_part == "00":
                # Main group
                return main_part[:4], 4
            else:
                # Subgroup
                return f"{main_part}/00", 5

        return None, 0

    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and special characters."""
        if not text:
            return ""
        # Remove line breaks and multiple spaces
        text = re.sub(r"\s+", " ", text.strip())
        # Remove HTML tags if any
        text = re.sub(r"<[^>]+>", "", text)
        return text

    def parse_ipc_file(self, filepath: Path) -> Generator[PatentClassification, None, None]:
        """
        Parse an IPC classification file.

        Format: code \t empty \t title_ja \t title_en \t document_count

        Args:
            filepath: Path to IPC file

        Yields:
            PatentClassification objects
        """
        logger.info(f"Parsing IPC file: {filepath.name}")

        with open(filepath, "r", encoding="euc-jp", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("\t")
                if len(parts) < 5:
                    logger.warning(f"Skipping malformed line {line_num} in {filepath.name}")
                    continue

                try:
                    code = parts[0].strip()
                    # parts[1] is empty in IPC files
                    title_ja = self._clean_text(parts[2])
                    title_en = self._clean_text(parts[3])
                    document_count = int(parts[4].strip()) if parts[4].strip() else 0

                    parent_code, dot_number = self._parse_code_hierarchy(code)

                    yield PatentClassification(
                        code=code,
                        classification_type="IPC",
                        dot_number=dot_number,
                        title_en=title_en,
                        title_ja=title_ja,
                        parent_code=parent_code,
                        concordance=code,
                        document_count=document_count
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing line {line_num} in {filepath.name}: {e}")
                    continue

    def parse_cpc_file(self, filepath: Path) -> Generator[PatentClassification, None, None]:
        """
        Parse a CPC classification file.

        Format: code \t dot_number \t title_en \t concordance \t ipc_part \t title_ja \t document_count

        Args:
            filepath: Path to CPC file

        Yields:
            PatentClassification objects
        """
        logger.info(f"Parsing CPC file: {filepath.name}")

        with open(filepath, "r", encoding="euc-jp", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("\t")
                if len(parts) < 7:
                    logger.warning(f"Skipping malformed line {line_num} in {filepath.name}")
                    continue

                try:
                    code = parts[0].strip()
                    dot_number = int(parts[1].strip())
                    title_en = self._clean_text(parts[2])
                    concordance = parts[3].strip() if len(parts) > 3 else code
                    # ipc_part = parts[4].strip() if len(parts) > 4 else None
                    title_ja = self._clean_text(parts[5]) if len(parts) > 5 else ""
                    document_count = int(parts[6].strip()) if len(parts) > 6 and parts[6].strip() else 0

                    parent_code, _ = self._parse_code_hierarchy(code)

                    yield PatentClassification(
                        code=code,
                        classification_type="CPC",
                        dot_number=dot_number,
                        title_en=title_en,
                        title_ja=title_ja,
                        parent_code=parent_code,
                        concordance=concordance,
                        document_count=document_count
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing line {line_num} in {filepath.name}: {e}")
                    continue

    def parse_fi_file(self, filepath: Path) -> Generator[PatentClassification, None, None]:
        """
        Parse an FI classification file.

        Format: code \t dot_number \t dot_in_title \t theme \t concordance \t document_count \t title_ja \t title_en

        Args:
            filepath: Path to FI file

        Yields:
            PatentClassification objects
        """
        logger.info(f"Parsing FI file: {filepath.name}")

        with open(filepath, "r", encoding="euc-jp", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("\t")
                if len(parts) < 8:
                    logger.warning(f"Skipping malformed line {line_num} in {filepath.name}")
                    continue

                try:
                    code = parts[0].strip()
                    dot_number = int(parts[1].strip())
                    # dot_in_title = int(parts[2].strip()) if parts[2].strip() else 0
                    theme = parts[3].strip() if parts[3].strip() else None
                    concordance = parts[4].strip() if parts[4].strip() else code
                    document_count = int(parts[5].strip()) if parts[5].strip() else 0
                    title_ja = self._clean_text(parts[6])
                    title_en = self._clean_text(parts[7])

                    parent_code, _ = self._parse_code_hierarchy(code)

                    yield PatentClassification(
                        code=code,
                        classification_type="FI",
                        dot_number=dot_number,
                        title_en=title_en,
                        title_ja=title_ja,
                        parent_code=parent_code,
                        theme=theme,
                        concordance=concordance,
                        document_count=document_count
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing line {line_num} in {filepath.name}: {e}")
                    continue

    def load_all_classifications(self) -> Generator[PatentClassification, None, None]:
        """
        Load all classification data from IPC, CPC, and FI files.

        Yields:
            PatentClassification objects from all sources
        """
        # Load IPC files
        ipc_dir = self.data_path / "data_ipc"
        if ipc_dir.exists():
            for ipc_file in sorted(ipc_dir.glob("ipc_*.txt")):
                yield from self.parse_ipc_file(ipc_file)

        # Load CPC files
        cpc_dir = self.data_path / "data_cpc_interleave"
        if cpc_dir.exists():
            for cpc_file in sorted(cpc_dir.glob("cpc_*.txt")):
                yield from self.parse_cpc_file(cpc_file)

        # Load FI files
        fi_dir = self.data_path / "data_fi"
        if fi_dir.exists():
            for fi_file in sorted(fi_dir.glob("fi_*.txt")):
                yield from self.parse_fi_file(fi_file)

    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the loaded data.

        Returns:
            Dictionary with counts by classification type
        """
        stats = {"IPC": 0, "CPC": 0, "FI": 0, "Total": 0}

        for classification in self.load_all_classifications():
            stats[classification.classification_type] += 1
            stats["Total"] += 1

        return stats
