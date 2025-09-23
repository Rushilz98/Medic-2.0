import os
import json
import joblib
import numpy as np
import warnings
from flask import Flask, render_template, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv  # Add this import for .env support

# Load environment variables from .env file
load_dotenv()

# Set up Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key')

# ===========================
# SUPPRESS WARNINGS
# ===========================
warnings.filterwarnings('ignore')

# ===========================
# LOAD THE TRAINED MODEL
# ===========================
try:
    # Load your trained model
    model_data = joblib.load('comprehensive_disease_diagnosis_model.pkl')
    
    # Extract model components
    tier1_model = model_data['tier1_model']
    tier2_model = model_data['tier2_model']
    le = model_data['label_encoder']
    symptoms = model_data['symptoms']
    category_map = model_data['disease_category_map']
    
    print("✅ Model loaded successfully!")
    print(f"Can diagnose {len(le.classes_)} disease conditions")
    print(f"Using {len(symptoms)} symptoms for diagnosis")
    
except FileNotFoundError:
    print("❌ ERROR: Model file not found. Please ensure 'comprehensive_disease_diagnosis_model.pkl' exists in current directory.")
    # In production, you'd want to handle this more gracefully
    tier1_model = None
    tier2_model = None
    le = None
    symptoms = []
    category_map = {}
except Exception as e:
    print(f"❌ ERROR loading model: {str(e)}")
    tier1_model = None
    tier2_model = None
    le = None
    symptoms = []
    category_map = {}

# ===========================
# SYMPTOM OUTPUT SCHEMA
# ===========================
class SymptomOutput(BaseModel):
    symptoms: list[str] = Field(description="List of exact symptom names matched from the predefined list")

# ===========================
# SYMPTOM MAPPER USING LLM
# ===========================
def create_symptom_mapper():
    """Creates a chain that maps natural language symptoms to exact symptom names"""
    
    # Get Google API key from environment (loaded from .env)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Google API key not configured. Please set GOOGLE_API_KEY in your .env file")
    
    # Create the prompt template
    prompt_template = """You are a medical symptom mapper. Your task is to convert casual descriptions of health symptoms into EXACT symptom names from the predefined medical list below. 

STRICT INSTRUCTIONS:
1. Analyze the user's message for health symptoms
2. Map each symptom ONLY to the EXACT symptom names listed below
3. EACH SYMPTOM NAME IS A COMPLETE KEYWORD - DO NOT BREAK IT INTO PARTS OR MODIFY IT
4. If a symptom doesn't have an EXACT match in the list, OMIT it completely
5. NEVER invent, modify, or approximate symptom names
6. Return ONLY a JSON object with key "symptoms" containing matched symptom names
7. DO NOT include any explanations, greetings, or additional text - ONLY the JSON

ACCEPTABLE SYMPTOM NAMES (USE EXACTLY THESE - EACH IS A COMPLETE KEYWORD):
{symptoms}

Example input: "I've been having trouble catching my breath and my chest feels tight"
Example output: {{"symptoms": ["shortness of breath", "chest tightness"]}}

Example input: "I feel dizzy and I can't sleep well at night"
Example output: {{"symptoms": ["dizziness", "insomnia"]}}

Example input: "My heart is racing and I feel anxious"
Example output: {{"symptoms": ["increased heart rate", "anxiety and nervousness"]}}

Example input: "I've got chest pain that's really sharp"
Example output: {{"symptoms": ["sharp chest pain"]}}

Example input: "I feel really tired all the time"
Example output: {{"symptoms": ["fatigue"]}}

Now process this input:
{user_input}"""

    # Set up the prompt
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["user_input", "symptoms"]
    )
    
    # Initialize the Gemini model
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest",
        temperature=0.1,
        convert_system_message_to_human=True,
        google_api_key=api_key
    )
    
    # Set up the output parser
    output_parser = JsonOutputParser(pydantic_object=SymptomOutput)
    
    # Create the chain
    chain = prompt | llm | output_parser
    
    return chain

def map_symptoms(user_input):
    """Map casual symptom descriptions to exact symptom names using LLM"""
    
    # Format the symptoms list for the prompt
    symptoms_str = ", ".join([f'"{symptom}"' for symptom in symptoms])
    
    try:
        # Get Google API key from environment (loaded from .env)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
            
        if not api_key:
            return {"symptoms": [], "error": "Google API key is missing. Please set GOOGLE_API_KEY in your .env file"}
        
        # Create the symptom mapper chain
        symptom_mapper = create_symptom_mapper()
        
        # Get the mapped symptoms
        result = symptom_mapper.invoke({
            "user_input": user_input,
            "symptoms": symptoms_str
        })
        
        # Filter to ensure only valid symptoms are returned
        valid_symptoms = [symptom for symptom in result["symptoms"] if symptom in symptoms]
        
        return {"symptoms": valid_symptoms}
    except Exception as e:
        return {"symptoms": [], "error": str(e)}

# ===========================
# DISEASE PREDICTION FUNCTION
# ===========================
def predict_disease(symptoms_input, top_n=3):
    """
    Predict diseases based on symptoms
    
    Args:
        symptoms_input: List of symptom names
        top_n: Number of top predicted diseases to show
    
    Returns:
        List of top predicted diseases with confidence
    """
    if not symptoms_input or not symptoms or tier2_model is None or le is None:
        return []
    
    # Convert input to standard format
    patient = np.zeros(len(symptoms))
    
    for symptom in symptoms_input:
        if symptom in symptoms:
            idx = list(symptoms).index(symptom)
            patient[idx] = 1
    
    # Get probabilities from Tier 2 model
    tier2_proba = tier2_model.predict_proba([patient])[0]
    
    # Get top predictions
    top_indices = np.argsort(tier2_proba)[::-1][:top_n]
    results = []
    
    for idx in top_indices:
        disease = le.classes_[idx]
        confidence = tier2_proba[idx]
        
        # Format disease name (remove technical terms)
        display_name = category_map.get(disease, disease)
        display_name = display_name.replace('_rare_variant', ' (rare variant)')
        
        # Check if critical
        critical_terms = ['heart attack', 'stroke', 'sepsis', 'meningitis', 'pulmonary embolism', 
                         'cancer', 'tumor', 'acute', 'severe', 'emergency']
        is_critical = any(term in display_name.lower() for term in critical_terms)
        
        results.append({
            "disease": display_name,
            "confidence": float(confidence),
            "is_critical": is_critical
        })
    
    return results

# ===========================
# FLASK ROUTES
# ===========================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route('/api/map_symptoms', methods=['POST'])
def api_map_symptoms():
    data = request.json
    user_input = data.get('symptoms', '')
    
    if not user_input:
        return jsonify({"error": "No symptoms provided"}), 400
    
    result = map_symptoms(user_input)
    return jsonify(result)

@app.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.json
    symptoms = data.get('symptoms', [])
    
    if not symptoms:
        return jsonify({"error": "No symptoms provided"}), 400
    
    predictions = predict_disease(symptoms)
    return jsonify({"predictions": predictions})

if __name__ == '__main__':
    # Check if GOOGLE_API_KEY is set
    if not os.getenv("GOOGLE_API_KEY"):
        print("\n⚠️ WARNING: GOOGLE_API_KEY not found in environment variables!")
        print("Get an API key from: https://aistudio.google.com/app/apikey\n")
    
    # Get port from environment - Render sets this automatically
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app with proper production settings
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False  # Never run debug=True in production
    )