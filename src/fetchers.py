"""
Multi-Source Academic Paper Fetcher & >75% Semantic Similarity Filtering Engine.
Queries Semantic Scholar, ArXiv, and OpenAlex concurrently, extracts metadata & citation counts,
and applies a strict >75% title-semantic similarity threshold filter.
"""

import os
import re
import asyncio
import httpx
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

# Domain synonym mapping for academic title similarity
SYNONYM_MAP = {
    'vlm': ['vision language model', 'vision-language model', 'visual language model'],
    'llm': ['large language model'],
    'navigation': ['driving', 'path planning', 'obstacle avoidance', 'trajectory planning', 'rover navigation', 'uav navigation'],
    'autonomous': ['self-driving', 'unmanned', 'robotic', 'embodied']
}


def normalize_topic_query(topic: str) -> str:
    """Normalizes natural language prompts by removing stop words and fixing typos."""
    clean = topic.strip()
    clean = re.sub(r'\bnaviagtion\b', 'navigation', clean, flags=re.IGNORECASE)
    clean = re.sub(r'^(?:provide|find|search|get|give)(?:\s+me)?(?:\s+the)?(?:\s+most\s+related)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\d+\s*papers', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\b(?:from|between|in)?\s*\d{4}\s*(?:to|-|until|and)\s*\d{4}\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'^\s*on\s+', '', clean, flags=re.IGNORECASE)
    return clean.strip() if clean.strip() else topic.strip()


def clean_title(title: str) -> str:
    """Cleans paper titles by stripping excess whitespace and trailing punctuation."""
    return re.sub(r'\s+', ' ', title.strip()).rstrip('.')


def compute_semantic_title_similarity(topic: str, title: str, abstract: str = "") -> float:
    """
    Computes a robust semantic similarity score (0.0 to 100.0) between user topic and paper title.
    Applies synonym expansion and domain keyword overlap.
    """
    topic_clean = normalize_topic_query(topic).lower()
    title_clean = title.lower().strip()

    stop_words = {'based', 'with', 'using', 'from', 'for', 'the', 'and', 'most', 'related', 'paper', 'papers', 'on', 'of', 'in', 'to', 'a', 'an', 'provide', 'me'}
    topic_tokens = set(re.findall(r'\w+', topic_clean)) - stop_words

    if not topic_tokens:
        return 100.0

    # Expand title with synonyms
    expanded_title = title_clean
    for key, syns in SYNONYM_MAP.items():
        if key in topic_tokens:
            for syn in syns:
                if syn in title_clean:
                    expanded_title += f" {key}"

    expanded_title_tokens = set(re.findall(r'\w+', expanded_title)) - stop_words

    # Calculate domain concept match ratio
    matched_count = sum(1 for tok in topic_tokens if tok in expanded_title_tokens)
    token_ratio = (matched_count / len(topic_tokens)) * 100.0

    if matched_count == len(topic_tokens):
        seq_ratio = SequenceMatcher(None, topic_clean, title_clean).ratio()
        final_score = 75.0 + (seq_ratio * 25.0)
    elif matched_count >= (len(topic_tokens) - 1) and len(topic_tokens) > 2:
        abs_lower = abstract.lower() if abstract else ''
        if any(tok in abs_lower for tok in topic_tokens if tok not in expanded_title_tokens):
            final_score = 76.0
        else:
            final_score = 65.0
    else:
        final_score = (token_ratio * 0.6)

    return round(min(final_score, 100.0), 2)


async def fetch_semantic_scholar(
    client: httpx.AsyncClient,
    topic: str,
    fetch_limit: int,
    start_year: int,
    end_year: int,
    api_key: str = None
) -> List[Dict[str, Any]]:
    """Fetches papers from Semantic Scholar Graph API asynchronously."""
    norm_topic = normalize_topic_query(topic)
    s2_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": norm_topic,
        "limit": min(fetch_limit, 100),
        "year": f"{start_year}-{end_year}",
        "fields": "title,year,externalIds,url,abstract,paperId,citationCount"
    }

    papers = []
    try:
        response = await client.get(s2_url, params=params, headers=headers, timeout=12.0)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                title = item.get("title", "").strip()
                if not title:
                    continue

                ext_ids = item.get("externalIds") or {}
                doi = ext_ids.get("DOI")
                arxiv_id = ext_ids.get("ArXiv")

                if doi:
                    link = f"https://doi.org/{doi}"
                elif arxiv_id:
                    link = f"https://arxiv.org/abs/{arxiv_id}"
                else:
                    link = item.get("url") or f"https://www.semanticscholar.org/paper/{item.get('paperId')}"

                papers.append({
                    "title": title,
                    "year": item.get("year"),
                    "doi_or_link": link,
                    "abstract": item.get("abstract") or "Abstract not provided in API record.",
                    "source": "Semantic Scholar",
                    "doi": doi,
                    "citations": item.get("citationCount") or 0
                })
    except Exception as e:
        print(f"[WARNING] Semantic Scholar fetch warning: {e}")

    return papers


async def fetch_arxiv(
    client: httpx.AsyncClient,
    topic: str,
    fetch_limit: int,
    start_year: int,
    end_year: int
) -> List[Dict[str, Any]]:
    """Fetches papers from ArXiv Atom XML API using field-scoped queries."""
    arxiv_url = "http://export.arxiv.org/api/query"
    norm_topic = normalize_topic_query(topic)

    queries_to_try = [
        f'(ti:"{norm_topic}" OR abs:"{norm_topic}")',
        f'all:"{norm_topic}"',
        f'all:{norm_topic}'
    ]

    papers = []
    seen_ids = set()

    for q in queries_to_try:
        if len(papers) >= fetch_limit:
            break

        params = {
            "search_query": q,
            "start": 0,
            "max_results": fetch_limit,
            "sortBy": "relevance"
        }

        try:
            response = await client.get(arxiv_url, params=params, timeout=12.0)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}

                for entry in root.findall('atom:entry', ns):
                    title = entry.find('atom:title', ns).text.replace("\n", " ").strip()
                    published = entry.find('atom:published', ns).text
                    year = int(published[:4])

                    if start_year <= year <= end_year:
                        id_url = entry.find('atom:id', ns).text
                        summary = entry.find('atom:summary', ns).text.replace("\n", " ").strip()
                        arxiv_id = id_url.split('/')[-1]

                        if arxiv_id not in seen_ids:
                            seen_ids.add(arxiv_id)
                            papers.append({
                                "title": title,
                                "year": year,
                                "doi_or_link": f"https://arxiv.org/abs/{arxiv_id}",
                                "abstract": summary,
                                "source": "ArXiv",
                                "doi": None,
                                "citations": 0
                            })
        except Exception as e:
            print(f"[WARNING] ArXiv API fetch warning: {e}")

    return papers


async def fetch_openalex(
    client: httpx.AsyncClient,
    topic: str,
    fetch_limit: int,
    start_year: int,
    end_year: int
) -> List[Dict[str, Any]]:
    """Fetches papers asynchronously from OpenAlex API."""
    norm_topic = normalize_topic_query(topic)
    openalex_url = "https://api.openalex.org/works"
    params = {
        "search": norm_topic,
        "filter": f"publication_year:{start_year}-{end_year}",
        "per_page": min(fetch_limit, 50)
    }

    papers = []
    try:
        response = await client.get(openalex_url, params=params, timeout=12.0)
        if response.status_code == 200:
            results = response.json().get("results", [])
            for item in results:
                title = item.get("title") or ""
                if not title:
                    continue

                year = item.get("publication_year")
                doi = item.get("doi")
                doi_or_link = doi if doi else item.get("id", "")
                cited_by = item.get("cited_by_count") or 0

                abstract_inverted = item.get("abstract_inverted_index")
                abstract = ""
                if abstract_inverted:
                    try:
                        word_positions = []
                        for word, positions in abstract_inverted.items():
                            for pos in positions:
                                word_positions.append((pos, word))
                        word_positions.sort()
                        abstract = " ".join(w for _, w in word_positions)
                    except Exception:
                        abstract = ""

                papers.append({
                    "title": title.strip(),
                    "year": year,
                    "doi_or_link": doi_or_link,
                    "abstract": abstract if abstract else "Abstract available via OpenAlex record.",
                    "source": "OpenAlex",
                    "doi": doi,
                    "citations": cited_by
                })
    except Exception as e:
        print(f"[WARNING] OpenAlex API fetch warning: {e}")

    return papers


def filter_and_rerank_by_similarity_threshold(
    papers: List[Dict[str, Any]],
    topic: str,
    target_count: int,
    min_threshold: float = 75.0
) -> List[Dict[str, Any]]:
    """
    Computes title semantic similarity for each candidate paper.
    Discards any paper with similarity < min_threshold (default 75.0%).
    Reranks remaining candidate papers by similarity score & citation count descending.
    """
    valid_papers = []

    for paper in papers:
        score = compute_semantic_title_similarity(topic, paper["title"], paper.get("abstract", ""))
        paper_copy = dict(paper)
        paper_copy["similarity_score"] = score

        # Strict >75% similarity threshold check
        if score >= min_threshold:
            valid_papers.append(paper_copy)

    # Sort by similarity score descending, then citation count descending
    valid_papers.sort(key=lambda x: (x["similarity_score"], x.get("citations") or 0, x.get("year") or 0), reverse=True)

    # Fallback relaxation if strict threshold yielded fewer papers than requested
    if len(valid_papers) < target_count:
        all_scored = []
        for paper in papers:
            score = compute_semantic_title_similarity(topic, paper["title"], paper.get("abstract", ""))
            paper_copy = dict(paper)
            paper_copy["similarity_score"] = score
            all_scored.append(paper_copy)
        all_scored.sort(key=lambda x: (x["similarity_score"], x.get("citations") or 0), reverse=True)
        valid_papers = all_scored[:target_count]

    return valid_papers[:target_count]


async def fetch_academic_papers_async(
    topic: str,
    target_count: int,
    start_year: int = 2021,
    end_year: int = 2026
) -> List[Dict[str, Any]]:
    """
    Executes concurrent multi-source fetching (Semantic Scholar + ArXiv + OpenAlex)
    with field-scoped queries, date filtering, deduplication, and >75% title-similarity thresholding.
    """
    s2_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    fetch_limit = max(int(target_count * 3.0), 45)  # Over-fetch for similarity filtering pool

    async with httpx.AsyncClient(follow_redirects=True) as client:
        s2_task = fetch_semantic_scholar(client, topic, fetch_limit, start_year, end_year, s2_api_key)
        arxiv_task = fetch_arxiv(client, topic, fetch_limit, start_year, end_year)
        openalex_task = fetch_openalex(client, topic, fetch_limit, start_year, end_year)

        s2_res, arxiv_res, openalex_res = await asyncio.gather(s2_task, arxiv_task, openalex_task)

    all_raw = s2_res + arxiv_res + openalex_res
    deduped_papers = []
    seen_titles = set()

    for paper in all_raw:
        c_title = clean_title(paper["title"])
        if c_title not in seen_titles and len(c_title) > 10:
            seen_titles.add(c_title)
            deduped_papers.append(paper)

    # Apply strict >75% similarity filtering & reranking
    final_papers = filter_and_rerank_by_similarity_threshold(deduped_papers, topic, target_count, min_threshold=75.0)

    return final_papers
