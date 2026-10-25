import uuid
import pytest
from services.pdf.extractor import PDFExtractor, PDFChunker, ScannedPDFError, PDFExtractionError
from services.vector_store.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


def create_sample_pdf(text: str = "Photosynthesis converts solar light into chemical energy.") -> bytes:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def create_blank_pdf() -> bytes:
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()  # Page with zero text
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_extraction_and_scanned_detection():
    # 1. Valid PDF with text
    valid_bytes = create_sample_pdf("Cellular respiration is the set of metabolic reactions that convert energy from nutrients into ATP.")
    pages = PDFExtractor.extract_pages(valid_bytes)
    assert len(pages) == 1
    assert pages[0][0] == 1
    assert "Cellular respiration" in pages[0][1]

    # 2. Blank PDF without extractable text raises ScannedPDFError
    blank_bytes = create_blank_pdf()
    with pytest.raises(ScannedPDFError):
        PDFExtractor.extract_pages(blank_bytes)


def test_pdf_chunking():
    chunker = PDFChunker(target_chars=100, overlap_chars=20)
    pages = [(1, "Paragraph one about mitochondria.\n\nParagraph two about adenosine triphosphate.")]
    chunks = chunker.chunk_pages(pages, document_id=str(uuid.uuid4()), owner_id=str(uuid.uuid4()))
    assert len(chunks) >= 1
    for c in chunks:
        assert c["page"] == 1
        assert "id" in c
        assert len(c["text"]) > 0


def test_qdrant_in_memory_indexing_and_search():
    client = QdrantClient(":memory:")
    vs = QdrantVectorStore(client=client, dimension=4, collection_name="test_col")
    vs.ensure_collection()

    owner_1 = str(uuid.uuid4())
    owner_2 = str(uuid.uuid4())
    doc_1 = str(uuid.uuid4())
    doc_2 = str(uuid.uuid4())

    pts = [
        {
            "id": str(uuid.uuid4()),
            "vector": [1.0, 0.0, 0.0, 0.0],
            "payload": {
                "owner_id": owner_1,
                "document_id": doc_1,
                "chunk_id": str(uuid.uuid4()),
                "page": 1,
                "text": "Cell theory states all organisms are composed of cells.",
            },
        },
        {
            "id": str(uuid.uuid4()),
            "vector": [0.0, 1.0, 0.0, 0.0],
            "payload": {
                "owner_id": owner_2,
                "document_id": doc_2,
                "chunk_id": str(uuid.uuid4()),
                "page": 5,
                "text": "Thermodynamics first law: energy conservation.",
            },
        },
    ]

    vs.upsert_points(pts)

    # Search strictly scoped to owner_1
    hits = vs.search(query_vector=[1.0, 0.0, 0.0, 0.0], owner_id=owner_1, top_k=5)
    assert len(hits) == 1
    assert hits[0]["payload"]["owner_id"] == owner_1
    assert "Cell theory" in hits[0]["payload"]["text"]

    # Delete doc_1
    vs.delete_by_document(owner_id=owner_1, document_id=doc_1)
    hits_after = vs.search(query_vector=[1.0, 0.0, 0.0, 0.0], owner_id=owner_1, top_k=5)
    assert len(hits_after) == 0
