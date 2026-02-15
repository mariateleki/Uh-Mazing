# python -m disfluency_removal.utils_prompts
import json
from pathlib import Path
from icecream import ic

# load benepar parser
import benepar, spacy
nlp = spacy.load('en_core_web_md')
if spacy.__version__.startswith('2'):
        nlp.add_pipe(benepar.BeneparComponent("benepar_en3"))
else:
    nlp.add_pipe("benepar", config={"model": "benepar_en3"})

PREFIX = "Remove only the disfluencies from the following text: " 
EXAMPLES_PREFIX = "First, we provide examples of disfluent and fluent text pairs: "

def load_kshot_examples(k, use_segment):
    """
    Loads k-shot examples from a .jsonl file and caches them.
    """
    data_mode = ""
    if use_segment:
        data_mode = "segment"
    else:
        data_mode = "full"

    kshot_path = Path("data/k_shot") / f"kshot_k={k}_{data_mode}_train.jsonl"

    examples = []
    with kshot_path.open("r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            examples.append(entry)

    return examples

def format_kshot_examples(examples):
    """
    Converts list of k-shot dicts to a formatted prompt segment.
    """
    return "\n".join(
        f"Disfluent: {ex['disfluent']}\nFluent: {ex['fluent']}\n"
        for ex in examples
    )

def get_prompt(input_text, k, use_segment):
    """
    Builds a prompt using up to k examples from a pre-saved JSONL file.
    """

    if k > 0:
        examples = load_kshot_examples(k,use_segment)
        examples_text = format_kshot_examples(examples)
        prompt = f"{EXAMPLES_PREFIX}\n{examples_text}\n{PREFIX}\n{input_text}\n"
    else:
        prompt = f"{PREFIX}\n{input_text}\n"

    return prompt


P1 = "Please remove all disfluencies from the following text without making any other changes. Do not paraphrase, rephrase, or alter the wording or structure of the sentences. Only remove disfluencies such as filler words (e.g., uh, um), repetitions, false starts, and unnecessary interjections. Text: "

P2 = "You are meant to remove only the disfluencies from the following text. These disfluencies can be filler words such as uh, um, like, you know, yeah, or they can be repeated phrases or hesitant phrases. Text: "

P3 = "You are tasked with refining disfluent spoken text into clear, fluent, and well-structured written prose. Your primary objective is to remove disfluencies while preserving the original meaning, tone, and flow of the speaker’s words. The output should mirror the input text in meaning and intent, with no additions, omissions, or unnecessary rephrasing. Key Definitions: Disfluencies disrupt flow without meaning. Remove fillers (e.g., uh, um, you know, like, I mean, so, okay), repetitions, false starts, hesitations, and conversational artifacts. Editing Instructions: Parse the input to identify all disfluencies and conversational artifacts. Remove only those disfluencies; retain all original words, sentence structure, and phrasing that contribute meaning; do not paraphrase or alter phrasing unless required for grammar or clarity. Validation: Ensure the result is clear, natural, and faithful to the speaker’s intent, tone, and nuance; confirm that no essential details or ideas are added, removed, or altered. Guidelines: Preserve originality by maintaining exact wording wherever possible; avoid unnecessary rephrasing; use punctuation and formatting to guarantee logical flow and smooth readability. Apply these instructions to clean the text—removing all disfluencies and artifacts while retaining the original meaning, tone, and structure. Text: "

P4 = "Below is the syntactic parse tree of the disfluent original text, sentence-by-sentence. Use it to reconstruct a clear, fluent version in plain English, preserving meaning and tone. Text: "


def get_metaprompt(input_text, prompt_num):

    if prompt_num == 1:
        prompt = f"{P1}\n{input_text}\n"

    if prompt_num == 2:
        prompt = f"{P2}\n{input_text}\n"

    if prompt_num == 3:
        prompt = f"{P3}\n{input_text}\n"

    if prompt_num == 4:

        # build the parse tree
        input_text_parse = ""
        doc = nlp(input_text)
        for sent in list(doc.sents):
            input_text_parse += sent._.parse_string

        prompt = f"{P4}\n{input_text_parse}\n"

    return prompt

