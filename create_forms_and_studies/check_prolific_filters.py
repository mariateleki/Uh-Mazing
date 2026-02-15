# python create_forms_and_studies/check_prolific_filters.py

import json
import os
import requests
from dotenv import load_dotenv

# For filters, you first call the API with this script to see the availible filters: 
# https://docs.prolific.com/api-reference/filters/get-filters
# Then read this about how to set the filters based on the results: 
# https://docs.prolific.com/api-reference/filters/filters-overview

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
load_dotenv()
API_TOKEN = os.getenv("PROLIFIC_TOKEN")

# ---------------------------------------------------------
# PRINT
# ---------------------------------------------------------
url = "https://api.prolific.com/api/v1/filters/"
# querystring = {"filter_tag":"custom-group"}
headers = {"Authorization": API_TOKEN}
response = requests.get(url, headers=headers) # , params=querystring
print(json.dumps(response.json(), indent=2, sort_keys=True))

# This was the choice list for fluent languages: 
# {
#       "choices": {
#         "0": "Rather not say",
#         "1": "Afrikaans",
#         "10": "Bulgarian",
#         "11": "Catalan",
#         "12": "Czech",
#         "13": "Chinese",
#         "14": "Croatian",
#         "15": "Danish",
#         "16": "Dari",
#         "17": "Dzongkha",
#         "18": "Dutch",
#         "19": "English",
#         "2": "Albanian",
#         "20": "Esperanto",
#         "21": "Estonian",
#         "22": "Faroese",
#         "23": "Farsi",
#         "24": "Finnish",
#         "25": "French",
#         "26": "Gaelic",
#         "27": "Galician",
#         "28": "German",
#         "29": "Greek",
#         "3": "Amharic",
#         "30": "Hebrew",
#         "31": "Hindi",
#         "32": "Hungarian",
#         "33": "Icelandic",
#         "34": "Indonesian",
#         "35": "Inuktitut",
#         "36": "Italian",
#         "37": "Japanese",
#         "38": "Khmer",
#         "39": "Korean",
#         "4": "Arabic",
#         "40": "Kurdish",
#         "41": "Laotian",
#         "42": "Latvian",
#         "43": "Lappish",
#         "44": "Lithuanian",
#         "45": "Macedonian",
#         "46": "Malay",
#         "47": "Maltese",
#         "48": "Nepali",
#         "49": "Norwegian",
#         "5": "Armenian",
#         "50": "Pashto",
#         "51": "Polish",
#         "52": "Portuguese",
#         "53": "Romanian",
#         "54": "Russian",
#         "55": "Scots",
#         "56": "Serbian",
#         "57": "Slovak",
#         "58": "Slovenian",
#         "59": "Somali",
#         "6": "Basque",
#         "60": "Spanish",
#         "61": "Swedish",
#         "62": "Swahili",
#         "63": "Tagalog-Filipino",
#         "64": "Tajik",
#         "65": "Tamil",
#         "66": "Thai",
#         "67": "Tibetan",
#         "68": "Tigrinya",
#         "69": "Tongan",
#         "7": "Bengali",
#         "70": "Turkish",
#         "71": "Turkmen",
#         "72": "Ukrainian",
#         "73": "Urdu",
#         "74": "Uzbek",
#         "75": "Welsh",
#         "76": "Vietnamese",
#         "77": "Telugu",
#         "78": "Papiamento",
#         "79": "Twi",
#         "8": "Belarusian",
#         "80": "Cantonese",
#         "81": "Mandarin",
#         "82": "Hakka",
#         "83": "Malayalam",
#         "84": "Gujarati",
#         "85": "Punjabi",
#         "86": "Other",
#         "87": "Irish",
#         "9": "Burmese"
#       },
#       "data_type": "ChoiceID",
#       "description": "Select the languages that you are fluent in.",
#       "filter_id": "fluent-languages",
#       "question": "Which of the following languages are you fluent in?",
#       "tags": [
#         "rep_sample_language",
#         "core-13",
#         "submission_demographic_export",
#         "waitlist-base-question",
#         "priority",
#         "fluent-language-maxxing"
#       ],
#       "title": "Fluent languages",
#       "type": "select"
#     },
