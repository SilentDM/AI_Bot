import project_utils as pu
import ai_utils, os, json
import ai_gemini as ag

ag.findmodel()
with open("models.json", "r") as f:
    data = json.load(f)
    print(data)


