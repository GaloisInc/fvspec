"""Tests for baselines.prompts."""

from baselines.models import FvspecSample
from baselines.prompts import load_system_prompt, render_user_prompt


class TestSystemPrompt:
    def test_loads_nonempty(self):
        prompt = load_system_prompt()
        assert len(prompt) > 100
        assert "sorry" in prompt.lower()

    def test_mentions_lean(self):
        prompt = load_system_prompt()
        assert "Lean" in prompt


class TestUserPrompt:
    def test_renders_all_fields(self):
        sample = FvspecSample(
            sample_id="42",
            spec="theorem foo : True := sorry",
            impl="def foo := 1",
            realpbt_code="def test_foo(): assert foo() == 1",
            realpbt_summary="foo returns 1",
            num_theorems=1,
            difficulty_binary="easy",
        )
        rendered = render_user_prompt(sample)
        assert "theorem foo" in rendered
        assert "def foo" in rendered
        assert "test_foo" in rendered
        assert "foo returns 1" in rendered
        assert "1 theorem" in rendered

    def test_renders_without_summary(self):
        sample = FvspecSample(
            sample_id="1",
            spec="theorem bar : True := sorry",
            impl="def bar := 2",
            realpbt_code="def test_bar(): pass",
            realpbt_summary=None,
            num_theorems=2,
        )
        rendered = render_user_prompt(sample)
        assert "theorem bar" in rendered
        assert "Summary" not in rendered
