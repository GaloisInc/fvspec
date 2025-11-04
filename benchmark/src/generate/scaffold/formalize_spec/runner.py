"""Per-sample orchestration for spec agent."""

from __future__ import annotations

import logging
from pathlib import Path

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize_spec.agent import spec_generation_agent
from generate.scaffold.formalize_spec.models import SpecPayload, SpecResult

logger = logging.getLogger(__name__)


async def run_spec_agent(
    datapoint: Datapoint,
    impl_signatures: dict[str, str],
    variant: str,
    workspace: Path,
) -> SpecResult:
    """Run spec generation agent for a single datapoint.

    Args:
        datapoint: The test datapoint
        impl_signatures: Function signatures from Impl.lean
        variant: Spec variant (functional/mvcgen)
        workspace: Workspace path

    Returns:
        Spec generation result
    """
    # Infer function name from test name (remove test_ prefix)
    function_name = datapoint.name.replace("test_", "").replace("Test", "")

    # Create payload
    payload = SpecPayload(
        pbt_code=datapoint.code,
        pbt_name=datapoint.name,
        impl_signatures=impl_signatures,
        function_name=function_name,
        variant=variant,
    )

    # Run agent
    logger.info(f"Running spec agent for {datapoint.name}...")
    result = await spec_generation_agent(payload, workspace)

    if result.success:
        logger.info(
            f"✓ Spec agent succeeded: {result.attempts} attempts, "
            f"compiles={'✓' if result.compiles else '✗'}, "
            f"has_sorry={'✓' if result.has_sorry else '✗'}"
        )
    else:
        logger.error(f"✗ Spec agent failed: {result.error}")

    return result
