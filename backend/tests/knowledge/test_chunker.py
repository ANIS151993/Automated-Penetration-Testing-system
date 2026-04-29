from app.knowledge.chunker import chunk_markdown


def test_chunk_markdown_aligns_to_headings() -> None:
    text = """# Reconnaissance Playbook

Plan to enumerate the engagement scope before deeper testing.

## Step 1 — Host discovery

Use nmap -sn against the engagement CIDR to enumerate live hosts.

## Step 2 — Service scan

Once live hosts are known, run service scans on common ports.
"""
    chunks = chunk_markdown(text, max_chars=500, min_chars=50)
    assert len(chunks) >= 1
    titles = [chunk.title for chunk in chunks]
    assert "Reconnaissance Playbook" in titles[0] or "Step" in titles[0]
    joined = "\n".join(chunk.content for chunk in chunks)
    assert "nmap" in joined
    assert "service scans" in joined


def test_chunk_markdown_splits_long_section() -> None:
    body = "\n\n".join(["paragraph " + str(i) * 80 for i in range(10)])
    text = f"# Long Section\n\n{body}"
    chunks = chunk_markdown(text, max_chars=400, min_chars=50)
    assert len(chunks) > 1
    assert all(len(chunk.content) <= 500 for chunk in chunks)
    assert all(chunk.title == "Long Section" for chunk in chunks)


def test_chunk_indices_are_sequential() -> None:
    text = "# A\n\nfirst body.\n\n## B\n\nsecond body."
    chunks = chunk_markdown(text, max_chars=20, min_chars=5)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
