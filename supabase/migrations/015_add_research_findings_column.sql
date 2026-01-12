-- Migration: Add research_findings column to consultations table
-- Description: Adds a JSONB column to store research paper-based analysis results
-- Date: 2026-01-12

-- Add research_findings column to consultations table
ALTER TABLE consultations
ADD COLUMN IF NOT EXISTS research_findings JSONB NULL;

-- Add index for faster queries on research_findings
CREATE INDEX IF NOT EXISTS idx_consultations_research_findings
ON consultations USING GIN (research_findings);

-- Add comment explaining the column
COMMENT ON COLUMN consultations.research_findings IS 'Research paper-based analysis results including diagnoses from PubMed, BMJ, and Scopus Q1/Q2 journals. Appended to guideline-based findings. Structure: {diagnoses: [{diagnosis, confidence, reasoning, research_citations: [{pmid, doi, title, journal, year, authors}]}], papers_reviewed: [...], analysis_date, filters_applied: {date_range, quartile, databases}}';
