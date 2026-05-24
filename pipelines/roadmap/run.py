import json, sys
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger("roadmap")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipelines.transformation.staging import run as run_staging
from pipelines.roadmap.phase0_raw import run as phase0
from pipelines.roadmap.phase1_profiling import run as phase1
from pipelines.roadmap.phase2_normalization import run as phase2
from pipelines.roadmap.phase3_extraction import run as phase3
from pipelines.roadmap.phase4_core_variant import run as phase4
from pipelines.roadmap.phase5_validation import run as phase5
from pipelines.roadmap.phase6_splink import run as phase6
from pipelines.roadmap.phase7_unified import run as phase7
from pipelines.roadmap.phase8_consumption import run as phase8


def run(max_phases: int = 8):
    logger.info("=" * 60)
    logger.info("ROADMAP PIPELINE — Full Run")
    logger.info("=" * 60)

    # Phase 0: Raw data
    if max_phases >= 0:
        phase0()

    # Load staging for downstream phases
    staging = run_staging()

    # Phase 1
    if max_phases >= 1:
        phase1()

    # Phase 2
    normalized = phase2(staging) if max_phases >= 2 else {}

    # Phase 3
    parsed = phase3(normalized) if max_phases >= 3 else {}

    # Phase 4
    core_variant = phase4(parsed) if max_phases >= 4 else {}

    # Phase 5
    if max_phases >= 5:
        phase5(core_variant)

    # Phase 6
    if max_phases >= 6:
        phase6(core_variant)

    # Phase 7
    from pipelines.roadmap.phase3_extraction import run as phase3_import
    nutrition = {}
    unified = phase7(core_variant, parsed, nutrition) if max_phases >= 7 else {}

    # Phase 8
    if max_phases >= 8:
        phase8(unified)

    # Final logs
    logger.info("=" * 60)
    logger.info("ALL PHASES COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "8"
    max_p = int(arg)
    run(max_phases=max_p)
