#!/usr/bin/env python3
"""
Integration test for political comics discovery and analysis.
"""

import json
import logging
from pathlib import Path

from discover_political_comics import PoliticalComicsDiscoverer
from analyze_publishing_schedule import PublishingAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run integration test of discovery and analysis."""
    logger.info("Starting political comics integration test...")
    
    # Step 1: Discover political comics
    logger.info("\n=== STEP 1: Discovering Political Comics ===")
    discoverer = PoliticalComicsDiscoverer()
    comics = discoverer.fetch_comics_list()
    
    if not comics:
        logger.error("No comics discovered!")
        return 1
    
    logger.info(f"Discovered {len(comics)} political comics")
    
    # Show first 5 comics
    logger.info("\nFirst 5 comics:")
    for comic in comics[:5]:
        logger.info(f"  - {comic['name']} ({comic['slug']})")
    
    # Step 2: Analyze publishing schedules for a sample
    logger.info("\n=== STEP 2: Analyzing Publishing Schedules ===")
    analyzer = PublishingAnalyzer()
    
    # Analyze first 5 comics
    sample_comics = comics[:5]
    analyzed_comics = analyzer.analyze_multiple_comics(sample_comics)
    
    logger.info("\nPublishing Schedule Analysis:")
    for comic in analyzed_comics:
        freq = comic['publishing_frequency']
        logger.info(f"\n{comic['name']}:")
        logger.info(f"  Type: {freq['type']}")
        logger.info(f"  Days per week: {freq.get('days_per_week', 'N/A')}")
        logger.info(f"  Confidence: {freq.get('confidence', 0):.2f}")
        logger.info(f"  Recommended update: {analyzer.recommend_update_frequency(freq)}")
    
    # Step 3: Save results
    logger.info("\n=== STEP 3: Saving Results ===")
    
    # Update comics with publishing frequency from sample
    for analyzed in analyzed_comics:
        for comic in comics:
            if comic['slug'] == analyzed['slug']:
                comic['publishing_frequency'] = analyzed['publishing_frequency']
                break
    
    # Save to file
    output_path = Path('political_comics_list.json')
    discoverer.save_comics_list(comics, output_path)
    
    logger.info(f"Saved results to {output_path}")
    logger.info("\nIntegration test completed successfully!")
    
    return 0


if __name__ == "__main__":
    exit(main())