"""Unified model training pipeline entry point for IEEE-CIS and Sparkov datasets."""

import argparse
import sys
import time
from pathlib import Path

# Support direct execution from root or within directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_pipeline.evaluation import (
    build_comparison_dataframe,
    save_evaluation_outputs,
)
from ml_pipeline.ieee_cis_pipeline import train_ieee_pipeline
from ml_pipeline.sparkov_pipeline import train_sparkov_pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="FraudShield Standalone Model Training Pipeline (IEEE-CIS & Sparkov)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["ieee_cis", "sparkov", "all"],
        default="all",
        help="Dataset(s) to train on. 'all' trains both IEEE-CIS and Sparkov.",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["rf", "svm", "all"],
        default="all",
        help="Algorithm(s) to train: Random Forest ('rf'), Calibrated SVM ('svm'), or both ('all').",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Optional row limit for fast dry-run or memory-constrained environments (e.g. 50000).",
    )
    parser.add_argument(
        "--bootstrap-rounds",
        type=int,
        default=200,
        help="Number of bootstrap resamples with replacement to compute 95%% confidence intervals.",
    )
    parser.add_argument(
        "--smote-ratio",
        type=float,
        default=0.25,
        help="Minority oversampling ratio for SMOTE on training set only (0.25 = 1 fraud per 4 legit).",
    )
    parser.add_argument(
        "--svm-max-samples",
        type=int,
        default=50000,
        help="Maximum training rows used for SVM to ensure fast convergence without hang.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "notebooks" / "data",
        help="Directory containing ieee_cis and sparkov data subfolders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "notebooks" / "outputs",
        help="Directory to save evaluation reports and serialized model artifacts.",
    )
    parser.add_argument(
        "--no-save-models",
        action="store_true",
        help="Skip saving serialized .joblib model artifacts to disk.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    start_time = time.time()

    print("\n" + "=" * 80)
    print("  FRAUDSHIELD: STANDALONE MODEL TRAINING PIPELINE")
    print("=" * 80)
    print("  Configuration:")
    print("    - Target Dataset(s)    : %s" % args.dataset)
    print("    - Target Algorithm(s)  : %s" % args.model)
    print("    - Row Sample Size      : %s" % (str(args.sample_size) if args.sample_size else "Full Dataset"))
    print("    - Bootstrap Iterations : %d (95%% empirical CI)" % args.bootstrap_rounds)
    print("    - SMOTE Training Ratio : %.2f" % args.smote_ratio)
    print("    - SVM Max Train Samples: %d" % args.svm_max_samples)
    print("    - Data Directory       : %s" % args.data_dir)
    print("    - Output Directory     : %s" % args.output_dir)
    print("    - Save Model Artifacts : %s" % (not args.no_save_models))
    print("=" * 80)

    all_results = {}
    save_models = not args.no_save_models

    if args.dataset in ["ieee_cis", "all"]:
        ieee_results = train_ieee_pipeline(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            model_choice=args.model,
            sample_size=args.sample_size,
            n_bootstraps=args.bootstrap_rounds,
            smote_ratio=args.smote_ratio,
            svm_max_samples=args.svm_max_samples,
            save_models=save_models,
        )
        all_results.update(ieee_results)

    if args.dataset in ["sparkov", "all"]:
        sparkov_results = train_sparkov_pipeline(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            model_choice=args.model,
            sample_size=args.sample_size,
            n_bootstraps=args.bootstrap_rounds,
            smote_ratio=min(args.smote_ratio, 0.20),
            svm_max_samples=args.svm_max_samples,
            save_models=save_models,
        )
        all_results.update(sparkov_results)

    print("\n" + "=" * 80)
    print("  COMPILING FOUR-MODEL BENCHMARK & BOOTSTRAP CONFIDENCE INTERVALS")
    print("=" * 80)

    if not all_results:
        print("  [Warning] No models were trained.")
        return

    md_path = save_evaluation_outputs(
        all_results=all_results,
        output_dir=args.output_dir,
        n_bootstraps=args.bootstrap_rounds,
    )

    df_comp = build_comparison_dataframe(all_results)
    print("\n" + df_comp.to_string(index=False))

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("  TRAINING & EVALUATION BENCHMARK COMPLETE (%.1f seconds)" % elapsed)
    print("=" * 80)
    print("  Comparison Artifact Saved:")
    print("    - Markdown Spec : %s" % md_path)
    if save_models:
        print("    - Model Binaries: %s/" % (args.output_dir / "models"))
    print("\n  Architecture Summary:")
    print("    * IEEE-CIS-trained model is your PRIMARY DEPLOYED MODEL (high-dimensional real benchmark).")
    print("    * Sparkov-trained model is RETAINED FOR EXPLAINABILITY ANALYSIS (human-readable SHAP features).")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
