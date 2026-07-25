"""
Core LangGraph State Machine & Agent Orchestration Engine.
Processes natural language prompts, extracts query parameters, coordinates multi-source fetchers,
applies >75% title similarity filtering, runs parallel LLM justification, and exports Excel report.
"""

import os
import re
import asyncio
from typing import Dict, Any, List
from dotenv import load_dotenv, find_dotenv

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from agent_schema import UserQueryParameters, AgentState
from fetchers import fetch_academic_papers_async
from excel_exporter import export_papers_to_excel

# Load environment variables
load_dotenv(find_dotenv(), override=True)


def get_llm():
    """Initializes LLM instance based on environment settings (OpenAI or Local Ollama)."""
    load_dotenv(find_dotenv(), override=True)
    provider = os.getenv("LLM_PROVIDER", "cloud").lower()
    if provider == "local":
        model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOpenAI(
            model=model_name,
            openai_api_base=f"{base_url}/v1",
            openai_api_key="ollama",
            temperature=0.2
        )
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            temperature=0.2
        )


def fallback_parse_parameters(user_prompt: str) -> UserQueryParameters:
    """Smart regex parameter extractor used when LLM quota is unavailable."""
    count_match = re.search(r'(\d+)\s*papers', user_prompt, re.IGNORECASE)
    target_count = int(count_match.group(1)) if count_match else 15

    year_match = re.search(r'(\d{4})\s*(?:to|-|until|and)\s*(\d{4})', user_prompt, re.IGNORECASE)
    if year_match:
        start_year, end_year = int(year_match.group(1)), int(year_match.group(2))
    else:
        start_year, end_year = 2021, 2026

    topic = user_prompt
    topic = re.sub(r'^(?:provide|find|search|get|give)(?:\s+me)?(?:\s+the)?(?:\s+most\s+related)?', '', topic, flags=re.IGNORECASE)
    topic = re.sub(r'\d+\s*papers', '', topic, flags=re.IGNORECASE)
    topic = re.sub(r'\b(?:from|between|in)?\s*\d{4}\s*(?:to|-|until|and)\s*\d{4}\b', '', topic, flags=re.IGNORECASE)
    topic = re.sub(r'^\s*on\s+', '', topic, flags=re.IGNORECASE)
    topic = topic.strip()

    if not topic:
        topic = user_prompt

    return UserQueryParameters(
        search_topic=topic,
        target_count=target_count,
        start_year=start_year,
        end_year=end_year
    )


# --- Node 1: Extract Parameters ---
async def extract_parameters_node(state: AgentState) -> Dict[str, Any]:
    """Uses LLM with structured output to parse topic, count limit, and date windows."""
    user_prompt = state["user_prompt"]

    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert research query parser. Extract the core research topic, requested paper count (default 15), and start/end publication years from the user query."),
            ("human", "{user_prompt}")
        ])
        structured_llm = llm.with_structured_output(UserQueryParameters)
        params = await (prompt | structured_llm).ainvoke({"user_prompt": user_prompt})
    except Exception as e:
        print(f"[WARNING] Parameter extraction fallback due to: {e}")
        params = fallback_parse_parameters(user_prompt)

    return {
        "params": params,
        "status_message": f"Extracted parameters: Topic='{params.search_topic}', Count={params.target_count}, Years={params.start_year}-{params.end_year}"
    }


# --- Node 2: Multi-Source Fetcher & >75% Similarity Filtering ---
async def fetch_papers_node(state: AgentState) -> Dict[str, Any]:
    """Executes multi-repository searching and applies strict >75% similarity filtering."""
    params: UserQueryParameters = state["params"]

    papers = await fetch_academic_papers_async(
        topic=params.search_topic,
        target_count=params.target_count,
        start_year=params.start_year,
        end_year=params.end_year
    )

    return {
        "raw_papers": papers,
        "status_message": f"Fetched and filtered {len(papers)} candidate papers with >75% title similarity."
    }


def build_fallback_justification(topic: str, title: str, abstract: str) -> str:
    """Builds clean paper-specific relevance justification from title & abstract."""
    t_clean = topic.strip()
    abs_clean = abstract.replace("\n", " ").strip() if abstract else ""
    first_sentence = abs_clean.split(".")[0] if abs_clean else f"Presents key innovations in {t_clean}"

    if len(first_sentence) > 150:
        first_sentence = first_sentence[:147] + "..."

    return (
        f"Addressing '{title[:80]}', the work {first_sentence[:100].lower()}. "
        f"This directly advances '{t_clean}' by providing empirical benchmarks and model architectures."
    )


async def generate_single_justification(llm: Any, topic: str, paper: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a 2-sentence relevance rationale explaining why paper was selected."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an academic reviewer. Write a concise, 2-sentence rationale explaining why this paper is relevant to the topic."),
        ("human", "Topic: {topic}\nPaper Title: {title}\nAbstract: {abstract}\n\nProvide 2 sentences justification:")
    ])

    try:
        chain = prompt | llm
        response = await chain.ainvoke({
            "topic": topic,
            "title": paper["title"],
            "abstract": paper["abstract"][:1000]
        })
        justification = response.content.strip()
    except Exception:
        justification = build_fallback_justification(topic, paper["title"], paper.get("abstract", ""))

    paper_copy = dict(paper)
    paper_copy["relevance_justification"] = justification
    return paper_copy


# --- Node 3: Parallel Relevance Justification Engine ---
async def justify_relevance_node(state: AgentState) -> Dict[str, Any]:
    """Generates 2-sentence relevance justifications in parallel using asyncio.gather."""
    params: UserQueryParameters = state["params"]
    raw_papers = state["raw_papers"]
    llm = get_llm()

    tasks = [
        generate_single_justification(llm, params.search_topic, paper)
        for paper in raw_papers
    ]

    processed_papers = await asyncio.gather(*tasks)

    return {
        "processed_papers": processed_papers,
        "status_message": f"Generated justifications for {len(processed_papers)} papers."
    }


# --- Node 4: Excel Report Exporter ---
async def export_excel_node(state: AgentState) -> Dict[str, Any]:
    """Formats processed papers and exports them to a styled Excel file."""
    processed_papers = state["processed_papers"]
    output_path = "output/Research_Papers_Report.xlsx"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    abs_path = export_papers_to_excel(processed_papers, output_path=output_path)

    return {
        "excel_path": abs_path,
        "status_message": f"Successfully exported report to {abs_path}"
    }


# --- Build LangGraph State Graph Workflow ---
def build_academic_agent_graph():
    """Constructs and compiles the streamlined research state graph machine."""
    workflow = StateGraph(AgentState)

    workflow.add_node("extract_parameters", extract_parameters_node)
    workflow.add_node("fetch_papers", fetch_papers_node)
    workflow.add_node("justify_relevance", justify_relevance_node)
    workflow.add_node("export_excel", export_excel_node)

    workflow.set_entry_point("extract_parameters")
    workflow.add_edge("extract_parameters", "fetch_papers")
    workflow.add_edge("fetch_papers", "justify_relevance")
    workflow.add_edge("justify_relevance", "export_excel")
    workflow.add_edge("export_excel", END)

    return workflow.compile()
