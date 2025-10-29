"""AST-based extraction of unit tests from Python PBT code.

This module uses Python's ast module to perform static analysis and extract
concrete test cases through constant propagation and symbolic execution.
"""

import ast
import warnings
from typing import Any
from generate.scaffold.units.structures import TestCase


class ASTExtractor(ast.NodeVisitor):
    """Extract unit tests from Python code via AST analysis.

    Performs constant propagation to track variable assignments and extract
    concrete test cases from assertions.

    Example:
        >>> code = '''
        ... X = [1, 2, 3]
        ... result = double(X)
        ... assert result == [2, 4, 6]
        ... '''
        >>> extractor = ASTExtractor()
        >>> tests = extractor.extract_tests(code, func_name="double")
        >>> len(tests)
        1
        >>> tests[0].inputs
        ['[1, 2, 3]']
    """

    def __init__(self) -> None:
        """Initialize the extractor with empty symbol table."""
        self.symbol_table: dict[str, Any] = {}
        self.tests: list[TestCase] = []
        self.func_name: str = ""
        self.test_counter: int = 0

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track variable assignments for constant propagation.

        Handles:
        - Simple literals: X = [1, 2, 3]
        - Numeric values: x = 5
        - Strings: s = "hello"

        Does not handle:
        - Function calls: X = generate_data()
        - Complex expressions: X = Y + Z (unless Y, Z are known)
        """
        # Only track simple single-target assignments
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            value = self._try_eval_node(node.value)
            if value is not None:
                self.symbol_table[var_name] = value
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Extract test cases from assert statements.

        Handles:
        - assert f(X) == Y
        - assert result == expected
        - assert f(1, 2) == 3

        Substitutes known values from symbol table.
        """
        # Check if this is a comparison assertion
        if isinstance(node.test, ast.Compare) and len(node.test.ops) == 1:
            # Handle: assert left == right
            if isinstance(node.test.ops[0], ast.Eq):
                left = node.test.left
                right = node.test.comparators[0]

                # Try to extract test from this comparison
                test_case = self._extract_test_from_comparison(left, right)
                if test_case:
                    self.tests.append(test_case)

        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Unroll simple for loops with concrete iterables.

        Handles:
        - for i in [0, 1, 2]: assert f(i) == i * 2
        - for x in ["a", "b"]: assert len(x) == 1

        Does not handle:
        - for i in range(n): ... (where n is unknown)
        - Complex loop bodies
        """
        # Check if we can evaluate the iterable
        iterable = self._try_eval_node(node.iter)
        if iterable is not None and isinstance(iterable, list):
            # Save original symbol table
            saved_symbols = self.symbol_table.copy()

            # Unroll loop
            if isinstance(node.target, ast.Name):
                loop_var = node.target.id
                for value in iterable:
                    # Set loop variable
                    self.symbol_table[loop_var] = value
                    # Visit loop body
                    for stmt in node.body:
                        self.visit(stmt)

            # Restore symbol table
            self.symbol_table = saved_symbols
        else:
            # Can't unroll, just visit normally
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle pytest.mark.parametrize decorators.

        Handles:
        - @pytest.mark.parametrize("x,y,expected", [(1,2,3), (5,10,15)])
        - @pytest.mark.parametrize("input,output", [[1,2], [3,4]])

        For each parameter combination, visits the function body with those
        values in the symbol table.
        """
        # Check for parametrize decorators
        parametrize_data = self._extract_parametrize(node)

        if parametrize_data:
            # Unroll parametrized tests
            param_names, param_values = parametrize_data

            # Save original symbol table
            saved_symbols = self.symbol_table.copy()

            # For each combination of parameter values
            for value_tuple in param_values:
                # Set parameters in symbol table
                for param_name, param_value in zip(param_names, value_tuple):
                    self.symbol_table[param_name] = param_value

                # Visit function body
                for stmt in node.body:
                    self.visit(stmt)

            # Restore symbol table
            self.symbol_table = saved_symbols
        else:
            # No parametrize, visit normally
            self.generic_visit(node)

    def _extract_parametrize(
        self, node: ast.FunctionDef
    ) -> tuple[list[str], list[tuple]] | None:
        """Extract pytest.mark.parametrize data from function decorators.

        Args:
            node: FunctionDef node to check

        Returns:
            Tuple of (parameter_names, parameter_values), or None if no parametrize

        Example:
            @pytest.mark.parametrize("x,y,expected", [(1,2,3), (5,10,15)])
            Returns: (["x", "y", "expected"], [(1, 2, 3), (5, 10, 15)])
        """
        for decorator in node.decorator_list:
            # Check for @pytest.mark.parametrize(...) or @parametrize(...)
            if isinstance(decorator, ast.Call):
                # Get the decorator name
                decorator_name = None
                if isinstance(decorator.func, ast.Attribute):
                    # pytest.mark.parametrize
                    if (
                        isinstance(decorator.func.value, ast.Attribute)
                        and isinstance(decorator.func.value.value, ast.Name)
                        and decorator.func.value.value.id == "pytest"
                        and decorator.func.value.attr == "mark"
                        and decorator.func.attr == "parametrize"
                    ):
                        decorator_name = "parametrize"
                elif isinstance(decorator.func, ast.Name):
                    # @parametrize (direct import)
                    if decorator.func.id == "parametrize":
                        decorator_name = "parametrize"

                if decorator_name == "parametrize" and len(decorator.args) >= 2:
                    # Extract parameter names (first arg)
                    param_names_arg = decorator.args[0]
                    param_names = None
                    if isinstance(param_names_arg, ast.Constant) and isinstance(
                        param_names_arg.value, str
                    ):
                        # Parse "x,y,expected" -> ["x", "y", "expected"]
                        param_names = [
                            name.strip() for name in param_names_arg.value.split(",")
                        ]

                    # Extract parameter values (second arg)
                    param_values_arg = decorator.args[1]
                    param_values = self._try_eval_node(param_values_arg)

                    if param_names and param_values and isinstance(param_values, list):
                        # Normalize parameter values to ensure consistent tuple format
                        # This handles the various ways pytest.mark.parametrize can
                        # specify values:
                        #   - Multiple params: @parametrize("a,b", [(1,2), (3,4)])
                        #     -> already tuples
                        #   - Single param with tuple values: @parametrize("a", [(1,), (2,)])
                        #     -> already tuples
                        #   - Single param with list of values: @parametrize("a", [1, 2, 3])
                        #     -> need (1,), (2,), (3,)
                        #   - Mixed formats that need consistent tuple wrapping
                        normalized_values = []
                        for val in param_values:
                            if isinstance(val, tuple):
                                # Already a tuple - use as-is (handles multi-param cases
                                # like (1,2,3))
                                normalized_values.append(val)
                            elif isinstance(val, list):
                                # List value needs different handling based on
                                # parameter count
                                if len(param_names) == 1:
                                    # Single parameter case: each list element becomes a
                                    # single-item tuple
                                    # Example: @parametrize("x", [1, 2, 3])
                                    # -> [(1,), (2,), (3,)]
                                    # This ensures each test gets one parameter value,
                                    # not a list
                                    normalized_values.append((val,))
                                else:
                                    # Multiple parameters: convert list to tuple directly
                                    # Example: @parametrize("x,y", [[1,2], [3,4]])
                                    # -> [(1,2), (3,4)]
                                    normalized_values.append(tuple(val))
                            else:
                                # Single scalar value: wrap in tuple for consistency
                                # Example: @parametrize("x", [1, 2]) where val=1 -> (1,)
                                # This ensures uniform tuple format regardless of
                                # input type
                                normalized_values.append((val,))

                        return (param_names, normalized_values)

        return None

    def _extract_test_from_comparison(
        self, left: ast.expr, right: ast.expr
    ) -> TestCase | None:
        """Extract a test case from a comparison expression.

        Args:
            left: Left side of comparison
            right: Right side of comparison

        Returns:
            TestCase if extraction succeeded, None otherwise
        """
        # Try to identify which side is the function call
        func_call = None
        expected = None

        if isinstance(left, ast.Call) and isinstance(left.func, ast.Name):
            func_call = left
            expected = self._try_eval_node(right)
        elif isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
            func_call = right
            expected = self._try_eval_node(left)
        elif isinstance(left, ast.Name) and left.id in self.symbol_table:
            # Handle: result = f(X); assert result == Y
            # TODO: Track function calls in assignments
            return None

        if func_call is None or expected is None:
            return None

        # Extract function name
        if not isinstance(func_call.func, ast.Name):
            return None
        func_name = func_call.func.id

        # Only extract tests for the target function
        if self.func_name and func_name != self.func_name:
            return None

        # Extract arguments
        inputs = []
        for arg in func_call.args:
            arg_value = self._try_eval_node(arg)
            if arg_value is None:
                # Can't evaluate this argument
                return None
            inputs.append(self._python_to_lean(arg_value))

        # Check if this is a float test
        is_float = self._is_float_value(expected)

        self.test_counter += 1

        return TestCase(
            func_name=func_name,
            inputs=inputs,
            expected_output=self._python_to_lean(expected),
            is_float=is_float,
            test_name=f"{func_name} test {self.test_counter}",
            extraction_method="ast",
        )

    def _try_eval_node(self, node: ast.expr) -> Any | None:
        """Try to evaluate an AST node to a concrete value.

        Args:
            node: AST node to evaluate

        Returns:
            Evaluated value, or None if evaluation fails
        """
        # Handle constants (literals)
        if isinstance(node, ast.Constant):
            return node.value

        # Handle names (variables)
        if isinstance(node, ast.Name):
            return self.symbol_table.get(node.id)

        # Handle lists
        if isinstance(node, ast.List):
            elements = []
            for elt in node.elts:
                val = self._try_eval_node(elt)
                if val is None:
                    return None
                elements.append(val)
            return elements

        # Handle tuples
        if isinstance(node, ast.Tuple):
            elements = []
            for elt in node.elts:
                val = self._try_eval_node(elt)
                if val is None:
                    return None
                elements.append(val)
            return tuple(elements)

        # Handle simple binary operations
        if isinstance(node, ast.BinOp):
            left = self._try_eval_node(node.left)
            right = self._try_eval_node(node.right)
            if left is not None and right is not None:
                try:
                    if isinstance(node.op, ast.Add):
                        return left + right
                    elif isinstance(node.op, ast.Sub):
                        return left - right
                    elif isinstance(node.op, ast.Mult):
                        return left * right
                except (TypeError, ValueError):
                    # Ignore type/value errors: operation not evaluable with current values
                    pass

        # Handle subscript operations (e.g., [1, 2, 3][i])
        if isinstance(node, ast.Subscript):
            value = self._try_eval_node(node.value)
            index = self._try_eval_node(node.slice)
            if value is not None and index is not None:
                try:
                    return value[index]
                except (TypeError, IndexError, KeyError):
                    pass

        # Can't evaluate
        return None

    def _is_float_value(self, value: Any) -> bool:
        """Check if a value should be treated as a float test.

        Args:
            value: Python value to check

        Returns:
            True if this is a float value requiring tolerance checking
        """
        if isinstance(value, float):
            return True
        if isinstance(value, list):
            return any(isinstance(x, float) for x in value)
        if isinstance(value, tuple):
            return any(isinstance(x, float) for x in value)
        return False

    def _python_to_lean(self, value: Any) -> str:
        """Convert a Python value to Lean syntax.

        Args:
            value: Python value (int, float, str, list, tuple)

        Returns:
            String representation in Lean syntax

        Examples:
            >>> extractor = ASTExtractor()
            >>> extractor._python_to_lean([1, 2, 3])
            '[1, 2, 3]'
            >>> extractor._python_to_lean("hello")
            '"hello"'
            >>> extractor._python_to_lean((1, 2))
            '(1, 2)'
        """
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, float):
            return str(value)
        elif isinstance(value, str):
            # Escape quotes
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        elif isinstance(value, list):
            elements = [self._python_to_lean(x) for x in value]
            return f"[{', '.join(elements)}]"
        elif isinstance(value, tuple):
            elements = [self._python_to_lean(x) for x in value]
            return f"({', '.join(elements)})"
        else:
            # Fallback to string representation
            return str(value)

    def extract_tests(self, pbt_code: str, func_name: str = "") -> list[TestCase]:
        """Extract unit tests from PBT code.

        Args:
            pbt_code: Python source code containing the PBT
            func_name: Optional function name to filter tests for

        Returns:
            List of extracted test cases

        Example:
            >>> code = '''
            ... X = [1, 2, 3]
            ... assert double(X) == [2, 4, 6]
            ... assert double([]) == []
            ... '''
            >>> extractor = ASTExtractor()
            >>> tests = extractor.extract_tests(code, func_name="double")
            >>> len(tests)
            2
        """
        self.func_name = func_name
        self.tests = []
        self.test_counter = 0
        self.symbol_table = {}

        try:
            # Suppress SyntaxWarning for invalid escape sequences in scraped code
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=SyntaxWarning)
                tree = ast.parse(pbt_code)
            self.visit(tree)
        except SyntaxError:
            # Can't parse the code, return empty list
            pass

        return self.tests
