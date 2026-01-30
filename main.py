from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from difflib import SequenceMatcher
import google.generativeai as genai
import os
import json

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

app = FastAPI(title="Medical Condition Scoring API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

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
    
    def _fuzzy_match_score(self, search_term: str, description: str) -> float:
        search_lower = search_term.lower()
        desc_lower = description.lower()
        
        # Exact substring match
        if search_lower in desc_lower:
            return 1.0
        
        # Word-level matching
        search_words = search_lower.split()
        desc_words = desc_lower.split()
        
        max_score = 0.0
        for search_word in search_words:
            for desc_word in desc_words:
                # Fuzzy match each word
                ratio = SequenceMatcher(None, search_word, desc_word).ratio()
                if ratio > max_score:
                    max_score = ratio
        
        return max_score
    
    def find_condition_by_name(self, condition_names: List[str]) -> List[Dict]:
        matched_conditions = []
        
        for condition_name in condition_names:
            scored_matches = []
            
            for code, data in self.conditions.items():
                match_score = self._fuzzy_match_score(condition_name, data['description'])
                
                # Accept matches with score >= 0.75 (75% similarity)
                if match_score >= 0.75:
                    scored_matches.append({
                        'code': code,
                        'raf_score': data['raf_score'],
                        'match_score': match_score
                    })
            
            # Sort by match quality and take top 5
            scored_matches.sort(key=lambda x: x['match_score'], reverse=True)
            
            for match in scored_matches[:5]:
                matched_conditions.append({
                    'raf_score': match['raf_score']
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

class AnalysisInput(BaseModel):
    drug_name: Optional[str] = None
    manufacturer: Optional[str] = None
    quantity: Optional[str] = None
    tests: Optional[List[str]] = None
    additional_info: Optional[str] = None

@app.post("/analyze")
async def analyze_medical_data(input_data: AnalysisInput):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    # Build analysis prompt
    prompt = """You are an expert medical AI assistant. Analyze the provided medical data using your medical knowledge and provide accurate predictions and analysis.

IMPORTANT: All responses must be based on your AI medical knowledge and predictions. Do not use placeholder data.

Input Data:
"""
    
    if input_data.drug_name:
        prompt += f"Drug Name: {input_data.drug_name}\n"
    if input_data.manufacturer:
        prompt += f"Manufacturer: {input_data.manufacturer}\n"
    if input_data.quantity:
        prompt += f"Quantity: {input_data.quantity}\n"
    if input_data.tests:
        prompt += f"Tests: {', '.join(input_data.tests)}\n"
    if input_data.additional_info:
        prompt += f"Additional Info: {input_data.additional_info}\n"
    
    prompt += """\n
Analyze this medical data using your expert medical knowledge and provide accurate, evidence-based predictions in this exact JSON format:
{
  "medical_conditions": ["actual predicted conditions based on the drug/tests"],
  "refill_frequency": "actual predicted frequency based on medical knowledge",
  "treatment_duration": "actual duration based on medical condition (if chronic: describe as long-term/lifelong, if not chronic: specify in months only)",
  "is_chronic": actual_boolean_based_on_medical_condition,
  "consultation_needed": actual_boolean_if_doctor_consultation_required,
  "lab_tests_needed": ["specific lab tests required"],
  "diagnostics_needed": ["imaging or diagnostic procedures required"],
  "medication_assessment": "evaluation of current medication effectiveness and safety",
  "pricing_ksh": {
    "medications": {
      "only_for_drugs_provided_by_user": "price_in_ksh_only_if_drug_name_given"
    },
    "consultation_cost": actual_consultation_price_in_kenyan_shillings,
    "total_cost": sum_of_consultation_and_medication_costs_only
  }
}

Provide real medical analysis with accurate Kenyan healthcare pricing, not generic responses. Return only valid JSON, no additional text."""
    
    model = genai.GenerativeModel('models/gemini-2.5-flash')
    response = model.generate_content(prompt)
    
    # Clean the response text
    response_text = response.text.strip()
    
    # Remove markdown code blocks if present
    if response_text.startswith('```json'):
        response_text = response_text[7:]
    if response_text.startswith('```'):
        response_text = response_text[3:]
    if response_text.endswith('```'):
        response_text = response_text[:-3]
    
    response_text = response_text.strip()
    
    return json.loads(response_text)

@app.get("/debug-env")
async def debug_environment():
    """Debug endpoint to check environment variables"""
    return {
        "gemini_key_exists": bool(os.getenv("GEMINI_API_KEY")),
        "gemini_key_length": len(os.getenv("GEMINI_API_KEY", "")),
        "all_env_keys": list(os.environ.keys())
    }

@app.get("/models")
async def list_available_models():
    """Debug endpoint to check available Gemini models"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not set in environment variables"}
    
    try:
        models = []
        for model in genai.list_models():
            models.append({
                "name": model.name,
                "supported_methods": model.supported_generation_methods
            })
        return {"api_key_status": "configured", "total_models": len(models), "models": models}
    except Exception as e:
        return {"error": f"Failed to list models: {str(e)}", "api_key_status": "configured" if api_key else "missing"}

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