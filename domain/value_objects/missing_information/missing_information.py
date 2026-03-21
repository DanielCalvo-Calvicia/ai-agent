
from dataclasses import dataclass
import json

from .field import Field, create_field
from .why_needed import WhyNeeded, create_why_needed
from .blocking import Blocking, create_blocking

schema_path = "schema/response/missing_information/missing_information.schema.json"
schema_base_path = "schema/response/missing_information/missing_information.base.schema.json"
schema_item_path = "schema/response/missing_information/missing_information.item.schema.json"


@dataclass(frozen=True)
class MissingInformation:
    field: Field
    why_needed: WhyNeeded
    blocking: Blocking
        
    def get_field(self):
        return self.field.get_value()
    def get_why_needed(self):
        return self.why_needed.get_value()
    def get_blocking(self):
        return self.blocking.get_value()
        
        
def create_missing_information(field_value: str, why_needed_value: str, blocking_value: str):
    field = create_field(field_value)
    why_needed = create_why_needed(why_needed_value)
    blocking = create_blocking(blocking_value)
    missing_information = MissingInformation(field, why_needed, blocking)
    return missing_information

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_base_schema():
    # Load the base schema from your local file
    with open(schema_base_path + "missing_information.base.schema.json", 'r') as f:
        base_schema_dic = json.load(f)
    return base_schema_dic

def get_item_schema():
    # Load the item schema from your local file
    with open(schema_item_path, 'r') as f:
        item_schema_dic = json.load(f)
    return item_schema_dic