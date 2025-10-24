from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings , ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv

app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))


template = """Answer the question based only on the following context:
{context}

Question: {question}
"""


prompt = ChatPromptTemplate.from_template(template)

final_prompt = prompt.invoke({"context": "Chickens are a type of bird.", "question": "What are chickens?"})

print(final_prompt)

# model = ChatOpenAI(model="gpt-3.5-turbo")

# parser = StrOutputParser()

# chain = prompt | model | parser

# print(chain.invoke({"topic": "chickens"}))

