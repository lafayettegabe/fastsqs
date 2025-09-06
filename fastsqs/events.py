from pydantic import BaseModel, model_validator
from typing import Any, Dict, Optional, Set
import re


class SQSEvent(BaseModel):
    
    @model_validator(mode='before')
    @classmethod
    def normalize_field_names(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
            
        model_fields = set()
        if hasattr(cls, 'model_fields'):
            model_fields = set(cls.model_fields.keys())
        
        normalized_data = dict(data)
        
        for field_name in model_fields:
            if field_name not in normalized_data:
                parts = field_name.split('_')
                if len(parts) > 1:
                    camel_case = parts[0] + ''.join(word.capitalize() for word in parts[1:])
                    if camel_case in normalized_data:
                        normalized_data[field_name] = normalized_data[camel_case]
                        continue
                
                field_normalized = field_name.lower().replace('_', '').replace('-', '')
                for key in data:
                    key_normalized = key.lower().replace('_', '').replace('-', '')
                    if key != field_name and key_normalized == field_normalized:
                        normalized_data[field_name] = normalized_data[key]
                        break
        
        return normalized_data
    
    @classmethod
    def get_message_type(cls) -> str:
        name = cls.__name__
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    
    @classmethod
    def get_message_type_variants(cls) -> Set[str]:
        base_name = cls.__name__
        
        variants = set()
        
        variants.add(base_name)
        
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', base_name).lower()
        variants.add(snake_case)
        
        camel_case = base_name[0].lower() + base_name[1:] if base_name else ""
        variants.add(camel_case)
        
        kebab_case = re.sub(r'(?<!^)(?=[A-Z])', '-', base_name).lower()
        variants.add(kebab_case)
        
        variants.add(base_name.lower())
        
        variants.add(base_name.upper())
        
        return variants
    
    @classmethod
    def from_sqs_record(cls, record: Dict[str, Any]) -> "SQSEvent":
        import json
        body = json.loads(record.get("body", "{}"))
        return cls.model_validate(body)
