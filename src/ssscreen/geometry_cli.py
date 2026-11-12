"""Standalone CLI entry for Stage 13 offline geometry evidence."""
from __future__ import annotations

from pathlib import Path
import click

from .geometry_pipeline import evaluate


@click.command('geometry-evaluate')
@click.option('--input', 'input_dir', type=click.Path(path_type=Path,exists=True,file_okay=False),required=True)
@click.option('--config','config_path',type=click.Path(path_type=Path,exists=True,dir_okay=False),required=True)
@click.option('--output','output_dir',type=click.Path(path_type=Path),required=True)
@click.option('--recommendations', 'recommendations_path', type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None,
              help='Optional Stage 12 recommendations.csv; identity-matched existing properties are included.')
@click.option('--target-wavelength-um', type=float, default=None,
              help='Target wavelength in micrometres; overrides detector_context.target_wavelength_um.')
def main(input_dir: Path, config_path: Path, output_dir: Path, recommendations_path: Path | None,
         target_wavelength_um: float | None) -> None:
    """Compute geometry and optionally import identity-matched Stage 12 evidence."""
    try:
        summary=evaluate(input_dir,config_path,output_dir,recommendations_path,
                         target_wavelength_um=target_wavelength_um)
    except (ValueError,FileNotFoundError,ImportError,OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Evaluated {summary['candidate_count']} candidates; "
               f"{summary['matching_solutions']} geometric matches; output={output_dir}")


if __name__=='__main__':main()
