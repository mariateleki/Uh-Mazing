# python -m disfluency_removal.utils_models
import os
import re
import random

from dotenv import load_dotenv

import torch
import numpy as np
import logging
from transformers import BitsAndBytesConfig, AutoTokenizer, AutoModelForCausalLM, set_seed, LogitsProcessorList
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from openai import OpenAI

from disfluency_removal.utils_prompts import *
from disfluency_removal.utils_decoding import AdaptiveLogitsProcessor

# Load environment variables
load_dotenv()

# Supress accelerate [INFO] logs
logging.getLogger("accelerate").setLevel(logging.WARNING)

# Check required keys exist
REQUIRED_VARS = ["OPENAI_API_KEY", "OPENAI_API_ORGANIZATION", "OPENAI_API_PROJECT", "HF_TOKEN", "GOOGLE_CLOUD_PROJECT"]
for var in REQUIRED_VARS:
    if os.getenv(var) is None:
        raise EnvironmentError(f"Missing required environment variable: {var}")

# Set up OpenAI client
openai_token = os.getenv("OPENAI_API_KEY")
openai_org = os.getenv("OPENAI_API_ORGANIZATION")
openai_project = os.getenv("OPENAI_API_PROJECT")
client = OpenAI(api_key=openai_token, organization=openai_org, project=openai_project)

# Set seed for everything
def set_all_seeds(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    set_seed(seed)  # transformers
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

def flatten_generated_text(text):
    text = text.replace("\n"," ")  # get rid of \n
    text = re.sub(r'\s+', ' ', text)  # collapse multiple spaces to one
    text = text.strip()
    return text

def run_metaprompting_openai_model(model_id, disfluent_text, seed, p_num):

    # put into prompt format
    input_text = get_metaprompt(input_text=disfluent_text, prompt_num=p_num)

    params = {
        "model": model_id,
        "messages": [{"role": "user", "content": input_text}],
        "temperature": 0.7,
        "seed": seed,
    }

    # send to OpenAI API
    response = client.chat.completions.create(**params)

    # format response
    extracted_output = response.choices[0].message.content.strip()
    extracted_output = flatten_generated_text(extracted_output)

    return extracted_output, input_text

def run_openai_model(model_id, disfluent_text, use_segment, k, seed):

    # put into prompt format
    input_text = get_prompt(input_text=disfluent_text,k=k,use_segment=use_segment)

    params = {
        "model": model_id,
        "messages": [{"role": "user", "content": input_text}],
        "temperature": 0.7,
        "seed": seed,
    }

    if model_id == "o4-mini-2025-04-16":
        params["reasoning_effort"] = "high"
        _ = params.pop("temperature")

    # send to OpenAI API
    response = client.chat.completions.create(**params)

    # format response
    extracted_output = response.choices[0].message.content.strip()
    extracted_output = flatten_generated_text(extracted_output)

    return extracted_output, input_text

def load_nonquantized_llama_model(model_id):
    tokenizer = AutoTokenizer.from_pretrained(model_id, 
                                              token=os.getenv("HF_TOKEN"))
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        token=os.getenv("HF_TOKEN"),
        torch_dtype=torch.bfloat16,
        device_map="auto")
    return tokenizer, model 

def load_quantized_llama_model(model_id):
    tokenizer = AutoTokenizer.from_pretrained(model_id, 
                                              token=os.getenv("HF_TOKEN"))
    bnb_config = BitsAndBytesConfig(load_in_4bit=True,
                                    bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        token=os.getenv("HF_TOKEN"),
        quantization_config=bnb_config,  # we run llama models in 4-bit
        device_map="auto")
    return tokenizer, model

def load_llama_model(model_id):
    
    if any(x in model_id.lower() for x in ["1b", "3b"]):
        tokenizer, model = load_nonquantized_llama_model(model_id)
    else: # quantize the bigger models like 8b, 11b, etc.
        tokenizer, model = load_quantized_llama_model(model_id)

    return tokenizer, model


def run_llama_model(tokenizer, model, use_segment, disfluent_text, k, ada):

    # set max generation length with hallucination buffer
    temp_input_text = disfluent_text
    temp_input_to_model = [{"role": "user", "content": temp_input_text}]
    temp_input_ids = tokenizer.apply_chat_template(
        temp_input_to_model, 
        add_generation_prompt=True,
        return_tensors="pt",
    )
    max_new_tokens_to_generate = int(len(list(temp_input_ids[0]))*2.5) # hallucination buffer

    # pass full input_text to tokenizer
    input_text = get_prompt(input_text=disfluent_text,k=k,use_segment=use_segment)
    input_to_model = [{"role": "user", "content": input_text}]
    input_ids = tokenizer.apply_chat_template(
        input_to_model, 
        add_generation_prompt=True,
        return_tensors="pt",
    )

    # put input_ids on device
    input_ids = input_ids.to(model.device)
        
    # generate text
    logits_processor = LogitsProcessorList([AdaptiveLogitsProcessor(ada=ada)]) if ada else None
    attention_mask = torch.ones_like(input_ids)

    # disable gradients for inference-only
    with torch.inference_mode():
        outputs = model.generate(
            input_ids,
            logits_processor=logits_processor,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,
            do_sample=True,
            max_new_tokens=max_new_tokens_to_generate,
            temperature=0.7,
            top_p=0.9,
            attention_mask=attention_mask,
            num_return_sequences=1, 
            return_dict_in_generate=True
        )
    
    decoded_output = tokenizer.decode(outputs.sequences[0], skip_special_tokens=False)
    # ic(decoded_output)

    # extract output using special tokens
    pattern = r"<\|start_header_id\|>assistant<\|end_header_id\|>\n\n(.*?)<\|eot_id\|>"
    match = re.search(pattern, decoded_output, re.DOTALL)
    if match:
        assistant_response = match.group(1).strip()
    else:
        assistant_response = ""

    # flatten output
    assistant_response = flatten_generated_text(assistant_response)

    return assistant_response, input_text


def load_phi_model(model_id):

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        torch_dtype="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    return tokenizer, model 

def run_phi_model(tokenizer, model, use_segment, disfluent_text, k):

    # calculate max length
    temp_input_text = disfluent_text
    temp_input_to_model = [{"role": "user", "content": temp_input_text}]
    temp_input_ids = tokenizer.apply_chat_template(
        temp_input_to_model, 
        add_generation_prompt=True,
        return_tensors="pt",
    )
    max_new_tokens_to_generate = int(len(list(temp_input_ids[0]))*2.5) # hallucination buffer

    # pass full input_text to tokenizer
    input_text = get_prompt(input_text=disfluent_text,k=k,use_segment=use_segment)
    input_to_model = [{"role": "user", "content": input_text}]
    input_ids = tokenizer.apply_chat_template(
        input_to_model, 
        add_generation_prompt=True,
        return_tensors="pt",
    )

    # put input_ids on device
    input_ids = input_ids.to(model.device)

    # Define generation pipeline
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
    )

    # Generation settings
    generation_args = {
        "max_new_tokens": max_new_tokens_to_generate,
        "return_full_text": False,
        "temperature": 0.7,
        "do_sample": True,
    }

    # Generate response
    output = pipe(input_text, **generation_args)
    output_text = output[0]['generated_text']

    return output_text, input_text


def load_mobilellm_model(model_id):
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True) # set true for 1.5B
    return tokenizer, model 

def run_mobilellm_model(tokenizer, model, use_segment, disfluent_text, k):

    # calculate max tokens
    temp_input_ids = tokenizer(
        disfluent_text, 
        return_tensors="pt",
    )
    temp_input_length = temp_input_ids.input_ids.shape[-1]
    max_new_tokens = int(temp_input_length * 2.5)

    # pass full input_text to tokenizer
    input_text = get_prompt(input_text=disfluent_text,k=k,use_segment=use_segment)
    input_ids = tokenizer(
        input_text, 
        return_tensors="pt",
    )

    # put input_ids on device
    input_ids = input_ids.to(model.device)

    # Define generation pipeline
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
    )

    # Generation settings
    generation_args = {
        "return_full_text": False,
        "temperature": 0.7,
        "do_sample": True,
        "max_new_tokens": max_new_tokens
    }

    # Generate response
    output = pipe(input_text, **generation_args)
    output_text = output[0]['generated_text']

    return output_text, input_text

def load_qwen_model(model_id):

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto"
    )
    return tokenizer, model


def run_qwen_model(tokenizer, model, use_segment, disfluent_text, k):

    # prepare the model input
    input_text = get_prompt(input_text=disfluent_text,k=k,use_segment=use_segment)
    messages = [
        {"role": "user", "content": input_text}
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False # Switches between thinking and non-thinking modes. Default is True.
    )
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # conduct text completion
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=32768
    )
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 

    # parsing thinking content
    try:
        # rindex finding 151668 (</think>)
        index = len(output_ids) - output_ids[::-1].index(151668)
    except ValueError:
        index = 0

    thinking_content = tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
    content = tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")

    # print("thinking content:", thinking_content)
    # print("content:", content)


    return content, input_text



###########################################################################


import torch
import re
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

def load_best_ft_model(model_id):

    _ = model_id  # don't care about this

    # Define model/tokenizer paths
    model_base = "meta-llama/Llama-3.2-3B-Instruct"
    adapter_path = "./src/disfluency_removal/fine-tune-llama/runs/run_best/final"

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    tokenizer.pad_token = tokenizer.eos_token 

    # Load 4-bit base model
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        model_base,
        quantization_config=bnb_config,
        device_map="auto"
    )

    # Load LoRA adapter
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()

    return tokenizer, model


def run_best_ft_model(tokenizer, model, use_segment, disfluent_text, k):

    # set max generation length with hallucination buffer
    temp_input_text = disfluent_text
    temp_input_to_model = [{"role": "user", "content": temp_input_text}]
    temp_input_ids = tokenizer.apply_chat_template(
        temp_input_to_model, 
        add_generation_prompt=True,
        return_tensors="pt",
    )
    max_new_tokens_to_generate = int(len(list(temp_input_ids[0]))*2.5) # hallucination buffer

    # pass full input_text to tokenizer
    input_text = get_prompt(input_text=disfluent_text,k=k,use_segment=use_segment)
    input_to_model = [{"role": "user", "content": input_text}]
    input_ids = tokenizer.apply_chat_template(
        input_to_model, 
        add_generation_prompt=True,
        return_tensors="pt",
    )

    # put input_ids on device
    input_ids = input_ids.to(model.device)
        
    # generate text
    attention_mask = torch.ones_like(input_ids)

    # disable gradients for inference-only
    with torch.inference_mode():
        outputs = model.generate(
            input_ids,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,
            do_sample=True,
            max_new_tokens=max_new_tokens_to_generate,
            temperature=0.7,
            top_p=0.9,
            attention_mask=attention_mask,
            num_return_sequences=1, 
            return_dict_in_generate=True
        )
    
    decoded_output = tokenizer.decode(outputs.sequences[0], skip_special_tokens=False)
    # ic(decoded_output)

    # extract output using special tokens
    pattern = r"<\|start_header_id\|>assistant<\|end_header_id\|>\n\n(.*?)<\|eot_id\|>"
    match = re.search(pattern, decoded_output, re.DOTALL)
    if match:
        assistant_response = match.group(1).strip()
    else:
        assistant_response = ""

    # flatten output
    assistant_response = flatten_generated_text(assistant_response)

    return assistant_response, input_text

