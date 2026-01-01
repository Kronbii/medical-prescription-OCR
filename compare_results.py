#!/usr/bin/env python3
"""
Compare results from different Gemini models

This script:
1. Reads results from gen-results directory
2. Compares extracted medicine names between models
3. Calculates match percentages and average processing times
4. Outputs comparison report to a text file
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import statistics


def normalize_medicine_name(name: str) -> str:
    """Normalize medicine name for comparison (lowercase, strip, remove special chars)"""
    if not name:
        return ""
    # Convert to lowercase, strip whitespace
    normalized = name.lower().strip()
    # Remove common punctuation and special characters for fuzzy matching
    normalized = normalized.replace("-", " ").replace("_", " ")
    # Remove extra spaces
    normalized = " ".join(normalized.split())
    return normalized


def load_model_results(results_dir: Path) -> Dict[str, Dict]:
    """
    Load all results for a model
    
    Returns:
        Dict mapping image_id -> {
            'medicines': Set[str],  # normalized for comparison
            'medicines_original': List[str],  # original names
            'processing_time': float,
            'success': bool
        }
    """
    model_data = {}
    
    # Find all numbered subdirectories
    for subdir in sorted(results_dir.iterdir()):
        if not subdir.is_dir() or subdir.name == "summary.json":
            continue
        
        # Skip if not a number (like summary.json parent)
        try:
            image_id = subdir.name
        except:
            continue
        
        results_file = subdir / "results.json"
        summary_file = subdir / "summary.json"
        
        if not results_file.exists() or not summary_file.exists():
            continue
        
        try:
            # Load medicines
            with open(results_file, 'r', encoding='utf-8') as f:
                results_data = json.load(f)
            
            medicines = results_data.get("medicines", [])
            # Store original medicine names
            medicines_original = [m for m in medicines if m]
            # Normalize medicine names for comparison
            medicines_set = {normalize_medicine_name(m) for m in medicines_original}
            
            # Load processing time
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
            
            processing_time = summary_data.get("processing_time")
            success = summary_data.get("success", True)
            
            model_data[image_id] = {
                'medicines': medicines_set,
                'medicines_original': medicines_original,
                'processing_time': processing_time,
                'success': success,
                'medicines_count': len(medicines_set)
            }
        except Exception as e:
            print(f"Warning: Failed to load {subdir}: {e}", file=sys.stderr)
            continue
    
    return model_data


def calculate_match_percentage(set1: Set[str], set2: Set[str]) -> float:
    """Calculate match percentage between two sets of medicine names"""
    if not set1 and not set2:
        return 100.0  # Both empty = 100% match
    if not set1 or not set2:
        return 0.0  # One empty, one not = 0% match
    
    # Calculate intersection (exact matches)
    intersection = set1 & set2
    
    # Calculate union (all unique medicines)
    union = set1 | set2
    
    # Jaccard similarity (intersection / union)
    if not union:
        return 100.0
    
    return (len(intersection) / len(union)) * 100.0


def compare_models(gen_results_dir: Path) -> Dict:
    """Compare all models in gen-results directory"""
    gen_results_dir = Path(gen_results_dir)
    
    if not gen_results_dir.exists():
        raise ValueError(f"Directory not found: {gen_results_dir}")
    
    # Load data for each model
    models_data = {}
    model_dirs = [d for d in gen_results_dir.iterdir() if d.is_dir()]
    
    if not model_dirs:
        raise ValueError(f"No model directories found in {gen_results_dir}")
    
    print(f"Found {len(model_dirs)} models: {[d.name for d in model_dirs]}")
    
    for model_dir in sorted(model_dirs):
        model_name = model_dir.name
        print(f"Loading results for {model_name}...")
        models_data[model_name] = load_model_results(model_dir)
        print(f"  Loaded {len(models_data[model_name])} images")
    
    # Get common image IDs (images processed by all models)
    all_image_ids = set()
    for model_data in models_data.values():
        all_image_ids.update(model_data.keys())
    
    # Find images present in all models
    common_images = set(all_image_ids)
    for model_data in models_data.values():
        common_images &= set(model_data.keys())
    
    print(f"\nCommon images across all models: {len(common_images)}")
    print(f"Total unique images: {len(all_image_ids)}")
    
    # Calculate statistics for each model
    model_stats = {}
    for model_name, model_data in models_data.items():
        processing_times = [
            data['processing_time'] 
            for data in model_data.values() 
            if data['processing_time'] is not None and data['success']
        ]
        
        medicine_counts = [
            data['medicines_count']
            for data in model_data.values()
            if data['success']
        ]
        
        success_count = sum(1 for data in model_data.values() if data['success'])
        total_count = len(model_data)
        
        model_stats[model_name] = {
            'avg_time': statistics.mean(processing_times) if processing_times else 0,
            'min_time': min(processing_times) if processing_times else 0,
            'max_time': max(processing_times) if processing_times else 0,
            'median_time': statistics.median(processing_times) if processing_times else 0,
            'avg_medicines': statistics.mean(medicine_counts) if medicine_counts else 0,
            'total_images': total_count,
            'successful_images': success_count,
            'success_rate': (success_count / total_count * 100) if total_count > 0 else 0
        }
    
    # Calculate pairwise comparisons
    model_names = sorted(models_data.keys())
    comparisons = {}
    
    for i, model1 in enumerate(model_names):
        for model2 in model_names[i+1:]:
            comparison_key = f"{model1} vs {model2}"
            
            # Get common images
            common = set(models_data[model1].keys()) & set(models_data[model2].keys())
            
            if not common:
                comparisons[comparison_key] = {
                    'avg_match': 0.0,
                    'common_images': 0,
                    'matches': []
                }
                continue
            
            # Calculate matches for each common image
            matches = []
            for image_id in sorted(common):
                med1 = models_data[model1][image_id]['medicines']
                med2 = models_data[model2][image_id]['medicines']
                med1_orig = models_data[model1][image_id]['medicines_original']
                med2_orig = models_data[model2][image_id]['medicines_original']
                match_pct = calculate_match_percentage(med1, med2)
                matches.append({
                    'image_id': image_id,
                    'match_pct': match_pct,
                    'med1_count': len(med1),
                    'med2_count': len(med2),
                    'med1_original': med1_orig,
                    'med2_original': med2_orig
                })
            
            avg_match = statistics.mean([m['match_pct'] for m in matches]) if matches else 0.0
            
            comparisons[comparison_key] = {
                'avg_match': avg_match,
                'common_images': len(common),
                'matches': matches
            }
    
    return {
        'models': model_stats,
        'comparisons': comparisons,
        'common_images': sorted(common_images),
        'total_images': len(all_image_ids),
        'models_data': models_data  # Store original data for detailed reporting
    }


def generate_report(comparison_data: Dict, output_file: Path):
    """Generate a human-readable comparison report"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("GEMINI MODELS COMPARISON REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        # Model Statistics
        f.write("MODEL STATISTICS\n")
        f.write("-" * 80 + "\n\n")
        
        for model_name, stats in sorted(comparison_data['models'].items()):
            f.write(f"Model: {model_name}\n")
            f.write(f"  Total Images Processed: {stats['total_images']}\n")
            f.write(f"  Successful: {stats['successful_images']} ({stats['success_rate']:.1f}%)\n")
            f.write(f"  Average Processing Time: {stats['avg_time']:.2f}s\n")
            f.write(f"  Min Time: {stats['min_time']:.2f}s\n")
            f.write(f"  Max Time: {stats['max_time']:.2f}s\n")
            f.write(f"  Median Time: {stats['median_time']:.2f}s\n")
            f.write(f"  Average Medicines per Image: {stats['avg_medicines']:.1f}\n")
            f.write("\n")
        
        # Pairwise Comparisons
        f.write("\n" + "=" * 80 + "\n")
        f.write("PAIRWISE COMPARISONS\n")
        f.write("=" * 80 + "\n\n")
        
        for comp_key, comp_data in sorted(comparison_data['comparisons'].items()):
            f.write(f"{comp_key}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Common Images: {comp_data['common_images']}\n")
            f.write(f"Average Match: {comp_data['avg_match']:.2f}%\n\n")
            
            # Show top 10 best and worst matches
            matches = sorted(comp_data['matches'], key=lambda x: x['match_pct'], reverse=True)
            
            f.write("Best Matches (Top 10):\n")
            for match in matches[:10]:
                f.write(f"  Image {match['image_id']}: {match['match_pct']:.1f}% "
                       f"(Model1: {match['med1_count']} meds, Model2: {match['med2_count']} meds)\n")
            
            f.write("\nWorst Matches (Bottom 10):\n")
            for match in matches[-10:]:
                f.write(f"  Image {match['image_id']}: {match['match_pct']:.1f}% "
                       f"(Model1: {match['med1_count']} meds, Model2: {match['med2_count']} meds)\n")
            
            f.write("\n")
        
        # Summary Table
        f.write("\n" + "=" * 80 + "\n")
        f.write("SUMMARY TABLE\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"{'Model':<20} {'Avg Time (s)':<15} {'Success Rate':<15} {'Avg Meds':<12}\n")
        f.write("-" * 80 + "\n")
        for model_name, stats in sorted(comparison_data['models'].items()):
            f.write(f"{model_name:<20} {stats['avg_time']:<15.2f} "
                   f"{stats['success_rate']:<15.1f}% {stats['avg_medicines']:<12.1f}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("COMPARISON MATRIX (Average Match %)\n")
        f.write("=" * 80 + "\n\n")
        
        model_names = sorted(comparison_data['models'].keys())
        f.write(f"{'Model':<20}")
        for model in model_names:
            f.write(f"{model:<20}")
        f.write("\n")
        f.write("-" * (20 * (len(model_names) + 1)) + "\n")
        
        for model1 in model_names:
            f.write(f"{model1:<20}")
            for model2 in model_names:
                if model1 == model2:
                    f.write(f"{'100.0%':<20}")
                else:
                    comp_key = f"{model1} vs {model2}" if model1 < model2 else f"{model2} vs {model1}"
                    if comp_key in comparison_data['comparisons']:
                        avg_match = comparison_data['comparisons'][comp_key]['avg_match']
                        f.write(f"{avg_match:.1f}%{'':<15}")
                    else:
                        f.write(f"{'N/A':<20}")
            f.write("\n")
        
        # Per-Image Detailed Comparisons
        f.write("\n" + "=" * 80 + "\n")
        f.write("PER-IMAGE DETAILED COMPARISONS\n")
        f.write("=" * 80 + "\n\n")
        
        model_names = sorted(comparison_data['models'].keys())
        models_data = comparison_data['models_data']
        
        # For each comparison pair, show detailed per-image breakdown
        for comp_key, comp_data in sorted(comparison_data['comparisons'].items()):
            model1, model2 = comp_key.split(" vs ")
            
            f.write(f"\n{comp_key}\n")
            f.write("=" * 80 + "\n\n")
            
            # Sort matches by image ID
            matches = sorted(comp_data['matches'], key=lambda x: int(x['image_id']) if x['image_id'].isdigit() else float('inf'))
            
            perfect_matches = [m for m in matches if m['match_pct'] == 100.0]
            mismatches = [m for m in matches if m['match_pct'] < 100.0]
            
            f.write(f"Perfect Matches (100%): {len(perfect_matches)} images\n")
            if perfect_matches:
                f.write("  Images: " + ", ".join([m['image_id'] for m in perfect_matches]) + "\n")
            f.write("\n")
            
            f.write(f"Mismatches: {len(mismatches)} images\n")
            f.write("-" * 80 + "\n\n")
            
            for match in mismatches:
                image_id = match['image_id']
                match_pct = match['match_pct']
                
                f.write(f"Image {image_id} - Match: {match_pct:.1f}%\n")
                f.write(f"  {model1} ({match['med1_count']} medicines):\n")
                if match['med1_original']:
                    for med in match['med1_original']:
                        f.write(f"    - {med}\n")
                else:
                    f.write(f"    (none)\n")
                
                f.write(f"  {model2} ({match['med2_count']} medicines):\n")
                if match['med2_original']:
                    for med in match['med2_original']:
                        f.write(f"    - {med}\n")
                else:
                    f.write(f"    (none)\n")
                
                # Show which medicines matched and which didn't
                med1_set = {normalize_medicine_name(m) for m in match['med1_original']}
                med2_set = {normalize_medicine_name(m) for m in match['med2_original']}
                matched = med1_set & med2_set
                only_in_model1 = med1_set - med2_set
                only_in_model2 = med2_set - med1_set
                
                if matched:
                    f.write(f"  ✓ Matched ({len(matched)}): ")
                    # Find original names for matched items
                    matched_orig = []
                    for m1 in match['med1_original']:
                        if normalize_medicine_name(m1) in matched:
                            matched_orig.append(m1)
                    f.write(", ".join(matched_orig[:3]))  # Show first 3
                    if len(matched_orig) > 3:
                        f.write(f" ... (+{len(matched_orig) - 3} more)")
                    f.write("\n")
                
                if only_in_model1:
                    f.write(f"  Only in {model1} ({len(only_in_model1)}): ")
                    only1_orig = [m for m in match['med1_original'] if normalize_medicine_name(m) in only_in_model1]
                    f.write(", ".join(only1_orig[:3]))
                    if len(only1_orig) > 3:
                        f.write(f" ... (+{len(only1_orig) - 3} more)")
                    f.write("\n")
                
                if only_in_model2:
                    f.write(f"  Only in {model2} ({len(only_in_model2)}): ")
                    only2_orig = [m for m in match['med2_original'] if normalize_medicine_name(m) in only_in_model2]
                    f.write(", ".join(only2_orig[:3]))
                    if len(only2_orig) > 3:
                        f.write(f" ... (+{len(only2_orig) - 3} more)")
                    f.write("\n")
                
                f.write("\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"Report generated from {comparison_data['total_images']} total images\n")
        f.write(f"Common images across all models: {len(comparison_data['common_images'])}\n")
        f.write("=" * 80 + "\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Compare results from different Gemini models"
    )
    parser.add_argument(
        "results_dir",
        type=Path,
        help="Path to gen-results directory"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("model_comparison_report.txt"),
        help="Output file path (default: model_comparison_report.txt)"
    )
    
    args = parser.parse_args()
    
    try:
        print(f"Loading results from: {args.results_dir}")
        comparison_data = compare_models(args.results_dir)
        
        print(f"\nGenerating report: {args.output}")
        generate_report(comparison_data, args.output)
        
        print(f"\n✓ Report saved to: {args.output}")
        print(f"\nSummary:")
        print(f"  Models compared: {len(comparison_data['models'])}")
        print(f"  Total images: {comparison_data['total_images']}")
        print(f"  Common images: {len(comparison_data['common_images'])}")
        
        # Print quick summary
        print("\nAverage Processing Times:")
        for model_name, stats in sorted(comparison_data['models'].items()):
            print(f"  {model_name}: {stats['avg_time']:.2f}s")
        
        print("\nAverage Match Percentages:")
        for comp_key, comp_data in sorted(comparison_data['comparisons'].items()):
            print(f"  {comp_key}: {comp_data['avg_match']:.2f}%")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

