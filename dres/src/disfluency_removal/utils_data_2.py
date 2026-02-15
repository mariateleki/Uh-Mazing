from pathlib import Path

def load_full_data(split_dir):
    split_dir = Path(split_dir)
    dis_dir = split_dir / "disfluent"
    fl_dir = split_dir / "fluent"
    return {
        "disfluent": [(f.name, f.read_text(encoding="utf-8").strip()) for f in sorted(dis_dir.glob("*.txt"))],
        "fluent": [(f.name, f.read_text(encoding="utf-8").strip()) for f in sorted(fl_dir.glob("*.txt"))],
    }

def load_segment_data(split_dir):
    split_dir = Path(split_dir)
    dis_dir = split_dir / "disfluent"
    fl_dir = split_dir / "fluent"
    dis_files = sorted(dis_dir.glob("*.txt"))
    fl_files = sorted(fl_dir.glob("*.txt"))
    segment_data = []
    for dis_f, fl_f in zip(dis_files, fl_files):
        assert dis_f.name == fl_f.name
        segment_data.append((
            dis_f.name.replace(".txt", ""),
            dis_f.read_text(encoding="utf-8").strip(),
            fl_f.read_text(encoding="utf-8").strip()
        ))
    return segment_data

# Load globals
full_train_data = load_full_data(Path("data/full/train"))
full_valid_data = load_full_data(Path("data/full/valid"))
full_test_data = load_full_data(Path("data/full/test"))

segment_train_data = load_segment_data(Path("data/segments/train"))
segment_valid_data = load_segment_data(Path("data/segments/valid"))
segment_test_data = load_segment_data(Path("data/segments/test"))
