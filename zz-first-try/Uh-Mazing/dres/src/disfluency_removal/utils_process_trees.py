import re
import os
import string
from icecream import ic

from disfluency_removal import tb # For parsing Penn Treebank format
from disfluency_removal.utils_dirs import * 

def get_tree_file_path(file_id, base_dir="data/treebank_3/parsed/mrg/swbd"):
    subdir = file_id[2]  # e.g., 'sw2005' → '2'
    return os.path.join(base_dir, subdir, file_id.replace('.txt','.mrg'))


# Extract terminal tokens from preterminal nodes, while skipping disfluency, speaker codes, and mumbles
def get_leaves_from_preterminals(tree):
    words = []

    # Identify and skip speaker label subtrees like (CODE (SYM SpeakerA1))
    def is_speaker_code(subtree):
        if isinstance(subtree, list) and len(subtree) >= 2 and subtree[0] == "CODE":
            for child in subtree[1:]:
                if isinstance(child, list) and len(child) == 2 and child[0] == "SYM" and child[1].startswith("Speaker"):
                    return True
        return False

    # Identify and skip unintelligible speech markers like (X (XX MUMBLEx))
    def is_mumble(subtree):
        if isinstance(subtree, list):
            if len(subtree) == 2 and subtree[1] == "MUMBLEx":
                return True
            if subtree[0] in ("XX", "X"):
                for child in subtree[1:]:
                    if isinstance(child, str) and child == "MUMBLEx":
                        return True
        return False

    # Traverse the tree recursively
    if isinstance(tree, list):
        if is_speaker_code(tree):
            words.append("["+str(tree)+"]")
        elif is_mumble(tree):
            return []  # Skip unwanted metadata or noise nodes
        # If it's a preterminal node with a real word, collect the word
        if len(tree) == 2 and isinstance(tree[1], str) and tree[0] not in ("-NONE-", "-DFL-"):
            words.append(tree[1])
        else:
            # Recursively process children
            for subtree in tree[1:]:
                words.extend(get_leaves_from_preterminals(subtree))

    return words

# Clean punctuation spacing and collapse extra whitespace
def clean_sentence(tokens):
    sentence = " ".join(tokens)

    # Remove unnecessary space before punctuation
    sentence = re.sub(r'\s+([.,!?])', r'\1', sentence)

    # Add space after punctuation if it's missing
    sentence = re.sub(r'([.,!?])(?=[^\s.,!?])', r'\1 ', sentence)

    # Replace multiple spaces with a single space
    sentence = re.sub(r'\s{2,}', ' ', sentence)

    return sentence.strip()

# Fix tokenized contractions into natural English form
def fix_contractions(sentence):
    fixes = {
        " n't": "n't", " 're": "'re", " 've": "'ve",
        " 'll": "'ll", " 'd": "'d", " 'm": "'m", " 's": "'s"
    }
    for k, v in fixes.items():
        sentence = sentence.replace(k, v)
    return sentence

# Run all postprocessing on a list of tokens
def postprocess_sentence(tokens):
    sentence = clean_sentence(tokens)
    sentence = fix_contractions(sentence)
    return sentence

def is_disfluent_node(label):
    return label in ("EDITED", "INTJ", "PRN")

def extract_tokens(tree, return_tags=False):
    # Lists to hold fluent and disfluent token outputs
    fluent_tokens = []
    disfluent_tokens = []
    token_tag_pairs = []  # Optional: (token, tag)

    # Utility to check if a label indicates a metadata node
    def is_metadata_node(label):
        return label in ("CODE", "SYM")

    # Utility to check if a token represents unintelligible speech
    def is_mumble_token(token):
        return token == "MUMBLEx"

    # Recursive helper to traverse the tree and collect tokens
    # Now also tracks the highest-level disfluent node label (EDITED, INTJ, PRN)
    def recurse(subtree, under_disfluent=False, disfluent_label=None):

        if isinstance(subtree, list):
            label = subtree[0] if subtree else ""

            # # Skip entire subtree if it is a metadata node
            # if is_metadata_node(label):
            #     fluent_tokens.append(subtree[1])
            #     disfluent_tokens.append(subtree[1])
            #     return

            # Determine if current node is disfluent and capture top-level label
            if is_disfluent_node(label) and not under_disfluent:
                under_disfluent = True
                disfluent_label = label  # store the top-most disfluent label

            # Check if this is a preterminal node (label and a word)
            if len(subtree) == 2 and isinstance(subtree[1], str):
                token = subtree[1]

                # append speaker
                if label == "SYM":
                    fluent_tokens.append(f"<{token}>")
                    disfluent_tokens.append(f"<{token}>")
                    return

                if subtree[0] not in ("-NONE-", "-DFL-") and not is_mumble_token(token):

                    # Include in fluent output only if not under disfluent context
                    if not under_disfluent:
                        fluent_tokens.append(token)

                    # Always include in disfluent output
                    if under_disfluent:
                        disfluent_tokens.append(f"_{token}_")
                    else:
                        disfluent_tokens.append(token)

                    # Append tag for disfluent output if requested
                    if return_tags:
                        tag = disfluent_label if under_disfluent else "NONE"
                        if token not in string.punctuation:
                            token_tag_pairs.append((token, tag))
            else:
                # Recurse into children with updated disfluent status and top-level label
                for child in subtree[1:]:
                    recurse(child, under_disfluent, disfluent_label)

    recurse(tree)

    if return_tags:
        return fluent_tokens, disfluent_tokens, token_tag_pairs

    return fluent_tokens, disfluent_tokens


def correct_final_punctuation(text):
    # Remove leading punctuation errors like ",." or ",,"
    text = re.sub(r'([.,!?]){2,}', lambda m: m.group(0)[-1], text)  # Reduce repeated punctuations to the last one
    text = re.sub(r'([.,!?])\s*([.,!?])', r'\2', text)              # Fix sequences like ", ." or ",." to "."

    # Remove space before punctuation
    text = re.sub(r'\s+([.,!?])', r'\1', text)

    # Replace multiple spaces with a single space
    text = re.sub(r'\s{2,}', ' ', text)

    # Remove extra spaces
    text = text.strip()

    return text

def get_text_dual(trees):
    fluent_sentences = []
    disfluent_sentences = []

    sep_counter = 1
    for i, tree in enumerate(trees):
        fluent_tokens, disfluent_tokens = extract_tokens(tree)

        fluent_sentence = postprocess_sentence(fluent_tokens).replace('\n','')
        disfluent_sentence = postprocess_sentence(disfluent_tokens).replace('\n','')

        fluent_sentences.append(fluent_sentence)
        disfluent_sentences.append(disfluent_sentence)

        # Add special token every 4 trees (after the 4th, 8th, etc.)
        # if (i + 1) % 4 == 0:
        #     sep_token = f"<SEP{sep_counter}>"
        #     fluent_sentences.append(sep_token)
        #     disfluent_sentences.append(sep_token)
        #     sep_counter += 1

    # form paragraph from sentences and perform post-processing
    fluent_text = ' '.join(fluent_sentences)
    fluent_text = correct_final_punctuation(fluent_text)

    disfluent_text = ' '.join(disfluent_sentences)
    disfluent_text = correct_final_punctuation(disfluent_text)

    return fluent_text, disfluent_text

def get_text_dual_from_file(tree_file):
    trees = tb.read_file(tree_file)
    return get_text_dual(trees)

def get_text_dual_from_string(tree_string):
    trees = tb.string_trees(tree_string)
    return get_text_dual(trees)


def parse_speaker_turn_symbol(symbol):
    """
    Parse a Speaker symbol like 'SpeakerA53' -> ('A', 53).
    Returns None if the symbol does not match this format.
    """
    m = re.match(r"^Speaker([A-Z])(\d+)$", str(symbol))
    if not m:
        return None
    speaker, turn = m.groups()
    return speaker, int(turn)


def unwrap_tree_root(tree):
    """
    Treebank reader may return wrapped trees like ['', actual_tree].
    Return the inner tree when present.
    """
    if (
        isinstance(tree, list)
        and len(tree) == 2
        and isinstance(tree[0], str)
        and tree[0] == ""
        and isinstance(tree[1], list)
    ):
        return tree[1]
    return tree


def get_speaker_turn_from_code_tree(tree):
    """
    Extract (speaker, turn) from a CODE tree:
    ['CODE', ['SYM', 'SpeakerA53'], ['.', '.']]
    Returns None if this is not a speaker CODE tree.
    """
    tree = unwrap_tree_root(tree)
    if not isinstance(tree, list) or not tree or tree[0] != "CODE":
        return None

    for child in tree[1:]:
        if isinstance(child, list) and len(child) == 2 and child[0] == "SYM":
            return parse_speaker_turn_symbol(child[1])

    return None


def normalize_tree_label(label):
    """
    Normalize PTB labels by removing functional suffixes.
    Example: 'NP-SBJ-1' -> 'NP'
    """
    if not isinstance(label, str):
        return ""
    # Preserve Penn Treebank special tags like -DFL- and -NONE-.
    if label.startswith("-"):
        return label
    return label.split("-")[0].split("=")[0]


def count_target_nodes_in_tree(tree, target_labels=("EDITED", "INTJ", "PRN")):
    """
    Count node labels in one parsed tree.
    Returns dict with keys from target_labels.
    """
    counts = {lbl: 0 for lbl in target_labels}

    def walk(node):
        node = unwrap_tree_root(node)
        if not isinstance(node, list) or not node:
            return

        label = normalize_tree_label(node[0])
        if label in counts:
            counts[label] += 1

        for child in node[1:]:
            if isinstance(child, list):
                walk(child)

    walk(tree)
    return counts


def group_trees_by_speaker_turn(trees):
    """
    Group parsed trees by (speaker, turn) based on CODE markers.
    Returns:
      {
        ('A', 1): [tree1, tree2, ...],
        ...
      }
    """
    grouped = {}
    current_key = None

    for tree in trees:
        speaker_turn = get_speaker_turn_from_code_tree(tree)
        if speaker_turn is not None:
            current_key = speaker_turn
            grouped.setdefault(current_key, [])
            continue

        if current_key is not None:
            grouped[current_key].append(tree)

    return grouped


def get_turn_disfluency_node_counts_from_trees(trees):
    """
    Compute per-turn node counts for EDITED, INTJ, PRN.
    Returns:
      {
        ('A', 1): {'EDITED': n, 'INTJ': n, 'PRN': n},
        ...
      }
    """
    grouped = group_trees_by_speaker_turn(trees)
    out = {}

    for key, turn_trees in grouped.items():
        turn_counts = {"EDITED": 0, "INTJ": 0, "PRN": 0}
        for t in turn_trees:
            c = count_target_nodes_in_tree(t, target_labels=("EDITED", "INTJ", "PRN"))
            turn_counts["EDITED"] += c["EDITED"]
            turn_counts["INTJ"] += c["INTJ"]
            turn_counts["PRN"] += c["PRN"]
        out[key] = turn_counts

    return out


def get_turn_disfluency_node_counts_from_file(tree_file):
    """
    Convenience wrapper around get_turn_disfluency_node_counts_from_trees()
    for a .mrg file path.
    """
    trees = tb.read_file(tree_file)
    return get_turn_disfluency_node_counts_from_trees(trees)


def collect_tokens_for_label_set(tree, include_labels=("EDITED", "INTJ", "PRN")):
    """
    Collect terminal tokens that appear under any node whose normalized label
    is in include_labels.
    """
    include = set(include_labels)
    tokens = []

    def walk(node, active=False):
        node = unwrap_tree_root(node)
        if not isinstance(node, list) or not node:
            return

        label = normalize_tree_label(node[0])
        is_active = active or (label in include)

        if len(node) == 2 and isinstance(node[1], str):
            token = node[1]
            # Keep lexical material only.
            if (
                is_active
                and label not in ("-NONE-", "-DFL-", "SYM")
                and token != "MUMBLEx"
            ):
                tokens.append(token)
            return

        for child in node[1:]:
            if isinstance(child, list):
                walk(child, is_active)

    walk(tree)
    return tokens


def tokens_to_sentence(tokens):
    """
    Convert token list into normalized text string.
    """
    if not tokens:
        return ""
    sent = postprocess_sentence(tokens)
    sent = correct_final_punctuation(sent)
    return sent


def get_turn_text_for_label_set_from_trees(trees, include_labels=("EDITED", "INTJ", "PRN")):
    """
    Build per-turn text that includes only tokens under include_labels.
    Returns:
      {
        ('A', 1): "text ...",
        ...
      }
    """
    grouped = group_trees_by_speaker_turn(trees)
    out = {}

    for key, turn_trees in grouped.items():
        tokens = []
        for t in turn_trees:
            tokens.extend(collect_tokens_for_label_set(t, include_labels=include_labels))
        out[key] = tokens_to_sentence(tokens)

    return out


def get_turn_text_for_label_set_from_file(tree_file, include_labels=("EDITED", "INTJ", "PRN")):
    """
    Convenience wrapper around get_turn_text_for_label_set_from_trees()
    for a .mrg file path.
    """
    trees = tb.read_file(tree_file)
    return get_turn_text_for_label_set_from_trees(trees, include_labels=include_labels)


def collect_tokens_excluding_disfluency_labels(
    tree,
    excluded_labels=("EDITED", "INTJ", "PRN")
):
    """
    Collect terminal tokens while excluding tokens inside the selected
    disfluency node labels.
    """
    excluded = set(excluded_labels)
    tokens = []

    def walk(node, blocked=False):
        node = unwrap_tree_root(node)
        if not isinstance(node, list) or not node:
            return

        label = normalize_tree_label(node[0])
        next_blocked = blocked or (label in excluded)

        if len(node) == 2 and isinstance(node[1], str):
            token = node[1]
            if (
                not next_blocked
                and label not in ("-NONE-", "-DFL-", "SYM")
                and token != "MUMBLEx"
            ):
                tokens.append(token)
            return

        for child in node[1:]:
            if isinstance(child, list):
                walk(child, next_blocked)

    walk(tree)
    return tokens


def get_turn_text_excluding_disfluency_labels_from_trees(
    trees,
    excluded_labels=("EDITED", "INTJ", "PRN")
):
    """
    Build per-turn text while removing only selected disfluency node classes.
    """
    grouped = group_trees_by_speaker_turn(trees)
    out = {}

    for key, turn_trees in grouped.items():
        tokens = []
        for t in turn_trees:
            tokens.extend(
                collect_tokens_excluding_disfluency_labels(
                    t,
                    excluded_labels=excluded_labels
                )
            )
        out[key] = tokens_to_sentence(tokens)

    return out


def get_turn_text_excluding_disfluency_labels_from_file(
    tree_file,
    excluded_labels=("EDITED", "INTJ", "PRN")
):
    """
    Convenience wrapper around get_turn_text_excluding_disfluency_labels_from_trees()
    for a .mrg file path.
    """
    trees = tb.read_file(tree_file)
    return get_turn_text_excluding_disfluency_labels_from_trees(
        trees,
        excluded_labels=excluded_labels
    )
