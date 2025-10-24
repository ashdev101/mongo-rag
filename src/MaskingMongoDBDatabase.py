from JSONPIIMasker import JSONPIIMasker
from langchain_mongodb.agent_toolkit import MongoDBDatabase

class MaskingMongoDBDatabase(MongoDBDatabase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.masker = JSONPIIMasker()

    def _find(self, collection_name, filter, projection=None, sort=None, limit=None):
        # Call the original _find method to get results
        results = super()._find(collection_name, filter, projection, sort, limit)

        # Mask each document's PII before returning
        masked_results = []
        for doc in results:
            masked_doc, _ = self.masker.mask(doc)
            masked_results.append(masked_doc)
        return masked_results
