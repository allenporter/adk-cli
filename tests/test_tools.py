import os
import pytest
from adk_cli.tools import ls, cat, write_file, edit_file, grep, read_many_files


@pytest.mark.asyncio
async def test_ls_and_write(tmp_path):
    os.chdir(tmp_path)

    # Test write_file
    await write_file("test.txt", "hello world")
    assert os.path.exists("test.txt")
    with open("test.txt", "r") as f:
        assert f.read() == "hello world"

    # Test ls
    os.mkdir("subdir")
    await write_file(".hidden", "hidden")

    output = await ls(".")
    assert "subdir/" in output
    assert "test.txt" in output
    assert ".hidden" not in output

    output_hidden = await ls(".", show_hidden=True)
    assert ".hidden" in output_hidden

    # Test cat
    content = await cat("test.txt")
    assert content == "hello world"


@pytest.mark.asyncio
async def test_read_many_files(tmp_path):
    os.chdir(tmp_path)
    await write_file("a.txt", "content a")
    await write_file("b.txt", "content b")

    output = await read_many_files(["a.txt", "b.txt"])
    assert "--- File: a.txt ---" in output
    assert "content a" in output
    assert "--- File: b.txt ---" in output
    assert "content b" in output


@pytest.mark.asyncio
async def test_cat_truncation(tmp_path):
    os.chdir(tmp_path)
    lines = [f"line {i}\n" for i in range(1, 1501)]
    with open("large.txt", "w") as f:
        f.writelines(lines)

    # Default cat should truncate at 1000 lines
    output = await cat("large.txt")
    assert "line 1" in output
    assert "line 1000" in output
    assert "line 1001" not in output
    assert "[Output truncated. Showing lines 1-1000" in output

    # Range-based cat
    output = await cat("large.txt", start_line=1001, end_line=1500)
    assert "line 1001" in output
    assert "line 1500" in output
    assert "line 1000" not in output
    assert "[Output truncated" not in output


@pytest.mark.asyncio
async def test_edit_file(tmp_path):
    os.chdir(tmp_path)
    await write_file("edit_test.txt", "first line\nsecond line\nthird line")

    # Successful edit
    result = await edit_file("edit_test.txt", "second line", "new second line")
    assert "Successfully edited" in result
    with open("edit_test.txt", "r") as f:
        assert f.read() == "first line\nnew second line\nthird line"

    # Failed edit (not found)
    result = await edit_file("edit_test.txt", "fourth line", "new fourth line")
    assert "Error: search_text not found" in result

    # Failed edit (ambiguous)
    await write_file("ambiguous.txt", "duplicate\nduplicate")
    result = await edit_file("ambiguous.txt", "duplicate", "new")
    assert "Error: search_text found 2 times" in result


@pytest.mark.asyncio
async def test_grep(tmp_path):
    os.chdir(tmp_path)
    await write_file("grep1.txt", "line 1\nfind me\nline 3")
    await write_file("grep2.txt", "dont find")

    # Simple grep
    output = await grep("find me", ".")
    assert "grep1.txt:2:find me" in output
    assert "grep2.txt" not in output

    # Grep with context
    output_ctx = await grep("find me", ".", context_lines=1)
    # Recursion (default) adds ./ prefix and dashes for context
    assert "grep1.txt-1-line 1" in output_ctx
    assert "grep1.txt:2:find me" in output_ctx
    assert "grep1.txt-3-line 3" in output_ctx
