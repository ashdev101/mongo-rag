from langchain_mongodb.agent_toolkit import (
    MONGODB_AGENT_SYSTEM_PROMPT,
    MongoDBDatabase,
)
from bson.json_util import dumps
import json
from RegexPIIMasker import FieldBasedPIIMasker
from typing import Any, Dict, List, Optional , Union , Iterable
from pymongo.cursor import Cursor
from pymongo import MongoClient
import pathlib
from aggregation.AggregationRBAC import AggregationRBAC


class MongoDBDatabasePIIToolkit(MongoDBDatabase):
    """MongoDBDatabaseToolkit with """

    def _load_local_schema(self, schema_path: str):
        with open(schema_path, "r") as f:
            self._local_schema = json.load(f)

    def __init__(
        self,
        client: MongoClient,
        database: str,
        pii_masker: FieldBasedPIIMasker,
        aggregationRBAC : AggregationRBAC,
        schema: Optional[str] = None,
        ignore_collections: Optional[List[str]] = None,
        include_collections: Optional[List[str]] = None,
        sample_docs_in_collection_info: int = 3,
        indexes_in_collection_info: bool = False,
    ):
        super().__init__(
            client,
            database,
            schema,
            ignore_collections,
            include_collections,
            sample_docs_in_collection_info,
            indexes_in_collection_info,
        )
        self.piiMasker = pii_masker
        self._local_schema = None
        self.aggregationRBAC = aggregationRBAC
        if schema:        # <--- schema argument contains path to schema.json
            self._load_local_schema(schema)
    # overridde the _get_sample_docs method to add PII masking

    def _get_sample_docs(self, collection: str) -> str:
        if self._local_schema and collection in self._local_schema:
            samples = self._local_schema[collection].get("samples", [])
            samples, _ = self.piiMasker.mask(samples)
            return f"{len(samples)} sample documents from {collection} collection:\n{dumps(samples, indent=2)}"
        return super()._get_sample_docs(collection)
    
    def get_usable_collection_names(self) -> Iterable[str]:
        if self._local_schema:
            if self._include_colls:
               return sorted(self._include_colls)
            return sorted(list(self._local_schema.keys()))
        return super().get_usable_collection_names()

    # def _get_sample_docs(self, collection: str) -> str:
    #     col = self._db[collection]
    #     docs = list(col.find({}, limit=self._sample_docs_in_coll_info))
    #     for doc in docs:
    #         self._elide_doc(doc)
    #     docs, _ = self.piiMasker.mask(docs)
    #     # print("sample docs in coll info" ,self._sample_docs_in_coll_info)
    #     # print("sample docs",docs)
    #     return (
    #         f"{self._sample_docs_in_coll_info} documents from {collection} collection:\n"
    #         f"{dumps(docs, indent=2)}"
    #     )
    
    def _get_collection_schema(self, collection: str) -> str:
        if self._local_schema and collection in self._local_schema:
            fields_dict = self._local_schema[collection]["fields"]

            lines = []
            for field, dtype in fields_dict.items():

                # if type is list → merge using |
                if isinstance(dtype, list):
                    dtype_str = " | ".join(dtype)
                else:
                    dtype_str = dtype

                lines.append(f"{field} : {dtype_str}")

            return "\n".join(lines)

        # fallback to parent handler
        return super()._get_collection_schema(collection)

    
    def _get_collection_indexes(self, collection: str) -> str:
        if self._local_schema and collection in self._local_schema:
            indexes = self._local_schema[collection].get("indexes", [])
            return f"Collection Indexes:\n{json.dumps(indexes, indent=2)}"
        return super()._get_collection_indexes(collection)
    
    def run(self, command: str) -> Union[str, Cursor]:
        """Execute a MongoDB aggregation command and return a string representing the results.

        If the statement returns documents, a string of the results is returned.
        If the statement returns no documents, an empty string is returned.

        The command MUST be of the form: `db.collectionName.aggregate(...)`.
        """
        if not command.startswith("db."):
            raise ValueError(f"Cannot run command {command}")

        try:
            col_name = command.split(".")[1]
        except IndexError as e:
            raise ValueError(
                "Invalid command format. Could not extract collection name."
            ) from e

        if col_name not in self.get_usable_collection_names():
            raise ValueError(f"Collection {col_name} does not exist!")

        if ".aggregate(" not in command:
            raise ValueError("Only aggregate(...) queries are currently supported.")

        # Parse pipeline using helper
        agg_pipeline = self._parse_command(command)

        try:
            coll = self._db[col_name]
            print("==="*10,"MongoDBDatabaseToolkitPii.py","==="*10)
            print("Collection Name:",col_name)
            print("===="*20)
            print("Aggregation Pipeline 1 :" , agg_pipeline)
            print("===="*20)
            agg_pipeline = self.aggregationRBAC.enforce(agg_pipeline)
            result = coll.aggregate(agg_pipeline)
            result_list = list(result)
            # print("Aggregation Result:" , result_list)
            masked_result, mapping = self.piiMasker.mask(result_list)
            # print("Masked Aggregation Result:" , masked_result)
            # Return a JSON object containing both the masked results and the
            # aggregation pipeline so that it can be used in the feedback mechanism
            print("===="*20)
            print("Aggregation Pipeline 2 :" , agg_pipeline)
            print("===="*20)
            # Save the last aggregation pipeline on the instance so callers
            # (e.g. the outer code in `Mongo.py`) can access it after execution.
            try:
                self.last_agg_pipeline = agg_pipeline
            except Exception:
                # Be defensive: if assignment fails for any reason, continue
                # but do not block returning results.
                pass
            agg_pipeline.append(col_name)
            return json.dumps(
                {
                    
                    "masked_results": masked_result,
                    "agg_pipeline": agg_pipeline,
                },
                default=str,
                indent=2,
            )
        except Exception as e:
            # print("Error executing aggregation:", e)
            raise ValueError(f"Error executing aggregation: {e}") from e
        
if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    app_dir = os.path.join(os.getcwd())
    load_dotenv(os.path.join(app_dir, ".env"))
  
    MONGODB_URI = os.getenv('MONGODB_URI')

    client = MongoClient(MONGODB_URI)
    db = MongoDBDatabasePIIToolkit(
        client,
        pii_masker=FieldBasedPIIMasker(),
        database="hr-cleaned",
        schema= "./json_repo/mongo_schema_report.json", 
        sample_docs_in_collection_info=2,
        indexes_in_collection_info=False,
        include_collections=["base_report" , "pms_q2_25_26_rating_report_all"]
    )

    print(db.get_collection_info())  # Should print the collection names in the 'testdb' database
        

