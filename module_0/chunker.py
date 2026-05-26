def fixed_size_chunk(text: str, chunk_size: int, overlap: int):
    chunks = []
    start_index = 0
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")
    while start_index < len(text):
        chunk = text[start_index : start_index + chunk_size]
        chunks.append(chunk)
        start_index = (start_index + chunk_size) - overlap
    return chunks

def split_by_heading(text: str, separator: str):
    sections = text.split(separator)
    result = []
    for i, sec in enumerate(sections):
        if i == 0:
            result.append(sec)
        else:
            result.append(separator + sec)
    return result

if __name__ == "__main__":
    with open("../data/technical_manual.md", "r") as f:
        text = f.read()

    chunks = fixed_size_chunk(text, chunk_size=500, overlap=50)

    print(f"Total chunks: {len(chunks)}")
    print(f"Chunk lengths: {[len(c) for c in chunks]}")
    print("=" * 60)

    for i, chunk in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i} (length: {len(chunk)}) ---")
        print(chunk)
    
    # Split on major heading
    major = split_by_heading(text, "\n## ")
    
    print(f"\nSplit on '## ': {len(major)} sections")
    
    for i, sec in enumerate(major[:3]):
        print(f"\n--- Major Section {i} (length: {len(sec)}) ---")
        print(sec[:150])

    # Split on sub-headings
    minor = split_by_heading(text, "\n### ")
    
    print(f"\nSplit on '### ': {len(minor)} sections")
    
    for i, sec in enumerate(minor[:3]):
        print(f"\n--- Minor Section {i} (length: {len(sec)}) ---")
        print(sec[:150])
