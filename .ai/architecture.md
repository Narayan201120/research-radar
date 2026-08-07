# Research Radar Architecture

## Stack

Backend
- FastAPI
- PostgreSQL
- SQLAlchemy 2.0
- Alembic

Frontend
- Next.js App Router
- TypeScript

Infrastructure
- Docker Compose

---

## Topics

1. Computer Vision
2. Large Language Models

---

## Data Model

Paper
- id
- openalex_id
- title
- abstract
- publication_year
- doi
- cited_by_count
- created_at

Author
- id
- openalex_id
- name

Topic
- id
- openalex_id
- name

PaperAuthor
- paper_id
- author_id

PaperTopic
- paper_id
- topic_id

PaperSimilarity
- paper_id
- similar_paper_id
- similarity_score

---

## Search Strategy

Search fields:
- title
- abstract

Filters:
- year
- topic
- author

Pagination:
- page
- page_size

---

## Similar Papers

Approach:
- TF-IDF
- title + abstract
- cosine similarity
- top 5 stored

Reason:
- deterministic
- no external APIs
- simple to explain

---

## Ingestion Flow

OpenAlex
    ↓
Normalize
    ↓
Upsert Papers
    ↓
Upsert Authors
    ↓
Upsert Topics
    ↓
Create Relations
    ↓
Generate Similarity Table

---

## Docker Topology

frontend
    ↓
backend
    ↓
postgres