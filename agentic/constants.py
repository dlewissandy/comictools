import os

LANGUAGE_MODEL = "gpt-5.2"

with open(os.path.join("data","prompts","system","boilerplate.txt"), "r") as f:
    BOILERPLATE_INSTRUCTIONS = f.read()
