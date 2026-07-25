"""
Schema definitions for Autonomous Deep Academic Literature Agent.
Defines Pydantic v2 schemas for parameters, papers, and LangGraph AgentState.
"""

from typing import List, Optional, TypedDict, Annotated
from pydantic import BaseModel, Field
import operator


class UserQueryParameters(BaseModel):
    """Extracted parameters from natural language user research prompts."""
    search_topic: str = Field(
        description="Core research topic/title extracted from prompt."
    )
    target_count: int = Field(
        default=7,
        description="Number of papers requested (Default: 7 papers)."
    )
    start_year: int = Field(
        default=2021,
        description="Start year filter for publication (Default: 2021)."
    )
    end_year: int = Field(
        default=2026,
        description="End year filter for publication (Default: 2026)."
    )


class ResearchPaper(BaseModel):
    """Schema for individual research paper metadata and LLM relevance rationale."""
    serial_no: int = Field(description="Sequential paper index starting from 1.")
    title: str = Field(description="Full paper title.")
    year: Optional[int] = Field(default=None, description="Publication year.")
    doi_or_link: str = Field(description="Verified DOI URL or web link to the paper.")
    abstract: str = Field(description="Paper abstract text.")
    relevance_justification: Optional[str] = Field(
        default=None,
        description="2-sentence justification explaining exact relevance to user topic."
    )


class AgentState(TypedDict):
    """Typed state dictionary for LangGraph workflow execution."""
    user_prompt: str
    params: Optional[UserQueryParameters]
    raw_papers: List[dict]
    processed_papers: List[dict]
    excel_path: Optional[str]
    generate_paper: bool
    paper_tex_path: Optional[str]
    paper_pdf_path: Optional[str]
    ai_density: Optional[float]
    overleaf_zip_path: Optional[str]
    status_message: str


