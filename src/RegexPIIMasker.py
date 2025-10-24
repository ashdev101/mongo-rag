import re
from typing import Any, Dict, Tuple

import re
from typing import Any, Dict, Tuple

PII_FIELDS = [
    "employee code",
    "first name",
    "last name",
    "primary email",
]

class FieldBasedPIIMasker:
    def __init__(self):
        self.mapping: Dict[str, str] = {}
        self.counter: Dict[str, int] = {}

    def mask(self, data: Any) -> Tuple[Any, Dict[str, str]]:
        """Mask PII in JSON-like dict or list."""
        self.mapping = {}
        self.counter = {}
        masked = self._mask_recursive(data)
        return masked, self.mapping

    def unmask(self, data: Any) -> Any:
        """Restore original values from masked text or JSON."""
        return self._unmask_recursive(data)

    def _mask_recursive(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._mask_value(k, v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._mask_recursive(item) for item in obj]
        else:
            return obj

    def _mask_value(self, key: str, value: Any) -> Any:
        if isinstance(value, dict):
            return self._mask_recursive(value)
        elif isinstance(value, list):
            return [self._mask_value(key, v) for v in value]
        elif key.lower() in PII_FIELDS:
            label = key.title()  # e.g., "First Name"
            token = self._get_mask_token(label)
            self.mapping[token] = str(value)
            return token
        else:
            return value

    def _get_mask_token(self, label: str) -> str:
        count = self.counter.get(label, 0)
        token = f"[{label} {count}]"
        self.counter[label] = count + 1
        return token

    def _unmask_recursive(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._unmask_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._unmask_recursive(item) for item in obj]
        elif isinstance(obj, str):
            for token, original in self.mapping.items():
                obj = re.sub(re.escape(token), original, obj)
            return obj
        else:
            return obj




# json_data =  [
#     {
#         "Employee Code": 1,
#         "FIRST NAME": "John",
#         "LAST NAME": "Doe",
#         "GRADE": "M0",
#         "Grade Level": "M.0",
#         "Designation": "Managing Director and CEO",
#         "DEPARTMENT": "Executive Office",
#         "SUB-DEPT": "Executive Office - General",
#         "Location": "Mumbai",
#         "Office": "Corporate",
#         "Region": "Corporate",
#         "DOJ": "22-03-2004",
#         "State": "Maharashtra",
#         "DOB": "17-09-1950",
#         "M/F": "Male",
#         "Primary Email": "john.doe@email.com",
#         "Assignment Status Type": "INACTIVE",
#         "DOR": "31-12-2010",
#         "DOL": "31-12-2010"
#     },
#     {
#         "Employee Code": 2,
#         "FIRST NAME": "Jane",
#         "LAST NAME": "Smith",
#         "GRADE": "M1",
#         "Grade Level": "M.1",
#         "Designation": "Chief Financial Officer",
#         "DEPARTMENT": "Finance",
#         "SUB-DEPT": "Accounts and Finance",
#         "Location": "Bangalore",
#         "Office": "Corporate",
#         "Region": "Corporate",
#         "DOJ": "15-07-2008",
#         "State": "Karnataka",
#         "DOB": "12-05-1975",
#         "M/F": "Female",
#         "Primary Email": "jane.smith@email.com",
#         "Assignment Status Type": "ACTIVE",
#         "DOR": "",
#         "DOL": ""
#     }
# ]

# # print("Original JSON:\n", json_data)

# masker = FieldBasedPIIMasker()

# masked_json, mapping = masker.mask(json_data)
# print("🔒 Masked JSON:\n", masked_json)
# print("\n🗺️ Mapping:\n", mapping)

# unmasked_json = masker.unmask(masked_json)
# print("\n🔓 Unmasked JSON:\n", unmasked_json)