"""Sentiment analysis service for news and market data"""

import logging
from typing import Dict, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class SentimentService:
    """
    Analyzes sentiment of news articles and text.
    
    Supports two backends:
    1. Transformers (DistilBERT) - better accuracy, requires torch
    2. TextBlob - fallback, no dependencies
    
    Returns normalized scores: -1.0 (bearish) to 1.0 (bullish)
    """
    
    def __init__(self, use_transformers: bool = True):
        """
        Initialize sentiment service.
        
        Args:
            use_transformers: If True, try to use DistilBERT; fallback to TextBlob
        """
        self.use_transformers = use_transformers
        self.sentiment_pipeline = None
        self.textblob_available = False
        
        # Try to load transformers model
        if use_transformers:
            try:
                from transformers import pipeline
                self.sentiment_pipeline = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english"
                )
                logger.info("Loaded DistilBERT sentiment model")
            except Exception as e:
                logger.warning(f"Failed to load transformers: {e}. Will fallback to TextBlob.")
                self.use_transformers = False
        
        # Setup TextBlob fallback
        if not self.use_transformers:
            try:
                from textblob import TextBlob
                self.textblob_available = True
                logger.info("TextBlob sentiment available as fallback")
            except ImportError:
                logger.warning("TextBlob not installed. Install with: pip install textblob")
                self.textblob_available = False
    
    def analyze_text(self, text: str) -> Dict:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze (e.g., news headline + description)
        
        Returns:
            {
                'sentiment_score': float (-1.0 to 1.0),
                'sentiment_label': str ('bearish', 'neutral', 'bullish'),
                'confidence': float (0.0 to 1.0),
                'model': str ('transformers' or 'textblob')
            }
        """
        if not text:
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'confidence': 0.0,
                'model': 'none'
            }
        
        # Clean and truncate text
        text = text.strip()[:512]  # Limit to 512 chars for transformer efficiency
        
        if self.use_transformers and self.sentiment_pipeline:
            return self._analyze_with_transformers(text)
        elif self.textblob_available:
            return self._analyze_with_textblob(text)
        else:
            logger.warning("No sentiment model available")
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'confidence': 0.0,
                'model': 'none'
            }
    
    def _analyze_with_transformers(self, text: str) -> Dict:
        """
        Analyze sentiment using DistilBERT transformers.
        
        Returns normalized -1.0 to 1.0 score.
        """
        try:
            result = self.sentiment_pipeline(text)[0]
            label = result['label']  # 'POSITIVE' or 'NEGATIVE'
            score = result['score']  # 0.0 to 1.0 confidence
            
            # Convert to -1 to 1 scale
            if label == 'POSITIVE':
                sentiment_score = score
                sentiment_label = 'bullish' if score > 0.7 else 'neutral'
            else:  # NEGATIVE
                sentiment_score = -score
                sentiment_label = 'bearish' if score > 0.7 else 'neutral'
            
            return {
                'sentiment_score': round(float(sentiment_score), 3),
                'sentiment_label': sentiment_label,
                'confidence': round(score, 3),
                'model': 'transformers'
            }
        
        except Exception as e:
            logger.error(f"Error in transformer sentiment analysis: {e}")
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'confidence': 0.0,
                'model': 'transformers_error'
            }
    
    def _analyze_with_textblob(self, text: str) -> Dict:
        """
        Analyze sentiment using TextBlob (fallback).
        
        TextBlob polarity: -1.0 to 1.0 (already in right range)
        """
        try:
            from textblob import TextBlob
            
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
            
            # Determine label based on polarity
            if polarity > 0.1:
                sentiment_label = 'bullish' if polarity > 0.5 else 'neutral'
            elif polarity < -0.1:
                sentiment_label = 'bearish' if polarity < -0.5 else 'neutral'
            else:
                sentiment_label = 'neutral'
            
            # Confidence is inverse of subjectivity (objective = more confident)
            confidence = 1.0 - subjectivity
            
            return {
                'sentiment_score': round(float(polarity), 3),
                'sentiment_label': sentiment_label,
                'confidence': round(confidence, 3),
                'model': 'textblob'
            }
        
        except Exception as e:
            logger.error(f"Error in TextBlob sentiment analysis: {e}")
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'confidence': 0.0,
                'model': 'textblob_error'
            }
    
    def extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """
        Extract keywords from text.
        
        Simple implementation using TextBlob (no dependency on transformer).
        
        Args:
            text: Text to extract keywords from
            max_keywords: Maximum keywords to return
        
        Returns:
            List of keyword strings
        """
        try:
            from textblob import TextBlob
            
            blob = TextBlob(text.lower())
            
            # Filter words: length > 4 chars, not stopwords
            stopwords = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
                'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
                'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
            }
            
            words = [
                word for word in blob.words
                if len(word) > 4 and word.lower() not in stopwords
            ]
            
            # Return top N by frequency (simple approach)
            from collections import Counter
            if words:
                counter = Counter(words)
                top_words = [word for word, _ in counter.most_common(max_keywords)]
                return top_words
            
            return []
        
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    def batch_analyze(self, texts: List[str]) -> List[Dict]:
        """
        Analyze sentiment for multiple texts efficiently.
        
        Args:
            texts: List of text strings
        
        Returns:
            List of sentiment dicts
        """
        results = []
        for text in texts:
            try:
                result = self.analyze_text(text)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch analysis: {e}")
                results.append({
                    'sentiment_score': 0.0,
                    'sentiment_label': 'neutral',
                    'confidence': 0.0,
                    'model': 'error'
                })
        
        return results
