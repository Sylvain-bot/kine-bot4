import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_response(context, question):
    prompt = (
        f"Voici les informations du patient :\n{context}\n"
        f"Question du patient : {question}\n"
        f"Réponds de façon claire, professionnelle et adaptée à un patient en rééducation."
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )

    return response.choices[0].message.content.strip()