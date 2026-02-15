# python -m disfluency_removal.data_1_generate_flat
# We follow split in section 4: https://aclanthology.org/2020.acl-main.346.pdf
# Output is in /data/{train,valid,test}, contains <SEPn>, in .txt format.

import re
from pathlib import Path

from disfluency_removal.utils_dirs import *
from disfluency_removal.utils_process_trees import *

# Define data locations
OUTPUT_DIR = Path(DATA_DIR / "treebank_3_flat")

# Patterns from Charniak & Johnson (2001)
train_re = re.compile(r"sw[23]\d+\.mrg$")
dev_re   = re.compile(r"sw4[5-9]\d+\.mrg$")
test_re  = re.compile(r"sw4[0-1]\d+\.mrg$")

# Recursively find all .mrg files
for mrg_file in TREEBANK_MRG_DIR.rglob("*.mrg"):
    filename = mrg_file.name

    # Determine split
    if train_re.match(filename):
        split = "train"
    elif dev_re.match(filename):
        split = "dev"
    elif test_re.match(filename):
        split = "test"
    else:
        continue  # Skip unknown pattern

    # Get fluent/disfluent output
    fluent, disfluent = get_text_dual_from_file(mrg_file)

    # Save to processed dirs
    (OUTPUT_DIR / split / "fluent").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / split / "disfluent").mkdir(parents=True, exist_ok=True)

    out_fluent = OUTPUT_DIR / split / "fluent" / (filename.replace(".mrg", ".txt"))
    out_disfluent = OUTPUT_DIR / split / "disfluent" / (filename.replace(".mrg", ".txt"))

    out_fluent.write_text(fluent, encoding="utf-8")
    out_disfluent.write_text(disfluent, encoding="utf-8")

    print(f"✔ Processed {filename} → {split}")
