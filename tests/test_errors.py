from lazylake.errors import extract_error
from lazylake.providers.demo import FAKE_SPARK_LOG


def test_extracts_the_real_cause_and_hides_noise():
    lines = FAKE_SPARK_LOG.splitlines()
    result = extract_error(lines)
    text = "\n".join(result)

    assert "PATH_NOT_FOUND" in text  # the real cause is there
    assert "Traceback" in text
    assert "NativeCodeLoader" not in text  # WARN/INFO noise is removed
    assert "at org.apache.spark" not in text  # the internal Java stack is hidden
    assert len(result) < len(lines)


def test_no_error_returns_empty():
    assert extract_error(["INFO all good", "INFO done"]) == []


def test_truncates_long_output():
    lines = [f"ValueError: boom {i}" for i in range(200)]
    result = extract_error(lines, context=0, max_lines=10)
    assert len(result) == 11
    assert "more lines" in result[-1]
