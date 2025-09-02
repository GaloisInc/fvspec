import tempfile
import re
from typing import Callable, Awaitable
from inspect_ai.tool import tool, ToolError
from benchmark.scaffold.tools import utilio

LEAN_EXE = "lean"


@tool
def lean_compile() -> Callable[[str], Awaitable[utilio.SubprocessResult]]:
    async def execute(code: str) -> utilio.SubprocessResult:
        """
        Typecheck Lean code.

        Args:
            code: The Lean code to typecheck

        Returns:
            A tuple of stdout, stderr and exitcode.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lean") as tmp:
            tmp.write(code)
            tmp.flush()
            stdout, stderr, exitcode = utilio.run_cmd([LEAN_EXE, tmp.name])
        if exitcode != 0:
            raise ToolError(stderr)
        return stdout, stderr, exitcode

    return execute


@tool
def write_code_to_disk() -> Callable[[str, str], Awaitable[str]]:
    """
    A tool that extracts <code>...</code> from 'text' and writes it
    into artifacts/spec/<sample_id>/Spec.lean.
    """

    async def execute(sample_id: str, text: str) -> str:
        """
        Write the <code>...</code> snippet from text into
        artifacts/spec/<sample_id>/Spec.lean.

        Args:
            sample_id: Identifier for the current sample.
            text: The text possibly containing <code>...</code>.
        Returns:
            A message describing whether the write succeeded.
        """

        # Look for <code>...</code>
        pattern = r"(?s)<code>(.*?)</code>"
        mtch = re.search(pattern, text)
        if not mtch:
            return utilio.no_code_block_found(sample_id, text)
        code_snippet = mtch.group(1)

        spec_file = utilio.get_output_filepath(sample_id)
        return utilio.writeit(spec_file, code_snippet)

    return execute
