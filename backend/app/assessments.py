"""Skill-request test bank: one 5-question quiz per stamp category.
Correct answers never leave the server — the API returns questions only,
grading happens here. Pass mark: 70%. Questions are deliberately
scenario-based (using AI well), not trivia about definitions."""

PASS_MARK = 70

QUIZZES: dict[str, list[dict]] = {
    "AI Skill": [
        {"id": "f1", "question": "You ask an AI a factual question and it answers confidently with a named source. What is the best next step?",
         "options": ["Accept it — confidence means accuracy", "Check that the source exists and actually says that", "Ask the same AI if it is sure", "Rephrase until the answer changes"], "correct": 1},
        {"id": "f2", "question": "Which prompt is most likely to produce a useful result?",
         "options": ["\"Write something about marketing\"", "\"Write a one-page summary\"", "\"Write a 150-word Instagram caption for a Georgian bakery launching sourdough, friendly tone, end with a question, no emojis\"", "\"Do marketing good\""], "correct": 2},
        {"id": "f3", "question": "What is a hallucination in generative AI?",
         "options": ["A system crash", "Fluent output that is factually wrong or invented", "A paid feature", "When the model refuses to answer"], "correct": 1},
        {"id": "f4", "question": "A classmate pastes a patient's personal data into a public chatbot for summarising. This is mainly a problem because…",
         "options": ["The summary will be worse", "Sensitive data may leave your control and be stored/processed by a third party", "Chatbots cannot summarise", "It uses more tokens"], "correct": 1},
        {"id": "f5", "question": "The AI's first answer to your task is mediocre. The most effective habit is to…",
         "options": ["Start a brand new account", "Accept it — first answers are the model's best", "Iterate: say what is wrong, add constraints or an example, and ask again", "Repeat the identical prompt many times"], "correct": 2},
    ],
    "AI Applied Skill": [
        {"id": "a1", "question": "You need AI to analyse a sales spreadsheet. The strongest workflow is to…",
         "options": ["Paste random rows and ask \"any insights?\"", "Describe the columns/goal, ask for a step-by-step analysis plan, then verify key figures against the raw data", "Ask for one final number and trust it", "Let the AI invent missing values"], "correct": 1},
        {"id": "a2", "question": "An AI-generated marketing text sounds great but mentions a product feature you don't sell. You should…",
         "options": ["Publish it — the AI probably knows better", "Remove/correct it and note that AI output needs domain verification before use", "Add more invented features for consistency", "Blame the tool publicly"], "correct": 1},
        {"id": "a3", "question": "For a repeatable weekly report, the best use of AI is to…",
         "options": ["Re-type the request from scratch every week", "Build a saved prompt template/workflow with fixed structure and checks, then reuse it", "Ask a different chatbot each time", "Avoid AI for anything repeated"], "correct": 1},
        {"id": "a4", "question": "AI suggests a business decision based on a trend in your data. Before acting you should…",
         "options": ["Act immediately", "Check sample size/data quality and whether correlation is being sold as causation", "Ask a second chatbot to rubber-stamp it", "Only act if the chart looks nice"], "correct": 1},
        {"id": "a5", "question": "Which is a good example of decomposing a task for AI?",
         "options": ["\"Make my whole business plan\"", "One prompt per stage: research → outline → draft → critique → final edit, reviewing each stage", "Typing the request in ALL CAPS", "Asking five chatbots and merging randomly"], "correct": 1},
    ],
    "AI Advanced Skill": [
        {"id": "v1", "question": "Your ML model's accuracy is 97% but it performs badly in production. A likely cause is…",
         "options": ["Too much training data", "Data leakage or train/test contamination inflating offline metrics", "The model is too honest", "Production users are wrong"], "correct": 1},
        {"id": "v2", "question": "In an LLM application, RAG (retrieval-augmented generation) mainly helps by…",
         "options": ["Making the model bigger", "Grounding answers in retrieved, citable documents instead of only model memory", "Removing the need for evaluation", "Translating text"], "correct": 1},
        {"id": "v3", "question": "You deploy an AI system. Which monitoring matters most after launch?",
         "options": ["Only uptime", "Input/output drift, quality sampling, error and abuse patterns, with a rollback path", "Social media likes", "Nothing — models don't change behaviour"], "correct": 1},
        {"id": "v4", "question": "A prompt change improves 3 test cases but you have no wider evaluation set. The responsible action is…",
         "options": ["Ship it immediately", "Build/run a broader regression eval before shipping — anecdotes are not evaluation", "Ask the model if the change is good", "Ship on Fridays only"], "correct": 1},
        {"id": "v5", "question": "MLOps versioning should cover…",
         "options": ["Only the model file", "Code, data, prompts/config and model — so any result can be reproduced", "Only the final presentation", "Nothing, notebooks are enough"], "correct": 1},
    ],
}


def grade(category: str, answers: dict[str, int]) -> tuple[int, bool, list[dict]]:
    quiz = QUIZZES[category]
    detail = []
    correct = 0
    for q in quiz:
        ok = answers.get(q["id"]) == q["correct"]
        correct += ok
        detail.append({"id": q["id"], "correct": ok})
    score = round(correct / len(quiz) * 100)
    return score, score >= PASS_MARK, detail
