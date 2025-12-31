"""
Automated evaluation system for measuring deal detection quality.
Creates test fixtures, runs evaluations, and computes metrics.
"""
import json
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from .schemas import EvaluationResult, RankedListing


@dataclass
class EvaluationMetrics:
    """Metrics for a single evaluation run."""
    query: str
    timestamp: str
    total_listings: int
    top_k: int
    
    # Relevance metrics
    precision_at_k: float = 0.0  # % of top K that are actually good deals
    
    # Deal detection
    median_value_score: float = 0.0
    pct_below_median: float = 0.0  # % of top K priced below market median
    
    # Attribute extraction
    model_extraction_rate: float = 0.0  # % with model extracted
    storage_extraction_rate: float = 0.0  # % with storage extracted
    condition_extraction_rate: float = 0.0  # % with condition extracted
    battery_extraction_rate: float = 0.0  # % with battery extracted
    
    # Risk detection
    avg_risk_score: float = 0.0
    high_risk_count: int = 0
    
    # Comps quality
    avg_comps_size: float = 0.0
    comps_coverage: float = 0.0  # % of listings with valid comps
    
    # User interaction
    questions_generated: int = 0


@dataclass
class GoldSetItem:
    """A manually labeled item for evaluation."""
    listing_id: str
    title: str
    price: float
    is_relevant: bool  # Is this a valid search result?
    deal_quality: str  # "great", "good", "fair", "poor", "scam"
    expected_model: Optional[str] = None
    expected_storage: Optional[int] = None
    expected_condition: Optional[str] = None
    notes: str = ""


class AutomatedEvaluator:
    """System for automated evaluation of deal detection quality."""
    
    def __init__(self, gold_set_path: Optional[str] = None):
        self.gold_set: list[GoldSetItem] = []
        self.eval_history: list[EvaluationMetrics] = []
        
        # Load gold set if exists
        if gold_set_path and os.path.exists(gold_set_path):
            self.load_gold_set(gold_set_path)
    
    def load_gold_set(self, path: str):
        """Load gold set from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.gold_set = [GoldSetItem(**item) for item in data]
    
    def save_gold_set(self, path: str):
        """Save gold set to JSON file."""
        data = [
            {
                "listing_id": item.listing_id,
                "title": item.title,
                "price": item.price,
                "is_relevant": item.is_relevant,
                "deal_quality": item.deal_quality,
                "expected_model": item.expected_model,
                "expected_storage": item.expected_storage,
                "expected_condition": item.expected_condition,
                "notes": item.notes,
            }
            for item in self.gold_set
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def compute_metrics(self, result: EvaluationResult) -> EvaluationMetrics:
        """Compute all metrics for an evaluation result."""
        ranked = result.ranked_listings
        k = len(ranked)
        
        if k == 0:
            return EvaluationMetrics(
                query=result.query,
                timestamp=result.evaluated_at,
                total_listings=result.total_evaluated,
                top_k=k,
            )
        
        # Value score analysis
        value_scores = [l.scores.value_score.score for l in ranked]
        median_value = sorted(value_scores)[len(value_scores) // 2] if value_scores else 0
        
        # Deal delta analysis (% below market)
        below_median = sum(
            1 for l in ranked 
            if l.scores.value_score.deal_delta and l.scores.value_score.deal_delta > 0
        )
        pct_below = (below_median / k * 100) if k > 0 else 0
        
        # Attribute extraction rates
        model_count = sum(1 for l in ranked if l.attributes.model_variant)
        storage_count = sum(1 for l in ranked if l.attributes.storage_gb)
        condition_count = sum(1 for l in ranked if l.attributes.condition.value != "unknown")
        battery_count = sum(1 for l in ranked if l.attributes.battery_health is not None)
        
        # Risk analysis
        risk_scores = [l.scores.risk_assessment.score for l in ranked]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        high_risk = sum(1 for s in risk_scores if s >= 50)
        
        # Comps analysis
        comps_sizes = [l.scores.value_score.comps_n for l in ranked]
        avg_comps = sum(comps_sizes) / len(comps_sizes) if comps_sizes else 0
        with_comps = sum(1 for s in comps_sizes if s >= 5)
        comps_coverage = (with_comps / k * 100) if k > 0 else 0
        
        # Precision against gold set
        precision = self._compute_precision(ranked)
        
        return EvaluationMetrics(
            query=result.query,
            timestamp=result.evaluated_at,
            total_listings=result.total_evaluated,
            top_k=k,
            precision_at_k=precision,
            median_value_score=median_value,
            pct_below_median=pct_below,
            model_extraction_rate=(model_count / k * 100) if k > 0 else 0,
            storage_extraction_rate=(storage_count / k * 100) if k > 0 else 0,
            condition_extraction_rate=(condition_count / k * 100) if k > 0 else 0,
            battery_extraction_rate=(battery_count / k * 100) if k > 0 else 0,
            avg_risk_score=avg_risk,
            high_risk_count=high_risk,
            avg_comps_size=avg_comps,
            comps_coverage=comps_coverage,
            questions_generated=len(result.questions),
        )
    
    def _compute_precision(self, ranked: list[RankedListing]) -> float:
        """Compute precision@K against gold set."""
        if not self.gold_set:
            return -1.0  # No gold set available
        
        gold_ids = {item.listing_id for item in self.gold_set if item.deal_quality in ("great", "good")}
        
        if not gold_ids:
            return -1.0
        
        correct = sum(1 for l in ranked if l.listing_id in gold_ids)
        return (correct / len(ranked) * 100) if ranked else 0
    
    def run_evaluation(
        self,
        query: str,
        listings: list[dict],
        preferences: dict,
    ) -> tuple[EvaluationResult, EvaluationMetrics]:
        """Run evaluation and compute metrics."""
        from .pipeline import run_evaluation
        
        result = run_evaluation(
            query=query,
            listings=listings,
            preferences=preferences,
        )
        
        metrics = self.compute_metrics(result)
        self.eval_history.append(metrics)
        
        return result, metrics
    
    def generate_report(self) -> str:
        """Generate a summary report of all evaluations."""
        if not self.eval_history:
            return "No evaluations run yet."
        
        lines = [
            "# Evaluation Report",
            f"Generated: {datetime.utcnow().isoformat()}Z",
            f"Total runs: {len(self.eval_history)}",
            "",
            "## Summary Statistics",
            "",
        ]
        
        # Aggregate metrics
        all_precision = [m.precision_at_k for m in self.eval_history if m.precision_at_k >= 0]
        all_below_median = [m.pct_below_median for m in self.eval_history]
        all_model_rate = [m.model_extraction_rate for m in self.eval_history]
        all_comps_coverage = [m.comps_coverage for m in self.eval_history]
        
        if all_precision:
            lines.append(f"- **Avg Precision@K**: {sum(all_precision)/len(all_precision):.1f}%")
        lines.append(f"- **Avg % Below Median**: {sum(all_below_median)/len(all_below_median):.1f}%")
        lines.append(f"- **Avg Model Extraction**: {sum(all_model_rate)/len(all_model_rate):.1f}%")
        lines.append(f"- **Avg Comps Coverage**: {sum(all_comps_coverage)/len(all_comps_coverage):.1f}%")
        
        lines.extend(["", "## Per-Query Results", ""])
        
        for m in self.eval_history[-10:]:  # Last 10
            lines.append(f"### {m.query}")
            lines.append(f"- Top {m.top_k} of {m.total_listings} listings")
            lines.append(f"- Value score median: {m.median_value_score:.0f}")
            lines.append(f"- Below market: {m.pct_below_median:.0f}%")
            lines.append(f"- Model extraction: {m.model_extraction_rate:.0f}%")
            lines.append("")
        
        return "\n".join(lines)
    
    def save_report(self, path: str):
        """Save report to file."""
        report = self.generate_report()
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
    
    def to_json(self) -> dict:
        """Export all metrics as JSON."""
        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_runs": len(self.eval_history),
            "evaluations": [
                {
                    "query": m.query,
                    "timestamp": m.timestamp,
                    "precision_at_k": m.precision_at_k,
                    "pct_below_median": m.pct_below_median,
                    "model_extraction_rate": m.model_extraction_rate,
                    "storage_extraction_rate": m.storage_extraction_rate,
                    "avg_comps_size": m.avg_comps_size,
                    "high_risk_count": m.high_risk_count,
                }
                for m in self.eval_history
            ],
        }
