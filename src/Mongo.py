import os
import json
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mongodb.agent_toolkit import (
    MongoDBDatabaseToolkit,
)
from MONGODB_AGENT_SYS_PROMPT import MONGODB_AGENT_SYSTEM_PROMPT
from MogoDBDatabaseToolkitPii import MongoDBDatabasePIIToolkit
from RegexPIIMasker import FieldBasedPIIMasker

# Load environment variables from .env file
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'
# NATURAL_LANGUAGE_QUERY = 'how many people have joined the organisation and resigned at the same year'
# NATURAL_LANGUAGE_QUERY = 'Give me the list of 10  people who have resigned involuntary in the year 2022 from the west region and  return there employee code , first name , last name and email address only'
# NATURAL_LANGUAGE_QUERY = 'what is the designation of Vikram Kaushik and is he currently with the company?'
# NATURAL_LANGUAGE_QUERY = 'who replaced Vikram Kaushik ?'
# NATURAL_LANGUAGE_QUERY = 'which all departments checklist i need to follow for offboarding process ?'
NATURAL_LANGUAGE_QUERY = "what are the list of things that are needed to be done for offboarding process from IT department ?"
# NATURAL_LANGUAGE_QUERY = "are sap ids disabled for emp id 245?"
# NATURAL_LANGUAGE_QUERY = "what is the status of the Donthamsetti Venkata Subbarao on his sap id , is it active or disabled?"
# NATURAL_LANGUAGE_QUERY = "how many people are pending for offboarding from IT department ?"
# NATURAL_LANGUAGE_QUERY = "how many people are pending for offboarding from IT department , give me the id and name ?"
# NATURAL_LANGUAGE_QUERY = "how many people have amount of recovery for accessories?"
# NATURAL_LANGUAGE_QUERY = "how much is the highest amount of recovery for consumable accessories from it department?"
# NATURAL_LANGUAGE_QUERY = "how much balance leave is there for emp id 4598?"
# NATURAL_LANGUAGE_QUERY = "Can u list down total number of employees who have joined the organization in the year 2025"
# NATURAL_LANGUAGE_QUERY = "how many employees are 30+ years which are active"
# NATURAL_LANGUAGE_QUERY = "list all employees who have joined in Commercial department this year"
# NATURAL_LANGUAGE_QUERY = "how many employees left org in 2025  and share the there email ids for them "


class NaturalLanguageToMQL:
    def __init__(self):
        # self.llm = ChatOpenAI(model="gpt-5")
        # self.llm = ChatOpenAI(model="gpt-4-turbo")
        self.llm = ChatOpenAI(model="gpt-4o")
        self.system_message = MONGODB_AGENT_SYSTEM_PROMPT.format(top_k=50)
        self.pii_masker = FieldBasedPIIMasker()
        self.db_wrapper = MongoDBDatabasePIIToolkit.from_connection_string(
            MONGODB_URI,
            database=DB_NAME,
            pii_masker=self.pii_masker,
        )
        self.toolkit = MongoDBDatabaseToolkit(db=self.db_wrapper, llm=self.llm)

        self.agent = create_react_agent(
            model=self.llm,
            tools=self.toolkit.get_tools(),
            prompt=self.system_message,
            # pre_model_hook=self.pii_masking_pre_model_hook,
            # post_model_hook=self.pii_unmask_post_model_hook
        )

        self.messages = []

    def pii_masking_pre_model_hook(self, state: dict) -> dict:
        messages = state["messages"]
        new_messages = []

        for msg in messages:
            if msg.type in ["tool", "ai"]:
                content = msg.content

                # Skip empty content
                if not content or not isinstance(content, str):
                    new_messages.append(msg)
                    continue

                # Try masking only if content is valid JSON
                try:
                    original_data = json.loads(content)
                    masked_data, mapping = self.pii_masker.mask(original_data)
                    msg.content = json.dumps(masked_data, indent=2)
                    state["pii_mapping"] = mapping
                except json.JSONDecodeError:
                    # Not valid JSON, skip masking
                    # print("⚠️ Content is not valid JSON, skipping PII masking." , content)
                    pass

            new_messages.append(msg)

        print("messages after masking:" , new_messages )
        return {
            "messages": new_messages,
            "pii_mapping": state.get("pii_mapping", {})
        }



    def pii_unmask_post_model_hook(self, state: dict) -> dict:
        messages = state["messages"]
        # print("[PII Unmasking] Messages Before Unmasking:")
        # for msg in messages:
        #     print(f"- {msg.type}: {msg.content}")
        mapping = state.get("pii_mapping", {})
        unmasked_messages = []

        # return {"messages": messages}

        for msg in messages:
            if msg.type == "ai":
                text = msg.content
                for token, real in mapping.items():
                    text = text.replace(token, real)
                msg.content = text

            unmasked_messages.append(msg)

        return {"messages": unmasked_messages}

    def convert_to_mql_and_execute_query(self, query: str):
        # Optional: Mask input query if needed
        masked_query, _ = self.pii_masker.mask({"query": query})
        masked_text = masked_query["query"]

        events = self.agent.stream(
            {"messages": [("user", masked_text)]},
            stream_mode="values",
        )

        for event in events:
            self.messages.extend(event["messages"])

    def print_results(self):
        if self.messages:
            final_output = self.messages[-1].content
            # print("🔒 Masked Output:")
            # print(final_output)

            unmasked_output = self.pii_masker.unmask({"content": final_output})["content"]
            # print("\n🔓 Unmasked Output:")
            print(unmasked_output)
        else:
            print("No messages to display.")


converter = NaturalLanguageToMQL()
converter.convert_to_mql_and_execute_query(NATURAL_LANGUAGE_QUERY)
converter.print_results()


