"""Pydantic models for Quick Tools endpoints."""

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    project: str = Field(default="context_engine")


class SearchRawRequest(BaseModel):
    project: str = Field(default="context_engine")
    query: str
    scope: str = Field(default="both")
    k: int = Field(default=10, ge=1, le=200)


class PinRequest(BaseModel):
    project: str = Field(default="context_engine")
    uri: str
    task: str
    label: int = Field(default=1, description="Use +1 for pin, -1 for forget")


class ExplainPlanRequest(BaseModel):
    plan_id: str | None = None
    last: bool = True


class RetrievalWeightsOverride(BaseModel):
    vector: float | None = Field(default=None, ge=0.0, le=1.0)
    bm25: float | None = Field(default=None, ge=0.0, le=1.0)


class RetrievalCandidatesOverride(BaseModel):
    vector_k: int | None = Field(default=None, ge=1, le=400)
    bm25_k: int | None = Field(default=None, ge=1, le=400)


class RetrievalOverride(BaseModel):
    mode: str | None = Field(default=None, pattern="^(hybrid|lexical|vector)$")
    lexical_config: str | None = None
    weights: RetrievalWeightsOverride | None = None
    candidates: RetrievalCandidatesOverride | None = None


class GetContextRequest(BaseModel):
    project: str = Field(default="context_engine")
    task: str
    max_code_chunks: int | None = Field(default=None, ge=1, le=50)
    max_doc_chunks: int | None = Field(default=None, ge=1, le=50)
    graph_depth: int | None = Field(default=None, ge=1, le=5)
    token_budget: int | None = Field(default=None, ge=1000, le=20000)
    retrieval: RetrievalOverride | None = None


class GraphifyRequest(BaseModel):
    project: str = Field(default="context_engine")
    dry_run: bool = Field(default=False)


class IndexRepoRequest(BaseModel):
    project: str = Field(default="context_engine")
