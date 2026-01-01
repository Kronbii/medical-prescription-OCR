"""CLI tool for processing prescription images"""
import sys
import time
from pathlib import Path
from typing import Optional
import click
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from app.core.agent import PrescriptionAgent
from app.core.config import Config
from app.services.image_processor import ImageProcessor
from app.services.output_service import OutputService
from app.types.prescription import ProcessingResult


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output directory for results (default: ./results)"
)
@click.option(
    "--parallel",
    "-p",
    type=int,
    default=None,
    help="Number of parallel workers (default: from config)"
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="Process directories recursively"
)
@click.option(
    "--summary",
    "-s",
    is_flag=True,
    default=True,
    help="Generate summary file"
)
@click.option(
    "--delay",
    "-d",
    type=float,
    default=None,
    help="Delay in seconds between API calls (processes sequentially when set)"
)
def main(input_path: str, output: Optional[str], parallel: Optional[int], recursive: bool, summary: bool, delay: Optional[float]):
    """
    Process prescription images from a file or directory.
    
    INPUT_PATH can be a single image file or a directory containing images.
    """
    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    # Setup paths
    Config._ensure_initialized()  # Ensure config is loaded
    input_path_obj = Path(input_path)
    output_dir = Path(output) if output else Config.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find images
    if input_path_obj.is_file():
        images = [input_path_obj] if ImageProcessor.is_image_file(input_path_obj) else []
    else:
        images = ImageProcessor.find_images(input_path_obj, recursive=recursive)
    
    if not images:
        click.echo(f"No valid images found in: {input_path}", err=True)
        sys.exit(1)
    
    click.echo("Processing prescription images...")
    click.echo(f"Found {len(images)} image(s) to process")
    
    # Initialize agent
    agent = PrescriptionAgent()
    
    results = []
    image_results = []  # Store results with image paths for ordered output
    
    # If delay is specified, process sequentially with delay
    if delay is not None and delay > 0:
        click.echo(f"Processing sequentially with {delay}s delay between API calls...")
        click.echo()  # Empty line before progress bar
        
        with tqdm(total=len(images), desc="Processing", bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
            for idx, image_path in enumerate(images):
                # Add delay before processing (except for first image)
                if idx > 0:
                    time.sleep(delay)
                
                try:
                    result = agent.process_image(image_path)
                    results.append(result)
                    image_results.append((image_path, result))
                    
                    # Save individual result and summary
                    image_name = image_path.name
                    OutputService.save_result(result, output_dir, image_name)
                    OutputService.save_image_summary(result, output_dir, image_name)
                    
                    if result.success:
                        if result.prescription:
                            OutputService.save_ocr_text(result.prescription)
                
                except Exception as e:
                    error_result = ProcessingResult(
                        success=False,
                        error=str(e)
                    )
                    results.append(error_result)
                    image_results.append((image_path, error_result))
                
                pbar.update(1)
    else:
        # Process in parallel (original behavior)
        Config._ensure_initialized()  # Ensure config is loaded
        max_workers = parallel or Config.MAX_WORKERS
        click.echo(f"Processing with {max_workers} parallel workers...")
        click.echo()  # Empty line before progress bar
        
        # Create a list to store results in order
        result_dict = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_image = {
                executor.submit(agent.process_image, img): img
                for img in images
            }
            
            # Process with progress bar
            with tqdm(total=len(images), desc="Processing", bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                for future in as_completed(future_to_image):
                    image_path = future_to_image[future]
                    try:
                        result = future.result()
                        results.append(result)
                        result_dict[image_path] = result
                        
                        # Save individual result and summary
                        image_name = image_path.name
                        OutputService.save_result(result, output_dir, image_name)
                        OutputService.save_image_summary(result, output_dir, image_name)
                        
                        if result.success:
                            if result.prescription:
                                OutputService.save_ocr_text(result.prescription)
                        
                    except Exception as e:
                        error_result = ProcessingResult(
                            success=False,
                            error=str(e)
                        )
                        results.append(error_result)
                        result_dict[image_path] = error_result
                    
                    pbar.update(1)
        
        # Build ordered results list
        image_results = [(img, result_dict[img]) for img in images]
    
    # Save summary
    if summary:
        summary_path = OutputService.save_batch_summary(results, output_dir)
    
    # Print results for each image
    click.echo()  # Empty line after progress bar
    for idx, (image_path, result) in enumerate(image_results, 1):
        image_name = str(image_path) if isinstance(image_path, Path) else image_path
        time_str = f"{result.processing_time:.2f}s" if result.processing_time else "N/A"
        
        if result.success:
            med_count = len(result.prescription.medicines) if result.prescription else 0
            click.echo(f"[{idx}/{len(images)}] {image_name} ... ✓ Done ({time_str})")
        else:
            # Truncate long error messages
            error_msg = result.error[:60] + "..." if result.error and len(result.error) > 60 else (result.error or "Unknown error")
            click.echo(f"[{idx}/{len(images)}] {image_name} ... ✗ Failed: {error_msg} ({time_str})")
    
    # Print statistics
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_meds = sum(
        len(r.prescription.medicines) 
        for r in results 
        if r.success and r.prescription
    )
    
    click.echo()
    click.echo(f"{'='*50}")
    click.echo(f"Processing complete!")
    click.echo(f"Total images: {len(results)}")
    click.echo(f"Successful: {successful}")
    click.echo(f"Failed: {failed}")
    click.echo(f"Total medications extracted: {total_meds}")
    click.echo(f"Results saved to: {output_dir}")
    click.echo(f"{'='*50}")


if __name__ == "__main__":
    main()

