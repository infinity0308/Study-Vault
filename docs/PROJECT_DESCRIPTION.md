# Project Description

## Overview
StudyVault is a Django + Django REST Framework learning-material library and RAG question-answering website. Users upload PDFs; the system stores originals in private Cloudflare R2, extracts and chunks their text, indexes vectors in Qdrant, and answers questions using retrieved context and a configured Gemma model.

## Problem
Students have learning material spread across many PDFs. Keyword search can be slow, while generic chatbot answers may not match the course notes. StudyVault provides natural-language Q&A grounded in uploaded material, with source excerpts and page references.

## Goals
- Attractive, responsive UI for PDF upload and question answering.
- Documented REST API.
- Private R2 storage for original PDFs.
- Asynchronous PDF extraction, chunking, and indexing.
- Qdrant semantic retrieval scoped to the current user's documents.
- Gemma-based answer generation with source references.
- Clear ingestion states, retries, and failure handling.
- Secure user and document isolation.

## Roles
**Learner:** sign in, upload/manage own PDFs, see processing status, ask questions, inspect sources.

**Administrator:** use Django admin for operational tasks only; the learner-facing UI must be custom-built and must not resemble Django admin.

## MVP features
1. Account registration/login/logout.
2. PDF upload with title, subject, and optional description.
3. Library list with search, filters, status badges, retry, and delete.
4. Background ingestion with page metadata and stable chunk IDs.
5. Ask form with optional document scope.
6. Grounded answer and source cards showing document title, page, and excerpt.
7. Abstention when retrieved material does not support an answer.
8. Health checks, structured logs, and recoverable task failures.

## Out of scope initially
- OCR for scanned/image-only PDFs.
- DOCX, PPTX, video, audio, or URL ingestion.
- Fine-tuning.
- Public document sharing or multi-organization administration.
- Autonomous web search and agent actions.
- Claims that citations alone guarantee answer correctness.

## Functional requirements
- Validate PDF signature, size, and type on the server.
- Associate every document with an owner.
- Store original files in private R2.
- Process large files outside the web request using a worker.
- Keep page metadata through extraction and chunking where possible.
- Verify embedding vector dimensions before Qdrant insertion.
- Filter retrieval by the authenticated owner on the server.
- Return source metadata generated from actual retrieved chunks.
- Make deletion remove the file and its vectors, retrying partial failures.
- Keep credentials out of source control and logs.

## Acceptance criteria
A user can upload a valid PDF, wait for indexing to complete, ask a question answered from that PDF, and see plausible source references. The user cannot access another user's documents by changing IDs or request parameters. Missing evidence and provider outages are handled honestly and clearly. The UI works on mobile and desktop.
