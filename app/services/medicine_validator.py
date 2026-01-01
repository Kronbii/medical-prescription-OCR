"""Medicine name validation service with database support and fuzzy matching"""
import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    print("Warning: rapidfuzz not installed. Using basic matching. Install with: pip install rapidfuzz", file=sys.stderr)

try:
    from phonetics import metaphone
    PHONETICS_AVAILABLE = True
except ImportError:
    PHONETICS_AVAILABLE = False
    print("Warning: phonetics not installed. Phonetic matching disabled. Install with: pip install phonetics", file=sys.stderr)

from app.core.config import Config


class MedicineValidator:
    """Service for validating and matching medicine names against a database"""
    
    def __init__(self, db_path: Optional[Path] = None, match_threshold: float = 0.75):
        """
        Initialize medicine validator
        
        Args:
            db_path: Path to medicine database file (JSON or CSV)
            match_threshold: Minimum similarity threshold (0.0-1.0) for matching
        """
        self.db_path = db_path
        self.match_threshold = match_threshold
        self.medicine_db: List[str] = []  # Preprocessed names for matching
        self.medicine_db_original: List[str] = []  # Original names for returning
        self.db_loaded = False
        
        if db_path:
            self._load_database()
    
    def _load_database(self) -> bool:
        """Load medicine database from file"""
        if not self.db_path or not self.db_path.exists():
            return False
        
        try:
            original_names = []
            
            if self.db_path.suffix.lower() == '.json':
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle different JSON structures
                    if isinstance(data, list):
                        original_names = [str(item) for item in data]
                    elif isinstance(data, dict):
                        # Check for 'medicines' key first (most common structure)
                        if 'medicines' in data:
                            original_names = [str(m) for m in data['medicines'] if m]
                        else:
                            # Fallback: try to extract string values
                            original_names = [str(v) for v in data.values() if isinstance(v, str) and v]
            elif self.db_path.suffix.lower() == '.csv':
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    # Assume first column contains medicine names
                    original_names = [row[0].strip() for row in reader if row and row[0].strip()]
            else:
                # Try to read as text file (one medicine per line)
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    original_names = [line.strip() for line in f if line.strip()]
            
            # Store original names
            self.medicine_db_original = [med for med in original_names if med]
            
            # Preprocess all database entries for faster matching
            self.medicine_db = [self._preprocess_name(med) for med in self.medicine_db_original]
            self.db_loaded = True
            return True
        except Exception as e:
            print(f"Warning: Failed to load medicine database from {self.db_path}: {e}", file=sys.stderr)
            return False
    
    def _preprocess_name(self, name: str) -> str:
        """
        Advanced preprocessing for medicine names
        
        Handles:
        - Lowercase conversion
        - Remove punctuation and special characters
        - Normalize whitespace
        - Handle common medical abbreviations
        - Remove dosage/strength information
        - Normalize common variations
        """
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove common dosage/strength patterns (e.g., "500mg", "10ml", "50%")
        # These can cause false mismatches
        normalized = re.sub(r'\b\d+\s*(mg|g|ml|l|%|mcg|iu|units?)\b', '', normalized, flags=re.IGNORECASE)
        
        # Remove common punctuation and special characters (keep alphanumeric and spaces)
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Normalize common medical abbreviations to standard forms
        # This helps match variations
        abbreviation_map = {
            r'\btab\b': 'tablet',
            r'\btabs\b': 'tablet',
            r'\bcaps\b': 'capsule',
            r'\bcapsules\b': 'capsule',
            r'\binj\b': 'injection',
            r'\bsyr\b': 'syrup',
            r'\bcre\b': 'cream',
            r'\bgel\b': 'gel',
            r'\botc\b': '',  # Remove OTC
            r'\brx\b': '',   # Remove Rx
        }
        
        for pattern, replacement in abbreviation_map.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        # Normalize whitespace (multiple spaces to single space)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove leading/trailing spaces
        normalized = normalized.strip()
        
        return normalized
    
    def _fuzzy_match_score(self, name1: str, name2: str) -> float:
        """
        Ultimate fuzzy match score using multiple advanced algorithms
        
        Uses:
        1. RapidFuzz (if available) - Multiple specialized algorithms
        2. Phonetic matching (Soundex/Metaphone) - For pronunciation variations
        3. Token-based matching - For word order differences
        4. Character n-grams - For typo handling
        5. Levenshtein distance - For edit distance
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not name1 or not name2:
            return 0.0
        
        # Exact match after preprocessing
        if name1 == name2:
            return 1.0
        
        scores = []
        weights = []
        
        # Method 1: RapidFuzz (if available) - Most accurate and fastest
        if RAPIDFUZZ_AVAILABLE:
            # Ratio: Standard string similarity (Levenshtein-based)
            ratio_score = fuzz.ratio(name1, name2) / 100.0
            scores.append(ratio_score)
            weights.append(0.25)
            
            # Partial Ratio: Best for when one string contains the other
            partial_score = fuzz.partial_ratio(name1, name2) / 100.0
            scores.append(partial_score)
            weights.append(0.20)
            
            # Token Sort Ratio: Ignores word order
            token_sort_score = fuzz.token_sort_ratio(name1, name2) / 100.0
            scores.append(token_sort_score)
            weights.append(0.20)
            
            # Token Set Ratio: Best for when one string is subset of another
            token_set_score = fuzz.token_set_ratio(name1, name2) / 100.0
            scores.append(token_set_score)
            weights.append(0.15)
        else:
            # Fallback: Use SequenceMatcher (slower but available)
            sequence_score = SequenceMatcher(None, name1, name2).ratio()
            scores.append(sequence_score)
            weights.append(0.40)
        
        # Method 2: Phonetic matching (for pronunciation variations)
        if PHONETICS_AVAILABLE:
            try:
                # Metaphone: Better than Soundex for medicine names
                meta1 = metaphone(name1)
                meta2 = metaphone(name2)
                if meta1 and meta2:
                    phonetic_score = 1.0 if meta1 == meta2 else 0.0
                    # Also check partial phonetic match
                    if not phonetic_score:
                        # Check if one is prefix of another (common in medicine names)
                        min_len = min(len(meta1), len(meta2))
                        if min_len >= 3:
                            phonetic_score = 0.5 if (meta1[:min_len] == meta2[:min_len]) else 0.0
                    scores.append(phonetic_score)
                    weights.append(0.10)
            except Exception:
                pass  # Skip phonetic if it fails
        
        # Method 3: Token-based Jaccard similarity (word-level)
        tokens1 = set(name1.split())
        tokens2 = set(name2.split())
        
        if tokens1 and tokens2:
            intersection = tokens1 & tokens2
            union = tokens1 | tokens2
            token_jaccard = len(intersection) / len(union) if union else 0.0
            scores.append(token_jaccard)
            weights.append(0.10)
        
        # Method 4: Character n-gram similarity (typo handling)
        def get_ngrams(text: str, n: int = 3) -> set:
            """Get character n-grams"""
            if len(text) < n:
                return {text}
            return {text[i:i+n] for i in range(len(text) - n + 1)}
        
        ngrams1 = get_ngrams(name1, n=3)
        ngrams2 = get_ngrams(name2, n=3)
        
        if ngrams1 and ngrams2:
            ngram_intersection = ngrams1 & ngrams2
            ngram_union = ngrams1 | ngrams2
            ngram_score = len(ngram_intersection) / len(ngram_union) if ngram_union else 0.0
            scores.append(ngram_score)
            weights.append(0.05)
        
        # Method 5: Substring/contains matching (for abbreviations)
        contains_score = 0.0
        if name1 in name2 or name2 in name1:
            shorter = min(len(name1), len(name2))
            longer = max(len(name1), len(name2))
            contains_score = shorter / longer if longer > 0 else 0.0
            scores.append(contains_score)
            weights.append(0.05)
        
        # Normalize weights to sum to 1.0
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        
        # Weighted average of all scores
        final_score = sum(score * weight for score, weight in zip(scores, weights))
        
        return min(final_score, 1.0)
    
    def find_closest_match(self, detected_name: str) -> Tuple[Optional[str], float]:
        """
        Find closest matching medicine in database using optimized search
        
        Uses RapidFuzz.process.extractOne for fast database search if available,
        otherwise falls back to custom fuzzy matching.
        
        Args:
            detected_name: Medicine name detected from prescription
            
        Returns:
            Tuple of (original_matched_medicine_name, similarity_score)
            Returns (None, 0.0) if no match above threshold
        """
        if not self.db_loaded or not self.medicine_db:
            return None, 0.0
        
        # Preprocess detected name
        preprocessed = self._preprocess_name(detected_name)
        
        if not preprocessed:
            return None, 0.0
        
        best_index = -1
        best_score = 0.0
        
        # Use RapidFuzz for fast database search (much faster for large DBs)
        if RAPIDFUZZ_AVAILABLE and len(self.medicine_db) > 10:
            try:
                # RapidFuzz's process.extractOne is optimized for large lists
                # It uses the best algorithm automatically
                result = process.extractOne(
                    preprocessed,
                    self.medicine_db,
                    scorer=fuzz.WRatio,  # Weighted ratio (best overall)
                    score_cutoff=self.match_threshold * 100  # Convert to 0-100 scale
                )
                
                if result:
                    matched_preprocessed, score, index = result
                    best_score = score / 100.0  # Convert back to 0-1 scale
                    best_index = index
            except Exception:
                # Fall back to custom matching if RapidFuzz fails
                pass
        
        # If RapidFuzz didn't find a match or isn't available, use custom matching
        if best_index == -1:
            for idx, db_medicine_preprocessed in enumerate(self.medicine_db):
                score = self._fuzzy_match_score(preprocessed, db_medicine_preprocessed)
                if score > best_score:
                    best_score = score
                    best_index = idx
        
        # Check if score meets threshold
        if best_score >= self.match_threshold and best_index >= 0:
            # Return original name from database (not preprocessed)
            return self.medicine_db_original[best_index], best_score
        
        return None, best_score
    
    def validate_medicine(self, detected_name: str) -> Dict[str, any]:
        """
        Validate a medicine name against database
        
        Args:
            detected_name: Medicine name to validate
            
        Returns:
            Dict with:
            - valid: bool
            - matched_name: str or None (original name from DB if match found)
            - similarity_score: float
            - status: "in_stock", "not_in_stock", or "unknown"
            - detected_name: str (original detected name)
        """
        if not self.db_loaded:
            return {
                'valid': False,
                'matched_name': None,
                'similarity_score': 0.0,
                'status': 'unknown',  # No database available
                'detected_name': detected_name
            }
        
        matched_name, score = self.find_closest_match(detected_name)
        
        if matched_name and score >= self.match_threshold:
            return {
                'valid': True,
                'matched_name': matched_name,  # This is the matched name from DB
                'similarity_score': score,
                'status': 'in_stock',
                'detected_name': detected_name
            }
        else:
            return {
                'valid': False,
                'matched_name': None,
                'similarity_score': score,
                'status': 'not_in_stock',  # Below threshold - not in stock
                'detected_name': detected_name
            }
    
    def validate_medicines_batch(self, detected_names: List[str]) -> List[Dict[str, any]]:
        """
        Validate multiple medicine names
        
        Args:
            detected_names: List of medicine names to validate
            
        Returns:
            List of validation results
        """
        return [self.validate_medicine(name) for name in detected_names]

