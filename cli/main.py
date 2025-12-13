"""CLI tool for processing prescription images"""
import sys
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
    help=f"Number of parallel workers (default: {Config.MAX_WORKERS})"
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
def main(input_path: str, output: Optional[str], parallel: Optional[int], recursive: bool, summary: bool):
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
    
    click.echo(f"Found {len(images)} image(s) to process")
    
    # Initialize agent
    agent = PrescriptionAgent()
    
    # Process images
    max_workers = parallel or Config.MAX_WORKERS
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_image = {
            executor.submit(agent.process_image, img): img
            for img in images
        }
        
        # Process with progress bar
        with tqdm(total=len(images), desc="Processing") as pbar:
            for future in as_completed(future_to_image):
                image_path = future_to_image[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Save individual result and summary
                    image_name = image_path.name
                    OutputService.save_result(result, output_dir, image_name)
                    OutputService.save_image_summary(result, output_dir, image_name)
                    
                    if result.success:
                        if result.prescription:
                            OutputService.save_ocr_text(result.prescription)
                        pbar.set_postfix_str(f"✓ {image_path.name}")
                    else:
                        pbar.set_postfix_str(f"✗ {image_path.name}: {result.error}")
                    
                except Exception as e:
                    error_result = ProcessingResult(
                        success=False,
                        error=str(e)
                    )
                    results.append(error_result)
                    pbar.set_postfix_str(f"✗ {image_path.name}: {e}")
                
                pbar.update(1)
    
    # Save summary
    if summary:
        summary_path = OutputService.save_batch_summary(results, output_dir)
        click.echo(f"\nSummary saved to: {summary_path}")
    
    # Print statistics
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_meds = sum(
        len(r.prescription.medicines) 
        for r in results 
        if r.success and r.prescription
    )
    
    click.echo(f"\n{'='*50}")
    click.echo(f"Processing complete!")
    click.echo(f"Total images: {len(results)}")
    click.echo(f"Successful: {successful}")
    click.echo(f"Failed: {failed}")
    click.echo(f"Total medications extracted: {total_meds}")
    click.echo(f"Results saved to: {output_dir}")
    click.echo(f"{'='*50}")


if __name__ == "__main__":
    main()

