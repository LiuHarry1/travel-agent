"""FAQ tool for travel-related questions."""
from __future__ import annotations

import asyncio
import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

from ..core.base_tool import BaseTool, ToolExecutionResult


class FAQTool(BaseTool):
    """FAQ tool that searches a travel FAQ knowledge base."""
    
    def __init__(self, csv_path: str | None = None):
        """
        Initialize FAQ tool.
        
        Args:
            csv_path: Optional path to CSV file. If not provided, uses default location.
        """
        super().__init__(
            name="faq",
            description="Travel FAQ Tool: A curated FAQ database for travel-related questions. Contains pre-approved answers to high-frequency questions, including: travel policy basics (eligibility, booking requirements, insurance coverage), approval workflows (domestic vs. international, required documents, timelines), visa requirements and application processes, expense reimbursement rules (per diem rates, allowable expenses, submission deadlines), and common exceptions and troubleshooting. Use Case: Best for direct, specific questions with predefined answers (e.g., 'What is the visa requirement for Japan?' 'How to apply for a travel visa?'). IMPORTANT: The query parameter must be in Chinese (中文) and must be travel-related."
        )
        
        # Determine CSV file path
        if csv_path is None:
            # Default path relative to this file
            current_dir = Path(__file__).parent.parent
            csv_path = current_dir / "data" / "travel-faq.csv"
        
        self.csv_path = Path(csv_path)
        self.faq_database: List[Tuple[str, str]] = []
        self.question_texts: List[str] = []  # List of question texts for BM25
        self.bm25: BM25Okapi | None = None
        self._load_faq_database()
        self._build_bm25_index()
    
    def _load_faq_database(self) -> None:
        """Load FAQ database from CSV file."""
        if not self.csv_path.exists():
            self.logger.warning(f"FAQ CSV file not found at {self.csv_path}")
            return
        
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    question = row.get("问题", "").strip()
                    answer = row.get("答案", "").strip()
                    if question and answer:
                        self.faq_database.append((question, answer))
            
            self.logger.info(f"Loaded {len(self.faq_database)} FAQ entries from {self.csv_path}")
        except Exception as e:
            self.logger.error(f"Error loading FAQ database from {self.csv_path}: {e}", exc_info=True)
    
    def _tokenize_chinese_text(self, text: str) -> List[str]:
        """
        Tokenize Chinese text for BM25 search.
        Uses character-level n-grams (unigrams, bigrams, trigrams) for Chinese text.
        
        Args:
            text: Input text in Chinese
            
        Returns:
            List of tokens
        """
        # Remove punctuation and whitespace
        text = re.sub(r'[，。！？、；：""''（）【】\s]', '', text)
        text = text.lower()
        
        if not text:
            return []
        
        tokens = []
        
        # Extract Chinese characters
        chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        
        if not chinese_chars:
            return []
        
        # Add unigrams (single characters)
        tokens.extend(chinese_chars)
        
        # Add bigrams (2-character sequences)
        if len(chinese_chars) >= 2:
            for i in range(len(chinese_chars) - 1):
                tokens.append(''.join(chinese_chars[i:i+2]))
        
        # Add trigrams (3-character sequences)
        if len(chinese_chars) >= 3:
            for i in range(len(chinese_chars) - 2):
                tokens.append(''.join(chinese_chars[i:i+3]))
        
        return tokens
    
    def _build_bm25_index(self) -> None:
        """Build BM25 index from FAQ questions."""
        if not self.faq_database:
            return
        
        if BM25Okapi is None:
            self.logger.warning("rank_bm25 not installed. Falling back to simple matching. Install with: pip install rank-bm25")
            return
        
        # Extract question texts and tokenize them
        self.question_texts = [question for question, _ in self.faq_database]
        tokenized_questions = [self._tokenize_chinese_text(q) for q in self.question_texts]
        
        # Build BM25 index
        try:
            self.bm25 = BM25Okapi(tokenized_questions)
            self.logger.info(f"Built BM25 index for {len(self.question_texts)} FAQ questions")
        except Exception as e:
            self.logger.error(f"Error building BM25 index: {e}", exc_info=True)
            self.bm25 = None
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for FAQ tool."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The travel-related question to search in FAQ knowledge base. Must be travel-related (visas, destinations, travel planning, approval workflows, expense reimbursement, etc.). Must be in Chinese (中文). Use for direct, specific questions with predefined answers. Do NOT use for questions about available tools, system capabilities, or non-travel topics."
                }
            },
            "required": ["query"]
        }
    
    def _search_with_bm25(self, query: str, top_k: int = 1) -> List[Tuple[int, float]]:
        """
        Search FAQ using BM25 algorithm.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of tuples (index, score) for top results
        """
        if self.bm25 is None or not self.faq_database:
            return []
        
        # Tokenize query
        query_tokens = self._tokenize_chinese_text(query)
        if not query_tokens:
            return []
        
        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k results
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = [(idx, scores[idx]) for idx in top_indices if scores[idx] > 0]
        
        return results
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute FAQ search.
        
        Args:
            arguments: Dictionary containing 'query' key with the search query
            
        Returns:
            ToolExecutionResult with FAQ answer
        """
        query = arguments.get("query", "").strip()
        
        if not query:
            return ToolExecutionResult(
                success=False,
                data=None,
                error="Query parameter is required"
            )
        
        # Simulate async processing delay
        await asyncio.sleep(0.1)  # Reduced delay since BM25 is fast
        
        if not self.faq_database:
            self.logger.warning("FAQ database is empty")
            return ToolExecutionResult(
                success=True,
                data={
                    "answer": None,
                    "found": False,
                    "message": "FAQ知识库为空。",
                    "source": "travel_faq_database"
                }
            )
        
        # Use BM25 for search if available, otherwise fall back to simple matching
        if self.bm25 is not None:
            # Search with BM25 - get top 5 results for reranking
            results = self._search_with_bm25(query, top_k=5)
            
            if results:
                query_lower = query.lower()
                # Extract important terms from query (location names, specific keywords)
                query_chars = [c for c in query if '\u4e00' <= c <= '\u9fff']
                specific_terms = []
                # Extract 2-4 character phrases from start of query
                for length in [4, 3, 2]:
                    if len(query_chars) >= length:
                        phrase = ''.join(query_chars[:length]).lower()
                        specific_terms.append(phrase)
                
                # Rerank results: prioritize matches that contain specific terms
                reranked_results = []
                for idx, bm25_score in results:
                    question, answer = self.faq_database[idx]
                    question_lower = question.lower()
                    
                    # Boost score if question contains specific terms
                    boost = 0.0
                    for term in specific_terms:
                        if term in question_lower:
                            boost += len(term) * 5  # Longer terms get more boost
                    
                    # If question contains query as substring, give extra boost
                    if query_lower in question_lower or question_lower in query_lower:
                        boost += 10
                    
                    adjusted_score = bm25_score + boost
                    reranked_results.append((idx, adjusted_score, bm25_score, question, answer))
                
                # Sort by adjusted score
                reranked_results.sort(key=lambda x: x[1], reverse=True)
                
                # BM25 scores are typically positive but not normalized to 0-1
                threshold = 1.0  # Minimum BM25 score to consider a match
                
                # Filter results by threshold and get top matches
                valid_results = []
                for idx, adjusted_score, bm25_score, matched_question, answer in reranked_results:
                    if bm25_score >= threshold:
                        normalized_score = min(1.0, bm25_score / 20.0)  # Adjusted normalization
                        valid_results.append({
                            "answer": answer,
                            "matched_question": matched_question,
                            "score": normalized_score,
                            "bm25_score": bm25_score
                        })
                
                if valid_results:
                    # Return top 3 results (or all if less than 3)
                    top_results = valid_results[:3]
                    self.logger.info(f"BM25 matched query '{query}' to {len(top_results)} question(s)")
                    return ToolExecutionResult(
                        success=True,
                        data={
                            "answers": top_results,
                            "count": len(top_results),
                            "source": "travel_faq_database"
                        },
                        metadata={"count": len(top_results)}
                    )
        
        # Fallback: simple keyword matching if BM25 not available or no match found
        # This is a simplified version for fallback
        query_lower = query.lower()
        matches: List[Tuple[str, str, float]] = []
        
        # Simple keyword-based matching as fallback
        query_chars = set(c for c in query_lower if '\u4e00' <= c <= '\u9fff')
        
        for question, answer in self.faq_database:
            question_lower = question.lower()
            question_chars = set(c for c in question_lower if '\u4e00' <= c <= '\u9fff')
            
            if not query_chars:
                continue
            
            # Calculate simple overlap score
            overlap = len(query_chars.intersection(question_chars))
            score = overlap / len(query_chars) if query_chars else 0.0
            
            # Check for substring match (exact or contained)
            if query_lower in question_lower or question_lower in query_lower:
                score = max(score, 0.8)
            
            if score >= 0.3:  # Threshold for valid matches
                matches.append((question, answer, score))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[2], reverse=True)
        
        threshold = 0.3
        if matches:
            # Return top 3 results (or all if less than 3)
            top_matches = matches[:3]
            results = [
                {
                    "answer": answer,
                    "matched_question": question,
                    "score": score
                }
                for question, answer, score in top_matches
            ]
            self.logger.info(f"Fallback matched query '{query}' to {len(results)} question(s)")
            return ToolExecutionResult(
                success=True,
                data={
                    "answers": results,
                    "count": len(results),
                    "source": "travel_faq_database"
                },
                metadata={"count": len(results)}
            )
        else:
            # No match found
            self.logger.info(f"No match for query '{query}'")
            return ToolExecutionResult(
                success=True,
                data={
                    "answers": [],
                    "count": 0,
                    "found": False,
                    "message": "No matching answers found in FAQ database.",
                    "source": "travel_faq_database"
                }
            )

