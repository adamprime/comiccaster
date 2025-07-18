#!/usr/bin/env python3
"""
Setup script for political comics in ComicCaster.
Discovers all political comics and analyzes their publishing schedules.
"""

import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import concurrent.futures

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from discover_political_comics import PoliticalComicsDiscoverer
from analyze_publishing_schedule import PublishingAnalyzer

# Set up logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
MAX_ANALYSIS_WORKERS = 4  # Limit concurrent requests to be respectful
ANALYSIS_BATCH_SIZE = 10  # Analyze comics in batches
RATE_LIMIT_DELAY = 1.0   # Seconds between batches


class PoliticalComicsSetup:
    """Main setup class for political comics."""
    
    def __init__(self):
        self.discoverer = PoliticalComicsDiscoverer()
        self.analyzer = PublishingAnalyzer()
        self.output_path = Path('political_comics_list.json')
    
    def run(self, analyze_all: bool = False, sample_size: Optional[int] = None):
        """
        Run the complete setup process.
        
        Args:
            analyze_all: If True, analyze all comics. If False, only analyze sample.
            sample_size: Number of comics to analyze if not analyzing all.
        """
        logger.info("Starting ComicCaster Political Comics Setup")
        logger.info("=" * 60)
        
        # Step 1: Discovery
        comics = self._discover_comics()
        if not comics:
            logger.error("Setup failed: No comics discovered")
            return False
        
        # Step 2: Analysis
        if analyze_all:
            logger.info(f"\nAnalyzing all {len(comics)} comics...")
            analyzed_comics = self._analyze_all_comics(comics)
        else:
            sample_size = sample_size or 5
            logger.info(f"\nAnalyzing sample of {sample_size} comics...")
            analyzed_comics = self._analyze_sample_comics(comics, sample_size)
        
        # Step 3: Save results
        self._save_results(comics, analyzed_comics)
        
        # Step 4: Summary
        self._print_summary(comics, analyzed_comics)
        
        logger.info("\nSetup completed successfully!")
        return True
    
    def _discover_comics(self) -> List[Dict]:
        """Discover all political comics."""
        logger.info("\n📋 Phase 1: Discovering Political Comics")
        logger.info("-" * 40)
        
        start_time = time.time()
        comics = self.discoverer.fetch_comics_list()
        elapsed = time.time() - start_time
        
        logger.info(f"✅ Discovered {len(comics)} political comics in {elapsed:.2f}s")
        
        # Show some examples
        if comics:
            logger.info("\nExample comics found:")
            for comic in comics[:5]:
                logger.info(f"  • {comic['name']} - {comic['url']}")
            if len(comics) > 5:
                logger.info(f"  ... and {len(comics) - 5} more")
        
        return comics
    
    def _analyze_sample_comics(self, comics: List[Dict], sample_size: int) -> List[Dict]:
        """Analyze a sample of comics."""
        sample = comics[:sample_size]
        analyzed = []
        
        for comic in sample:
            result = self._analyze_single_comic(comic)
            if result:
                analyzed.append(result)
                freq = result['publishing_frequency']
                logger.info(f"  ✓ {result['name']}: {freq['type']} "
                           f"({freq.get('days_per_week', '?')} days/week)")
        
        return analyzed
    
    def _analyze_all_comics(self, comics: List[Dict]) -> List[Dict]:
        """Analyze all comics with rate limiting and progress tracking."""
        logger.info("\n📊 Phase 2: Analyzing Publishing Schedules")
        logger.info("-" * 40)
        
        analyzed = []
        total = len(comics)
        
        # Process in batches to avoid overwhelming the server
        for i in range(0, total, ANALYSIS_BATCH_SIZE):
            batch = comics[i:i + ANALYSIS_BATCH_SIZE]
            batch_num = (i // ANALYSIS_BATCH_SIZE) + 1
            total_batches = (total + ANALYSIS_BATCH_SIZE - 1) // ANALYSIS_BATCH_SIZE
            
            logger.info(f"\nProcessing batch {batch_num}/{total_batches} "
                       f"(comics {i+1}-{min(i+len(batch), total)} of {total})")
            
            # Analyze batch with concurrent processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_ANALYSIS_WORKERS) as executor:
                future_to_comic = {}
                
                for comic in batch:
                    future = executor.submit(self._analyze_single_comic, comic)
                    future_to_comic[future] = comic
                
                for future in concurrent.futures.as_completed(future_to_comic):
                    result = future.result()
                    if result:
                        analyzed.append(result)
                        freq = result['publishing_frequency']
                        logger.info(f"  ✓ {result['name']}: {freq['type']} "
                                   f"({freq.get('days_per_week', '?')} days/week)")
            
            # Rate limiting between batches
            if i + ANALYSIS_BATCH_SIZE < total:
                logger.info(f"  ⏳ Rate limiting: waiting {RATE_LIMIT_DELAY}s...")
                time.sleep(RATE_LIMIT_DELAY)
        
        return analyzed
    
    def _analyze_single_comic(self, comic: Dict) -> Optional[Dict]:
        """Analyze a single comic with error handling."""
        try:
            logger.debug(f"Analyzing {comic['name']}...")
            dates = self.analyzer.fetch_comic_history(comic['slug'], days=30)
            
            if dates:
                frequency = self.analyzer.analyze_schedule(dates)
            else:
                frequency = {
                    'type': 'unknown',
                    'confidence': 0,
                    'reason': 'no_data_found'
                }
            
            comic_with_freq = comic.copy()
            comic_with_freq['publishing_frequency'] = frequency
            comic_with_freq['update_recommendation'] = self.analyzer.recommend_update_frequency(frequency)
            
            return comic_with_freq
            
        except Exception as e:
            logger.error(f"Error analyzing {comic['name']}: {e}")
            return None
    
    def _save_results(self, all_comics: List[Dict], analyzed_comics: List[Dict]):
        """Save results to JSON file."""
        logger.info("\n💾 Phase 3: Saving Results")
        logger.info("-" * 40)
        
        # Create a mapping of analyzed comics
        analyzed_map = {comic['slug']: comic for comic in analyzed_comics}
        
        # Update all comics with analysis results where available
        for comic in all_comics:
            if comic['slug'] in analyzed_map:
                analyzed = analyzed_map[comic['slug']]
                comic['publishing_frequency'] = analyzed.get('publishing_frequency')
                comic['update_recommendation'] = analyzed.get('update_recommendation')
        
        # Save to file
        self.discoverer.save_comics_list(all_comics, self.output_path)
        logger.info(f"✅ Saved to {self.output_path}")
    
    def _print_summary(self, all_comics: List[Dict], analyzed_comics: List[Dict]):
        """Print summary statistics."""
        logger.info("\n📈 Summary Statistics")
        logger.info("=" * 60)
        
        logger.info(f"Total political comics discovered: {len(all_comics)}")
        logger.info(f"Comics analyzed: {len(analyzed_comics)}")
        
        if analyzed_comics:
            # Frequency type breakdown
            freq_types = {}
            for comic in analyzed_comics:
                freq_type = comic['publishing_frequency']['type']
                freq_types[freq_type] = freq_types.get(freq_type, 0) + 1
            
            logger.info("\nPublishing frequency breakdown:")
            for freq_type, count in sorted(freq_types.items()):
                percentage = (count / len(analyzed_comics)) * 100
                logger.info(f"  • {freq_type}: {count} comics ({percentage:.1f}%)")
            
            # Update recommendation breakdown
            update_recs = {}
            for comic in analyzed_comics:
                rec = comic.get('update_recommendation', 'unknown')
                update_recs[rec] = update_recs.get(rec, 0) + 1
            
            logger.info("\nUpdate recommendation breakdown:")
            for rec, count in sorted(update_recs.items()):
                percentage = (count / len(analyzed_comics)) * 100
                logger.info(f"  • {rec}: {count} comics ({percentage:.1f}%)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Setup political comics for ComicCaster'
    )
    parser.add_argument(
        '--analyze-all',
        action='store_true',
        help='Analyze all comics (default: analyze sample of 5)'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=5,
        help='Number of comics to analyze if not using --analyze-all'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    setup = PoliticalComicsSetup()
    success = setup.run(
        analyze_all=args.analyze_all,
        sample_size=args.sample_size
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())