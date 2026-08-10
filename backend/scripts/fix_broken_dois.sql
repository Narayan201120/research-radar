-- One-time data fix: repoint 8 papers whose OpenAlex-registered DOI leads to a 404
-- (langtaosha preprint service and defunct TIB LDM service), and correct the
-- publication years that the re-registration had mis-set.
--
-- Each replacement URL was HTTP-verified and title-checked (Aug 2026).

BEGIN;

-- 431: "Attention Is All You Need" - 2025 langtaosha re-post; canonical is arXiv 2017
UPDATE paper
SET doi = 'https://doi.org/10.48550/arXiv.1706.03762',
    publication_year = 2017
WHERE id = 431;

-- 459: "Local and global algorithms for disambiguation to Wikipedia" (IJCNLP 2011)
UPDATE paper
SET doi = 'https://aclanthology.org/P11-1138/',
    publication_year = 2011
WHERE id = 459;

-- 512: "DailyDialog..." (IJCNLP 2017); arXiv 1710.03957
UPDATE paper
SET doi = 'https://doi.org/10.48550/arXiv.1710.03957',
    publication_year = 2017
WHERE id = 512;

-- 531: "Fine-grained Analysis of Sentence Embeddings..." (arXiv 2016)
UPDATE paper
SET doi = 'https://doi.org/10.48550/arXiv.1608.04207',
    publication_year = 2016
WHERE id = 531;

-- 557: "Universal Conceptual Cognitive Annotation (UCCA)" (ACL 2013, P13-1023)
UPDATE paper
SET doi = 'https://aclanthology.org/P13-1023/',
    publication_year = 2013
WHERE id = 557;

-- 649: "Learning to Retrieve Reasoning Paths..." (ICLR 2020, arXiv 1911.10470)
UPDATE paper
SET doi = 'https://doi.org/10.48550/arXiv.1911.10470',
    publication_year = 2019
WHERE id = 649;

-- 654: "Event Extraction for Portuguese..." - malformed DOI 10.1007/9; arXiv 2408.16932
UPDATE paper
SET doi = 'https://doi.org/10.48550/arXiv.2408.16932',
    publication_year = 2024
WHERE id = 654;

COMMIT;

-- sanity check
SELECT id, title, doi, publication_year
FROM paper
WHERE id IN (431, 459, 512, 531, 557, 649, 654)
ORDER BY id;
