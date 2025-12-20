"""PubMed literature evidence models."""

from pydantic import BaseModel, Field


class PubMedEvidence(BaseModel):
    """Research article from PubMed providing evidence for a variant.

    Enriched with Semantic Scholar metadata when available.
    """

    pmid: str = Field(..., description="PubMed ID")
    title: str = Field(..., description="Article title")
    abstract: str = Field("", description="Article abstract")
    authors: list[str] = Field(default_factory=list, description="Author list")
    journal: str = Field("", description="Journal name")
    year: str | None = Field(None, description="Publication year")
    doi: str | None = Field(None, description="DOI")
    url: str = Field(..., description="PubMed URL")
    signal_type: str = Field("unknown", description="resistance, sensitivity, mixed, or unknown")
    drugs_mentioned: list[str] = Field(default_factory=list, description="Drugs mentioned in article")

    # Semantic Scholar enrichment fields
    citation_count: int | None = Field(None, description="Total citation count from Semantic Scholar")
    influential_citation_count: int | None = Field(None, description="Influential citations from Semantic Scholar")
    tldr: str | None = Field(None, description="AI-generated paper summary from Semantic Scholar")
    is_open_access: bool | None = Field(None, description="Whether paper is open access")
    open_access_pdf_url: str | None = Field(None, description="URL to open access PDF if available")
    semantic_scholar_id: str | None = Field(None, description="Semantic Scholar paper ID")

    def is_resistance_evidence(self) -> bool:
        """Check if this article provides resistance evidence."""
        return self.signal_type in ['resistance', 'mixed']

    def is_sensitivity_evidence(self) -> bool:
        """Check if this article provides sensitivity evidence."""
        return self.signal_type in ['sensitivity', 'mixed']

    def get_summary(self, max_length: int = 300) -> str:
        """Get a brief summary of the article."""
        abstract_preview = self.abstract[:max_length] if self.abstract else ""
        if len(self.abstract) > max_length:
            abstract_preview += "..."
        return abstract_preview

    def format_citation(self) -> str:
        """Format as a citation string."""
        author_str = self.authors[0] if self.authors else "Unknown"
        if len(self.authors) > 1:
            author_str += " et al."
        year_str = f"({self.year})" if self.year else ""
        return f"{author_str} {year_str}. {self.journal}. PMID: {self.pmid}"

    def is_highly_cited(self, threshold: int = 50) -> bool:
        """Check if article is highly cited."""
        return self.citation_count is not None and self.citation_count >= threshold

    def is_influential(self, threshold: int = 5) -> bool:
        """Check if article has influential citations."""
        return self.influential_citation_count is not None and self.influential_citation_count >= threshold

    def get_best_summary(self, max_length: int = 300) -> str:
        """Get the best available summary - TLDR if available, else abstract.

        Semantic Scholar's TLDR is an AI-generated concise summary that's
        often more useful than truncated abstracts.
        """
        if self.tldr:
            return self.tldr
        return self.get_summary(max_length)

    def get_impact_indicator(self) -> str:
        """Get a human-readable impact indicator."""
        if self.citation_count is None:
            return ""

        parts = []
        if self.citation_count > 0:
            parts.append(f"{self.citation_count} citations")
        if self.influential_citation_count and self.influential_citation_count > 0:
            parts.append(f"{self.influential_citation_count} influential")
        if self.is_open_access:
            parts.append("Open Access")

        return " | ".join(parts) if parts else ""

    def format_rich_citation(self) -> str:
        """Format as a citation with impact metrics."""
        base = self.format_citation()
        impact = self.get_impact_indicator()
        if impact:
            return f"{base} [{impact}]"
        return base
