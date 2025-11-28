from typing import List, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Medical Condition Scoring API", version="1.0.0")

class MedicalConditionScorer:
    def __init__(self, csv_path="data/2025 Midyear_Final ICD-10-CM Mappings.csv"):
        self.conditions = {}
        try:
            self._load_conditions(csv_path)
        except FileNotFoundError:
            pass
    
    def _load_conditions(self, csv_path):
        with open(csv_path, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                if line_num == 1:
                    continue
                
                parts = self._parse_csv_line(line.strip())
                if len(parts) > 7 and parts[0] and parts[1]:
                    code = parts[0].replace('"', '').strip()
                    desc = parts[1].replace('"', '').strip()
                    hcc_v28 = parts[6].strip() if len(parts) > 6 else ''
                    
                    self.conditions[code] = {
                        'description': desc,
                        'raf_score': self._get_raf_score(hcc_v28)
                    }
    
    def _parse_csv_line(self, line):
        parts = []
        current = ""
        in_quotes = False
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(current.strip())
                current = ""
            else:
                current += char
        parts.append(current.strip())
        return parts
    
    def _get_raf_score(self, hcc_value):
        if not hcc_value:
            return 0.1
        try:
            hcc_num = int(hcc_value)
            raf_mapping = {
                1: 0.80, 2: 0.65, 6: 0.45, 8: 0.25, 9: 0.35,
                10: 0.40, 11: 0.30, 12: 0.28, 17: 0.60, 18: 0.55,
                19: 0.38, 20: 0.42, 21: 0.32, 22: 0.30, 23: 0.70,
                29: 0.45, 33: 0.35, 36: 0.40, 37: 0.38, 38: 0.35,
                39: 0.32, 43: 0.35, 46: 0.48, 47: 0.42, 48: 0.38,
                52: 0.45, 54: 0.38, 55: 0.35, 56: 0.38, 65: 0.40,
                72: 0.38, 75: 0.35, 78: 0.32, 85: 0.42, 92: 0.32,
                93: 0.30, 95: 0.38, 96: 0.35, 98: 0.35, 99: 0.38,
                100: 0.32, 106: 0.35, 108: 0.38, 109: 0.42, 111: 0.35,
                112: 0.38, 114: 0.45, 115: 0.40, 127: 0.38, 141: 0.35,
                155: 0.35, 158: 0.32, 168: 0.28, 182: 0.35, 186: 0.38,
                202: 0.45, 227: 0.40, 263: 0.35, 280: 0.38, 282: 0.42,
                283: 0.35, 387: 0.28, 395: 0.38, 454: 0.45
            }
            return raf_mapping.get(hcc_num, 0.1)
        except ValueError:
            return 0.1
    
    def find_condition_by_name(self, condition_names: List[str]) -> List[Dict]:
        matched_conditions = []
        
        for condition_name in condition_names:
            condition_lower = condition_name.lower()
            
            matches = [code for code, data in self.conditions.items() 
                      if condition_lower in data['description'].lower()]
            
            for match in matches[:3]:
                matched_conditions.append({
                    'raf_score': self.conditions[match]['raf_score']
                })
        
        return matched_conditions
    
    def calculate_medical_score(self, condition_names: List[str], age: int) -> float:
        if age < 30:
            age_score = 5
        elif age < 45: 
            age_score = 10
        elif age < 60:
            age_score = 15
        elif age < 75:
            age_score = 18
        else:
            age_score = 20
        
        conditions = self.find_condition_by_name(condition_names)
        
        if not conditions:
            return round(age_score, 1)
        
        highest_raf = max(condition['raf_score'] for condition in conditions)
        condition_score = min(highest_raf * 100, 80)
        total_score = age_score + condition_score
        
        return round(total_score, 1)

scorer = None
try:
    scorer = MedicalConditionScorer()
except:
    scorer = None

class ScoringInput(BaseModel):
    age: int
    conditions: List[str]

@app.post("/score")
async def score_medical_needs(input_data: ScoringInput):
    if not scorer or not scorer.conditions:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    score = scorer.calculate_medical_score(input_data.conditions, input_data.age)
    return {"score": score}

@app.get("/health")
async def health():
    if not scorer or not scorer.conditions:
        raise HTTPException(status_code=503, detail="Service unavailable")
    return {"status": "healthy", "conditions_loaded": len(scorer.conditions)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)