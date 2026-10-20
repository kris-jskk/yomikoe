TASK        kindle-prd
STATUS      done
ASSUMED     - The one PRD.md line went at the end of "Open questions" (a line inside the ING table would break the table).
            - D41–D44 went in as new rows directly after D40 in the decision-log table. No prose section was added and the summary sentence on line 9 was left as it was (changing it would edit an existing entry).
            - Milestone placement is proposed in PRD_KINDLE.md only. The M5–M7 text in PRD.md is unchanged.
            - The report is not in the commit. The brief's single commit message covers the docs and evidence; the report stays on disk for the supervisor.

RESULT      1. Parser licences: verified. No permissive, maintained KF8 reader exists. KindleUnpack and its fork `mobi` 0.4.1 are GPL-3.0, libmobi is LGPL-3.0, pymobi and mobi_header are GPL. `mobi-python` is MIT by classifier only: it has no LICENSE file and no evident KF8 support. ebooklib is AGPL-3.0. For EPUB, epubfile (BSD-3) and epub-utils (Apache-2.0, alpha) are permitted. Real Calibre is GPL-3.0 and not on PyPI. — _agent/results/821_kindle_parser_licences.txt
            2. D7 subprocess precedent: verified that it does NOT exist any more. D7 now says "no ffmpeg", and D16 "Replaces the ffmpeg subprocess of D7's original plan". The only live subprocess precedent is Tesseract (D28), which is Apache-2.0. So a GPL Calibre subprocess has no matching precedent. — _agent/results/822_d7_subprocess_precedent.txt
            3. Ingestion interface: verified from code. There is no adapter interface. `ingest(pdf_path, *, document_id, ocr, on_page, ocr_backend) -> IngestResult` is in ingestion/pipeline.py. The seam is `list[LogicalBlock]` (models.py). `compute_profile` and `apply_mathspeak` also take `pages`. The upload route refuses anything without `%PDF-`. — _agent/results/823_ingestion_interface.txt
            4. Numbering: verified. Highest decision is D40, highest ING id is ING-11, no KDL ids existed. — _agent/results/824_numbering.txt
OBSERVATIONS - CLAUDE.md line 15 ("Audio cache is Opus/WebM via an ffmpeg subprocess (D7)") is stale against D7 and D16 (822). Only the supervisor may edit CLAUDE.md.
            - PyPI "calibre" 0.14.0 is an unrelated MIT ML package. Do not confuse it with Calibre.
            - The `documents` table has no format or origin column (migrations 0001–0005). `LogicalBlock.source` is per-block provenance. So D44 proposes migration 0006.
            - The PRD already carries Kindle highlights as SRC-4 (M7). KDL-8 restates it and adds no scope.
            - D43 recommendation: option (b), an in-house clean-room KF8 reader using only the standard library, sharing an XHTML adapter with SRC-1 EPUB.

EVIDENCE    _agent/results/821_kindle_parser_licences.txt — PyPI JSON plus GitHub LICENSE API output for 15 candidates, and the mobi-is-a-KindleUnpack-fork README lines
            _agent/results/822_d7_subprocess_precedent.txt — grep of ffmpeg and subprocess in TECHNICAL_DESIGN.md, the D7, D16 and D28 rows, CLAUDE.md lines
            _agent/results/823_ingestion_interface.txt — pipeline.py and models.py quoted, ingest() callers, the upload PDF guard, the migration list
            _agent/results/824_numbering.txt — D-number and ING-number grep counts

FILES WRITTEN     docs/PRD_KINDLE.md
                  docs/PRD.md (one line appended)
                  docs/TECHNICAL_DESIGN.md (4 rows, D41–D44)
                  _agent/results/821_kindle_parser_licences.txt
                  _agent/results/822_d7_subprocess_precedent.txt
                  _agent/results/823_ingestion_interface.txt
                  _agent/results/824_numbering.txt
                  _agent/reports/2026-10-19-kindle-prd.md
FILES READ BEYOND THE BRIEF     api/hearnarro/ingestion/pipeline.py, api/hearnarro/ingestion/models.py, api/hearnarro/routes/documents.py, api/hearnarro/storage/jobs.py (lines 210–225), api/hearnarro/storage/migrations/versions/ (listing and grep), api/pyproject.toml (grep), api/scripts/check_licences.py (grep). CODE_MAP_M1 and CODE_MAP_M5 were grepped, not read in full.

UNVERIFIED  - All device facts (Fire Silk runs the app, the e-ink browser and audio limits): supervisor brief, labelled so in the PRD
            - Amazon serving personal documents as unencrypted .azw3 or the original PDF: supervisor brief
            - Whether Amazon-converted files use HUFF/CDIC compression: listed as an open risk
            - Kindle cache paths and the absence of an Amazon API: supervisor brief
NOT DONE    The gate test is specified only, as the brief asked. No tier-0 eval was run because no ingestion code changed.
DRAFTS      none

OUTPUT      commit 59a1fdd "docs: Kindle PRD (KDL-1..9, D41–D44 proposed)", 7 files, 532 insertions(+)
