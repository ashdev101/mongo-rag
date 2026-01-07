import os
import json
from langchain_openai import ChatOpenAI
from feedback.oneshot import oneshot_example
from langgraph.prebuilt import create_react_agent
from langchain_mongodb.agent_toolkit import (
    MongoDBDatabaseToolkit,
)
from MONGODB_AGENT_SYS_PROMPT import MONGODB_AGENT_SYSTEM_PROMPT
from MongoDbDatabseLocalContextAndPiiMasking import MongoDBDatabasePIIToolkit
from RegexPIIMasker import FieldBasedPIIMasker
from aggregation.AggregationRBAC import AggregationRBAC
from pathlib import Path
from data_context import DataContext
from databse_dsitcint_values import CANONICAL_GRADES, CANONICAL_DEPARTMENTS, CANONICAL_REGIONS
from llm.LLMFactory import LLMFactory
from memory.memorymanager import get_chat_history

# Load environment variables from .env file
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr-cleaned'
NATURAL_LANGUAGE_QUERY = 'how many people have joined the organisation and resigned at the same year'
# NATURAL_LANGUAGE_QUERY = 'Give me the list of 10  people who have resigned involuntary in the year 2022 from the west region and  return there employee code , first name , last name and email address only'
# NATURAL_LANGUAGE_QUERY = 'what is the designation of Vikram Kaushik and is he currently with the company?'
# NATURAL_LANGUAGE_QUERY = 'who replaced Vikram Kaushik ?'
# NATURAL_LANGUAGE_QUERY = 'which all departments checklist i need to follow for offboarding process ?'
# NATURAL_LANGUAGE_QUERY = "what are the list of things that are needed to be done for offboarding process from IT department ?"
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
    def __init__(self, aggregationRBAC : AggregationRBAC , userid: int , user_query: str = None ,include_collections: list = None , email: str = None):
        # self.llm = ChatOpenAI(model="gpt-5")
        # self.llm = ChatOpenAI(model="gpt-4-turbo") 
        self.SYSTEM_INSTRUCTIONS_MONGODB = DataContext
        # self.llm = ChatOpenAI(model="gpt-4o")
        self.llm =  LLMFactory(
                        provider="bedrock",
                        model="global.anthropic.claude-opus-4-5-20251101-v1:0",
                    ).create()
        example = oneshot_example(query=user_query) if user_query else ""
        print("+++++++++Similar Search Result: ",example,"+++++++++++++++++++++")
        print("========Inside Mongo.py for execution========")
        self.userid = userid
        self.system_message = MONGODB_AGENT_SYSTEM_PROMPT.format(
                                top_k=50, 
                                example=example ,
                                userinfo = {"employee code" : self.userid} ,
                                CANONICAL_REGIONS = CANONICAL_REGIONS,
                                CANONICAL_DEPARTMENTS = CANONICAL_DEPARTMENTS,
                                CANONICAL_GRADES = CANONICAL_GRADES,
                                BASE_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["base_report"],
                                OFFBOARDING_CHECKLIST_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["offboarding_checklist"],
                                LEAVE_TRANSACTION_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["leave_transaction_with_balance_report"],
                                PERFORMANCE_GOAL_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["performance_goal_report_2025_2026"],
                                GOAL_SETTING_STATUS_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["goal_setting_status"],
                                PERMORMANCE_RATING_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["permormance_rating_report"],
                                PIP_TRANSACTION_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["pip_transaction_report"],
                                PMS_TASK_STATUS_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["pms_task_status_report_all"],
                                # PMS_Q2_25_26_RATING_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["pms_q2_25_26_rating_report_all"],
                                PERFORMANCE_360_DEGREE_FEEDBACK_PARTICIPANTS_STATUS_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["performance_360_degree_feedback_participants_status_all"],
                                HISTORICAL_RATINGS_AND_OTHER_INFORMATION_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["historical_ratings_and_other_information"],
                                GOAL_DETAIL_REPORT_DESCRIPTION = self.SYSTEM_INSTRUCTIONS_MONGODB["goal_detail_report"],
                            )
        self.pii_masker = FieldBasedPIIMasker()
        self.aggregationRBAC = aggregationRBAC
        self.db_wrapper = MongoDBDatabasePIIToolkit.from_connection_string(
            MONGODB_URI,
            database=DB_NAME,
            schema= "./json_repo/mongo_schema_report.json",
            pii_masker=self.pii_masker,
            aggregationRBAC= self.aggregationRBAC,
            include_collections= include_collections
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
    
    # def _load_SystemPrompt(self, schema_path: str):
    #     with open(schema_path, "r") as f:
    #         self.SYSTEM_INSTRUCTIONS_MONGODB = json.load(f)

    def get_mongo_prompt(self):
        return self.system_message

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
        masked_query, _ = self.pii_masker.mask({"query": query})
        masked_text = masked_query["query"]

        result = self.agent.invoke(
            {"messages": [("user", masked_text)]}
        )

        for msg in result["messages"]:
            self.messages.append(msg)

    def print_results(self, return_output: bool = False):
        """
        Print or return the final agent output. When `return_output=True` a dict
        is returned containing the unmasked output and the last aggregation
        pipeline (if available) from the DB toolkit.
        """
        if not self.messages:
            if return_output:
                return {"unmasked_output": "No messages to display.", "agg_pipeline": None}
            print("No messages to display.")
            return

        final_output = self.messages[-1].content
        unmasked_output = self.pii_masker.unmask({"content": final_output})["content"]

        # Try to obtain the last pipeline from the DB wrapper if present
        agg_pipeline = getattr(self.db_wrapper, "last_agg_pipeline", None)

        print("===="*10,"Mongo.py",'===='*10)
        print(unmasked_output,"\n",agg_pipeline)
        print("Type of agg_pipeline",type(agg_pipeline))
        print("===="*20)

        agg_pipeline.append(unmasked_output)
        if return_output:
            return {"unmasked_output": unmasked_output, "agg_pipeline": agg_pipeline}

        # default behaviour: print unmasked output
        

if __name__ == "__main__":
    aggregationRBAC = AggregationRBAC(
                    user={"isHR" : False,
                            "employeeCode" : 7207,
                            "region" : [],
                            "department" : [],
                            "grades" : []
                        }
                    )
    converter = NaturalLanguageToMQL(aggregationRBAC=aggregationRBAC , userid = 7207 , email="Shayanta.Chaudhuri@tataplay.com")
    print(converter.get_mongo_prompt())
    # converter.convert_to_mql_and_execute_query(NATURAL_LANGUAGE_QUERY)
    # converter.print_results()