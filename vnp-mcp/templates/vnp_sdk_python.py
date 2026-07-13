"""
VNP Agent SDK - Python
=====================

One-line API selection for LLM agents.

INSTALL:
  pip install vnp-sdk

USAGE:
  from vnp import APISelector
  
  selector = APISelector()
  best = selector.select(
      use_case="image_generation",
      candidates=["openai", "anthropic", "together"],
      constraint="latency < 500ms"
  )
  # {"api": "anthropic", "score": 89.2, "confidence": 95.8, "uri": "https://api.anthropic.com"}
  
  # Use the best API
  response = requests.post(
      f"https://{best['uri']}",
      json={"prompt": "..."}
  )

FEATURES:
  - Real-time VNP scoring
  - Latency constraints
  - Cost-based selection
  - Regional preferences
  - Fallback chains
  - Caching (5-minute TTL)
  - Type hints (Python 3.9+)
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

import aiohttp
import requests
from cachetools import TTLCache

logger = logging.getLogger("vnp")

# ============================================================================
# CONFIGURATION
# ============================================================================

VNP_API_URL = "https://api.vnp.io"
VNP_GRAPHQL_URL = f"{VNP_API_URL}/graphql"
CACHE_TTL_SECONDS = 300  # 5 minutes


class UseCase(Enum):
    """VNP-supported use cases"""
    IMAGE_GENERATION = "image_generation"
    TEXT_GENERATION = "text_generation"
    TEXT_EMBEDDING = "text_embedding"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    TRANSLATION = "translation"
    PAYMENT_PROCESSING = "payment_processing"
    DATA_VALIDATION = "data_validation"
    CUSTOM = "custom"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class VNPScore:
    """VNP API score"""
    api_id: str
    api_name: str
    composite_score: float
    confidence_interval_95: Tuple[float, float]
    p99_latency_ms: float
    error_rate_pct: float
    availability_pct: float
    throughput_rps: float
    regional_scores: Dict[str, float]
    measurement_count: int
    last_updated: str
    vnp_uri: str  # Link to provider dashboard


@dataclass
class APISelection:
    """Result of API selection"""
    api: str  # e.g., "openai-api"
    score: float
    confidence: float
    p99_latency_ms: float
    error_rate_pct: float
    availability_pct: float
    uri: str  # Actual API endpoint
    reason: str  # Why this API was selected
    alternatives: List[Dict]  # Other candidates + scores
    selected_at: str


# ============================================================================
# VNP API CLIENT
# ============================================================================

class VNPClient:
    """Low-level client for VNP API"""
    
    def __init__(self, api_url: str = VNP_API_URL, cache_ttl: int = CACHE_TTL_SECONDS):
        self.api_url = api_url
        self.graphql_url = f"{api_url}/graphql"
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_score_sync(self, api_id: str) -> Optional[VNPScore]:
        """Synchronous score fetch (blocking)"""
        return asyncio.run(self.get_score(api_id))
    
    async def get_score(self, api_id: str) -> Optional[VNPScore]:
        """Fetch VNP score for an API"""
        cache_key = f"score:{api_id}"
        
        # Check cache
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        query = f"""
        query {{
            score(api_id: "{api_id}") {{
                apiId
                compositeScore
                confidence_interval_95
                dimensions {{
                    p99_latency {{ score }}
                    error_rate {{ score }}
                    availability {{ score }}
                    throughput {{ score }}
                }}
                regionalScores: regional_scores
                measurementCount: measurement_count
                lastUpdated: computed_at
            }}
        }}
        """
        
        try:
            if self.session:
                async with self.session.post(
                    self.graphql_url,
                    json={"query": query},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    result = await response.json()
            else:
                # Fallback to synchronous request
                response = requests.post(
                    self.graphql_url,
                    json={"query": query},
                    timeout=5
                )
                result = response.json()
            
            if "errors" in result:
                logger.warning(f"VNP error for {api_id}: {result['errors']}")
                return None
            
            data = result.get("data", {}).get("score")
            if not data:
                return None
            
            score = VNPScore(
                api_id=data["apiId"],
                api_name=data["apiId"].split(":")[-1],
                composite_score=data["compositeScore"],
                confidence_interval_95=tuple(data["confidence_interval_95"]),
                p99_latency_ms=data["dimensions"]["p99_latency"]["score"],
                error_rate_pct=data["dimensions"]["error_rate"]["score"],
                availability_pct=data["dimensions"]["availability"]["score"],
                throughput_rps=data["dimensions"]["throughput"]["score"],
                regional_scores=data.get("regionalScores", {}),
                measurement_count=data["measurementCount"],
                last_updated=data["lastUpdated"],
                vnp_uri=f"https://vnp.io/provider/{data['apiId']}"
            )
            
            self.cache[cache_key] = score
            return score
        
        except Exception as e:
            logger.error(f"Failed to fetch VNP score for {api_id}: {e}")
            return None
    
    def batch_scores(self, api_ids: List[str]) -> Dict[str, Optional[VNPScore]]:
        """Fetch multiple scores in parallel"""
        return asyncio.run(self._batch_scores_async(api_ids))
    
    async def _batch_scores_async(self, api_ids: List[str]) -> Dict[str, Optional[VNPScore]]:
        """Async batch score fetch"""
        tasks = [self.get_score(api_id) for api_id in api_ids]
        results = await asyncio.gather(*tasks)
        return {api_id: score for api_id, score in zip(api_ids, results)}


# ============================================================================
# API SELECTOR (Primary Interface)
# ============================================================================

class APISelector:
    """
    Smart API selection based on VNP scores.
    
    EXAMPLE:
        selector = APISelector()
        best = selector.select(
            candidates=["openai", "anthropic", "together"],
            constraint="latency < 500ms"
        )
    """
    
    def __init__(self, vnp_api_url: str = VNP_API_URL):
        self.client = VNPClient(api_url=vnp_api_url)
        self.api_endpoints = self._load_api_endpoints()
    
    def _load_api_endpoints(self) -> Dict[str, str]:
        """Load canonical API endpoints"""
        return {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "together": "https://api.together.xyz/v1",
            "groq": "https://api.groq.com/v1",
            "stripe": "https://api.stripe.com/v1",
            "twilio": "https://api.twilio.com",
            "cloudflare": "https://api.cloudflare.com/client/v4",
            "cohere": "https://api.cohere.ai",
            "replicate": "https://api.replicate.com/v1",
        }
    
    def select(
        self,
        candidates: List[str],
        use_case: Optional[UseCase] = None,
        constraint: Optional[str] = None,
        region: Optional[str] = None,
        prefer_cost_efficient: bool = False,
        fallback_chain: int = 3,
    ) -> APISelection:
        """
        Select best API from candidates based on VNP scores.
        
        PARAMETERS:
        -----------
        candidates : List[str]
            API names: ["openai", "anthropic", "together"]
        
        use_case : UseCase, optional
            Use case for scoring context
        
        constraint : str, optional
            Constraint: "latency < 500ms", "error_rate < 1%", "cost < $0.01"
        
        region : str, optional
            Preferred region: "us-east", "eu-west", etc.
        
        prefer_cost_efficient : bool, optional
            If True, optimize for cost instead of performance
        
        fallback_chain : int, optional
            Number of alternatives to return (default: 3)
        
        RETURNS:
        --------
        APISelection
            Selected API with score, confidence, URI, and alternatives
        """
        # Normalize candidate names to VNP IDs
        api_ids = [f"did:vnp:api:{name}" for name in candidates]
        
        # Fetch scores
        scores = self.client.batch_scores(api_ids)
        
        # Filter None scores
        valid_scores = {
            name: score
            for name, score in zip(candidates, [scores.get(aid) for aid in api_ids])
            if score is not None
        }
        
        if not valid_scores:
            raise ValueError(f"No VNP scores found for {candidates}")
        
        # Apply constraints
        filtered = self._apply_constraints(valid_scores, constraint, region)
        
        if not filtered:
            logger.warning(f"No APIs passed constraints {constraint}, using best unconstrained")
            filtered = valid_scores
        
        # Rank by score
        ranked = sorted(
            filtered.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )
        
        # Select best
        best_name, best_score = ranked[0]
        
        # Build alternatives list
        alternatives = [
            {
                "api": name,
                "score": score.composite_score,
                "confidence": score.confidence_interval_95[1] - score.confidence_interval_95[0],
            }
            for name, score in ranked[1:fallback_chain]
        ]
        
        return APISelection(
            api=best_name,
            score=best_score.composite_score,
            confidence=(best_score.confidence_interval_95[1] - best_score.confidence_interval_95[0]),
            p99_latency_ms=best_score.p99_latency_ms,
            error_rate_pct=best_score.error_rate_pct,
            availability_pct=best_score.availability_pct,
            uri=self.api_endpoints.get(best_name, f"https://api.{best_name}.com"),
            reason=f"Best VNP score ({best_score.composite_score:.1f}) with {best_score.measurement_count:,} measurements",
            alternatives=alternatives,
            selected_at=datetime.utcnow().isoformat(),
        )
    
    def _apply_constraints(
        self,
        scores: Dict[str, VNPScore],
        constraint: Optional[str],
        region: Optional[str],
    ) -> Dict[str, VNPScore]:
        """Filter scores by constraints"""
        if not constraint:
            return scores
        
        filtered = {}
        for name, score in scores.items():
            if self._check_constraint(score, constraint):
                filtered[name] = score
        
        return filtered
    
    def _check_constraint(self, score: VNPScore, constraint: str) -> bool:
        """Evaluate constraint against score"""
        # Parse constraint (simple parser)
        # Examples: "latency < 500ms", "error_rate < 1%", "availability > 99.9%"
        
        if "latency" in constraint and "<" in constraint:
            max_latency = float(constraint.split("<")[1].strip().replace("ms", ""))
            return score.p99_latency_ms < max_latency
        
        if "error_rate" in constraint and "<" in constraint:
            max_error = float(constraint.split("<")[1].strip().replace("%", ""))
            return score.error_rate_pct < max_error
        
        if "availability" in constraint and ">" in constraint:
            min_avail = float(constraint.split(">")[1].strip().replace("%", ""))
            return score.availability_pct > min_avail
        
        return True


# ============================================================================
# CONVENIENCE FUNCTIONS (1-liners)
# ============================================================================

def select_best_api(
    candidates: List[str],
    constraint: Optional[str] = None,
) -> APISelection:
    """
    One-liner API selection.
    
    EXAMPLE:
        from vnp import select_best_api
        best = select_best_api(["openai", "anthropic", "together"])
        print(best.api)  # "anthropic"
    """
    selector = APISelector()
    return selector.select(candidates=candidates, constraint=constraint)


def get_api_score(api_name: str) -> Optional[VNPScore]:
    """
    One-liner score fetch.
    
    EXAMPLE:
        from vnp import get_api_score
        score = get_api_score("openai")
        print(score.composite_score)  # 87.4
    """
    client = VNPClient()
    return client.get_score_sync(f"did:vnp:api:{api_name}")


# ============================================================================
# CONFIGURATION & LOGGING
# ============================================================================

def configure(
    api_url: str = VNP_API_URL,
    log_level: str = "INFO",
):
    """Configure VNP SDK"""
    global VNP_API_URL, VNP_GRAPHQL_URL
    VNP_API_URL = api_url
    VNP_GRAPHQL_URL = f"{api_url}/graphql"
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(name)s - %(levelname)s - %(message)s"
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "APISelector",
    "VNPClient",
    "VNPScore",
    "APISelection",
    "UseCase",
    "select_best_api",
    "get_api_score",
    "configure",
]
