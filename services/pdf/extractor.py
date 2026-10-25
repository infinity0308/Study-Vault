import io
import re
import uuid
from typing import List, Dict, Any, Tuple
import pymupdf  # fitz

MAX_PAGES_LIMIT = 500
MAX_CHUNKS_PER_DOCUMENT = 2000
MIN_TEXT_CHARS = 40  # Minimum characters across the entire document to consider it extractable


class PDFExtractionError(Exception):
    """Custom error for PDF extraction failures."""
    pass


class ScannedPDFError(PDFExtractionError):
    """Raised when PDF contains no extractable text (scanned image)."""
    pass


class PDFExtractor:
    """Validates and extracts page text from PDF bytes."""

    @staticmethod
    def validate_pdf_bytes(pdf_bytes: bytes, max_size_bytes: int = 25 * 1024 * 1024) -> None:
        """Validate size and magic bytes header."""
        if not pdf_bytes:
            raise PDFExtractionError("PDF file is empty.")

        if len(pdf_bytes) > max_size_bytes:
            raise PDFExtractionError(f"PDF exceeds size limit of {max_size_bytes // (1024 * 1024)}MB.")

        # Check for %PDF- magic signature in the first 1024 bytes
        if not pdf_bytes[:1024].startswith(b"%PDF-") and b"%PDF-" not in pdf_bytes[:1024]:
            raise PDFExtractionError("Invalid file signature. File is not a valid PDF document.")

    @classmethod
    def extract_pages(cls, pdf_bytes: bytes) -> List[Tuple[int, str]]:
        """
        Extract text page by page.
        Returns a list of tuples: (page_number_1_indexed, text).
        """
        cls.validate_pdf_bytes(pdf_bytes)

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise PDFExtractionError(f"Failed to open PDF document: {e}")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise PDFExtractionError("PDF contains 0 pages.")

        if total_pages > MAX_PAGES_LIMIT:
            doc.close()
            raise PDFExtractionError(f"PDF has {total_pages} pages, exceeding maximum limit of {MAX_PAGES_LIMIT}.")

        pages_text = []
        total_text_length = 0

        try:
            for page_idx in range(total_pages):
                page = doc[page_idx]
                text = page.get_text("text").strip()
                # Clean up repeated whitespace
                cleaned = re.sub(r"[ \t]+", " ", text)
                pages_text.append((page_idx + 1, cleaned))
                total_text_length += len(cleaned)
        finally:
            doc.close()

        if total_text_length < MIN_TEXT_CHARS:
            raise ScannedPDFError(
                "No extractable text was found in this PDF. Scanned PDFs are not currently supported."
            )

        return pages_text


class PDFChunker:
    """
    Chunks extracted page texts with configurable target length and overlap.
    Preserves page numbers and generates deterministic or UUID chunk IDs.
    """

    def __init__(
        self,
        target_chars: int = 3000,   # roughly ~750 tokens
        overlap_chars: int = 400,   # roughly ~100 tokens
        max_chunks: int = MAX_CHUNKS_PER_DOCUMENT,
    ):
        self.target_chars = target_chars
        self.overlap_chars = overlap_chars
        self.max_chunks = max_chunks

    def chunk_pages(
        self,
        pages: List[Tuple[int, str]],
        document_id: str,
        owner_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Chunk pages into overlapping segments.
        Returns a list of chunk dicts:
        {
            "id": uuid,
            "document_id": str,
            "owner_id": str,
            "page": int,
            "text": str,
        }
        """
        chunks = []

        for page_num, text in pages:
            if not text:
                continue

            # Split text by paragraphs first
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

            current_chunk_parts = []
            current_len = 0

            for para in paragraphs:
                para_len = len(para)
                if current_len + para_len > self.target_chars and current_chunk_parts:
                    chunk_text = " ".join(current_chunk_parts)
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "document_id": str(document_id),
                        "owner_id": str(owner_id),
                        "page": page_num,
                        "text": chunk_text,
                    })

                    if len(chunks) >= self.max_chunks:
                        return chunks

                    # Overlap: keep the last part if short enough
                    overlap_parts = []
                    acc = 0
                    for part in reversed(current_chunk_parts):
                        if acc + len(part) < self.overlap_chars:
                            overlap_parts.insert(0, part)
                            acc += len(part)
                        else:
                            break
                    current_chunk_parts = overlap_parts
                    current_len = sum(len(p) for p in current_chunk_parts)

                current_chunk_parts.append(para)
                current_len += para_len

            if current_chunk_parts:
                chunk_text = " ".join(current_chunk_parts)
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "document_id": str(document_id),
                    "owner_id": str(owner_id),
                    "page": page_num,
                    "text": chunk_text,
                })

                if len(chunks) >= self.max_chunks:
                    return chunks

        return chunks
