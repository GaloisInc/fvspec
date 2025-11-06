"""Tests for Lean module merging."""

from generate.scaffold.formalize.impl.lean_merger import (
    LeanModule,
    append_to_lean_file,
    merge_lean_code_strings,
    merge_lean_modules,
    parse_lean_module,
)


class TestParseLeanModule:
    """Tests for parse_lean_module function."""

    def test_parse_simple_module(self):
        """Test parsing simple module with import and namespace."""
        code = """import Batteries

namespace Fvspec.Impl

def foo := 1

end Fvspec.Impl"""
        module = parse_lean_module(code)

        assert module.imports == ["import Batteries"]
        assert "def foo := 1" in module.namespace_content
        assert module.namespace_name == "Fvspec.Impl"

    def test_parse_multiple_imports(self):
        """Test parsing module with multiple imports."""
        code = """import Batteries
import Std

namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""
        module = parse_lean_module(code)

        assert len(module.imports) == 2
        assert "import Batteries" in module.imports
        assert "import Std" in module.imports

    def test_parse_no_imports(self):
        """Test parsing module without imports."""
        code = """namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""
        module = parse_lean_module(code)

        assert module.imports == []
        assert "def foo := 1" in module.namespace_content

    def test_parse_with_comments(self):
        """Test parsing module with comments."""
        code = """-- This is a comment
import Batteries

namespace Fvspec.Impl
-- Another comment
def foo := 1
end Fvspec.Impl"""
        module = parse_lean_module(code)

        assert module.imports == ["import Batteries"]
        assert "def foo := 1" in module.namespace_content
        assert "-- This is a comment" in module.preamble

    def test_parse_complex_namespace_content(self):
        """Test parsing module with structures and multiple definitions."""
        code = """import Batteries

namespace Fvspec.Impl

structure Point where
  x : Nat
  y : Nat

def foo := 1

def bar (p : Point) : Nat := p.x + p.y

end Fvspec.Impl"""
        module = parse_lean_module(code)

        assert "structure Point" in module.namespace_content
        assert "def foo := 1" in module.namespace_content
        assert "def bar" in module.namespace_content

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        module = parse_lean_module("")

        assert module.imports == []
        assert module.namespace_content == ""


class TestMergeLeanModules:
    """Tests for merge_lean_modules function."""

    def test_merge_two_simple_modules(self):
        """Test merging two simple modules."""
        m1 = LeanModule(
            imports=["import Batteries"],
            namespace_content="def foo := 1",
            namespace_name="Fvspec.Impl",
            preamble="",
        )
        m2 = LeanModule(
            imports=["import Batteries"],
            namespace_content="def bar := 2",
            namespace_name="Fvspec.Impl",
            preamble="",
        )

        merged = merge_lean_modules([m1, m2])

        # Check deduplicated imports
        assert merged.count("import Batteries") == 1

        # Check single namespace
        assert merged.count("namespace Fvspec.Impl") == 1
        assert merged.count("end Fvspec.Impl") == 1

        # Check both definitions present
        assert "def foo := 1" in merged
        assert "def bar := 2" in merged

    def test_merge_with_different_imports(self):
        """Test merging modules with different imports."""
        m1 = LeanModule(
            imports=["import Batteries"],
            namespace_content="def foo := 1",
            namespace_name="Fvspec.Impl",
            preamble="",
        )
        m2 = LeanModule(
            imports=["import Std"],
            namespace_content="def bar := 2",
            namespace_name="Fvspec.Impl",
            preamble="",
        )

        merged = merge_lean_modules([m1, m2])

        # Both imports should be present
        assert "import Batteries" in merged
        assert "import Std" in merged

        # Should be in order
        lines = merged.split("\n")
        batteries_idx = next(i for i, line in enumerate(lines) if "Batteries" in line)
        std_idx = next(i for i, line in enumerate(lines) if "import Std" in line)
        assert batteries_idx < std_idx

    def test_merge_empty_list(self):
        """Test merging empty list of modules."""
        merged = merge_lean_modules([])

        assert "namespace Fvspec.Impl" in merged
        assert "end Fvspec.Impl" in merged

    def test_merge_preserves_definition_order(self):
        """Test that merge preserves definition order within each module."""
        m1 = LeanModule(
            imports=[],
            namespace_content="def foo := 1\ndef bar := 2",
            namespace_name="Fvspec.Impl",
            preamble="",
        )
        m2 = LeanModule(
            imports=[],
            namespace_content="def baz := 3\ndef qux := 4",
            namespace_name="Fvspec.Impl",
            preamble="",
        )

        merged = merge_lean_modules([m1, m2])

        # Find positions
        foo_pos = merged.index("def foo")
        bar_pos = merged.index("def bar")
        baz_pos = merged.index("def baz")
        qux_pos = merged.index("def qux")

        # Check order: foo, bar from m1, then baz, qux from m2
        assert foo_pos < bar_pos < baz_pos < qux_pos


class TestMergeLeanCodeStrings:
    """Tests for merge_lean_code_strings function."""

    def test_merge_realistic_impl_modules(self):
        """Test merging realistic impl agent outputs."""
        code1 = """import Batteries

namespace Fvspec.Impl

def cosine_similarity (x : Array Float) : Float :=
  0.0

end Fvspec.Impl"""

        code2 = """import Batteries

namespace Fvspec.Impl

def dot_product (x y : Array Float) : Float :=
  0.0

end Fvspec.Impl"""

        merged = merge_lean_code_strings([code1, code2])

        # Single import
        assert merged.count("import Batteries") == 1

        # Single namespace block
        assert merged.count("namespace Fvspec.Impl") == 1
        assert merged.count("end Fvspec.Impl") == 1

        # Both functions present
        assert "def cosine_similarity" in merged
        assert "def dot_product" in merged

    def test_merge_with_structures(self):
        """Test merging modules with structure definitions."""
        code1 = """import Batteries

namespace Fvspec.Impl

structure Point where
  x : Nat
  y : Nat

def origin : Point := { x := 0, y := 0 }

end Fvspec.Impl"""

        code2 = """import Batteries

namespace Fvspec.Impl

def distance (p1 p2 : Point) : Nat :=
  0  -- Simplified

end Fvspec.Impl"""

        merged = merge_lean_code_strings([code1, code2])

        # Structure should be first
        assert "structure Point" in merged
        assert "def origin" in merged
        assert "def distance" in merged

    def test_merge_handles_empty_strings(self):
        """Test that merge handles empty strings in list."""
        code1 = """import Batteries
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""

        merged = merge_lean_code_strings([code1, "", "   "])

        assert "def foo := 1" in merged
        assert merged.count("namespace Fvspec.Impl") == 1


class TestAppendToLeanFile:
    """Tests for append_to_lean_file function."""

    def test_append_to_empty(self):
        """Test appending to empty file."""
        new_code = """import Batteries
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""

        result = append_to_lean_file("", new_code)

        assert result == new_code

    def test_append_empty_to_existing(self):
        """Test appending empty string to existing code."""
        existing = """import Batteries
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""

        result = append_to_lean_file(existing, "")

        assert result == existing

    def test_append_second_definition(self):
        """Test appending second definition to existing code."""
        existing = """import Batteries
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""

        new = """import Batteries
namespace Fvspec.Impl
def bar := 2
end Fvspec.Impl"""

        result = append_to_lean_file(existing, new)

        # Should have single namespace and deduplicated imports
        assert result.count("import Batteries") == 1
        assert result.count("namespace Fvspec.Impl") == 1
        assert result.count("end Fvspec.Impl") == 1

        # Both definitions present
        assert "def foo := 1" in result
        assert "def bar := 2" in result

    def test_append_multiple_times(self):
        """Test multiple sequential appends."""
        code1 = """import Batteries
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""

        code2 = """import Batteries
namespace Fvspec.Impl
def bar := 2
end Fvspec.Impl"""

        code3 = """import Batteries
namespace Fvspec.Impl
def baz := 3
end Fvspec.Impl"""

        # Sequential appends
        result = append_to_lean_file("", code1)
        result = append_to_lean_file(result, code2)
        result = append_to_lean_file(result, code3)

        # Should have single namespace
        assert result.count("namespace Fvspec.Impl") == 1
        assert result.count("end Fvspec.Impl") == 1

        # All definitions present
        assert "def foo := 1" in result
        assert "def bar := 2" in result
        assert "def baz := 3" in result

    def test_append_with_different_imports(self):
        """Test appending code with different imports."""
        existing = """import Batteries
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl"""

        new = """import Std
import Batteries
namespace Fvspec.Impl
def bar := 2
end Fvspec.Impl"""

        result = append_to_lean_file(existing, new)

        # Both imports present (Batteries deduplicated)
        assert "import Batteries" in result
        assert "import Std" in result
        # Batteries should appear only once
        assert result.count("import Batteries") == 1


class TestIntegration:
    """Integration tests for realistic scenarios."""

    def test_orchestration_workflow(self):
        """Test realistic orchestration workflow: FUT + dependencies."""
        # FUT implementation
        fut_code = """import Batteries

namespace Fvspec.Impl

structure Config where
  learning_rate : Float
  batch_size : Nat

def train (cfg : Config) : String :=
  "training"

end Fvspec.Impl"""

        # Dependency 1
        dep1_code = """import Batteries

namespace Fvspec.Impl

def validate_config (cfg : Config) : Bool :=
  cfg.learning_rate > 0.0

end Fvspec.Impl"""

        # Dependency 2
        dep2_code = """import Batteries
import Std

namespace Fvspec.Impl

def log_config (cfg : Config) : String :=
  "config logged"

end Fvspec.Impl"""

        # Simulate orchestration: write FUT, then append dependencies
        impl_content = fut_code
        impl_content = append_to_lean_file(impl_content, dep1_code)
        impl_content = append_to_lean_file(impl_content, dep2_code)

        # Verify merged result
        assert impl_content.count("namespace Fvspec.Impl") == 1
        assert impl_content.count("end Fvspec.Impl") == 1
        assert impl_content.count("import Batteries") == 1
        assert "import Std" in impl_content

        # All definitions present
        assert "structure Config" in impl_content
        assert "def train" in impl_content
        assert "def validate_config" in impl_content
        assert "def log_config" in impl_content

        # Config structure defined before its usages
        config_pos = impl_content.index("structure Config")
        train_pos = impl_content.index("def train")
        validate_pos = impl_content.index("def validate_config")
        assert config_pos < train_pos
        assert config_pos < validate_pos


class TestDeduplication:
    """Tests for definition deduplication during merging."""

    def test_merge_skips_duplicate_definitions(self):
        """Test that duplicate definitions are skipped during merge."""
        # First module with pow function
        module1 = """import Batteries

namespace Fvspec.Impl

structure BigInt where
  sign : Int
  digits : Array Nat

def pow (self : BigInt) (other : BigInt) : BigInt :=
  sorry

end Fvspec.Impl"""

        # Second module with duplicate pow and new helper
        module2 = """import Batteries

namespace Fvspec.Impl

structure BigInt where
  sign : Int
  digits : Array Nat

def pow (self : BigInt) (other : BigInt) : BigInt :=
  sorry

def helper (x : BigInt) : BigInt :=
  sorry

end Fvspec.Impl"""

        merged = append_to_lean_file(module1, module2)

        # Should only have one copy of each duplicate
        assert merged.count("structure BigInt") == 1
        assert merged.count("def pow") == 1

        # Should include the new definition
        assert merged.count("def helper") == 1

    def test_merge_preserves_first_definition(self):
        """Test that the first definition is kept when duplicates exist."""
        module1 = """import Batteries

namespace Fvspec.Impl

def foo := 1

end Fvspec.Impl"""

        module2 = """import Batteries

namespace Fvspec.Impl

def foo := 2

def bar := 3

end Fvspec.Impl"""

        merged = append_to_lean_file(module1, module2)

        # Should keep first definition (foo := 1)
        assert "def foo := 1" in merged
        assert "def foo := 2" not in merged

        # Should include non-duplicate
        assert "def bar := 3" in merged

    def test_merge_skips_docstrings_with_duplicates(self):
        """Test that docstrings are skipped along with duplicate definitions."""
        module1 = """import Batteries

namespace Fvspec.Impl

/-- Compute power of BigInt -/
def pow (self : BigInt) (other : BigInt) : BigInt :=
  sorry

end Fvspec.Impl"""

        module2 = """import Batteries

namespace Fvspec.Impl

/-- Compute power of BigInt -/
def pow (self : BigInt) (other : BigInt) : BigInt :=
  sorry

/-- Helper function -/
def helper (x : BigInt) : BigInt :=
  sorry

end Fvspec.Impl"""

        merged = append_to_lean_file(module1, module2)

        # Should only have one pow definition and one docstring
        assert merged.count("def pow") == 1
        assert merged.count("/-- Compute power of BigInt -/") == 1

        # Should include new function with its docstring
        assert merged.count("def helper") == 1
        assert merged.count("/-- Helper function -/") == 1

        # Verify no orphaned docstrings (should have equal counts)
        assert merged.count("/--") == merged.count("-/")
